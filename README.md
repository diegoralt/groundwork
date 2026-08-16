# Groundwork

Un sistema de preparación de aplicaciones de trabajo (CVs adaptados, tracking de procesos, práctica de entrevistas) construido sobre una sola regla que nunca se rompe:

> **Todo dato en un CV, respuesta o historia debe rastrearse hasta tu perfil documentado. Si no está ahí, no se reclama — se confirma primero.**

Nace de un sistema privado usado en una búsqueda de empleo real durante varios meses, donde esa disciplina —y el costo real de romperla dos veces— se volvió el eje de todo el diseño.

## Por qué existe

La mayoría de herramientas de CV optimizan para que "suene bien" contra un ATS. Ninguna evita que inventes un logro. Este sistema hace lo contrario: cada afirmación en un CV se verifica contra tu propio historial documentado antes de escribirse, un segundo par de ojos (humano o IA) la revisa antes de enviarse, y las tecnologías que confirmaste no dominar quedan registradas para nunca volver a reclamarse por accidente.

## Dos capas

- **`prompts/`** — prompts en markdown, agnósticos de herramienta. Cópialos y pégalos en el chat de IA que uses (ChatGPT, Claude, Gemini, lo que sea).
- **`claude-code/`** — la misma lógica, empaquetada como agente/comandos de [Claude Code](https://claude.com/product/claude-code), si es lo que usas. Automatiza lo que en la capa de prompts es un checklist manual.

Los scripts en `scripts/` (Python puro) los usan ambas capas por igual — no dependen de ningún LLM.

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
- Cuestionario de bootstrap para construir tu perfil desde cero (`prompts/bootstrap-questionnaire.md`)
- Práctica de entrevista en vivo, turno por turno (`prompts/mock-interview-prompt.md`)

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
