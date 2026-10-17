#!/usr/bin/env python3
"""Verifica que un CV no reclame ningún término de la sección de gaps de profile/skills.md.

Salidas (convención de los checks obligatorios, ver docs/workflow.md):
  0 = OK: sin coincidencias (o sin gaps confirmados todavía), o todas resueltas
      con un marcador válido.
  1 = FALLA: coincidencia sin resolver, o marcador inválido, caducado,
      ambiguo, malformado o duplicado.
  2 = NO EVALUADO: CV o skills.md ilegible, o skills.md sin la sección
      "## Gaps confirmados" con su tabla.

Solo se revisa el cuerpo que llega al PDF (sin frontmatter ni notas internas
tras el primer '---' del cuerpo, igual que generate_cv_pdf.py); las líneas se
reportan con su número en el Markdown original.

Una tabla de gaps vacía es válida (0): significa "aún no confirmé ninguno", no que
no se evaluó. Si la sección falta o el archivo no se puede leer, es 2.

Resolución por aparición, en la nota interna del CV (una línea por resolución):
  gap_resuelto: <término> | <hash> | falso positivo|encuadre admitido | <justificación>
<hash> = 12 primeros hex del sha256 de "<encabezado ##/### más cercano>\\n<línea>"
(ambos sin espacios en los extremos); el script lo imprime para cada coincidencia.
Cambiar la línea o copiarla a otra sección invalida la resolución. Un marcador
cubre todas las menciones del término en esa línea. "encuadre admitido" solo
vale si la fila del término dice "Encuadres admisibles" en su contexto.
El script no juzga el contenido: la revisión previa al envío exige validar a mano
cada gap_resuelto contra tu perfil antes de aprobar.

Uso: check_gaps.py <cv.md> [skills.md]
     check_gaps.py --demo
"""
from __future__ import annotations

import hashlib
import re
import sys
import tempfile
from pathlib import Path

DEFAULT_GAPS = Path(__file__).resolve().parents[1] / "profile/skills.md"
SECTION_TITLE = "## Gaps confirmados"
HEADER_CELLS = ("Término", "Tecnología/Skill")
MOTIVOS = ("falso positivo", "encuadre admitido")


def split_body_notes(md: str) -> tuple[int, list[str], str]:
    """(línea inicial del cuerpo, líneas del cuerpo, texto de las notas internas)."""
    lines = md.split("\n")
    start = 0
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                start = i + 1
                break
    for i in range(start, len(lines)):
        if re.fullmatch(r"---\s*", lines[i]):
            return start, lines[start:i], "\n".join(lines[i + 1:])
    return start, lines[start:], ""


def load_gap_rows(skills_md: str) -> dict[str, str] | None:
    """{término: fila completa} de la tabla bajo SECTION_TITLE; {} si la tabla está
    vacía; None si la sección no existe."""
    m = re.search(r"^" + re.escape(SECTION_TITLE) + r".*$", skills_md, re.MULTILINE)
    if not m:
        return None
    rest = skills_md[m.end():]
    nxt = re.search(r"^## ", rest, re.MULTILINE)
    section = rest[: nxt.start()] if nxt else rest
    rows = {}
    for line in section.splitlines():
        cell = re.match(r"\|\s*([^|]+?)\s*\|", line)
        if not cell or cell.group(1).strip() in HEADER_CELLS or set(cell.group(1).strip()) <= {"-", ":"}:
            continue
        rows[cell.group(1).strip()] = line
    return rows


def line_hash(heading: str, line: str) -> str:
    return hashlib.sha256(f"{heading.strip()}\n{line.strip()}".encode("utf-8")).hexdigest()[:12]


def parse_markers(notes: str) -> tuple[list[tuple[str, str, str]], list[str]]:
    """([(término, hash, motivo)], [errores de formato])."""
    markers, errors = [], []
    for raw in notes.splitlines():
        if not raw.strip().lower().startswith("gap_resuelto:"):
            continue
        parts = [p.strip() for p in raw.split(":", 1)[1].split("|", 3)]
        if len(parts) != 4 or not all(parts):
            errors.append(f"malformado: {raw.strip()}")
            continue
        term, h, motivo, _ = parts
        if not re.fullmatch(r"[0-9a-f]{12}", h) or motivo.lower() not in MOTIVOS:
            errors.append(f"malformado (hash o motivo): {raw.strip()}")
            continue
        markers.append((term, h, motivo.lower()))
    return markers, errors


