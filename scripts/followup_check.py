#!/usr/bin/env python3
"""Follow-up checker: agenda y alertas de seguimiento, compartidas con pipeline_board.py.

Lee el frontmatter de applications/*-application.md (campos planos) y reporta:
  - agenda: next_date vencida, de hoy y de los próximos 3 días (solo procesos activos);
  - alertas por proceso activo:
      sin_fecha      avanzado o esperando, sin next_date y sin pausa vigente
      silencio       waiting, sin pausa vigente, más de 15 días desde el ancla
      revisar_canal  no_channel, días 21-44 desde el envío, sin revision_canal_fecha
      sugerir_cierre no_channel, desde el día 45 del envío (la revisión no lo mueve;
                     nunca cierra solo)
      pausa_vencida  pausa_hasta en el pasado
      sin_auditar    follow_up unconfirmed o ausente
      datos_medicion enviada desde `cohort_start` (config.yaml; vacío = sin cohorte, nunca
                     avisa) y sin alguno de MEDICION_OBLIGATORIA; sigue avisando aunque el
                     proceso ya esté cerrado (la cohorte se lee al final)
      dato_invalido  un campo de fecha que no es AAAA-MM-DD exacto
El ancla del silencio es el valor más reciente de contacto_empresa_ultimo,
date_resubmitted y date_submitted; last_updated no cuenta (editar un archivo no
reinicia el reloj).
Una pausa vigente (pausa_motivo con pausa_hasta vacío o futuro) suprime sin_fecha y
silencio, pero no la agenda.

Uso: followup_check.py [--hoy AAAA-MM-DD]
     followup_check.py --demo
"""
from __future__ import annotations

import re
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _config import load_config  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
APPLICATIONS_DIR = REPO_ROOT / "applications"

WAITING_WINDOW_DAYS = 15  # ponytail: ventana "normal" antes de avisar silencio; ajustar si la evidencia real difiere
REVIEW_CHANNEL_DAYS = 21
SUGGEST_CLOSE_DAYS = 45
CHECKER_WINDOW_DAYS = 3
MEDICION_OBLIGATORIA = ("canal", "fit", "cv_version", "parseo", "minutos_preparacion")
ACTIVE = {"submitted", "interviewing", "in_progress"}
DATE_FIELDS = ("next_date", "date_submitted", "date_resubmitted", "contacto_empresa_ultimo",
               "respuesta_humana_fecha", "respuesta_auto_fecha", "pausa_hasta", "revision_canal_fecha",
               "actividad_propia_ultima")


def parse_date(value: str | None) -> date | None:
    """Solo AAAA-MM-DD exacto: un valor con '#', comillas o texto extra no es fecha."""
    if not value or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def cohorte_desde(cfg: dict | None = None) -> date | None:
    """`cohort_start` de config.yaml. Vacío o ausente = sin cohorte (nadie debe campos de
    medición); inválido = igual, pero avisa por stderr en vez de apagar la alerta en silencio.
    YAML convierte `2026-10-07` sin comillas en date: se acepta tal cual."""
    valor = (cfg if cfg is not None else load_config()).get("cohort_start")
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if valor in (None, ""):
        return None
    if (d := parse_date(str(valor))) is None:
        print(f"cohort_start inválido en config.yaml ('{valor}'): se ignora; usa AAAA-MM-DD", file=sys.stderr)
    return d


COHORTE_DESDE = cohorte_desde()  # inicio de la cohorte de medición; cámbialo en config.yaml al abrir la siguiente


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
        fields["_file"] = path.name  # para que otros consumidores puedan enlazar al tracking
        apps.append(fields)
    return apps


def days_since(date_str: str, today: date):
    d = parse_date(date_str)
    return (today - d).days if d else None


def ancla_silencio(app: dict) -> date | None:
    fechas = [parse_date(app.get(k)) for k in ("contacto_empresa_ultimo", "date_resubmitted", "date_submitted")]
    fechas = [f for f in fechas if f]
    return max(fechas) if fechas else None


