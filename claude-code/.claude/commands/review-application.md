---
description: Corre el pipeline drafter-reviewer + ATS-check sobre una aplicación ya generada, antes de enviarla
argument-hint: [slug-empresa-rol]
---

Slug: $ARGUMENTS

1. Resuelve rutas por convención de slug:
   - CV: `cvs/cv_for_$ARGUMENTS.md`
   - Tracking: `applications/$ARGUMENTS-application.md`
   - PDF: `cvs-pdf/[nombre-de-config.yaml]-$ARGUMENTS.pdf`
   Si alguno no existe, dilo y detente.

2. Lanza el subagente `cv-reviewer` con las tres rutas. Si ya leíste el CV en este paso, pásale el contenido inline en el prompt en vez de pedirle que lo vuelva a leer.

3. Con la respuesta del reviewer:
   - Aplica la Parte A (ediciones puntuales) directamente con Edit sobre `cvs/cv_for_$ARGUMENTS.md`, una por una.
   - Para la Parte B, decide junto con el usuario qué incorporar — no la apliques mecánicamente.
   - Nunca incorpores una sugerencia que invente datos no verificados en `profile/`.

4. El ATS-check aplica solo al CV. Extrae las keywords requeridas/preferidas de la sección "Mapeo Perfil vs Requisitos" del tracking file y corre:
   `python3 scripts/ats_check.py "cvs-pdf/[nombre]-$ARGUMENTS.pdf" "kw1,kw2,kw3,..."`
   Si el CV se editó en el paso 3, regenera el PDF antes de correr el check:
   `python3 scripts/generate_cv_pdf.py "cvs/cv_for_$ARGUMENTS.md" "cvs-pdf/[nombre]-$ARGUMENTS.pdf"`

5. Corre el check de estilo sobre el Markdown fuente (informativo, nunca bloquea, no pide interacción):
   `python3 scripts/check_em_dash_style.py "cvs/cv_for_$ARGUMENTS.md"`
   Si reporta líneas de prosa, decide junto con el usuario si vale una pasada editorial — no las reescribas mecánicamente. Si se edita, regenera el PDF y vuelve a correr el ATS-check del paso 4.

6. Presenta: reporte del reviewer (Parte A aplicada / Parte B pendiente de decisión) + resultado del ATS-check + resultado del check de estilo. No marques la aplicación como lista sin aprobación explícita del usuario.
