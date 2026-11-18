import csv
import html
import json
import re
from datetime import UTC, datetime
from io import BytesIO, StringIO
from textwrap import wrap

import xlsxwriter
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from pptx import Presentation
from pptx.util import Inches, Pt

FORMATS = {
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "csv": "text/csv",
    "md": "text/markdown",
    "html": "text/html",
}


def present(value) -> str:
    return (
        json.dumps(value, ensure_ascii=False, default=str) if isinstance(value, (dict, list)) else str(value)
    )


def csv_safe(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


def output_csv(columns: list[str], rows: list[dict]) -> bytes:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([csv_safe(c) for c in columns])
    writer.writerows([[csv_safe(row.get(column)) for column in columns] for row in rows])
    return output.getvalue().encode("utf-8-sig")


def figure(chart: dict):
    if chart.get("type") not in {"bar", "line", "pie", "histogram"} or not chart.get("rows"):
        return None
    x, y = chart["x"], chart["y"]
    rows = chart["rows"][:30]
    labels = [str(row.get(x))[:20] for row in rows if isinstance(row.get(y), (int, float))]
    values = [row[y] for row in rows if isinstance(row.get(y), (int, float))]
    if not values:
        return None
    fig = Figure(figsize=(8, 3.2), layout="constrained")
    axis = fig.subplots()
    if chart["type"] == "line":
        axis.plot(labels, values, color="#167851")
    else:
        axis.bar(labels, values, color="#167851")
    axis.set_title(chart["method"])
    axis.tick_params(axis="x", labelrotation=60, labelsize=7)
    image = BytesIO()
    FigureCanvasAgg(fig).print_png(image)
    image.seek(0)
    return fig, image


def generate(format_name: str, title: str, result: dict) -> bytes:
    stamped = datetime.now(UTC).isoformat()
    sections = [
        ("Executive summary", result["summary"]),
        ("Objective", result["plan"]["objective"]),
        ("Source dataset and version", result.get("source") or "External sources are listed below."),
        ("Method", result["method"]),
        ("Parameters", result.get("parameters", {})),
        ("Assumptions", result.get("assumptions", [])),
        ("Limitations", result["limitations"]),
        ("Recommendations", result.get("recommendations", [])),
        ("Generated", stamped),
    ]
    if result.get("query"):
        sections.append(("Executed SQL", result["query"]["sql"]))
    for item in result.get("role_findings", []):
        sections.append(
            (f"Finding / {item['role']} / {item['metric']}", item.get("values", item.get("reason", "")))
        )
    for key in ("model", "comparison", "forecast"):
        if key in result:
            sections.append(
                (key.title(), {k: v for k, v in result[key].items() if k not in {"predictions", "observed"}})
            )
    for source in result.get("evidence", []):
        sections.append(
            ("Source reference", f"{source['title']} | {source['url']} | {source['retrieved_at']}")
        )
    table = result.get("query") or result.get("chart") or {}
    rows = table.get("rows", [])
    columns = table.get("columns") or (list(rows[0]) if rows else [])
    summary = [{"Section": key, "Value": present(value)} for key, value in sections]
    chart = result.get("chart")
    graphic = figure(chart) if chart and format_name in {"pdf", "pptx", "xlsx"} else None
    output = BytesIO()
    if format_name == "csv":
        if not rows:
            return output_csv(["Section", "Value"], summary)
        # One rectangular CSV preserves both the result table and report provenance.
        fields = ["Record type", "Section", "Value"] + [f"Data: {col}" for col in columns]
        records = [{"Record type": "report"} | row for row in summary]
        records.extend({"Record type": "data"} | {f"Data: {c}": row.get(c) for c in columns} for row in rows)
        return output_csv(fields, records)
    if format_name == "md":

        def plain(value):
            escaped = html.escape(str(value), quote=False)
            return re.sub(r"([\x60*_\[\]#!|])", r"\\\1", escaped)

        markdown = [f"# {plain(title)}", *[f"## {plain(k)}\n\n{plain(present(v))}" for k, v in sections]]
        if columns:
            markdown.extend(
                [
                    "## Result data",
                    "| " + " | ".join(map(plain, columns)) + " |",
                    "| " + " | ".join("---" for _ in columns) + " |",
                ]
            )
            markdown.extend(
                "| " + " | ".join(plain(row.get(c, "")).replace("\n", " ") for c in columns) + " |"
                for row in rows
            )
        return "\n\n".join(markdown).encode()
    if format_name == "html":
        body = "".join(f"<h2>{html.escape(k)}</h2><p>{html.escape(present(v))}</p>" for k, v in sections)
        headers = "".join(f"<th>{html.escape(c)}</th>" for c in columns)
        cells = "".join(
            "<tr>" + "".join(f"<td>{html.escape(present(row.get(c, '')))}</td>" for c in columns) + "</tr>"
            for row in rows
        )
        data_table = (
            f"<h2>Result data</h2><table><thead><tr>{headers}</tr></thead><tbody>{cells}</tbody></table>"
            if rows
            else ""
        )
        return (
            f"<!doctype html><html lang='en'><meta charset='utf-8'><title>{html.escape(title)}</title>"
            f"<body><h1>{html.escape(title)}</h1>{body}{data_table}</body></html>"
        ).encode()
    if format_name == "xlsx":
        with xlsxwriter.Workbook(
            output,
            {
                "in_memory": True,
                "strings_to_formulas": False,
                "strings_to_urls": False,
                "nan_inf_to_errors": True,
            },
        ) as workbook:
            heading = workbook.add_format({"bold": True, "bg_color": "#dcefe5"})
            overview = workbook.add_worksheet("Summary")
            overview.set_column("A:A", 34)
            overview.set_column("B:B", 72)
            overview.write_row(0, 0, [title, stamped], heading)
            for i, row in enumerate(summary, 1):
                overview.write_row(i, 0, [row["Section"], row["Value"][:32767]])
            if rows:
                sheet = workbook.add_worksheet("Result data")
                sheet.freeze_panes(1, 0)
                sheet.write_row(0, 0, columns, heading)
                for i, row in enumerate(rows, 1):
                    sheet.write_row(i, 0, [row.get(c) for c in columns])
            if graphic:
                workbook.add_worksheet("Chart").insert_image("A1", "chart.png", {"image_data": graphic[1]})
    elif format_name == "pdf":
        lines = []
        for section, value in sections:
            lines.extend([section, *wrap(present(value), width=95), ""])
        for row in rows[:20]:
            lines.extend(wrap(present(row), width=95))
        with PdfPages(output, metadata={"Title": title}) as pdf:
            chunks = [lines[i : i + 45] for i in range(0, len(lines), 45)]
            for index, chunk in enumerate(chunks):
                page = Figure(figsize=(8.27, 11.69))
                page.text(0.08, 0.95, title[:90], size=17, color="#174d3a")
                page.text(0.08, 0.90, "\n".join(chunk), va="top", size=8, linespacing=1.38)
                page.text(0.08, 0.05, f"{index + 1} / {len(chunks) + bool(graphic)}", size=8)
                pdf.savefig(page)
            if graphic:
                pdf.savefig(graphic[0])
    elif format_name == "pptx":
        presentation = Presentation()
        for heading, group in [(title, sections[:4]), ("Findings and evidence", sections[4:])]:
            for offset in range(0, len(group), 6):
                slide = presentation.slides.add_slide(presentation.slide_layouts[1])
                slide.shapes.title.text = heading
                text_frame = slide.placeholders[1].text_frame
                text_frame.clear()
                for index, (label, value) in enumerate(group[offset : offset + 6]):
                    paragraph = text_frame.paragraphs[0] if index == 0 else text_frame.add_paragraph()
                    paragraph.text = f"{label} — {present(value)[:230]}"
                    paragraph.font.size = Pt(15)
        if graphic:
            slide = presentation.slides.add_slide(presentation.slide_layouts[5])
            slide.shapes.title.text = "Analysis chart"
            slide.shapes.add_picture(graphic[1], Inches(0.6), Inches(1.6), width=Inches(8.8))
        presentation.save(output)
    else:
        raise ValueError("Unsupported report format.")
    return output.getvalue()
