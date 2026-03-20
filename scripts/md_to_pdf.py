"""Convert markdown files to PDF using fpdf2."""

import sys
import os
import re
from fpdf import FPDF

class MarkdownPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)
        self.set_margins(20, 20, 20)

    def header(self):
        pass

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")
        self.set_text_color(0)


def clean(text):
    """Remove markdown syntax and normalize unicode for plain text rendering."""
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'`(.*?)`', r'\1', text)
    text = re.sub(r'~~(.*?)~~', r'\1', text)
    # Replace unicode chars not supported by latin-1 fonts
    text = text.replace('\u2014', '-').replace('\u2013', '-')
    text = text.replace('\u2019', "'").replace('\u2018', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2b06', '^').replace('\u2b07', 'v')
    text = text.replace('\u27a1', '->').replace('\u2b05', '<-')
    text = text.replace('📈', '[+]').replace('📉', '[-]').replace('➡️', '[=]')
    text = text.replace('🔴', '[CRIT]').replace('🟠', '[HIGH]').replace('🟡', '[MED]')
    text = text.replace('⭐', '*')
    # Strip any remaining non-latin-1 characters
    text = text.encode('latin-1', errors='replace').decode('latin-1')
    return text.strip()


def convert(md_path, pdf_path):
    pdf = MarkdownPDF()
    pdf.add_page()

    with open(md_path, encoding="utf-8") as f:
        lines = f.readlines()

    in_table = False
    table_rows = []

    def flush_table():
        nonlocal table_rows
        if not table_rows:
            return

        col_widths = None
        data_rows = []
        for row in table_rows:
            cells = [clean(c) for c in row]
            # skip separator rows (---|--- etc)
            if all(re.match(r'^[-: ]+$', c) for c in cells if c):
                continue
            data_rows.append(cells)

        if not data_rows:
            table_rows = []
            return

        num_cols = max(len(r) for r in data_rows)
        page_w = pdf.w - pdf.l_margin - pdf.r_margin
        col_w = page_w / num_cols if num_cols > 0 else page_w

        for i, row in enumerate(data_rows):
            if i == 0:
                pdf.set_font("Helvetica", "B", 7.5)
                pdf.set_fill_color(220, 220, 220)
                fill = True
            else:
                pdf.set_font("Helvetica", "", 7)
                pdf.set_fill_color(245, 245, 245) if i % 2 == 0 else pdf.set_fill_color(255, 255, 255)
                fill = True

            # Pad row to num_cols
            while len(row) < num_cols:
                row.append("")

            for cell in row[:num_cols]:
                pdf.cell(col_w, 5.5, cell[:60], border=1, fill=fill)
            pdf.ln()

        pdf.ln(3)
        table_rows = []

    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\n")

        # Detect table rows
        if line.strip().startswith("|"):
            in_table = True
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            table_rows.append(cells)
            i += 1
            continue
        else:
            if in_table:
                flush_table()
                in_table = False

        stripped = line.strip()

        # H1
        if stripped.startswith("# ") and not stripped.startswith("## "):
            pdf.set_font("Helvetica", "B", 16)
            pdf.set_text_color(30, 30, 30)
            pdf.multi_cell(0, 9, clean(stripped[2:]))
            pdf.ln(2)

        # H2
        elif stripped.startswith("## "):
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_text_color(40, 40, 40)
            pdf.ln(3)
            pdf.multi_cell(0, 8, clean(stripped[3:]))
            pdf.ln(1)

        # H3
        elif stripped.startswith("### "):
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(60, 60, 60)
            pdf.ln(2)
            pdf.multi_cell(0, 7, clean(stripped[4:]))
            pdf.ln(1)

        # HR
        elif stripped.startswith("---"):
            pdf.set_draw_color(180, 180, 180)
            pdf.ln(2)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(3)

        # Bold line (metadata like **Generated:**)
        elif stripped.startswith("**") and "**" in stripped[2:]:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(80, 80, 80)
            pdf.multi_cell(0, 6, clean(stripped))
            pdf.ln(0.5)

        # Italic/blockquote
        elif stripped.startswith(">"):
            pdf.set_font("Helvetica", "I", 8.5)
            pdf.set_text_color(100, 100, 100)
            pdf.multi_cell(0, 6, clean(stripped[1:].strip()))
            pdf.ln(1)

        # Empty line
        elif stripped == "":
            pdf.ln(2)

        # Regular text
        else:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(50, 50, 50)
            pdf.multi_cell(0, 6, clean(stripped))

        i += 1

    # Flush any remaining table
    if in_table:
        flush_table()

    pdf.output(pdf_path)
    print(f"Saved: {pdf_path}")


if __name__ == "__main__":
    files = [
        ("output/insights/HP_App_v20.2_vs_v26.0_Comparison_US.md",
         "output/insights/HP_App_v20.2_vs_v26.0_Comparison_US.pdf"),
        ("output/insights/HP_App_v20.2_vs_v26.0_Comparison_AllCountries.md",
         "output/insights/HP_App_v20.2_vs_v26.0_Comparison_AllCountries.pdf"),
    ]
    for md, pdf in files:
        convert(md, pdf)
