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


def main() -> int:
    files = tracked_files()
    assert "templates/cv-template.md" in files, "el template del CV no llega al fork"
    assert not any(f.startswith(("profile/", "applications/", "cvs/")) for f in files), \
        f"datos personales versionados: {[f for f in files if f.startswith(('profile/', 'cvs/'))]}"

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
        for script in ("scripts/followup_check.py", "scripts/conversion_report.py"):
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

    print(f"smoke test ok — {len(files)} archivos, flujo completo del README")
    return 0


if __name__ == "__main__":
    sys.exit(main())
