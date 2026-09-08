import base64
import io
import os
import subprocess
import tempfile
import traceback
import tkinter as tk
from pathlib import Path


def _append(lines, label, ok, details=""):
    status = "OK" if ok else "ERRO"
    line = f"[{status}] {label}"
    if details:
        line += f": {details}"
    lines.append(line)


def run_self_test(report_path):
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    failed = False

    def check(label, func):
        nonlocal failed
        try:
            details = func()
            _append(lines, label, True, "" if details is None else str(details))
        except Exception as exc:
            failed = True
            _append(lines, label, False, f"{type(exc).__name__}: {exc}")
            lines.append(traceback.format_exc())

    def check_imports():
        import numpy
        import matplotlib
        import PIL
        import pyparsing
        import rich
        import fio_plot
        import bench_fio

        return (
            f"numpy={numpy.__version__}; "
            f"matplotlib={matplotlib.__version__}; "
            f"Pillow={PIL.__version__}"
        )

    def check_fio():
        from runtime_tools import configure_runtime_environment, find_fio

        configure_runtime_environment()
        fio = find_fio()
        if fio is None:
            raise RuntimeError("FIO não foi localizado.")

        result = subprocess.run(
            [str(fio), "--version"],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=20,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                (result.stderr or result.stdout or "fio --version falhou").strip()
            )
        return f"{fio} -> {result.stdout.strip()}"

    def check_matplotlib():
        import matplotlib
        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "teste_plot.png"
            fig = plt.figure(figsize=(3, 2))
            ax = fig.add_subplot(111)
            ax.plot([1, 2, 3], [1, 4, 2])
            fig.savefig(output)
            plt.close(fig)

            if not output.is_file() or output.stat().st_size == 0:
                raise RuntimeError("Matplotlib não criou o PNG.")

        return "backend Agg gerou PNG"

    def check_tk_png():
        from PIL import Image

        root = tk.Tk()
        root.withdraw()
        try:
            image = Image.new("RGBA", (16, 16), (255, 255, 255, 255))
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
            photo = tk.PhotoImage(data=encoded)

            if photo.width() != 16 or photo.height() != 16:
                raise RuntimeError(
                    "Tk PhotoImage carregou o PNG com tamanho incorreto."
                )
        finally:
            root.destroy()

        return f"Tk {tk.TkVersion} carregou PNG"

    def check_bench_templates():
        import importlib.resources as resources

        root = resources.files("bench_fio")
        templates = root.joinpath("templates")
        if not templates.is_dir():
            raise RuntimeError("Diretório bench_fio/templates não foi empacotado.")

        files = list(templates.iterdir())
        if not files:
            raise RuntimeError("bench_fio/templates está vazio.")

        return f"{len(files)} arquivo(s) de template"

    check("Imports Python", check_imports)
    check("FIO empacotado", check_fio)
    check("Matplotlib", check_matplotlib)
    check("Tkinter + PNG", check_tk_png)
    check("Templates do bench-fio", check_bench_templates)

    lines.insert(0, "FIO Benchmark - teste do pacote")
    lines.insert(1, f"Executável: {os.path.abspath(os.sys.executable)}")
    lines.append("")
    lines.append("RESULTADO: FALHOU" if failed else "RESULTADO: OK")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return 1 if failed else 0
