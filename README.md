# Groundwork

Un sistema de preparación de aplicaciones de trabajo (CVs adaptados, tracking de procesos, práctica de entrevistas) construido sobre una sola regla que nunca se rompe:

> **Todo dato en un CV, respuesta o historia debe rastrearse hasta tu perfil documentado. Si no está ahí, no se reclama — se confirma primero.**

Nace de un sistema privado usado en una búsqueda de empleo real durante varios meses, donde esa disciplina —y el costo real de romperla dos veces— se volvió el eje de todo el diseño.

## Por qué existe

La mayoría de herramientas de CV optimizan para que "suene bien" contra un ATS. Ninguna evita que inventes un logro. Este sistema hace lo contrario: cada afirmación en un CV se verifica contra tu propio historial documentado antes de escribirse, un segundo par de ojos (humano o IA) la revisa antes de enviarse, y las tecnologías que confirmaste no dominar quedan registradas para nunca volver a reclamarse por accidente.

## Dos rutas, el mismo sistema

**Groundwork no requiere Claude Code.** Todo se puede operar copiando y pegando los archivos de `prompts/` en el chat de IA que uses — ChatGPT, Claude, Gemini, el asistente de tu editor. Si además usas [Claude Code](https://claude.com/product/claude-code), los mismos pasos ya vienen empaquetados como comandos: no hay nada que instalar, `CLAUDE.md` y `.claude/` están en la raíz y funcionan al abrir tu fork.

| Fase | Ruta manual (cualquier IA) | Ruta Claude Code |
|---|---|---|
| Contexto persistente | Pega `prompts/system-prompt.md` como instrucción de sistema | Automático (`CLAUDE.md` lo carga) |
| Construir tu perfil | Pega `prompts/bootstrap-questionnaire.md` | `/bootstrap` |
| Revisar antes de enviar | Sigue `prompts/review-application-checklist.md` y pega `prompts/cv-reviewer-prompt.md` en una sesión aparte | `/review-application [slug]` |
| Practicar la entrevista | Pega `prompts/mock-interview-prompt.md` | `/mock-interview [slug]` |

La diferencia es solo cuánto tecleas: la ruta Claude Code resuelve rutas, lanza el revisor como subagente y encadena los checks; la manual te pide hacer esos pasos tú. Ninguna de las dos toma decisiones que la otra no tome.

Los scripts de `scripts/` (Python puro) sirven a ambas por igual — no dependen de ningún LLM.

> El segundo par de ojos funciona mejor en una **sesión distinta** de la que escribió el CV. En la ruta manual eso significa un chat nuevo; en Claude Code lo hace solo, lanzando el agente `cv-reviewer` con su propio contexto.

## Quickstart

Requiere Python 3.9+.

```bash
git clone <este-repo>
cd groundwork
pip install -r requirements.txt

cp config.example.yaml config.yaml        # llena tus datos — nunca se commitea
cp -r templates/profile ./profile          # llena tu perfil — nunca se commitea
mkdir applications cvs cvs-pdf             # tu contenido real vive aquí — nunca se commitea
```

Cada CV nuevo arranca de `templates/cv-template.md` — su formato es el que parsea `generate_cv_pdf.py`, no es libre (ver `docs/workflow.md`, Fase 2).

Si `profile/experience.md` está vacío, arranca con el cuestionario de bootstrap (`prompts/bootstrap-questionnaire.md`, o `/bootstrap` en Claude Code) en vez de llenarlo de memoria.

Flujo completo por aplicación en `docs/workflow.md`.

## Qué incluye hoy

- Generación de CV en Markdown → PDF formato Harvard (`scripts/generate_cv_pdf.py`)
- Revisor de CV independiente, drafter-reviewer (`prompts/cv-reviewer-prompt.md`)
- Verificación ATS de keywords y legibilidad del PDF (`scripts/ats_check.py`)
- Detector de prosa que delata redacción de IA (`scripts/check_em_dash_style.py`)
- Tracking de seguimiento con distinción entre "tienes a quién escribirle" y "solo puedes esperar" (`scripts/followup_check.py`)
- Cálculo de conversión real por categoría de rol, no por percepción (`scripts/conversion_report.py`)
- Tablero visual del pipeline (ver sección propia abajo)
- Cuestionario de bootstrap para construir tu perfil desde cero (`prompts/bootstrap-questionnaire.md`)
- Práctica de entrevista en vivo, turno por turno (`prompts/mock-interview-prompt.md`)

## Tablero visual del pipeline

Un solo archivo HTML — sin servidor, sin dependencias, se abre con doble clic — que lee `applications/*.md` y contesta la pregunta que importa revisar cada día: **¿qué requiere tu acción, y qué solo puede esperar?**

```bash
python3 scripts/pipeline_board.py --open
```

| Vista | Qué muestra |
|---|---|
| **Tablero** | Tres columnas — no por estado administrativo, sino por de quién es el siguiente movimiento: tuyo, de ellos, o sin nadie a quien escribirle. Arriba, la agenda de fechas comprometidas en los próximos días. |
| **Radar** | Una línea de tiempo: a la izquierda lo que lleva callado sin fecha, a la derecha lo comprometido, en la misma escala. |
| **Ficha** | Detalle por aplicación activa — recorrido de etapas, cobertura del puesto, con quién hablas, material relacionado (CV, tracking), preguntas sin resolver. |
| **Histórico** | Aplicaciones cerradas, con resumen agregado por desenlace (rechazadas, cerradas sin respuesta, ofertas). |

No necesita nada nuevo: lee el mismo frontmatter de `applications/*-application.md` que ya usan `followup_check.py` y `conversion_report.py`. Los campos `next_action`, `next_date`, `interviewer` y `open_questions` son opcionales (ver `templates/application-tracking-template.md`) — sin ellos el tablero genera igual, solo con menos detalle por tarjeta.

## Verificar que tu fork funciona

```bash
python3 scripts/smoke_test.py          # flujo completo del Quickstart en un fork limpio
python3 scripts/ats_check.py --demo    # self-check unitario (cada script tiene el suyo)
```

El smoke test copia solo los archivos versionados a un directorio temporal, sigue este README al pie de la letra y verifica que el PDF salga completo. Córrelo si tocas los scripts o el template.

## Qué no incluye (todavía)

Un buscador/recomendador automático de vacantes se evaluó y se descartó para este release. Dos razones: la mayoría de plataformas con las vacantes más relevantes (LinkedIn, bolsas locales) prohíben la recolección automatizada en sus términos de servicio y arriesgan la cuenta de quien lo use; y ninguna evidencia de la búsqueda real que originó este proyecto mostró que "encontrar vacantes" fuera el cuello de botella — el cuello de botella siempre fue el tiempo de preparación por aplicación y la disciplina de seguimiento, que es justo lo que este sistema ataca.

Si en el futuro se agrega, sería sobre APIs públicas (ej. Adzuna, Arbeitnow, Greenhouse/Lever) sin ningún vínculo a cuentas personales — nunca scraping de plataformas que lo prohíben.

## Privacidad

`profile/`, `applications/`, `cvs/`, `cvs-pdf/` y `config.yaml` están en `.gitignore` desde el primer commit — ni siquiera en tu propio fork se commitean por accidente. Si vas a publicar tu fork, revisa `prompts/system-prompt.md` → sección "Privacidad" antes: incluso sin datos personales en el contenido, los **nombres de archivo** de tus PDFs revelan a qué empresas aplicaste.

## Licencia

MIT — ver `LICENSE`.
