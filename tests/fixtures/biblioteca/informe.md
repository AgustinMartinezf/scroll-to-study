# Informe (fixture de prueba: una biblioteca inventada)

## Decisiones de diseño

La multa no referencia al socio directamente. La clave foránea de multa apunta a prestamo,
así solo se puede multar a alguien que se llevó un ejemplar.

No agregamos una FK directa de multa a socio porque ya está implícita en la cadena
socio → prestamo → multa, y abriría un segundo camino que podría contradecirla.

Que un ejemplar ya esté prestado no lo puede ver una FK: lo controla un trigger.

La reserva apunta al ejemplar y no al libro: se reserva una copia concreta.
