# Prompt: Cuestionario de Bootstrap (arrancar tu perfil desde cero)

Úsalo si `profile/experience.md` está vacío o casi vacío. Es una entrevista guiada, turno por turno — no un formulario que llenas de un tirón. Va rol por rol, del más reciente al más antiguo.

**Por qué no es un formulario simple:** preguntas abiertas tipo "cuéntame de tu experiencia" producen respuestas genéricas y difíciles de verificar después — exactamente el terreno donde se cuelan datos inflados sin que nadie los note en el momento. La metodología de este cuestionario (una variante de Behavioral Event Interview / Critical Incident Technique, usada en entrevistas de selección basadas en competencias) fuerza ejemplos concretos de situaciones reales en vez de generalidades, porque un ejemplo específico es verificable y uno genérico no.

---

Vas a entrevistarme para construir mi `profile/experience.md` desde cero. Sigue este proceso:

## Por cada rol, del más reciente al más antiguo

1. **Ubica el rol**: puesto, empresa, fechas, modalidad. Una sola pregunta, espera mi respuesta.

2. **Pide un incidente crítico, no un resumen.** No preguntes "¿cuáles eran tus responsabilidades?" — pregunta: *"Cuéntame de una situación específica en ese rol donde tuviste que resolver algo difícil o tomar una decisión importante. ¿Qué pasó exactamente?"* Espera la respuesta completa antes de seguir.

3. **Sondea hasta llegar a lo verificable**, con preguntas de seguimiento como:
   - "¿Qué fue exactamente lo que **tú** decidiste o hiciste, distinto de lo que decidió el equipo o tu líder?" (esto es lo que separa ownership real de narrativa colectiva — si la respuesta sigue en "nosotros"/"el equipo", vuelve a preguntar específicamente qué parte fue tuya)
   - "¿Cómo supiste que funcionó? ¿Hay un número, o es una observación cualitativa?" — **si no hay un número real, no lo inventes ni lo sugieras tú.** Anota el resultado cualitativo tal cual me lo cuentes. Un resultado real sin métrica vale más que una métrica que no puedo sostener en una entrevista.
   - "¿Eso lo hiciste tú solo, con un equipo, o siguiendo un proceso que ya existía?" — esto importa para no atribuirte autoría de un proceso que solo aplicaste (ver `system-prompt.md`, la regla central de todo el sistema).

4. **Repite el paso 2-3 dos o tres veces por rol** — con incidentes distintos (un logro, un conflicto o error manejado, una decisión técnica). No agotes cada rol en un solo incidente.

5. **Antes de escribir nada en `experience.md`**, resume lo que entendiste en 3-4 líneas y pregúntame si es correcto. Si algo quedó ambiguo (¿fue tuyo o del equipo? ¿el número es exacto o aproximado?), pregunta de nuevo — no lo redactes como si estuviera resuelto.

6. **Escribe la entrada en `experience.md`** siguiendo el formato de `templates/profile/experience.md`: verbo activo en primera persona, resultado solo si es real, y una nota de "⚠️ Cuidado" si hay algún matiz que no se puede omitir al reusar esta historia después (ej. "fue mantenimiento sobre algo ya construido, no diseño desde cero").

## Al terminar todos los roles

- Pregúntame cuál total de años de experiencia y años de liderazgo (si aplica) se derivan de las fechas que ya diste — la aritmética la haces tú, no me la preguntes a mí como dato suelto (mismo principio: verificable > declarado).
- Señala si 2-3 incidentes se parecen entre sí en distintos roles (mismo tipo de logro, mismo patrón) — esos son candidatos fuertes para `star-stories.md` una vez que empieces a redactar aplicaciones reales, pero no los escribas ahí todavía: `star-stories.md` se llena cuando una historia se repite en aplicaciones de verdad, no antes.
