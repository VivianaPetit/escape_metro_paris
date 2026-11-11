from __future__ import annotations

class Restricciones:
    def __init__(self) -> None:
        self.lineas_dobles: set[str] = set()
        self.cierres: list[tuple[str, int, int]] = []
        self.semilla: int | None = None

    def peso(self, arista) -> int:
        """Tiempo de viaje efectivo de una arista (aplica retrasos técnicos)."""
        return arista.peso * 2 if arista.linea in self.lineas_dobles else arista.peso

    def transbordo_permitido(self, linea_origen: str, linea_destino: str,
                             t_ini: int, t_fin: int) -> bool:
        """False si algún cierre afecta el transbordo que ocupa [t_ini, t_fin]."""
        for linea, a, b in self.cierres:
            if linea in (linea_origen, linea_destino) and t_ini <= b and t_fin >= a:
                return False
        return True
