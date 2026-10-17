#!/usr/bin/env python3
"""Sello de revisión: liga el veredicto de la revisión previa al envío al CV exacto que se envía.

Etapas (ver docs/workflow.md, Fase 3):
  --preparar   Al terminar la revisión. Corre cronología y gaps sobre el Markdown,
               regenera el PDF desde ese Markdown y corre ATS (con --keywords, las
               requeridas/preferidas del tracking) sobre el PDF nuevo.
               Si los tres salen en 0, escribe en el tracking las huellas (Markdown,
               PDF y contenido de profile/) con veredicto "pendiente".
               No requiere sello previo.
  --aprobar    Después de tu aprobación explícita. Si alguna huella cambió desde
               --preparar, no aprueba (salida 1): hay que repetir.
  --check      Solo lectura, ANTES de subir o enviar el documento.
  --sin-documento  Para formularios sin CV: registra "no aplica".
  --registrar-envio  Al enviar: con el veredicto aprobado y la huella vigente, escribe
               cv_version (12 primeros hex de la huella del PDF), cv_sha256, pdf_sha256,
               cv_ruta, cv_base, cv_idioma y date_submitted (si estaba vacía). No usa
               git: cvs/, cvs-pdf/ y applications/ están ignorados y nunca se commitean;
               la identidad del documento es su huella SHA-256.

Salidas: 0 = OK; 1 = FALLA (check en 1/2, huella distinta, veredicto incorrecto);
         2 = NO EVALUADO (sin sello, campos faltantes, archivo, ruta o dependencia ilegible).

Solo agrega o reemplaza claves revision_*, cv_* y date_submitted del frontmatter del
tracking; no toca el cuerpo, last_updated, advanced ni ninguna otra clave.

El segundo par de ojos (prompts/cv-reviewer-prompt.md) corre en una sesión distinta de
la que escribió el CV, y la aprobación es tuya: este script solo hace verificable que
lo aprobado es lo que se envía.

`familia` e `idioma` del frontmatter del CV son opcionales: sin ellos, cv_base queda
"general" y cv_idioma "es". Si los declaras, idioma debe ser es o en.

Uso: review_stamp.py <slug> --preparar --keywords "a,b,c|archivo.txt" --validacion "<texto>" [--cv RUTA --pdf RUTA]
     review_stamp.py <slug> --aprobar | --check
     review_stamp.py <slug> --sin-documento --validacion "<texto>"
     review_stamp.py <slug> --registrar-envio
     review_stamp.py --demo
Opción de prueba: --root DIR (raíz alternativa del repo; por defecto, este repo).
"""
from __future__ import annotations

import datetime
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

from _config import load_config

SCRIPTS = Path(__file__).resolve().parent
REPO = SCRIPTS.parent
FIELDS_DOC = ("revision_veredicto", "revision_fecha", "revision_cv", "revision_pdf",
              "revision_md_sha256", "revision_pdf_sha256", "revision_perfil_sha256",
              "revision_checks", "revision_validacion")
DEFAULT_FAMILIA, DEFAULT_IDIOMA = "general", "es"
DEMO_KEYWORDS = "liderazgo,Acme"  # presentes en DEMO_CV
# huellas y rutas del sello de un CV: no aplican a un envío sin documento
SELLO_CV_VACIO = {k: "" for k in ("revision_cv", "revision_pdf", "revision_md_sha256",
                                  "revision_pdf_sha256", "revision_perfil_sha256")}
TRUNCADO = "quedaron fuera del PDF"  # aviso de generate_cv_pdf.py: un '---' se llevó secciones del CV


