#!/usr/bin/env python3
"""Tablero visual del pipeline: genera applications/pipeline.html leyendo el
frontmatter de applications/*-application.md.

La vista se genera, nunca se edita a mano: si el tablero y un tracking no
coinciden, el tracking manda — la fuente de verdad siempre es el frontmatter.

Las columnas NO son estados administrativos, son de quién es el siguiente
movimiento — agrupar por "enviada" junta aplicaciones que no comparten nada.
La regla completa está en `whose_move()`.

Reutiliza el parseo y la lógica de fechas de followup_check.py — misma
definición de "días de silencio" en las dos herramientas, a propósito. Las
categorías de rol (`tier`) salen de `config.yaml`, igual que en
conversion_report.py — no hay categorías precargadas, las tuyas reflejan tu
propia carrera.

Uso:
    python3 scripts/pipeline_board.py           # genera el HTML
    python3 scripts/pipeline_board.py --open    # genera y lo abre
    python3 scripts/pipeline_board.py --agenda  # solo las fechas, en texto
    python3 scripts/pipeline_board.py --demo    # self-check
"""
import html
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

LIMIT_COL = 5  # tarjetas visibles antes de "mostrar más" en una columna del tablero
BADGE_CLASS = {
    "rejected": "rechazo",
    "closed_no_feedback": "silencio",
    "withdrawn": "no-enviada",
    "offer": "oferta",
}

EXTRA_STYLE = """
  .leyenda { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; padding: 6px 0 14px; font-size: 12px; color: var(--apagado); }
  .leyenda span { display: flex; align-items: center; gap: 6px; }
  .leyenda .pt { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
  .leyenda .bm { width: 10px; height: 10px; border-radius: 2px; border: 1.5px solid var(--mia); flex-shrink: 0; }

  .barra-filtro { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding-bottom: 16px; }
  .buscar { flex-shrink: 0; font: inherit; background: var(--sup); border: 1px solid var(--linea);
            border-radius: 7px; padding: 7px 10px; font-size: 13px; color: var(--tinta); min-width: 200px; }
  .buscar::placeholder { color: var(--tenue); }
  .chip-filtro { font: inherit; font-size: 12px; padding: 6px 12px; border-radius: 999px;
                 border: 1px solid var(--linea); background: var(--sup); color: var(--apagado); cursor: pointer; }
  .chip-filtro.activo { background: var(--tinta); border-color: var(--tinta); color: var(--papel); }
  .chip-filtro.vencidas { margin-left: auto; }

  .alerta { display: flex; align-items: baseline; gap: 8px; background: oklch(0.9 0.05 75); border: 1px solid oklch(0.75 0.08 75);
            border-radius: 10px; padding: 9px 14px; margin-bottom: 18px; font-size: 13px; color: oklch(0.35 0.1 75); }
  .alerta b { font-family: var(--mono); font-size: 12px; }

  .tarjeta[hidden], .chip[hidden] { display: none; }
  .mas { text-align: center; font: inherit; font-size: 12px; color: var(--apagado); border: 1px dashed var(--linea);
         border-radius: 10px; padding: 10px; cursor: pointer; background: none; width: 100%; }
  .mas:hover { background: var(--hueso); color: var(--tinta); }
  .vacio-filtro { color: var(--apagado); font-style: italic; text-align: center; padding: 30px 0; grid-column: 1 / -1; }

  .generado { font-size: 11px; color: var(--tenue); }

  .punto-radar a { display: flex; align-items: center; gap: 8px; text-decoration: none; color: inherit; }
  .punto-radar a:hover .perla { box-shadow: 0 0 0 3px rgba(0,0,0,0.08); }
  .punto-radar a:hover .nombre { text-decoration: underline; }

  .nav-ficha { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; }
  .prev-next { display: flex; gap: 16px; font-size: 12px; }
  .prev-next a { color: var(--apagado); text-decoration: none; }
  .prev-next a:hover { color: var(--tinta); }
  .leyenda-recorrido { display: flex; gap: 14px; flex-wrap: wrap; margin: 4px 0 16px; font-size: 11px; color: var(--tenue); }
  .leyenda-recorrido span { display: flex; align-items: center; gap: 5px; }
  .leyenda-recorrido .lp { width: 8px; height: 8px; border-radius: 50%; border: 1px solid; flex-shrink: 0; }

  .resumen-historico { display: flex; gap: 20px; flex-wrap: wrap; font-size: 13px; color: var(--apagado); padding-bottom: 14px; }
  .resumen-historico b { color: var(--tinta); font-family: var(--mono); font-weight: 500; }
  th.ordenable { cursor: pointer; user-select: none; }
  th.ordenable .flecha { font-size: 9px; margin-left: 3px; color: var(--tenue); }
  .badge { display: inline-block; font-size: 11px; padding: 3px 9px; border-radius: 999px; border: 1px solid transparent; white-space: nowrap; }
  .badge.rechazo { background: var(--hueso); border-color: var(--tenue); color: var(--tinta); }
  .badge.silencio { background: var(--hueso); color: var(--apagado); }
  .badge.no-enviada { border: 1px dashed var(--linea); color: var(--tenue); }
  .badge.oferta { background: oklch(0.9 0.05 155); border-color: oklch(0.75 0.08 155); color: oklch(0.35 0.1 155); }

  a:focus-visible, button:focus-visible, input:focus-visible {
    outline: 2px solid var(--mia); outline-offset: 2px; border-radius: 3px;
  }
"""

EXTRA_SCRIPT = """
(function () {
  var buscarT = document.getElementById("buscar-tablero");
  var chipsTier = document.querySelectorAll(".chip-filtro[data-tier]");
  var chipVencidas = document.getElementById("chip-vencidas");
  var tarjetas = document.querySelectorAll(".tarjeta[data-tier]");
  var chipsAgenda = document.querySelectorAll(".agenda .chip");
  var agenda = document.querySelector(".agenda");
  var tierActivo = "";
  var soloVencidas = false;

  function aplicarFiltroTablero() {
    var texto = ((buscarT && buscarT.value) || "").toLowerCase().trim();
    var hayFiltro = texto !== "" || tierActivo !== "" || soloVencidas;
    var visibles = 0;
    var porColumna = { mia: 0, suya: 0, nadie: 0 };
    tarjetas.forEach(function (t) {
      var pasaTier = !tierActivo || t.dataset.tier === tierActivo;
      var pasaTexto = !texto || (t.dataset.buscar || "").indexOf(texto) !== -1;
      var pasaVencidas = !soloVencidas || t.dataset.vencida === "1";
      var visible = pasaTier && pasaTexto && pasaVencidas;
      // el conteo de la columna es "cuántas cumplen el filtro", no "cuántas
      // están en el DOM sin oculto" — una colapsada por "mostrar más" sigue
      // contando aunque hoy no se vea, o el número mentiría igual que antes
      if (visible && porColumna.hasOwnProperty(t.dataset.col)) porColumna[t.dataset.col]++;
      if (!t.classList.contains("mas-oculta") || hayFiltro) {
        t.hidden = !visible;
        if (visible) visibles++;
      }
    });
    document.querySelectorAll(".mas").forEach(function (boton) { boton.hidden = hayFiltro; });
    var vacio = document.getElementById("vacio-tablero");
    if (vacio) vacio.hidden = visibles > 0;
    Object.keys(porColumna).forEach(function (key) {
      var cuenta = document.getElementById("cuenta-" + key);
      if (cuenta) cuenta.textContent = porColumna[key];
    });

    // "Próximos días" no es una cuarta columna: muestra la misma agenda que las
    // tarjetas de abajo, así que responde a los mismos tres filtros o deja de
    // tener sentido tenerla a la vista (mismo problema que ya se corrigió arriba,
    // esta vez para "solo vencidas" en vez de tier/texto).
    var agendaVisibles = 0;
    chipsAgenda.forEach(function (c) {
      var pasaTier = !tierActivo || c.dataset.tier === tierActivo;
      var pasaTexto = !texto || (c.dataset.buscar || "").indexOf(texto) !== -1;
      var pasaVencidas = !soloVencidas || c.dataset.vencida === "1";
      var visible = pasaTier && pasaTexto && pasaVencidas;
      c.hidden = !visible;
      if (visible) agendaVisibles++;
    });
    if (agenda) agenda.hidden = hayFiltro && agendaVisibles === 0;
    var contadorAgenda = document.getElementById("agenda-cuenta");
    if (contadorAgenda) contadorAgenda.textContent = agendaVisibles;
  }

  if (buscarT) buscarT.addEventListener("input", aplicarFiltroTablero);
  chipsTier.forEach(function (chip) {
    chip.addEventListener("click", function () {
      tierActivo = tierActivo === chip.dataset.tier ? "" : chip.dataset.tier;
      chipsTier.forEach(function (c) { c.classList.toggle("activo", c.dataset.tier === tierActivo); });
      aplicarFiltroTablero();
    });
  });
  if (chipVencidas) chipVencidas.addEventListener("click", function () {
    soloVencidas = !soloVencidas;
    chipVencidas.classList.toggle("activo", soloVencidas);
    aplicarFiltroTablero();
  });

  document.querySelectorAll(".mas").forEach(function (boton) {
    boton.addEventListener("click", function () {
      var col = boton.closest(".col");
      col.querySelectorAll(".mas-oculta").forEach(function (t) { t.hidden = false; });
      boton.hidden = true;
    });
  });

  var buscarH = document.getElementById("buscar-historico");
  var chipsDesenlace = document.querySelectorAll(".chip-filtro[data-desenlace]");
  var desenlaceActivo = "";
  var filas = document.querySelectorAll("#tabla-historico tbody tr[data-buscar]");

  function aplicarFiltroHistorico() {
    var texto = ((buscarH && buscarH.value) || "").toLowerCase().trim();
    var visibles = 0;
    filas.forEach(function (f) {
      var pasaDesenlace = !desenlaceActivo || f.dataset.desenlace === desenlaceActivo;
      var pasaTexto = !texto || f.dataset.buscar.indexOf(texto) !== -1;
      var visible = pasaDesenlace && pasaTexto;
      f.hidden = !visible;
      if (visible) visibles++;
    });
    var vacio = document.getElementById("vacio-historico");
    if (vacio) vacio.hidden = visibles > 0;
  }

  if (buscarH) buscarH.addEventListener("input", aplicarFiltroHistorico);
  chipsDesenlace.forEach(function (chip) {
    chip.addEventListener("click", function () {
      desenlaceActivo = desenlaceActivo === chip.dataset.desenlace ? "" : chip.dataset.desenlace;
      chipsDesenlace.forEach(function (c) { c.classList.toggle("activo", c.dataset.desenlace === desenlaceActivo); });
      aplicarFiltroHistorico();
    });
  });

  document.querySelectorAll("th.ordenable").forEach(function (th) {
    var asc = true;
    th.addEventListener("click", function () {
      var tbody = document.querySelector("#tabla-historico tbody");
      var filasArr = Array.prototype.slice.call(tbody.querySelectorAll("tr[data-buscar]"));
      var campo = th.dataset.ordenar;
      filasArr.sort(function (a, b) {
        var va = a.dataset[campo] || "";
        var vb = b.dataset[campo] || "";
        if (va < vb) return asc ? -1 : 1;
        if (va > vb) return asc ? 1 : -1;
        return 0;
      });
      filasArr.forEach(function (f) { tbody.appendChild(f); });
      document.querySelectorAll("th.ordenable .flecha").forEach(function (f) { f.textContent = "▾"; });
      th.querySelector(".flecha").textContent = asc ? "▾" : "▴";
      asc = !asc;
    });
  });
})();
"""

