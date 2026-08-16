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

7. **Presenta el resultado antes de marcar la aplicación como lista**: reporte del revisor (qué se aplicó / qué queda pendiente de decisión) + resultado del ATS check + resultado del check de estilo. No la des por enviable sin haber visto los tres.
