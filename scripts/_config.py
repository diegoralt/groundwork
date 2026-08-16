"""Carga config.yaml (tus datos reales). Usa config.example.yaml de respaldo
solo para que los scripts no truenen antes de que configures lo tuyo — con el
placeholder no vas a pasar ningún check real (es la idea: config.yaml sin
llenar no debe poder aprobar un CV por accidente)."""
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_config() -> dict:
    path = REPO_ROOT / "config.yaml"
    if not path.exists():
        path = REPO_ROOT / "config.example.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))
