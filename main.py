"""Punto de entrada: lee la red y coordina las rutas de Pierre y Amélie."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from buscador_rutas import (
    NodoRuta,
    PlanSincronizado,
    minutos_espera,
    minuto_primera_salida,
    planificar_sincronizacion,
)
from red_metro import ErrorEntrada, GrafoMetro, Mision, Restricciones, leer_entrada


def _argumentos() -> argparse.Namespace:
    """Define los argumentos de consola para entrada, salida y modo visual."""
    parser = argparse.ArgumentParser(
        description="Planifica el escape en el Metro de París."
    )
    parser.add_argument(
        "entrada",
        nargs="?",
        default="input.txt",
        help="archivo de la red y de la misión (por defecto: input.txt)",
    )
    parser.add_argument(
        "--salida",
        default="output.txt",
        help="archivo donde se guarda el reporte (por defecto: output.txt)",
    )
    parser.add_argument(
        "--sin-grafica",
        action="store_true",
        help="ejecuta solo el análisis de consola, sin abrir la ventana visual",
    )
    return parser.parse_args()


def _descripcion_ruta(
    nombre: str, ruta: list[NodoRuta], destino: str, tiempo_total: int
) -> list[str]:
    """Convierte una ruta cronometrada en líneas detalladas para el reporte."""
    lineas = [f"[RUTA DE {nombre.upper()}]"]
    if not ruta:
        return lineas + ["  No se encontró una ruta."]

    lineas.append(f"  Origen: estación {ruta[0].estacion}, minuto 0.")
    llegada = next(
        (paso for paso in ruta if paso.evento == "Destino"), ruta[-1]
    )
    indice_llegada = ruta.index(llegada)
    for indice, paso in enumerate(ruta[1:indice_llegada + 1], start=1):
        if paso.arista is not None:
            minuto_salida = (
                paso.minuto_salida
                if paso.minuto_salida is not None
                else paso.minuto
            )
            anterior = ruta[indice - 1]
            if minuto_salida > anterior.minuto:
                demora = minuto_salida - anterior.minuto
                tipo_espera = (
                    "transbordo"
                    if anterior.linea is not None
                    and anterior.linea != paso.arista.linea
                    else "espera"
                )
                lineas.append(
                    f"  Minuto {anterior.minuto}: {tipo_espera} de "
                    f"{demora} min en la estación {anterior.estacion}."
                )
            texto = (
                f"  Minuto {minuto_salida}: sale de {paso.arista.origen} "
                f"por {paso.arista.linea}"
            )
            if paso.evento != "Destino":
                texto += (
                    f"; llega a {paso.estacion} en el minuto {paso.minuto}."
                )
            else:
                texto += "."
            lineas.append(texto)
        elif paso.evento.startswith("Espera"):
            lineas.append(
                f"  Minuto {paso.minuto}: espera en la estación {paso.estacion}."
            )
    lineas.append(
        f"  Minuto {llegada.minuto}: llega a la puerta {destino} "
        f"(estación {llegada.estacion})."
    )
    if tiempo_total > llegada.minuto:
        lineas.append(
            f"  Espera en la puerta hasta la llegada simultánea "
            f"del minuto {tiempo_total}."
        )
    return lineas


def _descripcion_salidas(plan: PlanSincronizado) -> list[str]:
    """Explica el desfase ideal, los horarios aplicados y el riesgo acumulado."""
    duracion_base = max(
        plan.duracion_minima_pierre,
        plan.duracion_minima_amelie,
    )
    demora_pierre = duracion_base - plan.duracion_minima_pierre
    demora_amelie = duracion_base - plan.duracion_minima_amelie
    riesgo_pierre = minutos_espera(plan.ruta_pierre)
    riesgo_amelie = minutos_espera(plan.ruta_amelie)

    return [
        "[PROGRAMACIÓN DE SALIDAS Y RIESGO]",
        "  Duración individual mínima sin coordinar: "
        f"Pierre {plan.duracion_minima_pierre} min; "
        f"Amélie {plan.duracion_minima_amelie} min.",
        "  Desfase teórico sin conflictos: "
        f"Pierre inicia en el minuto {demora_pierre}; "
        f"Amélie inicia en el minuto {demora_amelie}.",
        "  Primera salida en túnel del plan conjunto: "
        f"Pierre, minuto {minuto_primera_salida(plan.ruta_pierre)}; "
        f"Amélie, minuto {minuto_primera_salida(plan.ruta_amelie)}. "
        "Este horario puede ajustarse para evitar colisiones.",
        "  Riesgo (1 punto por minuto de espera en estación): "
        f"Pierre {riesgo_pierre}; Amélie {riesgo_amelie}; "
        f"total {riesgo_pierre + riesgo_amelie} puntos.",
        "",
    ]


def crear_reporte(
    grafo_estaciones: int,
    grafo_tuneles: int,
    mision: Mision,
    plan: PlanSincronizado,
) -> str:
    """Genera el informe de rutas y llegada simultánea."""
    lineas = [
        "=== PLAN DE ESCAPE EN EL METRO DE PARÍS ===",
        f"Estaciones: {grafo_estaciones} | túneles dirigidos: {grafo_tuneles}",
        f"Pierre: estación {mision.origen_pierre} -> puerta D1, "
        f"estación {mision.puerta_pierre}.",
        f"Amélie: estación {mision.origen_amelie} -> puerta D2, "
        f"estación {mision.puerta_amelie}.",
        f"Tiempo de llegada simultánea: {plan.tiempo_total} minutos.",
        "",
    ]
    lineas.extend(_descripcion_salidas(plan))
    lineas.extend(
        _descripcion_ruta(
            "Pierre", plan.ruta_pierre, "D1", plan.tiempo_total
        )
    )
    lineas.append("")
    lineas.extend(
        _descripcion_ruta(
            "Amélie", plan.ruta_amelie, "D2", plan.tiempo_total
        )
    )
    lineas.extend(
        [
            "",
            "RESULTADO: ÉXITO. Pierre y Amélie llegan simultáneamente "
            "a sus puertas sin colisiones.",
        ]
    )
    return "\n".join(lineas) + "\n"


def _mostrar_grafica(
    grafo: GrafoMetro,
    mision: Mision,
    plan: PlanSincronizado,
    restricciones: Restricciones,
) -> None:
    """Importa e inicia la visualización sin cargarla en modo texto."""
    from visualizador import mostrar_visualizacion

    mostrar_visualizacion(grafo, mision, plan, restricciones)


def main() -> int:
    """Ejecuta el flujo completo y devuelve un código de estado para la consola."""
    argumentos = _argumentos()
    try:
        grafo, mision, restricciones = leer_entrada(argumentos.entrada)
    except (ErrorEntrada, OSError) as error:
        print(f"Error en la entrada: {error}", file=sys.stderr)
        return 1

    plan = planificar_sincronizacion(
        grafo,
        restricciones,
        mision.origen_pierre,
        mision.origen_amelie,
        mision.puerta_pierre,
        mision.puerta_amelie,
    )
    if plan is None:
        mensaje = (
            "No se encontró una llegada simultánea y sin colisiones entre "
            "Pierre y Amélie dentro del horizonte de búsqueda."
        )
        print(mensaje, file=sys.stderr)
        try:
            Path(argumentos.salida).write_text(mensaje + "\n", encoding="utf-8")
        except OSError as error:
            print(f"No se pudo escribir el reporte: {error}", file=sys.stderr)
        return 1

    reporte = crear_reporte(
        grafo.n_estaciones,
        grafo.n_tuneles,
        mision,
        plan,
    )
    print(reporte, end="")

    try:
        Path(argumentos.salida).write_text(reporte, encoding="utf-8")
    except OSError as error:
        print(f"No se pudo escribir el reporte: {error}", file=sys.stderr)
        return 1

    if not argumentos.sin_grafica:
        try:
            _mostrar_grafica(grafo, mision, plan, restricciones)
        except RuntimeError as error:
            print(f"No se pudo abrir la ventana gráfica: {error}", file=sys.stderr)
            print("Puedes usar --sin-grafica para ejecutar solo el reporte.")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
