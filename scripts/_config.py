"""Carga config.yaml (tus datos reales). Usa config.example.yaml de respaldo
solo para que los scripts no truenen antes de que configures lo tuyo — con el
placeholder no vas a pasar ningún check real (es la idea: config.yaml sin
llenar no debe poder aprobar un CV por accidente)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def require_modules(*names: str) -> None:
    """Sale con 2 (no evaluado) y un diagnóstico si falta una dependencia, sin traceback.
    Llamar antes de importar los módulos opcionales (pypdf, reportlab)."""
    missing = [n for n in names if importlib.util.find_spec(n) is None]
    if missing:
        print(f"NO EVALUADO: falta {', '.join(missing)} — pip install -r requirements.txt",
              file=sys.stderr)
        sys.exit(2)


def load_config(root: Path | None = None) -> dict:
    """`root` solo lo usan las pruebas (un repo temporal); por defecto, este repo."""
    require_modules("yaml")
    import yaml

    base = root or REPO_ROOT
    path = base / "config.yaml"
    if not path.exists():
        path = base / "config.example.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))
