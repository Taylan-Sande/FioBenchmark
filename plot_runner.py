import importlib.util
import logging
import os
from pathlib import Path

from benchmark_runner import BenchmarkResult
from embedded_cli import run_embedded_cli
from runtime_tools import configure_runtime_environment


class PlotError(RuntimeError):
    pass


def check_plot_dependencies():
    configure_runtime_environment()

    if importlib.util.find_spec("fio_plot") is None:
        raise PlotError(
            "O módulo fio_plot não foi encontrado.\n\n"
            "No aplicativo instalado ele deve vir incluído no próprio pacote. "
            "Em modo de desenvolvimento, execute:\n"
            "pip install -r requirements.txt"
        )


def _apply_fio_plot_compatibility():
    """
    fio-plot 1.1.21 possui um bug em fio_plot.fiolib.jsonimport:
    o módulo importa logging, mas usa uma variável global `logger`
    que nunca é inicializada.

    Normalmente o problema fica oculto; ele aparece quando o fio-plot
    entra no tratamento de erro de um arquivo JSON. Criamos o logger
    aqui sem modificar os arquivos da dependência.
    """
    from fio_plot.fiolib import jsonimport

    if not hasattr(jsonimport, "logger"):
        logger = logging.getLogger("fio_plot.fiolib.jsonimport")
        logger.setLevel(logging.ERROR)
        logger.propagate = False

        if not logger.handlers:
            logger.addHandler(logging.NullHandler())

        jsonimport.logger = logger


