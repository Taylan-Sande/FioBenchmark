import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from benchmark_runner import (
    BenchmarkError,
    BenchmarkRunner,
    check_benchmark_dependencies,
)
from plot_runner import PlotError, PlotRunner, check_plot_dependencies


APP_TITLE = "FIO Benchmark"

GRAPH_2D = "2D — IOPS e Latência por IODepth"
GRAPH_3D_IOPS = "3D — IOPS × IODepth × NumJobs"
GRAPH_LINE = "Line Chart — dados de LOG do FIO"
GRAPH_2D_GROUPED = "2D agrupado — IOPS e Latência"
GRAPH_3D_LAT = "3D — Latência × IODepth × NumJobs"

GRAPHS = (
    GRAPH_2D,
    GRAPH_3D_IOPS,
    GRAPH_LINE,
    GRAPH_2D_GROUPED,
    GRAPH_3D_LAT,
)

GRAPH_FIELDS = {
    GRAPH_2D: ("iodepths", "numjobs_fixed"),
    GRAPH_3D_IOPS: ("iodepths", "numjobs_list"),
    GRAPH_LINE: ("iodepths", "numjobs_fixed", "log_metric", "log_interval"),
    GRAPH_2D_GROUPED: ("iodepths", "numjobs_fixed"),
    GRAPH_3D_LAT: ("iodepths", "numjobs_list"),
}