sys.path.insert(0, str(Path(__file__).resolve().parent))
import conversion_report  # noqa: E402
from _config import load_config  # noqa: E402
from followup_check import (  # noqa: E402
    APPLICATIONS_DIR,
    REPO_ROOT,
    WAITING_WINDOW_DAYS,
    days_since,
    load_applications,
    resolve_anchor_date,
)

OUTPUT = APPLICATIONS_DIR / "pipeline.html"

CLOSE_THRESHOLD_DAYS = 90  # ventana antes de dar por cerrada una aplicación en silencio; ajusta si tu evidencia real difiere
AGENDA_WINDOW_DAYS = 7

ACTIVE_STATUS = {"interviewing", "submitted", "in_progress"}

COLUMNS = [
    ("mia", "Tu jugada", "oklch(0.58 0.14 25)"),
    ("suya", "Su jugada", "oklch(0.58 0.14 155)"),
    ("nadie", "Sin canal", "#b3ada2"),
]

CLOSED_LABELS = {
    "rejected": "Rechazada",
    "closed_no_feedback": "Cerrada sin respuesta",
    "withdrawn": "No enviada",
    "offer": "Oferta",
}

def load_tier_labels() -> dict:
    """Mismo criterio que conversion_report.py: las categorías de rol son
    tuyas, no vienen precargadas — se leen de `tiers:` en config.yaml."""
    return {t["id"]: t["label"] for t in (load_config().get("tiers") or [])}


TIER_LABELS = load_tier_labels()

DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def parse_date(value):
    try:
        return datetime.strptime((value or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def whose_move(app: dict) -> str:
    """Quién debe mover. Una fecha comprometida es tuya aunque la reunión la
    corran ellos: está en tu calendario y tienes que llegar preparado."""
    if app.get("follow_up") == "no_channel":
        return "nadie"
    if parse_date(app.get("next_date")):
        return "mia"
    if app.get("follow_up") == "pending_contact" or app.get("status") == "in_progress":
        return "mia"
    return "suya"


def overdue(app: dict, days) -> bool:
    """Pasó la ventana normal de espera y sigue sin reclasificarse."""
    return (
        app.get("follow_up") in ("waiting", "unconfirmed")
        and days is not None
        and days > WAITING_WINDOW_DAYS
    )


def fecha_corta(d: date) -> str:
    return f"{DIAS[d.weekday()]} {d.day}"


def fecha_larga(d: date) -> str:
    """Para fechas pasadas: el día de la semana ya no informa, el mes sí."""
    return f"{d.day} {MESES[d.month - 1][:3]}"


def agenda(apps: list, today: date) -> list:
    """Lo comprometido dentro de la ventana, en orden. Lo vencido sigue
    apareciendo: una fecha que ya pasó sin cerrarse es lo más urgente que hay."""
    items = []
    for app in apps:
        d = parse_date(app.get("next_date"))
        if d is None or d > today + timedelta(days=AGENDA_WINDOW_DAYS):
            continue
        items.append((d, app))
    return sorted(items, key=lambda pair: pair[0])


def primera_frase(texto: str) -> str:
    """El chip de agenda solo cabe una idea. Nunca bajar a minúsculas: se comen
    IA, IVA y los nombres propios."""
    limpio = " ".join(texto.split())
    corte = limpio.find(". ")
    return limpio[:corte] if corte != -1 else limpio.rstrip(".")


def card(app: dict, today: date, column: str, oculta: bool = False) -> str:
    e = html.escape
    days = days_since(resolve_anchor_date(app), today)
    decay = min(100, round(100 * (days or 0) / CLOSE_THRESHOLD_DAYS))
    when = parse_date(app.get("next_date"))
    late = overdue(app, days)
    vencida = late or (column == "nadie" and days is not None and decay >= 80)

    if when == today:
        stamp, stamp_color = "hoy", "oklch(0.5 0.14 25)"
    elif when is not None:
        stamp = fecha_corta(when) if when > today else f"vencía {fecha_corta(when)}"
        stamp_color = "oklch(0.5 0.14 25)" if when < today else "#6f6a61"
    elif days is None:
        stamp, stamp_color = "sin fecha", "#6f6a61"
    elif days == 0:
        # mismo caso que en radar(): tocado hoy sin fecha propia no debe leerse
        # como "0 d", que parece un contador vencido en vez de "recién actualizado"
        stamp, stamp_color = "hoy", "#6f6a61"
    else:
        stamp, stamp_color = f"{days} d", "oklch(0.5 0.14 75)" if late else "#6f6a61"

    if column == "mia":
        edge = "border-top: 3px solid oklch(0.58 0.14 25);"
    elif late:
        edge = "border-left: 3px solid oklch(0.58 0.14 75);"
    else:
        edge = ""

    if column == "nadie":
        bar = "#b3ada2" if decay < 80 else "#8a857b"
        surface, name_color, name_weight = "transparent", "#4a463f", "400"
    else:
        bar = "oklch(0.58 0.14 75)" if late else "oklch(0.58 0.14 155)"
        surface, name_color, name_weight = "#ffffff", "#1c1a17", "500"

    action = app.get("next_action", "").strip()
    action_html = (
        f'<p class="accion">{e(action)}</p>' if action
        else '<p class="accion sin">Sin acción definida</p>'
    )
    aviso = (
        f'<p class="umbral">se cierra sola en {CLOSE_THRESHOLD_DAYS - days} d</p>'
        if column == "nadie" and days is not None and decay >= 80 else ""
    )

    clases = "tarjeta mas-oculta" if oculta else "tarjeta"
    oculto_attr = " hidden" if oculta else ""
    buscar = e((app.get("company", "") + " " + app.get("position", "")).lower())

    return f"""      <article class="{clases}" data-col="{e(column)}" data-tier="{e(app.get('tier', ''))}" data-buscar="{buscar}" data-vencida="{'1' if vencida else '0'}"{oculto_attr} style="background: {surface}; {edge}">
        <div class="cab">
          <h3 style="color: {name_color}; font-weight: {name_weight};"><a href="#{e(app['_file'].replace('-application.md', ''))}">{e(app.get('company', '?'))}</a></h3>
          <span class="sello" style="color: {stamp_color};">{e(stamp)}</span>
        </div>
        <p class="rol">{e(app.get('position', ''))}</p>
        {action_html}
        <div class="barra"><span style="width: {decay}%; background: {bar};"></span></div>
        <div class="pie"><span>{e(TIER_LABELS.get(app.get('tier', ''), '—'))}</span>{aviso}</div>
      </article>"""


def conversion() -> list:
    """Avance por tier — la cifra que sostiene la estrategia de targeting, hoy
    solo visible corriendo otro script.

    El corpus sale de conversion_report, no del tablero: ese script ya excluye
    las retiradas (`status: withdrawn`) de su propio `load_applications()`.
    Recontar aquí produciría una segunda cifra para la misma métrica, que es
    exactamente la desincronización que este tablero existe para evitar."""
    apps = conversion_report.load_applications()
    rows = []
    for tier, label in TIER_LABELS.items():
        of_tier = [a for a in apps if a.get("tier") == tier]
        if not of_tier:
            continue
        advanced = sum(1 for a in of_tier if a.get("advanced") == "yes")
        rows.append((label, advanced, len(of_tier)))
    return sorted(rows, key=lambda r: -r[2])


COBERTURA = {
    "✅": ("sólido", "oklch(0.5 0.14 155)"),
    "⚠️": ("parcial", "oklch(0.5 0.14 75)"),
    "❌": ("declarado como hueco", "#8a857b"),
}

STATUS_LABELS = {
    "interviewing": "En entrevista",
    "submitted": "Enviada",
    "in_progress": "En preparación",
}


def tabla(texto: str, encabezado: str) -> list:
    """Filas de una tabla markdown bajo un encabezado dado. Mismo parseo que el
    recorrido: los trackings ya escriben estas tablas con formato fijo."""
    inicio = texto.find(encabezado)
    if inicio == -1:
        return []
    filas = []
    for linea in texto[inicio + len(encabezado):].splitlines():
        if linea.startswith("##"):
            break
        if not linea.startswith("|") or linea.startswith("|---") or "|---" in linea:
            continue
        celdas = [c.strip() for c in linea.strip("|").split("|")]
        if len(celdas) >= 2:
            filas.append(celdas)
    return filas[1:]  # la primera es el encabezado de columnas


def cuerpo(app: dict) -> str:
    archivo = APPLICATIONS_DIR / app.get("_file", "")
    return archivo.read_text() if archivo.is_file() else ""


def fit_level(texto: str) -> str:
    m = re.search(r"Fit Level:\*\* (\d)/5", texto)
    return f"Fit {m.group(1)} de 5" if m else ""


def material(app: dict) -> list:
    """Enlaces al material real de la aplicación, por existencia de archivo —
    no se listan enlaces rotos. `cvs-pdf/` es hermana de `applications/` (ver
    .gitignore), no está anidada, así que su href necesita subir un nivel."""
    slug = app["_file"].replace("-application.md", "")
    piezas = [
        (APPLICATIONS_DIR / f"{slug}-prep.md", f"{slug}-prep.md", "Preparación de la sesión", "MD"),
        (REPO_ROOT / "cvs-pdf" / f"{slug}.pdf", f"../cvs-pdf/{slug}.pdf", "CV enviado", "PDF"),
        (APPLICATIONS_DIR / app["_file"], app["_file"], "Seguimiento completo", "MD"),
    ]
    return [(href, nombre, tipo) for ruta, href, nombre, tipo in piezas if ruta.is_file()]


def cuenta_regresiva(when, today: date) -> str:
    if when is None:
        return ""
    dias = (when - today).days
    if dias == 0:
        return "hoy"
    if dias < 0:
        return f"vencía hace {abs(dias)} d"
    return f"en {dias} d" if dias < 7 else fecha_corta(when)


ESTADOS = {
    "✅": ("hecho", "oklch(0.58 0.14 155)"),
    "📅": ("agendado", "oklch(0.58 0.14 25)"),
    "🔴": ("bloqueado", "oklch(0.58 0.14 25)"),
    "🔄": ("en curso", "oklch(0.58 0.14 75)"),
    "⏳": ("pendiente", "#cfc9bf"),
    "❌": ("fallido", "#8a857b"),
    "⚫": ("cerrado", "#8a857b"),
}


def recorrido(app: dict) -> list:
    """Lee la tabla de Application Status del tracking. 32 de 33 archivos usan
    el mismo encabezado y un vocabulario cerrado de emojis, así que esto es
    parseo de datos estructurados, no de prosa."""
    archivo = APPLICATIONS_DIR / app.get("_file", "")
    if not archivo.is_file():
        return []  # el tablero no debe caerse porque un tracking se renombró
    texto = archivo.read_text()
    inicio = texto.find("## Application Status")
    if inicio == -1:
        return []
    etapas = []
    for linea in texto[inicio:].splitlines():
        if linea.startswith("##") and "Application Status" not in linea:
            break
        if not linea.startswith("|") or linea.startswith("|---") or "| Field |" in linea:
            continue
        celdas = [c.strip() for c in linea.strip("|").split("|")]
        if len(celdas) < 3:
            continue
        etapa = celdas[0].replace("`", "").strip("* ")  # el nombre trae negritas y a veces código
        marca = next((m for m in ESTADOS if celdas[1].startswith(m)), None)
        detalle = celdas[1][len(marca):] if marca else celdas[1]
        detalle = detalle.replace("**", "").replace("`", "").strip(" *")  # markdown que no se renderiza
        if detalle in ("—", "-"):
            detalle = ""  # una celda vacía se escribe con raya, no es contenido
        cuando = celdas[2] if celdas[2] not in ("—", "-", "") else ""
        etapas.append((etapa, marca, detalle, cuando))
    return etapas


def detalle(app: dict, today: date, prev=None, siguiente=None) -> str:
    """La ficha de la maqueta aprobada: identidad, la jugada pendiente, el
    recorrido, la cobertura del puesto, con quién hablas, el material y lo que
    sigue sin resolverse. Todo sale del tracking; lo único que no estaba en
    ningún lado es `interviewer`."""
    e = html.escape
    slug = app["_file"].replace("-application.md", "")
    texto = cuerpo(app)
    when = parse_date(app.get("next_date"))

    chips = [TIER_LABELS.get(app.get("tier", ""), ""), STATUS_LABELS.get(app.get("status", ""), ""), fit_level(texto)]
    chips_html = "".join(
        f'<span class="chip-ficha{" vivo" if i == 1 else ""}">{e(c)}</span>'
        for i, c in enumerate(chips) if c
    )

    enviada = parse_date(app.get("date_submitted"))
    meta = []
    if enviada:
        meta.append(f"enviada {fecha_larga(enviada)}")
        meta.append(f"{(today - enviada).days} días en proceso")

    accion = app.get("next_action", "").strip()
    banda = ""
    if accion and whose_move(app) == "mia":
        cuando = cuenta_regresiva(when, today)
        banda = (
            f'    <div class="banda">\n'
            f'      <div><span class="banda-eti">Tu jugada</span><span class="banda-txt">{e(accion)}</span></div>\n'
            + (f'      <span class="banda-mono mono">{e(cuando)}</span>\n' if cuando else "")
            + "    </div>"
        )

    pasos = []
    for etapa, marca, detalle_txt, cuando in recorrido(app):
        _, color = ESTADOS.get(marca, ("", "#cfc9bf"))
        relleno = color if marca and marca != "⏳" else "transparent"
        pasos.append(
            f'        <li><span class="hito" style="background: {relleno}; border-color: {color};"></span>'
            f'<div><span class="etapa">{e(etapa)}</span>'
            + (f'<span class="cuando-hito mono">{e(cuando)}</span>' if cuando else "")
            + (f'<p class="detalle-hito">{e(detalle_txt)}</p>' if detalle_txt else "")
            + "</div></li>"
        )

    filas_cob = []
    for fila in tabla(texto, "## Alignment Assessment"):
        marca = next((m for m in COBERTURA if fila[1].startswith(m)), None)
        if not marca:
            continue
        etiqueta, color = COBERTURA[marca]
        filas_cob.append(
            f'        <div class="cob"><span>{e(fila[0])}</span>'
            f'<span class="mono" style="color: {color};">{etiqueta}</span></div>'
        )

    quien = app.get("interviewer", "").strip()
    if quien:
        partes = [x.strip() for x in quien.split(";")]
        bloque_quien = (
            '      <section class="caja">\n        <h4>Con quién hablas</h4>\n'
            f'        <p class="quien-nombre">{e(partes[0])}</p>\n'
            + (f'        <p class="quien-rol">{e(partes[1])}</p>\n' if len(partes) > 1 else "")
            + (f'        <p class="quien-nota">{e(partes[2])}</p>\n' if len(partes) > 2 else "")
            + "      </section>"
        )
    else:
        bloque_quien = ""

    enlaces = "".join(
        f'        <a class="pieza" href="{e(href)}"><span>{e(nombre)}</span>'
        f'<span class="mono">{e(tipo)}</span></a>'
        for href, nombre, tipo in material(app)
    )

    abiertas = [q.strip()[:1].upper() + q.strip()[1:]
                for q in app.get("open_questions", "").split(";") if q.strip()]
    lista = (
        '<ul class="abiertas">' + "".join(f"<li>{e(q)}</li>" for q in abiertas) + "</ul>"
        if abiertas else '<p class="ninguna">Ninguna registrada.</p>'
    )

    nav_extra = ""
    if prev or siguiente:
        partes = []
        if prev:
            partes.append(f'<a href="#{e(prev[1])}">&#8249; {e(prev[0])}</a>')
        if siguiente:
            partes.append(f'<a href="#{e(siguiente[1])}">{e(siguiente[0])} &#8250;</a>')
        nav_extra = f'<div class="prev-next mono">{"".join(partes)}</div>'

    return f"""<section class="vista ficha" id="{e(slug)}" hidden>
    <div class="nav-ficha">
      <a class="volver mono" href="#tablero">&#8592; Tablero</a>
      {nav_extra}
    </div>
    <header>
      <div>
        <h3>{e(app.get('company', '?'))}</h3>
        <p class="ficha-rol">{e(app.get('position', ''))}</p>
        <div class="chips">{chips_html}</div>
      </div>
      <div class="ficha-meta mono">{"".join(f'<span>{e(m)}</span>' for m in meta)}</div>
    </header>
{banda}
    <div class="ficha-cuerpo">
      <div class="ficha-izq">
        <h4>Recorrido</h4>
        <div class="leyenda-recorrido">
          <span><i class="lp" style="background: oklch(0.58 0.14 155); border-color: oklch(0.58 0.14 155);"></i> hecho</span>
          <span><i class="lp" style="background: transparent; border-color: #cfc9bf;"></i> pendiente</span>
          <span><i class="lp" style="background: oklch(0.58 0.14 75); border-color: oklch(0.58 0.14 75);"></i> en curso</span>
          <span><i class="lp" style="background: oklch(0.58 0.14 25); border-color: oklch(0.58 0.14 25);"></i> bloqueado</span>
        </div>
        <ol class="hitos">
{chr(10).join(pasos) or '          <li class="ninguna">Sin tabla de etapas.</li>'}
        </ol>
{'        <h4 class="sep">Cobertura del puesto</h4>' + chr(10) + '        <div class="cobertura">' + chr(10) + chr(10).join(filas_cob) + chr(10) + '        </div>' if filas_cob else ''}
      </div>
      <div class="ficha-der">
{bloque_quien}
      <section class="caja-plana">
        <h4>Material</h4>
{enlaces}
      </section>
      <section class="caja-abierta">
        <h4>Sin resolver</h4>
        {lista}
      </section>
      </div>
    </div>
</section>"""


def radar(apps: list, today: date) -> str:
    """Una sola línea de tiempo, con hoy al centro. A la izquierda lo que lleva
    callado sin fecha; a la derecha lo comprometido. Cada aplicación aparece una
    vez: si tiene fecha, vive en el futuro; si no, en su silencio acumulado.

    Lo agendado y lo que se pudre comparten escala, así que el costo de no hacer
    nada queda a la misma vista que lo que sí vas a hacer."""
    e = html.escape
    hoy_pct, futuro_dias = 58.0, 14
    izq_por_dia = hoy_pct / CLOSE_THRESHOLD_DAYS
    der_por_dia = (100 - hoy_pct) / futuro_dias

    puntos = []
    for app in apps:
        when = parse_date(app.get("next_date"))
        days = days_since(resolve_anchor_date(app), today)
        if when is not None and when >= today:
            x = min(99.0, hoy_pct + (when - today).days * der_por_dia)
            color = "oklch(0.58 0.14 25)" if when == today else "oklch(0.58 0.14 155)"
            sello = "hoy" if when == today else fecha_corta(when)
        else:
            silencio = min(CLOSE_THRESHOLD_DAYS, days or 0)
            x = max(0.5, hoy_pct - silencio * izq_por_dia)
            if app.get("follow_up") == "no_channel":
                color = "#8a857b" if silencio >= 0.8 * CLOSE_THRESHOLD_DAYS else "#b3ada2"
            elif overdue(app, days):
                color = "oklch(0.58 0.14 75)"
            else:
                color = "oklch(0.58 0.14 155)"
            sello = f"{days} d" if days is not None else "sin fecha"
            if days == 0:
                # sin esto, algo actualizado hoy mismo se lee "0 d" pegado a la
                # línea de HOY, indistinguible de un silencio real que recién empieza
                sello = "hoy"
                x = max(0.5, hoy_pct - 1.2)
        slug = app["_file"].replace("-application.md", "")
        puntos.append((x, app.get("company", "?"), sello, color, slug))

    # reparto en carriles: cada etiqueta ocupa ancho, así que baja de fila hasta caber
    puntos.sort(key=lambda p: p[0])
    carriles = []
    for x, nombre, sello, color, slug in puntos:
        ancho = (len(nombre) + len(sello) + 4) * 0.55  # % aprox sobre un ancho de ~1400 px
        for carril in carriles:
            if carril[-1][0] + carril[-1][4] + 1.5 <= x:
                carril.append((x, nombre, sello, color, ancho, slug))
                break
        else:
            carriles.append([(x, nombre, sello, color, ancho, slug)])

    filas = "\n".join(
        "".join(
            f'<div class="punto-radar" style="left: {x:.1f}%; top: {18 + i * 34}px;">'
            f'<a href="#{e(slug)}"><span class="perla" style="background: {color};"></span>'
            f'<span class="nombre">{e(nombre)}</span><span class="mono sello-radar">{e(sello)}</span></a></div>'
            for x, nombre, sello, color, _, slug in carril
        )
        for i, carril in enumerate(carriles)
    )
    alto = 18 + len(carriles) * 34 + 34
    cierre = hoy_pct - 60 * izq_por_dia

    return f"""<section class="radar-caja">
  <div class="radar-cab">
    <span class="etiqueta">Radar</span>
    <p>A la izquierda lo que lleva callado sin fecha. A la derecha lo comprometido. En la misma escala.</p>
  </div>
  <div class="radar" style="height: {alto}px;">
    <div class="zona-cierre" style="width: {cierre:.1f}%;"></div>
    <div class="marca-cierre" style="left: {cierre:.1f}%;">zona de cierre</div>
    <div class="linea-hoy" style="left: {hoy_pct}%;"></div>
    <div class="marca-hoy" style="left: {hoy_pct}%;">HOY</div>
    <div class="pie-radar izq" style="right: {100 - hoy_pct}%;">SILENCIO ACUMULADO</div>
    <div class="pie-radar der" style="left: {hoy_pct}%;">COMPROMETIDO</div>
{filas}
  </div>
</section>"""


def texto_agenda(apps: list, today: date) -> str:
    """Línea de texto para el arranque de sesión. Corta a propósito: se inyecta
    al contexto cada vez que se abre el proyecto."""
    activas = [a for a in apps if a.get("status") in ACTIVE_STATUS]
    vencidas, hoy, proximas = [], [], []
    for when, app in agenda(activas, today):
        linea = f"{app.get('company', '?')} — {primera_frase(app.get('next_action', ''))}"
        if when < today:
            vencidas.append(f"  VENCIDO {fecha_corta(when)} · {linea}")
        elif when == today:
            hoy.append(f"  HOY · {linea}")
        else:
            proximas.append(f"  {fecha_corta(when)} · {linea}")
    bloques = vencidas + hoy + proximas
    if not bloques:
        return ""
    return "Fechas comprometidas en los próximos días:\n" + "\n".join(bloques)


def build_html(apps: list, today: date) -> str:
    e = html.escape
    active = [a for a in apps if a.get("status") in ACTIVE_STATUS]
    closed = sorted(
        (a for a in apps if a.get("status") not in ACTIVE_STATUS),
        key=lambda a: a.get("last_updated", ""),
        reverse=True,
    )
    mine = [a for a in active if whose_move(a) == "mia"]

    columns = []
    for key, label, dot in COLUMNS:
        group = [a for a in active if whose_move(a) == key]
        group.sort(key=lambda a: (
            parse_date(a.get("next_date")) or date.max,
            -(days_since(resolve_anchor_date(a), today) or 0),
        ))
        cards = "\n".join(
            card(a, today, key, oculta=(i >= LIMIT_COL)) for i, a in enumerate(group)
        ) or '      <p class="vacia">Ninguna</p>'
        boton_mas = (
            f'\n      <button class="mas" type="button">Mostrar {len(group) - LIMIT_COL} más &#9662;</button>'
            if len(group) > LIMIT_COL else ""
        )
        nota = (
            '      <p class="nota">Solo portal, sin persona a quien escribirle. No piden acción, solo se apagan.</p>\n'
            if key == "nadie" else ""
        )
        columns.append(
            f'    <section class="col">\n'
            f'      <div class="titulo"><span class="punto" style="background: {dot};"></span>'
            f"<h2>{e(label)}</h2><span class=\"cuenta\" id=\"cuenta-{e(key)}\">{len(group)}</span></div>\n"
            f"{nota}{cards}{boton_mas}\n    </section>"
        )

    chips = []
    for when, app in agenda(active, today):
        urgent = when <= today
        tier_attr = e(app.get("tier", ""))
        buscar_attr = e((app.get("company", "") + " " + app.get("position", "")).lower())
        # misma fórmula de "vencida" que card(): si no se computa igual aquí,
        # "Solo vencidas" filtraría las tarjetas pero dejaría su chip de agenda
        # visible sin explicación — el mismo problema que ya se corrigió arriba
        chip_days = days_since(resolve_anchor_date(app), today)
        chip_decay = min(100, round(100 * (chip_days or 0) / CLOSE_THRESHOLD_DAYS))
        chip_vencida = overdue(app, chip_days) or (
            whose_move(app) == "nadie" and chip_days is not None and chip_decay >= 80
        )
        chips.append(
            f'    <div class="chip{" hoy" if urgent else ""}" data-tier="{tier_attr}" '
            f'data-buscar="{buscar_attr}" data-vencida="{"1" if chip_vencida else "0"}">'
            f'<span class="cuando">{e("HOY" if when == today else fecha_corta(when).upper())}</span>'
            f"<span>{e(app.get('company', '?'))}: {e(primera_frase(app.get('next_action', '')))}</span></div>"
        )
    agenda_html = (
        f'<div class="agenda"><span class="etiqueta">Próximos días '
        f'<span id="agenda-cuenta" class="mono">{len(chips)}</span></span><div class="chips">\n'
        + "\n".join(chips)
        + "\n</div></div>"
        if chips else ""
    )

    leyenda_html = (
        '<div class="leyenda">'
        '<span><i class="bm"></i> tu jugada</span>'
        '<span><i class="pt" style="background: oklch(0.58 0.14 155);"></i> en curso, dentro de ventana</span>'
        '<span><i class="pt" style="background: oklch(0.58 0.14 75);"></i> pasó la ventana de espera</span>'
        '<span><i class="pt" style="background: #b3ada2;"></i> sin canal de seguimiento</span>'
        '</div>'
    )

    tiers_presentes = [k for k in TIER_LABELS if any(a.get("tier") == k for a in active)]
    chips_tier_html = "".join(
        f'<span class="chip-filtro" data-tier="{e(k)}">{e(TIER_LABELS[k])}</span>' for k in tiers_presentes
    )
    barra_filtro_html = (
        '<div class="barra-filtro">'
        '<input id="buscar-tablero" class="buscar" type="text" placeholder="Buscar empresa o rol…">'
        f'{chips_tier_html}'
        '<span id="chip-vencidas" class="chip-filtro vencidas">Solo vencidas</span>'
        '</div>'
    )

    cerca_cierre = [
        a for a in active if whose_move(a) == "nadie"
        and (days_since(resolve_anchor_date(a), today) or 0) >= 0.8 * CLOSE_THRESHOLD_DAYS
    ]
    alerta_html = ""
    if cerca_cierre:
        nombres = ", ".join(e(a.get("company", "?")) for a in cerca_cierre[:3])
        extra = f" y {len(cerca_cierre) - 3} más" if len(cerca_cierre) > 3 else ""
        plural = "aplicaciones" if len(cerca_cierre) != 1 else "aplicación"
        verbo = "cruzan" if len(cerca_cierre) != 1 else "cruza"
        alerta_html = (
            f'<div class="alerta"><b>{len(cerca_cierre)} {plural}</b> {verbo} '
            f'el umbral de cierre (90 días) esta semana — {nombres}{extra}</div>'
        )

    generado_str = datetime.now().strftime("%H:%M")

    barras = "\n".join(
        f'      <div class="conv"><div class="conv-cab"><span>{e(label)}</span>'
        f'<span class="mono">{adv} de {total}</span></div>'
        f'<div class="barra"><span style="width: {max(1, round(100 * adv / total))}%; '
        f'background: {"oklch(0.58 0.14 155)" if adv else "#b3ada2"};"></span></div></div>'
        for label, adv, total in conversion()
    )

    filas = "\n".join(
        f'      <tr data-buscar="{e((a.get("company", "?") + " " + a.get("position", "")).lower())}" '
        f'data-desenlace="{e(a.get("status", ""))}" data-empresa="{e(a.get("company", "?").lower())}" '
        f'data-fecha="{e(a.get("last_updated", ""))}">'
        f'<td><a href="{e(a["_file"])}">{e(a.get("company", "?"))}</a></td>'
        f'<td>{e(a.get("position", ""))}</td>'
        f'<td><span class="badge {BADGE_CLASS.get(a.get("status", ""), "silencio")}">'
        f'{e(CLOSED_LABELS.get(a.get("status", ""), a.get("status", "")))}</span></td>'
        f'<td>{e(TIER_LABELS.get(a.get("tier", ""), "—"))}</td>'
        f'<td>{e("sí" if a.get("advanced") == "yes" else "no")}</td>'
        f'<td class="mono">{e(a.get("last_updated", ""))}</td></tr>'
        for a in closed
    )

    resumen_counts = {}
    for a in closed:
        resumen_counts[a.get("status", "")] = resumen_counts.get(a.get("status", ""), 0) + 1
    resumen_partes = []
    for key in ("rejected", "closed_no_feedback", "withdrawn", "offer"):
        if resumen_counts.get(key):
            resumen_partes.append(f'<span><b>{resumen_counts[key]}</b> {e(CLOSED_LABELS[key].lower())}</span>')
    if closed:
        avanzaron = sum(1 for a in closed if a.get("advanced") == "yes")
        pct = round(100 * avanzaron / len(closed))
        resumen_partes.append(f'<span><b>{avanzaron} de {len(closed)}</b> llegaron a entrevista o prueba ({pct}%)</span>')
    resumen_historico_html = f'<div class="resumen-historico">{"".join(resumen_partes)}</div>' if resumen_partes else ""

    desenlaces_presentes = [k for k in CLOSED_LABELS if any(a.get("status") == k for a in closed)]
    chips_desenlace_html = "".join(
        f'<span class="chip-filtro" data-desenlace="{e(k)}">{e(CLOSED_LABELS[k])}</span>' for k in desenlaces_presentes
    )
    barra_filtro_historico_html = (
        '<div class="barra-filtro">'
        '<input id="buscar-historico" class="buscar" type="text" placeholder="Buscar empresa o rol…">'
        f'{chips_desenlace_html}'
        '</div>'
        if closed else ""
    )

    activas_ordenadas = sorted(active, key=lambda a: a.get("company", ""))
    fichas_html = []
    for i, a in enumerate(activas_ordenadas):
        prev = (
            (activas_ordenadas[i - 1].get("company", "?"), activas_ordenadas[i - 1]["_file"].replace("-application.md", ""))
            if i > 0 else None
        )
        siguiente = (
            (activas_ordenadas[i + 1].get("company", "?"), activas_ordenadas[i + 1]["_file"].replace("-application.md", ""))
            if i < len(activas_ordenadas) - 1 else None
        )
        fichas_html.append(detalle(a, today, prev, siguiente))
    fichas_html = "\n".join(fichas_html)

    fichas_js = json.dumps(
        sorted(a["_file"].replace("-application.md", "") for a in active),
        ensure_ascii=False,
    )

    titular = (
        f"{len(mine)} cosas esperan algo de ti" if len(mine) != 1
        else "Una cosa espera algo de ti"
    )

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pipeline de postulaciones</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,500&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
  :root {{
    --papel: #faf8f4; --sup: #fff; --tinta: #1c1a17; --apagado: #6f6a61;
    --tenue: #7d766b; --linea: #e6e1d9; --hueso: #f0ece5;
    --mia: oklch(0.58 0.14 25); --ojo: oklch(0.58 0.14 75); --marcha: oklch(0.58 0.14 155);
    --serif: Newsreader, Georgia, "Times New Roman", serif;
    --sans: "IBM Plex Sans", -apple-system, BlinkMacSystemFont, sans-serif;
    --mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, monospace;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: 40px 44px 44px; background: var(--papel); color: var(--tinta);
          font: 14px/1.5 var(--sans); }}
  a {{ color: inherit; }}
  .mono {{ font-family: var(--mono); }}

  .vistas {{ display: flex; gap: 4px; margin-bottom: 18px; }}
  .vistas a {{ padding: 7px 14px; border-radius: 7px; font-size: 13px; text-decoration: none;
               color: var(--apagado); border: 1px solid transparent; }}
  .vistas a:hover {{ background: var(--hueso); }}
  .vistas a.activa {{ background: var(--sup); border-color: var(--linea); color: var(--tinta); }}
  .vista[hidden] {{ display: none; }}

  .encabezado {{ display: flex; justify-content: space-between; align-items: flex-end;
                 gap: 24px; padding-bottom: 20px; border-bottom: 1px solid var(--linea); }}
  .fecha {{ margin: 0 0 4px; font-family: var(--mono); font-size: 11px; letter-spacing: .12em;
            text-transform: uppercase; color: var(--apagado); }}
  h1 {{ margin: 0 0 14px; font-family: var(--serif); font-weight: 500; font-size: 34px; letter-spacing: -.01em; }}
  .cifras {{ display: flex; gap: 28px; font-family: var(--mono); font-size: 12px; color: var(--apagado); }}
  .cifras div {{ display: flex; flex-direction: column; align-items: flex-end; gap: 2px; }}
  .cifras b {{ font-size: 22px; font-weight: 400; color: var(--tinta); }}

  .agenda {{ display: flex; align-items: center; gap: 14px; padding: 16px 0 22px; }}
  .etiqueta {{ font-family: var(--mono); font-size: 11px; letter-spacing: .12em;
               text-transform: uppercase; color: var(--apagado); white-space: nowrap; }}
  .chips {{ display: flex; gap: 10px; flex-wrap: wrap; }}
  .chip {{ display: flex; align-items: baseline; gap: 8px; background: var(--sup);
           border: 1px solid var(--linea); border-radius: 7px; padding: 8px 14px; font-size: 14px; }}
  .chip.hoy {{ background: var(--mia); border-color: var(--mia); color: #fdf6f4; }}
  .cuando {{ font-family: var(--mono); font-size: 12px; color: var(--apagado); }}
  .chip.hoy .cuando {{ color: #fdf6f4; opacity: .85; }}

  .tablero {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 22px; }}
  .col {{ display: flex; flex-direction: column; gap: 12px; }}
  .titulo {{ display: flex; align-items: baseline; gap: 8px; }}
  .punto {{ width: 7px; height: 7px; border-radius: 50%; }}
  .titulo h2 {{ margin: 0; font-size: 13px; font-weight: 600; letter-spacing: .02em; }}
  .cuenta {{ font-family: var(--mono); font-size: 12px; color: var(--apagado); }}
  .nota {{ margin: -4px 0 0; font-size: 12px; line-height: 1.5; color: var(--tenue); text-wrap: pretty; }}

  .tarjeta {{ border: 1px solid var(--linea); border-radius: 10px; padding: 16px 18px;
              display: flex; flex-direction: column; gap: 8px; }}
  .cab {{ display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }}
  .cab h3 {{ margin: 0; font-family: var(--serif); font-size: 21px; line-height: 1.15; }}
  .cab a {{ text-decoration: none; }}
  .cab a:hover {{ text-decoration: underline; }}
  .sello {{ font-family: var(--mono); font-size: 12px; white-space: nowrap; }}
  .rol {{ margin: -4px 0 0; font-size: 13px; color: var(--apagado); }}
  .accion {{ margin: 0; font-size: 14px; line-height: 1.45; }}
  .accion.sin {{ color: var(--ojo); font-style: italic; }}
  .barra {{ height: 3px; border-radius: 2px; background: var(--hueso); overflow: hidden; }}
  .barra span {{ display: block; height: 100%; }}
  .pie {{ display: flex; justify-content: space-between; align-items: baseline; gap: 8px;
          font-size: 11px; letter-spacing: .04em; text-transform: uppercase; color: var(--apagado); }}
  .umbral {{ margin: 0; font-family: var(--mono); font-size: 11px; text-transform: none;
             letter-spacing: 0; color: var(--tenue); }}
  .vacia {{ color: var(--apagado); font-style: italic; }}

  .conversion {{ display: flex; align-items: center; gap: 28px; margin-top: 26px;
                 padding-top: 18px; border-top: 1px solid var(--linea); }}
  .conversion .barras {{ display: flex; gap: 32px; flex-grow: 1; flex-wrap: wrap; }}
  .conv {{ display: flex; flex-direction: column; gap: 5px; flex-grow: 1; min-width: 140px; }}
  .conv-cab {{ display: flex; justify-content: space-between; font-size: 13px; }}
  .conv-cab .mono {{ color: var(--apagado); }}
  .conv .barra {{ height: 5px; border-radius: 3px; }}

  .radar-caja {{ margin-top: 4px; }}
  .radar-cab {{ display: flex; align-items: baseline; gap: 16px; margin-bottom: 10px; }}
  .radar-cab p {{ margin: 0; font-size: 13px; color: var(--apagado); }}
  .radar {{ position: relative; background: var(--sup); border: 1px solid var(--linea);
            border-radius: 12px; overflow: hidden; }}
  .zona-cierre {{ position: absolute; left: 0; top: 0; bottom: 0; background: #f4efe7; }}
  .marca-cierre {{ position: absolute; top: 10px; transform: translateX(-100%); padding-right: 10px;
                   font-family: var(--mono); font-size: 11px; color: var(--tenue); }}
  .linea-hoy {{ position: absolute; top: 0; bottom: 0; width: 2px; background: var(--mia); }}
  .marca-hoy {{ position: absolute; top: 8px; padding-left: 10px; font-family: var(--mono);
                font-size: 11px; letter-spacing: .1em; color: var(--mia); }}
  .pie-radar {{ position: absolute; bottom: 8px; font-family: var(--mono); font-size: 11px;
                letter-spacing: .1em; color: #c4bfb5; }}
  .pie-radar.izq {{ left: 0; text-align: center; }}
  .pie-radar.der {{ right: 0; text-align: center; }}
  .punto-radar {{ position: absolute; display: flex; align-items: center; gap: 8px; white-space: nowrap; }}
  .perla {{ width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }}
  .nombre {{ font-size: 13px; }}
  .sello-radar {{ font-size: 11px; color: var(--tenue); }}

  .volver {{ display: inline-block; font-size: 12px; color: var(--apagado);
             text-decoration: none; margin-bottom: 18px; }}
  .volver:hover {{ color: var(--tinta); }}
  .ficha header {{ display: flex; justify-content: space-between; align-items: flex-start;
                   gap: 16px; padding-bottom: 16px; border-bottom: 1px solid var(--hueso); }}
  .ficha h3 {{ margin: 0; font-family: var(--serif); font-size: 30px; font-weight: 500;
               line-height: 1.05; letter-spacing: -.01em; }}
  .ficha-rol {{ margin: 2px 0 0; font-size: 14px; color: #4a463f; }}
  .chips {{ display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; }}
  .chip-ficha {{ font-size: 11px; letter-spacing: .04em; text-transform: uppercase;
                 color: var(--apagado); border: 1px solid var(--linea); border-radius: 4px; padding: 3px 8px; }}
  .chip-ficha.vivo {{ color: oklch(0.5 0.14 155); border-color: oklch(0.85 0.05 155); }}
  .ficha-meta {{ display: flex; flex-direction: column; align-items: flex-end; gap: 5px;
                 font-size: 12px; color: var(--apagado); white-space: nowrap; }}

  .banda {{ display: flex; justify-content: space-between; align-items: center; gap: 20px;
            background: var(--mia); color: #fdf6f4; border-radius: 10px; padding: 16px 20px; margin: 16px 0 4px; }}
  .banda-eti {{ display: block; font-family: var(--mono); font-size: 11px; letter-spacing: .12em;
                text-transform: uppercase; opacity: .8; margin-bottom: 3px; }}
  .banda-txt {{ font-size: 17px; font-weight: 500; line-height: 1.3; }}
  .banda-mono {{ font-size: 13px; opacity: .9; white-space: nowrap; }}

  .ficha-cuerpo {{ display: grid; grid-template-columns: 1.5fr 1fr; gap: 26px; padding-top: 16px; }}
  .ficha-der {{ display: flex; flex-direction: column; gap: 18px; }}
  .sep {{ margin-top: 22px; }}
  .cobertura {{ border: 1px solid var(--linea); border-radius: 10px; overflow: hidden; }}
  .cob {{ display: flex; justify-content: space-between; align-items: center; gap: 12px;
          padding: 11px 16px; font-size: 14px; border-bottom: 1px solid var(--hueso); }}
  .cob:last-child {{ border-bottom: none; }}
  .cob .mono {{ font-size: 12px; white-space: nowrap; }}
  .caja {{ border: 1px solid var(--linea); border-radius: 10px; padding: 16px 18px; }}
  .quien-nombre {{ margin: 0; font-family: var(--serif); font-size: 20px; font-weight: 500; }}
  .quien-rol {{ margin: 1px 0 0; font-size: 13px; color: var(--apagado); }}
  .quien-nota {{ margin: 9px 0 0; font-size: 13px; line-height: 1.5; color: #4a463f; }}
  .caja-plana {{ display: flex; flex-direction: column; }}
  .pieza {{ display: flex; justify-content: space-between; align-items: center; gap: 10px;
            border: 1px solid var(--linea); border-radius: 8px; padding: 10px 14px;
            margin-bottom: 8px; font-size: 14px; text-decoration: none; }}
  .pieza:hover {{ background: var(--hueso); }}
  .pieza .mono {{ font-size: 11px; color: var(--apagado); }}
  .caja-abierta {{ border: 1px dashed #d8d2c8; border-radius: 10px; padding: 16px 18px; }}
  .ficha h4 {{ margin: 0 0 10px; font-size: 11px; letter-spacing: .06em; text-transform: uppercase;
               color: var(--apagado); font-weight: 500; }}
  .hitos {{ list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }}
  .hitos li {{ display: flex; gap: 12px; align-items: flex-start; }}
  .hito {{ width: 9px; height: 9px; border-radius: 50%; border: 1px solid; margin-top: 5px; flex-shrink: 0; }}
  .etapa {{ font-size: 14px; }}
  .cuando-hito {{ font-size: 11px; color: var(--apagado); margin-left: 8px; }}
  .detalle-hito {{ margin: 2px 0 0; font-size: 13px; line-height: 1.45; color: var(--apagado); }}
  .abiertas {{ margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 7px;
               font-size: 13px; line-height: 1.45; }}
  .ninguna {{ margin: 0; font-size: 13px; color: var(--tenue); font-style: italic; }}

  table {{ border-collapse: collapse; width: 100%; margin-top: 14px; }}
  th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--linea); }}
  th {{ color: var(--apagado); font-weight: 500; font-size: 11px; letter-spacing: .06em;
        text-transform: uppercase; }}
  td {{ font-size: 14px; }}
{EXTRA_STYLE}</style>
</head>
<body>
<div id="cabecera">
<nav class="vistas">
  <a href="#tablero">Tablero</a><a href="#radar">Radar</a><a href="#historico">Histórico <span class="mono">{len(closed)}</span></a>
</nav>
<header class="encabezado">
  <div>
    <p class="fecha">{DIAS[today.weekday()]} {today.day} de {MESES[today.month - 1]} <span class="generado">· generado {generado_str}</span></p>
  </div>
  <div class="cifras">
    <div><b>{len(active)}</b><span>activas</span></div>
    <div><b>{sum(1 for a in active if a.get('status') == 'interviewing')}</b><span>en entrevista</span></div>
    <div><b>{len(closed)}</b><span>cerradas</span></div>
  </div>
</header>
</div>
<section class="vista" id="tablero">
<h1>{e(titular)}</h1>
{leyenda_html}
{barra_filtro_html}
{alerta_html}
{agenda_html}
<main class="tablero">
{chr(10).join(columns)}
  <p id="vacio-tablero" class="vacio-filtro" hidden>Sin resultados para el filtro actual.</p>
</main>
<section class="conversion">
  <span class="etiqueta">Conversión real</span>
  <div class="barras">
{barras}
  </div>
</section>
</section>
<section class="vista" id="radar" hidden>
{radar(active, today)}
</section>
{fichas_html}
<section class="vista" id="historico" hidden>
{resumen_historico_html}
{barra_filtro_historico_html}
  <table id="tabla-historico">
    <thead><tr><th class="ordenable" data-ordenar="empresa">Empresa <span class="flecha">&#9662;</span></th><th>Puesto</th><th>Desenlace</th><th>Tier</th><th>¿Avanzó?</th><th class="ordenable" data-ordenar="fecha">Última act. <span class="flecha">&#9662;</span></th></tr></thead>
    <tbody>
{filas}
      <tr id="vacio-historico" hidden><td colspan="6" class="vacio-filtro">Sin resultados para el filtro actual.</td></tr>
    </tbody>
  </table>
</section>
<script>
  // Tres vistas generales más una ficha por aplicación. Dentro de una ficha se
  // oculta la cabecera: la migaja de vuelta es toda la navegación que hace falta.
  var VISTAS = ["tablero", "radar", "historico"];
  var FICHAS = {fichas_js};
  function mostrar() {{
    var destino = location.hash.slice(1);
    var activa = VISTAS.indexOf(destino) !== -1 || FICHAS.indexOf(destino) !== -1 ? destino : "tablero";
    VISTAS.concat(FICHAS).forEach(function (v) {{
      var el = document.getElementById(v);
      if (el) el.hidden = v !== activa;
    }});
    var enFicha = FICHAS.indexOf(activa) !== -1;
    document.getElementById("cabecera").hidden = enFicha;
    document.querySelectorAll(".vistas a").forEach(function (a) {{
      a.classList.toggle("activa", a.getAttribute("href") === "#" + activa);
    }});
    window.scrollTo(0, 0);
  }}
  window.addEventListener("hashchange", mostrar);
  mostrar();
{EXTRA_SCRIPT}</script>
</body>
</html>
"""


def main(argv: list) -> int:
    if "--demo" in argv:
        demo()
        return 0
    today = date.today()
    if "--agenda" in argv:
        print(texto_agenda(load_applications(), today))
        return 0
    OUTPUT.write_text(build_html(load_applications(), today))
    print(f"Tablero generado: {OUTPUT}")
    if "--open" in argv:
        subprocess.run(["open", str(OUTPUT)], check=False)
    return 0


def demo() -> None:
    """ponytail self-check: valida el reparto por columnas, la agenda y el escapado."""
    today = date(2026, 9, 3)

    # una fecha comprometida es jugada tuya, aunque estés "esperando respuesta"
    assert whose_move({"follow_up": "waiting", "next_date": "2026-09-11"}) == "mia"
    # sin fecha, esperar respuesta es jugada de ellos
    assert whose_move({"follow_up": "waiting"}) == "suya"
    # una decisión propia sin enviar también es tuya
    assert whose_move({"follow_up": "n/a", "status": "in_progress"}) == "mia"
    assert whose_move({"follow_up": "pending_contact"}) == "mia"
    # sin canal gana sobre todo lo demás: no hay a quién escribirle
    assert whose_move({"follow_up": "no_channel", "next_date": "2026-09-11"}) == "nadie"
    # una fecha ilegible no puede ascender la tarjeta a jugada tuya
    assert whose_move({"follow_up": "waiting", "next_date": "pronto"}) == "suya"

    assert overdue({"follow_up": "waiting"}, WAITING_WINDOW_DAYS + 1) is True
    assert overdue({"follow_up": "waiting"}, WAITING_WINDOW_DAYS) is False
    assert overdue({"follow_up": "no_channel"}, 400) is False

    apps = [
        {
            "_file": "a-application.md", "company": "Activa & Co", "position": "Tech Lead",
            "status": "interviewing", "tier": "liderazgo", "follow_up": "waiting",
            "advanced": "yes", "last_updated": "2026-09-01",
            "next_action": "Entrevista de fit.", "next_date": "2026-09-03",
        },
        {
            "_file": "b-application.md", "company": "Portal SA", "position": "Android",
            "status": "submitted", "tier": "android_ic", "follow_up": "no_channel",
            "advanced": "no", "date_submitted": "2026-06-10",
        },
        {
            "_file": "c-application.md", "company": "Cerrada SA", "position": "Android",
            "status": "rejected", "tier": "android_ic", "follow_up": "n/a",
            "advanced": "no", "last_updated": "2026-08-01",
        },
    ]
    assert primera_frase("Entrevista con IA. Después registrar.") == "Entrevista con IA"
    assert primera_frase("Sin punto final") == "Sin punto final"
    assert primera_frase("Una sola frase.") == "Una sola frase"

    # la agenda solo toma lo comprometido dentro de la ventana
    assert [a[1]["company"] for a in agenda(apps, today)] == ["Activa & Co"]

    linea = texto_agenda(apps, today)
    assert "HOY · Activa & Co — Entrevista de fit" in linea
    assert "Portal SA" not in linea, "sin fecha comprometida no entra a la agenda"
    assert texto_agenda([], today) == "", "sin fechas no se imprime encabezado suelto"

    # el radar reparte en carriles y nunca deja dos etiquetas encimadas
    marca = radar(apps[:2], today)
    assert marca.count("punto-radar") == 2
    assert "HOY" in marca and "zona de cierre" in marca
    # cada punto del radar enlaza a su ficha
    assert '<a href="#a">' in marca and '<a href="#b">' in marca

    # actualizado hoy sin fecha propia se lee "hoy", no "0 d" pegado a la línea de HOY
    app_hoy = {"_file": "hoy-application.md", "company": "Hoy Co", "follow_up": "waiting",
               "last_updated": today.isoformat()}
    marca_hoy = radar([app_hoy], today)
    assert ">hoy<" in marca_hoy and "0 d" not in marca_hoy

    # card() trae los atributos que el filtro/buscador del tablero necesita
    tarjeta = card({"_file": "x-application.md", "company": "X", "position": "Y", "tier": "liderazgo",
                     "follow_up": "waiting"}, today, "suya")
    assert 'data-tier="liderazgo"' in tarjeta and 'data-buscar="x y"' in tarjeta and 'data-col="suya"' in tarjeta
    # mismo fix del radar aplicado a la tarjeta: tocado hoy sin fecha propia dice "hoy", no "0 d"
    tarjeta_hoy = card({"_file": "x-application.md", "company": "X", "position": "Y",
                        "follow_up": "waiting", "last_updated": today.isoformat()}, today, "suya")
    assert ">hoy<" in tarjeta_hoy and "0 d" not in tarjeta_hoy
    tarjeta_oculta = card({"_file": "x-application.md", "company": "X", "position": "Y", "tier": "liderazgo",
                            "follow_up": "waiting"}, today, "suya", oculta=True)
    assert "mas-oculta" in tarjeta_oculta and " hidden" in tarjeta_oculta

    # un chip de agenda puede ser vencido igual que una tarjeta (fecha comprometida
    # + silencio previo por encima de la ventana): "Solo vencidas" debe alcanzarlo
    app_vencida_con_fecha = {
        "_file": "vencida-application.md", "company": "Vencida Co", "position": "Rol",
        "tier": "liderazgo", "status": "interviewing", "follow_up": "waiting",
        "last_updated": (today - timedelta(days=WAITING_WINDOW_DAYS + 5)).isoformat(),
        "next_date": today.isoformat(), "next_action": "Acción",
    }
    pagina_vencida = build_html([app_vencida_con_fecha], today)
    assert 'class="chip hoy" data-tier="liderazgo" data-buscar="vencida co rol" data-vencida="1"' in pagina_vencida

    # el recorrido sale de la tabla real del tracking, no de prosa — probado
    # contra un fixture temporal, nunca contra datos reales del usuario
    import tempfile
    global APPLICATIONS_DIR
    apps_dir_original = APPLICATIONS_DIR
    with tempfile.TemporaryDirectory() as tmp:
        APPLICATIONS_DIR = Path(tmp)
        (APPLICATIONS_DIR / "fixture-application.md").write_text(
            "---\ntype: application_tracking\n---\n\n"
            "## Application Status\n\n"
            "| Field | Status | Date |\n"
            "|-------|--------|------|\n"
            '| **Form Submission** | ✅ Enviada | 2026-08-01 |\n'
            '| **Revisión `cv-reviewer`** | ✅ "Go con cambios" | 2026-08-02 |\n'
            "| **Technical Interview** | ⏳ | |\n",
            encoding="utf-8",
        )
        pasos = recorrido({"_file": "fixture-application.md"})
        assert pasos, "el fixture sí tiene tabla de Application Status"
        etapas = [p[0] for p in pasos]
        assert "Form Submission" in etapas and "Technical Interview" in etapas
        assert "Revisión cv-reviewer" in etapas, "las comillas de código se limpian completas"
        assert all(p[1] in ESTADOS or p[1] is None for p in pasos)
        # una etapa sin fecha no debe inventarse una
        assert any(p[3] == "" for p in pasos)
        # el texto de la tabla llega en markdown y aquí no se renderiza
        assert not any("**" in p[2] for p in pasos)
        # un tracking inexistente devuelve vacío en vez de tumbar el tablero
        assert recorrido({"_file": "no-existe-application.md"}) == []
    APPLICATIONS_DIR = apps_dir_original

    # las preguntas abiertas se parten por punto y coma y suben a mayúscula
    ficha = detalle({"_file": "no-existe-application.md", "company": "X", "position": "Y",
                     "open_questions": "modalidad; a quién reporta"}, today)
    assert "<li>Modalidad</li>" in ficha and "<li>A quién reporta</li>" in ficha
    assert "Sin tabla de etapas" in ficha
    assert "Con quién hablas" not in ficha, "sin interviewer, el bloque no se dibuja"

    # la banda de acción solo aparece cuando la jugada es tuya
    base = {"_file": "no-existe-application.md", "company": "X", "position": "Y",
            "tier": "liderazgo", "status": "interviewing", "next_action": "Entrevista hoy",
            "next_date": today.isoformat(), "date_submitted": "2026-08-26",
            "interviewer": "A. Ejemplo; Engineering Manager; No es reclutamiento"}
    full = detalle(base, today)
    assert "Tu jugada" in full and "Entrevista hoy" in full and ">hoy<" in full
    assert "A. Ejemplo" in full and "Engineering Manager" in full
    assert "enviada 26 ago" in full and "8 días en proceso" in full
    sin_fecha = dict(base); sin_fecha.pop("next_date"); sin_fecha["follow_up"] = "waiting"
    assert "Tu jugada" not in detalle(sin_fecha, today), "esperando respuesta no lleva banda"

    # navegación anterior/siguiente entre fichas, solo cuando hay vecinas
    generica = {"_file": "no-existe-application.md", "company": "X", "position": "Y"}
    ficha_nav = detalle(generica, today, prev=("Empresa Anterior", "empresa-anterior"),
                         siguiente=("Empresa Siguiente", "empresa-siguiente"))
    assert '<a href="#empresa-anterior">' in ficha_nav and "Empresa Anterior" in ficha_nav
    assert '<a href="#empresa-siguiente">' in ficha_nav and "Empresa Siguiente" in ficha_nav
    assert "prev-next" not in detalle(generica, today), "sin fichas vecinas no se dibuja el bloque de navegación"

    assert cuenta_regresiva(date(2026, 9, 5), today) == "en 2 d"
    assert cuenta_regresiva(date(2026, 9, 1), today) == "vencía hace 2 d"
    assert cuenta_regresiva(None, today) == ""
    assert fit_level("**Fit Level:** 4/5 — BUENO") == "Fit 4 de 5"
    assert fit_level("sin dato") == ""

    page = build_html(apps, today)
    assert "Una cosa espera algo de ti" in page, "el titular concuerda en singular"
    assert "Activa &amp; Co" in page, "el nombre de la empresa debe ir escapado"
    assert "HOY" in page and "Cerrada SA" in page and "Rechazada" in page
    # "Próximos días" debe responder al mismo filtro de tier/texto que las tarjetas
    assert 'class="chip hoy" data-tier="liderazgo" data-buscar="activa &amp; co tech lead" data-vencida="0"' in page
    # .tarjeta y .chip declaran su propio display: sin este selector [hidden] no se ve,
    # porque una regla de autor con igual especificidad siempre le gana a la del navegador
    assert ".tarjeta[hidden]" in page and ".chip[hidden]" in page
    # "Próximos días" declara su propio conteo: no debe leerse como el mismo
    # número que el titular, que cuenta solo la columna "Tu jugada"
    assert '<span id="agenda-cuenta" class="mono">1</span>' in page
    # tres vistas generales más una por aplicación, y solo el tablero visible
    # antes de que corra el script
    for vid in ("tablero", "radar", "historico"):
        assert f'id="{vid}"' in page
    assert 'id="detalle"' not in page, "el índice apilado de fichas ya no existe"
    assert 'id="tablero" hidden' not in page and 'id="radar" hidden' in page
    # 3 generales + 1 ficha por activa
    assert page.count('<section class="vista') == 3 + len(
        [a for a in apps if a.get("status") in ACTIVE_STATUS]
    )
    assert '"a-application"' not in page and '"a"' in page.split("var FICHAS = ")[1][:60]
    assert 'id="cabecera"' in page
    # 85 días sin canal ya avisa que se cierra sola
    assert "se cierra sola en" in page
    # la conversión se lee del corpus real de conversion_report, no de estas filas
    assert "Conversión real" in page
    # leyenda, buscador/filtros y foco de teclado visible
    assert "leyenda" in page and "buscar-tablero" in page and "buscar-historico" in page
    assert "focus-visible" in page
    # el desenlace de una cerrada se pinta como badge de color, no texto plano
    assert 'class="badge rechazo"' in page
    # Portal SA lleva 85 días sin canal (>=80% de 90) y debe activar la alerta agregada
    assert "1 aplicación" in page and "cruza el umbral de cierre" in page
    # el conteo de cada columna necesita id propio para poder recalcularse al filtrar
    assert 'id="cuenta-mia"' in page and 'id="cuenta-suya"' in page and 'id="cuenta-nadie"' in page
    # una activa sin acción tiene que delatarse, no pasar en silencio
    apps[1]["next_action"] = ""
    assert "Sin acción definida" in build_html(apps, today)
    print("demo ok")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
