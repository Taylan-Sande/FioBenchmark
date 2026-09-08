import contextlib
import os
import subprocess
import tempfile
from pathlib import Path


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
        return None

    def windows_run_fio(settings, benchmark):
        benchmark.update(
            {"target_base": benchmark["target"].replace("\\", "")}
        )

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

        generatefio.generate_fio_job_file(
            settings,
            benchmark,
            output_directory,
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
