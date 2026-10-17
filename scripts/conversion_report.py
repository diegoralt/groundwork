#!/usr/bin/env python3
"""Conversion report: lee `tier` y `advanced` del frontmatter de applications/*-application.md
y calcula la tasa de conversión real por categoría de rol (llegó a entrevista/prueba técnica o no).

Las categorías salen de config.yaml (`tiers:`) — defínelas según tu propio
mercado objetivo. No hay categorías precargadas: las tuyas reflejan tu carrera,
no la de nadie más.

Segunda sección: respuesta humana en 14 días como "mínimo documentado", con su propio
cargador (incluye retiradas después del envío y trackings sin tier). Fórmula:
  - universo: date_submitted válido dentro de [--desde, --hasta);
  - madura: --corte - date_submitted >= 14 (días naturales); inmaduras aparte;
  - éxito: respuesta_humana=si con fecha válida en [envío, envío+14], precisión (exacta o a_mas_tardar)
    y evidencia; sin ellas es dato inválido, no éxito;
  - ambigua: solo suma en la sensibilidad, y solo con fecha en la misma ventana;
  - fecha humana anterior al envío o valor no reconocido: dato inválido, no éxito;
  - canal, fit, parseo, precisión, cierre_causa_origen y cv_idioma solo admiten los valores de
    templates/application-tracking-template.md (vacío = desconocido); otro valor (comillas,
    comentario, typo) queda visible como dato inválido y se agrupa como "inválido".
Para reproducir un mismo universo: --desde <inicio> --hasta <fin> --corte <fecha fija>.

Uso: conversion_report.py [--corte AAAA-MM-DD] [--desde AAAA-MM-DD] [--hasta AAAA-MM-DD]
     conversion_report.py --demo
"""
from __future__ import annotations

import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _config import load_config  # noqa: E402

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
    # (ej. una reaplicación guardada como "empresa-application-v2.md").
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


MATURITY_DAYS = 14
DIMENSIONS = ("canal", "tier", "fit", "cv_base", "cv_version", "parseo")
RESPUESTAS = {"si", "no", "ambigua", ""}
CLOSED = {"rejected", "closed_no_feedback"}


def parse_date(value: str | None) -> date | None:
    """Solo AAAA-MM-DD exacto; un valor con '#', comillas o texto extra es inválido."""
    if not value or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def load_all_trackings(apps_dir: Path = APPLICATIONS_DIR) -> list[dict]:
    """Cargador de la métrica de respuesta: todos los trackings, con o sin tier."""
    apps = []
    for path in sorted(apps_dir.glob("*.md")):
        fields = parse_frontmatter(path.read_text())
        if fields.get("type") != "application_tracking":
            continue
        fields["_file"] = path.name
        apps.append(fields)
    return apps


VALORES_VALIDOS = {  # templates/application-tracking-template.md, "Campos de medición"
    "respuesta_humana_precision": {"exacta", "a_mas_tardar"},
    "canal": {"calido", "directo_frio", "portal"},
    "fit": {"compatible", "excepcion", "desconocido"},
    "parseo": {"ok", "corregido", "fallo", "no_evaluado", "no_aplica"},
    "cierre_causa_origen": {"declarada", "inferida", "desconocida"},
    "cv_idioma": {"es", "en"},
}


def validar_campos(a: dict) -> list[str]:
    """Campos de medición con un valor fuera de su lista (vacío = desconocido, no es inválido)."""
    return [f"{k}='{v}' no es un valor válido" for k, ok in VALORES_VALIDOS.items()
            if (v := (a.get(k) or "").strip()) and v not in ok]


