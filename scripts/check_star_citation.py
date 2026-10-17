#!/usr/bin/env python3
"""STAR citation checker: detecta secciones STAR en applications/*-application.md que
probablemente reformulan una historia ya canonizada en profile/star-stories.md
sin citarla (convención: línea `*(Fuente: star-stories.md — "...")*` bajo el encabezado).

Heurística por palabras clave del título — informativo (salida siempre 0), no exige
interacción. Si un tracking tiene sección STAR pero sin bloques "### STAR #n:"
(por ejemplo, bullets), reporta "formato no evaluado" en vez de dar las citas por buenas.
Puede haber falsos negativos (títulos muy distintos para la misma historia) y falsos
positivos ocasionales (palabra genérica compartida); el valor está en señalar
candidatos, no en veredictos exactos.

Uso: check_star_citation.py [tracking.md]   (sin argumento: todos los trackings)
     check_star_citation.py --demo
"""
from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STAR_SOURCE = REPO_ROOT / "profile" / "star-stories.md"
APPLICATIONS_DIR = REPO_ROOT / "applications"
CITATION_MARKER = "star-stories.md"
MIN_KEYWORD_LEN = 5
DISTINCTIVE_LEN = 6  # una sola palabra de este largo ya alcanza para marcar match
# palabras genéricas de negocio: aunque sean largas, no son distintivas de una
# historia en particular y generaban falsos positivos
GENERIC_WORDS = {"producto", "productos", "equipo", "equipos", "proceso", "procesos", "cliente", "clientes"}


def title_keywords(title: str) -> set[str]:
    words = re.findall(r"[a-záéíóúñ]+", title.lower())
    return {w for w in words if len(w) >= MIN_KEYWORD_LEN and w not in GENERIC_WORDS}


def canonical_keyword_sets(text: str) -> dict[str, set[str]]:
    titles = re.findall(r"^## (.+)$", text, re.MULTILINE)
    return {t: title_keywords(t) for t in titles}


def is_probable_match(title_kw: set[str], canon_kw: set[str]) -> bool:
    overlap = title_kw & canon_kw
    if any(len(w) >= DISTINCTIVE_LEN for w in overlap):
        return True
    return len(overlap) >= 2


def has_star_section(text: str) -> bool:
    return re.search(r"^## .*STAR", text, re.MULTILINE | re.IGNORECASE) is not None


def check_file(path: Path, canon: dict[str, set[str]]) -> list[str]:
    text = path.read_text(encoding="utf-8")
    if has_star_section(text) and not re.search(r"^### STAR #\d+:", text, re.MULTILINE):
        return ["  formato no evaluado: hay sección STAR pero sin bloques '### STAR #n:' (por ejemplo, bullets)"]
    blocks = re.split(r"(?=^### STAR #\d+:)", text, flags=re.MULTILINE)
    warnings = []
    for block in blocks:
        m = re.match(r"^### STAR #\d+: (.+)$", block, re.MULTILINE)
        if not m:
            continue
        title = m.group(1).strip()
        if CITATION_MARKER in block[:400]:
            continue
        title_kw = title_keywords(title)
        for canon_title, canon_kw in canon.items():
            if is_probable_match(title_kw, canon_kw):
                warnings.append(f'  "{title}" se parece a "{canon_title}" pero no la cita')
                break
    return warnings


def report(only: Path | None = None, source: Path = STAR_SOURCE, applications: Path = APPLICATIONS_DIR) -> int:
    try:
        canon = canonical_keyword_sets(source.read_text(encoding="utf-8"))
    except OSError as e:
        print(f"NO EVALUADO: no se pudo leer {source.name} ({e}); es informativo, salida 0.")
        return 0
    total_files = 0
    total_warnings = 0
    paths = [only] if only else sorted(applications.glob("*-application.md"))
    for path in paths:
        warnings = check_file(path, canon)
        if warnings:
            total_files += 1
            total_warnings += len(warnings)
            print(f"{path.name}:")
            for w in warnings:
                print(w)
    if total_warnings:
        print(f"\n{total_warnings} aviso(s) en {total_files} archivo(s) (historias sin citar o formato no evaluado).")
    else:
        print("Todas las historias STAR que coinciden con star-stories.md están citadas.")
    return 0


def demo() -> None:
    """ponytail self-check: valida la heurística de match y la detección de cita. Datos sintéticos."""
    canon = canonical_keyword_sets(
        "# Historias\n\n## Migración de la base de datos sin downtime\n\n## Incidente de facturación en producción\n")
    migration_kw = title_keywords("Migración de base de datos en producción")
    assert any(is_probable_match(migration_kw, kw) for t, kw in canon.items() if "Migración" in t), \
        "una variante conocida de la historia de migración no matcheó"

    unrelated_kw = title_keywords("Adopción de un framework de pruebas")
    assert not any(is_probable_match(unrelated_kw, kw) for kw in canon.values()), \
        "falso positivo: un título no relacionado matcheó una historia canónica"

    with tempfile.TemporaryDirectory() as tmp:
        sin_cita = Path(tmp) / "a-application.md"
        sin_cita.write_text("## STAR Stories Preparadas\n\n### STAR #1: Migración de base de datos en producción\nTexto.\n",
                            encoding="utf-8")
        assert check_file(sin_cita, canon) and "no la cita" in check_file(sin_cita, canon)[0]
        citada = Path(tmp) / "d-application.md"
        citada.write_text('## STAR Stories Preparadas\n\n### STAR #1: Migración de base de datos en producción\n'
                          '*(Fuente: star-stories.md — "Migración de la base de datos sin downtime")*\n', encoding="utf-8")
        assert check_file(citada, canon) == []
        bullets = Path(tmp) / "b-application.md"
        bullets.write_text("## STAR Stories Preparadas\n\n- Incidente de facturación.\n", encoding="utf-8")
        assert "formato no evaluado" in check_file(bullets, canon)[0]
        sin_star = Path(tmp) / "c-application.md"
        sin_star.write_text("## Notas\n\nNada.\n", encoding="utf-8")
        assert check_file(sin_star, canon) == []
        src = Path(tmp) / "star-stories.md"
        src.write_text("## Migración de la base de datos sin downtime\n", encoding="utf-8")
        assert report(sin_cita, source=src) == 0, "es informativo: salida siempre 0"
        assert report(source=Path(tmp) / "no_existe.md") == 0, "fuente ausente: informativo, salida 0"

    print("demo ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--demo":
        demo()
        sys.exit(0)
    if len(sys.argv) == 2:
        sys.exit(report(Path(sys.argv[1])))
    sys.exit(report())
