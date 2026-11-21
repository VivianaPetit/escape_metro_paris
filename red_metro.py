"""Modelo del metro, reglas de viaje y lectura del archivo de entrada."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Arista:
    """Túnel dirigido con tiempo de viaje y línea."""

    origen: int
    destino: int
    peso: int
    linea: str

    def clave_tunel(self) -> tuple[int, int, str]:
        """Devuelve la clave física del túnel ignorando su dirección."""
        return (
            min(self.origen, self.destino),
            max(self.origen, self.destino),
            self.linea,
        )


class GrafoMetro:
    """Grafo dirigido ponderado almacenado como lista de adyacencia."""

    def __init__(self) -> None:
        self._transbordo: dict[int, int] = {}
        self._ady: dict[int, list[Arista]] = {}
        self._ady_inv: dict[int, list[Arista]] = {}
        self._n_tuneles = 0

    def agregar_estacion(
        self, id_estacion: int, tiempo_transbordo: int
    ) -> None:
        if id_estacion in self._transbordo:
            raise ValueError(f"Estación {id_estacion} duplicada")
        if tiempo_transbordo < 0:
            raise ValueError(
                f"Tiempo de transbordo negativo en estación {id_estacion}"
            )
        self._transbordo[id_estacion] = tiempo_transbordo
        self._ady[id_estacion] = []
        self._ady_inv[id_estacion] = []

    def agregar_tunel(
        self, origen: int, destino: int, peso: int, linea: str
    ) -> None:
        for estacion in (origen, destino):
            if estacion not in self._transbordo:
                raise ValueError(
                    f"El túnel {origen}->{destino} usa la estación "
                    f"{estacion}, que no está definida"
                )
        if peso <= 0:
            raise ValueError(
                f"El túnel {origen}->{destino} debe tener tiempo de viaje > 0"
            )
        arista = Arista(origen, destino, peso, linea)
        self._ady[origen].append(arista)
        self._ady_inv[destino].append(arista)
        self._n_tuneles += 1

    def existe(self, estacion: int) -> bool:
        return estacion in self._transbordo

    def estaciones(self) -> list[int]:
        return list(self._transbordo)

    def tiempo_transbordo(self, estacion: int) -> int:
        return self._transbordo[estacion]

    def vecinos(self, estacion: int) -> list[Arista]:
        """Devuelve los túneles que salen de la estación."""
        return self._ady[estacion]

    def predecesores(self, estacion: int) -> list[Arista]:
        """Devuelve los túneles que llegan a la estación."""
        return self._ady_inv[estacion]

    @property
    def n_estaciones(self) -> int:
        return len(self._transbordo)

    @property
    def n_tuneles(self) -> int:
        return self._n_tuneles


class Restricciones:
    """Retrasos de línea y cierres temporales de transbordo."""

    def __init__(self) -> None:
        self.lineas_dobles: set[str] = set()
        self.cierres: list[tuple[str, int, int]] = []

    def peso(self, arista: Arista) -> int:
        """Devuelve el tiempo efectivo del túnel."""
        return (
            arista.peso * 2
            if arista.linea in self.lineas_dobles
            else arista.peso
        )

    def transbordo_permitido(
        self,
        linea_origen: str,
        linea_destino: str,
        t_ini: int,
        t_fin: int,
    ) -> bool:
        """Comprueba que el cambio de línea no coincida con un cierre."""
        return not any(
            linea in (linea_origen, linea_destino)
            and t_ini <= fin_cierre
            and t_fin >= inicio_cierre
            for linea, inicio_cierre, fin_cierre in self.cierres
        )


@dataclass
class Movimiento:
    """Túnel posible y sus tiempos de transbordo, salida y llegada."""

    arista: Arista
    minuto_inicio: int
    minuto_salida: int
    minuto_llegada: int
    tiempo_transbordo: int
    tiempo_viaje: int


def movimientos_posibles(
    grafo: GrafoMetro,
    restricciones: Restricciones,
    estacion: int,
    linea_actual: str | None,
    minuto_actual: int,
) -> list[Movimiento]:
    """Genera los movimientos legales disponibles desde una estación.

    Un cambio de línea consume el tiempo de transbordo y no puede coincidir con
    un cierre. El primer túnel del recorrido no requiere transbordo.
    """
    if not grafo.existe(estacion):
        raise ValueError(f"La estación {estacion} no existe en el grafo")
    if minuto_actual < 0:
        raise ValueError("El minuto actual no puede ser negativo")

    posibles: list[Movimiento] = []
    for arista in grafo.vecinos(estacion):
        cambio_linea = linea_actual is not None and arista.linea != linea_actual
        tiempo_transbordo = (
            grafo.tiempo_transbordo(estacion) if cambio_linea else 0
        )
        minuto_salida = minuto_actual + tiempo_transbordo

        if cambio_linea and not restricciones.transbordo_permitido(
            linea_actual,
            arista.linea,
            minuto_actual,
            minuto_salida,
        ):
            continue

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


class ErrorEntrada(Exception):
    """Error de formato o datos inválidos en el archivo de entrada."""


@dataclass
class Mision:
    """Orígenes de los personajes y estaciones de sus puertas."""

    origen_pierre: int
    origen_amelie: int
    puerta_pierre: int
    puerta_amelie: int


def _entero(token: str, num_linea: int) -> int:
    try:
        return int(token)
    except ValueError:
        raise ErrorEntrada(
            f"Línea {num_linea}: '{token}' no es un entero válido"
        ) from None


def leer_entrada(
    ruta: str,
) -> tuple[GrafoMetro, Mision, Restricciones]:
    """Lee la red, la misión y las directivas desde un archivo de texto."""
    with open(ruta, encoding="utf-8") as archivo:
        crudas = archivo.readlines()

    filas: list[tuple[int, list[str]]] = []
    for numero, linea in enumerate(crudas, 1):
        texto = linea.split("#", 1)[0].replace("|", " ").strip()
        if texto:
            filas.append((numero, texto.split()))

    posicion = 0

    def siguiente(
        descripcion: str, cantidad_campos: int | None = None
    ) -> tuple[int, list[str]]:
        nonlocal posicion
        if posicion >= len(filas):
            raise ErrorEntrada(
                f"Fin de archivo inesperado: falta {descripcion}"
            )
        numero, tokens = filas[posicion]
        if cantidad_campos is not None and len(tokens) != cantidad_campos:
            raise ErrorEntrada(
                f"Línea {numero}: se esperaban {cantidad_campos} campos "
                f"({descripcion})"
            )
        posicion += 1
        return numero, tokens

    numero, tokens = siguiente("cabecera 'N M'", 2)
    cantidad_estaciones = _entero(tokens[0], numero)
    cantidad_tuneles = _entero(tokens[1], numero)

    grafo = GrafoMetro()
    try:
        for _ in range(cantidad_estaciones):
            numero, tokens = siguiente("estación y tiempo de transbordo", 2)
            grafo.agregar_estacion(
                _entero(tokens[0], numero),
                _entero(tokens[1], numero),
            )
        for _ in range(cantidad_tuneles):
            numero, tokens = siguiente("túnel: origen destino tiempo línea", 4)
            grafo.agregar_tunel(
                _entero(tokens[0], numero),
                _entero(tokens[1], numero),
                _entero(tokens[2], numero),
                tokens[3].upper(),
            )
    except ValueError as error:
        raise ErrorEntrada(f"Línea {numero}: {error}") from None

    numero, tokens = siguiente("datos de la misión", 4)
    mision = Mision(*(_entero(token, numero) for token in tokens))
    for estacion in (
        mision.origen_pierre,
        mision.origen_amelie,
        mision.puerta_pierre,
        mision.puerta_amelie,
    ):
        if not grafo.existe(estacion):
            raise ErrorEntrada(
                f"Línea {numero}: la estación {estacion} de la misión "
                "no existe"
            )
    if mision.origen_pierre == mision.origen_amelie:
        raise ErrorEntrada(
            "Pierre y Amélie no pueden comenzar en la misma estación "
            "(colisión en el minuto 0)"
        )
    if mision.puerta_pierre == mision.puerta_amelie:
        raise ErrorEntrada(
            "Las compuertas D1 y D2 deben ser estaciones distintas "
            "(ambos llegarían a la misma estación en el mismo instante)"
        )

    restricciones = Restricciones()
    while posicion < len(filas):
        numero, tokens = siguiente("directiva")
        clave = tokens[0].upper()
        if clave == "DOBLE" and len(tokens) == 2:
            restricciones.lineas_dobles.add(tokens[1].upper())
        elif clave == "SIN_TRANSBORDO" and len(tokens) == 4:
            restricciones.cierres.append(
                (
                    tokens[1].upper(),
                    _entero(tokens[2], numero),
                    _entero(tokens[3], numero),
                )
            )
        else:
            raise ErrorEntrada(
                f"Línea {numero}: directiva desconocida o mal formada: "
                f"{' '.join(tokens)}"
            )

    return grafo, mision, restricciones