def kebab(s: str) -> str:
    """'Ada Lóvelace Ruiz' -> 'ada-lovelace-ruiz' (igual que docs/workflow.md, Fase 2)."""
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def profile_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted((root / "profile").glob("*.md")):
        h.update(p.name.encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


def read_frontmatter(path: Path) -> tuple[list[str], int, dict[str, str]] | None:
    """(líneas del archivo, índice del '---' de cierre, {clave: valor}) o None."""
    lines = path.read_text(encoding="utf-8").split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            fm = {}
            for line in lines[1:i]:
                if ":" in line and not line.startswith(" "):
                    k, v = line.split(":", 1)
                    fm[k.strip()] = v.strip()
            return lines, i, fm
    return None


def write_fields(path: Path, fields: dict[str, str]) -> None:
    lines, close, _ = read_frontmatter(path)
    for key, value in fields.items():
        value = " ".join(str(value).split())  # una sola línea
        idx = next((i for i in range(1, close) if lines[i].split(":", 1)[0].strip() == key), None)
        if idx is None:
            lines.insert(close, f"{key}: {value}")
            close += 1
        else:
            lines[idx] = f"{key}: {value}"
    path.write_text("\n".join(lines), encoding="utf-8")


def run(*args: str) -> int:
    """Corre un script con este intérprete; si falla, muestra la causa (stderr, o stdout si stderr está vacío)."""
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True)
    if not r.returncode and TRUNCADO in r.stderr:  # sale en 0 pero descartó contenido: no se sella
        aviso = next(l for l in r.stderr.splitlines() if TRUNCADO in l)
        print(f"  ↳ {Path(args[0]).name} (PDF truncado): {aviso.strip()}")
        return 1
    if r.returncode:
        lineas = [l for l in (r.stderr.strip() or r.stdout.strip()).splitlines() if l.strip()]
        if lineas:
            print(f"  ↳ {Path(args[0]).name} (salida {r.returncode}): {lineas[-1]}")
    return r.returncode


def validar_metadatos(cv_fields: dict, tracking_fields: dict) -> list[str]:
    """Problemas de metadata del CV a enviar. `familia` e `idioma` son opcionales; si están, `idioma`
    debe ser es o en, y ninguno puede chocar con `cv_base`/`cv_idioma` ya puestos en el tracking
    (vacíos, como en la plantilla, no cuentan)."""
    problemas = []
    for campo, destino in (("familia", "cv_base"), ("idioma", "cv_idioma")):
        valor = cv_fields.get(campo, "").strip()
        previo = tracking_fields.get(destino, "").strip()
        if not valor:
            continue
        if campo == "idioma" and valor not in ("es", "en"):
            problemas.append(f"`idioma` del CV debe ser es o en, no '{valor}'")
        elif previo and previo != valor:
            problemas.append(f"`{destino}` del tracking ({previo}) no coincide con `{campo}` del CV ({valor})")
    return problemas


def scripts_dir(root: Path) -> Path:
    """Los scripts del repo que se evalúa (en pruebas, una copia en la raíz temporal)."""
    return root / "scripts" if (root / "scripts").is_dir() else SCRIPTS


def preparar(root: Path, tracking: Path, cv: Path, pdf: Path, validacion: str, keywords: str) -> int:
    if not validacion.strip():
        print("NO EVALUADO: falta --validacion (resumen de tu validación de gaps resueltos y claims).")
        return 2
    if not keywords.strip():
        print("NO EVALUADO: falta --keywords (requeridas/preferidas del tracking, 'a,b,c' o un .txt); "
              "sin ellas el ATS no comprueba cobertura sobre el PDF que se sella.")
        return 2
    if read_frontmatter(tracking) is None or not cv.exists():
        print(f"NO EVALUADO: tracking sin frontmatter o CV inexistente ({tracking}, {cv}).")
        return 2
    problemas = validar_metadatos((read_frontmatter(cv) or (0, 0, {}))[2], read_frontmatter(tracking)[2])
    if problemas:
        print("NO EVALUADO: metadata del CV con problemas. Corregirla antes de sellar:")
        for p in problemas:
            print(f"  - {p}")
        return 2
    sd = scripts_dir(root)
    crono = run(str(sd / "check_chronological_order.py"), str(cv))
    gaps = run(str(sd / "check_gaps.py"), str(cv), str(root / "profile/skills.md"))
    if crono or gaps:
        print(f"FALLA: cronología={crono} gaps={gaps}. Corregir y volver a correr; no se escribió el sello.")
        return 1
    pdf.parent.mkdir(parents=True, exist_ok=True)
    if run(str(sd / "generate_cv_pdf.py"), str(cv), str(pdf)) != 0 or not pdf.exists():
        print(f"NO EVALUADO: no se pudo regenerar el PDF {pdf}.")
        return 2
    ats = run(str(sd / "ats_check.py"), str(pdf), keywords)
    if ats == 2:
        print("NO EVALUADO: ATS no pudo evaluar el PDF regenerado. No se escribió el sello.")
        return 2
    if ats:
        print(f"FALLA: ATS={ats} sobre el PDF regenerado. No se escribió el sello.")
        return 1
    write_fields(tracking, {
        "revision_documento": "cv",  # pisa un "no aplica" previo (sin documento -> con documento)
        "revision_veredicto": "pendiente",
        "revision_fecha": datetime.date.today().isoformat(),
        "revision_cv": str(cv.relative_to(root)) if cv.is_relative_to(root) else str(cv),
        "revision_pdf": str(pdf.relative_to(root)) if pdf.is_relative_to(root) else str(pdf),
        "revision_md_sha256": sha256_file(cv),
        "revision_pdf_sha256": sha256_file(pdf),
        "revision_perfil_sha256": profile_hash(root),
        "revision_checks": f"cronologia={crono} gaps={gaps} ats={ats}",
        "revision_validacion": validacion,
    })
    print(f"Preparado (pendiente de aprobación): {cv.name} + {pdf.name}")
    return 0


