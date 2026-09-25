"""
Orquestador de benchmarking: corre paralelo.py via mpiexec con distinto
numero de procesos y calcula las metricas de rendimiento. Mapa rapido de
requisitos -> ubicacion en este archivo (buscar por la etiqueta REQUISITO):

  - Ejecucion con mpiexec (1,2,4,8 hilos) -> ejecutar_comando_mpi()
  - Tiempo de sincronizacion (promedio)   -> calcular_metricas(): promedios_sync
  - Aceleracion (speedup)                 -> calcular_metricas(): aceleraciones
  - Eficiencia                            -> calcular_metricas(): eficiencias
  - Ley de Amdahl / fraccion secuencial   -> calcular_metricas(): estimaciones_p
  - Graficas de tiempo/aceleracion/eficiencia -> graficar()

Este modulo funciona igual por terminal (`python src\\benchmark.py`, usa
NUM_PROCESOS=[1,2,4,8] y CORRIDAS=3 por defecto) y tambien se puede
importar (por ejemplo desde app.py) pasando otra lista de procesos,
otro numero de corridas, y un callback `on_progreso` para ir mostrando
resultados en vivo en una interfaz.
"""

import subprocess
import sys
import time
import csv
from pathlib import Path
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parent.parent
RUTA_TIEMPOS = BASE_DIR / "resultados" / "tiempos.csv"
RUTA_GRAFICAS = BASE_DIR / "resultados" / "graficas"

NUM_PROCESOS = [1, 2, 4, 8]
CORRIDAS = 3

def ejecutar_comando_mpi(n_procesos):
    """REQUISITO: Ejecucion con N procesos via mpiexec.
    Lanza paralelo.py como subproceso MPI y extrae el tiempo total y de sincronización
    que ese script imprime por consola (ver "Tiempo Total:" / "Tiempo Sincronizacion:" en paralelo.py)."""
    comando = ["mpiexec", "-n", str(n_procesos), sys.executable, str(BASE_DIR / "src" / "paralelo.py")]

    try:
        resultado = subprocess.run(comando, capture_output=True, text=True)
    except FileNotFoundError as e:
        print("---------------------------------------------------------")
        print("ERROR CRÍTICO: No se encontró 'mpiexec' en tu sistema.")
        print("Asegúrate de haber instalado MS-MPI y REINICIA tu terminal.")
        print("---------------------------------------------------------")
        raise

    tiempo_total = 0.0
    tiempo_sync = 0.0

    if resultado.returncode != 0:
        print(f"Error ejecutando MPI con {n_procesos} procesos:")
        print(resultado.stderr)
        return 0.0, 0.0

    for linea in resultado.stdout.split('\n'):
        if "Tiempo Total:" in linea:
            tiempo_total = float(linea.split(":")[1].strip())
        elif "Tiempo Sincronizacion:" in linea:
            tiempo_sync = float(linea.split(":")[1].strip())

    return tiempo_total, tiempo_sync

def correr_benchmark(n_procesos_lista=None, corridas=None, on_progreso=None, guardar_csv=True):
    """Corre `corridas` repeticiones de paralelo.py para cada N en n_procesos_lista.
    on_progreso(fila) se llama despues de cada corrida individual, para que quien
    llame (ej. la interfaz web) pueda mostrar avance en vivo sin esperar a que
    termine todo el benchmark."""
    n_procesos_lista = n_procesos_lista or NUM_PROCESOS
    corridas = corridas or CORRIDAS

    RUTA_GRAFICAS.mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "resultados").mkdir(exist_ok=True)

    filas = []

    for n in n_procesos_lista:
        print(f"Corriendo MPI con {n} proceso(s)...")
        for corrida in range(1, corridas + 1):
            t_total, t_sync = ejecutar_comando_mpi(n)
            fila = {
                "n_procesos": n,
                "corrida": corrida,
                "tiempo_total": t_total,
                "tiempo_sync": t_sync
            }
            filas.append(fila)
            print(f"  Corrida {corrida}: Total={t_total:.4f}s, Sync={t_sync:.4f}s")
            if on_progreso:
                on_progreso(fila)

    if guardar_csv:
        with open(RUTA_TIEMPOS, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["n_procesos", "corrida", "tiempo_total", "tiempo_sync"])
            writer.writeheader()
            writer.writerows(filas)

    return filas

