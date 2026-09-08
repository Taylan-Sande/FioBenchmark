"""Exportação de relatório HTML a partir de uma pasta de sessão."""

from __future__ import annotations

import base64
import html
from datetime import datetime
from pathlib import Path


def _img_data_uri(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if not data:
        return None
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/png;base64,{b64}"


def build_html_report(
    session_dir: Path,
    config: dict | None = None,
    title: str = "Relatório FIO Benchmark",
) -> str:
    session_dir = Path(session_dir)
    pngs = sorted(session_dir.glob("*.png"))
    jsons = sorted(session_dir.rglob("*.json"))
    logs = sorted(session_dir.rglob("*.log"))

    rows = []
    if config:
        keys = [
            ("graph", "Gráfico"),
            ("generate_all", "Gerar todos"),
            ("mode", "Modo"),
            ("block_size", "Block size"),
            ("size_mb", "Tamanho (MB)"),
            ("runtime", "Runtime (s)"),
            ("ramp_time", "Ramp (s)"),
            ("iodepths", "IODepths"),
            ("numjobs", "NumJobs"),
            ("log_metric", "Métrica Line"),
            ("log_interval", "LOG interval (ms)"),
            ("title", "Título"),
            ("target_root", "Unidade testada"),
            ("results_root", "Pasta resultados"),
        ]
        for key, label in keys:
            if key not in config or config[key] is None:
                continue
            val = config[key]
            if isinstance(val, (list, tuple)):
                val = " ".join(str(x) for x in val)
            rows.append(
                f"<tr><th>{html.escape(label)}</th>"
                f"<td>{html.escape(str(val))}</td></tr>"
            )

    figures = []
    for png in pngs:
        uri = _img_data_uri(png)
        if not uri:
            continue
        figures.append(
            f"<figure><figcaption>{html.escape(png.name)}</figcaption>"
            f'<img src="{uri}" alt="{html.escape(png.name)}"/></figure>'
        )

    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    body_figs = "\n".join(figures) or "<p>Nenhum gráfico PNG encontrado.</p>"
    body_params = (
        f"<table>{''.join(rows)}</table>"
        if rows
        else "<p>Parâmetros não disponíveis.</p>"
    )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<title>{html.escape(title)}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 24px; background: #111; color: #eee; }}
h1, h2 {{ color: #fff; }}
table {{ border-collapse: collapse; margin: 12px 0 24px; }}
th, td {{ border: 1px solid #444; padding: 6px 10px; text-align: left; }}
th {{ background: #222; }}
figure {{ margin: 16px 0 32px; }}
img {{ max-width: 100%; height: auto; background: #fff; border-radius: 4px; }}
.meta {{ color: #aaa; font-size: 0.9rem; }}
code {{ background: #222; padding: 2px 6px; border-radius: 3px; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<p class="meta">Gerado em {html.escape(generated)}<br/>
Sessão: <code>{html.escape(str(session_dir))}</code></p>
<h2>Parâmetros</h2>
{body_params}
<h2>Arquivos</h2>
<p class="meta">PNG: {len(pngs)} · JSON: {len(jsons)} · LOG: {len(logs)}</p>
<h2>Gráficos</h2>
{body_figs}
</body>
</html>
"""


def export_html_report(
    session_dir: Path,
    output_path: Path | None = None,
    config: dict | None = None,
    title: str = "Relatório FIO Benchmark",
) -> Path:
    session_dir = Path(session_dir)
    if output_path is None:
        output_path = session_dir / "relatorio.html"
    else:
        output_path = Path(output_path)

    html_text = build_html_report(session_dir, config=config, title=title)
    output_path.write_text(html_text, encoding="utf-8")
    return output_path