def current_matches(root: Path, fm: dict[str, str]) -> list[str]:
    """Lista de huellas que ya no coinciden (vacía si todo coincide)."""
    diffs = []
    for key, rel in (("revision_md_sha256", fm["revision_cv"]), ("revision_pdf_sha256", fm["revision_pdf"])):
        p = Path(rel) if Path(rel).is_absolute() else root / rel
        if not p.exists() or sha256_file(p) != fm[key]:
            diffs.append(rel)
    if profile_hash(root) != fm["revision_perfil_sha256"]:
        diffs.append("profile/")
    return diffs


def aprobar(root: Path, tracking: Path) -> int:
    parsed = read_frontmatter(tracking)
    if parsed is None or any(k not in parsed[2] for k in FIELDS_DOC):
        print("NO EVALUADO: no hay sello preparado completo; correr --preparar.")
        return 2
    fm = parsed[2]
    if fm["revision_veredicto"] != "pendiente":
        print(f"FALLA: el veredicto es '{fm['revision_veredicto']}', no 'pendiente'.")
        return 1
    diffs = current_matches(root, fm)
    if diffs:
        print(f"FALLA: cambió desde --preparar: {', '.join(diffs)}. Repetir checks y --preparar.")
        return 1
    write_fields(tracking, {"revision_veredicto": "aprobado",
                            "revision_aprobado_fecha": datetime.date.today().isoformat()})
    print("Aprobado.")
    return 0


def check(root: Path, tracking: Path) -> int:
    parsed = read_frontmatter(tracking) if tracking.exists() else None
    if parsed is None or "revision_veredicto" not in parsed[2]:
        print("NO EVALUADO: el tracking no tiene sello de revisión.")
        return 2
    fm = parsed[2]
    if fm.get("revision_documento") == "no aplica":
        if fm["revision_veredicto"] == "no aplica":
            print("OK: envío sin documento (no aplica).")
            return 0
        print("FALLA: registro sin documento incoherente.")
        return 1
    if any(k not in fm for k in FIELDS_DOC):
        print("NO EVALUADO: sello incompleto; correr --preparar.")
        return 2
    if fm["revision_veredicto"] != "aprobado":
        print(f"FALLA: el veredicto es '{fm['revision_veredicto']}'; falta --aprobar.")
        return 1
    diffs = current_matches(root, fm)
    if diffs:
        print(f"FALLA: cambió desde la aprobación: {', '.join(diffs)}. No enviar; volver a revisar.")
        return 1
    print(f"OK: {fm['revision_pdf']} es el documento aprobado.")
    return 0


