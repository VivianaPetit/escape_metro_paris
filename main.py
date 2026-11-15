import sys
from lector import ErrorEntrada, leer_entrada


def main() -> int:
    ruta = sys.argv[1] if len(sys.argv) > 1 else "input.txt"

    try:
        grafo, mision, rest = leer_entrada(ruta)
    except (ErrorEntrada, OSError) as e:
        print(f"Error en la entrada: {e}")
        return 1

    print(f"Estaciones: {grafo.n_estaciones} | Túneles: {grafo.n_tuneles}")

    print(f"Pierre: {mision.origen_pierre} -> D1 en {mision.puerta_pierre}")
    print(f"Amélie: {mision.origen_amelie} -> D2 en {mision.puerta_amelie}")

    print(f"Líneas dobles: {rest.lineas_dobles or 'ninguna'}")
    print(f"Cierres de transbordo: {rest.cierres or 'ninguno'}")
    print(f"Semilla de Silvie: {rest.semilla}")

    print("\nLista de adyacencia:")
    for v in sorted(grafo.estaciones()):
        salidas = [
            f"{e.destino}({e.linea}, {e.peso}"
            + (f"->{rest.peso(e)}" if rest.peso(e) != e.peso else "")
            + ")"
            for e in grafo.vecinos(v)
        ]
        print(f"Estación {v} [transbordo {grafo.tiempo_transbordo(v)} min] -> {', '.join(salidas) or '-'}")

    print("\nTransbordo L1->L4 en minutos [5,6] permitido?",
          rest.transbordo_permitido("L1", "L4", 5, 6))
    print("Transbordo L1->L4 en minutos [10,11] permitido?",
          rest.transbordo_permitido("L1", "L4", 10, 11))

    return 0


if __name__ == "__main__":
    sys.exit(main())