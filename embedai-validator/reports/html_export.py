"""HTML report exporter using Jinja2."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ai.recommendations import build_summary_recommendations
from core.result_model import RunResult
from utils.logger import get_logger
from utils.paths import PROJECT_ROOT, timestamped_path

log = get_logger(__name__)

_TEMPLATES_DIR = PROJECT_ROOT / "reports" / "templates"


def export_html(run: RunResult, path: Path | None = None) -> Path:
    """Render the HTML report and return its path."""
    out = path or timestamped_path("report", "html")

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("report.html.j2")

    recommendations = build_summary_recommendations(run)

    html = template.render(
        run=run,
        recommendations=recommendations,
    )
    out.write_text(html, encoding="utf-8")
    log.info("HTML report saved → %s", out)
    return out
