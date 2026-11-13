"""Cálculo de movimientos individuales en el grafo del metro."""

from grafo import Arista, GrafoMetro
from restricciones import Restricciones


class Movimiento:
    """Un túnel posible con sus tiempos de transbordo, salida y llegada."""

    arista: Arista
    minuto_inicio: int
    minuto_salida: int
    minuto_llegada: int
    tiempo_transbordo: int
    tiempo_viaje: int

    def __init__(
        self,
        arista: Arista,
        minuto_inicio: int,
        minuto_salida: int,
        minuto_llegada: int,
        tiempo_transbordo: int,
        tiempo_viaje: int,
    ) -> None:
        # Se asignan los datos explícitamente para no depender de dataclasses.
        self.arista = arista
        self.minuto_inicio = minuto_inicio
        self.minuto_salida = minuto_salida
        self.minuto_llegada = minuto_llegada
        self.tiempo_transbordo = tiempo_transbordo
        self.tiempo_viaje = tiempo_viaje


def movimientos_posibles(
    grafo: GrafoMetro,
    restricciones: Restricciones,
    estacion: int,
    linea_actual: str | None,
    minuto_actual: int,
) -> list[Movimiento]:
    """Devuelve los movimientos legales desde la estación en ese minuto.

    El minuto actual representa la llegada a la estación. Un cambio de línea
    requiere el tiempo de transbordo de esa estación y solo se permite si ese
    intervalo no se cruza con un cierre. El primer túnel del recorrido no
    requiere transbordo.
    """
    if not grafo.existe(estacion):
        raise ValueError(f"La estación {estacion} no existe en el grafo")
    if minuto_actual < 0:
        raise ValueError("El minuto actual no puede ser negativo")

    posibles: list[Movimiento] = []
    for arista in grafo.vecinos(estacion):
        cambio_linea = linea_actual is not None and arista.linea != linea_actual

        # Solo se paga el tiempo de estación al cambiar desde una línea previa.
        tiempo_transbordo = (
            grafo.tiempo_transbordo(estacion) if cambio_linea else 0
        )
        minuto_salida = minuto_actual + tiempo_transbordo

        # Los intervalos de cierre son inclusivos y afectan a cualquiera de
        # las líneas que participan en el transbordo.
        if cambio_linea and not restricciones.transbordo_permitido(
            linea_actual,
            arista.linea,
            minuto_actual,
            minuto_salida,
        ):
            continue

        # El peso efectivo incluye el retraso configurado para esa línea.
        tiempo_viaje = restricciones.peso(arista)
        posibles.append(
            Movimiento(
                arista=arista,
                minuto_inicio=minuto_actual,
                minuto_salida=minuto_salida,
                minuto_llegada=minuto_salida + tiempo_viaje,
                tiempo_transbordo=tiempo_transbordo,
                tiempo_viaje=tiempo_viaje,
            )
        )

    return posibles
