# Groundwork — Integración Claude Code

Copia este archivo a la raíz de tu repo (junto a `profile/`, `applications/`, etc.) y copia `.claude/` (dentro de esta misma carpeta `claude-code/`) también a la raíz. Claude Code carga `CLAUDE.md` automáticamente al abrir el proyecto.

## Instrucciones base

Lee y sigue `prompts/system-prompt.md` — ahí está la regla central (todo dato se rastrea a `profile/`, nunca se inventa) y la estructura completa de archivos. Este documento solo agrega lo específico de trabajar con Claude Code.

## Comandos disponibles

- **`/review-application [slug]`** — corre el agente `cv-reviewer` + `ats_check.py` + `check_em_dash_style.py` sobre una aplicación, antes de enviarla. Automatiza `prompts/review-application-checklist.md`.
- **`/mock-interview [slug opcional]`** — práctica de entrevista en vivo, turno por turno, en la misma conversación (nunca delegada a un subagente). Automatiza `prompts/mock-interview-prompt.md`.
- **`/bootstrap`** — cuestionario guiado para construir `profile/experience.md` desde cero. Automatiza `prompts/bootstrap-questionnaire.md`.

## Reglas de operación

- Nunca marques una aplicación como lista para enviar sin aprobación explícita.
- Antes de escribir cualquier CV, verifica cada afirmación contra `profile/`. Si no está documentada, pregunta antes de escribir — no asumas ni completes por tu cuenta.
- `config.yaml`, `profile/`, `applications/`, `cvs/`, `cvs-pdf/` nunca se commitean (ver `.gitignore` en la raíz del proyecto) — si vas a hacer un `git add`, revisa que ninguno se haya colado.
