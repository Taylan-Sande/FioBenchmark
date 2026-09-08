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
def bench_fio_compatibility():
    """
    Camada mínima de compatibilidade do bench-fio para Windows.

    O bench-fio upstream possui trechos orientados a Linux, como /tmp e
    drop_caches. Além disso, nesta aplicação o JSON do FIO é capturado pelo
    stdout no Windows, validado e só então salvo em disco. Isso evita arquivos
    JSON vazios que posteriormente quebrariam o fio-plot.
    """
    if os.name != "nt":
        yield
        return

    from bench_fio.benchlib import generatefio, runfio, supporting

    original_drop_caches = runfio.drop_caches
    original_run_fio = runfio.run_fio
    original_subprocess_run = subprocess.run

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

        output_file = Path(output_directory) / (
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
        fio_benchmark = dict(benchmark)
        fio_benchmark["target"] = _escape_fio_windows_path(
            benchmark["target"]
        )

        fio_output_directory = _escape_fio_windows_path(output_directory)

        generatefio.generate_fio_job_file(
            settings,
            fio_benchmark,
            fio_output_directory,
            str(tmpjobfile),
        )

        # Importante:
        # No Windows NÃO usamos --output=<arquivo>.
        # Capturamos o JSON pelo stdout e nós mesmos gravamos o arquivo
        # somente depois de confirmar que o conteúdo é JSON válido.
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

    runfio.drop_caches = windows_drop_caches
    runfio.run_fio = windows_run_fio
    subprocess.run = hidden_subprocess_run

    try:
        yield
    finally:
        subprocess.run = original_subprocess_run
        runfio.run_fio = original_run_fio
        runfio.drop_caches = original_drop_caches