def resolve_anchor_date(app: dict) -> str:
    """Compatibilidad con el tablero: el ancla del silencio como texto (sin last_updated)."""
    a = ancla_silencio(app)
    return a.isoformat() if a else ""


def pausa_vigente(app: dict, today: date) -> bool:
    if not app.get("pausa_motivo"):
        return False
    crudo = (app.get("pausa_hasta") or "").strip()
    if not crudo:
        return True  # pausa sin vencimiento
    hasta = parse_date(crudo)
    return hasta is not None and hasta >= today  # fecha inválida: no hay pausa vigente (dato_invalido avisa)


def agenda(apps: list, today: date, ventana: int) -> list:
    """(fecha, app) de procesos activos con next_date vencida, de hoy o dentro de la ventana."""
    items = []
    for app in apps:
        if app.get("status") not in ACTIVE:
            continue
        d = parse_date(app.get("next_date"))
        if d is not None and d <= today + timedelta(days=ventana):
            items.append((d, app))
    return sorted(items, key=lambda p: (p[0], p[1].get("company", "")))


def alertas(app: dict, today: date) -> list[tuple[str, str]]:
    out = []
    enviado = parse_date(app.get("date_submitted"))
    if COHORTE_DESDE and enviado and enviado >= COHORTE_DESDE and app.get("status") != "reemplazado":
        faltan = [k for k in MEDICION_OBLIGATORIA if not app.get(k, "").strip()]
        if faltan:
            out.append(("datos_medicion", "faltan: " + ", ".join(faltan)))
    if app.get("status") not in ACTIVE:
        return out
    invalid = [k for k in DATE_FIELDS if app.get(k) and parse_date(app.get(k)) is None]
    if invalid:
        out.append(("dato_invalido", "fecha inválida en " + ", ".join(invalid)))
    fu = app.get("follow_up") or ""
    if fu in ("", "unconfirmed"):
        out.append(("sin_auditar", "follow_up sin auditar"))
    pausa = pausa_vigente(app, today)
    hasta = parse_date(app.get("pausa_hasta"))
    if app.get("pausa_motivo") and not pausa and hasta is not None:  # fecha inválida: solo dato_invalido
        out.append(("pausa_vencida", "la pausa venció: revisar"))
    if not pausa and not parse_date(app.get("next_date")) and (
            app.get("advanced") == "yes" or fu in ("waiting", "pending_contact")):
        out.append(("sin_fecha", "proceso sin próxima fecha"))
    ancla = ancla_silencio(app)
    if fu == "waiting" and not pausa and ancla and (today - ancla).days > WAITING_WINDOW_DAYS:
        out.append(("silencio", f"{(today - ancla).days} días sin contacto de la empresa"))
    sub = parse_date(app.get("date_submitted"))
    if fu == "no_channel" and sub:
        dias = (today - sub).days
        if dias >= SUGGEST_CLOSE_DAYS:
            out.append(("sugerir_cierre", f"día {dias} sin canal: sugerir cierre"))
        elif dias >= REVIEW_CHANNEL_DAYS and not parse_date(app.get("revision_canal_fecha")):
            out.append(("revisar_canal", f"día {dias} sin canal: buscar canal (20-30 min)"))
    return out


TITULOS = {"dato_invalido": "Datos inválidos", "sin_auditar": "Sin auditar",
           "datos_medicion": "Faltan campos de medición (cohorte)", "pausa_vencida": "Pausas vencidas",
           "sin_fecha": "Activos sin próxima fecha", "silencio": f"Más de {WAITING_WINDOW_DAYS} días de silencio",
           "revisar_canal": f"Sin canal, día {REVIEW_CHANNEL_DAYS}+: buscar canal",
           "sugerir_cierre": f"Sin canal, día {SUGGEST_CLOSE_DAYS}+: sugerir cierre"}  # el orden es la prioridad


