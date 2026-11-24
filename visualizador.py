"""Centro de comando táctico para explorar y reproducir rutas del metro."""

from __future__ import annotations

import math
import random
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from buscador_rutas import (
    NodoRuta,
    PlanSincronizado,
    minuto_primera_salida,
    planificar_sincronizacion,
)
from red_metro import (
    Arista,
    ErrorEntrada,
    GrafoMetro,
    Mision,
    Restricciones,
    leer_entrada,
)


_FONDO_APP = "#090d16"
_FONDO_TARJETA = "#111827"
_FONDO_MAPA = "#0b1120"
_BORDE = "#1e293b"
_TEXTO = "#f8fafc"
_TEXTO_SECUNDARIO = "#94a3b8"
_TENUE = "#334155"
_ACENTO = "#38bdf8"
_EXITO = "#22c55e"
_ALERTA = "#f43f5e"
_COLORES_PERSONAJE = {"Pierre": "#06b6d4", "Amélie": "#ec4899"}
_COLORES_LINEA = (
    "#f59e0b",
    "#22c55e",
    "#3b82f6",
    "#a855f7",
    "#ef4444",
    "#14b8a6",
)


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
    """Centro de comando con mapa, protocolos y cronología interactivos."""

    def __init__(
        self,
        grafo: GrafoMetro,
        mision: Mision,
        plan: PlanSincronizado,
        restricciones: Restricciones,
    ) -> None:
        self.grafo = grafo
        self.mision = mision
        self.plan = plan
        self.restricciones = restricciones
        self.rutas = {
            "Pierre": plan.ruta_pierre,
            "Amélie": plan.ruta_amelie,
        }
        self.minuto = 0
        self.duracion = plan.tiempo_total
        self.reproduciendo = False
        self._after_id: str | None = None
        self._sincronizando_control = False
        self._nodo_arrastrado: int | None = None
        self._posiciones_manuales = False
        self.posiciones: dict[int, tuple[float, float]] = {}
        self._ultimo_tamano_mapa = (0, 0)
        self._colores_linea = self._calcular_colores_linea()
        self._filas_ruta: dict[str, list[str]] = {
            "Pierre": [],
            "Amélie": [],
        }
        self._velocidades = {"1x": 650, "2x": 325, "4x": 163}
        self._archivo_entrada = Path(__file__).with_name("input.txt")

        self.raiz = tk.Tk()
        self.raiz.title("Paris Metro | Centro de Comando Táctico")
        ancho = min(1680, max(1180, self.raiz.winfo_screenwidth() - 50))
        alto = min(1000, max(720, self.raiz.winfo_screenheight() - 90))
        self.raiz.geometry(f"{ancho}x{alto}")
        self.raiz.minsize(1120, 680)
        self._configurar_estilos()

        self.marco = ttk.Frame(self.raiz, padding=16, style="App.TFrame")
        self.marco.pack(fill=tk.BOTH, expand=True)
        self.marco.columnconfigure(0, weight=1)
        self.marco.rowconfigure(1, weight=1)
        self._crear_encabezado()
        self.contenido = ttk.Frame(self.marco, style="App.TFrame")
        self.contenido.grid(row=1, column=0, sticky="nsew")
        self.contenido.columnconfigure(0, weight=0, minsize=250)
        self.contenido.columnconfigure(1, weight=1, minsize=480)
        self.contenido.columnconfigure(2, weight=0, minsize=330)
        self.contenido.rowconfigure(0, weight=1)
        self._crear_dashboard()
        self._cargar_vista_entrada(self._archivo_entrada, avisar=False)
        self.raiz.bind("<space>", self._atajo_reproduccion)
        self.raiz.bind("<Left>", self._atajo_retroceder)
        self.raiz.bind("<Right>", self._atajo_avanzar)

    def _configurar_estilos(self) -> None:
        self.raiz.configure(background=_FONDO_APP)
        estilo = ttk.Style(self.raiz)
        estilo.theme_use("clam")
        estilo.configure("App.TFrame", background=_FONDO_APP)
        estilo.configure("Card.TFrame", background=_FONDO_TARJETA)
        estilo.configure(
            "Title.TLabel",
            background=_FONDO_APP,
            foreground=_TEXTO,
            font=("Segoe UI", 22, "bold"),
        )
        estilo.configure(
            "Subtitle.TLabel",
            background=_FONDO_APP,
            foreground=_TEXTO_SECUNDARIO,
            font=("Segoe UI", 10),
        )
        estilo.configure(
            "Section.TLabel",
            background=_FONDO_TARJETA,
            foreground=_TEXTO,
            font=("Segoe UI", 10, "bold"),
        )
        estilo.configure(
            "Muted.TLabel",
            background=_FONDO_TARJETA,
            foreground=_TEXTO_SECUNDARIO,
            font=("Segoe UI", 9),
        )
        estilo.configure(
            "Body.TLabel",
            background=_FONDO_TARJETA,
            foreground=_TEXTO,
            font=("Segoe UI", 10),
        )
        estilo.configure(
            "Metric.TLabel",
            background="#172337",
            foreground=_ACENTO,
            font=("Segoe UI", 14, "bold"),
            padding=(10, 8),
        )
        estilo.configure(
            "Primary.TButton",
            background="#0369a1",
            foreground=_TEXTO,
            font=("Segoe UI", 9, "bold"),
            padding=(9, 7),
            borderwidth=0,
        )
        estilo.map(
            "Primary.TButton",
            background=[("active", "#0284c7"), ("pressed", "#075985")],
        )
        estilo.configure(
            "Secondary.TButton",
            background="#1e293b",
            foreground=_TEXTO,
            font=("Segoe UI", 9, "bold"),
            padding=(8, 6),
            borderwidth=0,
        )
        estilo.map(
            "Secondary.TButton",
            background=[("active", "#334155"), ("pressed", "#475569")],
        )
        estilo.configure(
            "TNotebook",
            background=_FONDO_TARJETA,
            borderwidth=0,
        )
        estilo.configure(
            "TNotebook.Tab",
            background="#1e293b",
            foreground=_TEXTO_SECUNDARIO,
            padding=(10, 7),
            font=("Segoe UI", 9, "bold"),
        )
        estilo.map(
            "TNotebook.Tab",
            background=[("selected", "#172337")],
            foreground=[("selected", _TEXTO)],
        )
        estilo.configure(
            "Treeview",
            background="#0b1120",
            fieldbackground="#0b1120",
            foreground=_TEXTO,
            rowheight=27,
            bordercolor=_BORDE,
            font=("Segoe UI", 9),
        )
        estilo.configure(
            "Treeview.Heading",
            background="#1e293b",
            foreground=_TEXTO,
            font=("Segoe UI", 9, "bold"),
            relief="flat",
        )
        estilo.map(
            "Treeview",
            background=[("selected", "#164e63")],
            foreground=[("selected", _TEXTO)],
        )
        estilo.configure(
            "TCombobox",
            fieldbackground="#0b1120",
            background="#1e293b",
            foreground=_TEXTO,
            arrowcolor=_TEXTO,
        )
        estilo.configure(
            "Horizontal.TScale",
            background=_FONDO_TARJETA,
            troughcolor="#334155",
        )
        estilo.configure(
            "Horizontal.TProgressbar",
            background=_ACENTO,
            troughcolor="#1e293b",
            bordercolor="#1e293b",
            lightcolor=_ACENTO,
            darkcolor=_ACENTO,
        )

    def _crear_encabezado(self) -> None:
        encabezado = ttk.Frame(self.marco, style="App.TFrame")
        encabezado.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        encabezado.columnconfigure(0, weight=1)
        ttk.Label(
            encabezado,
            text="CENTRO DE COMANDO TÁCTICO",
            style="Title.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            encabezado,
            text="METRO DE PARÍS  /  OPERACIONES DE EVACUACIÓN",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))
        self.estado_global = ttk.Label(
            encabezado,
            text="●  SINCRONIZACIÓN ESTABLE",
            style="Metric.TLabel",
        )
        self.estado_global.grid(row=0, column=1, rowspan=2, sticky="e")

    def _crear_dashboard(self) -> None:
        for hijo in self.contenido.winfo_children():
            hijo.destroy()
        self._crear_panel_entrada()
        self._crear_panel_mapa()
        self._crear_panel_derecho()
        self._poblar_itinerarios()
        self._actualizar_reporte()
        self._dibujar_mapa()
        self._actualizar_posiciones()

    def _tarjeta(self, parent: tk.Misc, padding: int = 12) -> ttk.Frame:
        return ttk.Frame(parent, padding=padding, style="Card.TFrame")

    def _crear_panel_entrada(self) -> None:
        panel = self._tarjeta(self.contenido, 12)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(2, weight=1)
        ttk.Label(
            panel, text="01  /  ENTRADA DE MISIÓN", style="Section.TLabel"
        ).grid(row=0, column=0, sticky="w")
        self.archivo_label = ttk.Label(
            panel, text=str(self._archivo_entrada), style="Muted.TLabel"
        )
        self.archivo_label.grid(row=1, column=0, sticky="ew", pady=(5, 6))
        editor_frame = ttk.Frame(panel, style="Card.TFrame")
        editor_frame.grid(row=2, column=0, sticky="nsew")
        editor_frame.rowconfigure(0, weight=1)
        editor_frame.columnconfigure(0, weight=1)
        self.entrada_texto = tk.Text(
            editor_frame,
            wrap=tk.NONE,
            height=14,
            background="#0b1120",
            foreground="#cbd5e1",
            insertbackground=_TEXTO,
            selectbackground="#164e63",
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=8,
            font=("Consolas", 9),
            state=tk.DISABLED,
        )
        self.entrada_texto.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(
            editor_frame, orient=tk.VERTICAL, command=self.entrada_texto.yview
        )
        scroll.grid(row=0, column=1, sticky="ns")
        self.entrada_texto.configure(yscrollcommand=scroll.set)
        ttk.Button(
            panel,
            text="Cargar archivo .txt y recalcular",
            command=self._seleccionar_entrada,
            style="Primary.TButton",
        ).grid(row=3, column=0, sticky="ew", pady=(8, 12))

        ttk.Separator(panel).grid(row=4, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(
            panel, text="PROTOCOLOS DE SEGURIDAD", style="Section.TLabel"
        ).grid(row=5, column=0, sticky="w", pady=(0, 8))
        self.protocolos: dict[str, ttk.Label] = {}
        for fila, nombre in enumerate(
            (
                "No-Colisión Temporal",
                "No-Colisión Espacial",
                "Restricciones de Línea",
            ),
            start=6,
        ):
            etiqueta = ttk.Label(panel, text="", style="Body.TLabel")
            etiqueta.grid(row=fila, column=0, sticky="ew", pady=3)
            self.protocolos[nombre] = etiqueta
        self.resumen_red = ttk.Label(
            panel, text="", style="Muted.TLabel", justify=tk.LEFT
        )
        self.resumen_red.grid(row=9, column=0, sticky="ew", pady=(10, 0))
        self._actualizar_protocolos()

    def _crear_panel_mapa(self) -> None:
        panel = self._tarjeta(self.contenido, 12)
        panel.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        panel.rowconfigure(1, weight=1)
        panel.columnconfigure(0, weight=1)
        encabezado = ttk.Frame(panel, style="Card.TFrame")
        encabezado.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        encabezado.columnconfigure(0, weight=1)
        ttk.Label(
            encabezado, text="02  /  MAPA OPERACIONAL", style="Section.TLabel"
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            encabezado,
            text=f"{self.grafo.n_estaciones} estaciones   ·   "
            f"{self.grafo.n_tuneles} túneles   ·   arrastra nodos para ordenar",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))
        leyenda_lineas = ttk.Frame(encabezado, style="Card.TFrame")
        leyenda_lineas.grid(row=2, column=0, sticky="w", pady=(5, 0))
        for indice, (linea, color) in enumerate(self._colores_linea.items()):
            ttk.Label(
                leyenda_lineas,
                text=f"● {linea}",
                background=_FONDO_TARJETA,
                foreground=color,
                font=("Segoe UI", 8, "bold"),
            ).grid(row=0, column=indice, sticky="w", padx=(0, 9))
        self.mapa = tk.Canvas(
            panel,
            background=_FONDO_MAPA,
            highlightthickness=1,
            highlightbackground=_BORDE,
            bd=0,
            cursor="hand2",
        )
        self.mapa.grid(row=1, column=0, sticky="nsew")
        self.mapa.bind("<Configure>", self._redimensionar_mapa)
        self.mapa.bind("<ButtonPress-1>", self._iniciar_arrastre)
        self.mapa.bind("<B1-Motion>", self._arrastrar_nodo)
        self.mapa.bind("<ButtonRelease-1>", self._terminar_arrastre)
        self.alerta_colision = ttk.Label(
            panel, text="", style="Muted.TLabel", anchor=tk.CENTER
        )
        self.alerta_colision.grid(row=2, column=0, sticky="ew", pady=(6, 2))
        self._crear_controles(panel, 3)

    def _crear_controles(self, parent: tk.Misc, row: int) -> None:
        controles = ttk.Frame(parent, style="Card.TFrame")
        controles.grid(row=row, column=0, sticky="ew", pady=(8, 0))
        controles.columnconfigure(0, weight=1)
        barra = ttk.Frame(controles, style="Card.TFrame")
        barra.grid(row=0, column=0, sticky="ew")
        barra.columnconfigure(0, weight=1)
        ttk.Label(barra, text="REPRODUCCIÓN", style="Muted.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(barra, text="VELOCIDAD", style="Muted.TLabel").grid(
            row=0, column=1, sticky="e", padx=(8, 4)
        )
        self.velocidad = tk.StringVar(value="1x")
        selector = ttk.Combobox(
            barra,
            textvariable=self.velocidad,
            values=tuple(self._velocidades),
            state="readonly",
            width=5,
        )
        selector.grid(row=0, column=2, sticky="e")
        self.reloj = ttk.Label(
            controles,
            text="",
            background=_FONDO_TARJETA,
            foreground=_ACENTO,
            font=("Segoe UI", 20, "bold"),
        )
        self.reloj.grid(row=1, column=0, sticky="w", pady=(3, 0))
        self.progreso = ttk.Progressbar(
            controles,
            maximum=max(1, self.duracion),
            mode="determinate",
            style="Horizontal.TProgressbar",
        )
        self.progreso.grid(row=2, column=0, sticky="ew", pady=(3, 4))
        self.control_minuto = ttk.Scale(
            controles,
            from_=0,
            to=max(1, self.duracion),
            command=self._cambiar_minuto,
            style="Horizontal.TScale",
        )
        self.control_minuto.grid(row=3, column=0, sticky="ew", pady=(0, 7))
        botones = ttk.Frame(controles, style="Card.TFrame")
        botones.grid(row=4, column=0, sticky="ew")
        for columna in range(5):
            botones.columnconfigure(columna, weight=1)
        acciones = (
            ("▶ Iniciar", self.iniciar, "Primary.TButton"),
            ("Ⅱ Pausar", self.pausar, "Secondary.TButton"),
            ("← Min", self.retroceder, "Secondary.TButton"),
            ("Avanzar →", self.avanzar, "Secondary.TButton"),
            ("Reiniciar ↺", self.reiniciar, "Secondary.TButton"),
        )
        for columna, (texto, accion, estilo) in enumerate(acciones):
            ttk.Button(
                botones, text=texto, command=accion, style=estilo
            ).grid(
                row=0,
                column=columna,
                sticky="ew",
                padx=(0 if columna == 0 else 3, 0),
            )
        ttk.Label(
            controles,
            text="Atajos: Espacio pausar/reanudar · ←/→ cambiar minuto",
            style="Muted.TLabel",
        ).grid(row=5, column=0, sticky="w", pady=(6, 0))

    def _crear_panel_derecho(self) -> None:
        panel = self._tarjeta(self.contenido, 10)
        panel.grid(row=0, column=2, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(2, weight=1)
        ttk.Label(
            panel, text="03  /  INTELIGENCIA DE MISIÓN", style="Section.TLabel"
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))
        metricas = ttk.Frame(panel, style="Card.TFrame")
        metricas.grid(row=1, column=0, sticky="new", pady=(0, 8))
        for columna in range(3):
            metricas.columnconfigure(columna, weight=1, uniform="metricas")
        self.metricas: dict[str, ttk.Label] = {}
        for columna, (clave, titulo) in enumerate(
            (
                ("tiempo", "T MAX"),
                ("desfase", "DESFASE"),
                ("estado", "ESTADO"),
            )
        ):
            tarjeta = ttk.Frame(
                metricas, padding=7, style="Card.TFrame"
            )
            tarjeta.grid(
                row=0, column=columna, sticky="nsew", padx=(0, 5)
            )
            ttk.Label(
                tarjeta, text=titulo, style="Muted.TLabel"
            ).pack(anchor=tk.W)
            valor = ttk.Label(
                tarjeta,
                text="",
                background="#172337",
                foreground=_ACENTO,
                font=("Segoe UI", 10, "bold"),
                wraplength=95,
                justify=tk.LEFT,
            )
            valor.pack(fill=tk.X, pady=(4, 0))
            self.metricas[clave] = valor

        self.notebook = ttk.Notebook(panel)
        self.notebook.grid(row=2, column=0, sticky="nsew")
        self.tab_itinerarios = ttk.Frame(
            self.notebook, padding=7, style="Card.TFrame"
        )
        self.tab_reporte = ttk.Frame(
            self.notebook, padding=7, style="Card.TFrame"
        )
        self.notebook.add(self.tab_itinerarios, text="Itinerarios")
        self.notebook.add(self.tab_reporte, text="Reporte output.txt")
        self._crear_vistas_itinerario()
        self._crear_vista_reporte()
        self._actualizar_metricas()

    def _crear_vistas_itinerario(self) -> None:
        self.tab_itinerarios.columnconfigure(0, weight=1)
        self.tab_itinerarios.rowconfigure(1, weight=1)
        self.tab_itinerarios.rowconfigure(3, weight=1)
        self.arboles: dict[str, ttk.Treeview] = {}
        for fila, nombre in ((0, "Pierre"), (2, "Amélie")):
            ttk.Label(
                self.tab_itinerarios,
                text=f"●  {nombre.upper()}",
                background=_FONDO_TARJETA,
                foreground=_COLORES_PERSONAJE[nombre],
                font=("Segoe UI", 9, "bold"),
            ).grid(row=fila, column=0, sticky="w", pady=(3, 4))
            arbol = ttk.Treeview(
                self.tab_itinerarios,
                columns=("minuto", "estacion", "evento"),
                show="headings",
                height=6,
                selectmode="none",
            )
            arbol.heading("minuto", text="MIN")
            arbol.heading("estacion", text="EST.")
            arbol.heading("evento", text="EVENTO")
            arbol.column("minuto", width=45, stretch=False, anchor=tk.CENTER)
            arbol.column(
                "estacion", width=48, stretch=False, anchor=tk.CENTER
            )
            arbol.column("evento", width=150, stretch=True)
            arbol.tag_configure("activo", background="#164e63")
            arbol.grid(row=fila + 1, column=0, sticky="nsew")
            self.arboles[nombre] = arbol

    def _crear_vista_reporte(self) -> None:
        self.tab_reporte.rowconfigure(0, weight=1)
        self.tab_reporte.columnconfigure(0, weight=1)
        texto_frame = ttk.Frame(self.tab_reporte, style="Card.TFrame")
        texto_frame.grid(row=0, column=0, sticky="nsew")
        texto_frame.rowconfigure(0, weight=1)
        texto_frame.columnconfigure(0, weight=1)
        self.reporte_texto = tk.Text(
            texto_frame,
            wrap=tk.WORD,
            background="#0b1120",
            foreground="#cbd5e1",
            insertbackground=_TEXTO,
            selectbackground="#164e63",
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=8,
            font=("Consolas", 9),
            state=tk.DISABLED,
        )
        self.reporte_texto.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(
            texto_frame,
            orient=tk.VERTICAL,
            command=self.reporte_texto.yview,
        )
        scroll.grid(row=0, column=1, sticky="ns")
        self.reporte_texto.configure(yscrollcommand=scroll.set)
        ttk.Button(
            self.tab_reporte,
            text="Copiar reporte al portapapeles",
            command=self._copiar_reporte,
            style="Secondary.TButton",
        ).grid(row=1, column=0, sticky="ew", pady=(7, 0))

    def _calcular_colores_linea(self) -> dict[str, str]:
        lineas = sorted(
            {
                arista.linea
                for estacion in self.grafo.estaciones()
                for arista in self.grafo.vecinos(estacion)
            }
        )
        return {
            linea: _COLORES_LINEA[indice % len(_COLORES_LINEA)]
            for indice, linea in enumerate(lineas)
        }

    def _actualizar_protocolos(self) -> None:
        if not hasattr(self, "protocolos"):
            return
        reglas = len(self.restricciones.lineas_dobles) + len(
            self.restricciones.cierres
        )
        valores = {
            "No-Colisión Temporal": "●  ACTIVO  ·  plan sincronizado",
            "No-Colisión Espacial": "●  ACTIVO  ·  rutas separadas",
            "Restricciones de Línea": (
                f"●  {reglas} REGLA(S)  ·  "
                f"{len(self.restricciones.lineas_dobles)} retrasos / "
                f"{len(self.restricciones.cierres)} cierres"
            ),
        }
        for nombre, texto in valores.items():
            self.protocolos[nombre].configure(
                text=texto, foreground=_EXITO
            )
        dobles = ", ".join(sorted(self.restricciones.lineas_dobles)) or "—"
        cierres = ", ".join(
            f"{linea} min {inicio}-{fin}"
            for linea, inicio, fin in self.restricciones.cierres
        ) or "—"
        self.resumen_red.configure(
            text=f"Red: {self.grafo.n_estaciones} estaciones · "
            f"{self.grafo.n_tuneles} túneles\n"
            f"Líneas dobles: {dobles}\nCierres: {cierres}"
        )

    def _actualizar_metricas(self) -> None:
        if not hasattr(self, "metricas"):
            return
        salida_p = minuto_primera_salida(self.rutas["Pierre"])
        salida_a = minuto_primera_salida(self.rutas["Amélie"])
        desfase = abs(salida_p - salida_a)
        if desfase == 0:
            texto_desfase = "Salidas parejas"
        elif salida_p > salida_a:
            texto_desfase = f"Pierre espera {desfase} min"
        else:
            texto_desfase = f"Amélie espera {desfase} min"
        self.metricas["tiempo"].configure(
            text=f"{self.duracion} min", foreground=_ACENTO
        )
        self.metricas["desfase"].configure(
            text=texto_desfase, foreground="#fbbf24"
        )
        self.metricas["estado"].configure(
            text="SIN COLISIÓN", foreground=_EXITO
        )

    def _poblar_itinerarios(self) -> None:
        if not hasattr(self, "arboles"):
            return
        for nombre, ruta in self.rutas.items():
            arbol = self.arboles[nombre]
            arbol.delete(*arbol.get_children())
            self._filas_ruta[nombre] = []
            for paso in ruta:
                fila = arbol.insert(
                    "",
                    tk.END,
                    values=(
                        f"{paso.minuto:03d}",
                        paso.estacion,
                        paso.evento,
                    ),
                )
                self._filas_ruta[nombre].append(fila)
        self._actualizar_filas_activas()

    def _actualizar_reporte(self) -> None:
        if not hasattr(self, "reporte_texto"):
            return
        from main import crear_reporte

        reporte = crear_reporte(
            self.grafo.n_estaciones,
            self.grafo.n_tuneles,
            self.mision,
            self.plan,
        )
        self.reporte_texto.configure(state=tk.NORMAL)
        self.reporte_texto.delete("1.0", tk.END)
        self.reporte_texto.insert("1.0", reporte)
        self.reporte_texto.configure(state=tk.DISABLED)

    def _copiar_reporte(self) -> None:
        reporte = self.reporte_texto.get("1.0", "end-1c")
        self.raiz.clipboard_clear()
        self.raiz.clipboard_append(reporte)
        self.estado_global.configure(
            text="●  REPORTE COPIADO", foreground=_EXITO
        )

    def _seleccionar_entrada(self) -> None:
        nombre = filedialog.askopenfilename(
            parent=self.raiz,
            title="Seleccionar archivo de red y misión",
            filetypes=(("Archivos de texto", "*.txt"), ("Todos los archivos", "*")),
            initialdir=str(self._archivo_entrada.parent),
        )
        if not nombre:
            return
        ruta = Path(nombre)
        try:
            contenido = ruta.read_text(encoding="utf-8")
        except OSError as error:
            messagebox.showerror(
                "No se pudo leer el archivo", str(error), parent=self.raiz
            )
            return
        self._mostrar_entrada(ruta, contenido)
        if messagebox.askyesno(
            "Recalcular misión",
            "¿Cargar esta entrada y recalcular la sincronización?",
            parent=self.raiz,
        ):
            self._cargar_vista_entrada(ruta, contenido=contenido, avisar=True)

    def _cargar_vista_entrada(
        self,
        ruta: Path,
        contenido: str | None = None,
        avisar: bool = True,
    ) -> None:
        try:
            texto = (
                contenido
                if contenido is not None
                else ruta.read_text(encoding="utf-8")
            )
            grafo, mision, restricciones = leer_entrada(str(ruta))
            plan = planificar_sincronizacion(
                grafo,
                restricciones,
                mision.origen_pierre,
                mision.origen_amelie,
                mision.puerta_pierre,
                mision.puerta_amelie,
            )
            if plan is None:
                raise ErrorEntrada(
                    "No se encontró una llegada simultánea sin colisiones "
                    "dentro del horizonte de búsqueda."
                )
        except (ErrorEntrada, OSError, ValueError) as error:
            messagebox.showerror(
                "No se pudo recalcular la misión",
                str(error),
                parent=self.raiz,
            )
            return

        self.grafo = grafo
        self.mision = mision
        self.restricciones = restricciones
        self.plan = plan
        self.rutas = {
            "Pierre": plan.ruta_pierre,
            "Amélie": plan.ruta_amelie,
        }
        self.duracion = plan.tiempo_total
        self.minuto = 0
        self._archivo_entrada = ruta
        self._colores_linea = self._calcular_colores_linea()
        self.posiciones = {}
        self._ultimo_tamano_mapa = (0, 0)
        self._posiciones_manuales = False
        self._crear_dashboard()
        self._mostrar_entrada(ruta, texto)
        self._actualizar_metricas()
        self._actualizar_protocolos()
        self.estado_global.configure(
            text="●  SINCRONIZACIÓN ESTABLE", foreground=_ACENTO
        )
        if avisar:
            messagebox.showinfo(
                "Misión actualizada",
                "La red, las rutas y el reporte fueron recalculados.",
                parent=self.raiz,
            )

    def _mostrar_entrada(self, ruta: Path, contenido: str) -> None:
        self.archivo_label.configure(text=str(ruta))
        self.entrada_texto.configure(state=tk.NORMAL)
        self.entrada_texto.delete("1.0", tk.END)
        self.entrada_texto.insert("1.0", contenido)
        self.entrada_texto.configure(state=tk.DISABLED)

    def _calcular_posiciones(
        self, ancho: int, alto: int
    ) -> dict[int, tuple[float, float]]:
        """Calcula un layout orgánico y determinista con fuerzas de repulsión."""
        estaciones = sorted(self.grafo.estaciones())
        cantidad = len(estaciones)
        if cantidad == 0:
            return {}
        ancho_util = max(120, ancho - 80)
        alto_util = max(120, alto - 80)
        area = ancho_util * alto_util
        k = math.sqrt(area / cantidad)
        rng = random.Random(2026)
        puntos = {
            estacion: [
                ancho / 2 + rng.uniform(-ancho_util * 0.32, ancho_util * 0.32),
                alto / 2 + rng.uniform(-alto_util * 0.32, alto_util * 0.32),
            ]
            for estacion in estaciones
        }
        aristas = {
            tuple(sorted((arista.origen, arista.destino)))
            for estacion in estaciones
            for arista in self.grafo.vecinos(estacion)
            if arista.origen != arista.destino
        }
        temperatura_inicial = min(ancho, alto) * 0.12
        for iteracion in range(90):
            fuerzas = {estacion: [0.0, 0.0] for estacion in estaciones}
            for indice, uno in enumerate(estaciones):
                for dos in estaciones[indice + 1 :]:
                    dx = puntos[uno][0] - puntos[dos][0]
                    dy = puntos[uno][1] - puntos[dos][1]
                    distancia = max(math.hypot(dx, dy), 0.01)
                    fuerza = (k * k) / distancia
                    fx, fy = dx / distancia * fuerza, dy / distancia * fuerza
                    fuerzas[uno][0] += fx
                    fuerzas[uno][1] += fy
                    fuerzas[dos][0] -= fx
                    fuerzas[dos][1] -= fy
            for uno, dos in aristas:
                dx = puntos[uno][0] - puntos[dos][0]
                dy = puntos[uno][1] - puntos[dos][1]
                distancia = max(math.hypot(dx, dy), 0.01)
                fuerza = (distancia * distancia) / k
                fx, fy = dx / distancia * fuerza, dy / distancia * fuerza
                fuerzas[uno][0] -= fx
                fuerzas[uno][1] -= fy
                fuerzas[dos][0] += fx
                fuerzas[dos][1] += fy
            temperatura = temperatura_inicial * (1 - iteracion / 90)
            for estacion in estaciones:
                fx, fy = fuerzas[estacion]
                distancia = max(math.hypot(fx, fy), 0.01)
                paso = min(distancia, temperatura)
                puntos[estacion][0] += fx / distancia * paso
                puntos[estacion][1] += fy / distancia * paso
                puntos[estacion][0] = min(
                    ancho - 35, max(35, puntos[estacion][0])
                )
                puntos[estacion][1] = min(
                    alto - 35, max(35, puntos[estacion][1])
                )

        minimo_x = min(punto[0] for punto in puntos.values())
        maximo_x = max(punto[0] for punto in puntos.values())
        minimo_y = min(punto[1] for punto in puntos.values())
        maximo_y = max(punto[1] for punto in puntos.values())
        rango_x = max(1.0, maximo_x - minimo_x)
        rango_y = max(1.0, maximo_y - minimo_y)
        escala = min((ancho - 70) / rango_x, (alto - 70) / rango_y)
        return {
            estacion: (
                (punto[0] - minimo_x) * escala
                + (ancho - rango_x * escala) / 2,
                (punto[1] - minimo_y) * escala
                + (alto - rango_y * escala) / 2,
            )
            for estacion, punto in puntos.items()
        }

    def _redimensionar_mapa(self, evento) -> None:
        tamano = (evento.width, evento.height)
        if min(tamano) < 100 or tamano == self._ultimo_tamano_mapa:
            return
        anterior = self._ultimo_tamano_mapa
        self._ultimo_tamano_mapa = tamano
        if self.posiciones and self._posiciones_manuales and min(anterior) > 0:
            sx, sy = tamano[0] / anterior[0], tamano[1] / anterior[1]
            self.posiciones = {
                estacion: (x * sx, y * sy)
                for estacion, (x, y) in self.posiciones.items()
            }
        else:
            self.posiciones = self._calcular_posiciones(*tamano)
        self._dibujar_mapa()
        self._actualizar_posiciones()

    def _dibujar_rejilla(self) -> None:
        ancho = self.mapa.winfo_width()
        alto = self.mapa.winfo_height()
        for x in range(0, ancho, 40):
            self.mapa.create_line(
                x, 0, x, alto, fill="#111b2d", width=1, tags=("rejilla",)
            )
        for y in range(0, alto, 40):
            self.mapa.create_line(
                0, y, ancho, y, fill="#111b2d", width=1, tags=("rejilla",)
            )
        for x in range(40, ancho, 160):
            self.mapa.create_text(
                x + 4,
                4,
                text=f"X{x:04d}",
                anchor=tk.NW,
                fill="#334155",
                font=("Consolas", 7),
                tags=("rejilla",),
            )

    def _aristas_de_ruta(self) -> dict[str, set[tuple[int, int, str]]]:
        rutas: dict[str, set[tuple[int, int, str]]] = {}
        for nombre, ruta in self.rutas.items():
            rutas[nombre] = {
                (paso.arista.origen, paso.arista.destino, paso.arista.linea)
                for paso in ruta
                if paso.arista is not None
            }
        return rutas

    def _dibujar_mapa(self) -> None:
        if not hasattr(self, "mapa"):
            return
        estaciones = set(self.grafo.estaciones())
        if not estaciones.issubset(self.posiciones):
            ancho = max(480, self.mapa.winfo_width())
            alto = max(400, self.mapa.winfo_height())
            self.posiciones = self._calcular_posiciones(ancho, alto)
        self.mapa.delete("all")
        self._dibujar_rejilla()
        rutas = self._aristas_de_ruta()
        aristas = [
            arista
            for estacion in self.grafo.estaciones()
            for arista in self.grafo.vecinos(estacion)
        ]
        for arista in aristas:
            clave = (arista.origen, arista.destino, arista.linea)
            presentes = [
                nombre for nombre in rutas if clave in rutas[nombre]
            ]
            if not presentes:
                self._dibujar_arista(arista, _TENUE, 1.2, "tunel")
                continue
            for indice, nombre in enumerate(presentes):
                color = _COLORES_PERSONAJE[nombre]
                self._dibujar_arista(arista, color, 8, "halo", indice * 5)
                self._dibujar_arista(arista, color, 3, "ruta", indice * 5)
        for estacion in sorted(self.grafo.estaciones()):
            self._dibujar_estacion(estacion)
        self._dibujar_leyenda()

    def _dibujar_arista(
        self,
        arista: Arista,
        color: str,
        grosor: float,
        etiqueta: str,
        desplazamiento: float = 0,
    ) -> None:
        if arista.origen not in self.posiciones or arista.destino not in self.posiciones:
            return
        x1, y1 = self.posiciones[arista.origen]
        x2, y2 = self.posiciones[arista.destino]
        dx, dy = x2 - x1, y2 - y1
        distancia = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / distancia, dx / distancia
        mx = (x1 + x2) / 2 + nx * desplazamiento
        my = (y1 + y2) / 2 + ny * desplazamiento
        margen = min(20.0, distancia * 0.22)
        sx, sy = x1 + dx * margen / distancia, y1 + dy * margen / distancia
        ex, ey = x2 - dx * margen / distancia, y2 - dy * margen / distancia
        if desplazamiento:
            sx, sy = sx + nx * desplazamiento, sy + ny * desplazamiento
            ex, ey = ex + nx * desplazamiento, ey + ny * desplazamiento
        tags = (etiqueta, f"edge_{arista.origen}_{arista.destino}")
        self.mapa.create_line(
            sx,
            sy,
            mx,
            my,
            ex,
            ey,
            smooth=True,
            arrow=tk.LAST,
            arrowshape=(8, 10, 4),
            width=grosor,
            fill=color,
            tags=tags,
        )
        if etiqueta == "tunel" or grosor == 3:
            texto = f"{arista.linea}·{self.restricciones.peso(arista)}"
            self.mapa.create_text(
                mx,
                my,
                text=texto,
                fill=color if grosor > 2 else "#64748b",
                font=("Segoe UI", 7, "bold"),
                tags=("etiqueta_arista",),
            )

    def _dibujar_estacion(self, estacion: int) -> None:
        x, y = self.posiciones[estacion]
        extremos = {
            self.mision.origen_pierre: _COLORES_PERSONAJE["Pierre"],
            self.mision.origen_amelie: _COLORES_PERSONAJE["Amélie"],
            self.mision.puerta_pierre: _COLORES_PERSONAJE["Pierre"],
            self.mision.puerta_amelie: _COLORES_PERSONAJE["Amélie"],
        }
        color = extremos.get(estacion, "#64748b")
        grosor = 2 if estacion in extremos else 1
        self.mapa.create_oval(
            x - 14,
            y - 14,
            x + 14,
            y + 14,
            fill="#111827",
            outline=color,
            width=grosor,
            tags=("nodo", f"estacion_{estacion}"),
        )
        self.mapa.create_text(
            x,
            y,
            text=str(estacion),
            fill=_TEXTO,
            font=("Segoe UI", 9, "bold"),
            tags=("nodo", f"estacion_{estacion}"),
        )
        self.mapa.create_text(
            x,
            y + 23,
            text=f"t{self.grafo.tiempo_transbordo(estacion)}",
            fill=_TEXTO_SECUNDARIO,
            font=("Segoe UI", 7),
            tags=("nodo", f"estacion_{estacion}"),
        )

    def _dibujar_leyenda(self) -> None:
        leyenda = (
            (self.mision.origen_pierre, "P / ORIGEN", _COLORES_PERSONAJE["Pierre"], -42, -25),
            (self.mision.origen_amelie, "A / ORIGEN", _COLORES_PERSONAJE["Amélie"], 42, -25),
            (self.mision.puerta_pierre, "D1", _COLORES_PERSONAJE["Pierre"], -25, 27),
            (self.mision.puerta_amelie, "D2", _COLORES_PERSONAJE["Amélie"], 25, 27),
        )
        for estacion, texto, color, dx, dy in leyenda:
            if estacion not in self.posiciones:
                continue
            x, y = self.posiciones[estacion]
            self.mapa.create_text(
                x + dx,
                y + dy,
                text=texto,
                fill=color,
                font=("Segoe UI", 7, "bold"),
                tags=("leyenda",),
            )

    def _iniciar_arrastre(self, evento) -> None:
        mejor: tuple[float, int] | None = None
        for estacion, (x, y) in self.posiciones.items():
            distancia = math.hypot(evento.x - x, evento.y - y)
            if distancia <= 22 and (mejor is None or distancia < mejor[0]):
                mejor = distancia, estacion
        self._nodo_arrastrado = mejor[1] if mejor else None

    def _arrastrar_nodo(self, evento) -> None:
        if self._nodo_arrastrado is None:
            return
        self.posiciones[self._nodo_arrastrado] = (
            max(20, min(self.mapa.winfo_width() - 20, evento.x)),
            max(20, min(self.mapa.winfo_height() - 20, evento.y)),
        )
        self._posiciones_manuales = True
        self._dibujar_mapa()
        self._actualizar_posiciones()

    def _terminar_arrastre(self, evento) -> None:
        _ = evento.widget
        self._nodo_arrastrado = None

    def _coordenada_posicion(
        self, posicion: Posicion, desplazamiento: tuple[float, float]
    ) -> tuple[float, float]:
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

    def _estado_personaje(
        self, nombre: str, posicion: Posicion
    ) -> tuple[str, str]:
        ruta = self.rutas[nombre]
        if posicion.tipo == "tunel":
            return (
                "EN TÚNEL",
                f"{posicion.origen} → {posicion.destino} · {posicion.linea}",
            )
        if posicion.estacion is None:
            return "EN TRÁNSITO", "Ubicación no disponible"
        destino = (
            self.mision.puerta_pierre
            if nombre == "Pierre"
            else self.mision.puerta_amelie
        )
        llegada = next(
            (paso.minuto for paso in ruta if paso.evento == "Destino"),
            ruta[-1].minuto,
        )
        if posicion.estacion == destino and self.minuto >= llegada:
            return "EN BÚNKER", f"Puerta segura · estación {destino}"
        siguiente = next(
            (
                paso
                for paso in ruta
                if paso.arista is not None
                and (
                    paso.minuto_salida
                    if paso.minuto_salida is not None
                    else paso.minuto
                )
                > self.minuto
            ),
            None,
        )
        if siguiente is not None:
            anterior = siguiente.previo
            salida = (
                siguiente.minuto_salida
                if siguiente.minuto_salida is not None
                else siguiente.minuto
            )
            if salida > self.minuto:
                if (
                    anterior is not None
                    and anterior.linea is not None
                    and anterior.linea != siguiente.arista.linea
                ):
                    return "TRANSBORDO", f"Estación {posicion.estacion}"
                return "EN ESPERA", f"Estación {posicion.estacion}"
        return "EN ESTACIÓN", f"Estación {posicion.estacion}"

    def _posiciones_colisionan(
        self, primera: Posicion, segunda: Posicion
    ) -> bool:
        if (
            primera.tipo == "estacion"
            and segunda.tipo == "estacion"
            and primera.estacion == segunda.estacion
        ):
            return True
        if primera.tipo != "tunel" or segunda.tipo != "tunel":
            return False
        mismo_tunel = (
            primera.origen == segunda.origen
            and primera.destino == segunda.destino
        ) or (
            primera.origen == segunda.destino
            and primera.destino == segunda.origen
        )
        return mismo_tunel and math.isclose(
            primera.progreso,
            1 - segunda.progreso
            if primera.origen == segunda.destino
            else segunda.progreso,
            abs_tol=0.03,
        )

    def _actualizar_posiciones(self) -> None:
        if not hasattr(self, "mapa") or not self.posiciones:
            return
        self.mapa.delete("dinamico")
        posiciones = {
            nombre: posicion_en_minuto(ruta, self.minuto)
            for nombre, ruta in self.rutas.items()
        }
        colision = self._posiciones_colisionan(
            posiciones["Pierre"], posiciones["Amélie"]
        )
        for nombre in ("Pierre", "Amélie"):
            posicion = posiciones[nombre]
            desplazamiento = (
                (-8, -8) if nombre == "Pierre" else (8, -8)
            )
            x, y = self._coordenada_posicion(posicion, desplazamiento)
            color = _ALERTA if colision else _COLORES_PERSONAJE[nombre]
            self.mapa.create_oval(
                x - 15,
                y - 15,
                x + 15,
                y + 15,
                fill="",
                outline=color,
                width=2,
                tags=("dinamico",),
            )
            self.mapa.create_oval(
                x - 9,
                y - 9,
                x + 9,
                y + 9,
                fill=color,
                outline=_TEXTO,
                width=1,
                tags=("dinamico",),
            )
            self.mapa.create_text(
                x,
                y,
                text=nombre[0],
                fill=_FONDO_APP,
                font=("Segoe UI", 8, "bold"),
                tags=("dinamico",),
            )
            estado, detalle = self._estado_personaje(nombre, posicion)
            etiqueta = f"{nombre.upper()} · {estado}\n{detalle}"
            self.mapa.create_text(
                x,
                y - 25,
                text=etiqueta,
                fill=color,
                font=("Segoe UI", 7, "bold"),
                tags=("dinamico",),
            )
        if colision:
            self.alerta_colision.configure(
                text="⚠ ALERTA: POSIBLE COINCIDENCIA DE PERSONAJES",
                foreground=_ALERTA,
            )
            self.estado_global.configure(
                text="●  ALERTA DE COLISIÓN", foreground=_ALERTA
            )
            self.metricas["estado"].configure(
                text="ALERTA", foreground=_ALERTA
            )
        else:
            self.alerta_colision.configure(
                text="PROTOCOLO DE SEPARACIÓN  /  ACTIVO",
                foreground=_EXITO,
            )
            self.estado_global.configure(
                text="●  SINCRONIZACIÓN ESTABLE", foreground=_ACENTO
            )
            self.metricas["estado"].configure(
                text="SIN COLISIÓN", foreground=_EXITO
            )
        self.reloj.configure(
            text=f"T + {self.minuto:03d}  /  {self.duracion:03d} MIN"
        )
        self.progreso.configure(value=self.minuto)
        self._sincronizando_control = True
        try:
            self.control_minuto.set(self.minuto)
        finally:
            self._sincronizando_control = False
        self._actualizar_filas_activas()

    def _indice_paso_activo(self, ruta: list[NodoRuta]) -> int:
        activo = 0
        for indice, paso in enumerate(ruta):
            if paso.arista is not None:
                salida = (
                    paso.minuto_salida
                    if paso.minuto_salida is not None
                    else paso.minuto
                )
                if salida <= self.minuto < paso.minuto:
                    return indice
            if paso.minuto <= self.minuto:
                activo = indice
            else:
                break
        return activo

    def _actualizar_filas_activas(self) -> None:
        if not hasattr(self, "arboles"):
            return
        for nombre, ruta in self.rutas.items():
            filas = self._filas_ruta.get(nombre, [])
            if not filas:
                continue
            indice = min(self._indice_paso_activo(ruta), len(filas) - 1)
            for fila in filas:
                self.arboles[nombre].item(fila, tags=())
            self.arboles[nombre].item(filas[indice], tags=("activo",))
            self.arboles[nombre].see(filas[indice])

    def _cambiar_minuto(self, valor: str) -> None:
        if self._sincronizando_control:
            return
        self.minuto = min(self.duracion, max(0, round(float(valor))))
        self._actualizar_posiciones()

    def iniciar(self) -> None:
        if self.minuto >= self.duracion:
            self.minuto = 0
        if not self.reproduciendo:
            self.reproduciendo = True
            self._avanzar_reproduccion()

    def _avanzar_reproduccion(self) -> None:
        self._after_id = None
        if not self.reproduciendo:
            return
        if self.minuto >= self.duracion:
            self.reproduciendo = False
            return
        self.minuto += 1
        self._actualizar_posiciones()
        velocidad = self.velocidad.get()
        self._after_id = self.raiz.after(
            self._velocidades.get(velocidad, 650),
            self._avanzar_reproduccion,
        )

    def pausar(self) -> None:
        self.reproduciendo = False
        if self._after_id is not None:
            self.raiz.after_cancel(self._after_id)
            self._after_id = None

    def avanzar(self) -> None:
        self.pausar()
        self.minuto = min(self.duracion, self.minuto + 1)
        self._actualizar_posiciones()

    def retroceder(self) -> None:
        self.pausar()
        self.minuto = max(0, self.minuto - 1)
        self._actualizar_posiciones()

    def reiniciar(self) -> None:
        self.pausar()
        self.minuto = 0
        self._actualizar_posiciones()

    def _atajo_reproduccion(self, evento) -> str:
        _ = evento.widget
        if self.reproduciendo:
            self.pausar()
        else:
            self.iniciar()
        return "break"

    def _atajo_retroceder(self, evento) -> str:
        _ = evento.widget
        self.retroceder()
        return "break"

    def _atajo_avanzar(self, evento) -> str:
        _ = evento.widget
        self.avanzar()
        return "break"

    def mostrar(self) -> None:
        self.raiz.mainloop()


def mostrar_visualizacion(
    grafo: GrafoMetro,
    mision: Mision,
    plan: PlanSincronizado,
    restricciones: Restricciones,
) -> None:
    """Construye y muestra el centro de comando de las rutas coordinadas."""
    try:
        VisualizadorMetro(grafo, mision, plan, restricciones).mostrar()
    except tk.TclError as error:
        raise RuntimeError(str(error)) from error
