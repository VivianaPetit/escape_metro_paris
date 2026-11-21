"""Búsqueda de rutas y sincronización espacio-temporal de la misión."""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from itertools import count
from typing import TYPE_CHECKING

from red_metro import Arista, Movimiento, movimientos_posibles

if TYPE_CHECKING:
    from red_metro import GrafoMetro, Restricciones


@dataclass
class NodoRuta:
    """Un estado visitado por un personaje dentro de una ruta cronometrada."""

    minuto: int
    estacion: int
    linea: str | None
    evento: str
    previo: NodoRuta | None = None
    arista: Arista | None = None
    minuto_salida: int | None = None

    def __lt__(self, otro: NodoRuta) -> bool:
        """Permite que el heap atienda primero el estado de menor tiempo."""
        return self.minuto < otro.minuto


@dataclass
class PlanSincronizado:
    """Rutas coordinadas y tiempo de llegada simultánea al búnker."""

    ruta_pierre: list[NodoRuta]
    ruta_amelie: list[NodoRuta]
    tiempo_total: int
    duracion_minima_pierre: int
    duracion_minima_amelie: int


def minuto_primera_salida(ruta: list[NodoRuta]) -> int:
    """Devuelve el minuto en que la ruta toma su primer túnel."""
    for paso in ruta[1:]:
        if paso.arista is not None:
            return (
                paso.minuto_salida
                if paso.minuto_salida is not None
                else paso.minuto
            )
    return ruta[0].minuto if ruta else 0


def minutos_espera(ruta: list[NodoRuta]) -> int:
    """Cuenta minutos de espera expuesta, sin sumar viajes ni transbordos."""
    total = 0
    for anterior, paso in zip(ruta, ruta[1:]):
        if paso.arista is None and paso.evento.startswith("Espera"):
            total += max(0, paso.minuto - anterior.minuto)
    return total


class RastroEspacioTemporal:
    """Registra las estaciones y túneles ocupados en cada intervalo de tiempo."""

    def __init__(self) -> None:
        """Crea los índices de ocupación por minuto y los tramos de túnel."""
        self.estaciones_ocupadas: dict[int, set[int]] = {}
        self.tuneles_ocupados: list[tuple[int, int, int, int]] = []

    def _registrar_estacion(self, estacion: int, desde: int, hasta: int) -> None:
        """Marca una estación ocupada en todos los minutos del intervalo cerrado."""
        for minuto in range(desde, hasta + 1):
            self.estaciones_ocupadas.setdefault(minuto, set()).add(estacion)

    def registrar_ruta(
        self,
        ruta: list[NodoRuta],
        espera_inicial: int = 0,
        hasta_minuto: int | None = None,
    ) -> None:
        """Añade una ruta al rastro, incluyendo esperas y el tiempo de transbordo.

        Los minutos en una estación se consideran instantes discretos inclusivos.
        La ocupación de un túnel se representa con un intervalo semiabierto.
        """
        if not ruta:
            return

        primero = ruta[0]
        minuto_inicial = primero.minuto + espera_inicial
        self._registrar_estacion(primero.estacion, 0, minuto_inicial)

        for actual, siguiente in zip(ruta, ruta[1:]):
            minuto_actual = actual.minuto + espera_inicial
            minuto_siguiente = siguiente.minuto + espera_inicial

            if siguiente.arista is None:
                self._registrar_estacion(
                    actual.estacion, minuto_actual, minuto_siguiente
                )
                continue

            minuto_salida = (
                siguiente.minuto_salida
                if siguiente.minuto_salida is not None
                else actual.minuto
            ) + espera_inicial
            ultimo_minuto_en_estacion = (
                minuto_salida
                if minuto_salida == minuto_actual
                else minuto_salida - 1
            )
            self._registrar_estacion(
                actual.estacion, minuto_actual, ultimo_minuto_en_estacion
            )
            self.tuneles_ocupados.append(
                (
                    minuto_salida,
                    minuto_siguiente,
                    siguiente.arista.origen,
                    siguiente.arista.destino,
                )
            )
            self._registrar_estacion(
                siguiente.estacion, minuto_siguiente, minuto_siguiente
            )

        ultimo = ruta[-1]
        minuto_final = ultimo.minuto + espera_inicial
        if hasta_minuto is not None and hasta_minuto > minuto_final:
            self._registrar_estacion(
                ultimo.estacion, minuto_final, hasta_minuto
            )

    def colisiona_estacion(self, minuto: int, estacion: int) -> bool:
        """Indica si una estación está ocupada en el minuto exacto consultado."""
        return estacion in self.estaciones_ocupadas.get(minuto, set())

    def colisiona_estacion_intervalo(
        self, desde: int, hasta: int, estacion: int
    ) -> bool:
        """Indica si la estación está ocupada en algún minuto inclusivo."""
        return any(
            self.colisiona_estacion(minuto, estacion)
            for minuto in range(desde, hasta + 1)
        )

    def colisiona_tunel(
        self, t_ini: int, t_fin: int, origen: int, destino: int
    ) -> bool:
        """Comprueba cruces en un mismo túnel, aunque vayan en sentidos opuestos."""
        for r_ini, r_fin, r_origen, r_destino in self.tuneles_ocupados:
            mismo_tunel = (
                (origen == r_origen and destino == r_destino)
                or (origen == r_destino and destino == r_origen)
            )
            if mismo_tunel and max(t_ini, r_ini) < min(t_fin, r_fin):
                return True
        return False


