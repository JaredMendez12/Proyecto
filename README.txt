PROYECTO PARCIAL 1 - Computo Paralelo con Ley de Amdahl y MPI
===================================================================

Descripcion
-----------
Este proyecto procesa un dataset de "Steam Reviews": por cada juego
(app_name) cuenta cuantas resenas son positivas, cuantas negativas, y
suma el total de votos utiles (review_votes). Ese calculo se hace de
dos formas y se compara su rendimiento:
  - SECUENCIAL: un solo proceso recorre todo el dataset.
  - PARALELA: el dataset se reparte en bloques entre N procesos usando
    MPI con patron Maestro/Esclavo (Scatter/Gather/Barrera).

Luego se corren ambas versiones con distintas cantidades de procesos
(1, 2, 4 y 8) para calcular aceleracion, eficiencia y la fraccion
secuencial segun la Ley de Amdahl.


1. REQUISITOS (que instalar antes de empezar)
===================================================================
- Sistema operativo: Windows 10/11 (el proyecto usa mpiexec y
  os.startfile, especificos de Windows).
- Python 3.10 o superior (incluye pip).
- Microsoft MPI (MS-MPI), runtime v10.1.1 o superior. Es obligatorio
  para que mpi4py y el comando "mpiexec" funcionen en Windows.
  Descarga: https://github.com/microsoft/Microsoft-MPI/releases
  (o el instalador oficial: https://www.microsoft.com/en-us/download/details.aspx?id=105289)
  Instala el paquete msmpisetup.exe (el runtime). El SDK (msmpisdk.msi)
  no es necesario si mpi4py se instala via wheel precompilado.
- Librerias de Python:
    pandas       (fijar version 2.2.3 si Windows Smart App Control
                   bloquea la DLL de versiones mas nuevas por falta
                   de reputacion)
    numpy
    matplotlib
    mpi4py
    streamlit    (solo si se usa la interfaz web app.py)
    sv_ttk       (solo si se usa la interfaz de escritorio gui.py)
  (tkinter viene incluido con la instalacion estandar de Python en
  Windows, no requiere instalacion aparte).
- Dataset "Steam Reviews": NO esta incluido en este repositorio (pesa
  varios GB, esta excluido en .gitignore). Descargarlo desde:
    https://www.kaggle.com/datasets/andrewmvd/steam-reviews


2. INSTALACION
===================================================================
1. (Opcional pero recomendado) Crea y activa un entorno virtual:
     python -m venv venv
     venv\Scripts\activate

2. Instala las dependencias de Python:
     pip install pandas numpy matplotlib mpi4py streamlit sv_ttk

3. Instala Microsoft MPI (MS-MPI) usando el instalador oficial (ver
   enlace en la seccion de Requisitos). Reinicia la terminal despues
   de instalarlo para que el comando "mpiexec" quede disponible en el
   PATH.

4. Verifica que mpiexec este disponible:
     mpiexec -help

5. Descarga el dataset desde https://www.kaggle.com/datasets/andrewmvd/steam-reviews
   y coloca el CSV resultante en:
     data/raw/dataset.csv
   (crea las carpetas data/raw si no existen).


3. USO - COMO EJECUTAR EL PROYECTO
===================================================================
Paso previo (obligatorio, una sola vez): generar la muestra del
dataset a partir del CSV original.
     python main.py

Esto lee las primeras 1,500,000 filas de data/raw/dataset.csv y guarda
la muestra en data/sample/muestra_grande.csv, que es lo que usan
secuencial.py y paralelo.py.

Luego elige UNA de estas 3 formas de operar el proyecto (las 3
ejecutan exactamente el mismo codigo por debajo):

--- FORMA 1: Terminal (linea de comandos) ---
   python src\secuencial.py                    -> version secuencial (linea base, T1)
   mpiexec -n 4 python src\paralelo.py          -> version paralela manual (ejemplo con 4 procesos)
   python src\benchmark.py                     -> benchmark completo: corre 1,2,4,8 procesos
                                                   x 3 repeticiones, calcula metricas y
                                                   genera las graficas

--- FORMA 2: Interfaz de escritorio (Tkinter, gui.py) ---
     python gui.py
   Ventana con botones para generar la muestra, correr secuencial,
   correr paralelo (con N procesos elegido en un spinner) y correr el
   benchmark completo; muestra la salida en vivo en una consola
   integrada y permite ver las graficas y la tabla de resultados.

--- FORMA 3: Interfaz web (Streamlit, app.py) ---
     python -m streamlit run app.py
   Se abre un panel en el navegador (http://localhost:8501) con los
   mismos pasos que la version de escritorio: salida en vivo, sección
   de benchmark configurable (lista de procesos y repeticiones
   editables), graficas que se dibujan conforme terminan las
   configuraciones, tablas de datos crudos y de resumen, y un analisis
   automatico comparando distintas corridas del benchmark dentro de la
   misma sesion.

Resultados: los tiempos crudos quedan en resultados\tiempos.csv y las
graficas (tiempo de ejecucion, aceleracion, eficiencia) se guardan en
resultados\graficas\. Se regeneran cada vez que se corre el benchmark
completo, por cualquiera de las 3 formas.


4. QUE SE IMPLEMENTO Y DONDE (mapeo a los requisitos del trabajo)
===================================================================
Requisito                  Donde esta implementado
-------------------------  --------------------------------------------
Division por bloques       src\paralelo.py -> np.array_split(np.arange(
                            len(df)), size) reparte el dataset en tantos
                            bloques como procesos haya.

Patron Maestro/Esclavo     src\paralelo.py -> funcion main(): el bloque
                            "if rank == 0" es el maestro (unico que lee
                            el CSV completo); el resto de rangos son los
                            esclavos.

Scatter                    src\paralelo.py -> comm.scatter(bloques,
                            root=0) reparte un bloque distinto a cada
                            proceso.

Gather                     src\paralelo.py -> comm.gather(resultado_
                            local, root=0) junta los resultados
                            parciales de todos los procesos en el
                            maestro.

Cerraduras (Barreras)      src\paralelo.py -> comm.Barrier() se usa dos
                            veces: una antes de arrancar el cronometro
                            (para que todos los procesos empiecen
                            juntos) y otra despues de procesar (para
                            medir cuanto espera cada proceso a los
                            demas = tiempo de sincronizacion).

Tiempo de sincronizacion   src\paralelo.py -> se mide como t_sync_end -
                            t_sync_start alrededor de la segunda
                            barrera.

3 corridas con 1,2,4,8     src\benchmark.py -> correr_benchmark():
procesos                   CORRIDAS=3 son las repeticiones,
                            NUM_PROCESOS=[1,2,4,8] es la lista de
                            configuraciones. Cada combinacion se guarda
                            en resultados\tiempos.csv.

Aceleracion (Speedup)      src\benchmark.py -> calcular_metricas():
                            S(n) = T1 / Tn (T1 = tiempo secuencial,
                            Tn = tiempo con n procesos).

Eficiencia                 src\benchmark.py -> calcular_metricas():
                            E(n) = S(n) / n.

Ley de Amdahl / fraccion   src\benchmark.py -> calcular_metricas():
secuencial                 se despeja la fraccion paralelizable p de
                            S(n) = 1 / ((1-p) + p/n)  =>
                            p = (1 - 1/S) / (1 - 1/n), promediada sobre
                            las configuraciones con n>1. La fraccion
                            secuencial reportada es (1 - p).

Graficas de resultados     src\benchmark.py -> graficar(): genera
                            tiempo_ejecucion.png, aceleracion.png y
                            eficiencia.png en resultados\graficas\.

Nota sobre "hilos" vs "procesos": MPI crea PROCESOS del sistema
operativo (cada uno con su propia memoria, se comunican por mensajes),
no hilos (que comparten memoria dentro de un mismo proceso). El
enunciado dice "1, 2, 4 y 8 hilos" de forma coloquial; en este proyecto
esos numeros son, tecnicamente, procesos MPI.

El unico hilo real de Python en todo el proyecto esta en gui.py
(threading.Thread), y es solo para que la ventana no se congele
mientras espera a un subproceso; no tiene relacion con el
procesamiento paralelo del dataset ni con la Ley de Amdahl.


5. ESTRUCTURA DE ARCHIVOS
===================================================================
  main.py                    -> Genera la muestra del dataset (paso previo)
  gui.py                      -> Interfaz de escritorio (Tkinter)
  app.py                      -> Interfaz web (Streamlit)
  amdahl.py                   -> Script aparte, exploratorio (usa
                                  multiprocessing, no MPI; no forma
                                  parte del pipeline principal)

  src\
    secuencial.py              -> Version secuencial (referencia, T1)
    paralelo.py                -> Version paralela con MPI (Maestro/Esclavo)
    benchmark.py               -> Orquesta las corridas, calcula metricas
                                   y genera las graficas

  data\
    raw\dataset.csv            -> Dataset original (Steam Reviews), NO
                                   se sube a git, colocar manualmente
    sample\muestra_grande.csv  -> Muestra generada por main.py

  resultados\
    tiempos.csv                 -> Tiempos crudos de la ultima corrida
    graficas\
      tiempo_ejecucion.png       -> Tiempo total y de sincronizacion vs N
      aceleracion.png            -> Aceleracion real vs ideal
      eficiencia.png             -> Eficiencia vs N


6. NOTAS Y LIMITACIONES CONOCIDAS
===================================================================
- Los tiempos medidos tienen ruido notable (varian entre corridas)
  porque dependen de otros procesos corriendo en la misma maquina y
  porque el trabajo por fila es relativamente poco comparado con el
  overhead de arrancar procesos MPI. Por eso se promedian 3
  repeticiones por configuracion, y la fraccion secuencial estimada
  puede variar un poco entre corridas del benchmark (es normal).
- El requisito "trabajar por bloques o hilos" se cumple con bloques
  (division del DataFrame con np.array_split), una de las dos opciones
  validas segun el enunciado ("o").
- amdahl.py es un script exploratorio aparte, hecho con
  multiprocessing.Pool (no con MPI); no debe confundirse con
  src\paralelo.py, que es la implementacion real que cumple los
  requisitos del entregable.
