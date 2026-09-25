"""
Version PARALELA (MPI, patron Maestro/Esclavo) del procesamiento del
dataset Steam Reviews. Mapa rapido de requisitos -> ubicacion en este
archivo (buscar por la etiqueta REQUISITO):

  - Patron Maestro/Esclavo   -> main(): bloque `if rank == 0` (maestro)
                                 vs codigo que corre en todos los rangos
  - Division por bloques     -> main(): np.array_split(...)
  - Scatter                  -> main(): comm.scatter(...)
  - Gather                   -> main(): comm.gather(...)
  - Cerraduras (Barreras)    -> main(): las dos llamadas a comm.Barrier()
  - Tiempo de sincronizacion -> main(): t_sync_start / t_sync_end alrededor
                                 de la barrera 2
"""

from mpi4py import MPI
from pathlib import Path
from collections import defaultdict
import pandas as pd
import numpy as np
import time

BASE_DIR = Path(__file__).resolve().parent.parent
RUTA_MUESTRA = BASE_DIR / "data" / "sample" / "muestra_grande.csv"
COLUMNAS_NECESARIAS = ["app_name", "review_score", "review_votes"]

def procesar_bloque(bloque):
    resultados = defaultdict(lambda: {"positivas": 0, "negativas": 0, "votos_utiles": 0})
    if bloque is None or bloque.empty:
        return dict(resultados)
    
    for fila in bloque.itertuples(index=False):
        juego = fila.app_name
        if pd.isna(juego):
            continue
        if fila.review_score == 1:
            resultados[juego]["positivas"] += 1
        else:
            resultados[juego]["negativas"] += 1
        resultados[juego]["votos_utiles"] += fila.review_votes
    
    return dict(resultados)

def combinar_resultados(lista_resultados):
    combinado = defaultdict(lambda: {"positivas": 0, "negativas": 0, "votos_utiles": 0})
    for parcial in lista_resultados:
        for juego, datos in parcial.items():
            combinado[juego]["positivas"] += datos["positivas"]
            combinado[juego]["negativas"] += datos["negativas"]
            combinado[juego]["votos_utiles"] += datos["votos_utiles"]
    return dict(combinado)

def main():
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()
    
    # REQUISITO: Cerradura/Barrera 1 - todos los procesos arrancan el cronometro juntos
    comm.Barrier()
    inicio = 0
    if rank == 0:
        inicio = time.perf_counter()
        print(f"[Maestro (M)] Iniciando procesamiento paralelo con {size} procesos.")
        print(f"[Maestro (M)] Leyendo dataset desde el disco duro...")

    # REQUISITO: Patron Maestro/Esclavo
    bloques = None
    if rank == 0:
        try:
            df = pd.read_csv(RUTA_MUESTRA, usecols=COLUMNAS_NECESARIAS)
            print(f"[Maestro (M)] ¡Leídas {len(df):,} filas! Cortando en {size} pedazos iguales (bloques)...")
        except FileNotFoundError:
            print(f"Error: No se encontró {RUTA_MUESTRA}")
            comm.Abort(1)

        # REQUISITO: Division por bloques
        indices = np.array_split(np.arange(len(df)), size)
        bloques = [df.iloc[idx] for idx in indices]
        print(f"[Maestro (M)] Ejecutando Scatter: enviando un bloque de trabajo a cada esclavo.")

    # REQUISITO: Scatter
    t_scatter_start = time.perf_counter()
    bloque_local = comm.scatter(bloques, root=0)
    t_scatter_end = time.perf_counter()
    
    filas_asignadas = len(bloque_local) if bloque_local is not None else 0
    simbolo = "(M)" if rank == 0 else "(E)"
    print(f"[Proceso {rank} {simbolo}] Recibí mi bloque de {filas_asignadas:,} filas. Trabajando...")

    # ESCLAVOS: cada proceso procesa su bloque
    t_trabajo_start = time.perf_counter()
    resultado_local = procesar_bloque(bloque_local)
    t_trabajo_end = time.perf_counter()
    
    tiempo_mi_trabajo = t_trabajo_end - t_trabajo_start
    print(f"[Proceso {rank} {simbolo}] Terminé mi bloque en {tiempo_mi_trabajo:.2f}s. Esperando en la barrera a que los demás acaben...")

    # REQUISITO: Cerradura/Barrera 2 (Tiempo de sincronización)
    t_sync_start = time.perf_counter()
    comm.Barrier()
    t_sync_end = time.perf_counter()
    tiempo_sync = t_sync_end - t_sync_start

    print(f"[Proceso {rank} {simbolo}] La barrera se levantó (esperé {tiempo_sync:.4f}s). Enviando mis resultados al Maestro (Gather)...")

    # REQUISITO: Gather
    resultados_globales = comm.gather(resultado_local, root=0)
    tiempos_sync_globales = comm.gather(tiempo_sync, root=0)

    # MAESTRO: Combina resultados
    if rank == 0:
        print(f"[Maestro (M)] Recibí todas las libretas parciales. Fusionando datos finales...")
        resultado_final = combinar_resultados(resultados_globales)
        fin = time.perf_counter()
        
        tiempo_total = fin - inicio
        tiempo_sync_maximo = max(tiempos_sync_globales)  # El proceso que esperó más
        
        print(f"[Maestro (M)] ¡Fusión completa!\n")
        print(f"--- RESULTADOS MPI ---")
        print(f"Procesos: {size}")
        print(f"Tiempo Total: {tiempo_total:.4f}")
        print(f"Tiempo Sincronizacion: {tiempo_sync_maximo:.4f}")
        print(f"Juegos: {len(resultado_final)}")

if __name__ == '__main__':
    main()