def registrar_envio(root: Path, tracking: Path) -> int:
    if check(root, tracking) != 0:
        print("FALLA: sin sello aprobado vigente no se registra el envío.")
        return 1
    parsed = read_frontmatter(tracking)
    fm = parsed[2]
    hoy = datetime.date.today().isoformat()
    fecha = {} if fm.get("date_submitted", "").strip() else {"date_submitted": hoy}
    if fm.get("revision_documento") == "no aplica":
        # sin documento: la identidad de un CV anterior (ruta, huellas, familia, idioma) ya no aplica
        write_fields(tracking, {"cv_version": "no_aplica", "cv_ruta": "", "cv_sha256": "", "pdf_sha256": "",
                                "cv_base": "", "cv_idioma": "", **SELLO_CV_VACIO, **fecha})
        print("Registrado: envío sin documento (cv_version: no_aplica).")
        return 0
    cv_rel = fm["revision_cv"]
    cv_path = Path(cv_rel) if Path(cv_rel).is_absolute() else root / cv_rel
    cv_fm = read_frontmatter(cv_path)
    cv_fields = cv_fm[2] if cv_fm else {}
    problemas = validar_metadatos(cv_fields, fm)
    if problemas:
        print("FALLA: no se registra el envío con metadata en conflicto:")
        for p in problemas:
            print(f"  - {p}")
        return 1
    write_fields(tracking, {
        "cv_version": fm["revision_pdf_sha256"][:12],
        "cv_sha256": fm["revision_md_sha256"], "pdf_sha256": fm["revision_pdf_sha256"],
        "cv_ruta": fm["revision_pdf"],
        "cv_base": cv_fields.get("familia", "").strip() or DEFAULT_FAMILIA,
        "cv_idioma": cv_fields.get("idioma", "").strip() or DEFAULT_IDIOMA,
        **fecha})
    print(f"Registrado: {fm['revision_pdf']} (cv_version {fm['revision_pdf_sha256'][:12]})")
    return 0


def sin_documento(tracking: Path, validacion: str) -> int:
    if read_frontmatter(tracking) is None or not validacion.strip():
        print("NO EVALUADO: tracking sin frontmatter o falta --validacion.")
        return 2
    write_fields(tracking, {"revision_documento": "no aplica", "revision_veredicto": "no aplica",
                            "revision_fecha": datetime.date.today().isoformat(),
                            "revision_validacion": validacion, **SELLO_CV_VACIO})
    print("Registrado: envío sin documento.")
    return 0


def main(argv: list[str]) -> int:
    def opt(name: str) -> str | None:
        return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else None

    root = Path(opt("--root") or REPO).resolve()
    if not argv or argv[0].startswith("--"):
        print(__doc__)
        return 2
    slug = argv[0]
    tracking = root / f"applications/{slug}-application.md"
    if not tracking.exists():
        print(f"NO EVALUADO: no existe {tracking}.")
        return 2
    cv = Path(opt("--cv")) if opt("--cv") else root / f"cvs/cv_for_{slug}.md"
    pdf = Path(opt("--pdf")) if opt("--pdf") else \
        root / f"cvs-pdf/{kebab(load_config(root)['contact']['name'])}-{slug}.pdf"
    cv = cv if cv.is_absolute() else root / cv
    pdf = pdf if pdf.is_absolute() else root / pdf
    if "--preparar" in argv:
        return preparar(root, tracking, cv, pdf, opt("--validacion") or "", opt("--keywords") or "")
    if "--aprobar" in argv:
        return aprobar(root, tracking)
    if "--check" in argv:
        return check(root, tracking)
    if "--sin-documento" in argv:
        return sin_documento(tracking, opt("--validacion") or "")
    if "--registrar-envio" in argv:
        return registrar_envio(root, tracking)
    print(__doc__)
    return 2


# --- demo: todo con datos sintéticos, sobre una copia temporal del repo mínimo -----------------

DEMO_CONFIG = """contact:
  name: "Ada Lóvelace Ruiz"
  email: "ada@example.com"
  phone: "+52 5550001111"
  location: "Ciudad, País"
  linkedin: "https://www.linkedin.com/in/ada/"
  github: "https://github.com/ada"
tiers:
  - id: plataforma
    label: "Plataforma"
"""
DEMO_SKILLS = ("## Gaps confirmados — lo que NO dominas\n\n| Tecnología/Skill | Confirmado | Contexto |\n"
               "|---|---|---|\n| Kubernetes | 2026-01-10 | teórico |\n")
