import importlib.util
import json
import os
import platform
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from bench_compat import bench_fio_compatibility
from embedded_cli import run_embedded_cli
from runtime_tools import configure_runtime_environment, find_fio


class BenchmarkError(RuntimeError):
    pass


@dataclass
class BenchmarkResult:
    output_root: Path
    target_workdir: Path
    command: list[str]
    stdout: str


def check_benchmark_dependencies():
    fio_path = configure_runtime_environment()

    if fio_path is None or find_fio() is None:
        raise BenchmarkError(
            "O FIO não foi encontrado.\n\n"
            "No aplicativo instalado ele deve vir incluído no próprio pacote. "
            "Em modo de desenvolvimento, instale o FIO no sistema."
        )

    if importlib.util.find_spec("bench_fio") is None:
        raise BenchmarkError(
            "O módulo bench_fio não foi encontrado.\n\n"
            "Em modo de desenvolvimento, execute:\n"
            "pip install -r requirements.txt"
        )


def _io_engine():
    system = platform.system().lower()

    if system == "windows":
        return "windowsaio"
    if system == "linux":
        return "libaio"
    if system == "darwin":
        return "posixaio"

    return "sync"


def _validate_json_results(output_root):
    json_files = list(Path(output_root).rglob("*.json"))

    if not json_files:
        raise BenchmarkError(
            "O benchmark terminou, mas nenhum arquivo JSON foi gerado."
        )

    invalid = []

    for file in json_files:
        try:
            if file.stat().st_size == 0:
                invalid.append(f"{file} — arquivo vazio")
                continue

            with file.open("r", encoding="utf-8-sig") as handle:
                json.load(handle)

        except (OSError, json.JSONDecodeError) as exc:
            invalid.append(f"{file} — {exc}")

    if invalid:
        details = "\n".join(invalid[:10])
        raise BenchmarkError(
            "O FIO gerou resultado JSON inválido. O gráfico não será "
            "executado com dados corrompidos.\n\n"
            f"{details}"
        )

    return json_files


