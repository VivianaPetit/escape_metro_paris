# Escape en el Metro de París

Programa en Python que modela el metro como un grafo, sincroniza las rutas de
Pierre y Amélie y muestra su recorrido en una ventana gráfica. Solo usa la
biblioteca estándar; Tkinter se requiere para la ventana.

El proyecto está organizado en cinco archivos Python: red y entrada,
planificador, visualizador, ejecución y pruebas.

## Grafo elegido

En memoria se usa una **lista de adyacencia**: cada estación guarda sus túneles
salientes. Es adecuada porque la red tiene muchas menos conexiones que pares
posibles de estaciones.

La visualización sigue el estilo de la **Clase 15, “Caminos de Aumento de
Flujo”**: estaciones como nodos y túneles dirigidos como arcos con etiquetas.
Se adaptan las flechas y costos a las líneas del metro; no se muestran flujos ni
capacidades. La Clase 16 trata precedencias de proyectos, menos apropiadas para
una red de transporte con ciclos.

## Ejecutar

Desde esta carpeta:

```powershell
python main.py
```

Lee `input.txt`, calcula la operación, guarda `output.txt` y abre la
visualización. Para ejecutar solo en consola:

```powershell
python main.py --sin-grafica
python main.py otra_red.txt --salida resultado.txt --sin-grafica
```

En la ventana, **Iniciar**, **Pausar**, **Avanzar** y **Reiniciar** controlan la
animación; el deslizador permite elegir un minuto.

## Entrega en tres archivos

El proyecto de trabajo conserva sus módulos, README y pruebas. Para entregar
solo tres archivos, comprime los archivos fuente y la documentación en
`fuente_escape_metro_paris.zip`; entrega ese ZIP junto con `input.txt` y
`output.txt`. Extrae el ZIP en la misma carpeta que la entrada y la salida para
ejecutar el programa. Confirma con el docente que acepta el código fuente
comprimido como uno de los tres archivos.

## Entrada

El formato es: cantidad de estaciones y túneles dirigidos; una fila por
estación (`id tiempo_transbordo`); una por túnel (`origen destino tiempo línea`);
y la misión (`origen_pierre origen_amelie puerta_D1 puerta_D2`). Las líneas
pueden terminar en comentarios iniciados por `#`.

Directivas opcionales:

```text
DOBLE L7
SIN_TRANSBORDO L4 5 6
```

`DOBLE` duplica los tiempos de esa línea; `SIN_TRANSBORDO` cierra la línea en
el intervalo inclusivo indicado. Ver [input.txt](input.txt) para el ejemplo.

## Cómo funciona

- Dijkstra calcula rutas individuales considerando estación y línea.
- A* coordina a ambos fugitivos minuto a minuto, minimizando su llegada común
  y evitando compartir estaciones o túneles.
- El informe compara las duraciones individuales para mostrar el desfase
  teórico de salida y también las salidas usadas por el plan sin colisiones.
- Cada minuto de espera en una estación suma un punto de riesgo; los
  transbordos y los minutos dentro de túneles no cuentan como espera.
- La interfaz muestra líneas y pesos con flechas; los marcadores se mueven por
  estaciones y túneles. `output.txt` contiene las rutas y el horario.

## Archivos y funciones

### `red_metro.py` — red, reglas y entrada

| Clase o función | Descripción |
|---|---|
| `Arista` | Guarda origen, destino, peso y línea de un túnel dirigido. |
| `Arista.clave_tunel()` | Devuelve la clave física del túnel sin dirección. |
| `GrafoMetro` | Administra estaciones, aristas y listas de adyacencia. |
| `GrafoMetro.agregar_estacion(...)` / `agregar_tunel(...)` | Agregan y validan la red. |
| `GrafoMetro.existe(...)`, `estaciones()`, `vecinos(...)`, `predecesores(...)` | Consultan la estructura del grafo. |
| `GrafoMetro.tiempo_transbordo(...)`, `n_estaciones`, `n_tuneles` | Consultan tiempos y tamaños. |
| `Restricciones` | Guarda retrasos por línea y cierres de transbordo. |
| `Restricciones.peso(...)` / `transbordo_permitido(...)` | Calculan el costo y validan cambios de línea. |
| `Movimiento` / `movimientos_posibles(...)` | Representan y generan viajes legales con su horario. |
| `ErrorEntrada` / `Mision` | Representan errores de formato y datos de la misión. |
| `_entero(...)` / `leer_entrada(...)` | Convierten datos y leen la red desde el archivo. |

### `buscador_rutas.py` — planificación