def calcular_metricas(filas, n_procesos_lista=None):
    """Calcula promedios, aceleracion, eficiencia y la fraccion secuencial de
    Amdahl a partir de las filas de correr_benchmark(). No imprime ni grafica,
    solo devuelve los numeros para que el llamador decida como mostrarlos."""
    n_procesos_lista = n_procesos_lista or sorted({f["n_procesos"] for f in filas})

    promedios = {}
    promedios_sync = {}
    for n in n_procesos_lista:
        tiempos_totales = [f["tiempo_total"] for f in filas if f["n_procesos"] == n]
        tiempos_syncs = [f["tiempo_sync"] for f in filas if f["n_procesos"] == n]

        if not tiempos_totales: tiempos_totales = [1.0]
        if not tiempos_syncs: tiempos_syncs = [0.0]

        promedios[n] = sum(tiempos_totales) / len(tiempos_totales)
        # REQUISITO: Tiempo de sincronizacion - promedio (sobre las corridas)
        # del tiempo que los procesos esperan en la barrera 2 de paralelo.py.
        promedios_sync[n] = sum(tiempos_syncs) / len(tiempos_syncs)

    t1 = promedios[n_procesos_lista[0]]  # tiempo de referencia (normalmente N=1)

    # REQUISITO: Aceleracion (speedup) = T1 / Tn, para cada N en n_procesos_lista
    aceleraciones = [t1 / promedios[n] for n in n_procesos_lista]
    # REQUISITO: Eficiencia = Aceleracion / N (que tan bien se aprovecha cada proceso)
    eficiencias = [a / n for a, n in zip(aceleraciones, n_procesos_lista)]

    # REQUISITO: Ley de Amdahl - se despeja la fraccion paralelizable p de
    # S(n) = 1 / ((1-p) + p/n)  =>  p = (1 - 1/S) / (1 - 1/n)
    # y se promedia sobre todas las corridas con n>1 para obtener una
    # estimacion de la fraccion secuencial (1 - p) del programa.
    estimaciones_p = []
    for n, s in zip(n_procesos_lista, aceleraciones):
        if n == 1 or s == 1: continue
        p = (1 - (1 / s)) / (1 - (1 / n))
        estimaciones_p.append(p)

    p_estimado = sum(estimaciones_p) / len(estimaciones_p) if estimaciones_p else 0
    fraccion_secuencial = 1 - p_estimado

    return {
        "n_procesos_lista": n_procesos_lista,
        "promedios": promedios,
        "promedios_sync": promedios_sync,
        "aceleraciones": aceleraciones,
        "eficiencias": eficiencias,
        "p_estimado": p_estimado,
        "fraccion_secuencial": fraccion_secuencial,
    }

def imprimir_reporte(metricas):
    ns = metricas["n_procesos_lista"]
    print("\n========= REPORTE TÉCNICO DE RENDIMIENTO =========")
    for n, a, e in zip(ns, metricas["aceleraciones"], metricas["eficiencias"]):
        print(f"Hilos: {n} | Tiempo: {metricas['promedios'][n]:.4f}s | Sync: {metricas['promedios_sync'][n]:.4f}s | Aceleración: {a:.2f}x | Eficiencia: {e:.2%}")

    print("\n--- LEY DE AMDAHL ---")
    print(f"Fracción paralelizable (p): {metricas['p_estimado']:.4f}")
    print(f"Fracción secuencial (1 - p): {metricas['fraccion_secuencial']:.4f}")
    print("==================================================")

def analizar_resultados(filas, n_procesos_lista=None):
    """Conserva el comportamiento original: calcula, imprime y grafica de un tiro."""
    metricas = calcular_metricas(filas, n_procesos_lista)
    imprimir_reporte(metricas)
    graficar(metricas)
    return metricas

def graficar(metricas):
    ns = metricas["n_procesos_lista"]
    promedios = metricas["promedios"]
    promedios_sync = metricas["promedios_sync"]

    # REQUISITO: Graficar los tiempos de ejecución (valores crudos en
    # segundos, no derivados como aceleracion/eficiencia) vs numero de
    # procesos, para ver cuanto tarda cada parte (total y sincronizacion).
    plt.figure(figsize=(8, 5))
    plt.plot(ns, [promedios[n] for n in ns], "o-", label="Tiempo Total (promedio)")
    plt.plot(ns, [promedios_sync[n] for n in ns], "o-", color="crimson", label="Tiempo de Sincronizacion (promedio)")
    plt.xlabel("Numero de Hilos/Procesos")
    plt.ylabel("Tiempo (segundos)")
    plt.title("Tiempo de Ejecucion vs Numero de Hilos")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(RUTA_GRAFICAS / "tiempo_ejecucion.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Grafica de Aceleración
    plt.figure(figsize=(8, 5))
    plt.plot(ns, metricas["aceleraciones"], "o-", label="Aceleracion Real")
    plt.plot(ns, ns, ":", color="gray", label="Aceleracion Ideal")
    plt.xlabel("Numero de Hilos/Procesos")
    plt.ylabel("Aceleracion")
    plt.title("Aceleracion vs Numero de Hilos")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(RUTA_GRAFICAS / "aceleracion.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Grafica de Eficiencia
    plt.figure(figsize=(8, 5))
    plt.plot(ns, metricas["eficiencias"], "o-", color="darkorange")
    plt.axhline(1.0, color="gray", linestyle=":", label="Eficiencia Ideal (100%)")
    plt.xlabel("Numero de Hilos/Procesos")
    plt.ylabel("Eficiencia")
    plt.title("Eficiencia vs Numero de Hilos")
    plt.ylim(0, 1.1)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(RUTA_GRAFICAS / "eficiencia.png", dpi=150, bbox_inches="tight")
    plt.close()

    print(f"Graficas generadas en: {RUTA_GRAFICAS}")

if __name__ == "__main__":
    print("Iniciando pruebas de rendimiento automatizadas con MPI...")
    filas = correr_benchmark()
    analizar_resultados(filas)
