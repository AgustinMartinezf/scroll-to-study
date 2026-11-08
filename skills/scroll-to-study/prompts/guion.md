Escribís el guion de UN video vertical de 45–60 s, estilo TikTok, que prepara a un estudiante para defender su proyecto. Un motor lo anima solo: vos decidís qué se dice y qué aparece en cada palabra.

# Estructura obligatoria
- Gancho (primera frase): una pregunta o dato que genere tensión en 2 segundos.
- 3 o 4 bloques. Cada bloque es una escena: entre 1 y 4 elementos visuales y entre 2 y 4 frases.
- Clímax: el dato más fuerte, con la acción boom sobre un elemento, en el último bloque.
- Final: frase "En la defensa decí: …" con 2 o 3 líneas para memorizar, y frase "Mañana: <tema siguiente>".
- En total, entre 110 y 150 palabras habladas. Frases cortas, de 5 a 17 palabras, una idea cada una. Español rioplatense, tuteo con voseo ("decí", "fijate").

# Verdad
- Usá SOLO las afirmaciones que se te dan. No agregues hechos, nombres, números, motivos ni ejemplos que no estén ahí.
- En cada bloque, "fuentes" lista los ids de afirmaciones que respaldan lo que se dice y se muestra en ese bloque.
- Si para que el video se entienda necesitás algo que no está en las afirmaciones, ponelo en "comprobar" del bloque (texto breve de lo que hay que verificar) en vez de afirmarlo como cierto.
- Filas de ejemplo en tablas: usá valores que aparezcan en las afirmaciones; si inventás valores ilustrativos, que sean evidentemente de ejemplo.

# Formato de las frases
- {accion id} justo antes de una palabra: la acción ocurre cuando la voz dice esa palabra. Desfase opcional: {good g-r0 +0.2}. Extras opcionales clave=valor: {focus g s=1.2}.
- [+palabra] o [-palabra]: resalta esa palabra del subtítulo en verde o rojo. Una sola palabra por marca. Usalo con moderación (1 o 2 por bloque) en la palabra clave.
- Las etiquetas solo pueden usar ids de elementos del MISMO bloque. Cada bloque tiene que tener al menos una etiqueta.
- Las palabras técnicas se escriben normal (FK, UNIQUE, id_prestamo): la pronunciación la resuelve un léxico aparte. Nunca uses ~.
- No pongas una etiqueta antes de una palabra que tenga guion o + (ON-DELETE): poné la etiqueta en la palabra de al lado.
- Un elemento que tiene {show id} empieza oculto y aparece en esa palabra. Las filas de una tabla se llenan con {show tabla-r0}, {show tabla-r1}…

# Acciones
show, hide, hl (resaltar), good / bad (verde / rojo con sacudida), strike (tachar: solo celdas, encabezados, chips, renglones de lista, cajas de flujo o big), swap (voltear al texto "alt" de un chip), type (tipear una consola), pulse, shake, boom (golpe del clímax), point (el personaje señala; solo diálogos), focus (la cámara se acerca).

# Elementos (no pongas tamaños: fs y w los calcula el compilador)
- table: id, title, cols [..], rows [[..],[..]] (máximo 4 filas, cada fila con tantas celdas como columnas). Ids implícitos: id-r0 (fila), id-r0-c1 (celda), id-h0 (encabezado).
- chip: id, text (máx. ~40 caracteres), kind (good, bad, warn, neutral, blue, white, purple), icon opcional, mono true para código, alt + altkind opcionales para swap.
- toast: id, text (error tipo consola, máx. ~35 caracteres), kind "bad" o "good".
- dialog: id, char (novato, pro, admin, estudiante, docente), text (globo corto).
- console: id, lines [..], title opcional. Usar con type.
- list: id, title opcional, items [[id, html], …]. html admite <b> verde y <em> rojo.
- arrow: id, label opcional.
- flow: id, items [{id, text, icon?, kind?}] — máximo 4 cajas de texto corto.
- big: id, text (dato grande, ideal para el clímax).
- row: id, items [chips sin "type"] — 2 o 3 chips en fila.
Íconos (Phosphor): check-circle, x-circle, warning, lightning, arrow-right, users, list-checks, database, key, lock, link, table, code, terminal-window, shield-check, question, calendar-check, trash, plus-circle, magnifying-glass.

# Escenas que funcionan
- Tabla que se llena fila por fila y una fila se pone en rojo cuando algo no entra.
- Novato vs pro: diálogo del novato con la idea equivocada, chip rojo, chip verde con la correcta.
- Flujo de 3 cajas que aparecen en orden mientras se nombran.
- Consola que tipea un comando y un toast con el error.
- Chip que se voltea (swap) de la idea vieja a la nueva, o un strike sobre la opción descartada.