class Planificador:
    """Calcula caminos mínimos y rutas seguras en el tiempo."""

    def __init__(self, grafo: GrafoMetro, restricciones: Restricciones) -> None:
        """Guarda la red y las reglas de circulación aplicables."""
        self.grafo = grafo
        self.rest = restricciones

    def _nodo_desde_movimiento(
        self, movimiento: Movimiento, previo: NodoRuta
    ) -> NodoRuta:
        """Crea el estado de llegada que conserva la arista y salida del túnel."""
        evento = f"Viaje {movimiento.arista.linea}"
        if movimiento.tiempo_transbordo:
            evento = f"Transbordo a {movimiento.arista.linea} y viaje"
        return NodoRuta(
            minuto=movimiento.minuto_llegada,
            estacion=movimiento.arista.destino,
            linea=movimiento.arista.linea,
            evento=evento,
            previo=previo,
            arista=movimiento.arista,
            minuto_salida=movimiento.minuto_salida,
        )

    def buscar_ruta_individual(
        self, origen: int, destino: int
    ) -> NodoRuta | None:
        """Devuelve la ruta más rápida entre dos estaciones, sin otras personas."""
        if not self.grafo.existe(origen) or not self.grafo.existe(destino):
            raise ValueError("El origen y el destino deben existir en el grafo")

        inicio = NodoRuta(0, origen, None, "Origen")
        frontera: list[NodoRuta] = [inicio]
        mejores: dict[tuple[int, str | None], int] = {(origen, None): 0}

        while frontera:
            actual = heapq.heappop(frontera)
            estado_actual = (actual.estacion, actual.linea)
            if actual.minuto > mejores.get(estado_actual, float("inf")):
                continue
            if actual.estacion == destino:
                return NodoRuta(
                    actual.minuto,
                    destino,
                    actual.linea,
                    "Destino",
                    actual,
                )

            for movimiento in movimientos_posibles(
                self.grafo,
                self.rest,
                actual.estacion,
                actual.linea,
                actual.minuto,
            ):
                nuevo = self._nodo_desde_movimiento(movimiento, actual)
                estado_nuevo = (nuevo.estacion, nuevo.linea)
                if nuevo.minuto < mejores.get(estado_nuevo, float("inf")):
                    mejores[estado_nuevo] = nuevo.minuto
                    heapq.heappush(frontera, nuevo)

        return None

    def buscar_ruta_sin_colision(
        self,
        origen: int,
        destino: int,
        espera_inicial: int,
        rastro: RastroEspacioTemporal,
        tiempo_minimo: int = 0,
        limite_minutos: int = 1440,
    ) -> NodoRuta | None:
        """Busca la llegada más temprana evitando ocupaciones ajenas.

        El personaje puede esperar en una estación. Los cambios de línea y los
        túneles se validan durante todo el intervalo, no solo al llegar.
        """
        if not self.grafo.existe(origen) or not self.grafo.existe(destino):
            raise ValueError("El origen y el destino deben existir en el grafo")
        if espera_inicial < 0 or tiempo_minimo < 0 or limite_minutos < 0:
            raise ValueError("Los minutos de búsqueda no pueden ser negativos")

        inicio = NodoRuta(0, origen, None, "Origen")
        if rastro.colisiona_estacion_intervalo(0, espera_inicial, origen):
            return None

        frontera: list[NodoRuta] = [inicio]
        visitados: set[tuple[int, str | None, int]] = set()

        while frontera:
            actual = heapq.heappop(frontera)
            estado = (actual.estacion, actual.linea, actual.minuto)
            if estado in visitados:
                continue
            visitados.add(estado)

            if actual.estacion == destino and actual.minuto >= tiempo_minimo:
                return NodoRuta(
                    actual.minuto,
                    destino,
                    actual.linea,
                    "Destino",
                    actual,
                )
            if actual.minuto >= limite_minutos:
                continue

            siguiente_minuto = actual.minuto + 1
            if (
                rastro.colisiona_estacion(siguiente_minuto, actual.estacion)
                is False
            ):
                espera = NodoRuta(
                    siguiente_minuto,
                    actual.estacion,
                    actual.linea,
                    "Espera",
                    actual,
                )
                heapq.heappush(frontera, espera)

            if actual.minuto < espera_inicial and actual.linea is None:
                continue

            for movimiento in movimientos_posibles(
                self.grafo,
                self.rest,
                actual.estacion,
                actual.linea,
                actual.minuto,
            ):
                if movimiento.minuto_llegada > limite_minutos:
                    continue
                ultimo_minuto_en_estacion = (
                    movimiento.minuto_salida
                    if movimiento.minuto_salida == actual.minuto
                    else movimiento.minuto_salida - 1
                )
                if rastro.colisiona_estacion_intervalo(
                    actual.minuto,
                    ultimo_minuto_en_estacion,
                    actual.estacion,
                ):
                    continue
                if rastro.colisiona_tunel(
                    movimiento.minuto_salida,
                    movimiento.minuto_llegada,
                    actual.estacion,
                    movimiento.arista.destino,
                ):
                    continue
                if rastro.colisiona_estacion(
                    movimiento.minuto_llegada, movimiento.arista.destino
                ):
                    continue
                heapq.heappush(
                    frontera, self._nodo_desde_movimiento(movimiento, actual)
                )

        return None

    def reconstruir_ruta(self, nodo_final: NodoRuta) -> list[NodoRuta]:
        """Reconstruye una ruta ordenada a partir de sus enlaces al predecesor."""
        ruta: list[NodoRuta] = []
        actual: NodoRuta | None = nodo_final
        while actual is not None:
            ruta.append(actual)
            actual = actual.previo
        return list(reversed(ruta))

    def imprimir_ruta(
        self, nombre: str, ruta: list[NodoRuta], espera_inicial: int = 0
    ) -> None:
        """Imprime las estaciones, esperas, transbordos y minutos de la ruta."""
        if not ruta:
            print(f"\n[RUTA DE {nombre.upper()}] No disponible.")
            return
        tiempo_viaje = ruta[-1].minuto - ruta[0].minuto
        print(f"\n[RUTA DE {nombre.upper()} (Tiempo total: {tiempo_viaje} min)]")
        for paso in ruta:
            minuto_real = paso.minuto + espera_inicial
            if paso.evento == "Origen":
                print(f"Minuto {minuto_real}: Estación {paso.estacion} (Origen)")
            elif paso.evento == "Destino":
                print(
                    f"Minuto {minuto_real}: Estación {paso.estacion} (Destino)"
                )
            else:
                print(
                    f"Minuto {minuto_real}: Estación {paso.estacion} "
                    f"({paso.evento})"
                )