def check(cv_path: str, gaps_path: str) -> int:
    try:
        md = Path(cv_path).read_text(encoding="utf-8")
        skills_md = Path(gaps_path).read_text(encoding="utf-8")
    except OSError as e:
        print(f"NO EVALUADO: no se pudo leer un archivo ({e}).")
        return 2
    rows = load_gap_rows(skills_md)
    if rows is None:
        print(f"NO EVALUADO: {Path(gaps_path).name} no tiene la sección '{SECTION_TITLE}' con su tabla.")
        return 2

    start, body, notes = split_body_notes(md)
    hits = []  # (término, número de línea original, línea, hash)
    heading = ""
    seen = {}
    for offset, line in enumerate(body):
        if re.match(r"#{2,3} ", line):
            heading = line
        for term in rows:
            if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", line, re.IGNORECASE):
                h = line_hash(heading, line)
                hits.append((term, start + offset + 1, line.strip(), h))
                seen.setdefault((term, h), []).append(start + offset + 1)

    markers, errors = parse_markers(notes)
    fail = bool(errors)
    for e in errors:
        print(f"❌ marcador {e}")
    keys = [(t.lower(), h) for t, h, _ in markers]
    for k in {k for k in keys if keys.count(k) > 1}:
        print(f"❌ marcador duplicado: {k[0]} | {k[1]}")
        fail = True
    hit_keys = {(t.lower(), h) for t, _, _, h in hits}
    for term, h, motivo in markers:
        if (term.lower(), h) not in hit_keys:
            print(f"❌ marcador caducado (la línea cambió o ya no existe): {term} | {h}")
            fail = True
        elif motivo == "encuadre admitido":
            row = next((r for t, r in rows.items() if t.lower() == term.lower()), "")
            if "encuadres admisibles" not in row.lower():
                print(f"❌ marcador inválido: '{term}' no tiene encuadres admisibles en {Path(gaps_path).name} (solo cabe eliminarlo del CV)")
                fail = True

    valid = {(t.lower(), h) for t, h, m in markers}
    if not rows:
        print(f"Sin gaps confirmados en {Path(gaps_path).name}: nada que contrastar todavía.")
    elif not hits:
        print(f"Sin coincidencias contra los {len(rows)} términos de {Path(gaps_path).name}.")
    for term, line_no, line, h in hits:
        if len(seen[(term, h)]) > 1:
            print(f"❌ línea {line_no}: «{term}» ambigua (líneas idénticas en la misma sección {seen[(term, h)]}) — {line[:100]}")
            fail = True
        elif (term.lower(), h) in valid:
            print(f"✅ línea {line_no}: «{term}» resuelta ({h}) — {line[:100]}")
        else:
            print(f"❌ línea {line_no}: «{term}» SIN RESOLVER — hash {h} — {line[:100]}")
            fail = True

    if fail:
        print("\nFALLA: eliminar el gap del CV o, si es falso positivo o encuadre admitido, agregar en la nota interna:")
        print("  gap_resuelto: <término> | <hash> | falso positivo|encuadre admitido | <justificación>")
        print("Cada gap_resuelto se valida a mano contra tu perfil antes de aprobar.")
        return 1
    print("OK" + (" (con resoluciones; validarlas a mano)" if hits else ""))
    return 0


