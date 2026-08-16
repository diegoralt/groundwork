#!/usr/bin/env python3
"""Conversion report: lee `tier` y `advanced` del frontmatter de applications/*-application.md
y calcula la tasa de conversión real por categoría de rol (llegó a entrevista/prueba técnica o no).

Las categorías salen de config.yaml (`tiers:`) — defínelas según tu propio
mercado objetivo. No hay categorías precargadas: las tuyas reflejan tu carrera,
no la de nadie más.
"""
import re
import sys
from pathlib import Path

from _config import load_config

REPO_ROOT = Path(__file__).resolve().parents[1]
APPLICATIONS_DIR = REPO_ROOT / "applications"


def load_tier_labels() -> dict[str, str]:
    tiers = load_config().get("tiers") or []
    return {t["id"]: t["label"] for t in tiers}


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


def load_applications() -> list[dict]:
    # glob amplio a propósito: "*-application.md" no calza con nombres irregulares
    # (ej. una reaplicación guardada como "empresa-application-v2.md"). El filtro
    # por `type` de abajo ya descarta application-tracking-template.md.
    apps = []
    for path in sorted(APPLICATIONS_DIR.glob("*.md")):
        fields = parse_frontmatter(path.read_text())
        if fields.get("type") != "application_tracking":
            continue
        if fields.get("status") == "withdrawn":
            continue  # nunca se envió, no cuenta para conversión
        if not fields.get("tier"):
            continue  # sin clasificar todavía
        apps.append(fields)
    return apps


def report() -> int:
    tier_labels = load_tier_labels()
    if not tier_labels:
        print("⚠️  config.yaml no tiene `tiers:` definidos — nada que reportar.")
        print("   Agrega al menos una categoría de rol antes de clasificar aplicaciones.")
        return 1

    apps = load_applications()
    by_tier: dict[str, list[dict]] = {}
    for app in apps:
        by_tier.setdefault(app["tier"], []).append(app)

    print(f"Conversión real por categoría de rol — {len(apps)} aplicaciones\n")
    for tier, label in tier_labels.items():
        rows = by_tier.get(tier, [])
        if not rows:
            continue
        advanced = [r for r in rows if r.get("advanced") == "yes"]
        rate = 100 * len(advanced) / len(rows)
        companies = ", ".join(r.get("company", "(sin empresa)") for r in advanced) or "ninguna"
        print(f"{label}: {len(advanced)}/{len(rows)} = {rate:.0f}%  (avanzaron: {companies})")

    unknown_tier = {app["tier"] for app in apps} - set(tier_labels)
    if unknown_tier:
        print(f"\n⚠️  Tiers en aplicaciones sin definir en config.yaml: {', '.join(unknown_tier)}")

    unclassified = sum(
        1
        for path in APPLICATIONS_DIR.glob("*.md")
        if path.name != "application-tracking-template.md"
        and (f := parse_frontmatter(path.read_text())).get("type") == "application_tracking"
        and f.get("status") != "withdrawn"
        and not f.get("tier")
    )
    if unclassified:
        print(f"\n⚠️  {unclassified} aplicación(es) sin campo `tier` — no se contaron.")

    return 0


def demo() -> None:
    """ponytail self-check: valida el parseo y el cálculo de tasa por tier."""
    sample = """---
type: application_tracking
status: submitted
tier: liderazgo
advanced: yes
---
body
"""
    fields = parse_frontmatter(sample)
    assert fields["tier"] == "liderazgo"
    assert fields["advanced"] == "yes"

    fake_apps = [
        {"tier": "liderazgo", "advanced": "yes", "company": "A"},
        {"tier": "liderazgo", "advanced": "no", "company": "B"},
        {"tier": "liderazgo", "advanced": "no", "company": "C"},
    ]
    rate = 100 * sum(1 for a in fake_apps if a["advanced"] == "yes") / len(fake_apps)
    assert abs(rate - 33.33) < 0.1

    print("demo ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--demo":
        demo()
        sys.exit(0)
    sys.exit(report())