DEMO_CV = """---
type: cv
familia: plataforma
idioma: es
---

# Ada Lóvelace Ruiz

ada@example.com | +52 5550001111 | Ciudad, País

**Líder técnica · Ingeniera de plataforma**

## Resumen Profesional

Ingeniera con experiencia en plataformas internas, liderazgo de equipos distribuidos y entrega de software en producción con revisión y criterios de aceptación explícitos.

## Experiencia Laboral

### Líder técnica @ Acme
**Abril 2026 - Presente** | Remoto

- Dirijo un sistema en producción con especificación versionada y revisión por pares.

### Ingeniera @ Beta
**Enero 2022 - Noviembre 2025** | Ciudad

- Lideré un equipo de 12 personas con planeación trimestral y control de cambios.
"""


def demo_root(tmp: str) -> Path:
    """Repo mínimo: copia de scripts/, config, perfil con un gap, CV válido."""
    root = Path(tmp)
    shutil.copytree(SCRIPTS, root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    for d in ("profile", "cvs", "cvs-pdf", "applications"):
        (root / d).mkdir()
    (root / "config.yaml").write_text(DEMO_CONFIG, encoding="utf-8")
    (root / "profile/skills.md").write_text(DEMO_SKILLS, encoding="utf-8")
    (root / "profile/experience.md").write_text("perfil v1\n", encoding="utf-8")
    (root / "cvs/cv_for_demo.md").write_text(DEMO_CV, encoding="utf-8")
    return root


def new_tracking(root: Path, slug: str, extra: str = "") -> list[str]:
    (root / f"applications/{slug}-application.md").write_text(
        f"---\ntype: application_tracking\nstatus: draft\nadvanced: no\nlast_updated: 2026-10-01\n{extra}---\n\n# {slug}\n",
        encoding="utf-8")
    return [slug, "--root", str(root)]


def demo() -> None:
    """ponytail self-check: recorrido completo del sello, sin git, con archivos que git ignoraría."""
    assert kebab("Ada Lóvelace  Ruiz") == "ada-lovelace-ruiz"
    with tempfile.TemporaryDirectory() as tmp:
        root = demo_root(tmp)
        cv = root / "cvs/cv_for_demo.md"
        tr = root / "applications/demo-application.md"
        r = new_tracking(root, "demo")
        original_fm = tr.read_text(encoding="utf-8")
        pdf = root / "cvs-pdf/ada-lovelace-ruiz-demo.pdf"  # nombre desde contact.name

        assert main(r + ["--check"]) == 2, "sin sello"
        assert main(r + ["--preparar"]) == 2, "sin --validacion"
        assert main(r + ["--preparar", "--keywords", DEMO_KEYWORDS, "--validacion", "ok", "--cv", "cvs/no_existe.md"]) == 2, "ruta inexistente"
        bad = root / "cvs/cv_for_bad.md"
        bad.write_text(DEMO_CV.replace("Abril 2026 - Presente", "2026"), encoding="utf-8")
        assert main(r + ["--preparar", "--keywords", DEMO_KEYWORDS, "--validacion", "ok", "--cv", str(bad)]) == 1, "check en 2 impide preparar"
        assert "revision_" not in tr.read_text(encoding="utf-8"), "no debe escribir si falla"
        gap = root / "cvs/cv_for_gap.md"
        gap.write_text(DEMO_CV.replace("revisión por pares", "revisión por pares sobre Kubernetes"), encoding="utf-8")
        assert main(r + ["--preparar", "--keywords", DEMO_KEYWORDS, "--validacion", "ok", "--cv", str(gap)]) == 1, "gap colado impide preparar"

        assert main(r + ["--preparar", "--validacion", "ok"]) == 2, "sin --keywords"
        assert main(r + ["--preparar", "--keywords", "liderazgo,Kotlin", "--validacion", "ok"]) == 1, "keyword ausente en el PDF"
        assert "revision_" not in tr.read_text(encoding="utf-8"), "ATS sin cobertura: no debe sellar"
        assert main(r + ["--preparar", "--keywords", DEMO_KEYWORDS, "--validacion", "sin gaps; claims revisados"]) == 0, "primer sello"
        assert pdf.exists(), "el PDF lleva el nombre de contact.name en kebab-case"
        assert main(r + ["--check"]) == 1, "pendiente no pasa check"
        cv.write_text(DEMO_CV + "\n- Bullet agregado después de preparar.\n", encoding="utf-8")
        assert main(r + ["--aprobar"]) == 1, "Markdown cambiado entre preparar y aprobar"
        cv.write_text(DEMO_CV, encoding="utf-8")
        assert main(r + ["--preparar", "--keywords", DEMO_KEYWORDS, "--validacion", "ok"]) == 0
        assert main(r + ["--aprobar"]) == 0
        before = tr.read_text(encoding="utf-8")
        assert main(r + ["--check"]) == 0
        assert tr.read_text(encoding="utf-8") == before, "--check no debe escribir"
        resto = [l for l in before.split("\n") if not l.startswith("revision_")]
        assert "\n".join(resto) == original_fm.rstrip("\n") or "\n".join(resto) == original_fm, \
            "el resto del tracking debe quedar idéntico"

        good_pdf = pdf.read_bytes()
        pdf.write_bytes(good_pdf + b"\n%cambio")
        assert main(r + ["--check"]) == 1, "PDF cambiado después de aprobar"
        pdf.write_bytes(good_pdf)
        (root / "profile/experience.md").write_text("perfil v2\n", encoding="utf-8")
        assert main(r + ["--check"]) == 1, "perfil modificado"
        (root / "profile/experience.md").write_text("perfil v1\n", encoding="utf-8")
        (root / "profile/nuevo.md").write_text("x\n", encoding="utf-8")
        assert main(r + ["--check"]) == 1, "perfil con archivo agregado"
        (root / "profile/nuevo.md").unlink()
        assert main(r + ["--check"]) == 0

        # registrar envío: sin git, con huellas; defaults solo si el CV no declara familia/idioma
        assert main(r + ["--registrar-envio"]) == 0
        fm = read_frontmatter(tr)[2]
        assert fm["cv_version"] == fm["revision_pdf_sha256"][:12] and fm["pdf_sha256"] == fm["revision_pdf_sha256"]
        assert fm["cv_sha256"] == fm["revision_md_sha256"] and fm["cv_base"] == "plataforma" and fm["cv_idioma"] == "es"
        assert fm["date_submitted"] == datetime.date.today().isoformat()

        # dos CVs distintos -> dos versiones distinguibles
        cv2 = root / "cvs/cv_for_demo2.md"
        cv2.write_text(DEMO_CV.replace("12 personas", "doce personas"), encoding="utf-8")
        r2 = new_tracking(root, "demo2")
        assert main(r2 + ["--preparar", "--keywords", DEMO_KEYWORDS, "--validacion", "ok"]) == 0 and main(r2 + ["--aprobar"]) == 0
        assert main(r2 + ["--registrar-envio"]) == 0
        assert read_frontmatter(root / "applications/demo2-application.md")[2]["cv_version"] != fm["cv_version"], \
            "dos PDFs distintos deben dar cv_version distintas"

        # familia/idioma opcionales: defaults; inválidos o en conflicto: no se sella ni se escribe
        sin = root / "cvs/cv_for_sin.md"
        sin.write_text(DEMO_CV.replace("familia: plataforma\n", "").replace("idioma: es\n", ""), encoding="utf-8")
        rs = new_tracking(root, "sin")
        assert main(rs + ["--preparar", "--keywords", DEMO_KEYWORDS, "--validacion", "ok"]) == 0 and main(rs + ["--aprobar"]) == 0
        assert main(rs + ["--registrar-envio"]) == 0
        fs = read_frontmatter(root / "applications/sin-application.md")[2]
        assert fs["cv_base"] == DEFAULT_FAMILIA and fs["cv_idioma"] == DEFAULT_IDIOMA, "defaults"
        (root / "cvs/cv_for_fr.md").write_text(DEMO_CV.replace("idioma: es", "idioma: fr"), encoding="utf-8")
        rf = new_tracking(root, "fr")
        antes = (root / "applications/fr-application.md").read_text(encoding="utf-8")
        assert main(rf + ["--preparar", "--keywords", DEMO_KEYWORDS, "--validacion", "ok"]) == 2, "idioma inválido"
        (root / "cvs/cv_for_conf.md").write_text(DEMO_CV, encoding="utf-8")
        rc = new_tracking(root, "conf", "cv_base: otra\n")
        assert main(rc + ["--preparar", "--keywords", DEMO_KEYWORDS, "--validacion", "ok"]) == 2, "conflicto de familia"
        assert (root / "applications/fr-application.md").read_text(encoding="utf-8") == antes, "no debe escribir"
        (root / "cvs/cv_for_en.md").write_text(DEMO_CV.replace("idioma: es", "idioma: en"), encoding="utf-8")
        re_ = new_tracking(root, "en")
        assert main(re_ + ["--preparar", "--keywords", DEMO_KEYWORDS, "--validacion", "ok"]) == 0 and main(re_ + ["--aprobar"]) == 0
        assert main(re_ + ["--registrar-envio"]) == 0
        assert read_frontmatter(root / "applications/en-application.md")[2]["cv_idioma"] == "en"

        # sello incompleto, sin documento y de sin documento a documento
        (root / "applications/inc-application.md").write_text(
            "---\ntype: application_tracking\nrevision_veredicto: aprobado\n---\n", encoding="utf-8")
        assert main(["inc", "--root", str(root), "--check"]) == 2, "sello incompleto"
        rsd = new_tracking(root, "sd")
        assert main(rsd + ["--sin-documento", "--validacion", "formulario sin CV"]) == 0
        assert main(rsd + ["--check"]) == 0 and main(rsd + ["--registrar-envio"]) == 0, "sin documento"
        assert read_frontmatter(root / "applications/sd-application.md")[2]["cv_version"] == "no_aplica"
        assert main(rsd + ["--preparar", "--keywords", DEMO_KEYWORDS, "--validacion", "ok", "--cv", "cvs/cv_for_demo.md",
                           "--pdf", "cvs-pdf/sd.pdf"]) == 0
        assert main(rsd + ["--aprobar"]) == 0 and main(rsd + ["--check"]) == 0, "de sin documento a documento"

        faltante_demo(root)
        wrapper_demo(root)
    print("\ndemo OK")


def faltante_demo(root: Path) -> None:
    """Sin pypdf o reportlab: salida 2 (no evaluado) con diagnóstico, sin traceback, y sin sello."""
    for script, modulo in (("ats_check.py", "pypdf"), ("generate_cv_pdf.py", "reportlab")):
        r = subprocess.run([sys.executable, "-c",
                            f"import sys, runpy; sys.path.insert(0, r'{root / 'scripts'}'); "
                            f"sys.modules['{modulo}'] = None; sys.argv = ['x']; "
                            f"runpy.run_path(r'{root / 'scripts' / script}', run_name='__main__')"],
                           capture_output=True, text=True)
        assert r.returncode == 2 and f"falta {modulo}" in r.stderr and "Traceback" not in r.stderr, \
            f"módulo ausente: {script} -> {r.returncode} {r.stderr[-200:]}"


def wrapper_demo(root: Path) -> None:
    """run() muestra la causa por stdout o stderr y conserva el código; ATS 2 no sella, ATS 1 sigue en 1."""
    import contextlib
    import io

    def capturar(*args: str) -> tuple[int, str]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            return run(*args), buf.getvalue()

    code, out = capturar(str(root / "scripts/ats_check.py"), str(root / "no_existe.pdf"), "")
    assert code != 0 and out.strip(), "fallo controlado o error: causa visible"
    boom = root / "boom.py"
    boom.write_text('raise RuntimeError("boom")\n', encoding="utf-8")
    code, out = capturar(str(boom))
    assert code == 1 and "RuntimeError: boom" in out, "error por stderr: causa visible"

    r = new_tracking(root, "ats")
    tr = root / "applications/ats-application.md"
    (root / "cvs/cv_for_ats.md").write_text(DEMO_CV, encoding="utf-8")
    real = run
    try:
        for ats, esperado in ((2, 2), (1, 1)):
            globals()["run"] = lambda *a, ats=ats: ats if a[0].endswith("ats_check.py") else real(*a)
            assert main(r + ["--preparar", "--keywords", DEMO_KEYWORDS, "--validacion", "ok"]) == esperado, f"ATS {ats} -> {esperado}"
            assert "revision_" not in tr.read_text(encoding="utf-8"), f"ATS {ats}: no debe sellar"
    finally:
        globals()["run"] = real


if __name__ == "__main__":
    if sys.argv[1:] == ["--demo"]:
        demo()
        sys.exit(0)
    sys.exit(main(sys.argv[1:]))
