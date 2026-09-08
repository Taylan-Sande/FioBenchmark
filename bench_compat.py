import contextlib
import json
import os
import subprocess
import tempfile
from pathlib import Path


def _escape_fio_windows_path(path):
    """
    Escapa a letra da unidade para valores escritos dentro de um job FIO.

    C:\\Users\\Taylan\\teste
    -> C\\:\\Users\\Taylan\\teste

    O ':' é separador para certas opções do FIO, por isso precisa ser
    escapado quando aparece na letra da unidade.
    """
    value = str(path).replace("/", "\\")

    if len(value) >= 2 and value[1] == ":":
        value = value[0] + r"\:" + value[2:]

    return value


def _extract_json_payload(stdout):
    """
    Retorna somente o JSON emitido pelo FIO.

    Normalmente --output-format=json já produz JSON puro no stdout.
    O fallback entre a primeira '{' e a última '}' protege contra alguma
    mensagem textual eventual antes/depois do JSON.
    """
    text = (stdout or "").lstrip("\ufeff").strip()

    if not text:
        raise RuntimeError(
            "O FIO terminou sem produzir conteúdo JSON no stdout."
        )

    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1 or end <= start:
            preview = text[:1500]
            raise RuntimeError(
                "O FIO não produziu um JSON válido.\n\n"
                f"Início da saída do FIO:\n{preview}"
            )

        candidate = text[start:end + 1]

        try:
            json.loads(candidate)
        except json.JSONDecodeError as exc:
            preview = text[:1500]
            raise RuntimeError(
                "O FIO produziu uma saída que não pôde ser interpretada "
                "como JSON.\n\n"
                f"Erro JSON: {exc}\n\n"
                f"Início da saída do FIO:\n{preview}"
            ) from exc

        return candidate


