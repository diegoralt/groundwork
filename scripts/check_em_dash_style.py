#!/usr/bin/env python3
"""Clasifica cada raya (—) de un CV fuente en estructural vs. prosa narrativa.

Estructural = convención de formato ya validada (etiqueta de skill en negrita
seguida de raya, o encabezado "Empresa — Puesto"): no se reporta como hallazgo.
Prosa = conector narrativo (el patrón que de verdad delata redacción de IA),
incluida una segunda raya que aparezca DESPUÉS de una etiqueta estructural en
la misma línea (ej. una aclaración de rol pegada tras la lista de skills).

Nunca bloquea (exit code siempre 0) — es informativo, corre desatendido dentro
de /review-application sin frenar el flujo ni pedir interacción.

Uso: check_em_dash_style.py <cv.md>
     check_em_dash_style.py --demo
"""
import re
import sys
from pathlib import Path

SKILL_LABEL = re.compile(r"^\*\*[^*]+\*\*\s*—")  # **Label** — contenido
HEADER = re.compile(r"^#{2,3}\s.*—")             # ### Empresa — Puesto


def _strip_frontmatter_and_notes(md: str) -> str:
    """Quita el frontmatter YAML y las notas internas tras el '---' final.

    Copia deliberada de la misma función en generate_cv_pdf.py: este script
    no debe depender de ese módulo (evita cargar reportlab solo para esto).
    """
    if md.startswith("---"):
        md = md.split("---", 2)[2]
    parts = re.split(r"^---\s*$", md, flags=re.MULTILINE)
    return parts[0]


def classify_lines(md: str) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    """Devuelve (estructurales, prosa) como listas de (num_linea, texto_linea).

    Clasifica por raya, no por línea: una línea con etiqueta estructural que
    además trae una raya adicional después (ej. aclaración de rol pegada a un
    "Label — ..." de skills) cuenta esa raya extra como prosa, aunque la línea
    también aparezca en estructurales por su primera raya.
    """
    structural, prose = [], []
    for i, line in enumerate(_strip_frontmatter_and_notes(md).splitlines(), start=1):
        dashes = [m.start() for m in re.finditer("—", line)]
        if not dashes:
            continue

        if HEADER.match(line):
            structural.append((i, line.strip()))
            continue

        label_match = SKILL_LABEL.match(line)
        if label_match:
            structural.append((i, line.strip()))
            if len(dashes) > 1:  # rayas extra tras la etiqueta = prosa real
                prose.append((i, line.strip()))
            continue

        prose.append((i, line.strip()))
    return structural, prose


def report(md_path: str) -> int:
    md = Path(md_path).read_text(encoding="utf-8")
    structural, prose = classify_lines(md)
    total_lines = len(structural) + len(prose)
    total_dashes = sum(
        line.count("—") for _, line in {**dict(structural), **dict(prose)}.items()
    )

    print(f"Líneas con raya: {total_lines}  |  rayas totales: {total_dashes}  |  "
          f"estructural: {len(structural)}  |  prosa: {len(prose)}")
    if not prose:
        print("Sin conectores de prosa — nada que revisar.")
        return 0

    print("\nConectores de prosa (candidatos a variar coma/punto/dos puntos/paréntesis):")
    for i, line in prose:
        print(f"  L{i}: {line}")
    return 0  # informativo: nunca bloquea el flujo de /review-application


def demo() -> None:
    md = (
        "---\ntype: cv\n---\n\n"
        "**Mobile** — Android, Kotlin\n"
        "### Acme Corp — Engineer Lead\n"
        "**Plataformas Web** — React, TypeScript — como arquitecto, no codificador\n"
        "- Hice el trabajo — el resultado fue bueno\n"
        "\n---\n\n**Nota**: interna — no debe contarse\n"
    )
    structural, prose = classify_lines(md)
    assert len(structural) == 3, structural  # Mobile, encabezado de empresa, Plataformas Web (1a raya)
    assert len(prose) == 2, prose  # la 2a raya de Plataformas Web + la línea de "Hice el trabajo"
    assert any("como arquitecto" in line for _, line in prose), \
        "la raya extra tras una etiqueta estructural debe surgir como prosa"
    assert not any("interna" in line for _, line in structural + prose), \
        "las notas internas no deben contarse"
    print("demo ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--demo":
        demo()
        sys.exit(0)
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(report(sys.argv[1]))
