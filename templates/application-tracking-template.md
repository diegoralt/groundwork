---
type: application_tracking
company: [Empresa]
position: [Título del Rol]
status: [in_progress | submitted | screening | interviewing | rejected | offer | withdrawn | closed_no_feedback]
tier: [tu propia categoría — ver config.yaml]
advanced: [yes | no — ¿llegó a entrevista o prueba técnica? déjalo vacío hasta saberlo]
follow_up: [waiting | pending_contact | no_channel | unconfirmed]
follow_up_contact: [email o nombre del contacto, solo si follow_up es pending_contact]
date_started: YYYY-MM-DD
date_submitted: YYYY-MM-DD
last_updated: YYYY-MM-DD
tags: [empresa, vacante, área, tipo-rol]
# Los siguientes campos son opcionales — no rompen nada si faltan, pero
# scripts/pipeline_board.py (tablero visual, `python3 scripts/pipeline_board.py --open`)
# los necesita para saber de quién es el siguiente movimiento. Sin `next_action`
# la tarjeta se genera igual, pero avisa "Sin acción definida".
next_action: [una línea, verbo primero — ej. "Escribir seguimiento si no hay respuesta para el 12-09"]
next_date: [YYYY-MM-DD — solo si hay una fecha comprometida (entrevista agendada, plazo de decisión propio). Omitir si no la hay]
interviewer: [nombre; puesto de quien entrevista; qué esperar de la sesión — hasta tres partes separadas por ";". Omitir si aún no lo sabes]
open_questions: [preguntas sin resolver de esta aplicación, separadas por ";" — ej. "modalidad y ubicación; a quién reporta el rol"]
---

# [Empresa] - [Título del Rol] Application [[STATUS]]

## Position Overview

**Company:** [Empresa]
**Position:** [Título del Rol]
**Type:** Full-time / Part-time / Contract
**Location:** [Ciudad / Remote / Hybrid]
**URL:** [link a la vacante]

### Role Summary
[2-3 oraciones describiendo el rol y su enfoque principal.]

---

## Application Status

> `pipeline_board.py` traduce esta tabla al "Recorrido" de la ficha de cada aplicación. Vocabulario completo de estados, además de ✅/⏳/❌: 📅 agendado, 🔄 en curso, 🔴 bloqueado, ⚫ cerrado — cualquier otro emoji se muestra igual, solo sin color.

| Field | Status | Date |
|-------|--------|------|
| **CV Preparation** | ✅ / ⏳ / ❌ | YYYY-MM-DD |
| **Form Submission** | ✅ / ⏳ / ❌ | YYYY-MM-DD |
| **Initial Screening** | ✅ / ⏳ / ❌ | YYYY-MM-DD |
| **Phone/Video Screening** | ✅ / ⏳ / ❌ | YYYY-MM-DD |
| **Technical Interview** | ✅ / ⏳ / ❌ | YYYY-MM-DD |
| **Final Round** | ✅ / ⏳ / ❌ | YYYY-MM-DD |
| **Offer Decision** | ✅ / ⏳ / ❌ | YYYY-MM-DD |

---

## Datos Exactos del Formulario
> Completar solo si el proceso incluye formulario online. Usar como referencia para futuras aplicaciones. Los datos fijos (educación, voluntariado, certificaciones) van en `profile/personal.md` y `profile/skills.md` — cópialos de ahí, no los reescribas aquí cada vez.

### Education
| Campo | Valor |
|---|---|
| School | [tu universidad/institución] |
| Field of study | [tu carrera] |
| Degree | [tu título] |
| Start date | YYYY-MM-DD |
| End date | YYYY-MM-DD |

### Work Experience — Summaries para formulario

**[Título] @ [Empresa] ([fecha inicio] / [fecha fin])**
> [Summary de 2-4 oraciones optimizado para el rol. En inglés. Incluir métricas y keywords del JD — pero solo las que estén verificadas en profile/experience.md.]

*(repetir por cada posición)*

### Volunteer Experience / Professional Associations / Qualifications
> Copia solo lo relevante desde `profile/personal.md` y `profile/skills.md` — no inventes ni repitas todo por defecto.

---

## Mapeo: Perfil vs Requisitos

### Alineado — Fortalezas Clave

| Requisito del JD | Experiencia | Nivel | Evidencia |
|---|---|---|---|
| [Requisito] | [Experiencia concreta] | [X/10] | [Dónde en profile/experience.md] |

### Parcial — Gaps Menores

| Requisito | Realidad | Gap | Severidad |
|---|---|---|---|
| [Requisito] | [Lo que tienes] | [Diferencia] | Alta / Media / Baja |

**Regla no negociable:** si un requisito del posting no está respaldado en `profile/`, es un gap real. Se documenta aquí, nunca se reclama en el CV.

---

## Competitive Advantages

1. **[Ventaja 1]:** [Descripción con evidencia]
2. **[Ventaja 2]:** [Descripción con evidencia]
3. **[Ventaja 3]:** [Descripción con evidencia]

---

## STAR Stories Preparadas

Parte de `profile/star-stories.md` y adapta al posting — no redactes una historia nueva desde cero si ya existe una versión verificada.

### STAR #1: [Tema — ej. Liderazgo de equipo distribuido]

**Situación:** [Contexto. Qué estaba pasando.]
**Tarea:** [Tu responsabilidad específica.]
**Acción:**
- [Paso 1]
- [Paso 2]
- [Paso 3]
**Resultado:** [Métrica o impacto concreto — solo si es real y verificable.]

*(repetir para 3-5 historias clave según el rol)*

---

## Preguntas Esperadas & Respuestas

### P1: "[Pregunta frecuente del rol]"
> [Respuesta en 60-90 segundos. Tono conversacional. Datos reales.]

### P2: "[Pregunta sobre gap o transición]"
> [Respuesta honesta que convierte el gap en narrativa positiva — nunca en un dato inventado.]

*(mínimo 4 preguntas por archivo)*

---

## Preguntas a Hacer en la Entrevista

1. "[Pregunta sobre el equipo o rol]"
2. "[Pregunta sobre stack o herramientas]"
3. "[Pregunta sobre cultura o proceso]"

---

## Alignment Assessment

**Fit Level:** [1-5] — [CALIFICACIÓN: EXCELENTE / BUENO / PARCIAL]

| Requisito | Cobertura | Evidencia |
|---|---|---|
| [Requisito clave] | ✅ / ⚠️ / ❌ | [Evidencia] |

---

## Expected Timeline

| Milestone | Target Date | Status |
|---|---|---|
| Form submission | YYYY-MM-DD | ✅ / ⏳ |
| Initial screening | ~YYYY-MM-DD | ⏳ |
| Phone/Video screening | ~YYYY-MM-DD | ⏳ |
| Technical interview | ~YYYY-MM-DD | ⏳ |
| Final round | ~YYYY-MM-DD | ⏳ |
| Offer decision | ~YYYY-MM-DD | ⏳ |

---

## Contact Information

Copia desde `config.yaml` — no lo escribas dos veces.

---

## Notes

- [Observación relevante sobre esta aplicación específica]
- [Decisiones tomadas en el proceso]
- [Próximo paso inmediato]

---

**Status:** [Estado actual]
**Last Updated:** YYYY-MM-DD
