import sys
from lector import ErrorEntrada, leer_entrada
from buscador_rutas import Planificador, RastroEspacioTemporal


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

    planificador = Planificador(grafo, rest)

    # 1. Rutas base
    nodo_p = planificador.buscar_ruta_individual(mision.origen_pierre, mision.puerta_pierre)
    nodo_a = planificador.buscar_ruta_individual(mision.origen_amelie, mision.puerta_amelie)

    if not nodo_p or not nodo_a:
        print("\nError: No hay ruta hacia el búnker para uno o ambos personajes.")
        return 1

    ruta_p_final = planificador.reconstruir_ruta(nodo_p)
    tiempo_p = ruta_p_final[-1].minuto
    tiempo_a = planificador.reconstruir_ruta(nodo_a)[-1].minuto

    # 2. Bucle de sincronización
    tiempo_operacion = max(tiempo_p, tiempo_a)
    ruta_a_final = None

    while True:
        espera_p = tiempo_operacion - tiempo_p
        espera_a = tiempo_operacion - tiempo_a
        
        rastro = RastroEspacioTemporal()
        rastro.registrar_ruta(ruta_p_final, espera_p)
        
        nodo_final_a = planificador.buscar_ruta_sin_colision(
            mision.origen_amelie, mision.puerta_amelie, espera_a, rastro
        )
        
        if nodo_final_a and nodo_final_a.minuto == tiempo_operacion:
            ruta_a_final = planificador.reconstruir_ruta(nodo_final_a)
            break
        
        tiempo_operacion += 1
        if tiempo_operacion > 1440:
            print("\nImposible sincronizar sin colisiones.")
            return 1

    # 3. Reporte final
    print("\n" + "="*40)
    print("=== PLAN DE ESCAPE CONFIGURADO ===")
    print(f"Tiempo Total de la Operación: {tiempo_operacion} minutos\n")
    
    print("[PROGRAMACIÓN DE SALIDAS]")
    print(f"* Pierre arranca en el minuto: {espera_p}" + (f" (Espera {espera_p} min)" if espera_p > 0 else ""))
    print(f"* Amélie arranca en el minuto: {espera_a}" + (f" (Espera {espera_a} min)" if espera_a > 0 else ""))

    planificador.imprimir_ruta("Pierre", ruta_p_final, espera_p)
    
    tiempo_viaje_a = ruta_a_final[-1].minuto - ruta_a_final[0].minuto
    print(f"\n[RUTA DE AMÉLIE (Tiempo total de viaje: {tiempo_viaje_a} min)]")
    
    for paso in ruta_a_final:
        if paso.evento == "Origen":
            estado = f"Inicia tras {espera_a} min de espera" if espera_a > 0 else "Origen"
            print(f"Minuto {paso.minuto}: Estación {paso.estacion} ({estado})")
        elif paso.evento == "Destino":
            print(f"Minuto {paso.minuto}: Estación {paso.estacion} (Destino Compuerta D2)")
        else:
            print(f"Minuto {paso.minuto}: Estación {paso.estacion} ({paso.evento})")

    print(f"\nResultado de Sincronización: ÉXITO. Llegada simultánea en el minuto {tiempo_operacion}.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())