def response_metric(apps: list[dict], corte: date, desde: date | None = None, hasta: date | None = None) -> dict:
    m = {"universo": [], "inmaduras": [], "maduras": [], "exitos": [], "ambiguas_en_ventana": [],
         "ambiguas": [], "sin_dato": [], "invalidos": [], "sin_fecha_envio": [], "tardias": []}
    for a in apps:
        name = a.get("company", a.get("_file", "?"))
        sub = parse_date(a.get("date_submitted"))
        if sub is None:
            if a.get("date_submitted"):
                m["invalidos"].append((name, "date_submitted no es AAAA-MM-DD"))
            elif a.get("status") not in ("withdrawn", "in_progress", "draft"):
                m["sin_fecha_envio"].append(name)
            continue
        if (desde and sub < desde) or (hasta and sub >= hasta):
            continue
        m["universo"].append(a)
        for why in validar_campos(a):
            m["invalidos"].append((name, why))
        if (corte - sub).days < MATURITY_DAYS:
            m["inmaduras"].append(a)
            continue
        m["maduras"].append(a)
        rh = (a.get("respuesta_humana") or "").strip()
        raw = a.get("respuesta_humana_fecha")
        rf = parse_date(raw)
        if rh not in RESPUESTAS:
            m["invalidos"].append((name, f"respuesta_humana='{rh}'"))
            continue
        if rh == "":
            m["sin_dato"].append(a)
            continue
        if rh in ("si", "ambigua") and (rf is None or rf < sub):
            m["invalidos"].append((name, "fecha de respuesta ausente, inválida o anterior al envío"))
            if rh == "ambigua":
                m["ambiguas"].append(a)
            continue
        falta = [k for k in ("respuesta_humana_precision", "respuesta_humana_evidencia")
                 if rh in ("si", "ambigua") and not (a.get(k) or "").strip()]
        if rh in ("si", "ambigua") and not falta and \
                (a.get("respuesta_humana_precision") or "").strip() not in VALORES_VALIDOS["respuesta_humana_precision"]:
            falta = ["respuesta_humana_precision válida"]
        if falta:
            m["invalidos"].append((name, f"respuesta_humana={rh} sin " + ", ".join(falta)))
            if rh == "ambigua":
                m["ambiguas"].append(a)
            continue
        in_window = rf is not None and 0 <= (rf - sub).days <= MATURITY_DAYS
        if rh == "si":
            (m["exitos"] if in_window else m["tardias"]).append(a)
        elif rh == "ambigua":
            m["ambiguas"].append(a)
            if in_window:
                m["ambiguas_en_ventana"].append(a)
    return m


def _pct(n: int, d: int) -> str:
    return f"{n}/{d} = {100 * n / d:.1f}%" if d else f"{n}/0 (sin datos)"


def print_response(apps: list[dict], corte: date, desde: date | None, hasta: date | None) -> None:
    m = response_metric(apps, corte, desde, hasta)
    mad, exi = m["maduras"], m["exitos"]
    rango = f"envíos en [{desde or 'inicio'}, {hasta or 'hoy'})"
    print(f"\nRespuesta humana en {MATURITY_DAYS} días (mínimo documentado) — corte {corte}, {rango}\n")
    print(f"  Resultado: {_pct(len(exi), len(mad))}")
    sens = len(exi) + len(m["ambiguas_en_ventana"])
    print(f"  Sensibilidad (si las ambiguas con fecha en ventana fueran humanas): {_pct(sens, len(mad))}")
    con_dato = len(mad) - len(m["sin_dato"])
    print(f"  Cobertura: {con_dato}/{len(mad)} maduras con respuesta_humana registrada")
    print(f"  Inmaduras (fuera de N): {len(m['inmaduras'])} · respuestas humanas después del día 14: {len(m['tardias'])}")
    if m["sin_dato"]:
        print("  Maduras sin dato: " + ", ".join(a.get("company", "?") for a in m["sin_dato"]))
    if m["ambiguas"]:
        print("  Ambiguas: " + ", ".join(a.get("company", "?") for a in m["ambiguas"]))
    if m["sin_fecha_envio"]:
        print("  Sin fecha de envío (fuera): " + ", ".join(m["sin_fecha_envio"]))
    for name, why in m["invalidos"]:
        print(f"  ⚠️  dato inválido: {name} — {why}")
    exi_ids = {id(a) for a in exi}
    for dim in DIMENSIONS:
        groups: dict[str, list] = {}
        for a in mad:
            valor = a.get(dim) or "sin dato"
            if dim in VALORES_VALIDOS and valor != "sin dato" and valor.strip() not in VALORES_VALIDOS[dim]:
                valor = "inválido"
            groups.setdefault(valor, []).append(a)
        parts = [f"{k} {sum(1 for a in v if id(a) in exi_ids)}/{len(v)}" for k, v in sorted(groups.items())]
        print(f"  Por {dim}: " + (" · ".join(parts) if parts else "sin maduras"))
    mins = [(a, int(a["minutos_preparacion"])) for a in mad if (a.get("minutos_preparacion") or "").isdigit()]
    exi_con_min = [a for a, _ in mins if id(a) in exi_ids]
    if not mins:
        print("  Esfuerzo: sin minutos registrados en la cohorte madura")
    elif not exi_con_min:
        print(f"  Esfuerzo: {len(mins)}/{len(mad)} con minutos; sin éxitos con dato")
    else:
        print(f"  Esfuerzo: {sum(v for _, v in mins) / len(exi_con_min):.0f} min por respuesta humana "
              f"({len(mins)}/{len(mad)} con minutos, {len(exi_con_min)} éxitos con dato)")
    cerrados = [a for a in m["universo"] if a.get("status") in CLOSED]  # solo la cohorte, no el histórico
    valida = lambda a: (a.get("cierre_causa_origen") or "").strip() in VALORES_VALIDOS["cierre_causa_origen"]
    reg = [a for a in cerrados if valida(a)]  # un valor inválido se avisa aparte y no cuenta como cobertura
    decl = [a for a in reg if a["cierre_causa_origen"].strip() == "declarada"]
    print(f"  Cierres: causa registrada {_pct(len(reg), len(cerrados))} · declarada por la empresa {_pct(len(decl), len(cerrados))}")


