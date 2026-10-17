---
description: Corre el pipeline drafter-reviewer + ATS-check sobre una aplicación ya generada, antes de enviarla
argument-hint: [slug-empresa-rol]
---

Slug: $ARGUMENTS

1. Resuelve rutas por convención de slug (`docs/workflow.md` → Fase 2):
   - CV: `cvs/cv_for_$ARGUMENTS.md`
   - Tracking: `applications/$ARGUMENTS-application.md`
   - PDF: `cvs-pdf/[nombre]-$ARGUMENTS.pdf`, donde `[nombre]` es `contact.name` de `config.yaml` en kebab-case (minúsculas, sin acentos, espacios como guiones) — no el valor crudo
   Si alguno no existe, dilo y detente. Antes de culpar a un paso faltante, revisa si existe un archivo con slug parecido: el error más común es que los tres no coincidan.

2. Lanza el subagente `cv-reviewer` con las tres rutas. Si ya leíste el CV en este paso, pásale el contenido inline en el prompt en vez de pedirle que lo vuelva a leer.

3. Con la respuesta del reviewer:
   - Aplica la Parte A (ediciones puntuales) directamente con Edit sobre `cvs/cv_for_$ARGUMENTS.md`, una por una.
   - Para la Parte B, decide junto con el usuario qué incorporar — no la apliques mecánicamente.
   - Nunca incorpores una sugerencia que invente datos no verificados en `profile/`.

4. El ATS-check aplica solo al CV. Extrae las keywords requeridas/preferidas de la sección "Mapeo: Perfil vs Requisitos" del tracking file y corre:
   `python3 scripts/ats_check.py "cvs-pdf/[nombre]-$ARGUMENTS.pdf" "kw1,kw2,kw3,..."`
   Si el CV se editó en el paso 3, regenera el PDF antes de correr el check:
   `python3 scripts/generate_cv_pdf.py "cvs/cv_for_$ARGUMENTS.md" "cvs-pdf/[nombre]-$ARGUMENTS.pdf"`

5. Corre el check de estilo sobre el Markdown fuente (informativo, nunca bloquea, no pide interacción):
   `python3 scripts/check_em_dash_style.py "cvs/cv_for_$ARGUMENTS.md"`
   Si reporta líneas de prosa, decide junto con el usuario si vale una pasada editorial — no las reescribas mecánicamente. Si se edita, regenera el PDF y vuelve a correr el ATS-check del paso 4.

6. Corre los checks obligatorios (salidas 0 = OK, 1 = falla, 2 = no evaluado; el 2 nunca cuenta como aprobado):
   - `python3 scripts/check_chronological_order.py "cvs/cv_for_$ARGUMENTS.md"`
   - `python3 scripts/check_gaps.py "cvs/cv_for_$ARGUMENTS.md"` (los términos salen de la sección "Gaps confirmados" de `profile/skills.md`; una tabla vacía es válida). Si un término es un falso positivo, la resolución es una línea `gap_resuelto:` en las notas internas del CV; valídala a mano con el usuario contra `profile/`.
   - Informativo, sin bloqueo: `python3 scripts/check_star_citation.py "applications/$ARGUMENTS-application.md"`.

7. Prepara el sello de revisión: `python3 scripts/review_stamp.py $ARGUMENTS --preparar --validacion "<qué se validó a mano>"`. Repite cronología y gaps, regenera el PDF y corre el ATS; si los tres salen en 0 escribe las huellas SHA-256 en el tracking con veredicto "pendiente". Cualquier edición posterior al sello lo invalida.

8. Presenta: reporte del reviewer (Parte A aplicada / Parte B pendiente de decisión) + ATS-check + check de estilo + checks obligatorios + sello preparado. No marques la aplicación como lista sin aprobación explícita del usuario.

9. Solo tras esa aprobación explícita, corre `python3 scripts/review_stamp.py $ARGUMENTS --aprobar` y luego `--check`. Al registrar el envío: `python3 scripts/review_stamp.py $ARGUMENTS --registrar-envio`. Para un formulario sin CV: `--sin-documento --validacion "motivo"`.