class PlotRunner:
    GRAPH_2D = "2D — IOPS e Latência por IODepth"
    GRAPH_3D_IOPS = "3D — IOPS × IODepth × NumJobs"
    GRAPH_LINE = "Line Chart — dados de LOG do FIO"
    GRAPH_2D_GROUPED = "2D agrupado — IOPS e Latência"
    GRAPH_3D_LAT = "3D — Latência × IODepth × NumJobs"

    ALL_GRAPHS = (
        GRAPH_2D,
        GRAPH_3D_IOPS,
        GRAPH_LINE,
        GRAPH_2D_GROUPED,
        GRAPH_3D_LAT,
    )

    GRAPH_FILENAMES = {
        GRAPH_2D: "grafico_2d_iops_lat.png",
        GRAPH_3D_IOPS: "grafico_3d_iops.png",
        GRAPH_LINE: "grafico_line_chart.png",
        GRAPH_2D_GROUPED: "grafico_2d_agrupado.png",
        GRAPH_3D_LAT: "grafico_3d_lat.png",
    }

    def __init__(self, config, benchmark_result: BenchmarkResult):
        self.config = config
        self.result = benchmark_result

    def _find_data_directory(self):
        cfg = self.config
        qd = cfg["iodepths"][0]
        nj = cfg["numjobs"][0]

        expected = f"{cfg['mode']}-{qd}-{nj}.json"
        matches = list(self.result.output_root.rglob(expected))

        if matches:
            return matches[0].parent

        json_files = list(self.result.output_root.rglob("*.json"))
        if not json_files:
            raise PlotError("Nenhum resultado JSON foi encontrado.")

        candidates = {}
        for file in json_files:
            candidates.setdefault(file.parent, 0)
            if file.name.startswith(cfg["mode"] + "-"):
                candidates[file.parent] += 2
            if file.parent.name.lower() == cfg["block_size"].lower():
                candidates[file.parent] += 1

        return max(candidates, key=candidates.get)

    def _metrics_for_line_chart(self):
        metric = self.config.get("log_metric", "IOPS e Latência")

        if metric == "IOPS":
            return ["iops"]
        if metric == "Latência":
            return ["lat"]
        return ["iops", "lat"]

    def _find_log_files(self, data_dir):
        """Procura .log na pasta dos JSON e, se vazio, em todo o output_root."""
        logs = list(Path(data_dir).glob("*.log"))
        if logs:
            return logs
        root = Path(self.result.output_root)
        return list(root.rglob("*.log"))

    def _validate_line_logs(self, data_dir):
        logs = self._find_log_files(data_dir)
        if not logs:
            root = Path(self.result.output_root)
            sample = sorted(
                str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()
            )[:40]
            listing = "\n".join(sample) if sample else "(pasta vazia)"
            raise PlotError(
                "O gráfico Line Chart precisa dos arquivos .log do FIO "
                "(write_iops_log / write_lat_log), mas nenhum foi encontrado.\n\n"
                f"Pasta procurada: {data_dir}\n"
                f"Sessão: {root}\n\n"
                f"Arquivos encontrados:\n{listing}"
            )
        return logs

    def _numjobs_for_plot(self, graph):
        """Para gráficos 2D/Line usa o primeiro numjobs; para 3D usa a lista completa."""
        numjobs = self.config["numjobs"]
        if graph in (self.GRAPH_2D, self.GRAPH_2D_GROUPED, self.GRAPH_LINE):
            return [numjobs[0]]
        return numjobs

    def _build_command(self, data_dir, output_png, graph):
        cfg = self.config
        numjobs = self._numjobs_for_plot(graph)

        command = [
            "fio-plot",
            "-i", str(data_dir),
            "-o", str(output_png),
            "-T", cfg["title"],
            "-r", cfg["mode"],
        ]

        if graph == self.GRAPH_2D:
            command.extend(
                [
                    "-l",
                    "-n", str(numjobs[0]),
                    "-d", *[str(v) for v in cfg["iodepths"]],
                ]
            )
        elif graph == self.GRAPH_2D_GROUPED:
            command.extend(
                [
                    "-l",
                    "-n", str(numjobs[0]),
                    "-d", *[str(v) for v in cfg["iodepths"]],
                    "--group-bars",
                ]
            )
        elif graph == self.GRAPH_3D_IOPS:
            command.extend(["-L", "-t", "iops"])
        elif graph == self.GRAPH_3D_LAT:
            command.extend(["-L", "-t", "lat"])
        elif graph == self.GRAPH_LINE:
            command.extend(
                [
                    "-g",
                    "-t", *self._metrics_for_line_chart(),
                    "-d", *[str(v) for v in cfg["iodepths"]],
                    "-n", str(numjobs[0]),
                    "--xlabel-parent", "0",
                ]
            )
        else:
            raise PlotError("Tipo de gráfico desconhecido.")

        return command

    def _run_one(self, data_dir, graph, output_png: Path):
        from fio_plot import main as fio_plot_main

        plot_dir = Path(data_dir)
        if graph == self.GRAPH_LINE:
            logs = self._validate_line_logs(data_dir)
            # fio-plot -g lê os .log do diretório -i; usa a pasta onde estão
            plot_dir = logs[0].parent

        command = self._build_command(plot_dir, output_png, graph)

        try:
            return_code, output = run_embedded_cli(
                "fio-plot",
                fio_plot_main,
                command[1:],
            )
        except Exception as exc:
            raise PlotError(
                f"Não foi possível executar o fio-plot ({graph}):\n" + str(exc)
            ) from exc

        if return_code != 0:
            details = output.strip() or "fio-plot terminou sem mensagem."
            raise PlotError(
                f"O fio-plot não conseguiu gerar o gráfico ({graph}).\n\n"
                f"Detalhes:\n{details[-6000:]}"
            )

        if not output_png.is_file() or output_png.stat().st_size == 0:
            details = output.strip()
            message = (
                f"O fio-plot terminou sem erro, mas o arquivo "
                f"{output_png.name} não foi criado ({graph})."
            )
            if details:
                message += "\n\nDetalhes:\n" + details[-5000:]
            raise PlotError(message)

        return output_png

    def run(self, progress_callback=None):
        """
        Gera um ou todos os gráficos conforme config["generate_all"].
        progress_callback(step, total, message) é opcional.
        Retorna lista de Path dos PNGs gerados (o primeiro é o principal para a UI).
        """
        check_plot_dependencies()
        _apply_fio_plot_compatibility()

        os.environ.setdefault("MPLBACKEND", "Agg")

        data_dir = self._find_data_directory()
        generate_all = bool(self.config.get("generate_all", False))

        if generate_all:
            graphs = list(self.ALL_GRAPHS)
        else:
            graphs = [self.config["graph"]]

        total = len(graphs)
        pngs = []
        errors = []

        for idx, graph in enumerate(graphs, start=1):
            filename = self.GRAPH_FILENAMES.get(graph, "grafico.png")
            output_png = self.result.output_root / filename

            if progress_callback:
                progress_callback(
                    idx,
                    total,
                    f"Gerando gráfico {idx}/{total}: {graph}",
                )

            try:
                png = self._run_one(data_dir, graph, output_png)
                pngs.append(png)
            except PlotError as exc:
                if generate_all:
                    # Não aborta os demais gráficos se um falhar
                    errors.append(f"{graph}: {exc}")
                    continue
                raise

        if not pngs:
            detail = "\n\n".join(errors) if errors else "Nenhum gráfico gerado."
            raise PlotError(
                "Nenhum gráfico pôde ser gerado.\n\n" + detail
            )

        if errors and generate_all:
            # Anexa aviso em arquivo na sessão para o usuário ver
            try:
                warn = self.result.output_root / "avisos_graficos.txt"
                warn.write_text("\n\n".join(errors), encoding="utf-8")
            except OSError:
                pass

        return pngs
