import heapq
from typing import Optional
from dataclasses import dataclass

from grafo import GrafoMetro
from restricciones import Restricciones
from movimientos import movimientos_posibles, Movimiento

@dataclass
class NodoRuta:
    """Representa un paso o estado dentro de la ruta calculada."""
    minuto: int
    estacion: int
    linea: Optional[str]
    evento: str
    previo: Optional['NodoRuta'] = None

    def __lt__(self, otro: 'NodoRuta') -> bool:
        # Permite que heapq ordene los nodos priorizando el menor tiempo (minuto)
        return self.minuto < otro.minuto


class RastroEspacioTemporal:
    """Lleva el registro de dónde y cuándo está un personaje para evitar colisiones."""
    def __init__(self):
        self.estaciones_ocupadas: dict[int, int] = {}
        self.tuneles_ocupados: list[tuple[int, int, int, int]] = []

    def registrar_ruta(self, ruta: list[NodoRuta], espera_inicial: int):
        """Guarda los movimientos de un personaje minuto a minuto."""
        for i in range(len(ruta)):
            paso = ruta[i]
            minuto_real = paso.minuto + espera_inicial
            self.estaciones_ocupadas[minuto_real] = paso.estacion
            
            # Si hay un paso siguiente, registramos la ocupación del túnel
            if i < len(ruta) - 1:
                sig_paso = ruta[i+1]
                min_sig_real = sig_paso.minuto + espera_inicial
                if paso.estacion != sig_paso.estacion:
                    self.tuneles_ocupados.append(
                        (minuto_real, min_sig_real, paso.estacion, sig_paso.estacion)
                    )

    def colisiona_estacion(self, minuto: int, estacion: int) -> bool:
        """Devuelve True si la estación ya está ocupada en ese minuto exacto."""
        return self.estaciones_ocupadas.get(minuto) == estacion

    def colisiona_tunel(self, t_ini: int, t_fin: int, u: int, v: int) -> bool:
        """Devuelve True si el túnel está siendo usado en ese mismo intervalo de tiempo."""
        for (r_ini, r_fin, r_u, r_v) in self.tuneles_ocupados:
            # Verifica si es el mismo túnel sin importar la dirección
            if (u == r_u and v == r_v) or (u == r_v and v == r_u):
                # Verifica si los intervalos de tiempo se cruzan
                if max(t_ini, r_ini) < min(t_fin, r_fin):
                    return True
        return False


class Planificador:
    """Motor de búsqueda que encuentra las rutas óptimas usando el algoritmo de Dijkstra."""
    def __init__(self, grafo: GrafoMetro, restricciones: Restricciones):
        self.grafo = grafo
        self.rest = restricciones

    def buscar_ruta_individual(self, origen: int, destino: int) -> Optional[NodoRuta]:
        """Encuentra la ruta más rápida ignorando colisiones con otros personajes."""
        frontera = []
        visitados = {}
        inicio = NodoRuta(minuto=0, estacion=origen, linea=None, evento="Origen")
        
        heapq.heappush(frontera, inicio)
        visitados[(origen, None)] = 0

        while frontera:
            actual = heapq.heappop(frontera)
            
            if actual.estacion == destino:
                return NodoRuta(minuto=actual.minuto, estacion=destino, linea=actual.linea, evento="Destino", previo=actual)

            if actual.minuto > visitados.get((actual.estacion, actual.linea), float('inf')):
                continue

            # Usamos tu módulo de movimientos para obtener opciones válidas
            for mov in movimientos_posibles(self.grafo, self.rest, actual.estacion, actual.linea, actual.minuto):
                
                evento = f"Viaje {mov.arista.linea}"
                if mov.tiempo_transbordo > 0:
                    evento = f"Transbordo a {mov.arista.linea} y Viaje"

                nuevo_estado = (mov.arista.destino, mov.arista.linea)

                if mov.minuto_llegada < visitados.get(nuevo_estado, float('inf')):
                    visitados[nuevo_estado] = mov.minuto_llegada
                    heapq.heappush(frontera, NodoRuta(mov.minuto_llegada, mov.arista.destino, mov.arista.linea, evento, actual))
                    
        return None

    def buscar_ruta_sin_colision(self, origen: int, destino: int, espera_inicial: int, rastro: RastroEspacioTemporal) -> Optional[NodoRuta]:
        """Encuentra la ruta más rápida esquivando a otro personaje en el espacio y tiempo."""
        frontera = []
        visitados = set()
        inicio = NodoRuta(minuto=espera_inicial, estacion=origen, linea=None, evento="Origen")
        
        heapq.heappush(frontera, inicio)

        while frontera:
            actual = heapq.heappop(frontera)
            estado = (actual.estacion, actual.linea, actual.minuto)

            if estado in visitados: 
                continue
            visitados.add(estado)

            if actual.estacion == destino:
                return NodoRuta(minuto=actual.minuto, estacion=destino, linea=actual.linea, evento="Destino", previo=actual)

            # Usamos tu módulo de movimientos para obtener opciones válidas
            for mov in movimientos_posibles(self.grafo, self.rest, actual.estacion, actual.linea, actual.minuto):
                
                # 1. Validar colisión temporal en la estación de destino
                if rastro.colisiona_estacion(mov.minuto_llegada, mov.arista.destino): 
                    continue
                
                # 2. Validar colisión espacial en el túnel (desde que termina el transbordo hasta que llega)
                if rastro.colisiona_tunel(mov.minuto_salida, mov.minuto_llegada, actual.estacion, mov.arista.destino): 
                    continue

                evento = f"Viaje {mov.arista.linea}"
                if mov.tiempo_transbordo > 0:
                    evento = f"Transbordo a {mov.arista.linea} y Viaje"

                nuevo_estado = (mov.arista.destino, mov.arista.linea, mov.minuto_llegada)
                
                if nuevo_estado not in visitados:
                    heapq.heappush(frontera, NodoRuta(mov.minuto_llegada, mov.arista.destino, mov.arista.linea, evento, actual))
                    
        return None

    def reconstruir_ruta(self, nodo_final: NodoRuta) -> list[NodoRuta]:
        """Arma la lista de pasos desde el inicio hasta el fin leyendo los enlaces 'previo'."""
        ruta, actual = [], nodo_final
        while actual:
            ruta.append(actual)
            actual = actual.previo
        return ruta[::-1]

    def imprimir_ruta(self, nombre: str, ruta: list[NodoRuta], espera_inicial: int = 0):
        """Muestra el itinerario del personaje por consola."""
        tiempo_viaje = ruta[-1].minuto - ruta[0].minuto
        print(f"\n[RUTA DE {nombre.upper()} (Tiempo total de viaje: {tiempo_viaje} min)]")
        for paso in ruta:
            minuto_real = paso.minuto + espera_inicial
            if paso.evento == "Origen":
                if espera_inicial > 0: 
                    print(f"Minuto {paso.minuto}: Estación {paso.estacion} (Inicia tras {espera_inicial} min de espera)")
                else: 
                    print(f"Minuto {paso.minuto}: Estación {paso.estacion} (Origen)")
            elif paso.evento == "Destino": 
                print(f"Minuto {minuto_real}: Estación {paso.estacion} (Destino Compuerta)")
            else: 
                print(f"Minuto {minuto_real}: Estación {paso.estacion} ({paso.evento})")