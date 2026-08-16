#!/usr/bin/env python3
"""Follow-up checker: lee el frontmatter de applications/*-application.md y reporta
qué aplicaciones necesitan seguimiento, cuáles solo pueden esperar, y cuáles
siguen sin auditar (campo `follow_up` ausente o `unconfirmed`).

No decide por sí mismo si una aplicación tiene contacto humano o no — esa
clasificación la hace el usuario/tu asistente al triar la aplicación y queda
escrita en el campo `follow_up` del frontmatter. Este script solo lee y avisa.
"""
import re
import sys
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
APPLICATIONS_DIR = REPO_ROOT / "applications"

WAITING_WINDOW_DAYS = 15  # ponytail: ventana "normal" antes de sugerir reclasificar; ajustar si la evidencia real difiere


def parse_frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    fields = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def label(app: dict) -> str:
    """Un tracking file a medio llenar no debe tirar el reporte completo."""
    return f"{app.get('company', '(sin empresa)')} ({app.get('position', 'sin puesto')})"


def load_applications() -> list[dict]:
    # glob amplio a propósito: "*-application.md" no calza con nombres irregulares
    # (ej. una reaplicación guardada como "empresa-application-v2.md" se quedaría
    # fuera en silencio). El filtro por `type` de abajo ya descarta el template.
    apps = []
    for path in sorted(APPLICATIONS_DIR.glob("*.md")):
        fields = parse_frontmatter(path.read_text())
        if fields.get("type") != "application_tracking":
            continue
        apps.append(fields)
    return apps


def days_since(date_str: str, today: date):
    try:
        submitted = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None
    return (today - submitted).days


def resolve_anchor_date(app: dict) -> str:
    """"waiting" usa last_updated: ya refleja el último evento real (entrevista,
    prueba técnica), mientras que date_submitted se queda fijo en el envío original.
    Los demás estados usan date_submitted, con date_started como respaldo si
    nunca se volvió aplicación formal (ej. un CV enviado "como referencia", sin
    postulación formal de por medio)."""
    if app.get("follow_up") == "waiting":
        return app.get("last_updated") or app.get("date_submitted") or ""
    return app.get("date_submitted") or app.get("date_started") or ""


def report(today: date = None) -> int:
    today = today or date.today()
    apps = load_applications()

    action_needed, unconfirmed, reclassify = [], [], []

    for app in apps:
        follow_up = app.get("follow_up")
        if not follow_up or follow_up == "n/a":
            continue

        days = days_since(resolve_anchor_date(app), today)

        if follow_up == "pending_contact":
            action_needed.append((app, days))
        elif follow_up == "unconfirmed":
            unconfirmed.append((app, days))
        elif follow_up == "waiting" and days is not None and days > WAITING_WINDOW_DAYS:
            reclassify.append((app, days))

    if action_needed:
        print("Seguimiento pendiente — tienes contacto, actúa:")
        for app, days in sorted(action_needed, key=lambda x: -(x[1] or 0)):
            contact = app.get("follow_up_contact", "(sin contacto registrado)")
            print(f"  - {label(app)} — {days} días — {contact}")
        print()

    if reclassify:
        print(f"Pasaron {WAITING_WINDOW_DAYS}+ días en 'Esperando respuesta' — revisar y reclasificar:")
        for app, days in sorted(reclassify, key=lambda x: -(x[1] or 0)):
            print(f"  - {label(app)} — {days} días")
        print()

    if unconfirmed:
        print("Sin auditar (follow_up: unconfirmed):")
        for app, days in unconfirmed:
            print(f"  - {label(app)} — {days} días")
        print()

    if not (action_needed or reclassify or unconfirmed):
        print("Sin pendientes de seguimiento.")

    return 0


def demo() -> None:
    """ponytail self-check: valida el parseo de frontmatter y la clasificación por días."""
    sample = """---
type: application_tracking
company: Test Co
position: Test Role
status: submitted
follow_up: pending_contact
follow_up_contact: test@example.com
date_submitted: 2026-07-01
---
body
"""
    fields = parse_frontmatter(sample)
    assert fields["company"] == "Test Co"
    assert fields["follow_up"] == "pending_contact"
    assert fields["follow_up_contact"] == "test@example.com"

    assert days_since("2026-07-01", date(2026, 8, 15)) == 45
    assert days_since("not-a-date", date(2026, 8, 15)) is None

    # "waiting" ancla en last_updated (momentum reciente), no en date_submitted viejo
    interviewing = {"follow_up": "waiting", "date_submitted": "2026-07-01", "last_updated": "2026-08-10"}
    assert resolve_anchor_date(interviewing) == "2026-08-10"

    # sin date_submitted (nunca se volvió formal) cae a date_started
    reference_only = {"follow_up": "pending_contact", "date_submitted": "", "date_started": "2026-07-11"}
    assert resolve_anchor_date(reference_only) == "2026-07-11"

    # un tracking a medio llenar se reporta, no tira el reporte entero
    assert label({}) == "(sin empresa) (sin puesto)"
    assert label(fields) == "Test Co (Test Role)"

    print("demo ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--demo":
        demo()
        sys.exit(0)
    sys.exit(report())
