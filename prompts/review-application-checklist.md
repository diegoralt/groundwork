# Checklist: Revisión antes de enviar

Corre esto antes de dar por lista cualquier aplicación. Si usas Claude Code, `/review-application [slug]` automatiza los pasos — esta versión es la manual, para cualquier otra herramienta.

1. **Resuelve las rutas** desde el slug compartido (`[empresa]-[rol]` en kebab-case, ver `docs/workflow.md` → Fase 2): CV en `cvs/cv_for_[slug].md`, tracking en `applications/[slug]-application.md`, PDF en `cvs-pdf/[tu-nombre]-[slug].pdf`. Si alguno no existe, no sigas: o falta un paso anterior, o el slug no coincide en los tres.

2. **Corre el revisor de CV** (`prompts/cv-reviewer-prompt.md`) en una sesión nueva, con el CV, `profile/experience.md`, `profile/skills.md` y la vacante adjuntos.

3. **Aplica la Parte A** (ediciones puntuales) directamente sobre el CV, una por una. Para la Parte B, decide tú qué incorporar — no la apliques mecánicamente. Nunca incorpores una sugerencia que invente un dato no verificado en `profile/`.

4. **Regenera el PDF** si editaste el CV:
   ```
   python3 scripts/generate_cv_pdf.py cvs/cv_for_[slug].md cvs-pdf/[tu-nombre]-[slug].pdf
   ```

5. **Corre el ATS check** — extrae las keywords requeridas/preferidas de la sección "Mapeo: Perfil vs Requisitos" del tracking file:
   ```
   python3 scripts/ats_check.py cvs-pdf/[tu-nombre]-[slug].pdf "kw1,kw2,kw3,..."
   ```

6. **Corre el check de estilo** (informativo, nunca bloquea):
   ```
   python3 scripts/check_em_dash_style.py cvs/cv_for_[slug].md
   ```
   Si reporta líneas de prosa, decide si vale una pasada editorial — no las reescribas mecánicamente. Si editas, vuelve al paso 4.

7. **Corre los checks obligatorios** (salidas: 0 = OK, 1 = falla, 2 = no evaluado; el 2 nunca cuenta como aprobado):
   ```
   python3 scripts/check_chronological_order.py cvs/cv_for_[slug].md
   python3 scripts/check_gaps.py cvs/cv_for_[slug].md
   ```
   - Cronología: la Experiencia debe estar en orden inverso estricto, con fechas legibles en cada entrada.
   - Gaps: ningún término de la sección "Gaps confirmados" de `profile/skills.md` puede aparecer en el cuerpo del CV. Una tabla de gaps vacía es válida (0): aún no confirmaste ninguno. Si un término aparece por un falso positivo, resuélvelo con una línea `gap_resuelto:` en las notas internas (el script imprime el formato) y valídala tú contra tu perfil.
   - Informativo, sin bloqueo: `python3 scripts/check_star_citation.py applications/[slug]-application.md` avisa si una historia STAR reformula una de `profile/star-stories.md` sin citarla.

8. **Sella la revisión** — liga lo que revisaste al CV exacto que vas a enviar:
   ```
   python3 scripts/review_stamp.py [slug] --preparar --keywords "kw1,kw2,..." --validacion "gaps resueltos y claims revisados contra profile/"
   ```
   `--preparar` repite cronología y gaps, regenera el PDF desde el Markdown y corre el ATS sobre el PDF nuevo; si los tres salen en 0, escribe en el tracking las huellas SHA-256 del CV, del PDF y de `profile/`, con veredicto "pendiente". Cualquier edición posterior invalida el sello.

9. **Presenta el resultado antes de marcar la aplicación como lista**: reporte del revisor (qué se aplicó / qué queda pendiente de decisión) + ATS check + check de estilo + checks obligatorios + sello preparado. No la des por enviable sin haber visto todo, y solo tú apruebas.

10. **Después de tu aprobación explícita y antes de subir el CV**: `python3 scripts/review_stamp.py [slug] --aprobar`, luego `--check` (debe decir OK: el PDF es el aprobado). **Al enviar**: `python3 scripts/review_stamp.py [slug] --registrar-envio` guarda en el tracking `cv_version` (12 primeros caracteres de la huella del PDF), las huellas completas y la fecha de envío. Si el formulario no pide documento: `--sin-documento --validacion "motivo"`, y luego `--registrar-envio`.
