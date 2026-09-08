import contextlib
import os
import subprocess
import tempfile
from pathlib import Path


def _escape_fio_windows_path(path):
    """
    Converte um caminho Windows para o formato esperado dentro de um job FIO.

    Exemplo:
        C:\\Users\\Taylan\\teste
    vira:
        C\\:\\Users\\Taylan\\teste

    O FIO usa ':' como separador de múltiplos arquivos/diretórios, então o
    ':' da letra da unidade precisa ser escapado dentro do arquivo .fio.
    """
    value = str(path).replace("/", "\\")

    if len(value) >= 2 and value[1] == ":":
        value = value[0] + r"\:" + value[2:]

    return value


@contextlib.contextmanager
def bench_fio_compatibility():
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
        # A implementação original do bench-fio tenta usar:
        # /proc/sys/vm/drop_caches, que é específica de Linux.
        return None

    def windows_run_fio(settings, benchmark):
        # Mantém o caminho real para operações de filesystem do Python.
        benchmark["target_base"] = benchmark["target"]

        output_directory = supporting.generate_output_directory(
            settings,
            benchmark,
        )

        output_file = (
            f"{output_directory}/"
            f"{benchmark['mode']}-"
            f"{benchmark['iodepth']}-"
            f"{benchmark['numjobs']}.json"
        )

        job_dir = Path(tempfile.gettempdir()) / "FioBenchmark" / "jobs"
        job_dir.mkdir(parents=True, exist_ok=True)

        safe_name = Path(benchmark["target_base"]).name or "benchmark"
        tmpjobfile = job_dir / f"{safe_name}-tmpjobfile.fio"

        # O Python precisa do caminho normal, mas o arquivo de configuração
        # do FIO precisa escapar o ':' da unidade Windows.
        fio_benchmark = dict(benchmark)
        fio_benchmark["target"] = _escape_fio_windows_path(
            benchmark["target"]
        )

        # Os caminhos dos logs também são escritos dentro do .fio e precisam
        # da mesma regra.
        fio_output_directory = _escape_fio_windows_path(
            output_directory
        )

        generatefio.generate_fio_job_file(
            settings,
            fio_benchmark,
            fio_output_directory,
            str(tmpjobfile),
        )

        command = [
            "fio",
            "--output-format=json",
            f"--output={output_file}",
        ]

        if settings["remote"]:
            command.append(f"--client={settings['remote']}")

        command.append(str(tmpjobfile))

        try:
            if not settings["dry_run"]:
                supporting.make_directory(output_directory)
                runfio.run_raw_command(command, output_file)

            if settings["remote"]:
                runfio.fix_json_file(output_file)
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
