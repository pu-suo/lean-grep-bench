"""Convert data/benchmark.jsonl into a human-viewable CSV or HTML file."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path
from typing import Any

COLUMNS: list[str] = [
    "id",
    "scenario",
    "query",
    "ground_truth_name",
    "ground_truth_source",
    "context.enclosing_decl",
    "context.enclosing_signature",
    "context.goal",
    "context.hypotheses",
    "context.prior_tactics",
    "provenance.source_file",
    "provenance.line",
    "provenance.tactic_kind",
    "generation.generator_model",
    "generation.verifier_model",
    "generation.seed",
]

LIST_JOIN = " | "
DEFAULT_MAX_LEN = 500
SCENARIO_COLORS = {
    "local_only": "#dbeafe",
    "mathlib_only": "#dcfce7",
    "mixed": "#fef3c7",
}


def load_items(path: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def _truncate(s: str, max_len: int | None) -> str:
    if max_len is None or len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def flatten_for_csv(item: dict[str, Any], max_len: int | None) -> list[str]:
    ctx = item.get("context") or {}
    prov = item.get("provenance") or {}
    gen = item.get("generation") or {}

    def cell(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, list):
            return _truncate(LIST_JOIN.join(str(v) for v in value), max_len)
        return _truncate(str(value), max_len)

    return [
        cell(item.get("id")),
        cell(item.get("scenario")),
        cell(item.get("query")),
        cell(item.get("ground_truth_name")),
        cell(item.get("ground_truth_source")),
        cell(ctx.get("enclosing_decl")),
        cell(ctx.get("enclosing_signature")),
        cell(ctx.get("goal")),
        cell(ctx.get("hypotheses")),
        cell(ctx.get("prior_tactics")),
        cell(prov.get("source_file")),
        cell(prov.get("line")),
        cell(prov.get("tactic_kind")),
        cell(gen.get("generator_model")),
        cell(gen.get("verifier_model")),
        cell(gen.get("seed")),
    ]


def write_csv(items: list[dict[str, Any]], out: Path, max_len: int | None) -> None:
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(COLUMNS)
        for item in items:
            writer.writerow(flatten_for_csv(item, max_len))


def _h(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value))


def _list_html(values: list[Any] | None) -> str:
    if not values:
        return ""
    parts = ["<ul>"]
    for v in values:
        parts.append(f"<li><code>{_h(v)}</code></li>")
    parts.append("</ul>")
    return "".join(parts)


def _row_html(item: dict[str, Any]) -> str:
    ctx = item.get("context") or {}
    prov = item.get("provenance") or {}
    gen = item.get("generation") or {}
    scenario = item.get("scenario") or ""

    cells = [
        f'<td class="id">{_h(item.get("id"))}</td>',
        f'<td class="scenario scenario-{_h(scenario)}">{_h(scenario)}</td>',
        f"<td>{_h(item.get('query'))}</td>",
        f"<td><code>{_h(item.get('ground_truth_name'))}</code></td>",
        f"<td>{_h(item.get('ground_truth_source'))}</td>",
        f"<td><code>{_h(ctx.get('enclosing_decl'))}</code></td>",
        f"<td class='sig'><code>{_h(ctx.get('enclosing_signature'))}</code></td>",
        f"<td><code>{_h(ctx.get('goal'))}</code></td>",
        f"<td>{_list_html(ctx.get('hypotheses'))}</td>",
        f"<td>{_list_html(ctx.get('prior_tactics'))}</td>",
        f"<td><code>{_h(prov.get('source_file'))}</code></td>",
        f"<td>{_h(prov.get('line'))}</td>",
        f"<td>{_h(prov.get('tactic_kind'))}</td>",
        f"<td>{_h(gen.get('generator_model'))}</td>",
        f"<td>{_h(gen.get('verifier_model'))}</td>",
        f"<td>{_h(gen.get('seed'))}</td>",
    ]
    return f'<tr data-scenario="{_h(scenario)}">{"".join(cells)}</tr>'


def write_html(items: list[dict[str, Any]], out: Path) -> None:
    headers = "".join(f"<th>{_h(c)}</th>" for c in COLUMNS)
    rows = "\n".join(_row_html(it) for it in items)
    scenarios = sorted({(it.get("scenario") or "") for it in items})
    options = '<option value="">all</option>' + "".join(
        f'<option value="{_h(s)}">{_h(s)}</option>' for s in scenarios if s
    )
    scenario_css = "\n".join(
        f"  tr td.scenario-{name} {{ background: {color}; }}"
        for name, color in SCENARIO_COLORS.items()
    )

    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Lean benchmark viewer ({len(items)} items)</title>
<style>
  body {{ font-family: system-ui, -apple-system, sans-serif; margin: 0; padding: 0; }}
  header {{ position: sticky; top: 0; background: #fff; padding: 0.5rem 1rem; border-bottom: 1px solid #ddd; z-index: 2; }}
  header label {{ font-size: 0.9rem; }}
  header select {{ font-size: 0.9rem; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
  thead th {{ position: sticky; top: 2.4rem; background: #f4f4f5; border-bottom: 2px solid #ccc; padding: 6px 8px; text-align: left; z-index: 1; }}
  td {{ border-bottom: 1px solid #eee; padding: 6px 8px; vertical-align: top; max-width: 480px; overflow-wrap: anywhere; }}
  td.sig {{ max-width: 640px; }}
  code {{ font-family: "DejaVu Sans Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace; font-size: 12px; white-space: pre-wrap; }}
  ul {{ margin: 0; padding-left: 1.1rem; }}
  li {{ margin: 1px 0; }}
  td.id {{ font-family: "DejaVu Sans Mono", ui-monospace, monospace; white-space: nowrap; }}
{scenario_css}
  tr.hidden {{ display: none; }}
</style>
</head>
<body>
<header>
  <label>Filter scenario:
    <select id="scenario-filter">{options}</select>
  </label>
  <span id="count" style="margin-left: 1rem; color: #666;"></span>
</header>
<table>
  <thead><tr>{headers}</tr></thead>
  <tbody id="rows">
{rows}
  </tbody>
</table>
<script>
  (function () {{
    const sel = document.getElementById('scenario-filter');
    const rows = Array.from(document.querySelectorAll('#rows tr'));
    const count = document.getElementById('count');
    function apply() {{
      const v = sel.value;
      let shown = 0;
      for (const r of rows) {{
        const match = !v || r.dataset.scenario === v;
        r.classList.toggle('hidden', !match);
        if (match) shown += 1;
      }}
      count.textContent = shown + ' / ' + rows.length + ' items';
    }}
    sel.addEventListener('change', apply);
    apply();
  }})();
</script>
</body>
</html>
"""
    out.write_text(doc, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="input", required=True, type=Path)
    parser.add_argument("--out", dest="output", required=True, type=Path)
    parser.add_argument("--format", choices=["csv", "html"], default="html")
    parser.add_argument(
        "--max-len",
        type=int,
        default=DEFAULT_MAX_LEN,
        help="Truncate long CSV cells to this length (default: 500).",
    )
    parser.add_argument(
        "--no-truncate",
        action="store_true",
        help="Do not truncate any CSV cells.",
    )
    args = parser.parse_args(argv)

    items = load_items(args.input)
    if args.format == "csv":
        max_len = None if args.no_truncate else args.max_len
        write_csv(items, args.output, max_len)
    else:
        write_html(items, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
