"""
Ruta de menor tiempo de un personaje, usando Dijkstra.

Detalle importante: el tiempo de transbordo cuenta como costo. Por eso un
nodo del Dijkstra no es solo la estación, sino el par (estación, línea con
la que se llegó):

    Tomar un túnel de la misma línea con la que se llegó cuesta su tiempo de viaje.
    Tomar un túnel de otra línea cuesta tiempo de transbordo de la estación + tiempo de viaje.
    Al salir del origen no hay línea previa (None), así que no hay transbordo.

Por ahora no se aplican restricciones (líneas dobles / clausuradas).
"""
from __future__ import annotations
import heapq

INF = float("inf")

def ruta_minima(grafo, origen: int, destino: int):
    """Devuelve (tiempo_total, eventos) o None si no hay camino.

    `eventos` es una lista de tuplas (minuto_relativo, estación, descripción),
    donde el minuto 0 es la salida del origen. Descripciones:
        'Origen'
        'Viaje L1'                 llegada a una estación por un túnel de L1
        'Termina Transbordo a L4'  fin del transbordo (aún en la misma estación)
    """
    inicio = (origen, None)
    dist = {inicio: 0}
    padre = {inicio: None}   # estado -> (estado_anterior, tiempo_transbordo, arista)
    heap = [(0, 0, inicio)]
    contador = 1             # desempate para que el heap nunca compare estados

    mejor_final = None
    while heap:
        d, _, estado = heapq.heappop(heap)
        if d > dist[estado]:
            continue
        v, linea = estado
        if v == destino:
            mejor_final = estado
            break
        for e in grafo.vecinos(v):
            tt = 0
            if linea is not None and linea != e.linea:
                tt = grafo.tiempo_transbordo(v)
            nuevo = (e.destino, e.linea)
            nd = d + tt + e.peso
            if nd < dist.get(nuevo, INF):
                dist[nuevo] = nd
                padre[nuevo] = (estado, tt, e)
                heapq.heappush(heap, (nd, contador, nuevo))
                contador += 1

    if mejor_final is None:
        return None

    # Reconstruir el camino hacia atrás
    pasos = []
    estado = mejor_final
    while padre[estado] is not None:
        anterior, tt, e = padre[estado]
        pasos.append((tt, e))
        estado = anterior
    pasos.reverse()

    # Convertir a eventos con minutos relativos
    t = 0
    eventos = [(0, origen, "Origen")]
    for tt, e in pasos:
        if tt > 0:
            t += tt
            eventos.append((t, e.origen, f"Termina Transbordo a {e.linea}"))
        t += e.peso
        eventos.append((t, e.destino, f"Viaje {e.linea}"))
    return dist[mejor_final], eventos