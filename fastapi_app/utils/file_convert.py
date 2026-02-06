from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from pathlib import Path


def docx_to_pdf(docx_path: Path, pdf_path: Path):
    document = Document(docx_path)
    c = canvas.Canvas(str(pdf_path), pagesize=A4)

    width, height = A4
    x, y = 40, height - 40

    for para in document.paragraphs:
        if y < 40:
            c.showPage()
            y = height - 40

        c.drawString(x, y, para.text)
        y -= 14

    c.save()
