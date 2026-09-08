import base64
import io
import os
import sys
import threading
import traceback
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image

from benchmark_runner import (
    BenchmarkError,
    BenchmarkRunner,
    check_benchmark_dependencies,
)
from plot_runner import PlotError, PlotRunner, check_plot_dependencies


APP_TITLE = "FIO Benchmark"
DEFAULT_RESULTS_ROOT = Path.home() / "FioBenchmark" / "resultados"

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

# Temas claro / escuro para ttk (tema "clam")
LIGHT_THEME = {
    "bg": "#f0f0f0",
    "fg": "#1a1a1a",
    "field_bg": "#ffffff",
    "select_bg": "#0078d4",
    "select_fg": "#ffffff",
    "button_bg": "#e1e1e1",
    "button_active": "#d0d0d0",
    "frame_bg": "#f0f0f0",
    "labelframe_bg": "#f0f0f0",
    "hint_fg": "#555555",
    "primary_bg": "#0078d4",
    "primary_fg": "#ffffff",
    "primary_active": "#106ebe",
    "border": "#c0c0c0",
    "trough": "#d0d0d0",
    "progress": "#0078d4",
}

DARK_THEME = {
    "bg": "#1e1e1e",
    "fg": "#e0e0e0",
    "field_bg": "#2d2d2d",
    "select_bg": "#0e639c",
    "select_fg": "#ffffff",
    "button_bg": "#3c3c3c",
    "button_active": "#505050",
    "frame_bg": "#1e1e1e",
    "labelframe_bg": "#252526",
    "hint_fg": "#a0a0a0",
    "primary_bg": "#0e639c",
    "primary_fg": "#ffffff",
    "primary_active": "#1177bb",
    "border": "#3c3c3c",
    "trough": "#3c3c3c",
    "progress": "#0e639c",
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
        self.dark_mode = False
        self._style = None

        self.bind("<Escape>", self._exit_fullscreen)
        self.bind("<F11>", self._toggle_fullscreen)

        self._create_variables()
        self._configure_style()
        self._build_ui()
        self._update_graph_fields()
        self._update_readmix_state()
        self._apply_theme()

    def report_callback_exception(self, exc, value, tb):
        details = "".join(traceback.format_exception(exc, value, tb))
        log_dir = Path.home() / "FioBenchmark"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "erro_interface.log"

        try:
            with log_path.open("a", encoding="utf-8") as log:
                log.write("\n" + "=" * 80 + "\n")
                log.write(details)
        except OSError:
            pass

        try:
            messagebox.showerror(
                "Erro na interface",
                (
                    "Ocorreu um erro na interface.\n\n"
                    f"Detalhes foram gravados em:\n{log_path}\n\n"
                    f"{value}"
                ),
            )
        except Exception:
            pass

    def _configure_style(self):
        self._style = ttk.Style(self)
        try:
            self._style.theme_use("clam")
        except tk.TclError:
            pass

        self._style.configure("Title.TLabel", font=("TkDefaultFont", 20, "bold"))
        self._style.configure("Section.TLabel", font=("TkDefaultFont", 11, "bold"))
        self._style.configure("Primary.TButton", font=("TkDefaultFont", 10, "bold"))

    def _apply_theme(self):
        theme = DARK_THEME if self.dark_mode else LIGHT_THEME
        style = self._style

        self.configure(bg=theme["bg"])

        style.configure(
            ".",
            background=theme["bg"],
            foreground=theme["fg"],
            fieldbackground=theme["field_bg"],
            troughcolor=theme["trough"],
            bordercolor=theme["border"],
            lightcolor=theme["border"],
            darkcolor=theme["border"],
        )
        style.configure("TFrame", background=theme["frame_bg"])
        style.configure(
            "TLabelframe",
            background=theme["labelframe_bg"],
            foreground=theme["fg"],
            bordercolor=theme["border"],
        )
        style.configure(
            "TLabelframe.Label",
            background=theme["labelframe_bg"],
            foreground=theme["fg"],
        )
        style.configure("TLabel", background=theme["bg"], foreground=theme["fg"])
        style.configure(
            "Title.TLabel",
            background=theme["bg"],
            foreground=theme["fg"],
            font=("TkDefaultFont", 20, "bold"),
        )
        style.configure(
            "Hint.TLabel",
            background=theme["bg"],
            foreground=theme["hint_fg"],
        )
        style.configure(
            "TButton",
            background=theme["button_bg"],
            foreground=theme["fg"],
            bordercolor=theme["border"],
        )
        style.map(
            "TButton",
            background=[("active", theme["button_active"]), ("disabled", theme["trough"])],
            foreground=[("disabled", theme["hint_fg"])],
        )
        style.configure(
            "Primary.TButton",
            background=theme["primary_bg"],
            foreground=theme["primary_fg"],
            font=("TkDefaultFont", 10, "bold"),
        )
        style.map(
            "Primary.TButton",
            background=[("active", theme["primary_active"]), ("disabled", theme["trough"])],
            foreground=[("disabled", theme["hint_fg"])],
        )
        style.configure(
            "TEntry",
            fieldbackground=theme["field_bg"],
            foreground=theme["fg"],
            insertcolor=theme["fg"],
            bordercolor=theme["border"],
        )
        style.configure(
            "TCombobox",
            fieldbackground=theme["field_bg"],
            foreground=theme["fg"],
            background=theme["button_bg"],
            arrowcolor=theme["fg"],
            bordercolor=theme["border"],
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", theme["field_bg"])],
            foreground=[("readonly", theme["fg"])],
            selectbackground=[("readonly", theme["select_bg"])],
            selectforeground=[("readonly", theme["select_fg"])],
        )
        style.configure(
            "TSpinbox",
            fieldbackground=theme["field_bg"],
            foreground=theme["fg"],
            insertcolor=theme["fg"],
            bordercolor=theme["border"],
            arrowcolor=theme["fg"],
        )
        style.configure(
            "TProgressbar",
            background=theme["progress"],
            troughcolor=theme["trough"],
            bordercolor=theme["border"],
        )
        style.configure(
            "TScrollbar",
            background=theme["button_bg"],
            troughcolor=theme["trough"],
            bordercolor=theme["border"],
            arrowcolor=theme["fg"],
        )
        style.map(
            "TScrollbar",
            background=[("active", theme["button_active"])],
        )
        style.configure(
            "TPanedwindow",
            background=theme["bg"],
        )
        style.configure(
            "Sash",
            sashthickness=6,
            background=theme["border"],
        )

        # Canvas usado no formulário rolável (não é ttk)
        if hasattr(self, "_form_canvas"):
            self._form_canvas.configure(
                bg=theme["bg"],
                highlightbackground=theme["bg"],
                highlightcolor=theme["bg"],
            )

        # Dropdown do Combobox (lista popup)
        try:
            self.option_add("*TCombobox*Listbox.background", theme["field_bg"])
            self.option_add("*TCombobox*Listbox.foreground", theme["fg"])
            self.option_add("*TCombobox*Listbox.selectBackground", theme["select_bg"])
            self.option_add("*TCombobox*Listbox.selectForeground", theme["select_fg"])
        except tk.TclError:
            pass

        if hasattr(self, "dark_mode_button"):
            self.dark_mode_button.configure(
                text="☀ Modo claro" if self.dark_mode else "🌙 Modo escuro"
            )

    def _toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        self._apply_theme()

    def _create_variables(self):
        self.graph_var = tk.StringVar(value=GRAPH_2D)
        self.target_var = tk.StringVar()
        self.results_root_var = tk.StringVar(value=str(DEFAULT_RESULTS_ROOT))

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
        self.generate_all_var = tk.BooleanVar(value=False)

        self.status_var = tk.StringVar(value="Pronto.")
        self.result_path_var = tk.StringVar(value="")
        self.progress_max = 1
        self.progress_value = 0

    def _build_ui(self):
        main = ttk.Frame(self, padding=16)
        main.pack(fill="both", expand=True)

        header = ttk.Frame(main)
        header.pack(fill="x", pady=(0, 4))

        ttk.Label(header, text="FIO Benchmark", style="Title.TLabel").pack(
            side="left", anchor="w"
        )
        self.dark_mode_button = ttk.Button(
            header,
            text="🌙 Modo escuro",
            command=self._toggle_dark_mode,
            width=14,
        )
        self.dark_mode_button.pack(side="right", padx=(8, 0))

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
        self._form_canvas = canvas
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
        self._results_section(content)
        self._common_section(content)
        self._graph_options_section(content)
        self._action_section(content)

    def _graph_section(self, parent):
        frame = ttk.LabelFrame(parent, text="1. Gráfico", padding=12)
        frame.pack(fill="x", pady=(0, 10))

        self.graph_combo = ttk.Combobox(
            frame,
            textvariable=self.graph_var,
            values=GRAPHS,
            state="readonly",
        )
        self.graph_combo.pack(fill="x")
        self.graph_combo.bind("<<ComboboxSelected>>", self._update_graph_fields)

        self.generate_all_check = ttk.Checkbutton(
            frame,
            text="Gerar todos os gráficos (com os mesmos dados do teste)",
            variable=self.generate_all_var,
            command=self._on_generate_all_toggled,
        )
        self.generate_all_check.pack(anchor="w", pady=(8, 0))

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

    def _results_section(self, parent):
        frame = ttk.LabelFrame(parent, text="3. Pasta de resultados", padding=12)
        frame.pack(fill="x", pady=(0, 10))

        ttk.Label(
            frame,
            text=(
                "Os resultados (dados do FIO + gráficos) serão salvos aqui. "
                "Cada execução cria uma subpasta com data/hora."
            ),
            wraplength=620,
            justify="left",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        ttk.Entry(frame, textvariable=self.results_root_var).grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=(0, 8)
        )
        ttk.Button(
            frame,
            text="Escolher...",
            command=self._choose_results_root,
        ).grid(row=1, column=2)

        ttk.Label(
            frame,
            text=f"Padrão: {DEFAULT_RESULTS_ROOT}",
            style="Hint.TLabel",
            wraplength=620,
            justify="left",
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

    def _common_section(self, parent):
        frame = ttk.LabelFrame(parent, text="4. Configurações comuns", padding=12)
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
            text="5. Sequência de testes",
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

        progress_frame = ttk.Frame(frame)
        progress_frame.pack(side="right", fill="x", expand=True, padx=(12, 0))

        self.progress = ttk.Progressbar(
            progress_frame,
            mode="determinate",
            maximum=100,
            value=0,
            length=220,
        )
        self.progress.pack(side="top", fill="x")

        self.progress_label_var = tk.StringVar(value="")
        ttk.Label(
            progress_frame,
            textvariable=self.progress_label_var,
            style="Hint.TLabel",
        ).pack(side="top", anchor="e")

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

    def _on_generate_all_toggled(self):
        generate_all = self.generate_all_var.get()
        if generate_all:
            self.graph_combo.configure(state="disabled")
            self.graph_description.config(
                text=(
                    "Serão gerados todos os 5 tipos de gráfico a partir do "
                    "mesmo teste. O benchmark roda com a lista completa de "
                    "NumJobs e IODepths (necessário para os 3D). "
                    "Os gráficos 2D/Line usam o primeiro NumJobs da lista."
                )
            )
        else:
            self.graph_combo.configure(state="readonly")
        self._update_graph_fields()

    def _update_graph_fields(self, event=None):
        for widget in self.graph_options_frame.winfo_children():
            widget.destroy()

        generate_all = self.generate_all_var.get()
        graph = self.graph_var.get()

        if generate_all:
            # União dos campos necessários para todos os gráficos
            fields = ("iodepths", "numjobs_list", "log_metric", "log_interval")
            if not self.generate_all_var.get():
                pass
            # descrição já setada no toggle; reforça se veio do combo
            self.graph_description.config(
                text=(
                    "Serão gerados todos os 5 tipos de gráfico a partir do "
                    "mesmo teste. O benchmark roda com a lista completa de "
                    "NumJobs e IODepths (necessário para os 3D). "
                    "Os gráficos 2D/Line usam o primeiro NumJobs da lista."
                )
            )
        else:
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
                text="NumJobs:" if generate_all else "NumJobs:",
            ).grid(row=row, column=0, sticky="w")
            ttk.Entry(
                self.graph_options_frame,
                textvariable=self.numjobs_list_var,
            ).grid(row=row + 1, column=0, sticky="ew", pady=(3, 0))
            hint = (
                "Lista completa (3D usa todos; 2D/Line usam o 1º). Ex.: 1 2 4 8"
                if generate_all
                else "Valores separados por espaço. Ex.: 1 2 4 8"
            )
            ttk.Label(
                self.graph_options_frame,
                text=hint,
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

    def _choose_results_root(self):
        initial = self.results_root_var.get().strip() or str(DEFAULT_RESULTS_ROOT)
        try:
            Path(initial).mkdir(parents=True, exist_ok=True)
        except OSError:
            initial = str(Path.home())

        folder = filedialog.askdirectory(
            title="Escolha a pasta onde salvar os resultados",
            initialdir=initial,
        )
        if folder:
            self.results_root_var.set(folder)

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

        results_root_text = self.results_root_var.get().strip()
        if not results_root_text:
            raise ValueError("Informe a pasta de resultados.")
        results_root = Path(results_root_text).expanduser()
        try:
            results_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ValueError(
                f"Não foi possível criar/usar a pasta de resultados:\n{exc}"
            ) from exc
        if not results_root.is_dir():
            raise ValueError("A pasta de resultados informada não existe.")
        if not os.access(results_root, os.W_OK):
            raise ValueError(
                "Sem permissão de escrita na pasta de resultados escolhida."
            )

        title = self.title_var.get().strip()
        if not title:
            raise ValueError("Informe o título do gráfico.")

        size_mb = self._positive_int(self.size_mb_var.get(), "Tamanho por job")
        runtime = self._positive_int(self.runtime_var.get(), "Runtime")
        ramp_time = self._positive_int(
            self.ramp_time_var.get(), "Ramp time", allow_zero=True
        )
        iodepths = self._int_list(self.iodepths_var.get(), "IODepth")

        generate_all = bool(self.generate_all_var.get())

        if generate_all:
            # Lista completa para os 3D; 2D/Line usam o primeiro valor no plot
            numjobs = self._int_list(self.numjobs_list_var.get(), "NumJobs")
            log_interval = self._positive_int(
                self.log_interval_var.get(), "Intervalo do LOG"
            )
        else:
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
            "generate_all": generate_all,
            "target_root": str(target),
            "results_root": str(results_root.resolve()),
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

    def _set_progress(self, step, total, message):
        """Atualiza barra e status (sempre chamar via self.after a partir de threads)."""
        total = max(1, int(total))
        step = max(0, min(int(step), total))
        percent = int((step / total) * 100)
        self.progress.configure(mode="determinate", maximum=100, value=percent)
        self.progress_label_var.set(f"{percent}%")
        if message:
            self.status_var.set(message)

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

        # Progresso = cada job FIO + cada gráfico
        runner_preview = BenchmarkRunner(config)
        num_jobs = runner_preview.expected_job_count()
        num_graphs = len(GRAPHS) if config.get("generate_all") else 1
        self.progress_max = num_jobs + num_graphs
        self.progress_value = 0
        self._bench_jobs_total = num_jobs

        self.running = True
        self.run_button.configure(state="disabled")
        self.open_folder_button.configure(state="disabled")
        self._set_progress(
            0,
            self.progress_max,
            f"Iniciando… {num_jobs} job(s) de benchmark + {num_graphs} gráfico(s).",
        )

        thread = threading.Thread(
            target=self._worker,
            args=(config,),
            daemon=True,
        )
        thread.start()

    def _worker(self, config):
        try:
            total = self.progress_max
            bench_total = self._bench_jobs_total

            self.after(
                0,
                lambda: self._set_progress(
                    0,
                    total,
                    f"Executando benchmark (0/{bench_total}). Não feche a aplicação.",
                ),
            )

            def bench_progress(done, job_total, message):
                # done = jobs concluídos (1..bench_total)
                self.after(
                    0,
                    lambda d=done, m=message: self._set_progress(d, total, m),
                )

            benchmark = BenchmarkRunner(config)
            benchmark_result = benchmark.run(progress_callback=bench_progress)

            self.after(
                0,
                lambda: self._set_progress(
                    bench_total,
                    total,
                    "Benchmark concluído. Gerando gráfico(s) com fio-plot…",
                ),
            )

            def plot_progress(step, graph_total, message):
                # step 1..N dos gráficos → progresso global = bench_total + step
                self.after(
                    0,
                    lambda s=step, m=message: self._set_progress(
                        bench_total + s, total, m
                    ),
                )

            plotter = PlotRunner(config, benchmark_result)
            result = plotter.run(progress_callback=plot_progress)
            if isinstance(result, (list, tuple)):
                png_paths = list(result)
            else:
                png_paths = [result]

            self.after(
                0,
                lambda: self._set_progress(total, total, "Concluído."),
            )
            self.after(0, self._finish_success, png_paths)
        except (BenchmarkError, PlotError, OSError) as exc:
            message = str(exc)
            self.after(0, self._finish_error, message)
        except Exception as exc:
            message = "Ocorreu um erro inesperado:\n" + str(exc)
            self.after(0, self._finish_error, message)

    def _finish_success(self, png_paths):
        self.running = False
        self.run_button.configure(state="normal")
        self.status_var.set("Concluído.")
        self.progress_label_var.set("100%")
        self.progress.configure(value=100)

        primary = Path(png_paths[0]) if png_paths else None
        if primary is not None:
            if len(png_paths) == 1:
                self.result_path_var.set(f"Gráfico: {primary}")
                msg = "O benchmark terminou e o gráfico foi gerado."
            else:
                self.result_path_var.set(
                    f"{len(png_paths)} gráficos em: {primary.parent}"
                )
                msg = (
                    f"O benchmark terminou e {len(png_paths)} gráficos "
                    f"foram gerados.\n\nPasta:\n{primary.parent}"
                )
            self.open_folder_button.configure(state="normal")
            self._show_image(primary)
        else:
            self.result_path_var.set("")
            self.open_folder_button.configure(state="disabled")
            msg = "O benchmark terminou."

        messagebox.showinfo("Concluído", msg)

    def _finish_error(self, message):
        self.running = False
        self.run_button.configure(state="normal")
        self.status_var.set("Falha.")
        self.progress_label_var.set("")
        self.progress.configure(value=0)
        messagebox.showerror("Erro", message)

    def _show_image(self, path):
        try:
            with Image.open(path) as image:
                self.result_source_image = image.convert("RGBA").copy()

            self.image_label.configure(text="")
            self.update_idletasks()
            self.after(50, self._render_result_image)
        except Exception as exc:
            self.result_source_image = None
            self.image_label.configure(
                image="",
                text=(
                    "O gráfico foi gerado, mas não pôde ser exibido aqui.\n\n"
                    f"Arquivo: {path}\n\n"
                    f"Erro: {exc}"
                ),
            )
            raise

    def _on_image_area_resize(self, event=None):
        if self.result_source_image is None:
            return

        if self.resize_after_id is not None:
            try:
                self.after_cancel(self.resize_after_id)
            except tk.TclError:
                pass

        self.resize_after_id = self.after(120, self._render_result_image)

    def _render_result_image(self):
        self.resize_after_id = None

        if self.result_source_image is None:
            return

        width = self.image_label.winfo_width()
        height = self.image_label.winfo_height()

        if width <= 10 or height <= 10:
            self.resize_after_id = self.after(120, self._render_result_image)
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

        buffer = io.BytesIO()
        resized.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

        self.result_image = tk.PhotoImage(data=encoded)
        self.image_label.configure(image=self.result_image, text="")

    def _exit_fullscreen(self, event=None):
        self.attributes("-fullscreen", False)

    def _toggle_fullscreen(self, event=None):
        current = bool(self.attributes("-fullscreen"))
        self.attributes("-fullscreen", not current)

    def _open_result_folder(self):
        path_text = self.result_path_var.get().strip()
        if not path_text:
            return

        # Formatos possíveis:
        # "Gráfico: /path/to/grafico.png"
        # "N gráficos em: /path/to/session"
        if path_text.startswith("Gráfico: "):
            path_text = path_text.removeprefix("Gráfico: ").strip()
            folder = Path(path_text).parent
        elif " gráficos em: " in path_text:
            path_text = path_text.split(" gráficos em: ", 1)[-1].strip()
            folder = Path(path_text)
        else:
            folder = Path(path_text)
            if folder.is_file():
                folder = folder.parent

        if not folder.exists():
            messagebox.showerror(
                "Pasta não encontrada",
                f"A pasta não existe:\n{folder}",
            )
            return

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
    if "--self-test" in sys.argv:
        from runtime_selftest import run_self_test

        try:
            index = sys.argv.index("--self-test")
            report_path = (
                Path(sys.argv[index + 1])
                if len(sys.argv) > index + 1
                else Path.home() / "FioBenchmark" / "selftest.txt"
            )
        except (ValueError, IndexError):
            report_path = Path.home() / "FioBenchmark" / "selftest.txt"

        raise SystemExit(run_self_test(report_path))

    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
