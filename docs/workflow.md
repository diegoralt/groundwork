---
type: referencia
name: Guía de Flujo de Trabajo
description: Cómo usar Groundwork paso a paso
---

# Flujo de Trabajo

## Fase 0: Bootstrap (una sola vez, si arrancas de cero)

Si `profile/experience.md` está vacío, corre `/bootstrap` (Claude Code) o pega `prompts/bootstrap-questionnaire.md` en el chat de tu elección. Es una entrevista guiada rol por rol — no un formulario que llenas de memoria de un tirón.

## Fase 1: Setup

1. Copia `config.example.yaml` a `config.yaml` y llena tus datos de contacto y tus propias categorías de rol (`tiers`).
2. Copia cada archivo de `templates/profile/` a `profile/` y complétalo (o usa la Fase 0 para `experience.md`).

Estos archivos son la única fuente de verdad. Ningún dato en un CV o un tracking puede afirmar algo que no esté aquí.

## Fase 2: Nueva aplicación

**El slug**: cada aplicación tiene un identificador `[empresa-kebab-case]-[rol-kebab-case]` (ej. `aurelia-senior-backend-engineer`) que **los tres artefactos comparten**:

| Artefacto | Ruta |
|---|---|
| CV fuente | `cvs/cv_for_[slug].md` |
| PDF | `cvs-pdf/[tu-nombre]-[slug].pdf` |
| Tracking | `applications/[slug]-application.md` |

`[tu-nombre]` es tu `contact.name` de `config.yaml` en kebab-case: minúsculas, sin acentos, espacios como guiones (`Ada Lovelace Ruiz` → `ada-lovelace-ruiz`). No es el valor crudo — un nombre con espacios y mayúsculas produce archivos que la siguiente sesión no encuentra.

Con esto localizas todo lo de una aplicación con un solo patrón de búsqueda, y `/review-application [slug]` resuelve las tres rutas sin que le digas dónde está cada cosa. Si el comando dice que un archivo no existe, lo primero que hay que revisar es que el slug coincida en los tres.

1. **Evalúa la vacante primero**: ¿cae en tus propias categorías objetivo (`config.yaml` → `tiers`)? ¿algún "must have" ya está en la sección "Gaps confirmados" de `skills.md`? Si no pasa tu propio filtro, se descarta antes de invertir tiempo.
2. **Genera el CV específico** desde `templates/cv-template.md`, verificado línea por línea contra `profile/`, en `cvs/cv_for_[slug].md`.

   El formato no es libre: `generate_cv_pdf.py` lo parsea. Tres reglas que importan:
   - `# Nombre` primero, y la **línea de contacto inmediatamente después** — la posición es lo que le da su estilo.
   - `## Sección` (se pone en mayúsculas al render), `### Puesto @ Empresa`, bullets con `- `.
   - **Un solo `---` después del frontmatter**: marca el inicio de las notas internas, que nunca llegan al PDF. Nunca uses `---` como separador de secciones — todo lo que quede debajo se pierde. El script avisa si detecta encabezados del lado descartado.

3. **Genera el archivo de tracking** `applications/[slug]-application.md` desde `templates/application-tracking-template.md`. Las STAR stories se adaptan desde `profile/star-stories.md`, no se redactan de cero.
4. **Genera el PDF** con `python3 scripts/generate_cv_pdf.py cvs/cv_for_[slug].md cvs-pdf/[tu-nombre]-[slug].pdf`.

## Fase 3: Revisión antes de enviar

Corre `/review-application [slug]` (Claude Code) o sigue `prompts/review-application-checklist.md` a mano. En cualquiera de los dos casos:

1. Segundo par de ojos (`prompts/cv-reviewer-prompt.md`) — critica el CV contra el posting y contra `profile/`, en una sesión distinta de la que lo escribió.
2. `ats_check.py` — cobertura de keywords en el PDF final.
3. `check_em_dash_style.py` — detecta prosa que delata redacción de IA (informativo, no bloquea).

Nunca marques una aplicación como lista sin revisar los tres resultados.

## Fase 3.5: Práctica antes de una entrevista real

Corre `/mock-interview [slug]` (o sin slug para modo genérico) o pega `prompts/mock-interview-prompt.md` — simulación turno por turno, nunca de un solo disparo. El feedback siempre prioriza fidelidad contra `profile/` antes que forma — nunca valida un dato que no esté ahí, ni en modo práctica.

## Fase 4: Seguimiento y conversión

- Corre `python3 scripts/followup_check.py` al retomar tu búsqueda — lee el campo `follow_up` de cada tracking file y avisa qué tiene contacto pendiente de seguimiento, qué lleva 15+ días "esperando respuesta" sin reclasificar, y qué quedó sin auditar. Distingue `pending_contact` (vencido, hay a quién escribir) de `no_channel` (vencido, solo portal, espera pasiva) — no genera tarea donde no hay acción real posible.
- Un rechazo o cierre no borra el CV/tracking: quedan como material reutilizable para procesos similares.
- Corre `python3 scripts/conversion_report.py` para tu tasa de conversión real por categoría — se calcula sola desde el frontmatter (`tier`/`advanced`), no hace falta recontar a mano. Si tu percepción de qué tipo de rol te funciona no coincide con este número, confía en el número.

## Tips

1. **Sé específico**: en lugar de "trabajé en un proyecto", detalla impacto cuantificable ya documentado en `experience.md` — y si no hay un número real, describe el resultado cualitativo en vez de inventar uno.
2. **Nunca copies keywords del posting sin verificar que aplican en `profile/`** — es la fuente más común de datos inflados que después son imposibles de sostener en entrevista.
3. **Actualiza `profile/` primero** — todo lo demás (CVs, tracking, STAR stories) se deriva de ahí.
