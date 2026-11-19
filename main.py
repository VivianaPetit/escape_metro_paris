"""

Dijkstra para Pierre y para Amélie (cada uno por su cuenta).
El tiempo de la operación es el del que más tarda (T = max(TP, TA)).
El más rápido se retrasa en su origen (T - su tiempo) minutos para llegar a su compuerta exactamente en el minuto T.

Todavía no se aplican las restricciones (colisiones, líneas clausuradas).
"""
import sys
from dijkstra import ruta_minima
from lector import ErrorEntrada, leer_entrada


def bloque_ruta(titulo, eventos, retraso, tiempo_viaje, etiqueta_destino):
    """Líneas del reporte para un personaje. Los minutos se desplazan `retraso`."""
    lineas = [f"[RUTA DE {titulo} (Tiempo total de viaje: {tiempo_viaje} min)]"]
    ultimo = len(eventos) - 1
    for i, (minuto, estacion, desc) in enumerate(eventos):
        if i == 0:
            desc = "Origen - Inicia Movimiento" if retraso > 0 else "Origen"
        if i == ultimo:
            desc = etiqueta_destino if i > 0 else f"{desc}; {etiqueta_destino}"
        lineas.append(f"Minuto {minuto + retraso}: Estación {estacion} ({desc})")
    return lineas


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ruta_in = sys.argv[1] if len(sys.argv) > 1 else "input.txt"
    ruta_out = sys.argv[2] if len(sys.argv) > 2 else "output.txt"

    try:
        grafo, mision, _restricciones = leer_entrada(ruta_in)
    except (ErrorEntrada, OSError) as e:
        print(f"Error en la entrada: {e}")
        return 1

    # Paso 1: Dijkstra para cada personaje
    res_p = ruta_minima(grafo, mision.origen_pierre, mision.puerta_pierre)
    res_a = ruta_minima(grafo, mision.origen_amelie, mision.puerta_amelie)
    if res_p is None or res_a is None:
        quien = "Pierre" if res_p is None else "Amélie"
        texto = ("=== PLAN DE ESCAPE CONFIGURADO ===\n"
                 f"No existe camino para {quien}.\n\n"
                 "Resultado de Sincronización: FRACASO.\n")
        open(ruta_out, "w", encoding="utf-8").write(texto)
        print(texto)
        return 0
    tp, ev_p = res_p
    ta, ev_a = res_a

    # Paso 2: el tiempo de la operación es el del que más tarda
    T = max(tp, ta)

    # Paso 3: el más rápido espera en su origen la diferencia
    retraso_p = T - tp
    retraso_a = T - ta

    salida = ["=== PLAN DE ESCAPE CONFIGURADO ===",
              f"Tiempo Total de la Operación: {T} minutos", "",
              "[PROGRAMACIÓN DE SALIDAS]"]
    for nombre, r in (("Pierre", retraso_p), ("Amélie", retraso_a)):
        txt = f"* {nombre} arranca en el minuto: {r}"
        if r > 0:
            txt += f" (Debe esperar {r} minutos en su estación de origen)"
        salida.append(txt)
    if retraso_p == retraso_a:
        salida.append("* Desfase de salida: 0 minutos (ambos salen al mismo tiempo).")
    else:
        tarde, temprano = ("Pierre", "Amélie") if retraso_p > retraso_a else ("Amélie", "Pierre")
        salida.append(f"* Desfase de salida: {tarde} debe retrasar su salida exactamente "
                      f"{abs(retraso_p - retraso_a)} minutos respecto a {temprano} para "
                      f"garantizar la llegada simultánea al búnker a los {T} minutos "
                      f"de iniciada la operación.")
    salida.append("")
    salida += bloque_ruta("PIERRE", ev_p, retraso_p, tp, "Destino Compuerta D1")
    salida.append("")
    salida += bloque_ruta("AMÉLIE", ev_a, retraso_a, ta, "Destino Compuerta D2")
    salida += ["", f"Resultado de Sincronización: ÉXITO. Llegada simultánea en el minuto {T}."]
    texto = "\n".join(salida) + "\n"

    with open(ruta_out, "w", encoding="utf-8") as f:
        f.write(texto)
    print(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