def demo() -> None:
    """ponytail self-check: un caso por cada estado y salida. Datos sintéticos."""
    skills_md = """# Competencias

## Hard Skills
- **Python**: 7/10

## Gaps confirmados — lo que NO dominas

| Tecnología/Skill | Confirmado | Contexto |
|---|---|---|
| Kubernetes | 2026-01-10 | conocimiento teórico |
| Rust | 2026-01-12 | Encuadres admisibles: "dirigí un sistema en Rust generado por un asistente" |

**Por qué existe:** evita reclamar dos veces lo que no dominas.
"""
    rust_line = "- Dirigí un servicio con Rust generado por un asistente."
    rust_h = line_hash("### Proyecto", rust_line)
    k_line = "AWS (ECS, S3), Kubernetes, Docker"
    k_h = line_hash("## Cloud", k_line)
    head = "---\ntype: cv\n---\n"
    cases = {
        "limpio": (head + "## Cloud\nAWS (ECS, S3), Docker\n---\n**Kubernetes** — gap, no incluido.\n", 0),
        "gap_colado": (head + f"## Cloud\n{k_line}\n", 1),
        "rust_admitido": (head + f"### Proyecto\n{rust_line}\n---\ngap_resuelto: Rust | {rust_h} | encuadre admitido | dirigido, generado por un asistente\n", 0),
        "kubernetes_admitido": (head + f"## Cloud\n{k_line}\n---\ngap_resuelto: Kubernetes | {k_h} | encuadre admitido | x\n", 1),
        "claim_agregado": (head + f"### Proyecto\n{rust_line} También implementé Rust.\n---\n"
                           f"gap_resuelto: Rust | {rust_h} | encuadre admitido | x\n", 1),
        "copiada_a_otra_seccion": (head + f"### Proyecto\n{rust_line}\n### Otro\n{rust_line}\n---\n"
                                   f"gap_resuelto: Rust | {rust_h} | encuadre admitido | x\n", 1),
        "duplicada_misma_seccion": (head + f"### Proyecto\n{rust_line}\n{rust_line}\n---\n"
                                    f"gap_resuelto: Rust | {rust_h} | encuadre admitido | x\n", 1),
        "marcador_duplicado": (head + f"### Proyecto\n{rust_line}\n---\ngap_resuelto: Rust | {rust_h} | encuadre admitido | x\n"
                               f"gap_resuelto: Rust | {rust_h} | encuadre admitido | y\n", 1),
        "marcador_malformado": (head + "## Cloud\nAWS\n---\ngap_resuelto: Rust | zz | quizá\n", 1),
    }
    with tempfile.TemporaryDirectory() as tmp:
        gp = Path(tmp) / "skills.md"
        gp.write_text(skills_md, encoding="utf-8")
        for name, (md, expected) in cases.items():
            p = Path(tmp) / f"{name}.md"
            p.write_text(md, encoding="utf-8")
            print(f"\n--- {name}")
            got = check(str(p), str(gp))
            assert got == expected, f"{name}: esperaba {expected}, obtuve {got}"
        x = Path(tmp) / "x.md"
        x.write_text(head + "## Cloud\nKubernetes\n", encoding="utf-8")
        # tabla válida pero vacía: 0, no "no evaluado"
        vacio = Path(tmp) / "vacio.md"
        vacio.write_text("## Gaps confirmados — x\n\n| Tecnología/Skill | Confirmado | Contexto |\n|---|---|---|\n", encoding="utf-8")
        assert check(str(x), str(vacio)) == 0, "tabla vacía debe ser OK (sin gaps confirmados)"
        # sección ausente o archivo ilegible: 2
        sin = Path(tmp) / "sin_seccion.md"
        sin.write_text("## Hard Skills\n- Python\n", encoding="utf-8")
        assert check(str(x), str(sin)) == 2, "fuente sin la sección debe ser NO EVALUADO"
        assert check(str(Path(tmp) / "no_existe.md"), str(gp)) == 2
        assert check(str(x), str(Path(tmp) / "no_existe.md")) == 2
    assert list(load_gap_rows(skills_md)) == ["Kubernetes", "Rust"]
    assert load_gap_rows("## Hard Skills\n") is None
    print("\ndemo OK")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--demo":
        demo()
        sys.exit(0)
    if len(sys.argv) not in (2, 3):
        print("Uso: check_gaps.py <cv.md> [skills.md]")
        sys.exit(2)
    gaps_arg = sys.argv[2] if len(sys.argv) == 3 else str(DEFAULT_GAPS)
    sys.exit(check(sys.argv[1], gaps_arg))
