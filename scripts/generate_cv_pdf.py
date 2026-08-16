#!/usr/bin/env python3
"""Genera el PDF de un CV a partir de su Markdown en cvs/.

Formato Harvard: sin foto, cronología inversa, una sola columna, texto real
extraíble por un ATS (verificar después con ats_check.py).

Uso: generate_cv_pdf.py <cv.md> <salida.pdf>
     generate_cv_pdf.py --demo
"""
import re
import sys
from pathlib import Path

from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

from _config import load_config

# ponytail: Helvetica es built-in (sin fuentes externas) pero solo cubre WinAnsi.
# Los pocos glifos fuera de ese set se sustituyen en vez de registrar un TTF.
NON_WINANSI = {"→": "-&gt;", "≠": "!=", "✅": "-", "⚠️": "!", "•": "-"}

NAME = ParagraphStyle("name", fontName="Helvetica-Bold", fontSize=17, leading=20, spaceAfter=2)
CONTACT = ParagraphStyle("contact", fontName="Helvetica", fontSize=8.5, leading=11, spaceAfter=10)
SECTION = ParagraphStyle(
    "section", fontName="Helvetica-Bold", fontSize=10.5, leading=13,
    spaceBefore=7.5, spaceAfter=3.5, textColor="#1a1a1a",
)
JOB = ParagraphStyle("job", fontName="Helvetica-Bold", fontSize=9.5, leading=12, spaceBefore=6)
META = ParagraphStyle("meta", fontName="Helvetica-Oblique", fontSize=8.5, leading=11, spaceAfter=3)
BODY = ParagraphStyle(
    "body", fontName="Helvetica", fontSize=8.5, leading=10.7,
    alignment=TA_JUSTIFY, spaceAfter=3,
)
BULLET = ParagraphStyle("bullet", parent=BODY, spaceAfter=1.7)


def _inline(text: str) -> str:
    """Markdown inline -> markup de ReportLab. El orden importa: escapar primero."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for bad, good in NON_WINANSI.items():
        text = text.replace(bad, good)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<link href="\2"><u>\1</u></link>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text


def strip_frontmatter_and_notes(md: str) -> str:
    """Quita el frontmatter YAML y las notas internas que van tras el '---' final.

    Las notas documentan gaps y correcciones para uso interno: nunca al PDF.

    Avisa si lo descartado trae encabezados: un '---' usado como regla horizontal
    entre secciones (lo que emite cualquier LLM al que le pidas un CV en markdown)
    se lleva el resto del documento sin que nada lo note. Las notas internas
    nunca llevan encabezados — solo etiquetas '**Nota**:' — así que la presencia
    de un '#' del lado descartado distingue el error del uso legítimo.
    """
    if md.startswith("---"):
        md = md.split("---", 2)[2]
    parts = re.split(r"^---\s*$", md, flags=re.MULTILINE)
    dropped = "".join(parts[1:])
    if re.search(r"^#{1,3}\s", dropped, flags=re.MULTILINE):
        print(
            f"⚠️  {len(dropped.splitlines())} líneas con encabezados quedaron fuera del PDF: "
            "el primer '---' después del frontmatter marca el inicio de las notas internas. "
            "No uses '---' como separador de secciones dentro del CV.",
            file=sys.stderr,
        )
    return parts[0]


def build_flowables(md: str) -> list:
    flow, bullets = [], []

    def flush_bullets():
        if bullets:
            flow.append(ListFlowable(
                [ListItem(Paragraph(b, BULLET), leftIndent=12) for b in bullets],
                bulletType="bullet", bulletFontSize=6, start="circle",
                leftIndent=11, bulletOffsetY=-1,
            ))
            bullets.clear()

    for raw in strip_frontmatter_and_notes(md).splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith("# "):
            flush_bullets()
            flow.append(Paragraph(_inline(line[2:]), NAME))
        elif line.startswith("## "):
            flush_bullets()
            flow.append(Paragraph(_inline(line[3:]).upper(), SECTION))
        elif line.startswith("### "):
            flush_bullets()
            flow.append(Paragraph(_inline(line[4:]), JOB))
        elif line.startswith("- "):
            bullets.append(_inline(line[2:]))
        else:
            flush_bullets()
            # la línea de contacto es la primera del documento tras el nombre
            style = CONTACT if not flow or getattr(flow[-1], "style", None) is NAME else (
                META if line.startswith("**") and line.endswith("**") else BODY
            )
            flow.append(Paragraph(_inline(line), style))

    flush_bullets()
    return flow


def generate(md_path: str, pdf_path: str) -> None:
    author = load_config()["contact"]["name"]
    doc = SimpleDocTemplate(
        pdf_path, pagesize=letter,
        leftMargin=0.62 * inch, rightMargin=0.62 * inch,
        topMargin=0.4 * inch, bottomMargin=0.4 * inch,
        title=Path(pdf_path).stem, author=author,
    )
    doc.build(build_flowables(Path(md_path).read_text(encoding="utf-8")))
    print(f"PDF generado: {pdf_path} ({doc.page} paginas)")


def demo() -> None:
    """ponytail self-check: lo que se rompe en silencio es el parser, no el layout."""
    assert _inline("**x** y") == "<b>x</b> y"
    assert _inline("[a](http://b)") == '<link href="http://b"><u>a</u></link>'
    assert _inline("a & b < c") == "a &amp; b &lt; c"
    assert _inline("20% →") == "20% -&gt;", _inline("20% →")

    md = "---\ntype: cv\n---\n\n# Nombre\n\nmail | tel\n\n## S\n\n### Rol\n\n- uno\n- dos\n\n---\n\n**Nota**: interna\n"
    assert "Nota" not in strip_frontmatter_and_notes(md), "las notas internas se filtran al PDF"
    assert "type: cv" not in strip_frontmatter_and_notes(md), "el frontmatter se filtra al PDF"

    # un '---' usado como regla horizontal se lleva el resto del CV: debe avisar
    import io
    from contextlib import redirect_stderr

    truncated = "---\ntype: cv\n---\n\n# Nombre\n\n## Experiencia\n\n---\n\n## Educación\n\n### Uni\n"
    err = io.StringIO()
    with redirect_stderr(err):
        kept = strip_frontmatter_and_notes(truncated)
    assert "Educación" not in kept, "el corte en el '---' cambió de comportamiento"
    assert "quedaron fuera del PDF" in err.getvalue(), "el truncado silencioso no avisó"

    err = io.StringIO()
    with redirect_stderr(err):
        strip_frontmatter_and_notes(md)
    assert err.getvalue() == "", "las notas internas legítimas no deben disparar la alerta"

    flow = build_flowables(md)
    styles = [f.style.name for f in flow if hasattr(f, "style")]
    assert styles[:2] == ["name", "contact"], styles
    assert any(isinstance(f, ListFlowable) for f in flow), "los bullets no se agruparon"

    # una lista de bullets seguida de una línea plana (subtítulo en negritas) no debe tronar
    md2 = "# N\n\nmail\n\n## S\n\n### Rol\n\n**Grupo A:**\n- uno\n\n**Grupo B:**\n- dos\n"
    build_flowables(md2)
    print("demo ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--demo":
        demo()
        sys.exit(0)
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    generate(sys.argv[1], sys.argv[2])