GRAPH_DESCRIPTIONS = {
    GRAPH_2D:
        "Varia IODepth e mantém NumJobs fixo. O fio-plot usa -l.",
    GRAPH_3D_IOPS:
        "Varia IODepth e NumJobs. O fio-plot usa -L -t iops.",
    GRAPH_LINE:
        "Usa os LOGs do FIO para mostrar IOPS e/ou latência ao longo do tempo.",
    GRAPH_2D_GROUPED:
        "Mesmo teste do 2D, mas o fio-plot usa -l --group-bars.",
    GRAPH_3D_LAT:
        "Varia IODepth e NumJobs. O fio-plot usa -L -t lat.",
}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1100x800")
        self.minsize(920, 680)
        self.attributes("-fullscreen", True)

        self.result_image = None
        self.result_source_image = None
        self.resize_after_id = None
        self.running = False

        self.bind("<Escape>", self._exit_fullscreen)
        self.bind("<F11>", self._toggle_fullscreen)

        self._configure_style()
        self._create_variables()
        self._build_ui()
        self._update_graph_fields()
        self._update_readmix_state()

    def _configure_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("Title.TLabel", font=("TkDefaultFont", 20, "bold"))
        style.configure("Section.TLabel", font=("TkDefaultFont", 11, "bold"))
        style.configure("Hint.TLabel", foreground="#555555")
        style.configure("Primary.TButton", font=("TkDefaultFont", 10, "bold"))

    def _create_variables(self):
        self.graph_var = tk.StringVar(value=GRAPH_2D)
        self.target_var = tk.StringVar()

        self.size_mb_var = tk.StringVar(value="1024")
        self.mode_var = tk.StringVar(value="randread")
        self.block_size_var = tk.StringVar(value="4k")
        self.runtime_var = tk.StringVar(value="30")
        self.ramp_time_var = tk.StringVar(value="5")
        self.readmix_var = tk.StringVar(value="70")
        self.title_var = tk.StringVar(value="Benchmark FIO")

        self.iodepths_var = tk.StringVar(value="1 2 4 8 16 32")
        self.numjobs_fixed_var = tk.StringVar(value="1")
        self.numjobs_list_var = tk.StringVar(value="1 2 4 8")
        self.log_metric_var = tk.StringVar(value="IOPS e Latência")
        self.log_interval_var = tk.StringVar(value="1000")

        self.status_var = tk.StringVar(value="Pronto.")
        self.result_path_var = tk.StringVar(value="")

    def _build_ui(self):
        main = ttk.Frame(self, padding=16)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="FIO Benchmark", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            main,
            text=(
                "Escolha um gráfico, configure o teste e selecione uma pasta "
                "existente no SSD ou pendrive que deseja testar."
            ),
            style="Hint.TLabel",
        ).pack(anchor="w", pady=(2, 12))

        paned = ttk.Panedwindow(main, orient="horizontal")
        paned.pack(fill="both", expand=True)

        left = ttk.Frame(paned, padding=(0, 0, 10, 0))
        right = ttk.Frame(paned, padding=(10, 0, 0, 0))
        paned.add(left, weight=2)
        paned.add(right, weight=3)

        self._build_form(left)
        self._build_result_panel(right)

    def _build_form(self, parent):
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        content = ttk.Frame(canvas)

        window = canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind(
            "<Configure>",
            lambda _: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfigure(window, width=e.width),
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._graph_section(content)
        self._target_section(content)
        self._common_section(content)
        self._graph_options_section(content)
        self._action_section(content)

    def _graph_section(self, parent):
        frame = ttk.LabelFrame(parent, text="1. Gráfico", padding=12)
        frame.pack(fill="x", pady=(0, 10))

        combo = ttk.Combobox(
            frame,
            textvariable=self.graph_var,
            values=GRAPHS,
            state="readonly",
        )
        combo.pack(fill="x")
        combo.bind("<<ComboboxSelected>>", self._update_graph_fields)

        self.graph_description = ttk.Label(
            frame,
            text="",
            style="Hint.TLabel",
            wraplength=620,
            justify="left",
        )
        self.graph_description.pack(anchor="w", pady=(8, 0))

    def _target_section(self, parent):
        frame = ttk.LabelFrame(parent, text="2. Armazenamento a testar", padding=12)
        frame.pack(fill="x", pady=(0, 10))

        ttk.Label(
            frame,
            text=(
                "Selecione uma pasta que esteja na unidade desejada. "
                "A aplicação criará dentro dela uma pasta temporária exclusiva "
                "e a removerá ao terminar."
            ),
            wraplength=620,
            justify="left",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        ttk.Entry(frame, textvariable=self.target_var).grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=(0, 8)
        )
        ttk.Button(
            frame,
            text="Escolher...",
            command=self._choose_target,
        ).grid(row=1, column=2)

        ttk.Label(frame, text="Tamanho por job (MB):").grid(
            row=2, column=0, sticky="w", pady=(10, 0)
        )
        ttk.Spinbox(
            frame,
            from_=64,
            to=102400,
            increment=64,
            textvariable=self.size_mb_var,
            width=12,
        ).grid(row=3, column=0, sticky="w")

        ttk.Label(
            frame,
            text=(
                "Ex.: 1024 MB com NumJobs 4 pode precisar de aproximadamente "
                "4 GB na unidade durante o teste."
            ),
            style="Hint.TLabel",
            wraplength=430,
            justify="left",
        ).grid(row=3, column=1, columnspan=2, sticky="w", padx=(8, 0))

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

    def _common_section(self, parent):
        frame = ttk.LabelFrame(parent, text="3. Configurações comuns", padding=12)
        frame.pack(fill="x", pady=(0, 10))

        ttk.Label(frame, text="Modo de I/O:").grid(row=0, column=0, sticky="w")
        mode = ttk.Combobox(
            frame,
            textvariable=self.mode_var,
            values=("randread", "randwrite", "randrw", "read", "write"),
            state="readonly",
            width=16,
        )
        mode.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        mode.bind("<<ComboboxSelected>>", self._update_readmix_state)

        ttk.Label(frame, text="Block size:").grid(row=0, column=1, sticky="w")
        ttk.Combobox(
            frame,
            textvariable=self.block_size_var,
            values=("4k", "8k", "16k", "32k", "64k", "128k", "256k", "1m"),
            state="readonly",
            width=14,
        ).grid(row=1, column=1, sticky="ew", padx=(0, 8))

        ttk.Label(frame, text="Runtime por teste (s):").grid(
            row=0, column=2, sticky="w"
        )
        ttk.Spinbox(
            frame,
            from_=1,
            to=3600,
            textvariable=self.runtime_var,
            width=10,
        ).grid(row=1, column=2, sticky="ew")

        ttk.Label(frame, text="Ramp time (s):").grid(
            row=2, column=0, sticky="w", pady=(10, 0)
        )
        ttk.Spinbox(
            frame,
            from_=0,
            to=600,
            textvariable=self.ramp_time_var,
            width=10,
        ).grid(row=3, column=0, sticky="ew", padx=(0, 8))

        ttk.Label(frame, text="% leitura no randrw:").grid(
            row=2, column=1, sticky="w", pady=(10, 0)
        )
        self.readmix_spin = ttk.Spinbox(
            frame,
            from_=1,
            to=99,
            textvariable=self.readmix_var,
            width=10,
        )
        self.readmix_spin.grid(row=3, column=1, sticky="ew", padx=(0, 8))

        ttk.Label(frame, text="Título do gráfico:").grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(10, 0)
        )
        ttk.Entry(frame, textvariable=self.title_var).grid(
            row=5, column=0, columnspan=3, sticky="ew"
        )

        for col in range(3):
            frame.columnconfigure(col, weight=1)

    def _graph_options_section(self, parent):
        self.graph_options_frame = ttk.LabelFrame(
            parent,
            text="4. Sequência de testes",
            padding=12,
        )
        self.graph_options_frame.pack(fill="x", pady=(0, 10))

    def _action_section(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=(0, 8))

        self.run_button = ttk.Button(
            frame,
            text="Executar benchmark e gerar gráfico",
            style="Primary.TButton",
            command=self._start,
        )
        self.run_button.pack(side="left")

        self.progress = ttk.Progressbar(frame, mode="indeterminate", length=180)
        self.progress.pack(side="right")

        ttk.Label(
            parent,
            textvariable=self.status_var,
            wraplength=620,
            justify="left",
        ).pack(anchor="w")

    def _build_result_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Resultado", padding=12)
        frame.pack(fill="both", expand=True)

        self.image_label = ttk.Label(
            frame,
            text="O gráfico aparecerá aqui quando o teste terminar.",
            anchor="center",
            justify="center",
        )
        self.image_label.pack(fill="both", expand=True)
        self.image_label.bind("<Configure>", self._on_image_area_resize)

        ttk.Label(
            frame,
            textvariable=self.result_path_var,
            style="Hint.TLabel",
            wraplength=360,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        self.open_folder_button = ttk.Button(
            frame,
            text="Abrir pasta do resultado",
            command=self._open_result_folder,
            state="disabled",
        )
        self.open_folder_button.pack(anchor="w", pady=(8, 0))

    def _update_graph_fields(self, event=None):
        for widget in self.graph_options_frame.winfo_children():
            widget.destroy()

        graph = self.graph_var.get()
        self.graph_description.config(text=GRAPH_DESCRIPTIONS[graph])
        fields = GRAPH_FIELDS[graph]
        row = 0

        if "iodepths" in fields:
            ttk.Label(
                self.graph_options_frame,
                text="IODepth(s):",
            ).grid(row=row, column=0, sticky="w")
            ttk.Entry(
                self.graph_options_frame,
                textvariable=self.iodepths_var,
            ).grid(row=row + 1, column=0, sticky="ew", pady=(3, 0))
            ttk.Label(
                self.graph_options_frame,
                text="Valores separados por espaço. Ex.: 1 2 4 8 16 32",
                style="Hint.TLabel",
            ).grid(row=row + 2, column=0, sticky="w", pady=(2, 8))
            row += 3

        if "numjobs_fixed" in fields:
            ttk.Label(
                self.graph_options_frame,
                text="NumJobs fixo:",
            ).grid(row=row, column=0, sticky="w")
            ttk.Spinbox(
                self.graph_options_frame,
                from_=1,
                to=128,
                textvariable=self.numjobs_fixed_var,
                width=10,
            ).grid(row=row + 1, column=0, sticky="w", pady=(3, 8))
            row += 2

        if "numjobs_list" in fields:
            ttk.Label(
                self.graph_options_frame,
                text="NumJobs:",
            ).grid(row=row, column=0, sticky="w")
            ttk.Entry(
                self.graph_options_frame,
                textvariable=self.numjobs_list_var,
            ).grid(row=row + 1, column=0, sticky="ew", pady=(3, 0))
            ttk.Label(
                self.graph_options_frame,
                text="Valores separados por espaço. Ex.: 1 2 4 8",
                style="Hint.TLabel",
            ).grid(row=row + 2, column=0, sticky="w", pady=(2, 8))
            row += 3

        if "log_metric" in fields:
            ttk.Label(
                self.graph_options_frame,
                text="Métrica do Line Chart:",
            ).grid(row=row, column=0, sticky="w")
            ttk.Combobox(
                self.graph_options_frame,
                textvariable=self.log_metric_var,
                values=("IOPS", "Latência", "IOPS e Latência"),
                state="readonly",
                width=24,
            ).grid(row=row + 1, column=0, sticky="w", pady=(3, 8))
            row += 2

        if "log_interval" in fields:
            ttk.Label(
                self.graph_options_frame,
                text="Intervalo do LOG (ms):",
            ).grid(row=row, column=0, sticky="w")
            ttk.Spinbox(
                self.graph_options_frame,
                from_=100,
                to=60000,
                increment=100,
                textvariable=self.log_interval_var,
                width=10,
            ).grid(row=row + 1, column=0, sticky="w", pady=(3, 0))
            ttk.Label(
                self.graph_options_frame,
                text="1000 ms = uma amostra por segundo.",
                style="Hint.TLabel",
            ).grid(row=row + 2, column=0, sticky="w")

        self.graph_options_frame.columnconfigure(0, weight=1)

    def _update_readmix_state(self, event=None):
        state = "normal" if self.mode_var.get() == "randrw" else "disabled"
        self.readmix_spin.configure(state=state)

    def _choose_target(self):
        folder = filedialog.askdirectory(
            title="Escolha uma pasta na unidade que deseja testar"
        )
        if folder:
            self.target_var.set(folder)

    @staticmethod
    def _positive_int(value, field, allow_zero=False):
        try:
            number = int(value)
        except ValueError:
            raise ValueError(f"{field} deve ser um número inteiro.") from None

        minimum = 0 if allow_zero else 1
        if number < minimum:
            if allow_zero:
                raise ValueError(f"{field} não pode ser negativo.")
            raise ValueError(f"{field} deve ser maior que zero.")
        return number

    @classmethod
    def _int_list(cls, text, field):
        parts = text.replace(",", " ").split()
        if not parts:
            raise ValueError(f"Informe pelo menos um valor em {field}.")
        return [cls._positive_int(part, field) for part in parts]

    def _collect_config(self):
        graph = self.graph_var.get()
        target = Path(self.target_var.get().strip()).expanduser()

        if not self.target_var.get().strip():
            raise ValueError("Selecione a pasta da unidade que deseja testar.")
        if not target.is_dir():
            raise ValueError("A pasta selecionada não existe.")

        title = self.title_var.get().strip()
        if not title:
            raise ValueError("Informe o título do gráfico.")

        size_mb = self._positive_int(self.size_mb_var.get(), "Tamanho por job")
        runtime = self._positive_int(self.runtime_var.get(), "Runtime")
        ramp_time = self._positive_int(
            self.ramp_time_var.get(), "Ramp time", allow_zero=True
        )
        iodepths = self._int_list(self.iodepths_var.get(), "IODepth")

        fields = GRAPH_FIELDS[graph]

        if "numjobs_list" in fields:
            numjobs = self._int_list(self.numjobs_list_var.get(), "NumJobs")
        else:
            numjobs = [
                self._positive_int(self.numjobs_fixed_var.get(), "NumJobs")
            ]

        log_interval = 1000
        if "log_interval" in fields:
            log_interval = self._positive_int(
                self.log_interval_var.get(), "Intervalo do LOG"
            )

        readmix = None
        if self.mode_var.get() == "randrw":
            readmix = self._positive_int(
                self.readmix_var.get(), "Percentual de leitura"
            )
            if not 1 <= readmix <= 99:
                raise ValueError(
                    "O percentual de leitura no randrw deve ficar entre 1 e 99."
                )

        return {
            "graph": graph,
            "target_root": str(target),
            "size_mb": size_mb,
            "mode": self.mode_var.get(),
            "block_size": self.block_size_var.get(),
            "runtime": runtime,
            "ramp_time": ramp_time,
            "readmix": readmix,
            "title": title,
            "iodepths": iodepths,
            "numjobs": numjobs,
            "log_metric": self.log_metric_var.get(),
            "log_interval": log_interval,
        }

    def _start(self):
        if self.running:
            return

        try:
            config = self._collect_config()
            check_benchmark_dependencies()
            check_plot_dependencies()
        except (ValueError, BenchmarkError, PlotError) as exc:
            messagebox.showerror("Não foi possível iniciar", str(exc))
            return

        if config["mode"] in {"write", "randwrite", "randrw"}:
            answer = messagebox.askyesno(
                "Teste com escrita",
                (
                    "Este modo grava dados na unidade selecionada.\n\n"
                    "A aplicação usará somente uma pasta temporária exclusiva "
                    "criada por ela e apagará essa pasta ao terminar.\n\n"
                    "Deseja continuar?"
                ),
            )
            if not answer:
                return

        self.running = True
        self.run_button.configure(state="disabled")
        self.open_folder_button.configure(state="disabled")
        self.progress.start(10)
        self.status_var.set("Executando o benchmark. Não feche a aplicação.")

        thread = threading.Thread(
            target=self._worker,
            args=(config,),
            daemon=True,
        )
        thread.start()

    def _worker(self, config):
        try:
            benchmark = BenchmarkRunner(config)
            benchmark_result = benchmark.run()

            self.after(
                0,
                lambda: self.status_var.set(
                    "Benchmark concluído. Gerando o gráfico com fio-plot..."
                ),
            )

            plotter = PlotRunner(config, benchmark_result)
            png_path = plotter.run()

            self.after(0, lambda: self._finish_success(png_path))
        except (BenchmarkError, PlotError, OSError) as exc:
            self.after(0, lambda: self._finish_error(str(exc)))
        except Exception as exc:
            self.after(
                0,
                lambda: self._finish_error(
                    "Ocorreu um erro inesperado:\n" + str(exc)
                ),
            )

    def _finish_success(self, png_path):
        self.running = False
        self.progress.stop()
        self.run_button.configure(state="normal")
        self.status_var.set("Concluído.")
        self.result_path_var.set(f"Gráfico: {png_path}")
        self.open_folder_button.configure(state="normal")
        self._show_image(Path(png_path))
        messagebox.showinfo(
            "Concluído",
            "O benchmark terminou e o gráfico foi gerado.",
        )

    def _finish_error(self, message):
        self.running = False
        self.progress.stop()
        self.run_button.configure(state="normal")
        self.status_var.set("Falha.")
        messagebox.showerror("Erro", message)

    def _show_image(self, path):
        with Image.open(path) as image:
            self.result_source_image = image.copy()

        self.image_label.configure(text="")
        self.after_idle(self._render_result_image)

    def _on_image_area_resize(self, event=None):
        if self.result_source_image is None:
            return

        if self.resize_after_id is not None:
            self.after_cancel(self.resize_after_id)

        self.resize_after_id = self.after(100, self._render_result_image)

    def _render_result_image(self):
        self.resize_after_id = None

        if self.result_source_image is None:
            return

        width = self.image_label.winfo_width()
        height = self.image_label.winfo_height()

        if width <= 10 or height <= 10:
            return

        margin = 12
        available_width = max(1, width - margin)
        available_height = max(1, height - margin)

        original_width, original_height = self.result_source_image.size

        scale = min(
            available_width / original_width,
            available_height / original_height,
        )

        new_width = max(1, int(original_width * scale))
        new_height = max(1, int(original_height * scale))

        resized = self.result_source_image.resize(
            (new_width, new_height),
            Image.Resampling.LANCZOS,
        )

        self.result_image = ImageTk.PhotoImage(resized)
        self.image_label.configure(image=self.result_image)

    def _exit_fullscreen(self, event=None):
        self.attributes("-fullscreen", False)

    def _toggle_fullscreen(self, event=None):
        current = bool(self.attributes("-fullscreen"))
        self.attributes("-fullscreen", not current)

    def _open_result_folder(self):
        path_text = self.result_path_var.get().removeprefix("Gráfico: ").strip()
        if not path_text:
            return

        folder = Path(path_text).parent
        try:
            if os.name == "nt":
                os.startfile(folder)
            elif os.uname().sysname == "Darwin":
                import subprocess
                subprocess.Popen(["open", str(folder)])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", str(folder)])
        except OSError as exc:
            messagebox.showerror(
                "Não foi possível abrir a pasta",
                str(exc),
            )


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