def por_tipo(apps: list, today: date) -> dict[str, list[tuple[dict, str]]]:
    """tipo de alerta -> [(app, texto)] sobre todos los trackings; cada consumidor filtra lo suyo."""
    out: dict[str, list[tuple[dict, str]]] = {}
    for a in apps:
        for tipo, texto in alertas(a, today):
            out.setdefault(tipo, []).append((a, texto))
    return out


def report(today: date | None = None) -> int:
    today = today or date.today()
    apps = load_applications()
    bloques = []
    items = agenda(apps, today, CHECKER_WINDOW_DAYS)
    for titulo, cond in (("Vencidas", lambda d: d < today), ("Hoy", lambda d: d == today),
                         (f"Próximos {CHECKER_WINDOW_DAYS} días", lambda d: d > today)):
        filas = [f"  - {d.isoformat()} · {a.get('company', '?')} — {a.get('next_action', '')[:90]}" for d, a in items if cond(d)]
        if filas:
            bloques.append(f"{titulo}:\n" + "\n".join(filas))
    alert = por_tipo(apps, today)
    for tipo, titulo in TITULOS.items():
        if alert.get(tipo):
            filas = [f"  - {a.get('company', '?')} ({a.get('position', '')}) — {texto}" for a, texto in alert[tipo]]
            bloques.append(f"{titulo}:\n" + "\n".join(filas))
    print("\n\n".join(bloques) if bloques else "Sin pendientes de seguimiento.")
    return 0