@dataclass(frozen=True)
class _EstadoPersonaje:
    """Estado interno de un fugitivo: estación, transbordo o túnel."""

    modo: str
    estacion: int | None
    linea: str | None
    arista: Arista | None = None
    restante: int = 0
    viaje_pendiente: int = 0
    minuto_salida: int = 0


_ClaveEstado = tuple[int, _EstadoPersonaje, _EstadoPersonaje]


def _distancias_sin_transbordo(
    grafo: GrafoMetro, restricciones: Restricciones, destino: int
) -> dict[int, int]:
    """Calcula cotas inferiores de viaje ignorando el tiempo de transbordo."""
    distancias = {destino: 0}
    frontera = [(0, destino)]
    while frontera:
        distancia, estacion = heapq.heappop(frontera)
        if distancia != distancias.get(estacion):
            continue
        for arista in grafo.predecesores(estacion):
            candidata = distancia + restricciones.peso(arista)
            if candidata < distancias.get(arista.origen, float("inf")):
                distancias[arista.origen] = candidata
                heapq.heappush(frontera, (candidata, arista.origen))
    return distancias


def _estacion_del_estado(estado: _EstadoPersonaje) -> int | None:
    """Devuelve la estación ocupada, incluyendo el tiempo de transbordo."""
    if estado.modo in ("estacion", "transbordo"):
        return estado.estacion
    return None


