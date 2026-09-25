PROYECTO PARCIAL 1 - Computo Paralelo con Ley de Amdahl y MPI
===================================================================

Descripcion
-----------
Este proyecto procesa un dataset de "Steam Reviews" comparando una ejecución en 
un solo hilo contra una implementacion paralela (Maestro-Esclavo) usando MPI.
Cumple con todos los requisitos de: 
- División por bloques
- Patrón Maestro/Esclavo
- Scatter y Gather
- Cerraduras (Barreras)
- Medición de aceleración, eficiencia, fracción secuencial y tiempo de sincronización.

Requisitos
----------
- Python 3.10+
- Microsoft MPI (MS-MPI) instalado en el sistema (Obligatorio para mpi4py en Windows).
- pip

Instalacion
-----------
1. Activa tu entorno virtual (si usas uno).
2. Instala las dependencias:
   pip install pandas numpy matplotlib mpi4py

Preparacion del dataset
------------------------
El dataset original NO esta incluido en este repositorio (es muy pesado).
1. Descargalo desde: https://www.kaggle.com/datasets/andrewmvd/steam-reviews
2. Coloca el CSV descargado en: data/raw/dataset.csv
3. Ejecuta la preparación inicial para crear la muestra de la base de datos:
   python main.py

Como compilar y ejecutar
------------------------
El proyecto no requiere compilación previa (es Python), pero sí requiere ejecución a través del binario de MPI (`mpiexec`).

OPCIÓN 1: Ejecución manual (Para probar la paralelizacion paso a paso)
Para correr con 4 hilos (esclavos/maestro):
   mpiexec -n 4 python src\paralelo.py

OPCIÓN 2: Ejecución del Reporte Técnico de Rendimiento (Benchmark) - RECOMENDADO
Este script automatiza las 3 corridas solicitadas para 1, 2, 4 y 8 hilos, calcula
la Ley de Amdahl, la fracción secuencial, el tiempo de sincronización y crea las GRÁFICAS.
   python src\benchmark.py

Una vez ejecutado, los resultados quedarán en la consola, y las gráficas 
de aceleración y eficiencia se guardarán automáticamente en la carpeta `resultados/graficas/`.