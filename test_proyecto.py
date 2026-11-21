"""Pruebas de posiciones visuales, sincronización e informe de rutas."""

from __future__ import annotations

import unittest

from buscador_rutas import (
    NodoRuta,
    RastroEspacioTemporal,
    minutos_espera,
    minuto_primera_salida,
    planificar_sincronizacion,
)
from main import crear_reporte
from red_metro import (
    Arista,
    GrafoMetro,
    Restricciones,
    leer_entrada,
    movimientos_posibles,
)
from visualizador import posicion_en_minuto


class PruebasPosicionesYPlanificacion(unittest.TestCase):
    """Comprueba el horario, las colisiones y la representación de las rutas."""

    def nuevo_grafo(self) -> tuple[GrafoMetro, Restricciones]:
        """Construye una red pequeña para probar movimientos y restricciones."""
        grafo = GrafoMetro()
        grafo.agregar_estacion(1, 2)
        grafo.agregar_estacion(2, 3)
        grafo.agregar_estacion(3, 1)
        grafo.agregar_tunel(1, 2, 4, "L1")
        grafo.agregar_tunel(2, 3, 5, "L4")
        grafo.agregar_tunel(2, 1, 4, "L1")
        return grafo, Restricciones()

    def test_primer_tunel_no_requiere_transbordo(self) -> None:
        grafo, restricciones = self.nuevo_grafo()
        movimiento = movimientos_posibles(
            grafo, restricciones, 1, None, 0
        )[0]
        self.assertEqual(movimiento.minuto_salida, 0)
        self.assertEqual(movimiento.minuto_llegada, 4)
        self.assertEqual(movimiento.tiempo_transbordo, 0)

    def test_continuidad_en_la_misma_linea(self) -> None:
        grafo, restricciones = self.nuevo_grafo()
        movimiento = next(
            opcion
            for opcion in movimientos_posibles(
                grafo, restricciones, 2, "L1", 4
            )
            if opcion.arista.linea == "L1"
        )
        self.assertEqual(movimiento.minuto_salida, 4)
        self.assertEqual(movimiento.minuto_llegada, 8)

    def test_cambio_de_linea_suma_transbordo(self) -> None:
        grafo, restricciones = self.nuevo_grafo()
        movimiento = next(
            opcion
            for opcion in movimientos_posibles(
                grafo, restricciones, 2, "L1", 4
            )
            if opcion.arista.linea == "L4"
        )
        self.assertEqual(movimiento.tiempo_transbordo, 3)
        self.assertEqual(movimiento.minuto_salida, 7)
        self.assertEqual(movimiento.minuto_llegada, 12)

    def test_cierre_solapado_bloquea_transbordo(self) -> None:
        grafo, restricciones = self.nuevo_grafo()
        restricciones.cierres.append(("L4", 5, 6))
        lineas = {
            movimiento.arista.linea
            for movimiento in movimientos_posibles(
                grafo, restricciones, 2, "L1", 4
            )
        }
        self.assertNotIn("L4", lineas)
        self.assertIn("L1", lineas)

    def test_cierre_terminado_no_bloquea_transbordo(self) -> None:
        grafo, restricciones = self.nuevo_grafo()
        restricciones.cierres.append(("L4", 5, 6))
        lineas = {
            movimiento.arista.linea
            for movimiento in movimientos_posibles(
                grafo, restricciones, 2, "L1", 10
            )
        }
        self.assertIn("L4", lineas)

    def test_linea_doble_duplica_tiempo(self) -> None:
        grafo, restricciones = self.nuevo_grafo()
        restricciones.lineas_dobles.add("L4")
        movimiento = next(
            opcion
            for opcion in movimientos_posibles(
                grafo, restricciones, 2, "L4", 4
            )
            if opcion.arista.linea == "L4"
        )
        self.assertEqual(movimiento.tiempo_viaje, 10)
        self.assertEqual(movimiento.minuto_llegada, 14)

    def test_movimiento_rechaza_estacion_o_minuto_invalidos(self) -> None:
        grafo, restricciones = self.nuevo_grafo()
        for estacion, minuto in ((99, 0), (1, -1)):
            with self.subTest(estacion=estacion, minuto=minuto):
                with self.assertRaises(ValueError):
                    movimientos_posibles(
                        grafo, restricciones, estacion, None, minuto
                    )

    def test_posicion_intermedia_en_tunel(self) -> None:
        """La posición se interpola entre las estaciones de un viaje."""
        origen = NodoRuta(0, 1, None, "Origen")
        llegada = NodoRuta(
            4, 2, "L1", "Viaje L1", origen, Arista(1, 2, 4, "L1"), 0
        )

        posicion = posicion_en_minuto([origen, llegada], 2)

        self.assertEqual(posicion.tipo, "tunel")
        self.assertEqual((posicion.origen, posicion.destino), (1, 2))
        self.assertEqual(posicion.progreso, 0.5)

    def test_calcula_salida_inicial_y_minutos_de_riesgo(self) -> None:
        """Las esperas en estaciones suman riesgo y fijan la salida efectiva."""
        origen = NodoRuta(0, 1, None, "Origen")
        espera_uno = NodoRuta(1, 1, None, "Espera", origen)
        espera_dos = NodoRuta(2, 1, None, "Espera", espera_uno)
        llegada = NodoRuta(
            4, 2, "L1", "Destino", espera_dos, Arista(1, 2, 2, "L1"), 2
        )
        ruta = [origen, espera_uno, espera_dos, llegada]

        self.assertEqual(minuto_primera_salida(ruta), 2)
        self.assertEqual(minutos_espera(ruta), 2)

    def test_plan_de_ejemplo_sin_colisiones_entre_personajes(self) -> None:
        """La entrada encuentra rutas sincronizadas sin cruces entre fugitivos."""
        grafo, mision, restricciones = leer_entrada("input.txt")
        plan = planificar_sincronizacion(
            grafo,
            restricciones,
            mision.origen_pierre,
            mision.origen_amelie,
            mision.puerta_pierre,
            mision.puerta_amelie,
        )

        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.ruta_pierre[-1].minuto, plan.tiempo_total)
        self.assertEqual(plan.ruta_amelie[-1].minuto, plan.tiempo_total)

        rastro_pierre = RastroEspacioTemporal()
        rastro_pierre.registrar_ruta(
            plan.ruta_pierre, hasta_minuto=plan.tiempo_total
        )
        rastro_amelie = RastroEspacioTemporal()
        rastro_amelie.registrar_ruta(
            plan.ruta_amelie, hasta_minuto=plan.tiempo_total
        )
        minutos_compartidos = set(rastro_pierre.estaciones_ocupadas) & set(
            rastro_amelie.estaciones_ocupadas
        )
        self.assertFalse(
            any(
                rastro_pierre.estaciones_ocupadas[minuto]
                & rastro_amelie.estaciones_ocupadas[minuto]
                for minuto in minutos_compartidos
            )
        )
        self.assertFalse(
            any(
                rastro_pierre.colisiona_tunel(inicio, fin, origen, destino)
                for inicio, fin, origen, destino
                in rastro_amelie.tuneles_ocupados
            )
        )

    def test_minimiza_llegada_comun_en_rutas_independientes(self) -> None:
        """La llegada simultánea es la más temprana si no hay conflictos."""
        grafo = GrafoMetro()
        for estacion in range(1, 5):
            grafo.agregar_estacion(estacion, 0)
        grafo.agregar_tunel(1, 2, 2, "L1")
        grafo.agregar_tunel(3, 4, 3, "L2")

        plan = planificar_sincronizacion(
            grafo,
            Restricciones(),
            origen_pierre=1,
            origen_amelie=3,
            puerta_pierre=2,
            puerta_amelie=4,
        )

        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.tiempo_total, 3)
        self.assertEqual(plan.ruta_pierre[-1].minuto, 3)
        self.assertEqual(plan.ruta_amelie[-1].minuto, 3)
        self.assertEqual(plan.duracion_minima_pierre, 2)
        self.assertEqual(plan.duracion_minima_amelie, 3)

    def test_reporte_muestra_desfase_y_riesgo(self) -> None:
        """El informe incluye los horarios y el riesgo acumulado."""
        grafo, mision, restricciones = leer_entrada("input.txt")
        plan = planificar_sincronizacion(
            grafo,
            restricciones,
            mision.origen_pierre,
            mision.origen_amelie,
            mision.puerta_pierre,
            mision.puerta_amelie,
        )
        self.assertIsNotNone(plan)
        assert plan is not None

        reporte = crear_reporte(
            grafo.n_estaciones,
            grafo.n_tuneles,
            mision,
            plan,
        )

        self.assertIn("[PROGRAMACIÓN DE SALIDAS Y RIESGO]", reporte)
        self.assertIn(
            "RESULTADO: ÉXITO. Pierre y Amélie llegan simultáneamente",
            reporte,
        )
        referencia = max(
            plan.duracion_minima_pierre,
            plan.duracion_minima_amelie,
        )
        self.assertIn(
            "Desfase teórico sin conflictos: "
            f"Pierre inicia en el minuto "
            f"{referencia - plan.duracion_minima_pierre}; "
            f"Amélie inicia en el minuto "
            f"{referencia - plan.duracion_minima_amelie}.",
            reporte,
        )
        self.assertIn(
            "Primera salida en túnel del plan conjunto: "
            f"Pierre, minuto {minuto_primera_salida(plan.ruta_pierre)}; "
            f"Amélie, minuto {minuto_primera_salida(plan.ruta_amelie)}.",
            reporte,
        )
        riesgo_pierre = minutos_espera(plan.ruta_pierre)
        riesgo_amelie = minutos_espera(plan.ruta_amelie)
        self.assertIn(
            "Pierre {0}; Amélie {1}; total {2} puntos.".format(
                riesgo_pierre,
                riesgo_amelie,
                riesgo_pierre + riesgo_amelie,
            ),
            reporte,
        )


if __name__ == "__main__":
    unittest.main()