def _cota_restante(
    estado: _EstadoPersonaje,
    destino: int,
    distancias: dict[int, int],
    restricciones: Restricciones,
) -> int:
    """Estima el tiempo restante con un costo optimista admisible."""
    if estado.modo == "tunel" and estado.arista is not None:
        return estado.restante + distancias.get(
            estado.arista.destino, 1_000_000_000
        )
    if estado.modo == "transbordo" and estado.arista is not None:
        return restricciones.peso(estado.arista) + distancias.get(
            estado.arista.destino, 1_000_000_000
        )
    if estado.estacion == destino:
        return 0
    if estado.estacion is None:
        return 1_000_000_000
    return distancias.get(estado.estacion, 1_000_000_000)


def _acciones_posibles(
    estado: _EstadoPersonaje,
    destino: int,
    minuto: int,
    grafo: GrafoMetro,
    restricciones: Restricciones,
) -> list[Movimiento | None]:
    """Genera espera, viaje o continuidad forzada de un personaje."""
    if estado.modo != "estacion" or estado.estacion is None:
        return [None]
    if estado.estacion == destino:
        return [None]
    return [
        None,
        *movimientos_posibles(
            grafo, restricciones, estado.estacion, estado.linea, minuto
        ),
    ]


def _avanzar_estado(
    estado: _EstadoPersonaje, accion: Movimiento | None
) -> tuple[_EstadoPersonaje, Arista | None]:
    """Avanza exactamente un minuto y devuelve el túnel usado en ese minuto."""
    if estado.modo == "transbordo":
        if estado.restante > 1:
            return (
                _EstadoPersonaje(
                    "transbordo",
                    estado.estacion,
                    estado.linea,
                    estado.arista,
                    estado.restante - 1,
                    estado.viaje_pendiente,
                    estado.minuto_salida,
                ),
                None,
            )
        return (
            _EstadoPersonaje(
                "tunel",
                None,
                estado.arista.linea if estado.arista else None,
                estado.arista,
                estado.viaje_pendiente,
                0,
                estado.minuto_salida,
            ),
            None,
        )

    if estado.modo == "tunel":
        if estado.restante > 1:
            return (
                _EstadoPersonaje(
                    "tunel",
                    None,
                    estado.linea,
                    estado.arista,
                    estado.restante - 1,
                    0,
                    estado.minuto_salida,
                ),
                estado.arista,
            )
        if estado.arista is None:
            raise ValueError("Un estado de túnel debe conservar su arista")
        return (
            _EstadoPersonaje(
                "estacion",
                estado.arista.destino,
                estado.arista.linea,
            ),
            estado.arista,
        )

    if accion is None:
        return estado, None

    arista = accion.arista
    if accion.tiempo_transbordo > 1:
        return (
            _EstadoPersonaje(
                "transbordo",
                arista.origen,
                estado.linea,
                arista,
                accion.tiempo_transbordo - 1,
                accion.tiempo_viaje,
                accion.minuto_salida,
            ),
            None,
        )
    if accion.tiempo_transbordo == 1:
        return (
            _EstadoPersonaje(
                "tunel",
                None,
                arista.linea,
                arista,
                accion.tiempo_viaje,
                0,
                accion.minuto_salida,
            ),
            None,
        )
    if accion.tiempo_viaje == 1:
        return (
            _EstadoPersonaje("estacion", arista.destino, arista.linea),
            arista,
        )
    return (
        _EstadoPersonaje(
            "tunel",
            None,
            arista.linea,
            arista,
            accion.tiempo_viaje - 1,
            0,
            accion.minuto_salida,
        ),
        arista,
    )


