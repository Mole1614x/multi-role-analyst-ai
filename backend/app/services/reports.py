import csv
import html
import json
import re
from base64 import b64encode
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
    kind = chart.get("type")
    if kind not in {"bar", "line", "pie", "histogram", "scatter", "heatmap"} or not chart.get("rows"):
        return None
    fig = Figure(figsize=(8, 3.2), layout="constrained")
    axis = fig.subplots()
    if kind == "heatmap":
        columns = chart["columns"]
        matrix = [
            [row[column] if row[column] is not None else float("nan") for column in columns]
            for row in chart["rows"]
        ]
        heatmap = axis.imshow(matrix, vmin=-1, vmax=1, cmap="BrBG")
        axis.set_xticks(range(len(columns)), columns)
        axis.set_yticks(range(len(columns)), columns)
        fig.colorbar(heatmap, ax=axis, label="Pearson correlation")
    else:
        x, y = chart["x"], chart["y"]
        rows = chart["rows"][-60:] if kind == "line" else chart["rows"][:30]
        points = [
            row
            for row in rows
            if isinstance(row.get(y), (int, float))
            and (kind != "scatter" or isinstance(row.get(x), (int, float)))
        ]
        if not points:
            return None
        labels = [str(row.get(x))[:20] for row in points]
        values = [row[y] for row in points]
        if kind == "line":
            indices = list(range(len(points)))
            axis.plot(indices, values, color="#167851")
            if any("lower" in row for row in points):
                lower = [row.get("lower", float("nan")) for row in points]
                upper = [row.get("upper", float("nan")) for row in points]
                axis.fill_between(indices, lower, upper, color="#6b84bd", alpha=0.25)
            spacing = max(1, len(labels) // 8)
            axis.set_xticks(indices[::spacing], labels[::spacing])
        elif kind == "pie" and any(values):
            axis.pie(values, labels=labels, textprops={"fontsize": 8, "parse_math": False})
        elif kind == "scatter":
            axis.scatter([row[x] for row in points], values, color="#167851")
            axis.set_xlabel(x, parse_math=False)
            axis.set_ylabel(y, parse_math=False)
        else:
            axis.bar(labels, values, color="#167851")
    axis.set_title(chart["method"], parse_math=False)
    if kind != "pie":
        axis.tick_params(axis="x", labelrotation=60, labelsize=7)
        for label in axis.get_xticklabels() + axis.get_yticklabels():
            label.set_parse_math(False)
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
    for index, step in enumerate(result.get("completed_steps", []), start=1):
        details = {
            key: step[key]
            for key in ("summary", "source", "method", "role_findings", "claim_checks", "limitations")
            if key in step
        }
        sections.append((f"Workflow step {index} / {step['plan']['objective']}", details))
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
    for check in result.get("claim_checks", []):
        sections.append(("Research claim and citations", check))
    for source in result.get("evidence", []):
        sections.append(
            ("Source reference", f"{source['title']} | {source['url']} | {source['retrieved_at']}")
        )
    table = result.get("query") or result.get("chart") or {}
    rows = table.get("rows", [])
    columns = table.get("columns") or (list(rows[0]) if rows else [])
    summary = [{"Section": key, "Value": present(value)} for key, value in sections]
    chart = result.get("chart")
    graphic = figure(chart) if chart and format_name in {"pdf", "pptx", "xlsx", "html"} else None
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
        graphic_html = ""
        if graphic:
            encoded = b64encode(graphic[1].getvalue()).decode("ascii")
            graphic_html = (
                f"<h2>Analysis chart</h2><img alt='Analysis chart' src='data:image/png;base64,{encoded}'>"
            )
        return (
            f"<!doctype html><html lang='en'><meta charset='utf-8'><title>{html.escape(title)}</title>"
            f"<body><h1>{html.escape(title)}</h1>{body}{graphic_html}{data_table}</body></html>"
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
                page.text(0.08, 0.95, title[:90], size=17, color="#174d3a", parse_math=False)
                page.text(0.08, 0.90, "\n".join(chunk), va="top", size=8, linespacing=1.38, parse_math=False)
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
        if columns and rows:
            slide = presentation.slides.add_slide(presentation.slide_layouts[5])
            slide.shapes.title.text = "Result data preview"
            fields = columns[:6]
            entries = rows[:8]
            table = slide.shapes.add_table(
                len(entries) + 1, len(fields), Inches(0.5), Inches(1.5), Inches(9), Inches(4)
            ).table
            for row_index, values in enumerate(
                [fields] + [[entry.get(c) for c in fields] for entry in entries]
            ):
                for column_index, cell in enumerate(values):
                    box = table.cell(row_index, column_index).text_frame
                    box.text = ("—" if cell is None else str(cell))[:55]
                    box.paragraphs[0].font.size = Pt(11)
        if graphic:
            slide = presentation.slides.add_slide(presentation.slide_layouts[5])
            slide.shapes.title.text = "Analysis chart"
            slide.shapes.add_picture(graphic[1], Inches(0.6), Inches(1.6), width=Inches(8.8))
        presentation.save(output)
    else:
        raise ValueError("Unsupported report format.")
    return output.getvalue()