# Salida
Respondé SOLO con el JSON, sin texto antes ni después:
{"bloques":[{"fuentes":["A1"],"comprobar":[],"elementos":[…],"frases":["…"]}, …],
 "final":{"frases":["En la [+defensa] decí: … {show fl1}… {show fl2}…", "{show fnext}Mañana: …"],
          "lineas":["<b>…</b> …","…"], "mañana":"<titulo del tema siguiente>"}}
En el final, cada línea N necesita {show flN} antes de la palabra donde aparece, y "Mañana" necesita {show fnext}.

# Ejemplo completo (otro tema, mismo formato)
{
 "bloques": [
  {
   "fuentes": ["A1", "A2"],
   "comprobar": [],
   "elementos": [
    {"type": "table", "id": "m", "title": "multa", "cols": ["id_prestamo", "monto", "motivo"],
     "rows": [["17", "120", "atraso"], ["99", "80", "atraso"]]},
    {"type": "chip", "id": "fkp", "text": "FK id_prestamo → prestamo", "kind": "good", "mono": true, "icon": "arrow-right"},
    {"type": "toast", "id": "e1", "text": "ERROR 1452 · fk_multa_prestamo"}
   ],
   "frases": [
    "{show m}¿Puede haber una {show m-r0}multa por un libro que {show m-r1}no se prestó? En nuestra base, {bad m-r1}[-no].",
    "La multa no apunta al socio: apunta al {show fkp}{good m-r0 +0.2}[+préstamo].",
    "La FK es {hl m-h0}id_prestamo: cada multa nace de un préstamo [+real].",
    "Si ese préstamo no existe, la multa no {show e1}[-entra]."
   ]
  },
  {
   "fuentes": ["A3", "A4"],
   "comprobar": [],
   "elementos": [
    {"type": "chip", "id": "fks", "text": "prestamo → socio (ci_socio)", "kind": "good", "mono": true, "icon": "arrow-right"},
    {"type": "chip", "id": "solo", "text": "solo socios que se llevaron algo", "kind": "white", "icon": "users"},
    {"type": "flow", "id": "cad", "items": [{"id": "k1", "text": "socio", "icon": "users"}, {"id": "k2", "text": "préstamo", "icon": "list-checks"}, {"id": "k3", "text": "multa", "icon": "check-circle", "kind": "good"}]}
   ],
   "frases": [
    "Y el préstamo apunta al {show fks}[+socio] por ci_socio.",
    "Así, solo se multa a socios que se llevaron un {show solo}ejemplar.",
    "La [+cadena] queda: {show k1}socio, {show k2}préstamo, {show k3}multa."
   ]
  },
  {
   "fuentes": ["A5", "A6"],
   "comprobar": [],
   "elementos": [
    {"type": "dialog", "id": "nov", "char": "novato", "text": "¿Y una FK directa a socio?"},
    {"type": "chip", "id": "imp", "text": "Ya está implícita en el préstamo", "kind": "good", "icon": "check-circle"},
    {"type": "chip", "id": "dos", "text": "Un segundo camino que puede contradecir", "kind": "bad", "icon": "warning"}
   ],
   "frases": [
    "¿Y por qué no una {show nov}FK directa a socio?",
    "Porque ya está {show imp}[+implícita], y abriría un segundo camino que podría {show dos}[-contradecirla]."
   ]
  },
  {
   "fuentes": ["A7", "A8"],
   "comprobar": [],
   "elementos": [
    {"type": "table", "id": "r", "title": "reserva", "cols": ["id_ejemplar", "ci_socio", "estado"], "rows": [["301", "41234567", "activa"]]},
    {"type": "chip", "id": "fkr", "text": "FK id_ejemplar → ejemplar", "kind": "good", "mono": true, "icon": "arrow-right"},
    {"type": "chip", "id": "una", "text": "se reserva una copia concreta", "kind": "white"},
    {"type": "chip", "id": "trg", "text": "¿ya está prestado? → trigger", "kind": "warn", "icon": "lightning"}
   ],
   "frases": [
    "La {show r}{show r-r0 +0.2}reserva apunta al ejemplar, no al libro: {show fkr}{hl r-h0 +0.1}id_ejemplar.",
    "Así se reserva una {show una}copia concreta, no un título cualquiera.",
    "Lo que una FK no ve, como que el ejemplar ya esté prestado, va en un {show trg}{boom trg +0.3}[-trigger]."
   ]
  }
 ],
 "final": {
  "frases": [
   "En la [+defensa] decí: FK {show fl1}en cadena, {show fl2}socio, préstamo, multa, y la base lo controla sola.",
   "{show fnext}Mañana: la PK de ejemplar."
  ],
  "lineas": ["<b>FK en cadena</b>, sin atajos", "socio → préstamo → multa"],
  "mañana": "la PK de ejemplar"
 }
}
