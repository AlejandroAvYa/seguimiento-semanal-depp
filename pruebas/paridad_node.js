// Ejecuta el motor del tablero sobre un caso y entrega el resultado en JSON (lo usa test_paridad.py).
"use strict";
const fs = require("fs");
const path = require("path");
const raiz = path.resolve(__dirname, "..");
const motor = require(path.join(raiz, "tablero/src/motor.js"));
const docx = require(path.join(raiz, "tablero/src/docx.js"));
const modelo = JSON.parse(fs.readFileSync(path.join(raiz, "tablero/src/modelo_depp.json"), "utf8"));
const caso = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
let corte;
if (caso.lectura) {
  const anterior = caso.anterior ? motor.leerCorte(modelo, caso.anterior) : null;
  corte = motor.construirCorte(modelo, caso.lectura, caso.cut, anterior, caso.captura || null);
} else {
  corte = motor.leerCorte(modelo, caso.corte);
}
const ejecutiva = motor.minuta(modelo, corte, false);
const completa = motor.minuta(modelo, corte, true);
const salida = {
  corte: caso.lectura ? corte : null,
  summary: motor.analizar(modelo, corte).summary,
  ejecutiva, completa,
  docx: docx.cuerpoMinuta(ejecutiva),
  movimientos: motor.movimientos(modelo, corte).map(m => [m.tipo, m.fila.id, m.fecha, m.cambios])
};
process.stdout.write(JSON.stringify(salida));
