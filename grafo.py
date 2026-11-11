from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Arista:
    """Túnel dirigido origen -> destino con tiempo de viaje (min) y línea."""
    origen: int
    destino: int
    peso: int
    linea: str

    def clave_tunel(self) -> tuple:
        """ID del túnel. """
        return (min(self.origen, self.destino), max(self.origen, self.destino), self.linea)


class GrafoMetro:
    """Grafo dirigido ponderado almacenado como lista de adyacencia."""

    def __init__(self) -> None:
        self._transbordo: dict[int, int] = {}
        self._ady: dict[int, list[Arista]] = {}
        self._ady_inv: dict[int, list[Arista]] = {}
        self._n_tuneles = 0

    def agregar_estacion(self, id_estacion: int, tiempo_transbordo: int) -> None:
        if id_estacion in self._transbordo:
            raise ValueError(f"Estación {id_estacion} duplicada")
        if tiempo_transbordo < 0:
            raise ValueError(f"Tiempo de transbordo negativo en estación {id_estacion}")
        self._transbordo[id_estacion] = tiempo_transbordo
        self._ady[id_estacion] = []
        self._ady_inv[id_estacion] = []

    def agregar_tunel(self, origen: int, destino: int, peso: int, linea: str) -> None:
        for v in (origen, destino):
            if v not in self._transbordo:
                raise ValueError(f"El túnel {origen}->{destino} usa la estación {v}, que no está definida")
        if peso <= 0:
            raise ValueError(f"El túnel {origen}->{destino} debe tener tiempo de viaje > 0")
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
        """Aristas que salen de la estación."""
        return self._ady[estacion]

    def predecesores(self, estacion: int) -> list[Arista]:
        """Aristas que llegan a la estación."""
        return self._ady_inv[estacion]

    @property
    def n_estaciones(self) -> int:
        return len(self._transbordo)

    @property
    def n_tuneles(self) -> int:
        return self._n_tuneles