def demo() -> None:
    """ponytail self-check con hoy fijo: agenda, cada alerta y sus límites."""
    global COHORTE_DESDE, APPLICATIONS_DIR
    hoy = date(2026, 10, 6)
    COHORTE_DESDE = date(2026, 10, 7)  # el demo no depende del config.yaml de quien lo corra
    d = lambda n: (hoy + timedelta(days=n)).isoformat()
    base = {"status": "submitted", "follow_up": "waiting", "company": "X"}

    def app(**kw):
        a = dict(base)
        a.update(kw)
        return a

    apps = [app(company="ayer", next_date=d(-1)), app(company="hoy", next_date=d(0)),
            app(company="mas3", next_date=d(3)), app(company="mas4", next_date=d(4)),
            app(company="cerrada", status="rejected", advanced="yes", next_date=d(0)),
            app(company="reemplazada", status="reemplazado", next_date=d(0))]
    assert [a["company"] for _, a in agenda(apps, hoy, 3)] == ["ayer", "hoy", "mas3"]
    assert "mas4" in [a["company"] for _, a in agenda(apps, hoy, 7)]

    tipos = lambda a: [t for t, _ in alertas(a, hoy)]
    # pausa vigente sin fecha: suprime sin_fecha y silencio, pero sigue en la agenda
    pausada = app(advanced="yes", date_submitted=d(-40), pausa_motivo="congelado por RH")
    assert tipos(pausada) == []
    assert agenda([dict(pausada, next_date=d(1))], hoy, 3)
    assert "pausa_vencida" in tipos(app(next_date=d(2), pausa_motivo="x", pausa_hasta=d(-1)))
    # silencio: contacto reciente de la empresa reinicia el reloj; last_updated no
    assert "silencio" not in tipos(app(next_date=d(2), date_submitted=d(-40), contacto_empresa_ultimo=d(-3)))
    assert "silencio" in tipos(app(next_date=d(2), date_submitted=d(-40), last_updated=d(0)))
    assert "silencio" not in tipos(app(next_date=d(2), date_submitted=d(-40), date_resubmitted=d(-5)))
    # no_channel: límites 20/21/44/45 desde el envío
    nc = lambda dias, **kw: app(follow_up="no_channel", date_submitted=d(-dias), **kw)
    assert tipos(nc(20)) == []
    assert tipos(nc(21)) == ["revisar_canal"]
    assert tipos(nc(44)) == ["revisar_canal"]
    assert tipos(nc(45)) == ["sugerir_cierre"]
    # revisión hecha el día 21: no repite la búsqueda y el cierre sigue en el día 45 original
    assert tipos(nc(30, revision_canal_fecha=d(-9))) == []
    assert tipos(nc(45, revision_canal_fecha=d(-24))) == ["sugerir_cierre"]
    # sin auditar y datos inválidos
    assert "sin_auditar" in tipos(app(follow_up="unconfirmed", next_date=d(1)))
    assert "dato_invalido" in tipos(app(next_date="2026-10-09 # nota"))
    assert "sin_fecha" in tipos(app(advanced="yes"))
    assert alertas(app(status="closed_no_feedback", follow_up="no_channel", date_submitted=d(-90)), hoy) == []
    # datos_medicion: desde la cohorte, un campo faltante a la vez; el cierre no la apaga
    completo = dict(canal="portal", fit="compatible", cv_version="abc123", parseo="ok", minutos_preparacion="30")
    env = dict(date_submitted="2026-10-10", next_date=d(2))
    assert "datos_medicion" not in tipos(app(**env, **completo)), "registro completo"
    for campo in MEDICION_OBLIGATORIA:
        incompleto = {k: v for k, v in completo.items() if k != campo}
        faltan = dict(alertas(app(**env, **incompleto), hoy)).get("datos_medicion", "")
        assert faltan == f"faltan: {campo}", (campo, faltan)
    vacio = dict(alertas(app(**env), hoy))["datos_medicion"]
    assert all(k in vacio for k in MEDICION_OBLIGATORIA), "todo vacío lista los cinco"
    assert "datos_medicion" not in tipos(app(date_submitted="2026-10-06", next_date=d(2))), "antes de la cohorte"
    assert "datos_medicion" not in tipos(app(status="reemplazado", date_submitted="2026-10-10")), "reemplazado"
    for estado in ("rejected", "closed_no_feedback"):
        cerrado = alertas(app(status=estado, date_submitted="2026-10-10", **{k: v for k, v in completo.items() if k != "fit"}), hoy)
        assert cerrado == [("datos_medicion", "faltan: fit")], (estado, cerrado)
    assert alertas(app(status="rejected", date_submitted="2026-10-10", **completo), hoy) == []
    assert "datos_medicion" in por_tipo([app(status="rejected", date_submitted="2026-10-10")], hoy)
    # cohort_start: vacío = sin cohorte (nunca avisa); date de YAML y texto valen igual
    COHORTE_DESDE = cohorte_desde({})
    assert COHORTE_DESDE is None and "datos_medicion" not in tipos(app(**env))
    assert cohorte_desde({"cohort_start": date(2026, 10, 7)}) == cohorte_desde({"cohort_start": "2026-10-07"}) == date(2026, 10, 7)
    assert cohorte_desde({"cohort_start": ""}) is None and cohorte_desde({"cohort_start": "ayer"}) is None
    # pipeline_board.py depende de `_file` para enlazar cada tarjeta a su tracking
    sample = "---\ntype: application_tracking\ncompany: Test Co\n---\nbody\n"
    original = APPLICATIONS_DIR
    with tempfile.TemporaryDirectory() as tmp:
        APPLICATIONS_DIR = Path(tmp)
        (APPLICATIONS_DIR / "fixture-application.md").write_text(sample, encoding="utf-8")
        (APPLICATIONS_DIR / "otro.md").write_text("sin frontmatter", encoding="utf-8")
        apps = load_applications()
        assert [a["_file"] for a in apps] == ["fixture-application.md"]
    APPLICATIONS_DIR = original
    print("demo ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--demo":
        demo()
        sys.exit(0)
    hoy_arg = sys.argv[sys.argv.index("--hoy") + 1] if "--hoy" in sys.argv else None
    sys.exit(report(parse_date(hoy_arg) if hoy_arg else None))