@contextlib.contextmanager
def bench_fio_compatibility(progress_callback=None):
    """
    Compatibilidade do bench-fio + gancho de progresso por job.

    - No Windows: evita drop_caches, esconde console, grava JSON validado
      e garante .log na pasta do resultado.
    - Em qualquer SO: se progress_callback for passado, chama
      progress_callback(done, total_hint, benchmark) após cada job FIO.
      total_hint pode ser None se ainda desconhecido.
    """
    from bench_fio.benchlib import runfio

    original_run_fio = runfio.run_fio
    original_drop_caches = getattr(runfio, "drop_caches", None)
    original_subprocess_run = subprocess.run

    job_counter = {"done": 0}

    def notify_progress(benchmark):
        if not progress_callback:
            return
        job_counter["done"] += 1
        try:
            progress_callback(job_counter["done"], None, benchmark)
        except Exception:
            pass

    # ---- Windows-only patches (defined below, applied if nt) ----
    apply_windows = os.name == "nt"
    if apply_windows:
        from bench_fio.benchlib import generatefio, supporting

    def hidden_subprocess_run(*args, **kwargs):
        flags = kwargs.get("creationflags", 0)
        flags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
        kwargs["creationflags"] = flags
        return original_subprocess_run(*args, **kwargs)

    def windows_drop_caches():
        # /proc/sys/vm/drop_caches não existe no Windows.
        return None

    def windows_run_fio(settings, benchmark):
        # Este valor é usado pelo Python para verificar/criar diretórios.
        benchmark["target_base"] = benchmark["target"]

        output_directory = supporting.generate_output_directory(
            settings,
            benchmark,
        )
        output_dir_path = Path(output_directory)
        output_dir_path.mkdir(parents=True, exist_ok=True)

        output_file = output_dir_path / (
            f"{benchmark['mode']}-"
            f"{benchmark['iodepth']}-"
            f"{benchmark['numjobs']}.json"
        )

        supporting.make_directory(output_directory)

        job_dir = Path(tempfile.gettempdir()) / "FioBenchmark" / "jobs"
        job_dir.mkdir(parents=True, exist_ok=True)

        safe_name = Path(benchmark["target_base"]).name or "benchmark"
        tmpjobfile = job_dir / f"{safe_name}-tmpjobfile.fio"

        # Valores que serão escritos dentro do arquivo .fio.
        # directory=/filename= precisam de escape do ':' da unidade.
        fio_benchmark = dict(benchmark)
        fio_benchmark["target"] = _escape_fio_windows_path(
            benchmark["target"]
        )

        # Prefixo dos .log SEM caminho absoluto problemático.
        # Usamos só o basename; o FIO roda com cwd=output_directory,
        # então os .log caem na mesma pasta do JSON (exigido pelo fio-plot).
        log_prefix = (
            f"{benchmark['mode']}-iodepth-{benchmark['iodepth']}"
            f"-numjobs-{benchmark['numjobs']}"
        )

        generatefio.generate_fio_job_file(
            settings,
            fio_benchmark,
            # caminho só para montar o job; reescrevemos os write_*_log abaixo
            log_prefix,
            str(tmpjobfile),
        )

        # Garante write_*_log com basename relativo (cwd = output_directory).
        # O generatefio grava write_*_log=prefix/...; forçamos o valor final.
        try:
            job_text = tmpjobfile.read_text(encoding="utf-8", errors="replace")
            lines = []
            for line in job_text.splitlines():
                lower = line.strip().lower()
                if lower.startswith("write_bw_log"):
                    lines.append(f"write_bw_log={log_prefix}")
                elif lower.startswith("write_lat_log"):
                    lines.append(f"write_lat_log={log_prefix}")
                elif lower.startswith("write_iops_log"):
                    lines.append(f"write_iops_log={log_prefix}")
                else:
                    lines.append(line)
            # Garante que as três opções existam mesmo se o template mudar
            joined = "\n".join(lines)
            for key in ("write_bw_log", "write_lat_log", "write_iops_log"):
                if f"{key}=" not in joined.lower():
                    lines.append(f"{key}={log_prefix}")
            tmpjobfile.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError:
            pass

        # Importante:
        # No Windows NÃO usamos --output=<arquivo>.
        # Capturamos o JSON pelo stdout e nós mesmos gravamos o arquivo
        # somente depois de confirmar que o conteúdo é JSON válido.
        # cwd=output_directory faz os .log do FIO caírem junto do JSON.
        command = [
            "fio",
            "--output-format=json",
        ]

        if settings["remote"]:
            command.append(f"--client={settings['remote']}")

        command.append(str(tmpjobfile))

        try:
            if settings["dry_run"]:
                return

            result = original_subprocess_run(
                command,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(output_dir_path),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )

            stdout = result.stdout or ""
            stderr = result.stderr or ""

            if result.returncode != 0:
                raise RuntimeError(
                    "O FIO terminou com erro.\n\n"
                    f"Código: {result.returncode}\n"
                    f"stderr:\n{stderr[-3000:]}\n\n"
                    f"stdout:\n{stdout[-3000:]}"
                )

            payload = _extract_json_payload(stdout)

            # Validação final antes de persistir.
            json.loads(payload)

            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(payload, encoding="utf-8")

            if not output_file.is_file() or output_file.stat().st_size == 0:
                raise RuntimeError(
                    f"O JSON do FIO não foi gravado corretamente: {output_file}"
                )

        finally:
            try:
                tmpjobfile.unlink(missing_ok=True)
            except OSError:
                pass

    def progress_wrapped_run_fio(settings, benchmark):
        """Envolve o run_fio atual (Linux original ou Windows) com progresso."""
        result = base_run_fio(settings, benchmark)
        notify_progress(benchmark)
        return result

    # base_run_fio = implementação efetiva antes do wrapper de progresso
    if apply_windows:
        runfio.drop_caches = windows_drop_caches
        subprocess.run = hidden_subprocess_run
        base_run_fio = windows_run_fio
    else:
        base_run_fio = original_run_fio

    if progress_callback:
        runfio.run_fio = progress_wrapped_run_fio
    else:
        runfio.run_fio = base_run_fio

    try:
        yield
    finally:
        subprocess.run = original_subprocess_run
        runfio.run_fio = original_run_fio
        if original_drop_caches is not None:
            runfio.drop_caches = original_drop_caches
