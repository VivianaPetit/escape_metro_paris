"""Interfaz gráfica para explorar el grafo y reproducir las dos rutas."""

from __future__ import annotations

import math
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

from buscador_rutas import NodoRuta, PlanSincronizado
from red_metro import Arista, GrafoMetro, Mision, Restricciones


_COLORES_LINEA = (
    "#2563eb",
    "#16a34a",
    "#d97706",
    "#9333ea",
    "#0891b2",
    "#dc2626",
    "#4f46e5",
)
_COLORES_PERSONAJE = {
    "Pierre": "#7c3aed",
    "Amélie": "#ea580c",
}
_FONDO_APP = "#e5e7eb"
_FONDO_TARJETA = "#ffffff"
_FONDO_MAPA = "#f1f3f5"
_TEXTO_PRINCIPAL = "#172033"
_TEXTO_SECUNDARIO = "#64748b"
_BORDE = "#e2e8f0"
_ACENTO = "#2563eb"


@dataclass(frozen=True)
class Posicion:
    """Ubicación de un personaje en una estación o dentro de un túnel."""

    tipo: str
    estacion: int | None = None
    origen: int | None = None
    destino: int | None = None
    progreso: float = 0.0
    linea: str | None = None


def posicion_en_minuto(ruta: list[NodoRuta], minuto: int) -> Posicion:
    """Calcula la estación o el punto del túnel ocupado en un minuto."""
    if not ruta:
        raise ValueError("No se puede consultar la posición de una ruta vacía")
    if minuto < 0:
        raise ValueError("El minuto no puede ser negativo")

    primero = ruta[0]
    if minuto <= primero.minuto:
        return Posicion("estacion", estacion=primero.estacion)

    for actual, siguiente in zip(ruta, ruta[1:]):
        if siguiente.arista is None:
            if actual.minuto <= minuto <= siguiente.minuto:
                return Posicion("estacion", estacion=actual.estacion)
            continue

        minuto_salida = (
            siguiente.minuto_salida
            if siguiente.minuto_salida is not None
            else actual.minuto
        )
        if actual.minuto <= minuto < minuto_salida:
            return Posicion("estacion", estacion=actual.estacion)
        if minuto_salida <= minuto < siguiente.minuto:
            duracion = siguiente.minuto - minuto_salida
            progreso = (minuto - minuto_salida) / duracion
            return Posicion(
                "tunel",
                origen=siguiente.arista.origen,
                destino=siguiente.arista.destino,
                progreso=progreso,
                linea=siguiente.arista.linea,
            )
        if minuto == siguiente.minuto:
            return Posicion("estacion", estacion=siguiente.estacion)

    return Posicion("estacion", estacion=ruta[-1].estacion)


