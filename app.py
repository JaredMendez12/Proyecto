"""
Interfaz web (Streamlit) para el proyecto. Es solo un panel de control:
cada boton ejecuta exactamente el mismo codigo que correrias a mano en
terminal (python main.py, mpiexec -n N python src\\paralelo.py, y las
funciones de src\\benchmark.py), asi que correr las cosas por terminal
o con la ventana Tkinter (gui.py) sigue funcionando igual que antes.

Se abre con:
    python -m streamlit run app.py
"""

import sys
import re
import subprocess
import time
from pathlib import Path

import streamlit as st
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "src"))
import benchmark  # noqa: E402

PYTHON = sys.executable

st.set_page_config(page_title="Proyecto Parcial 1 - MPI", layout="wide")

if "historial" not in st.session_state:
    st.session_state.historial = []  # cada item: {"etiqueta", "metricas"}
if "mostrar_logs" not in st.session_state:
    st.session_state.mostrar_logs = True


def parsear_metricas_main(texto):
    m = re.search(r"Muestra guardada:\s*(\d+)\s*filas", texto)
    return {"Filas guardadas": f"{int(m.group(1)):,}"} if m else {}


def parsear_metricas_secuencial(texto):
    metricas = {}
    m = re.search(r"Tiempo secuencial:\s*([\d.]+)", texto)
    if m:
        metricas["Tiempo"] = f"{float(m.group(1)):.4f} s"
    m = re.search(r"Juegos procesados:\s*(\d+)", texto)
    if m:
        metricas["Juegos procesados"] = m.group(1)
    return metricas


def parsear_metricas_paralelo(texto):
    metricas = {}
    for patron, clave, formato in [
        (r"Procesos:\s*(\d+)", "Procesos", "{}"),
        (r"Tiempo Total:\s*([\d.]+)", "Tiempo total", "{:.4f} s"),
        (r"Tiempo Sincronizacion:\s*([\d.]+)", "Sincronización", "{:.4f} s"),
        (r"Juegos:\s*(\d+)", "Juegos procesados", "{}"),
    ]:
        m = re.search(patron, texto)
        if m:
            valor = float(m.group(1)) if "." in formato else int(m.group(1))
            metricas[clave] = formato.format(valor)
    return metricas