class BenchmarkRunner:
    WRITE_MODES = {"write", "randwrite", "randrw", "rw", "readwrite"}

    def __init__(self, config):
        self.config = config

    def _validate_target(self):
        target = Path(self.config["target_root"]).expanduser().resolve()

        if not target.is_dir():
            raise BenchmarkError("A pasta escolhida para o teste não existe.")

        if not os.access(target, os.W_OK):
            raise BenchmarkError(
                "A aplicação não possui permissão para escrever na pasta escolhida."
            )

        max_jobs = max(self.config["numjobs"])
        required_bytes = self.config["size_mb"] * max_jobs * 1024 * 1024
        required_with_margin = int(required_bytes * 1.10)

        free_bytes = shutil.disk_usage(target).free

        if free_bytes < required_with_margin:
            required_gb = required_with_margin / (1024 ** 3)
            free_gb = free_bytes / (1024 ** 3)

            raise BenchmarkError(
                "Não há espaço livre suficiente para o teste.\n\n"
                f"Necessário com margem: {required_gb:.2f} GB\n"
                f"Disponível: {free_gb:.2f} GB"
            )

        return target

    # Slugs curtos e estáveis para o nome da pasta de sessão
    GRAPH_SLUGS = {
        "2D — IOPS e Latência por IODepth": "2d_iops_lat",
        "3D — IOPS × IODepth × NumJobs": "3d_iops",
        "Line Chart — dados de LOG do FIO": "line_chart",
        "2D agrupado — IOPS e Latência": "2d_agrupado",
        "3D — Latência × IODepth × NumJobs": "3d_lat",
    }

    def _session_folder_name(self):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if self.config.get("generate_all"):
            slug = "todos"
        else:
            graph = self.config.get("graph", "grafico")
            slug = self.GRAPH_SLUGS.get(graph, "grafico")
        # Ex.: 2d_iops_lat_20260908_011530  ou  todos_20260908_011530
        return f"{slug}_{stamp}"

    def _make_output_root(self):
        # Pasta base: config["results_root"] se informado, senão ~/FioBenchmark/resultados
        custom = self.config.get("results_root")
        if custom:
            base = Path(custom).expanduser().resolve()
        else:
            base = Path.home() / "FioBenchmark" / "resultados"
        base.mkdir(parents=True, exist_ok=True)

        session = base / self._session_folder_name()
        # Se por acaso a pasta já existir (mesmo segundo), acrescenta sufixo curto
        if session.exists():
            session = base / f"{self._session_folder_name()}_{uuid.uuid4().hex[:4]}"
        session.mkdir(parents=True, exist_ok=False)

        return session

    def _build_command(self, target_workdir, output_root):
        cfg = self.config

        command = [
            "bench-fio",
            "--target", str(target_workdir),
            "--type", "directory",
            "--size", f"{cfg['size_mb']}M",
            "--output", str(output_root),
            "--block-size", cfg["block_size"],
            "--iodepth", *[str(v) for v in cfg["iodepths"]],
            "--numjobs", *[str(v) for v in cfg["numjobs"]],
            "--runtime", str(cfg["runtime"]),
            "--mode", cfg["mode"],
            "--engine", _io_engine(),
            "--direct", "1",
            "--loops", "1",
            "--time-based",
            "--loginterval", str(cfg["log_interval"]),
            "--create",
        ]

        if cfg["mode"] == "randrw":
            command.extend(["--rwmixread", str(cfg["readmix"])])

        if cfg["mode"] in self.WRITE_MODES:
            command.append("--destructive")

        if cfg["ramp_time"] > 0:
            command.extend(
                ["--extra-opts", f"ramp_time={cfg['ramp_time']}"]
            )

        return command

    def expected_job_count(self):
        """Quantidade de jobs FIO que o bench-fio vai disparar."""
        cfg = self.config
        # loop_items no bench-fio: target × mode × iodepth × numjobs × block_size
        # aqui usamos 1 target, 1 mode, 1 block_size
        iodepths = cfg.get("iodepths") or [1]
        numjobs = cfg.get("numjobs") or [1]
        loops = int(cfg.get("loops", 1) or 1)
        return max(1, len(iodepths) * len(numjobs) * loops)

    def estimated_seconds(self):
        """
        Estimativa grosseira de duração do benchmark.
        runtime + ramp_time por job (+ overhead ~2s por job).
        """
        cfg = self.config
        runtime = int(cfg.get("runtime") or 0)
        ramp = int(cfg.get("ramp_time") or 0)
        jobs = self.expected_job_count()
        per_job = runtime + ramp + 2
        return jobs * per_job

    def run(self, progress_callback=None, cancel_event=None):
        """
        progress_callback(done_jobs, total_jobs, message) é opcional.
        cancel_event: threading.Event — se setado, interrompe entre jobs.
        """
        check_benchmark_dependencies()

        from bench_fio import main as bench_fio_main

        target_root = self._validate_target()
        output_root = self._make_output_root()

        target_workdir = (
            target_root / f".fio_benchmark_tmp_{uuid.uuid4().hex[:8]}"
        )
        target_workdir.mkdir(parents=False, exist_ok=False)

        command = self._build_command(target_workdir, output_root)
        total_jobs = self.expected_job_count()

        def on_fio_job(done, _total_hint, benchmark):
            if cancel_event is not None and cancel_event.is_set():
                raise BenchmarkError("Benchmark cancelado pelo usuário.")
            if not progress_callback:
                return
            qd = benchmark.get("iodepth", "?")
            nj = benchmark.get("numjobs", "?")
            mode = benchmark.get("mode", "?")
            message = (
                f"Benchmark job {done}/{total_jobs}: "
                f"{mode} · IODepth={qd} · NumJobs={nj}"
            )
            progress_callback(done, total_jobs, message)

        try:
            with bench_fio_compatibility(
                progress_callback=on_fio_job,
                cancel_event=cancel_event,
            ):
                return_code, output = run_embedded_cli(
                    "bench-fio",
                    bench_fio_main,
                    command[1:],
                )
        except BenchmarkError:
            raise
        except Exception as exc:
            if cancel_event is not None and cancel_event.is_set():
                raise BenchmarkError("Benchmark cancelado pelo usuário.") from exc
            raise BenchmarkError(
                "Não foi possível executar o benchmark:\n" + str(exc)
            ) from exc
        finally:
            shutil.rmtree(target_workdir, ignore_errors=True)

        if cancel_event is not None and cancel_event.is_set():
            raise BenchmarkError("Benchmark cancelado pelo usuário.")

        if return_code != 0:
            details = output.strip() or "bench-fio terminou sem mensagem."
            if cancel_event is not None and cancel_event.is_set():
                raise BenchmarkError("Benchmark cancelado pelo usuário.")
            raise BenchmarkError(
                "O benchmark falhou.\n\n"
                f"Detalhes:\n{details[-6000:]}"
            )

        # Não basta o arquivo existir. Ele precisa ser JSON válido antes
        # de o fio-plot receber os resultados.
        _validate_json_results(output_root)

        return BenchmarkResult(
            output_root=output_root,
            target_workdir=target_workdir,
            command=command,
            stdout=output.strip(),
        )