| Clase o función | Descripción |
|---|---|
| `NodoRuta` | Representa un estado cronometrado de una ruta. |
| `NodoRuta.__lt__(otro)` | Ordena estados por minuto para el heap. |
| `PlanSincronizado` | Guarda ambas rutas, llegada simultánea y duraciones individuales mínimas. |
| `minuto_primera_salida(ruta)` | Devuelve cuándo se toma el primer túnel. |
| `minutos_espera(ruta)` | Cuenta los minutos de espera que generan riesgo. |
| `_EstadoPersonaje` | Estado interno: estación, transbordo o túnel. |
| `RastroEspacioTemporal.__init__()` | Inicializa el registro de ocupaciones. |
| `RastroEspacioTemporal._registrar_estacion(...)` | Marca una estación por minutos. |
| `RastroEspacioTemporal.registrar_ruta(...)` | Registra estaciones, esperas y túneles. |
| `RastroEspacioTemporal.colisiona_estacion(...)` | Consulta una estación en un minuto. |
| `RastroEspacioTemporal.colisiona_estacion_intervalo(...)` | Consulta un intervalo de estación. |
| `RastroEspacioTemporal.colisiona_tunel(...)` | Detecta cruces en un túnel. |
| `Planificador.__init__(...)` | Asocia el grafo y sus restricciones. |
| `Planificador._nodo_desde_movimiento(...)` | Crea el estado de llegada de un movimiento. |
| `Planificador.buscar_ruta_individual(...)` | Busca la ruta individual más rápida con Dijkstra. |
| `Planificador.buscar_ruta_sin_colision(...)` | Busca una ruta temporal evitando ocupaciones. |
| `Planificador.reconstruir_ruta(...)` | Reconstruye la ruta desde el estado final. |
| `Planificador.imprimir_ruta(...)` | Imprime los pasos de una ruta. |
| `_distancias_sin_transbordo(...)` | Calcula la heurística admisible de A*. |
| `_estacion_del_estado(...)` | Devuelve la estación ocupada por un estado. |
| `_cota_restante(...)` | Estima el tiempo restante sin sobreestimarlo. |
| `_acciones_posibles(...)` | Genera espera, viaje o continuación. |
| `_avanzar_estado(...)` | Avanza un personaje un minuto. |
| `_crear_paso_de_llegada(...)` | Crea un nodo al terminar un viaje. |
| `_reconstruir_rutas_conjuntas(...)` | Reconstruye las rutas de ambos fugitivos. |
| `planificar_sincronizacion(...)` | Encuentra la llegada conjunta más temprana. |

### `visualizador.py` — interfaz gráfica

| Clase o función | Descripción |
|---|---|
| `VisualizadorMetro` | Administra el mapa y la ventana interactiva. |
| `VisualizadorMetro.__init__(...)` | Prepara ventana, mapa y controles. |
| `Posicion` / `posicion_en_minuto(...)` | Calculan la ubicación de una ruta en cada instante. |
| `_configurar_estilos()` | Aplica la paleta y los estilos visuales. |
| `_crear_encabezado()` / `_crear_encabezado_mapa()` | Construyen los encabezados de la ventana y el mapa. |
| `_calcular_posiciones(ancho, alto)` | Distribuye las estaciones según el tamaño del mapa. |
| `_redimensionar_mapa(evento)` | Recalcula y dibuja el mapa al cambiar su tamaño. |
| `_calcular_colores_linea()` | Asigna colores a las líneas. |
| `_crear_panel()` | Construye leyendas, reloj y controles. |
| `_texto_resultado()` | Resume la llegada simultánea sin colisiones. |
| `_dibujar_mapa()` | Dibuja la red. |
| `_dibujar_tunel(...)` | Dibuja una arista, flecha y peso. |
| `_dibujar_estacion(...)` | Dibuja una estación y su transbordo. |
| `_dibujar_leyenda_puertas()` | Marca orígenes y puertas. |
| `_coordenada_posicion(...)` | Convierte una posición a coordenadas visuales. |
| `_actualizar_posiciones()` | Actualiza marcadores y reloj. |
| `_cambiar_minuto(valor)` | Responde al deslizador. |
| `iniciar()` / `_avanzar_reproduccion()` | Inicia y avanza la animación. |
| `pausar()` | Pausa la animación. |
| `avanzar()` | Avanza un minuto manualmente. |
| `reiniciar()` | Vuelve al minuto cero. |
| `mostrar()` | Inicia el ciclo de Tkinter. |
| `mostrar_visualizacion(...)` | Abre la ventana y reporta errores gráficos. |

### `main.py` — ejecución del programa

| Función | Descripción |
|---|---|
| `_argumentos()` | Lee las opciones de consola. |
| `_descripcion_ruta(...)` | Formatea una ruta para el reporte. |
| `_descripcion_salidas(plan)` | Describe el desfase de salida y los puntos de riesgo. |
| `crear_reporte(...)` | Compone el informe final. |
| `_mostrar_grafica(...)` | Inicia la interfaz. |
| `main()` | Coordina lectura, planificación y salida. |

### `test_proyecto.py` — pruebas

Prueba los movimientos y sus cierres, posiciones en túneles, sincronización,
colisiones entre las dos rutas y el formato del reporte.

```powershell
python -m unittest -v test_proyecto.py
```
