import importlib.util
import logging
import os

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
        metric = self.config["log_metric"]

        if metric == "IOPS":
            return ["iops"]
        if metric == "Latência":
            return ["lat"]
        return ["iops", "lat"]

    def _validate_line_logs(self, data_dir):
        logs = list(data_dir.glob("*.log"))
        if not logs:
            raise PlotError(
                "O gráfico Line Chart precisa dos arquivos .log do FIO, "
                "mas nenhum foi encontrado."
            )

    def _build_command(self, data_dir, output_png):
        cfg = self.config
        graph = cfg["graph"]

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
                    "-n", str(cfg["numjobs"][0]),
                    "-d", *[str(v) for v in cfg["iodepths"]],
                ]
            )
        elif graph == self.GRAPH_2D_GROUPED:
            command.extend(
                [
                    "-l",
                    "-n", str(cfg["numjobs"][0]),
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
                    "-n", str(cfg["numjobs"][0]),
                    "--xlabel-parent", "0",
                ]
            )
        else:
            raise PlotError("Tipo de gráfico desconhecido.")

        return command

    def run(self):
        check_plot_dependencies()
        _apply_fio_plot_compatibility()

        os.environ.setdefault("MPLBACKEND", "Agg")
        from fio_plot import main as fio_plot_main

        data_dir = self._find_data_directory()

        if self.config["graph"] == self.GRAPH_LINE:
            self._validate_line_logs(data_dir)

        output_png = self.result.output_root / "grafico.png"
        command = self._build_command(data_dir, output_png)

        try:
            return_code, output = run_embedded_cli(
                "fio-plot",
                fio_plot_main,
                command[1:],
            )
        except Exception as exc:
            raise PlotError(
                "Não foi possível executar o fio-plot:\n" + str(exc)
            ) from exc

        if return_code != 0:
            details = output.strip() or "fio-plot terminou sem mensagem."
            raise PlotError(
                "O fio-plot não conseguiu gerar o gráfico.\n\n"
                f"Detalhes:\n{details[-6000:]}"
            )

        if not output_png.is_file() or output_png.stat().st_size == 0:
            details = output.strip()
            message = (
                "O fio-plot terminou sem erro, mas o arquivo grafico.png "
                "não foi criado."
            )
            if details:
                message += "\n\nDetalhes:\n" + details[-5000:]
            raise PlotError(message)

        return output_png
