---
description: Simula una entrevista técnica/STAR turno por turno, con feedback en vivo sobre fidelidad y storytelling
argument-hint: [slug-empresa-rol opcional]
---

Slug: $ARGUMENTS

Esto es una práctica interactiva dentro de esta misma conversación — nunca delegues a un subagente, la gracia es el ida y vuelta en vivo con el usuario. Sigue el flujo completo de `prompts/mock-interview-prompt.md`.

## 1. Resuelve el modo

- Si hay `$ARGUMENTS`: busca `applications/$ARGUMENTS-application.md`. Si no existe, dilo y detente.
- Si no hay `$ARGUMENTS`: modo genérico, sin tracking file de por medio.

## 2. Carga contexto (antes de empezar, no lo muestres al usuario)

- Si hay tracking file: sección "Preguntas Esperadas & Respuestas", "STAR Stories Preparadas" y "Role Summary".
- Siempre: `profile/star-stories.md`, `profile/experience.md`, y la sección "Gaps confirmados" de `profile/skills.md` si existe.

## 3. Pregunta al usuario el foco de la sesión

Ofrece las opciones A-D descritas en `prompts/mock-interview-prompt.md` (Q&A preparada / ownership-storytelling / trivia técnica dirigida / un gap específico que el usuario nombre).

## 4. Corre la sesión, una pregunta a la vez

Sigue exactamente el proceso de `prompts/mock-interview-prompt.md`, sección "Corre la sesión así" — fidelidad primero, siempre.

## 5. Al cerrar

Sigue la sección "Al cerrar" del prompt — resumen corto, sin calificación numérica.
