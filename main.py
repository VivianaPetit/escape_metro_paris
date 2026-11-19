import sys
from lector import ErrorEntrada, leer_entrada


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ruta = sys.argv[1] if len(sys.argv) > 1 else "input.txt"

    # 1. Leer y validar el archivo
    try:
        grafo, mision, rest = leer_entrada(ruta)
    except (ErrorEntrada, OSError) as e:
        print(f"Error en la entrada: {e}")
        return 1

    # 2. Resumen del grafo (debe coincidir con la cabecera "N M" del input)
    print(f"Estaciones: {grafo.n_estaciones} | Túneles: {grafo.n_tuneles}")

    # 3. Misión
    print(f"Pierre: {mision.origen_pierre} -> D1 en {mision.puerta_pierre}")
    print(f"Amélie: {mision.origen_amelie} -> D2 en {mision.puerta_amelie}")

    # 4. Restricciones
    print(f"Líneas con tiempo doble: {sorted(rest.lineas_dobles) or 'ninguna'}")
    print(f"Cierres de transbordo: {rest.cierres or 'ninguno'}")

    # 5. Lista de adyacencia, con el peso efectivo (muestra peso->peso_doble si aplica)
    print("\nLista de adyacencia:")
    for v in sorted(grafo.estaciones()):
        salidas = []
        for e in grafo.vecinos(v):
            peso = f"{e.peso}->{rest.peso(e)}" if rest.peso(e) != e.peso else str(e.peso)
            salidas.append(f"{e.destino}({e.linea}, {peso})")
        print(f"  {v} [transbordo {grafo.tiempo_transbordo(v)} min] -> {', '.join(salidas) or '-'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
