-- Fixture de prueba: una biblioteca inventada
CREATE TABLE socio (
  ci_socio INT PRIMARY KEY,
  nombre VARCHAR(60) NOT NULL
);

CREATE TABLE ejemplar (
  id_ejemplar INT PRIMARY KEY,
  isbn CHAR(13) NOT NULL
);

CREATE TABLE prestamo (
  id_prestamo INT AUTO_INCREMENT PRIMARY KEY,
  id_ejemplar INT NOT NULL,
  ci_socio INT NOT NULL,
  fecha_devolucion DATE,
  CONSTRAINT fk_prestamo_socio FOREIGN KEY (ci_socio) REFERENCES socio (ci_socio),
  CONSTRAINT fk_prestamo_ejemplar FOREIGN KEY (id_ejemplar) REFERENCES ejemplar (id_ejemplar)
);

CREATE TABLE multa (
  id_multa INT AUTO_INCREMENT PRIMARY KEY,
  id_prestamo INT NOT NULL,
  monto DECIMAL(8,2) NOT NULL,
  CONSTRAINT fk_multa_prestamo FOREIGN KEY (id_prestamo) REFERENCES prestamo (id_prestamo)
);

CREATE TABLE reserva (
  id_ejemplar INT NOT NULL,
  ci_socio INT NOT NULL,
  estado VARCHAR(10) NOT NULL,
  PRIMARY KEY (id_ejemplar, ci_socio),
  CONSTRAINT fk_reserva_ejemplar FOREIGN KEY (id_ejemplar) REFERENCES ejemplar (id_ejemplar)
);
