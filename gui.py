import sys
import subprocess
import threading
import queue
import os
import csv
from pathlib import Path
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

import sv_ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

BASE_DIR = Path(__file__).resolve().parent
RESULTADOS_DIR = BASE_DIR / "resultados"
GRAFICAS_DIR = RESULTADOS_DIR / "graficas"
TIEMPOS_CSV = RESULTADOS_DIR / "tiempos.csv"
PYTHON = sys.executable

# Asegurar que src esté en el sys.path para poder usar las funciones de métricas de benchmark
sys.path.insert(0, str(BASE_DIR / "src"))
try:
    import benchmark
except ImportError:
    benchmark = None


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Proyecto Parcial 1 - Cómputo Paralelo MPI (Pro Edition)")
        self.root.geometry("1050x700")
        
        # 1. APLICAR TEMA NATIVO Y MODERNO DE WINDOWS 11 (MODO OSCURO)
        sv_ttk.set_theme("dark")

        self.cola_salida = queue.Queue()
        self.proceso_corriendo = False
        self.canvas_widget = None

        self._construir_ui()
        self.root.after(100, self._drenar_cola)

    def _construir_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # ---- PESTAÑA 1: TERMINAL Y CONTROL ----
        self.tab_control = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_control, text=" 💻 Panel y Terminal ")
        self._construir_tab_control()

        # ---- PESTAÑA 2: VISOR DE GRÁFICAS INTERACTIVO ----
        self.tab_graficas = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_graficas, text=" 📈 Gráficas Interactivas ")
        self._construir_tab_graficas()

        # ---- PESTAÑA 3: TABLA DE DATOS (EXCEL) ----
        self.tab_datos = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_datos, text=" 📋 Tabla de Resultados ")
        self._construir_tab_datos()

        # ---- BARRA DE ESTADO Y PROGRESO ----
        frame_status = ttk.Frame(self.root)
        frame_status.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=5)
        
        self.progreso = ttk.Progressbar(frame_status, mode='indeterminate')
        self.progreso.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        self.estado_var = tk.StringVar(value="Listo.")
        ttk.Label(frame_status, textvariable=self.estado_var, font=("Consolas", 10)).pack(side=tk.RIGHT)

    def _construir_tab_control(self):
        marco_izq = ttk.Frame(self.tab_control, padding=10)
        marco_izq.pack(side=tk.LEFT, fill=tk.Y)
        
        marco_der = ttk.Frame(self.tab_control, padding=10)
        marco_der.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        ttk.Label(marco_izq, text="Panel de Control", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 15))

        self.botones = []

        b1 = ttk.Button(marco_izq, text="1. Generar muestra (main.py)", command=self.correr_generar_muestra)
        b1.pack(fill=tk.X, pady=5)
        self.botones.append(b1)

        b2 = ttk.Button(marco_izq, text="2. Correr Secuencial", command=self.correr_secuencial)
        b2.pack(fill=tk.X, pady=5)
        self.botones.append(b2)

        marco_paralelo = ttk.LabelFrame(marco_izq, text="3. Correr Paralelo (Manual)")
        marco_paralelo.pack(fill=tk.X, pady=10, ipady=5, ipadx=5)
        ttk.Label(marco_paralelo, text="Procesos:").pack(side=tk.LEFT, padx=5)
        self.n_procesos = tk.IntVar(value=4)
        ttk.Spinbox(marco_paralelo, from_=1, to=32, textvariable=self.n_procesos, width=5).pack(side=tk.LEFT)
        b3 = ttk.Button(marco_paralelo, text="Ejecutar", command=self.correr_paralelo)
        b3.pack(side=tk.RIGHT, padx=5)
        self.botones.append(b3)

        marco_bench = ttk.LabelFrame(marco_izq, text="4. Benchmark Completo")
        marco_bench.pack(fill=tk.X, pady=10, ipady=5, ipadx=5)
        ttk.Label(marco_bench, text="Ejecuta y calcula Aceleración/Eficiencia\n(1, 2, 4 y 8 procesos).", justify=tk.LEFT).pack(anchor="w", padx=5, pady=5)
        # Usar el estilo Accent.TButton de sv_ttk para resaltar este boton
        b4 = ttk.Button(marco_bench, text="Ejecutar Benchmark", style="Accent.TButton", command=self.correr_benchmark)
        b4.pack(fill=tk.X, padx=5, pady=5)
        self.botones.append(b4)

        b5 = ttk.Button(marco_izq, text="📁 Abrir Carpeta Resultados", command=self.abrir_resultados)
        b5.pack(fill=tk.X, pady=20)
        self.botones.append(b5)

        ttk.Label(marco_der, text="Terminal en vivo", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 5))
        self.texto_salida = scrolledtext.ScrolledText(marco_der, bg="#1e1e1e", fg="#4af626", font=("Consolas", 10), borderwidth=0)
        self.texto_salida.pack(fill=tk.BOTH, expand=True)
        self.texto_salida.configure(state="disabled")

    def _construir_tab_graficas(self):
        top_frame = ttk.Frame(self.tab_graficas, padding=10)
        top_frame.pack(side=tk.TOP, fill=tk.X)
        
        ttk.Button(top_frame, text="🔄 Cargar / Refrescar Gráficas", command=self.cargar_graficas).pack(side=tk.LEFT)
        ttk.Label(top_frame, text=" (Interactúa con las gráficas, haz zoom, y usa el disquete para guardarlas)").pack(side=tk.LEFT, padx=10)

        # Contenedor para incrustar matplotlib
        self.frame_canvas = ttk.Frame(self.tab_graficas)
        self.frame_canvas.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.cargar_graficas()

    def _construir_tab_datos(self):
        top_frame = ttk.Frame(self.tab_datos, padding=10)
        top_frame.pack(side=tk.TOP, fill=tk.X)
        
        ttk.Button(top_frame, text="🔄 Cargar Tabla", command=self.cargar_datos).pack(side=tk.LEFT)
        ttk.Label(top_frame, text=" Datos extraídos de tiempos.csv").pack(side=tk.LEFT, padx=10)
        
        # 3. TABLA DE RESULTADOS ESTILO EXCEL (Treeview)
        columnas = ("Procesos", "Corrida", "Tiempo Total (s)", "Tiempo Sincronización (s)")
        self.tree = ttk.Treeview(self.tab_datos, columns=columnas, show="headings", height=15)
        
        for col in columnas:
            self.tree.heading(col, text=col)
            self.tree.column(col, anchor="center")
            
        scrollbar = ttk.Scrollbar(self.tab_datos, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)
        
        self.cargar_datos()

    def cargar_graficas(self):
        if not TIEMPOS_CSV.exists() or benchmark is None:
            return

        if self.canvas_widget:
            self.canvas_widget.destroy()
            for widget in self.frame_canvas.winfo_children():
                widget.destroy()

        try:
            # Re-procesar datos y crear figura interactiva
            filas = []
            with open(TIEMPOS_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    filas.append({
                        "n_procesos": int(r["n_procesos"]),
                        "corrida": int(r["corrida"]),
                        "tiempo_total": float(r["tiempo_total"]),
                        "tiempo_sync": float(r["tiempo_sync"])
                    })
            
            n_procesos_lista = sorted(list(set(f["n_procesos"] for f in filas)))
            metricas = benchmark.calcular_metricas(filas, n_procesos_lista)

            # Estilo oscuro para matplotlib a juego con sv_ttk
            plt.style.use('dark_background')
            fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(12, 4))
            
            ns = metricas["n_procesos_lista"]
            
            ax1.plot(ns, [metricas["promedios"][n] for n in ns], "o-", label="Total", color="#00ffcc")
            ax1.plot(ns, [metricas["promedios_sync"][n] for n in ns], "o-", color="#ff4d4d", label="Sync")
            ax1.set_title("Tiempo de Ejecución")
            ax1.set_xlabel("Procesos")
            ax1.set_ylabel("Segundos")
            ax1.grid(True, alpha=0.2)
            ax1.legend()

            ax2.plot(ns, metricas["aceleraciones"], "o-", label="Real", color="#00ffcc")
            ax2.plot(ns, ns, ":", color="gray", label="Ideal")
            ax2.set_title("Aceleración (Speedup)")
            ax2.set_xlabel("Procesos")
            ax2.grid(True, alpha=0.2)
            ax2.legend()

            ax3.plot(ns, metricas["eficiencias"], "o-", color="#ffcc00", label="Eficiencia")
            ax3.axhline(1.0, color="gray", linestyle=":", label="Ideal")
            ax3.set_title("Eficiencia")
            ax3.set_xlabel("Procesos")
            ax3.set_ylim(0, 1.1)
            ax3.grid(True, alpha=0.2)
            ax3.legend()

            fig.tight_layout()

            # 2. INCRUSTAR MATPLOTLIB INTERACTIVO
            canvas = FigureCanvasTkAgg(fig, master=self.frame_canvas)
            canvas.draw()
            self.canvas_widget = canvas.get_tk_widget()
            self.canvas_widget.pack(fill=tk.BOTH, expand=True)
            
            # Toolbar interactiva de matplotlib
            toolbar = NavigationToolbar2Tk(canvas, self.frame_canvas)
            toolbar.update()
            toolbar.pack(side=tk.BOTTOM, fill=tk.X)

        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron dibujar las gráficas: {e}")

    def cargar_datos(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        if not TIEMPOS_CSV.exists():
            return
            
        try:
            with open(TIEMPOS_CSV, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader) 
                for row in reader:
                    formateado = []
                    for val in row:
                        try:
                            formateado.append(f"{float(val):.4f}" if "." in val else val)
                        except:
                            formateado.append(val)
                    self.tree.insert("", tk.END, values=formateado)
        except Exception:
            pass

    def _escribir(self, linea):
        self.cola_salida.put(("texto", linea))

    def _pedir_estado_botones(self, habilitados):
        self.cola_salida.put(("botones", habilitados))

    def _pedir_estado_texto(self, texto):
        self.cola_salida.put(("estado", texto))
        
    def _set_progreso(self, corriendo):
        self.cola_salida.put(("progreso", corriendo))

    def _drenar_cola(self):
        try:
            while True:
                tipo, valor = self.cola_salida.get_nowait()
                if tipo == "texto":
                    self.texto_salida.configure(state="normal")
                    self.texto_salida.insert(tk.END, valor)
                    self.texto_salida.see(tk.END)
                    self.texto_salida.configure(state="disabled")
                elif tipo == "botones":
                    estado = "normal" if valor else "disabled"
                    for b in self.botones:
                        b.configure(state=estado)
                elif tipo == "estado":
                    self.estado_var.set(valor)
                elif tipo == "progreso":
                    if valor:
                        self.progreso.start(10)
                    else:
                        self.progreso.stop()
        except queue.Empty:
            pass
        self.root.after(100, self._drenar_cola)

    def _correr_comando(self, comando, etiqueta):
        if self.proceso_corriendo:
            messagebox.showwarning("Ocupado", "Ya hay un paso ejecutándose, espera a que termine.")
            return

        def worker():
            self.proceso_corriendo = True
            self._pedir_estado_botones(False)
            self._set_progreso(True)
            self._pedir_estado_texto(f"Procesando: {etiqueta}...")
            self._escribir(f"\n[{etiqueta}] ================================\n$ {' '.join(comando)}\n\n")
            try:
                proc = subprocess.Popen(
                    comando, cwd=str(BASE_DIR),
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, encoding='utf-8', errors='replace'
                )
                for linea in proc.stdout:
                    self._escribir(linea)
                codigo = proc.wait()
                self._escribir(f"\n[{etiqueta}] finalizado (código {codigo})\n")
                self._pedir_estado_texto(f"Listo.")
                
                if "benchmark.py" in comando and codigo == 0:
                    self.root.after(500, self.cargar_graficas)
                    self.root.after(500, self.cargar_datos)
                    
            except FileNotFoundError as e:
                self._escribir(f"\nERROR: no se encontró el ejecutable ({e}).\n")
                self._pedir_estado_texto("Error: comando no encontrado")
            finally:
                self.proceso_corriendo = False
                self._pedir_estado_botones(True)
                self._set_progreso(False)

        threading.Thread(target=worker, daemon=True).start()

    def correr_generar_muestra(self):
        self._correr_comando([PYTHON, "main.py"], "Generar Muestra")

    def correr_secuencial(self):
        self._correr_comando([PYTHON, "src/secuencial.py"], "Secuencial")

    def correr_paralelo(self):
        n = str(self.n_procesos.get())
        self._correr_comando(["mpiexec", "-n", n, PYTHON, "src/paralelo.py"], f"Paralelo ({n} proc)")

    def correr_benchmark(self):
        self.notebook.select(self.tab_control)
        self._correr_comando([PYTHON, "src/benchmark.py"], "Benchmark Completo")

    def abrir_resultados(self):
        GRAFICAS_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(RESULTADOS_DIR)

if __name__ == "__main__":
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    root = tk.Tk()
    App(root)
    root.mainloop()
