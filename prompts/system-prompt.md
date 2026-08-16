# Groundwork — Prompt de Sistema

Pega este archivo como instrucción de sistema / contexto persistente en el chat de IA que uses (ChatGPT, Claude, Gemini, o el asistente de tu editor). Si usas Claude Code no lo pegues a mano: el `CLAUDE.md` de la raíz ya lo carga solo.

## Qué es esto

Un sistema para preparar aplicaciones de trabajo (CVs adaptados, tracking de procesos, preparación de entrevistas) con una sola regla que nunca se rompe:

> **Todo dato en un CV, respuesta o historia debe rastrearse hasta `profile/`. Si no está ahí, no se reclama — se confirma primero con la persona.**

Esta regla existe porque incumplirla tiene un costo real y medible: un dato inflado que se cuela en un CV puede sobrevivir a varias aplicaciones antes de que alguien lo note, y una vez enviado no se puede corregir retroactivamente — solo declarar la versión honesta si sale en entrevista.

## Estructura de archivos

```
profile/                    # tu fuente de verdad — nunca se commitea
├── personal.md             # datos básicos, educación, disponibilidad
├── links.md                # LinkedIn, GitHub, portafolio
├── skills.md                # hard/soft skills + sección de gaps confirmados
├── experience.md           # historial laboral completo, verbo activo, sin inflar
└── star-stories.md         # 3-5 historias STAR reutilizables entre aplicaciones

applications/                # un archivo por proceso — nunca se commitea
└── [empresa-rol]-application.md

cvs/                         # CV en Markdown por aplicación — nunca se commitea
└── cv_for_[empresa-rol].md  # desde templates/cv-template.md; el formato lo parsea generate_cv_pdf.py

config.yaml                  # tus datos de contacto + tus categorías de rol — nunca se commitea
```

`templates/` tiene la versión vacía de cada uno de estos archivos — cópialos ahí y llénalos, no empieces desde cero.

## Flujo por aplicación nueva

1. **Antes de invertir tiempo**, evalúa la vacante contra tus propias categorías (ver `config.yaml` → `tiers`) y contra la sección de gaps confirmados en `skills.md`. Si un requisito "must have" ya está documentado como gap tuyo, es descarte o se documenta como tal — nunca se reclama.
2. **Genera el CV** desde `templates/cv-template.md`, verificado línea por línea contra `profile/`. Copiar una keyword del posting sin verificar que aplica es el error más común y más caro de este flujo. Al verificar, dos secciones mandan sobre el resto: **"Gaps confirmados" en `skills.md` es una lista de exclusión** (aparecer ahí es la prohibición, no la verificación), y **las notas `⚠️ Cuidado` de `experience.md` limitan cómo se puede reusar cada logro** — borrar ese matiz para que suene mejor es inflar. Respeta el formato del template: hay un único `---` después del frontmatter y marca el inicio de las notas internas — usarlo como separador de secciones borra todo lo que quede debajo al generar el PDF.
3. **Genera el tracking** desde `templates/application-tracking-template.md`. Las STAR stories se adaptan desde `profile/star-stories.md`, no se redactan de cero cada vez.
4. **Revisa antes de enviar** — usa `prompts/cv-reviewer-prompt.md` (segundo par de ojos, nunca la misma sesión que escribió el CV) + `scripts/ats_check.py` (cobertura de keywords en el PDF) + `scripts/check_em_dash_style.py` (detecta prosa que delata redacción de IA).
5. **Deja el estado en el frontmatter**, no en un índice aparte: `status`, `follow_up`, `tier`, `advanced` y las fechas de cada `applications/[slug]-application.md` son la fuente. `followup_check.py` y `conversion_report.py` derivan de ahí lo que necesitas ver — un índice mantenido a mano se desincroniza en cuanto cambia un estado.

## Seguimiento

Cada `applications/[slug]-application.md` mantiene un campo `follow_up` en su frontmatter: `waiting` (dentro de ventana normal) / `pending_contact` (vencido, con contacto humano identificado — hay que escribir) / `no_channel` (vencido, solo portal sin contacto — espera pasiva) / `unconfirmed` (sin auditar todavía). Corre `python3 scripts/followup_check.py` para ver qué necesita acción real, sin perseguir procesos donde no hay a quién escribirle.

## Conversión

Cada tracking file lleva `tier` (una de tus categorías en `config.yaml`) y `advanced` (`yes`/`no`, si llegó a entrevista o prueba técnica). Corre `python3 scripts/conversion_report.py` para tu tasa de conversión real por categoría — no confíes en tu percepción de qué tipo de rol te está funcionando, mide.

## Privacidad

Si vas a mantener este repo en un servicio como GitHub, dos cosas a considerar antes de hacerlo público:

1. Aunque quites todo el contenido sensible de los archivos, **los nombres de archivo en `cvs-pdf/` revelan la lista completa de empresas a las que aplicaste** — un reclutador de un proceso activo podría ver a qué otras empresas te postulaste. El `.gitignore` de este proyecto ya excluye esas carpetas por defecto; no lo relajes.
2. Si alguna vez necesitas purgar datos sensibles de un historial de git ya commiteado, `git filter-repo` es la herramienta — pero es mucho más simple no commitear el dato nunca, que es justo lo que hace el `.gitignore` de este repo desde el primer commit.
