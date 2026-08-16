# Estado — groundwork

> Punto de retomada. Se sobrescribe cada sesión, no se acumula. El historial lo tiene git.
> Última actualización: 2026-08-15

> **Este archivo se publica.** El repo es público (o va a serlo): nada de nombres de
> empresas reales, rutas locales ni datos del repo privado del que salió el proyecto.
> Las lecciones duraderas y lo que sí es sensible viven en memoria, no aquí.

## Estado actual

Spin-off open-source de un pipeline privado de CV/aplicaciones. MIT, sin remoto configurado todavía.

Esta sesión hizo una **pasada de verificación funcional** — correr el flujo end-to-end como usuario nuevo, no solo los self-checks — arregló lo que se rompía, y reescribió la historia de git a un único commit limpio (ver "Fugas de datos personales").

### Cómo se prueba esto

Dos niveles, ambos sin framework ni dependencias de test:

- **Unitario**: `python3 scripts/<script>.py --demo` en cada uno de los 5 scripts. Asserts sobre parsers y cálculo.
- **Integración**: `python3 scripts/smoke_test.py`. Copia solo los archivos versionados a un tmpdir (lo que recibe quien haga fork), corre el Quickstart del README literal, genera CV → PDF y pasa los cuatro checks. Verifica que las 5 secciones del template lleguen al PDF y que las notas internas no.

El smoke test existe porque los tres bugs de esta sesión eran de integración: los `--demo` pasaban todos mientras el generador truncaba CVs. Se verificó que falla al reintroducir el bug del `---`.

### Bugs encontrados y corregidos (cada uno con su regresión en el `--demo` del script)

1. **`generate_cv_pdf.py` truncaba el CV en silencio.** `strip_frontmatter_and_notes()` corta en el *primer* `---`, que es el separador de notas internas — pero un `---` usado como regla horizontal (lo que emite cualquier LLM al que le pidas un CV en markdown) se llevaba el resto del documento con exit 0 y cero advertencias. Medido contra un CV legacy real: 106 líneas → 35, 4 empleos → 1. Ahora avisa a stderr cuando lo descartado trae encabezados (las notas internas nunca los llevan — solo etiquetas `**Nota**:` —, así que el `#` distingue el error del uso legítimo).
2. **`followup_check.py` crasheaba con `KeyError: 'company'`** ante un tracking a medio llenar, a media impresión del reporte. Mismo patrón latente en `conversion_report.py`. Resuelto con un helper `label()` y `.get()`.
3. **`ats_check.check_garbled()` no veía el glifo roto que produce el propio generador.** Un carácter fuera de WinAnsi no sale como `�` ni `(cid:N)`: reportlab lo sustituye por `\x7f` o por `■` según el caso. El check daba luz verde a un PDF con cajas negras visibles.

### Fugas de datos personales corregidas

Tres strings del repo privado sobrevivieron a la auditoría del commit inicial:

- `scripts/ats_check.py` — un teléfono real verbatim en un comentario.
- `scripts/followup_check.py` — el nombre de una empresa real y el detalle de cómo se le aplicó, en un docstring.
- `.claude/ESTADO.md` — la ruta local del repo privado y dos nombres de archivo `cv_for_*.md` con empresas reales.

Los tres corregidos, y la historia de git **reescrita a un único commit limpio** (`git checkout --orphan`) porque los dos commits anteriores los contenían. No había remoto, así que no quedó copia en ningún lado.

Lección de método: la auditoría del commit inicial revisó contenido de documentos, no **comentarios y docstrings de código** — que es justo donde se cuela el detalle real usado como ejemplo al portar un script. Un `grep` de nombre/email/teléfono/empresas debe correr sobre el repo entero, sin excluir `.py`, y el `-w` importa: sin límites de palabra, los nombres cortos de empresa ahogan la señal en falsos positivos (p. ej. una empresa llamada "Stori" hace match con cada "historia" del texto).

### Faltante estructural cerrado

**`templates/cv-template.md`** — el artefacto central del pipeline (`cvs/cv_for_[slug].md`) era el único sin plantilla, y `system-prompt.md` afirmaba falsamente que `templates/` los tenía todos. El formato es un contrato implícito del parser, ahora documentado en `docs/workflow.md` (Fase 2) y referenciado desde README y `system-prompt.md`.

### Decisión de alcance (no revisitar sin nueva evidencia)

Funcionalidad 2 (buscador/recomendador automático de vacantes) se evaluó y se descartó para este release — riesgo de ToS/cuenta (LinkedIn prohíbe scraping automatizado), y ninguna evidencia del pipeline original mostró que "encontrar vacantes" fuera el cuello de botella. Si se retoma: solo sobre APIs públicas (Adzuna, Arbeitnow, Greenhouse/Lever), sin vínculo a cuenta personal. Detalle en `README.md` → "Qué no incluye (todavía)".

## Siguiente acción

1. **Revisar el contenido completo** — pendiente explícito, todavía no se hizo una pasada de lectura completa por el usuario.
2. Una vez revisado y aprobado: crear el repo en GitHub, conectar `origin`, primer push.

## Decisiones abiertas

- **¿`.claude/ESTADO.md` debe versionarse en un repo público?** Hoy sí se versiona y por lo tanto viaja en cada fork: un tercero recibe las notas internas de desarrollo del proyecto. Se sanitizó para que no lleve datos personales, pero la pregunta de fondo sigue: la convención de continuidad asume repos privados. Alternativa si molesta: `.gitignore` sobre `.claude/` y llevar la continuidad fuera del repo.
- `check_em_dash_style.py` mantiene su copia deliberada de `strip_frontmatter_and_notes()` **sin** la advertencia de truncado (solo la tiene el generador, que corre primero en el flujo). Si alguien corre el style check aislado sobre un CV con `---` de más, no se entera. Decisión consciente para no duplicar la lógica.
- Cosmético sin resolver: el estilo `META` (itálica) de `generate_cv_pdf.py` casi nunca dispara, porque las líneas de fecha reales son `**Ene 2022 - Nov 2025** | Ciudad` y no terminan en `**`. Caen a `BODY`. Los PDFs del proyecto original salieron así; no se tocó.
- El smoke test no valida el **contenido** de los prompts, solo que el flujo de scripts corra. La capa de prompts (`prompts/`, `claude-code/`) no tiene verificación automatizada y probablemente no debería tenerla — se valida usándola.

## Notas de operación

- **No copiar contenido del repo privado sin auditar comentarios y docstrings, no solo el texto de los documentos** — ver "Fugas de datos personales" arriba.
- La regla central del sistema (nunca reclamar un dato no verificado) vive en `prompts/system-prompt.md`.
- Python mínimo: 3.9 (PEP 585 en las anotaciones). Documentado en README.
- `LICENSE` lleva el nombre real del autor a propósito: es la atribución de copyright MIT, no una fuga.