def _crear_paso_de_llegada(
    movimiento: Movimiento, previo: NodoRuta, destino: int
) -> NodoRuta:
    """Convierte una acción completada en un nodo de la ruta visible."""
    evento = (
        "Destino"
        if movimiento.arista.destino == destino
        else f"Viaje {movimiento.arista.linea}"
    )
    if movimiento.tiempo_transbordo and evento != "Destino":
        evento = f"Transbordo a {movimiento.arista.linea} y viaje"
    return NodoRuta(
        movimiento.minuto_llegada,
        movimiento.arista.destino,
        movimiento.arista.linea,
        evento,
        previo,
        movimiento.arista,
        movimiento.minuto_salida,
    )


def _reconstruir_rutas_conjuntas(
    clave_final: _ClaveEstado,
    padres: dict[
        _ClaveEstado,
        tuple[_ClaveEstado, Movimiento | None, Movimiento | None] | None,
    ],
    origen_pierre: int,
    origen_amelie: int,
    puerta_pierre: int,
    puerta_amelie: int,
) -> tuple[list[NodoRuta], list[NodoRuta]]:
    """Reconstruye ambas rutas a partir de las transiciones conjuntas."""
    transiciones: list[
        tuple[_ClaveEstado, _ClaveEstado, Movimiento | None, Movimiento | None]
    ] = []
    actual = clave_final
    while padres[actual] is not None:
        padre, accion_pierre, accion_amelie = padres[actual]
        transiciones.append((padre, actual, accion_pierre, accion_amelie))
        actual = padre
    transiciones.reverse()

    def reconstruir(
        indice: int, origen: int, destino: int
    ) -> list[NodoRuta]:
        """Traduce esperas y viajes de un personaje a nodos de ruta."""
        ruta = [NodoRuta(0, origen, None, "Origen")]
        movimiento_pendiente: Movimiento | None = None

        for previo, siguiente, accion_p, accion_a in transiciones:
            estado_previo = previo[indice + 1]
            estado_siguiente = siguiente[indice + 1]
            accion = accion_p if indice == 0 else accion_a
            minuto_siguiente = siguiente[0]

            if estado_previo.modo == "estacion":
                if accion is None:
                    evento = (
                        "Espera sincronizada"
                        if estado_previo.estacion == destino
                        else "Espera"
                    )
                    ruta.append(
                        NodoRuta(
                            minuto_siguiente,
                            estado_previo.estacion or origen,
                            estado_previo.linea,
                            evento,
                            ruta[-1],
                        )
                    )
                else:
                    movimiento_pendiente = accion
                    if estado_siguiente.modo == "estacion":
                        ruta.append(
                            _crear_paso_de_llegada(
                                accion, ruta[-1], destino
                            )
                        )
                        movimiento_pendiente = None
                continue

            if (
                estado_previo.modo == "tunel"
                and estado_siguiente.modo == "estacion"
                and movimiento_pendiente is not None
            ):
                ruta.append(
                    _crear_paso_de_llegada(
                        movimiento_pendiente, ruta[-1], destino
                    )
                )
                movimiento_pendiente = None

        return ruta

    return (
        reconstruir(0, origen_pierre, puerta_pierre),
        reconstruir(1, origen_amelie, puerta_amelie),
    )


