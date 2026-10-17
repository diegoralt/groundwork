#!/usr/bin/env python3
"""Prueba de integración: simula un fork limpio y corre el Quickstart del README.

Los `--demo` de cada script son unitarios y no ven los fallos de integración —
un CV truncado, un template que no existe, una ruta que cambió. Esto copia solo
los archivos versionados a un tmpdir (exactamente lo que recibe quien haga fork),
sigue el README al pie de la letra y verifica el resultado.

Uso: smoke_test.py
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# ponytail: si el PDF pierde secciones (bug del '---' como regla horizontal), estas
# faltan y el assert truena. Son las que el template siempre trae, en mayúsculas
# porque generate_cv_pdf.py convierte los '## '.
EXPECTED_SECTIONS = ["RESUMEN PROFESIONAL", "EXPERIENCIA LABORAL", "COMPETENCIAS CLAVE",
                     "EDUCACIÓN", "IDIOMAS"]


def tracked_files() -> list[str]:
    """Lo que un `git clone` entrega: versionados + no ignorados por .gitignore."""
    out = set()
    for args in (["ls-files"], ["ls-files", "--others", "--exclude-standard"]):
        r = subprocess.run(["git", "-C", str(REPO_ROOT), *args],
                           capture_output=True, text=True, check=True)
        out.update(line for line in r.stdout.splitlines() if line)
    return sorted(out)


def run(fork: Path, *cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *cmd], cwd=fork, capture_output=True, text=True)


def sello_y_checks(fork: Path) -> None:
    """Checks obligatorios y sello de revisión en un fork con la config de OTRO usuario
    (nombre con acentos y espacios, tier propio), sin ningún commit de datos."""
    sys.path.insert(0, str(fork / "scripts"))
    import review_stamp as rs  # copia del fork, no la del repo

    (fork / "config.yaml").write_text(rs.DEMO_CONFIG, encoding="utf-8")
    pdf_name = "ada-lovelace-ruiz"  # kebab de "Ada Lóvelace Ruiz"
    cv = fork / "cvs/cv_for_acme-tech-lead.md"
    cv.write_text(rs.DEMO_CV, encoding="utf-8")

    # gaps: tabla vacía del template público -> 0 (no es "no evaluado")
    r = run(fork, "scripts/check_gaps.py", str(cv))
    assert r.returncode == 0 and "Sin gaps confirmados" in r.stdout, f"tabla de gaps vacía debe ser OK:\n{r.stdout}"
    # sección ausente o archivo ilegible -> 2; fila sintética que aparece en el CV -> 1
    skills = fork / "profile/skills.md"
    original = skills.read_text(encoding="utf-8")
    skills.write_text("## Hard Skills\n- Python\n", encoding="utf-8")
    assert run(fork, "scripts/check_gaps.py", str(cv)).returncode == 2, "sin la sección de gaps: NO EVALUADO"
    skills.write_text(original + "\n| Lideré | 2026-01-01 | sintético |\n", encoding="utf-8")
    assert run(fork, "scripts/check_gaps.py", str(cv)).returncode == 1, "un gap presente en el CV debe fallar"
    skills.write_text(original, encoding="utf-8")
    assert run(fork, "scripts/check_gaps.py", str(cv), "profile/no_existe.md").returncode == 2

    # cronología: el template sin llenar no puede aprobar
    r = run(fork, "scripts/check_chronological_order.py", "templates/cv-template.md")
    assert r.returncode == 2, "el template con [Mes Año] sin llenar debe ser NO EVALUADO"
    assert run(fork, "scripts/check_chronological_order.py", str(cv)).returncode == 0

    # sello: recorrido completo desde la plantilla pública del tracking
    tracking = (fork / "templates/application-tracking-template.md").read_text(encoding="utf-8")
    slug = "acme-tech-lead"
    for old, new in [("[Empresa]", "Acme"), ("[Título del Rol]", "Líder técnica")]:
        tracking = tracking.replace(old, new)
    (fork / f"applications/{slug}-application.md").write_text(tracking, encoding="utf-8")
    stamp = ["scripts/review_stamp.py", slug]
    r = run(fork, *stamp, "--preparar", "--validacion", "smoke: sin gaps, claims sintéticos")
    assert r.returncode == 0, f"--preparar falló:\n{r.stdout}{r.stderr}"
    pdf = fork / f"cvs-pdf/{pdf_name}-{slug}.pdf"
    assert pdf.exists(), "el PDF debe llevar contact.name en kebab-case, sin acentos"
    assert run(fork, *stamp, "--check").returncode == 1, "pendiente no pasa --check"
    assert run(fork, *stamp, "--aprobar").returncode == 0
    assert run(fork, *stamp, "--check").returncode == 0
    r = run(fork, *stamp, "--registrar-envio")
    assert r.returncode == 0, f"--registrar-envio falló:\n{r.stdout}"
    fm = rs.read_frontmatter(fork / f"applications/{slug}-application.md")[2]
    assert fm["cv_version"] == fm["revision_pdf_sha256"][:12] and fm["cv_base"] == "plataforma", fm
    assert fm["date_submitted"], "el registro del envío fija date_submitted si estaba vacía"
    # invalidación: editar el CV, el PDF o el perfil después de aprobar
    cv.write_text(rs.DEMO_CV + "\n- Bullet agregado después de aprobar.\n", encoding="utf-8")
    assert run(fork, *stamp, "--check").returncode == 1, "editar el CV invalida el sello"
    cv.write_text(rs.DEMO_CV, encoding="utf-8")
    assert run(fork, *stamp, "--check").returncode == 0
    experiencia = fork / "profile/experience.md"
    original_exp = experiencia.read_text(encoding="utf-8")
    experiencia.write_text("otro perfil\n", encoding="utf-8")
    assert run(fork, *stamp, "--check").returncode == 1, "editar el perfil invalida el sello"
    experiencia.write_text(original_exp, encoding="utf-8")
    # envío sin documento
    (fork / "applications/formulario-application.md").write_text(tracking, encoding="utf-8")
    sd = ["scripts/review_stamp.py", "formulario"]
    assert run(fork, *sd, "--sin-documento", "--validacion", "formulario sin CV").returncode == 0
    assert run(fork, *sd, "--registrar-envio").returncode == 0
    assert run(fork, *sd, "--check").returncode == 0

    # lo sellado nunca se commitea: git debe ignorar todo lo que el sello escribe o lee
    for rel in ("cvs/cv_for_x.md", "cvs-pdf/x.pdf", "applications/x-application.md", "config.yaml"):
        r = subprocess.run(["git", "-C", str(REPO_ROOT), "check-ignore", "-q", rel])
        assert r.returncode == 0, f"{rel} no está ignorado: el sello podría publicar datos"


def medicion_y_agenda(fork: Path) -> None:
    """Esquema único de tracking de punta a punta: la plantilla pública y el sello producen lo que
    leen followup_check, conversion_report y pipeline_board, con la config de OTRO usuario
    (tier propio, nombre con acentos, cohort_start que YAML lee como fecha)."""
    import datetime
    import review_stamp as rs

    hoy = datetime.date.today()
    corte = hoy + datetime.timedelta(days=20)
    (fork / "config.yaml").write_text(rs.DEMO_CONFIG + "cohort_start: 2026-09-01\n", encoding="utf-8")
    apps = fork / "applications"
    plantilla = (fork / "templates/application-tracking-template.md").read_text(encoding="utf-8")

    def nuevo(slug: str, empresa: str, **campos) -> Path:
        path = apps / f"{slug}-application.md"
        path.write_text(plantilla.replace("[Empresa]", empresa).replace("[Título del Rol]", "Rol"), encoding="utf-8")
        rs.write_fields(path, {"status": "submitted", "follow_up": "waiting", "tier": "plataforma",
                               "advanced": "no", **campos})
        return path

    def lineas(salida: str, nombre: str) -> list[str]:
        return [l for l in salida.splitlines() if nombre in l]

    seguimiento = lambda dia: run(fork, "scripts/followup_check.py", "--hoy", dia).stdout

    # identidad: el sello llena cv_version y date_submitted; solo faltan los campos que llena el usuario
    sal = seguimiento(corte.isoformat())
    assert "faltan: canal, fit, parseo, minutos_preparacion" in sal and "cv_version" not in sal, sal
    assert "dato_invalido" not in sal and "fecha inválida" not in sal, "la plantilla no deja fechas inválidas"

    # dos versiones de CV distinguibles, a partir de la misma plantilla y el mismo sello
    otro = nuevo("acme-otro", "Acme")
    cv2 = fork / "cvs/cv_for_acme-otro.md"
    cv2.write_text(rs.DEMO_CV + "\n- Bullet distinto.\n", encoding="utf-8")
    stamp2 = ["scripts/review_stamp.py", "acme-otro"]
    assert run(fork, *stamp2, "--preparar", "--validacion", "smoke: segunda versión").returncode == 0
    assert run(fork, *stamp2, "--aprobar").returncode == 0
    assert run(fork, *stamp2, "--registrar-envio").returncode == 0
    v1 = rs.read_frontmatter(apps / "acme-tech-lead-application.md")[2]["cv_version"]
    v2 = rs.read_frontmatter(otro)[2]["cv_version"]
    sd = rs.read_frontmatter(apps / "formulario-application.md")[2]["cv_version"]
    assert len({v1, v2}) == 2 and sd == "no_aplica", (v1, v2, sd)

    # frontera de datos_medicion: el día de cohort_start entra, el anterior no
    nuevo("antes", "FronteraAntes", date_submitted="2026-08-31", contacto_empresa_ultimo="2026-10-25", next_date="2026-11-30")
    nuevo("dia", "FronteraDia", date_submitted="2026-09-01", contacto_empresa_ultimo="2026-10-25", next_date="2026-11-30")
    sal = seguimiento("2026-10-30")
    assert lineas(sal, "FronteraDia (Rol) — faltan:") and not lineas(sal, "FronteraAntes (Rol) — faltan:"), sal

    # pausa: con motivo suprime sin_fecha y silencio; sin motivo no; una fecha comprometida sigue en la agenda
    nuevo("pausa-con", "PausaCon", date_submitted="2026-10-08", pausa_motivo="proceso congelado", pausa_hasta="2026-11-10")
    nuevo("pausa-sin", "PausaSin", date_submitted="2026-10-08", pausa_hasta="2026-11-10")
    nuevo("pausa-fecha", "PausaFecha", date_submitted="2026-10-08", pausa_motivo="x", pausa_hasta="2026-11-10",
          next_date="2026-10-31", next_action="Entrevista")
    sal = seguimiento("2026-10-30")
    assert not [l for l in lineas(sal, "PausaCon") if "sin próxima fecha" in l or "sin contacto" in l], sal
    sin = " ".join(lineas(sal, "PausaSin"))
    assert "sin próxima fecha" in sin and "sin contacto de la empresa" in sin, sal
    assert lineas(sal, "2026-10-31 · PausaFecha"), "la pausa no apaga la fecha comprometida"

    # respuesta humana documentada: cuenta en la ventana de 14 días; desglose por versión de CV
    rs.write_fields(apps / "acme-tech-lead-application.md", {
        "status": "submitted", "follow_up": "waiting", "tier": "plataforma", "advanced": "yes",
        "respuesta_humana": "si", "respuesta_humana_fecha": (hoy + datetime.timedelta(days=3)).isoformat(),
        "respuesta_humana_precision": "exacta", "respuesta_humana_evidencia": "correo del reclutador"})
    r = run(fork, "scripts/conversion_report.py", "--desde", hoy.isoformat(),
            "--hasta", (hoy + datetime.timedelta(days=1)).isoformat(), "--corte", corte.isoformat())
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Resultado: 1/3 = 33.3%" in r.stdout, r.stdout
    assert "Plataforma: 1/" in r.stdout and "avanzaron: Acme" in r.stdout, "las categorías salen de config.yaml"
    por_version = lineas(r.stdout, "Por cv_version:")[0]
    assert v1 in por_version and v2 in por_version and "no_aplica" in por_version, por_version

    # tablero: el enlace al PDF lleva el contact.name del config
    rs.write_fields(apps / "acme-tech-lead-application.md", {"next_date": ""})
    r = run(fork, "scripts/pipeline_board.py")
    assert r.returncode == 0, r.stderr
    tablero = (apps / "pipeline.html").read_text(encoding="utf-8")
    assert 'href="../cvs-pdf/ada-lovelace-ruiz-acme-tech-lead.pdf"' in tablero, "el enlace al PDF no usa contact.name"
    assert 'data-tier="plataforma"' in tablero and "datos por completar" in tablero


def main() -> int:
    files = tracked_files()
    assert "templates/cv-template.md" in files, "el template del CV no llega al fork"
    assert not any(f.startswith(("profile/", "applications/", "cvs/")) for f in files), \
        f"datos personales versionados: {[f for f in files if f.startswith(('profile/', 'cvs/'))]}"

    # la integración de Claude Code funciona sin instalar nada: ya está en la raíz
    for f in ("CLAUDE.md", ".claude/agents/cv-reviewer.md", ".claude/commands/bootstrap.md",
              ".claude/commands/mock-interview.md", ".claude/commands/review-application.md"):
        assert f in files, f"{f} no llega al fork — la ruta Claude Code no funcionaría sola"
    assert not any(f.startswith("claude-code/") for f in files), \
        "quedó la carpeta de staging: la integración ya no se copia a mano"
    # ESTADO.md son notas de desarrollo de groundwork, no del usuario que hace fork
    assert ".claude/ESTADO.md" not in files, "ESTADO.md está versionado y viaja en cada fork"

    with tempfile.TemporaryDirectory() as tmp:
        fork = Path(tmp) / "fork"
        for f in files:
            dst = fork / f
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO_ROOT / f, dst)

        # Quickstart del README, literal
        shutil.copy2(fork / "config.example.yaml", fork / "config.yaml")
        shutil.copytree(fork / "templates/profile", fork / "profile")
        for d in ("applications", "cvs", "cvs-pdf"):
            (fork / d).mkdir()

        # Fase 2: CV desde el template -> PDF
        shutil.copy2(fork / "templates/cv-template.md", fork / "cvs/cv_for_demo.md")
        r = run(fork, "scripts/generate_cv_pdf.py", "cvs/cv_for_demo.md", "cvs-pdf/demo.pdf")
        assert r.returncode == 0, f"generate_cv_pdf falló:\n{r.stderr}"
        assert r.stderr == "", f"el template dispara la alerta de truncado:\n{r.stderr}"

        from pypdf import PdfReader
        text = PdfReader(str(fork / "cvs-pdf/demo.pdf")).pages[0].extract_text()
        for section in EXPECTED_SECTIONS:
            assert section in text, f"'{section}' no llegó al PDF — ¿se truncó el CV?"
        assert "Gaps confirmados" not in text, "las notas internas se colaron al PDF"

        # Fase 3: los checks previos al envío
        r = run(fork, "scripts/ats_check.py", "cvs-pdf/demo.pdf", "Liderazgo,Arquitectura")
        assert "2/2 encontradas" in r.stdout, f"ATS no encontró las keywords:\n{r.stdout}"
        assert r.returncode == 1, "config.example.yaml sin llenar no debe aprobar un CV"
        assert "glifo no representable" not in r.stdout, f"el template rompe glifos:\n{r.stdout}"

        r = run(fork, "scripts/check_em_dash_style.py", "cvs/cv_for_demo.md")
        assert r.returncode == 0, f"el check de estilo nunca debe bloquear:\n{r.stderr}"

        # Fase 4: tracking, con applications/ vacío y con una aplicación real
        for script in ("scripts/followup_check.py", "scripts/conversion_report.py", "scripts/pipeline_board.py"):
            r = run(fork, script)
            assert r.returncode == 0, f"{script} truena con applications/ vacío:\n{r.stderr}"

        tracking = (fork / "templates/application-tracking-template.md").read_text()
        for old, new in [("[Empresa]", "Acme"), ("[Título del Rol]", "Tech Lead")]:
            tracking = tracking.replace(old, new)
        for key, value in [("status", "submitted"), ("tier", "liderazgo"), ("advanced", "yes"),
                           ("follow_up", "pending_contact"), ("date_submitted", "2026-07-01")]:
            tracking = "\n".join(
                f"{key}: {value}" if line.startswith(f"{key}:") else line
                for line in tracking.splitlines())
        (fork / "applications/acme-application.md").write_text(tracking)

        r = run(fork, "scripts/followup_check.py")
        assert "Acme (Tech Lead)" in r.stdout, f"la aplicación no se reportó:\n{r.stdout}"
        r = run(fork, "scripts/conversion_report.py")
        assert "1/1 = 100%" in r.stdout, f"conversión mal calculada:\n{r.stdout}"

        r = run(fork, "scripts/pipeline_board.py")
        assert r.returncode == 0, f"pipeline_board.py truena con applications/ real:\n{r.stderr}"
        board = (fork / "applications/pipeline.html").read_text()
        assert "Acme" in board, "el tablero no incluyó la aplicación real"
        assert 'data-col="mia"' in board, "pending_contact sin next_date debería ser jugada propia"

        sello_y_checks(fork)
        medicion_y_agenda(fork)

    print(f"smoke test ok — {len(files)} archivos, flujo completo del README")
    return 0


if __name__ == "__main__":
    sys.exit(main())
