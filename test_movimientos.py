"""Pruebas estándar para las reglas temporales de movimientos."""

from grafo import GrafoMetro
from movimientos import movimientos_posibles
from restricciones import Restricciones


def nuevo_grafo() -> tuple[GrafoMetro, Restricciones]:
    """Construye la misma red pequeña para cada comprobación independiente."""
    grafo = GrafoMetro()
    grafo.agregar_estacion(1, 2)
    grafo.agregar_estacion(2, 3)
    grafo.agregar_estacion(3, 1)
    grafo.agregar_tunel(1, 2, 4, "L1")
    grafo.agregar_tunel(2, 3, 5, "L4")
    grafo.agregar_tunel(2, 1, 4, "L1")
    return grafo, Restricciones()


def comprobar_primer_tunel_sin_transbordo() -> None:
    """El primer túnel sale inmediatamente y usa su peso original."""
    grafo, restricciones = nuevo_grafo()
    movimiento = movimientos_posibles(
        grafo, restricciones, 1, None, 0
    )[0]

    assert movimiento.minuto_salida == 0
    assert movimiento.minuto_llegada == 4
    assert movimiento.tiempo_transbordo == 0


def comprobar_continuidad_en_la_misma_linea() -> None:
    """Seguir por la línea actual no consume tiempo de transbordo."""
    grafo, restricciones = nuevo_grafo()
    movimientos = movimientos_posibles(grafo, restricciones, 2, "L1", 4)
    movimiento = next(
        opcion for opcion in movimientos if opcion.arista.linea == "L1"
    )

    assert movimiento.minuto_salida == 4
    assert movimiento.minuto_llegada == 8


def comprobar_cambio_de_linea() -> None:
    """Cambiar de línea suma el tiempo de transbordo de la estación."""
    grafo, restricciones = nuevo_grafo()
    movimientos = movimientos_posibles(grafo, restricciones, 2, "L1", 4)
    movimiento = next(
        opcion for opcion in movimientos if opcion.arista.linea == "L4"
    )

    assert movimiento.tiempo_transbordo == 3
    assert movimiento.minuto_salida == 7
    assert movimiento.minuto_llegada == 12


def comprobar_cierre_durante_transbordo() -> None:
    """Un cierre que se solapa bloquea solo el cambio de línea afectado."""
    grafo, restricciones = nuevo_grafo()
    restricciones.cierres.append(("L4", 5, 6))
    lineas = [
        movimiento.arista.linea
        for movimiento in movimientos_posibles(
            grafo, restricciones, 2, "L1", 4
        )
    ]

    assert "L4" not in lineas
    assert "L1" in lineas


def comprobar_cierre_fuera_del_transbordo() -> None:
    """Un cierre anterior no bloquea un transbordo posterior."""
    grafo, restricciones = nuevo_grafo()
    restricciones.cierres.append(("L4", 5, 6))
    lineas = [
        movimiento.arista.linea
        for movimiento in movimientos_posibles(
            grafo, restricciones, 2, "L1", 10
        )
    ]

    assert "L4" in lineas


def comprobar_tiempo_de_linea_doble() -> None:
    """Una línea marcada como doble duplica el peso de sus túneles."""
    grafo, restricciones = nuevo_grafo()
    restricciones.lineas_dobles.add("L4")
    movimiento = next(
        opcion
        for opcion in movimientos_posibles(
            grafo, restricciones, 2, "L4", 4
        )
        if opcion.arista.linea == "L4"
    )

    assert movimiento.tiempo_viaje == 10
    assert movimiento.minuto_llegada == 14


def comprobar_entradas_invalidas() -> None:
    """La función rechaza estaciones desconocidas y minutos negativos."""
    grafo, restricciones = nuevo_grafo()

    for estacion, minuto in ((99, 0), (1, -1)):
        try:
            movimientos_posibles(
                grafo, restricciones, estacion, None, minuto
            )
        except ValueError:
            continue
        raise AssertionError("Se esperaba ValueError para una entrada inválida")


if __name__ == "__main__":
    # Ejecutar el archivo ejecuta todas las comprobaciones sin un test runner.
    comprobaciones = (
        comprobar_primer_tunel_sin_transbordo,
        comprobar_continuidad_en_la_misma_linea,
        comprobar_cambio_de_linea,
        comprobar_cierre_durante_transbordo,
        comprobar_cierre_fuera_del_transbordo,
        comprobar_tiempo_de_linea_doble,
        comprobar_entradas_invalidas,
    )
    for comprobar in comprobaciones:
        comprobar()
    print(f"{len(comprobaciones)} comprobaciones correctas.")
