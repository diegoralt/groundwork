#!/usr/bin/env python3
"""ATS sanity check: extrae texto del PDF y reporta cobertura de keywords.

Los datos de contacto que debe encontrar salen de config.yaml (o
config.example.yaml de respaldo) — nunca hardcodeados en el script.
"""
import re
import sys
from pathlib import Path

from pypdf import PdfReader

from _config import load_config

MIN_CHARS_OK = 200  # ponytail: bajo esto, el PDF probablemente es ilegible para un ATS
_contact = load_config()["contact"]
CONTACT_MUST_APPEAR = [_contact["email"], _contact["phone"]]


def extract_text(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _normalize(s: str) -> str:
    """Colapsa todo espacio en blanco a uno solo: el PDF parte frases largas en dos líneas
    ('Navigation\\nComponent') y sin esto toda keyword multi-palabra da falso negativo."""
    return re.sub(r"\s+", " ", s).lower()


def check_keywords(text: str, keywords: list[str]) -> dict[str, bool]:
    normalized = _normalize(text)
    return {kw: _normalize(kw) in normalized for kw in keywords}


def check_contact_info(text: str) -> dict[str, bool]:
    lowered = text.lower()
    digits_only = re.sub(r"\D", "", text)
    # el teléfono suele extraerse con espacios/guiones ("+52 555 000 0000"); comparar solo dígitos
    return {c: (c in digits_only if c.isdigit() else c.lower() in lowered) for c in CONTACT_MUST_APPEAR}


def check_garbled(text: str) -> list[str]:
    issues = []
    if "�" in text:
        issues.append("carácter de reemplazo '�' presente — posible fuente/encoding roto")
    if re.search(r"\(cid:\d+\)", text):
        issues.append("marcadores '(cid:N)' presentes — glifo sin mapeo a texto real")
    # ponytail: un carácter fuera del set de la fuente no da '�' ni '(cid:N)' — reportlab
    # lo sustituye por '\x7f' o por '■' según el caso (ambos observados: '•' y un emoji).
    # Se enumeran las dos sustituciones reales en vez de modelar cobertura de fuentes.
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f■]", text):
        issues.append("glifo no representable por la fuente (sale como caja) — "
                      "revisa el markdown fuente por símbolos fuera de WinAnsi, ej. emoji")
    return issues


def report(pdf_path: str, keywords: list[str]) -> int:
    text = extract_text(pdf_path)
    ok = True

    print(f"Texto extraído: {len(text)} caracteres")
    if len(text) < MIN_CHARS_OK:
        print("⚠️  Muy poco texto extraído — el PDF puede ser ilegible para un ATS")
        ok = False

    for issue in check_garbled(text):
        print(f"⚠️  {issue}")
        ok = False

    print("\nDatos de contacto como texto real:")
    for c, found in check_contact_info(text).items():
        print(f"  {'✅' if found else '❌'} {c}")
        ok = ok and found

    results = check_keywords(text, keywords)
    hits = sum(results.values())
    print(f"\nKeywords: {hits}/{len(keywords)} encontradas\n")
    for kw, found in results.items():
        print(f"  {'✅' if found else '❌'} {kw}")

    return 0 if ok and hits == len(keywords) else 1


def _load_keywords(arg: str) -> list[str]:
    path = Path(arg)
    if path.exists():
        return [line.strip() for line in path.read_text().splitlines() if line.strip()]
    return [kw.strip() for kw in arg.split(",") if kw.strip()]


def demo() -> None:
    """ponytail self-check: genera un PDF mínimo y verifica que la extracción funciona."""
    from reportlab.pdfgen import canvas

    tmp_pdf = "/tmp/_ats_check_demo.pdf"
    c = canvas.Canvas(tmp_pdf)
    c.drawString(100, 750, f"Python Kotlin Leadership {CONTACT_MUST_APPEAR[0]} {CONTACT_MUST_APPEAR[1]}")
    c.save()

    text = extract_text(tmp_pdf)
    assert "Python" in text, f"extracción rota, obtuve: {text!r}"
    assert check_garbled(text) == [], "falso positivo de texto roto"
    assert check_garbled("texto con � roto") != [], "no detectó el carácter de reemplazo"
    assert check_garbled("glifo\x7froto") != [], "no detectó el glifo fuera de la fuente"
    assert check_garbled("emoji sustituido por ■") != [], "no detectó la caja de glifo ausente"
    assert check_garbled("salto\nreal\ty tab\r\n") == [], "los espacios en blanco no son glifos rotos"

    results = check_keywords(text, ["Python", "Rust"])
    assert results["Python"] is True
    assert results["Rust"] is False

    # una keyword de varias palabras partida por salto de línea debe seguir contando
    wrapped = check_keywords("... Navigation\nComponent ...", ["Navigation Component"])
    assert wrapped["Navigation Component"] is True, "salto de línea rompe el match multi-palabra"

    contact = check_contact_info(text)
    assert all(contact.values()), f"contacto no detectado: {contact}"

    Path(tmp_pdf).unlink()
    print("demo ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--demo":
        demo()
        sys.exit(0)

    if len(sys.argv) != 3:
        print("Uso: ats_check.py <pdf_path> <keywords: 'a,b,c' o archivo .txt>")
        sys.exit(2)

    keywords = _load_keywords(sys.argv[2])
    sys.exit(report(sys.argv[1], keywords))