def correr_y_mostrar_celda(comando, etiqueta, state_key, parser=None):
    """Estilo celda de Notebook: corre el comando, muestra logs en vivo y 
    guarda el resultado final en session_state para que no desaparezca."""
    mostrar_logs = st.session_state.mostrar_logs

    if state_key not in st.session_state:
        st.session_state[state_key] = None

    if mostrar_logs:
        st.code(f"$ {' '.join(comando)}", language="bash")

    btn = st.button(f"▶ Ejecutar: {etiqueta}", key=f"btn_{state_key}")
    
    placeholder = st.empty()
    metricas_ph = st.empty()

    if btn:
        if not mostrar_logs:
            placeholder.info(f"⏳ Ejecutando {etiqueta}...")

        lineas = []
        try:
            proc = subprocess.Popen(
                comando, cwd=str(BASE_DIR),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
        except FileNotFoundError as e:
            st.error(f"No se encontró el ejecutable ({e}). Si es 'mpiexec', instala MS-MPI.")
            return

        for linea in proc.stdout:
            lineas.append(linea)
            if mostrar_logs:
                placeholder.code("".join(lineas[-300:]), height=300)
        codigo = proc.wait()

        texto_completo = "".join(lineas)
        metricas = parser(texto_completo) if parser else {}
        
        st.session_state[state_key] = {
            "codigo": codigo,
            "texto": texto_completo,
            "metricas": metricas
        }

    # Renderizar el estado guardado para que no se borre
    estado = st.session_state[state_key]
    if estado:
        if not mostrar_logs:
            placeholder.empty()
        elif not btn:  # Si no lo acabamos de dibujar streameando
            placeholder.code(estado["texto"], height=300)

        if estado["codigo"] == 0:
            st.success(f"Terminado correctamente (código {estado['codigo']})")
            if estado["metricas"]:
                cols = metricas_ph.columns(len(estado["metricas"]))
                for col, (clave, valor) in zip(cols, estado["metricas"].items()):
                    col.metric(clave, valor)
        else:
            st.error(f"Terminó con error (código {estado['codigo']})")


def graficar_comparacion(metrica_key, titulo, ylabel, ylim=None):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for item in st.session_state.historial:
        m = item["metricas"]
        ns = m["n_procesos_lista"]
        if metrica_key == "tiempo_total":
            valores = [m["promedios"][n] for n in ns]
        elif metrica_key == "tiempo_sync":
            valores = [m["promedios_sync"][n] for n in ns]
        else:
            valores = m[metrica_key]
        ax.plot(ns, valores, "o-", label=item["etiqueta"])

    if metrica_key == "aceleraciones" and st.session_state.historial:
        ns_ideal = st.session_state.historial[-1]["metricas"]["n_procesos_lista"]
        ax.plot(ns_ideal, ns_ideal, ":", color="gray", label="Aceleración ideal")
    if metrica_key == "eficiencias":
        ax.axhline(1.0, color="gray", linestyle=":", label="Eficiencia ideal (100%)")

    ax.set_xlabel("Número de procesos")
    ax.set_ylabel(ylabel)
    ax.set_title(titulo)
    if ylim:
        ax.set_ylim(*ylim)
    ax.grid(True, alpha=0.3)
    ax.legend()
    return fig


def graficar_una_corrida(metricas, metrica_key, titulo, ylabel, ylim=None):
    """Grafica de UNA sola corrida (no superpuesta con otras), para
    mostrarla junto a su propia tabla en el desglose por corrida."""
    fig, ax = plt.subplots(figsize=(6, 4))
    ns = metricas["n_procesos_lista"]

    if metrica_key == "tiempo_total":
        ax.plot(ns, [metricas["promedios"][n] for n in ns], "o-", label="Tiempo total")
        ax.plot(ns, [metricas["promedios_sync"][n] for n in ns], "o-", color="crimson", label="Tiempo de sincronización")
    elif metrica_key == "aceleraciones":
        ax.plot(ns, metricas["aceleraciones"], "o-", label="Aceleración real")
        ax.plot(ns, ns, ":", color="gray", label="Aceleración ideal")
    elif metrica_key == "eficiencias":
        ax.plot(ns, metricas["eficiencias"], "o-", color="darkorange", label="Eficiencia")
        ax.axhline(1.0, color="gray", linestyle=":", label="Eficiencia ideal (100%)")

    ax.set_xlabel("Número de procesos")
    ax.set_ylabel(ylabel)
    ax.set_title(titulo)
    if ylim:
        ax.set_ylim(*ylim)
    ax.grid(True, alpha=0.3)
    ax.legend()
    return fig


def analizar_diferencias(historial):
    """Genera un texto de analisis a partir de los numeros reales de cada
    corrida (no es texto fijo): compara fraccion secuencial, mejor
    aceleracion lograda y variabilidad del tiempo de referencia (1 proceso)
    entre las distintas corridas guardadas en esta sesion."""
    fracciones = [(item["etiqueta"], item["metricas"]["fraccion_secuencial"]) for item in historial]
    valores_frac = [f for _, f in fracciones]
    promedio_frac = sum(valores_frac) / len(valores_frac)
    corrida_min = min(fracciones, key=lambda x: x[1])
    corrida_max = max(fracciones, key=lambda x: x[1])

    mejores = []
    for item in historial:
        m = item["metricas"]
        i_max = max(range(len(m["aceleraciones"])), key=lambda i: m["aceleraciones"][i])
        mejores.append((item["etiqueta"], m["n_procesos_lista"][i_max], m["aceleraciones"][i_max]))
    mejor_global = max(mejores, key=lambda x: x[2])

    lineas = []
    lineas.append(f"- Se compararon **{len(historial)}** corrida(s): {', '.join(e for e, _ in fracciones)}.")
    lineas.append(
        f"- La **fracción secuencial estimada (Ley de Amdahl)** promedió **{promedio_frac:.2%}** entre corridas, "
        f"con un mínimo de {corrida_min[1]:.2%} (en '{corrida_min[0]}') y un máximo de {corrida_max[1]:.2%} (en '{corrida_max[0]}'). "
        f"Como el código no cambia entre corridas, esa diferencia de {abs(corrida_max[1] - corrida_min[1]):.2%} "
        f"refleja principalmente ruido del sistema (otros procesos corriendo, calendarización del SO) y no una mejora real."
    )
    lineas.append(
        f"- La **mejor aceleración observada** en todas las corridas fue **{mejor_global[2]:.2f}x**, "
        f"lograda con {mejor_global[1]} proceso(s) en la corrida '{mejor_global[0]}'."
    )

    t1s = [(item["etiqueta"], item["metricas"]["promedios"].get(min(item["metricas"]["n_procesos_lista"])))
           for item in historial]
    valores_t1 = [v for _, v in t1s if v is not None]
    if len(valores_t1) >= 2:
        variacion = (max(valores_t1) - min(valores_t1)) / min(valores_t1)
        lineas.append(
            f"- El tiempo de referencia con el menor número de procesos varió entre "
            f"{min(valores_t1):.2f}s y {max(valores_t1):.2f}s según la corrida (una variación de {variacion:.1%}), "
            f"lo cual es normal al medir tiempos de ejecución reales en una máquina compartida con otros procesos."
        )

    return "\n".join(lineas)


st.title("Proyecto Parcial 1 — Cómputo Paralelo con MPI")
st.caption("Panel de control: genera el dataset, corre las versiones secuencial/paralela y el benchmark, todo con salida y gráficas en vivo.")

st.session_state.mostrar_logs = st.toggle(
    "🖥️ Mostrar logs detallados de la terminal",
    value=st.session_state.mostrar_logs,
    help="Actívalo para ver la salida cruda de cada comando (como en una terminal). Desactívalo para ver solo las tarjetas con los resultados clave.",
)

st.subheader("1. Preparar dataset")
with st.container(border=True):
    correr_y_mostrar_celda([PYTHON, "main.py"], "Generar muestra del dataset", "celda_1", parser=parsear_metricas_main)

st.subheader("2. Versión secuencial")
with st.container(border=True):
    correr_y_mostrar_celda([PYTHON, "src/secuencial.py"], "Versión secuencial", "celda_2", parser=parsear_metricas_secuencial)

st.subheader("3. Versión paralela manual")
with st.container(border=True):
    n_manual = st.number_input("Número de procesos para esta celda:", min_value=1, max_value=64, value=4, step=1)
    correr_y_mostrar_celda(["mpiexec", "-n", str(n_manual), PYTHON, "src/paralelo.py"], f"Versión paralela ({n_manual} procesos)", "celda_3", parser=parsear_metricas_paralelo)

st.divider()

st.subheader("4. Benchmark")

col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    procesos_txt = st.text_input("Lista de procesos a probar (separados por coma)", value="1,2,4,8")
with col2:
    corridas = st.number_input("Corridas por configuración", min_value=1, max_value=20, value=3, step=1)
with col3:
    etiqueta_sugerida = f"Corrida #{len(st.session_state.historial) + 1}"
    etiqueta_input = st.text_input(
        "Etiqueta de esta corrida",
        key="etiqueta_input",
        placeholder=etiqueta_sugerida,
        help="Ponle un nombre que te ayude a identificarla despues, ej. 'Con 1.5M filas' o 'Laptop en carga'.",
    )
    etiqueta = etiqueta_input.strip() or etiqueta_sugerida

col_run, col_clear = st.columns([1, 1])
ejecutar = col_run.button("▶ Ejecutar benchmark", type="primary", width="stretch")
limpiar = col_clear.button("🗑 Limpiar historial de corridas", width="stretch")

if limpiar:
    st.session_state.historial = []
    st.rerun()

if ejecutar:
    try:
        n_procesos_lista = sorted({int(x.strip()) for x in procesos_txt.split(",") if x.strip()})
        if not n_procesos_lista:
            raise ValueError("Lista vacía")
    except ValueError:
        st.error("Lista de procesos inválida. Usa números separados por coma, ej: 1,2,4,8")
        n_procesos_lista = None

    if n_procesos_lista:
        st.write(f"**{etiqueta}** — procesos: {n_procesos_lista}, corridas por configuración: {corridas}")

        total_repeticiones = len(n_procesos_lista) * corridas
        barra_progreso = st.progress(0, text=f"0/{total_repeticiones} repeticiones completadas")
        resumen_placeholder = st.empty()
        log_placeholder = st.empty() if st.session_state.mostrar_logs else None
        graf_tiempo_ph, graf_acel_ph, graf_efi_ph = st.empty(), st.empty(), st.empty()

        filas_acumuladas = []
        conteo_por_n = {}
        lineas_log = []

        def on_progreso(fila):
            filas_acumuladas.append(fila)
            n = fila["n_procesos"]
            conteo_por_n[n] = conteo_por_n.get(n, 0) + 1

            hechas = len(filas_acumuladas)
            barra_progreso.progress(hechas / total_repeticiones, text=f"{hechas}/{total_repeticiones} repeticiones completadas")

            if log_placeholder is not None:
                lineas_log.append(
                    f"[{fila['n_procesos']} proc, corrida {fila['corrida']}] "
                    f"Total={fila['tiempo_total']:.4f}s  Sync={fila['tiempo_sync']:.4f}s"
                )
                log_placeholder.code("\n".join(lineas_log[-300:]), height=350)

            resumen_lineas = []
            for n_check in n_procesos_lista:
                completadas_n = conteo_por_n.get(n_check, 0)
                if completadas_n == 0:
                    resumen_lineas.append(f"- ⏳ **{n_check} proceso(s)** — pendiente")
                elif completadas_n < corridas:
                    resumen_lineas.append(f"- 🔄 **{n_check} proceso(s)** — {completadas_n}/{corridas} repeticiones")
                else:
                    tiempos_n = [f["tiempo_total"] for f in filas_acumuladas if f["n_procesos"] == n_check]
                    resumen_lineas.append(
                        f"- ✅ **{n_check} proceso(s)** — {corridas}/{corridas} repeticiones — "
                        f"promedio {sum(tiempos_n) / len(tiempos_n):.4f} s"
                    )
            resumen_placeholder.markdown("\n".join(resumen_lineas))

            if conteo_por_n[n] == corridas:
                completados = sorted(k for k, v in conteo_por_n.items() if v == corridas)
                parciales = [f for f in filas_acumuladas if f["n_procesos"] in completados]
                metricas_parciales = benchmark.calcular_metricas(parciales, completados)

                historial_temporal = st.session_state.historial + [
                    {"etiqueta": f"{etiqueta} (en curso)", "metricas": metricas_parciales}
                ]
                _historial_real = st.session_state.historial
                st.session_state.historial = historial_temporal
                graf_tiempo_ph.pyplot(graficar_comparacion("tiempo_total", "Tiempo de ejecución vs procesos", "Segundos"))
                graf_acel_ph.pyplot(graficar_comparacion("aceleraciones", "Aceleración vs procesos", "Aceleración"))
                graf_efi_ph.pyplot(graficar_comparacion("eficiencias", "Eficiencia vs procesos", "Eficiencia", ylim=(0, 1.1)))
                st.session_state.historial = _historial_real

        try:
            filas = benchmark.correr_benchmark(
                n_procesos_lista=n_procesos_lista, corridas=corridas, on_progreso=on_progreso
            )
            metricas_final = benchmark.calcular_metricas(filas, n_procesos_lista)
            st.session_state.historial.append({"etiqueta": etiqueta, "metricas": metricas_final, "filas": filas})
            benchmark.graficar(metricas_final)
            st.success(f"Benchmark '{etiqueta}' completo. Fracción secuencial estimada (Amdahl): {metricas_final['fraccion_secuencial']:.4f}")
            st.session_state.etiqueta_input = ""
            st.rerun()
        except FileNotFoundError:
            st.error("No se encontró 'mpiexec'. Instala MS-MPI y reinicia esta app (cierra la terminal donde corre Streamlit y ábrela de nuevo).")

DESCRIPCIONES_GRAFICAS = {
    "tiempo_total": "Tiempo total promedio (segundos) y tiempo de sincronización promedio, para cada cantidad de procesos probada en esta corrida. Es el dato crudo, antes de calcular aceleración o eficiencia.",
    "aceleraciones": "Aceleración real (T₁/Tₙ) contra la aceleración ideal (línea punteada). Entre más cerca esté la curva de la línea ideal, mejor escala el programa al agregar procesos.",
    "eficiencias": "Aceleración dividida entre el número de procesos. Cerca del 100% significa buen aprovechamiento; la caída al aumentar procesos es esperada por el overhead de Scatter/Gather/Barrera y por la fracción secuencial (Ley de Amdahl).",
}

if st.session_state.historial:
    st.subheader(f"Resultados por corrida ({len(st.session_state.historial)} corrida(s) en esta sesión)")

    for idx, item in enumerate(st.session_state.historial, start=1):
        m = item["metricas"]
        filas_crudas = item.get("filas", [])
        st.markdown(f"### {item['etiqueta']}")
        st.caption(f"Corrida #{idx} de esta sesión")

        st.markdown("**Datos por configuración** (cada fila es una repetición individual, sin promediar):")
        if filas_crudas:
            col_tablas = st.columns(len(m["n_procesos_lista"]))
            for col, n in zip(col_tablas, m["n_procesos_lista"]):
                with col:
                    st.markdown(f"*{n} proceso(s)*")
                    tabla_n = [
                        {
                            "Repetición": f["corrida"],
                            "Tiempo (s)": round(f["tiempo_total"], 4),
                            "Sync (s)": round(f["tiempo_sync"], 4),
                        }
                        for f in filas_crudas if f["n_procesos"] == n
                    ]
                    st.dataframe(tabla_n, width="stretch", hide_index=True)
        else:
            st.caption("No hay datos crudos guardados para esta corrida (se generó antes de esta funcionalidad).")

        st.markdown("**Comparación / resumen** (promedio de las repeticiones de arriba, para comparar entre configuraciones):")
        tabla_corrida = []
        for i, n in enumerate(m["n_procesos_lista"]):
            tabla_corrida.append({
                "Procesos": n,
                "Tiempo promedio (s)": round(m["promedios"][n], 4),
                "Sync promedio (s)": round(m["promedios_sync"][n], 4),
                "Aceleración": round(m["aceleraciones"][i], 2),
                "Eficiencia": f"{m['eficiencias'][i]:.1%}",
            })
        st.dataframe(tabla_corrida, width="stretch", hide_index=True)
        st.caption(f"Fracción secuencial estimada (Ley de Amdahl) para esta corrida: {m['fraccion_secuencial']:.2%}")

        gcol1, gcol2, gcol3 = st.columns(3)
        especificaciones = [
            (gcol1, "tiempo_total", "Tiempo de ejecución", "Segundos", None),
            (gcol2, "aceleraciones", "Aceleración", "Aceleración", None),
            (gcol3, "eficiencias", "Eficiencia", "Eficiencia", (0, 1.1)),
        ]
        for columna, clave, titulo, ylabel, ylim in especificaciones:
            with columna:
                with st.container(border=True):
                    st.pyplot(graficar_una_corrida(m, clave, titulo, ylabel, ylim))
                    st.caption(DESCRIPCIONES_GRAFICAS[clave])

        st.divider()

    st.subheader("Análisis de diferencias entre corridas")

    st.markdown(analizar_diferencias(st.session_state.historial))

    st.markdown("**Comparación superpuesta** (todas las corridas en la misma gráfica, para verlas una junto a otra):")
    acol1, acol2, acol3 = st.columns(3)
    with acol1:
        with st.container(border=True):
            st.pyplot(graficar_comparacion("tiempo_total", "Tiempo de ejecución vs procesos", "Segundos"))
            st.caption(DESCRIPCIONES_GRAFICAS["tiempo_total"])
    with acol2:
        with st.container(border=True):
            st.pyplot(graficar_comparacion("aceleraciones", "Aceleración vs procesos", "Aceleración"))
            st.caption(DESCRIPCIONES_GRAFICAS["aceleraciones"])
    with acol3:
        with st.container(border=True):
            st.pyplot(graficar_comparacion("eficiencias", "Eficiencia vs procesos", "Eficiencia", ylim=(0, 1.1)))
            st.caption(DESCRIPCIONES_GRAFICAS["eficiencias"])
else:
    st.info("Todavía no has corrido ningún benchmark en esta sesión. Presiona '▶ Ejecutar benchmark' arriba.")
