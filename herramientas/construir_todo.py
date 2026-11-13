"""Reconstruye todo lo derivado: modelo Word, tablero, ejemplos ficticios y demostración."""
import pathlib
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
for paso in ["generar_modelo_word.py", "construir_tablero.py", "generar_ejemplos.py", "construir_tablero.py"]:
    print(f"== {paso}")
    subprocess.run([sys.executable, str(RAIZ / "herramientas" / paso)], check=True)