def planificar_sincronizacion(
    grafo: GrafoMetro,
    restricciones: Restricciones,
    origen_pierre: int,
    origen_amelie: int,
    puerta_pierre: int,
    puerta_amelie: int,
    limite_minutos: int = 1440,
) -> PlanSincronizado | None:
    """Encuentra el plan global de llegada simultánea más temprana.

    Una búsqueda A* conjunta avanza a ambos personajes minuto a minuto. En cada
    estado genera esperas o movimientos, y descarta pares de acciones que los
    pondrían en la misma estación o en el mismo túnel.
    """
    planificador = Planificador(grafo, restricciones)
    final_pierre = planificador.buscar_ruta_individual(
        origen_pierre, puerta_pierre
    )
    final_amelie = planificador.buscar_ruta_individual(
        origen_amelie, puerta_amelie
    )
    if final_pierre is None or final_amelie is None:
        return None

    if limite_minutos < max(final_pierre.minuto, final_amelie.minuto):
        return None

    inicio_pierre = _EstadoPersonaje(
        "estacion", origen_pierre, None
    )
    inicio_amelie = _EstadoPersonaje(
        "estacion", origen_amelie, None
    )
    inicio: _ClaveEstado = (0, inicio_pierre, inicio_amelie)
    if origen_pierre == origen_amelie:
        return None

    distancias_pierre = _distancias_sin_transbordo(
        grafo, restricciones, puerta_pierre
    )
    distancias_amelie = _distancias_sin_transbordo(
        grafo, restricciones, puerta_amelie
    )

    def heuristica(
        estado_pierre: _EstadoPersonaje, estado_amelie: _EstadoPersonaje
    ) -> int:
        """Estima el tiempo restante hasta que ambos alcancen sus puertas."""
        return max(
            _cota_restante(
                estado_pierre,
                puerta_pierre,
                distancias_pierre,
                restricciones,
            ),
            _cota_restante(
                estado_amelie,
                puerta_amelie,
                distancias_amelie,
                restricciones,
            ),
        )

    turnos = count()
    frontera: list[tuple[int, int, int, _ClaveEstado]] = [
        (heuristica(inicio_pierre, inicio_amelie), 0, next(turnos), inicio)
    ]
    padres: dict[
        _ClaveEstado,
        tuple[_ClaveEstado, Movimiento | None, Movimiento | None] | None,
    ] = {inicio: None}
    visitados: set[_ClaveEstado] = set()
    clave_final: _ClaveEstado | None = None

    while frontera:
        _, minuto, _, clave = heapq.heappop(frontera)
        if clave in visitados:
            continue
        visitados.add(clave)
        _, estado_pierre, estado_amelie = clave

        if (
            estado_pierre.modo == "estacion"
            and estado_pierre.estacion == puerta_pierre
            and estado_amelie.modo == "estacion"
            and estado_amelie.estacion == puerta_amelie
        ):
            clave_final = clave
            break
        if minuto >= limite_minutos:
            continue

        acciones_pierre = _acciones_posibles(
            estado_pierre,
            puerta_pierre,
            minuto,
            grafo,
            restricciones,
        )
        acciones_amelie = _acciones_posibles(
            estado_amelie,
            puerta_amelie,
            minuto,
            grafo,
            restricciones,
        )
        for accion_pierre in acciones_pierre:
            siguiente_pierre, tunel_pierre = _avanzar_estado(
                estado_pierre, accion_pierre
            )
            for accion_amelie in acciones_amelie:
                siguiente_amelie, tunel_amelie = _avanzar_estado(
                    estado_amelie, accion_amelie
                )

                if tunel_pierre is not None and tunel_amelie is not None:
                    mismo_tunel = (
                        tunel_pierre.origen == tunel_amelie.origen
                        and tunel_pierre.destino == tunel_amelie.destino
                    ) or (
                        tunel_pierre.origen == tunel_amelie.destino
                        and tunel_pierre.destino == tunel_amelie.origen
                    )
                    if mismo_tunel:
                        continue

                estacion_pierre = _estacion_del_estado(siguiente_pierre)
                estacion_amelie = _estacion_del_estado(siguiente_amelie)
                if (
                    estacion_pierre is not None
                    and estacion_pierre == estacion_amelie
                ):
                    continue

                nuevo_minuto = minuto + 1
                nueva_clave: _ClaveEstado = (
                    nuevo_minuto,
                    siguiente_pierre,
                    siguiente_amelie,
                )
                if nueva_clave in padres:
                    continue
                padres[nueva_clave] = (
                    clave,
                    accion_pierre,
                    accion_amelie,
                )
                cota = heuristica(siguiente_pierre, siguiente_amelie)
                if nuevo_minuto + cota > limite_minutos:
                    continue
                heapq.heappush(
                    frontera,
                    (
                        nuevo_minuto + cota,
                        nuevo_minuto,
                        next(turnos),
                        nueva_clave,
                    ),
                )

    if clave_final is None:
        return None
    ruta_pierre, ruta_amelie = _reconstruir_rutas_conjuntas(
        clave_final,
        padres,
        origen_pierre,
        origen_amelie,
        puerta_pierre,
        puerta_amelie,
    )
    return PlanSincronizado(
        ruta_pierre,
        ruta_amelie,
        clave_final[0],
        final_pierre.minuto,
        final_amelie.minuto,
    )