def report(corte: date | None = None, desde: date | None = None, hasta: date | None = None) -> int:
    tier_labels = load_tier_labels()
    apps = load_applications()
    by_tier: dict[str, list[dict]] = {}
    for app in apps:
        by_tier.setdefault(app["tier"], []).append(app)

    if tier_labels:
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
    if unknown_tier and tier_labels:
        print(f"\n⚠️  Tiers en aplicaciones sin definir en config.yaml: {', '.join(unknown_tier)}")

    unclassified = sum(
        1
        for path in APPLICATIONS_DIR.glob("*.md")
        if (f := parse_frontmatter(path.read_text())).get("type") == "application_tracking"
        and f.get("status") != "withdrawn"
        and not f.get("tier")
    )
    if unclassified:
        print(f"\n⚠️  {unclassified} aplicación(es) sin campo `tier` — no se contaron.")

    print_response(load_all_trackings(), corte or date.today(), desde, hasta)
    if not tier_labels:
        print("\n⚠️  config.yaml no tiene `tiers:` definidos — sin conversión por categoría.")
        print("   Agrega al menos una categoría de rol antes de clasificar aplicaciones.")
        return 1
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

    response_demo()
    print("demo ok")


def response_demo() -> None:
    """Casos de la métrica de respuesta humana, con corte fijo 2026-10-06."""
    C = date(2026, 10, 6)
    d = lambda n: (C - timedelta(days=n)).isoformat()  # envío hace n días

    def app(name, sub, **kw):
        if kw.get("respuesta_humana") in ("si", "ambigua") and "respuesta_humana_fecha" in kw:
            kw.setdefault("respuesta_humana_precision", "exacta")
            kw.setdefault("respuesta_humana_evidencia", "correo del reclutador")
        return {"company": name, "date_submitted": sub, "status": kw.pop("status", "submitted"), **kw}

    apps = [
        app("dia0", d(20), respuesta_humana="si", respuesta_humana_fecha=d(20)),
        app("dia14", d(20), respuesta_humana="si", respuesta_humana_fecha=d(6)),
        app("dia15", d(20), respuesta_humana="si", respuesta_humana_fecha=d(5)),
        app("inmadura", d(5), respuesta_humana="si", respuesta_humana_fecha=d(4)),
        app("auto_y_humana", d(30), respuesta_auto_fecha=d(30), respuesta_humana="si", respuesta_humana_fecha=d(27)),
        app("ambigua_en", d(30), respuesta_humana="ambigua", respuesta_humana_fecha=d(25)),
        app("ambigua_fuera", d(40), respuesta_humana="ambigua", respuesta_humana_fecha=d(10)),
        app("ambigua_sin_fecha", d(40), respuesta_humana="ambigua"),
        app("anterior_al_envio", d(30), respuesta_humana="si", respuesta_humana_fecha=d(31)),
        app("retirada", d(30), status="withdrawn", respuesta_humana="no"),
        app("nunca", "", status="withdrawn"),
        app("reemplazada", d(30), status="reemplazado", respuesta_humana="si", respuesta_humana_fecha=d(28)),
        app("reenvio", d(10), intento_de="reemplazada"),
        app("vieja_sin_campos", d(60)),
        app("fecha_invalida", "2026-13-40"),
        app("con_comentario", d(30), respuesta_humana="si # x", respuesta_humana_fecha=d(29)),
        app("cv_a", d(30), cv_base="liderazgo", cv_version="aaaaaaaaaaaa", respuesta_humana="no"),
        app("cv_b", d(30), cv_base="liderazgo", cv_version="bbbbbbbbbbbb", respuesta_humana="no"),
        app("cv_desc", d(30), cv_version="desconocido", respuesta_humana="no"),
        app("cv_na", d(30), cv_version="no_aplica", respuesta_humana="no", minutos_preparacion="30"),
    ]
    m = response_metric(apps, C)
    names = lambda k: sorted(a.get("company") for a in m[k])
    assert names("exitos") == ["auto_y_humana", "dia0", "dia14", "reemplazada"], names("exitos")
    assert names("tardias") == ["dia15"]
    assert "inmadura" in names("inmaduras") and "reenvio" in names("inmaduras")
    assert names("ambiguas_en_ventana") == ["ambigua_en"]
    assert "retirada" in [a["company"] for a in m["maduras"]] and "nunca" not in [a["company"] for a in m["universo"]]
    inval = [n for n, _ in m["invalidos"]]
    assert {"anterior_al_envio", "fecha_invalida", "con_comentario", "ambigua_sin_fecha"} <= set(inval), inval
    assert "vieja_sin_campos" in names("sin_dato")
    # evidencia, precisión y valores de los campos que sostienen la métrica
    x = [
        app("si_sin_evidencia", d(30), respuesta_humana="si", respuesta_humana_fecha=d(28), respuesta_humana_evidencia=""),
        app("si_sin_precision", d(30), respuesta_humana="si", respuesta_humana_fecha=d(28), respuesta_humana_precision=""),
        app("si_precision_rara", d(30), respuesta_humana="si", respuesta_humana_fecha=d(28), respuesta_humana_precision="aprox"),
        app("ambigua_sin_evidencia", d(30), respuesta_humana="ambigua", respuesta_humana_fecha=d(28), respuesta_humana_evidencia=""),
        app("si_completa", d(30), respuesta_humana="si", respuesta_humana_fecha=d(28), canal="calido", fit="compatible"),
        app("canal_comillas", d(30), respuesta_humana="no", canal='"calido"'),
        app("fit_comentario", d(30), respuesta_humana="no", fit="compatible # comentario"),
        app("canal_vacio", d(30), respuesta_humana="no", canal="", fit=""),
    ]
    mx = response_metric(x, C)
    nombres = lambda k: sorted(a["company"] for a in mx[k])
    assert nombres("exitos") == ["si_completa"], nombres("exitos")
    inv = {n: why for n, why in mx["invalidos"]}
    assert "evidencia" in inv["si_sin_evidencia"] and "precision" in inv["si_sin_precision"], inv
    assert "si_precision_rara" in inv and "ambigua_sin_evidencia" in inv, inv
    assert nombres("ambiguas_en_ventana") == [], "una ambigua sin evidencia no suma ni a la sensibilidad"
    assert "ambigua_sin_evidencia" in nombres("ambiguas"), "pero sigue visible"
    assert "canal_comillas" in inv and "fit_comentario" in inv and "canal_vacio" not in inv, inv
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        print_response(x, C, None, None)
    salida = buf.getvalue()
    linea_canal = [l for l in salida.splitlines() if l.strip().startswith("Por canal:")][0]
    assert "inválido 0/1" in linea_canal, linea_canal
    assert "dato inválido: canal_comillas" in salida and "dato inválido: fit_comentario" in salida, salida
    # cohorte reproducible: el límite --hasta es exclusivo y un corte posterior no cambia el universo
    m1 = response_metric(apps, C, desde=date.fromisoformat(d(30)), hasta=date.fromisoformat(d(20)))
    m2 = response_metric(apps, C + timedelta(days=60), desde=date.fromisoformat(d(30)), hasta=date.fromisoformat(d(20)))
    assert {a["company"] for a in m1["universo"]} == {a["company"] for a in m2["universo"]}
    assert "dia0" not in {a["company"] for a in m1["universo"]}, "hasta es exclusivo"
    assert response_metric([], C)["maduras"] == []
    # desglose por cv_version separa dos versiones de una misma base
    groups = {a.get("cv_version") for a in m["maduras"] if a.get("cv_base") == "liderazgo"}
    assert groups == {"aaaaaaaaaaaa", "bbbbbbbbbbbb"}
    cierres = [app("c_ok", d(30), status="rejected", cierre_causa_origen="declarada"),
               app("c_mal", d(30), status="rejected", cierre_causa_origen="declarada # nota")]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        print_response(cierres, C, None, None)
    assert "causa registrada 1/2" in buf.getvalue(), "una causa de cierre inválida no cuenta como registrada:\n" + buf.getvalue()
    print_response(apps, C, None, None)  # no debe tronar con 0 éxitos con minutos


def _arg(name: str) -> date | None:
    if name in sys.argv:
        value = sys.argv[sys.argv.index(name) + 1]
        parsed = parse_date(value)
        if parsed is None:
            print(f"Fecha inválida para {name}: {value}")
            sys.exit(2)
        return parsed
    return None


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--demo":
        demo()
        sys.exit(0)
    sys.exit(report(_arg("--corte"), _arg("--desde"), _arg("--hasta")))
