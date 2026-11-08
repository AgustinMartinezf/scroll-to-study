With the inventory of statements of a course, propose the list of TOPICS for 30–60 second videos that prepare an exam. One topic = one concept, one property or one type of exercise the exam can ask for.

Rules:
- Each topic uses 2 to 6 statements from the inventory, by id. A statement may appear in more than one topic if needed, but avoid repeating.
- Use only statements with state "ok" or "general". Do not use the ones marked "comprobar".
- "pregunta": an exam question this video prepares, in one sentence, in the VIDEO LANGUAGE ("What happens if an ACK is lost?", "Differentiate $x^3$").
- Order as it is learned: basic definitions first, then what builds on them, worked exercise types at the end.
- With exercises and general methods: one topic = one type of exercise from the material + its method and traps ("Venn with three sets", "∈ or ⊂"). The question is how to recognize that type of exercise and how to approach it. Every topic must include at least one statement from the material (the exercise), not only general methods.
- Between 8 and 20 topics. Ids t01, t02, …
- "titulo": short (2 to 6 words), in the VIDEO LANGUAGE; it is used in "Tomorrow: <titulo>".
- Optional "formato": only if the person asks for a specific one (pregunta, mito, avsb, pasos, historia); otherwise the tool picks it from the statements.
Output: {"temas": [{"id", "titulo", "pregunta", "afirmaciones"}, …]}
