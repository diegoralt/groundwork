# Estado — groundwork

> Punto de retomada. Se sobrescribe cada sesión, no se acumula. El historial lo tiene git.
> Última actualización: 2026-08-15

> **Este archivo ya NO se versiona** (`.gitignore` → `/.claude/ESTADO.md`). Son notas de
> desarrollo de groundwork; a quien hace fork no le sirven y antes le llegaban dentro de
> su `.claude/`. Costo aceptado: no hay continuidad de groundwork entre máquinas.
> Las lecciones duraderas viven en memoria, no aquí.

## Estado actual

Spin-off open-source de un pipeline privado de CV/aplicaciones. MIT, sin remoto todavía. Un commit limpio en `main`; **todo lo demás sin commitear** (15 cambios entre modificados y renombrados).

El sistema está verificado en los cuatro frentes que importan: los scripts corren, el flujo del README corre en un fork limpio, la capa de prompts se auditó contra un perfil ficticio con violaciones plantadas, y la paridad con el proyecto privado original está contrastada. No hay nada roto conocido.

### Estructura (post-reestructura del 2026-08-15)

La integración de Claude Code vive **en la raíz** — `CLAUDE.md`, `.claude/agents/`, `.claude/commands/`. Cero pasos de instalación. Antes había una carpeta `claude-code/` de staging que había que copiar a mano; ese paso pisaba el `.claude/` existente y le entregaba al forker el ESTADO.md de groundwork. La carpeta ya no existe.

Las dos rutas de uso (prompts manuales / Claude Code) están comparadas fase por fase en una tabla del README. **Groundwork no requiere Claude Code** y el README lo dice en la primera línea de esa sección.

### Cómo se prueba

- **Unitario**: `python3 scripts/<script>.py --demo` en los 5 scripts. Parsers y cálculo.
- **Integración**: `python3 scripts/smoke_test.py`. Copia lo que devuelve `git ls-files` a un tmpdir (lo que recibe quien hace fork), corre el Quickstart literal, genera CV → PDF, pasa los cuatro checks. Además verifica que la integración de Claude Code llegue completa, que no reaparezca `claude-code/` y que `ESTADO.md` no viaje.

El smoke test existe porque todos los bugs graves encontrados han sido de integración: los `--demo` pasaban en verde mientras el generador truncaba CVs. Se verificó que falla de verdad al reintroducir el bug del `---`.

### Invariantes que no se deben romper

1. **El CV markdown tiene exactamente 3 líneas `---`** (frontmatter + apertura de notas). Usarlo como regla horizontal trunca el PDF; el generador avisa a stderr pero el template es la defensa real.
2. **El slug es compartido** por CV, PDF y tracking; `[tu-nombre]` del PDF va en kebab-case, no el valor crudo de `contact.name`. Documentado en `docs/workflow.md` → Fase 2.
3. **"Gaps confirmados" de `skills.md` es una lista de exclusión**, y las notas `⚠️ Cuidado` limitan cómo reusar un logro. Ambas convenciones las tienen que conocer los dos `cv-reviewer` (prompt y agente) y el paso de generación de CV — se auditó una vez que no las conocían y 3 de 6 violaciones plantadas pasaban limpias.
4. **Ninguna PII en el repo**, incluidos comentarios y docstrings. `LICENSE` lleva el nombre real a propósito (atribución MIT).

### Decisión de alcance (no revisitar sin nueva evidencia)

Buscador/recomendador automático de vacantes: descartado para este release — riesgo de ToS/cuenta (LinkedIn prohíbe scraping automatizado) y ninguna evidencia de que "encontrar vacantes" fuera el cuello de botella. Si se retoma, solo sobre APIs públicas (Adzuna, Arbeitnow, Greenhouse/Lever). Detalle en `README.md` → "Qué no incluye (todavía)".

## Siguiente acción

1. **Commitear todo lo pendiente.**
2. **Revisar el contenido completo** — pendiente explícito, todavía no se hizo una pasada de lectura completa por el usuario.
3. Una vez revisado y aprobado: crear el repo en GitHub, conectar `origin`, primer push.

## Decisiones abiertas

- **Falta la vista de "todas mis aplicaciones y su estado".** El proyecto original tenía `applications-index.md` mantenido a mano; aquí `followup_check.py` solo muestra lo accionable y `conversion_report.py` solo tasas por tier. Con 15 aplicaciones no hay panorama. Si se agrega, derivada del frontmatter y no mantenida a mano. Es alcance de producto, no un bug.
- **La prueba adversarial la ejecutó quien plantó las trampas**, así que prueba que el prompt *contiene* la instrucción que atrapa cada violación, no que un modelo sin contexto la aplicaría. Una prueba limpia necesita un evaluador que no haya visto el fixture.
- **Las referencias cruzadas de la capa de prompts** (rutas y nombres de sección citados entre archivos) se verifican a mano; encontraron 2 defectos reales el 2026-08-15. Vale moverlo al smoke test si vuelve a pasar.
- `check_em_dash_style.py` mantiene su copia deliberada de `strip_frontmatter_and_notes()` **sin** la advertencia de truncado — solo la tiene el generador, que corre primero. Decisión consciente para no duplicar lógica.
- Cosmético: el estilo `META` (itálica) de `generate_cv_pdf.py` casi nunca dispara, porque las líneas de fecha reales (`**Ene 2022 - Nov 2025** | Ciudad`) no terminan en `**` y caen a `BODY`. Los PDFs del proyecto original salieron así; no se tocó.

## Notas de operación

- **No copiar contenido del repo privado sin auditar comentarios y docstrings**, no solo el texto de los documentos: ahí se coló PII que sobrevivió a la primera auditoría.
- Python mínimo: 3.9 (PEP 585 en las anotaciones). Documentado en README.
