from __future__ import annotations
from dataclasses import dataclass

from grafo import GrafoMetro
from restricciones import Restricciones


class ErrorEntrada(Exception):
    """Error de formato o de datos en el archivo de entrada."""

@dataclass
class Mision:
    origen_pierre: int
    origen_amelie: int
    puerta_pierre: int   # D1
    puerta_amelie: int   # D2


def _entero(token: str, num_linea: int) -> int:
    try:
        return int(token)
    except ValueError:
        raise ErrorEntrada(f"Línea {num_linea}: '{token}' no es un entero válido") from None


def leer_entrada(ruta: str) -> tuple[GrafoMetro, Mision, Restricciones]:
    with open(ruta, encoding="utf-8") as f:
        crudas = f.readlines()

    filas: list[tuple[int, list[str]]] = []
    for num, linea in enumerate(crudas, 1):
        texto = linea.split("#", 1)[0].replace("|", " ").strip()
        if texto:
            filas.append((num, texto.split()))

    pos = 0

    def siguiente(descripcion: str, n_tokens: int | None = None):
        nonlocal pos
        if pos >= len(filas):
            raise ErrorEntrada(f"Fin de archivo inesperado: falta {descripcion}")
        num, tokens = filas[pos]
        if n_tokens is not None and len(tokens) != n_tokens:
            raise ErrorEntrada(f"Línea {num}: se esperaban {n_tokens} campos ({descripcion})")
        pos += 1
        return num, tokens

    num, t = siguiente("cabecera 'N M'", 2)
    n_est, n_tun = _entero(t[0], num), _entero(t[1], num)

    grafo = GrafoMetro()
    try:
        for _ in range(n_est):
            num, t = siguiente("estación y tiempo de transbordo", 2)
            grafo.agregar_estacion(_entero(t[0], num), _entero(t[1], num))
        for _ in range(n_tun):
            num, t = siguiente("túnel: origen destino tiempo línea", 4)
            grafo.agregar_tunel(_entero(t[0], num), _entero(t[1], num),
                                _entero(t[2], num), t[3].upper())
    except ValueError as e:
        raise ErrorEntrada(f"Línea {num}: {e}") from None

    num, t = siguiente("datos de la misión", 4)
    mision = Mision(*(_entero(x, num) for x in t))
    for v in (mision.origen_pierre, mision.origen_amelie,
              mision.puerta_pierre, mision.puerta_amelie):
        if not grafo.existe(v):
            raise ErrorEntrada(f"Línea {num}: la estación {v} de la misión no existe")
    if mision.origen_pierre == mision.origen_amelie:
        raise ErrorEntrada("Pierre y Amélie no pueden comenzar en la misma estación (colisión en el minuto 0)")
    if mision.puerta_pierre == mision.puerta_amelie:
        raise ErrorEntrada("Las compuertas D1 y D2 deben ser estaciones distintas "
                           "(ambos llegarían a la misma estación en el mismo instante)")

    rest = Restricciones()
    while pos < len(filas):
        num, t = siguiente("directiva")
        clave = t[0].upper()
        if clave == "DOBLE" and len(t) == 2:
            rest.lineas_dobles.add(t[1].upper())
        elif clave == "SIN_TRANSBORDO" and len(t) == 4:
            rest.cierres.append((t[1].upper(), _entero(t[2], num), _entero(t[3], num)))
        elif clave == "SEMILLA" and len(t) == 2:
            rest.semilla = _entero(t[1], num)
        else:
            raise ErrorEntrada(f"Línea {num}: directiva desconocida o mal formada: {' '.join(t)}")

    return grafo, mision, rest
