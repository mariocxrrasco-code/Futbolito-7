---
name: token-efficiency
description: Optimizes token usage, reduces context consumption, enforces concise responses, surgical file inspection, and minimal diffs. Use when the user wants to save tokens, optimize API costs, or work in concise mode.
---

# Token Efficiency & Context Minimizer

## Reglas para Ahorro de Tokens en Futbolito 7:
1. **Respuestas Concisas y Sin Relleno:** Omitir introducciones genéricas, cortesías y explicaciones redundantes. Ir directo al grano, código o comandos.
2. **Inspección Quirúrgica de Archivos:** Al usar `view_file`, SIEMPRE limitar `StartLine` y `EndLine` a las funciones o clases específicas que se necesitan. No volcar archivos enteros al contexto.
3. **Ediciones Mínimas (Diffs Exactos):** Usar siempre `replace_file_content` para sustituir solo los fragmentos necesarios, evitando reescribir archivos enteros (`write_to_file` con `Overwrite=true` innecesario).
4. **Clarificación Previa vs Especulación:** Si hay ambigüedad en los requerimientos del sprint o del modelo, preguntar puntualmente en vez de generar cientos de líneas de código tentativo que consuman tokens dobles al corregirse.
5. **Comandos Directos:** Proporcionar comandos y scripts limpios, listos para ejecutar.
