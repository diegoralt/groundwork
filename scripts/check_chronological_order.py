#!/usr/bin/env python3
"""Verifica cronología inversa estricta en la sección de Experiencia de un CV.

Salidas (convención de los checks obligatorios, ver docs/workflow.md):
  0 = OK: todas las entradas se evaluaron y están en orden.
  1 = FALLA: desorden real (o un inicio posterior a su fin).
  2 = NO EVALUADO: sin sección, sección sin entradas, o alguna entrada sin
      fechas legibles. Nunca cuenta como aprobado.

Alcance: solo la sección "## Experiencia (Profesional|Laboral)" o
"## (Professional )?Experience", hasta el siguiente "## " (los proyectos
quedan fuera) y antes de las notas internas (primer '---' del cuerpo, igual
que generate_cv_pdf.py). Cada "### Título" debe tener en su siguiente línea
no vacía un rango "Mes AAAA – Mes AAAA|Presente", con meses completos o
abreviados en español o inglés. No hay excepción manual: un bloque resumen
lleva sus fechas reales.

ponytail: parseo por regex sobre el formato Harvard de templates/cv-template.md,
no un parser de markdown genérico.

Uso: check_chronological_order.py <cv.md>
     check_chronological_order.py --demo
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
    # abreviaturas ES/EN (con o sin punto, el punto se quita antes de buscar)
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "jun": 6, "jul": 7, "ago": 8,
    "sep": 9, "sept": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12,
    "jan": 1, "apr": 4, "aug": 8, "dec": 12,
}
PRESENTE = (9999, 12)

SECTION_RE = re.compile(
    r"^## (?:Experiencia(?: Profesional| Laboral)?|(?:Professional )?Experience)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
DATE_TOKEN = r"[A-Za-zñÁÉÍÓÚáéíóúÑ]+\.?\s+\d{4}|Presente|Present"
RANGE_RE = re.compile(rf"({DATE_TOKEN})\s*[–—-]\s*({DATE_TOKEN})", re.IGNORECASE)


def body_of(md: str) -> str:
    """Quita frontmatter y notas internas (todo desde el primer '---' del cuerpo)."""
    if md.startswith("---"):
        md = md.split("---", 2)[2]
    return re.split(r"^---\s*$", md, flags=re.MULTILINE)[0]


def parse_date_token(token: str):
    """'Noviembre 2025' / 'Nov. 2025' -> (2025, 11); 'Presente' -> (9999, 12); None si no parsea."""
    token = token.strip().lower()
    if token in ("presente", "present"):
        return PRESENTE
    m = re.fullmatch(r"([a-záéíóúñ]+)\.?\s+(\d{4})", token)
    if not m:
        return None
    mes = MESES.get(m.group(1))
    return (int(m.group(2)), mes) if mes else None


def experience_section(md: str) -> str | None:
    """Todas las secciones de Experiencia concatenadas (un CV puede partirla en dos)."""
    body = body_of(md)
    partes = []
    for m in SECTION_RE.finditer(body):
        rest = body[m.end():]
        nxt = re.search(r"^## ", rest, re.MULTILINE)
        partes.append(rest[: nxt.start()] if nxt else rest)
    return "\n".join(partes) if partes else None


def extract_entries(section: str) -> list[tuple[str, tuple | None, tuple | None]]:
    """(título, inicio, fin) por cada '### ' de la sección; None si la fecha no se lee."""
    lines = section.split("\n")
    entries = []
    for i, line in enumerate(lines):
        if not line.startswith("### "):
            continue
        title = line[4:].strip()
        date_line = next((l for l in lines[i + 1:] if l.strip()), "")
        if date_line.startswith("#"):
            date_line = ""
        rm = RANGE_RE.search(date_line)
        start = parse_date_token(rm.group(1)) if rm else None
        end = parse_date_token(rm.group(2)) if rm else None
        entries.append((title, start, end))
    return entries


def check(md_path: str) -> int:
    try:
        text = Path(md_path).read_text(encoding="utf-8")
    except OSError as e:
        print(f"NO EVALUADO: no se pudo leer {md_path} ({e}).")
        return 2
    section = experience_section(text)
    if section is None:
        print("NO EVALUADO: no se encontró la sección de Experiencia (ES/EN).")
        return 2
    entries = extract_entries(section)
    if not entries:
        print("NO EVALUADO: la sección de Experiencia no tiene entradas '### '.")
        return 2

    broken, unevaluated = False, False
    prev_end = None
    print("Orden de Experiencia (fecha de fin, más reciente primero):\n")
    for title, start, end in entries:
        if start is None or end is None:
            unevaluated = True
            print(f"  ⚪ {title} — NO EVALUADO: fechas ilegibles (inicio {start}, fin {end})")
            continue
        problem = ""
        if start > end:
            problem = "inicio posterior al fin"
        elif prev_end is not None and end > prev_end:
            problem = "fuera de orden"
        if problem:
            broken = True
            print(f"  ❌ {title} — {start} → {end}: {problem}")
        else:
            print(f"  ✅ {title} — {start} → {end}")
        prev_end = end

    print()
    if broken:
        print("FALLA: la Experiencia NO está en cronología inversa estricta — reordenar antes de generar el PDF.")
        return 1
    if unevaluated:
        print("NO EVALUADO: hay entradas sin fechas legibles. Agregar sus fechas reales (no hay excepción manual).")
        return 2
    print("OK: cronología inversa correcta.")
    return 0


def demo() -> None:
    """ponytail self-check: un caso por cada estado y salida."""
    cases = {
        "ok_abreviado": ("## Experiencia Profesional\n\n### A\n**Remoto | Abr. 2026 – Presente**\n\n"
                         "### B\n**Remoto | Ene 2022 – Nov 2025**\n\n### C\n**CDMX | March 2015 – May 2017**\n", 0),
        "desorden": ("## Experiencia Profesional\n\n### B\n**Ago 2019 – Nov 2025**\n\n### A\n**Abril 2026 – Presente**\n", 1),
        "inicio_tras_fin": ("## Experiencia Laboral\n\n### A\n**Mayo 2020 – Enero 2019**\n", 1),
        "sin_fecha": ("## Experiencia Profesional\n\n### A\n**Abril 2026 – Presente**\n\n### Resumen previo\nVarios roles.\n", 2),
        "mes_inventado": ("## Experiencia Profesional\n\n### A\n**Foobar 2022 – Noviembre 2025**\n", 2),
        "parcial": ("## Experiencia Profesional\n\n### A\n**Abril 2026 – Presente**\n\n### B\n**Ene 2022 – Nov 2025**\n\n"
                    "### C\n**2015 – 2020**\n", 2),
        "seccion_vacia": ("## Experiencia Profesional\n\n## Educación\n", 2),
        "sin_entradas": ("## Experiencia Profesional\n\nTexto sin roles.\n\n## Educación\n", 2),
        "dos_secciones": ("## Experiencia Profesional\n\n### A\n**Ene 2022 – Nov 2025**\n\n## Otra\n\nx\n\n"
                          "## Experiencia Laboral\n\n### B\n**Ago 2023 – Dic 2025**\n", 1),
        "sin_seccion": ("## Resumen\n\nTexto.\n", 2),
        "en_con_proyecto": ("## Professional Experience\n\n### A\n**April 2026 - Present**\n\n### B\n**January 2022 - November 2025**\n\n"
                            "## Featured Projects\n\n### Artify\nSin fecha.\n", 0),
        "nota_ignorada": ("## Experiencia Profesional\n\n### A\n**Abril 2026 – Presente**\n\n---\n\n### Nota\nsin fecha\n", 0),
    }
    with tempfile.TemporaryDirectory() as tmp:
        for name, (md, expected) in cases.items():
            p = Path(tmp) / f"{name}.md"
            p.write_text("---\ntype: cv\n---\n\n" + md, encoding="utf-8")
            got = check(str(p))
            assert got == expected, f"{name}: esperaba {expected}, obtuve {got}"
    assert parse_date_token("Sept. 2024") == (2024, 9)
    assert parse_date_token("Presente") == PRESENTE
    assert parse_date_token("Foobar 2022") is None
    print("\ndemo OK")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--demo":
        demo()
        sys.exit(0)
    if len(sys.argv) != 2:
        print("Uso: check_chronological_order.py <cv.md>")
        sys.exit(2)
    sys.exit(check(sys.argv[1]))
