import importlib.util
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

    def _make_output_root(self):
        base = Path.home() / "FioBenchmark" / "resultados"
        base.mkdir(parents=True, exist_ok=True)

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session = base / f"{stamp}_{uuid.uuid4().hex[:6]}"
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

    def run(self):
        check_benchmark_dependencies()

        from bench_fio import main as bench_fio_main

        target_root = self._validate_target()
        output_root = self._make_output_root()

        target_workdir = (
            target_root / f".fio_benchmark_tmp_{uuid.uuid4().hex[:8]}"
        )
        target_workdir.mkdir(parents=False, exist_ok=False)

        command = self._build_command(target_workdir, output_root)

        try:
            with bench_fio_compatibility():
                return_code, output = run_embedded_cli(
                    "bench-fio",
                    bench_fio_main,
                    command[1:],
                )
        except Exception as exc:
            raise BenchmarkError(
                "Não foi possível executar o bench-fio:\n" + str(exc)
            ) from exc
        finally:
            shutil.rmtree(target_workdir, ignore_errors=True)

        if return_code != 0:
            details = output.strip() or "bench-fio terminou sem mensagem."
            raise BenchmarkError(
                "O benchmark falhou.\n\n"
                f"Detalhes:\n{details[-4000:]}"
            )

        json_files = list(output_root.rglob("*.json"))
        if not json_files:
            raise BenchmarkError(
                "O bench-fio terminou, mas nenhum arquivo JSON foi encontrado "
                "na pasta de resultados."
            )

        return BenchmarkResult(
            output_root=output_root,
            target_workdir=target_workdir,
            command=command,
            stdout=output.strip(),
        )