class VisualizadorMetro:
    """Ventana interactiva con estaciones, túneles, rutas y posiciones móviles."""

    def __init__(
        self,
        grafo: GrafoMetro,
        mision: Mision,
        plan: PlanSincronizado,
        restricciones: Restricciones,
    ) -> None:
        """Crea el mapa, el panel de estado y los controles de reproducción."""
        self.grafo = grafo
        self.mision = mision
        self.plan = plan
        self.restricciones = restricciones
        self.rutas = {
            "Pierre": plan.ruta_pierre,
            "Amélie": plan.ruta_amelie,
        }
        self.minuto = 0
        self.reproduciendo = False
        self._sincronizando_control = False
        self.duracion = plan.tiempo_total
        self.colores = self._calcular_colores_linea()
        self._ultimo_tamano_mapa = (0, 0)

        self.raiz = tk.Tk()
        self.raiz.title("Escape en el Metro de París")
        ancho = min(1440, max(760, self.raiz.winfo_screenwidth() - 60))
        alto = min(900, max(560, self.raiz.winfo_screenheight() - 100))
        self.raiz.geometry(f"{ancho}x{alto}")
        self.raiz.minsize(760, 560)
        self._ancho_panel = min(340, max(260, int(ancho * 0.28)))
        self._configurar_estilos()

        self.marco = ttk.Frame(
            self.raiz, padding=20, style="App.TFrame"
        )
        self.marco.pack(fill=tk.BOTH, expand=True)
        self.marco.columnconfigure(0, weight=1)
        self.marco.rowconfigure(1, weight=1)

        self._crear_encabezado()
        self.contenido = ttk.Frame(self.marco, style="App.TFrame")
        self.contenido.grid(row=1, column=0, sticky="nsew")
        self.contenido.columnconfigure(0, weight=1)
        self.contenido.columnconfigure(1, weight=0)
        self.contenido.rowconfigure(0, weight=1)

        self.tarjeta_mapa = ttk.Frame(
            self.contenido,
            padding=14,
            style="Card.TFrame",
        )
        self.tarjeta_mapa.grid(
            row=0, column=0, sticky="nsew", padx=(0, 14)
        )
        self.tarjeta_mapa.rowconfigure(1, weight=1)
        self.tarjeta_mapa.columnconfigure(0, weight=1)
        self._crear_encabezado_mapa()
        self.mapa = tk.Canvas(
            self.tarjeta_mapa,
            width=960,
            height=680,
            background=_FONDO_MAPA,
            highlightthickness=0,
            bd=0,
        )
        self.mapa.grid(row=1, column=0, sticky="nsew")
        self.mapa.bind("<Configure>", self._redimensionar_mapa)
        self.posiciones = self._calcular_posiciones(960, 680)

        self.panel = ttk.Frame(
            self.contenido,
            width=self._ancho_panel,
            padding=0,
            style="App.TFrame",
        )
        self.panel.grid(row=0, column=1, sticky="nsew")
        self.panel.grid_propagate(False)
        self.panel.rowconfigure(0, weight=1)
        self.panel.columnconfigure(0, weight=1)
        self.panel_canvas = tk.Canvas(
            self.panel,
            background=_FONDO_APP,
            highlightthickness=0,
            bd=0,
        )
        self.panel_canvas.grid(row=0, column=0, sticky="nsew")
        self.panel_scrollbar = ttk.Scrollbar(
            self.panel,
            orient=tk.VERTICAL,
            command=self.panel_canvas.yview,
        )
        self.panel_scrollbar.grid(row=0, column=1, sticky="ns")
        self.panel_canvas.configure(yscrollcommand=self.panel_scrollbar.set)
        self.panel_contenido = ttk.Frame(
            self.panel_canvas, style="App.TFrame"
        )
        self._panel_window = self.panel_canvas.create_window(
            (0, 0), window=self.panel_contenido, anchor="nw"
        )
        self.panel_canvas.bind("<Configure>", self._ajustar_ancho_panel)
        self.panel_contenido.bind("<Configure>", self._actualizar_region_panel)

        self._crear_panel()
        self._dibujar_mapa()
        self._actualizar_posiciones()
        self.raiz.bind("<Configure>", self._redimensionar_ventana)

    def _configurar_estilos(self) -> None:
        """Define una paleta clara y estilos coherentes para la ventana."""
        self.raiz.configure(background=_FONDO_APP)
        estilo = ttk.Style(self.raiz)
        estilo.theme_use("clam")
        estilo.configure("App.TFrame", background=_FONDO_APP)
        estilo.configure("Card.TFrame", background=_FONDO_TARJETA)
        estilo.configure(
            "Title.TLabel",
            background=_FONDO_APP,
            foreground=_TEXTO_PRINCIPAL,
            font=("Segoe UI", 24, "bold"),
        )
        estilo.configure(
            "Subtitle.TLabel",
            background=_FONDO_APP,
            foreground=_TEXTO_SECUNDARIO,
            font=("Segoe UI", 11),
        )
        estilo.configure(
            "Metric.TLabel",
            background="#e8f0ff",
            foreground="#1d4ed8",
            font=("Segoe UI", 11, "bold"),
            padding=(14, 10),
        )
        estilo.configure(
            "Section.TLabel",
            background=_FONDO_TARJETA,
            foreground=_TEXTO_PRINCIPAL,
            font=("Segoe UI", 12, "bold"),
        )
        estilo.configure(
            "Muted.TLabel",
            background=_FONDO_TARJETA,
            foreground=_TEXTO_SECUNDARIO,
            font=("Segoe UI", 10),
        )
        estilo.configure(
            "Body.TLabel",
            background=_FONDO_TARJETA,
            foreground=_TEXTO_PRINCIPAL,
            font=("Segoe UI", 11),
        )
        estilo.configure(
            "Clock.TLabel",
            background=_FONDO_TARJETA,
            foreground=_TEXTO_PRINCIPAL,
            font=("Segoe UI", 25, "bold"),
        )
        estilo.configure(
            "StatusSuccess.TLabel",
            background="#ecfdf5",
            foreground="#047857",
            font=("Segoe UI", 10, "bold"),
            padding=12,
        )
        estilo.configure(
            "Primary.TButton",
            background=_ACENTO,
            foreground="#ffffff",
            font=("Segoe UI", 10, "bold"),
            padding=(10, 8),
            borderwidth=0,
        )
        estilo.map(
            "Primary.TButton",
            background=[("active", "#1d4ed8"), ("pressed", "#1e40af")],
            foreground=[("disabled", "#cbd5e1")],
        )
        estilo.configure(
            "Secondary.TButton",
            background="#f1f5f9",
            foreground=_TEXTO_PRINCIPAL,
            font=("Segoe UI", 10, "bold"),
            padding=(10, 8),
            borderwidth=0,
        )
        estilo.map(
            "Secondary.TButton",
            background=[("active", "#e2e8f0"), ("pressed", "#cbd5e1")],
        )
        estilo.configure(
            "Horizontal.TScale",
            background=_FONDO_TARJETA,
            troughcolor="#dbe4f0",
        )

    def _crear_encabezado(self) -> None:
        """Crea el título principal y el resumen del tiempo de operación."""
        encabezado = ttk.Frame(self.marco, style="App.TFrame")
        encabezado.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        encabezado.columnconfigure(0, weight=1)
        ttk.Label(
            encabezado,
            text="Escape en el Metro de París",
            style="Title.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            encabezado,
            text="Planificación de rutas y llegada simultánea",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        ttk.Label(
            encabezado,
            text=f"LLEGADA SIMULTÁNEA   {self.duracion} min",
            style="Metric.TLabel",
        ).grid(row=0, column=1, rowspan=2, sticky="e")

    def _crear_encabezado_mapa(self) -> None:
        """Explica los datos que aparecen en el mapa."""
        encabezado = ttk.Frame(self.tarjeta_mapa, style="Card.TFrame")
        encabezado.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        encabezado.columnconfigure(0, weight=1)
        ttk.Label(
            encabezado, text="RED DEL METRO", style="Section.TLabel"
        ).grid(row=0, column=0, sticky="w")
        self.detalle_mapa = ttk.Label(
            encabezado,
            text=f"{self.grafo.n_estaciones} estaciones  ·  "
            f"{self.grafo.n_tuneles} túneles dirigidos  ·  "
            "etiqueta = línea y minutos  ·  t = transbordo",
            style="Muted.TLabel",
            wraplength=900,
        )
        self.detalle_mapa.grid(
            row=1, column=0, sticky="w", pady=(3, 0)
        )

    def _calcular_posiciones(
        self, ancho: int, alto: int
    ) -> dict[int, tuple[float, float]]:
        """Distribuye las estaciones en un anillo ajustado al tamaño del mapa."""
        estaciones = sorted(self.grafo.estaciones())
        centro_x, centro_y = ancho / 2, alto / 2
        radio = max(110.0, min(ancho * 0.39, alto * 0.37))
        cantidad = max(1, len(estaciones))
        return {
            estacion: (
                centro_x + radio * math.cos(
                    2 * math.pi * indice / cantidad - math.pi / 2
                ),
                centro_y + radio * math.sin(
                    2 * math.pi * indice / cantidad - math.pi / 2
                ),
            )
            for indice, estacion in enumerate(estaciones)
        }

    def _redimensionar_mapa(self, evento: tk.Event) -> None:
        """Redibuja la red cuando cambia el espacio disponible para el mapa."""
        tamano = (evento.width, evento.height)
        if tamano == self._ultimo_tamano_mapa or min(tamano) < 100:
            return
        self._ultimo_tamano_mapa = tamano
        self.detalle_mapa.configure(wraplength=max(220, evento.width - 10))
        self.posiciones = self._calcular_posiciones(*tamano)
        self._dibujar_mapa()
        self._actualizar_posiciones()

    def _redimensionar_ventana(self, evento: tk.Event) -> None:
        """Ajusta el panel lateral al espacio disponible en la ventana."""
        if evento.widget is not self.raiz:
            return
        ancho_panel = min(340, max(260, int(evento.width * 0.28)))
        if ancho_panel != self._ancho_panel:
            self._ancho_panel = ancho_panel
            self.panel.configure(width=ancho_panel)

    def _ajustar_ancho_panel(self, evento: tk.Event) -> None:
        """Mantiene el contenido del panel dentro del ancho visible."""
        self.panel_canvas.itemconfigure(
            self._panel_window, width=evento.width
        )
        self.estado.configure(wraplength=max(160, evento.width - 44))

    def _actualizar_region_panel(self, _evento: tk.Event) -> None:
        """Actualiza el área desplazable cuando cambian las tarjetas del panel."""
        if _evento.widget is not self.panel_contenido:
            return
        self.panel_canvas.configure(
            scrollregion=self.panel_canvas.bbox("all")
        )

    def _calcular_colores_linea(self) -> dict[str, str]:
        """Asigna un color legible y repetible a cada línea del grafo."""
        lineas = sorted(
            {arista.linea for estacion in self.grafo.estaciones()
             for arista in self.grafo.vecinos(estacion)}
        )
        return {
            linea: _COLORES_LINEA[indice % len(_COLORES_LINEA)]
            for indice, linea in enumerate(lineas)
        }

    def _crear_panel(self) -> None:
        """Construye tarjetas de estado, ubicación, leyenda y reproducción."""
        self.panel_contenido.grid_columnconfigure(0, weight=1)

        estado = ttk.Frame(
            self.panel_contenido, padding=14, style="Card.TFrame"
        )
        estado.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(
            estado, text="RESULTADO DE LA MISIÓN", style="Muted.TLabel"
        ).pack(anchor=tk.W, pady=(0, 9))
        self.estado = ttk.Label(
            estado,
            text=self._texto_resultado(),
            style="StatusSuccess.TLabel",
            justify=tk.LEFT,
            wraplength=290,
        )
        self.estado.pack(fill=tk.X)

        ubicaciones = ttk.Frame(
            self.panel_contenido, padding=14, style="Card.TFrame"
        )
        ubicaciones.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(
            ubicaciones, text="UBICACIÓN ACTUAL", style="Section.TLabel"
        ).pack(anchor=tk.W, pady=(0, 7))
        self.ubicaciones: dict[str, ttk.Label] = {}
        for nombre, color in _COLORES_PERSONAJE.items():
            fila = ttk.Frame(ubicaciones, style="Card.TFrame")
            fila.pack(fill=tk.X, pady=3)
            ttk.Label(
                fila,
                text="●",
                foreground=color,
                background=_FONDO_TARJETA,
                font=("Segoe UI", 12, "bold"),
            ).pack(side=tk.LEFT, padx=(0, 7))
            ttk.Label(
                fila, text=nombre, style="Body.TLabel", width=8
            ).pack(side=tk.LEFT)
            self.ubicaciones[nombre] = ttk.Label(
                fila,
                text="",
                style="Muted.TLabel",
                anchor=tk.E,
                justify=tk.RIGHT,
            )
            self.ubicaciones[nombre].pack(
                side=tk.RIGHT, fill=tk.X, expand=True
            )

        leyenda = ttk.Frame(
            self.panel_contenido, padding=14, style="Card.TFrame"
        )
        leyenda.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(
            leyenda, text="LÍNEAS DEL GRAFO", style="Section.TLabel"
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 7))
        for indice, (linea, color) in enumerate(self.colores.items()):
            ttk.Label(
                leyenda,
                text=f"●  {linea}",
                foreground=color,
                background=_FONDO_TARJETA,
                font=("Segoe UI", 10, "bold"),
            ).grid(
                row=1 + indice // 2,
                column=indice % 2,
                sticky="w",
                padx=(0, 14),
                pady=2,
            )

        controles = ttk.Frame(
            self.panel_contenido, padding=14, style="Card.TFrame"
        )
        controles.grid(row=3, column=0, sticky="ew")
        controles.columnconfigure(0, weight=1)
        ttk.Label(
            controles, text="REPRODUCCIÓN", style="Muted.TLabel"
        ).grid(row=0, column=0, sticky="w")
        self.reloj = ttk.Label(
            controles, text="", style="Clock.TLabel"
        )
        self.reloj.grid(row=1, column=0, sticky="w", pady=(2, 0))
        self.detalle_reloj = ttk.Label(
            controles, text="", style="Muted.TLabel"
        )
        self.detalle_reloj.grid(row=2, column=0, sticky="w", pady=(0, 8))
        self.progreso = ttk.Progressbar(
            controles,
            maximum=max(1, self.duracion),
            mode="determinate",
        )
        self.progreso.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        self.control_minuto = ttk.Scale(
            controles,
            from_=0,
            to=max(1, self.duracion),
            command=self._cambiar_minuto,
            style="Horizontal.TScale",
        )
        self.control_minuto.grid(row=4, column=0, sticky="ew", pady=(0, 10))

        botones = ttk.Frame(controles, style="Card.TFrame")
        botones.grid(row=5, column=0, sticky="ew")
        botones.columnconfigure(0, weight=1)
        botones.columnconfigure(1, weight=1)
        ttk.Button(
            botones,
            text="▶  Iniciar",
            command=self.iniciar,
            style="Primary.TButton",
        ).grid(row=0, column=0, sticky="ew", padx=(0, 5), pady=(0, 5))
        ttk.Button(
            botones,
            text="Ⅱ  Pausar",
            command=self.pausar,
            style="Secondary.TButton",
        ).grid(row=0, column=1, sticky="ew", padx=(5, 0), pady=(0, 5))
        ttk.Button(
            botones,
            text="Avanzar  ▸",
            command=self.avanzar,
            style="Secondary.TButton",
        ).grid(row=1, column=0, sticky="ew", padx=(0, 5))
        ttk.Button(
            botones,
            text="↺  Reiniciar",
            command=self.reiniciar,
            style="Secondary.TButton",
        ).grid(row=1, column=1, sticky="ew", padx=(5, 0))

        ttk.Label(
            controles,
            text="Arrastra el control para saltar a un minuto.",
            style="Muted.TLabel",
        ).grid(row=6, column=0, sticky="w", pady=(9, 0))

    def _texto_resultado(self) -> str:
        """Resume la sincronización y la llegada segura a ambas puertas."""
        return (
            "RUTAS SIN COLISIONES\n"
            f"Llegada simultánea en el minuto {self.plan.tiempo_total}."
        )

    def _dibujar_mapa(self) -> None:
        """Dibuja los túneles y las estaciones sobre el mismo sistema de nodos."""
        self.mapa.delete("all")
        grupos: dict[tuple[int, int], list[Arista]] = {}
        for estacion in self.grafo.estaciones():
            for arista in self.grafo.vecinos(estacion):
                clave = tuple(sorted((arista.origen, arista.destino)))
                grupos.setdefault(clave, []).append(arista)

        for aristas in grupos.values():
            lineas = sorted({arista.linea for arista in aristas})
            desplazamientos = {
                linea: 8.0 + 13.0 * indice
                for indice, linea in enumerate(lineas)
            }
            for arista in aristas:
                self._dibujar_tunel(
                    arista, desplazamientos[arista.linea]
                )

        for estacion in sorted(self.grafo.estaciones()):
            self._dibujar_estacion(estacion)
        self._dibujar_leyenda_puertas()

    def _dibujar_tunel(self, arista: Arista, desplazamiento: float) -> None:
        """Dibuja una arista dirigida, su flecha y su tiempo de viaje."""
        x1, y1 = self.posiciones[arista.origen]
        x2, y2 = self.posiciones[arista.destino]
        dx, dy = x2 - x1, y2 - y1
        distancia = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / distancia, dx / distancia
        mx, my = (x1 + x2) / 2 + nx * desplazamiento, (y1 + y2) / 2 + ny * desplazamiento
        sx, sy = x1 + nx * desplazamiento * 0.35, y1 + ny * desplazamiento * 0.35
        ex, ey = x2 + nx * desplazamiento * 0.35, y2 + ny * desplazamiento * 0.35
        color = self.colores[arista.linea]
        self.mapa.create_line(
            sx,
            sy,
            mx,
            my,
            ex,
            ey,
            smooth=True,
            arrow=tk.LAST,
            arrowshape=(9, 11, 4),
            width=2.2,
            fill=color,
            tags=("tunel",),
        )

        peso = self.restricciones.peso(arista)
        texto = f"{arista.linea} · {peso}"
        rectangulo = self.mapa.create_rectangle(
            mx - 27,
            my - 9,
            mx + 27,
            my + 9,
            fill="#ffffff",
            outline=_BORDE,
            tags=("etiqueta_tunel",),
        )
        etiqueta = self.mapa.create_text(
            mx,
            my,
            text=texto,
            fill=color,
            font=("Segoe UI", 9, "bold"),
            tags=("etiqueta_tunel",),
        )
        self.mapa.tag_lower(rectangulo, etiqueta)

    def _dibujar_estacion(self, estacion: int) -> None:
        """Dibuja una estación con su identificador y tiempo de transbordo."""
        x, y = self.posiciones[estacion]
        es_origen = estacion in (
            self.mision.origen_pierre,
            self.mision.origen_amelie,
        )
        es_destino = estacion in (
            self.mision.puerta_pierre,
            self.mision.puerta_amelie,
        )
        colores_estacion = {
            self.mision.origen_pierre: _COLORES_PERSONAJE["Pierre"],
            self.mision.origen_amelie: _COLORES_PERSONAJE["Amélie"],
            self.mision.puerta_pierre: _COLORES_PERSONAJE["Pierre"],
            self.mision.puerta_amelie: _COLORES_PERSONAJE["Amélie"],
        }
        contorno = colores_estacion.get(estacion, "#94a3b8")
        grosor = 3 if es_origen or es_destino else 1.4
        self.mapa.create_oval(
            x - 18,
            y - 18,
            x + 18,
            y + 18,
            fill="#ffffff",
            outline=contorno,
            width=grosor,
            tags=("estacion",),
        )
        self.mapa.create_text(
            x,
            y - 1,
            text=str(estacion),
            font=("Segoe UI", 11, "bold"),
            fill=_TEXTO_PRINCIPAL,
            tags=("estacion",),
        )
        self.mapa.create_text(
            x,
            y + 29,
            text=f"t {self.grafo.tiempo_transbordo(estacion)}",
            font=("Segoe UI", 9, "bold"),
            fill=_TEXTO_SECUNDARIO,
            tags=("estacion",),
        )

    def _dibujar_leyenda_puertas(self) -> None:
        """Anota en el mapa las estaciones de inicio y las dos puertas del búnker."""
        anotaciones = (
            (self.mision.origen_pierre, "P inicio", "#7c3aed", -31, -29),
            (self.mision.origen_amelie, "A inicio", "#ea580c", 30, -29),
            (self.mision.puerta_pierre, "D1", "#7c3aed", -28, 29),
            (self.mision.puerta_amelie, "D2", "#ea580c", 28, 29),
        )
        for estacion, etiqueta, color, dx, dy in anotaciones:
            x, y = self.posiciones[estacion]
            id_texto = self.mapa.create_text(
                x + dx,
                y + dy,
                text=etiqueta,
                fill=color,
                font=("Segoe UI", 9, "bold"),
                tags=("leyenda",),
            )
            caja = self.mapa.bbox(id_texto)
            if caja is not None:
                fondo = self.mapa.create_rectangle(
                    caja[0] - 4,
                    caja[1] - 2,
                    caja[2] + 4,
                    caja[3] + 2,
                    fill=_FONDO_MAPA,
                    outline=color,
                    width=1,
                    tags=("leyenda",),
                )
                self.mapa.tag_lower(fondo, id_texto)

    def _coordenada_posicion(
        self, posicion: Posicion, desplazamiento: tuple[float, float]
    ) -> tuple[float, float]:
        """Convierte una posición lógica de estación o túnel a coordenadas."""
        dx, dy = desplazamiento
        if posicion.tipo == "estacion" and posicion.estacion is not None:
            x, y = self.posiciones[posicion.estacion]
            return x + dx, y + dy
        if posicion.origen is None or posicion.destino is None:
            return 0.0, 0.0
        x1, y1 = self.posiciones[posicion.origen]
        x2, y2 = self.posiciones[posicion.destino]
        return (
            x1 + (x2 - x1) * posicion.progreso + dx,
            y1 + (y2 - y1) * posicion.progreso + dy,
        )

    def _actualizar_posiciones(self) -> None:
        """Actualiza las fichas móviles y el reloj del minuto seleccionado."""
        self.mapa.delete("dinamico")
        nombres = ("Pierre", "Amélie")
        desplazamientos = {
            "Pierre": (-9.0, -9.0),
            "Amélie": (9.0, -9.0),
        }
        for nombre in nombres:
            posicion = posicion_en_minuto(self.rutas[nombre], self.minuto)
            x, y = self._coordenada_posicion(
                posicion, desplazamientos[nombre]
            )
            color = _COLORES_PERSONAJE[nombre]
            self.mapa.create_oval(
                x - 9,
                y - 9,
                x + 9,
                y + 9,
                fill=color,
                outline="#ffffff",
                width=2,
                tags=("dinamico",),
            )
            self.mapa.create_text(
                x,
                y,
                text=nombre[0],
                fill="#ffffff",
                font=("Segoe UI", 9, "bold"),
                tags=("dinamico",),
            )
            if posicion.tipo == "estacion":
                detalle = f"estación {posicion.estacion}"
            else:
                detalle = (
                    f"túnel {posicion.origen}->{posicion.destino} "
                    f"({posicion.linea})"
                )
            self.ubicaciones[nombre].configure(text=detalle)

        self.reloj.configure(text=f"{self.minuto:02d}")
        self.detalle_reloj.configure(
            text=f"minuto de {self.duracion:02d}"
        )
        self.progreso.configure(value=self.minuto)
        self._sincronizando_control = True
        try:
            self.control_minuto.set(self.minuto)
        finally:
            self._sincronizando_control = False

    def _cambiar_minuto(self, valor: str) -> None:
        """Permite saltar a un minuto elegido con el control deslizante."""
        if self._sincronizando_control:
            return
        self.minuto = min(self.duracion, max(0, round(float(valor))))
        self._actualizar_posiciones()

    def iniciar(self) -> None:
        """Reproduce la simulación a intervalos hasta llegar al minuto final."""
        if not self.reproduciendo and self.minuto < self.duracion:
            self.reproduciendo = True
            self._avanzar_reproduccion()

    def _avanzar_reproduccion(self) -> None:
        """Avanza un minuto y agenda el siguiente paso de la animación."""
        if not self.reproduciendo:
            return
        if self.minuto >= self.duracion:
            self.reproduciendo = False
            return
        self.minuto += 1
        self._actualizar_posiciones()
        self.raiz.after(650, self._avanzar_reproduccion)

    def pausar(self) -> None:
        """Detiene la animación sin cambiar el minuto actual."""
        self.reproduciendo = False

    def avanzar(self) -> None:
        """Muestra el siguiente minuto sin iniciar la reproducción continua."""
        self.pausar()
        self.minuto = min(self.duracion, self.minuto + 1)
        self._actualizar_posiciones()

    def reiniciar(self) -> None:
        """Vuelve al minuto cero y deja la animación pausada."""
        self.pausar()
        self.minuto = 0
        self._actualizar_posiciones()

    def mostrar(self) -> None:
        """Entra en el ciclo de eventos de Tkinter y mantiene abierta la ventana."""
        self.raiz.mainloop()


def mostrar_visualizacion(
    grafo: GrafoMetro,
    mision: Mision,
    plan: PlanSincronizado,
    restricciones: Restricciones,
) -> None:
    """Construye y muestra la ventana de las rutas sincronizadas."""
    try:
        VisualizadorMetro(
            grafo, mision, plan, restricciones
        ).mostrar()
    except tk.TclError as error:
        raise RuntimeError(str(error)) from error
