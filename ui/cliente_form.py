"""Formulario de alta/edición: todos los campos de la planilla, agrupados por sección y con
scroll (son muchos, no entran en una pantalla).

El formulario se construye leyendo `campos.py`, así que agregar un campo ahí lo agrega acá
automáticamente. `self.vars` guarda lo que el usuario escribió, y `armar_cliente()` lo pasa a
un Cliente listo para guardar."""
import tkinter as tk
from tkinter import messagebox, ttk

import fechas
import neon_db
from campos import SECCIONES
from models import Cliente, Evento


class ClienteForm(tk.Toplevel):
    def __init__(self, master, on_saved, cliente: Cliente | None = None):
        super().__init__(master)
        self.on_saved = on_saved
        self.cliente = cliente
        self.title("Editar cliente" if cliente else "Nuevo cliente")
        self.geometry("900x680")
        self.minsize(700, 520)
        self.transient(master)
        self.grab_set()

        self.vars: dict[str, tk.StringVar] = {}
        self.texts: dict[str, tk.Text] = {}
        self.eventos_widgets: list[dict] = []

        self._construir()
        if cliente:
            self._cargar(cliente)
        self._agregar_fila_evento()

    # ---------- construcción ----------

    def _construir(self):
        # Canvas + scrollbar: el contenido es más alto que la ventana.
        container = tk.Frame(self)
        container.pack(fill="both", expand=True)
        canvas = tk.Canvas(container, highlightthickness=0)
        self.canvas = canvas
        scroll = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        body = tk.Frame(canvas)
        # El scrollregion se recalcula cuando cambia el alto del contenido...
        body.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        ventana = canvas.create_window((0, 0), window=body, anchor="nw")
        # ...y el contenido se estira al ancho del canvas cuando cambia el ancho de la ventana.
        # (create_window no acepta fill="x": el ancho hay que setearlo a mano con itemconfig.)
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(ventana, width=e.width),
        )
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        # Scroll con la rueda del mouse. El bind se hace al entrar con el puntero y se saca al
        # salir (un bind_all sin quitar dejaría el scroll atado al widget viejo para siempre).
        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", self._scroll))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

        # Apellido y nombre van arriba, más grandes, porque son lo primero que se busca después.
        top = ttk.LabelFrame(body, text="Cliente", padding=10)
        top.pack(fill="x", padx=12, pady=(12, 6))
        for col, (columna, etiqueta, ancho) in enumerate(
            [("apellido", "Apellido", 30), ("nombre", "Nombre", 30)]
        ):
            tk.Label(top, text=etiqueta + " *").grid(row=0, column=col, sticky="w", padx=(0 if col == 0 else 14, 6))
            var = tk.StringVar()
            self.vars[columna] = var
            var.trace_add("write", lambda *_a, v=var: self._mayusculas(v))
            entry = tk.Entry(top, textvariable=var, width=ancho, font=("TkDefaultFont", 12, "bold"))
            entry.grid(row=1, column=col, sticky="w", padx=(0 if col == 0 else 14, 0))
            entry.bind("<Return>", lambda _e: self._guardar())

        self.aviso_var = tk.StringVar()
        tk.Label(top, textvariable=self.aviso_var, fg="#f59e0b", anchor="w").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )

        # Secciones que vienen de campos.py. Apellido y nombre ya van arriba, así que se sacan
        # de su sección (el resto de "Cliente" —DNI, teléfono, mail...— sí va con el resto).
        for titulo, lista in SECCIONES:
            self._seccion(body, titulo, [c for c in lista if c.columna not in ("apellido", "nombre")])

        # Tabla Fecha / Descripción del final de la planilla.
        self._seccion_eventos(body)

        # Botones, en un frame aparte para que queden siempre visibles, sin scroll.
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", padx=12, pady=10)
        self.guardar_btn = tk.Button(btn_frame, text="Guardar", command=self._guardar, width=14)
        self.guardar_btn.pack(side="right", padx=5)
        self.guardar_btn.bind("<Return>", lambda _e: self._guardar())
        tk.Button(
            btn_frame, text="Cancelar" if self.cliente else "Cerrar", command=self.destroy, width=14
        ).pack(side="right", padx=5)

    def _seccion(self, padre, titulo: str, lista) -> None:
        frame = ttk.LabelFrame(padre, text=titulo, padding=10)
        frame.pack(fill="x", padx=12, pady=6)
        fila = 0
        for i, campo in enumerate(lista):
            # Dos pares etiqueta/campo por fila para que no quede un scroll interminable.
            col = (i % 2) * 2
            if i % 2 == 0 and i > 0:
                fila += 1
            if campo.tipo == "largo":
                fila += 1  # ocupa la fila entera
            self._campo(frame, campo, fila, col)
        # Las dos columnas de campos pesan lo mismo, así el segundo par no queda pegado al
        # borde derecho por un hueco enorme.
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)

    def _campo(self, frame, campo, fila: int, col: int) -> None:
        if campo.tipo == "largo":
            tk.Label(frame, text=campo.etiqueta).grid(row=fila, column=col, sticky="nw", padx=(0, 8), pady=4)
            text = tk.Text(frame, width=campo.ancho, height=3, wrap="word")
            text.grid(row=fila, column=col + 1, sticky="ew", padx=(0, 18), pady=4)
            self.texts[campo.columna] = text
            frame.columnconfigure(col + 1, weight=1)
            return

        var = tk.StringVar()
        self.vars[campo.columna] = var
        tk.Label(frame, text=campo.etiqueta).grid(row=fila, column=col, sticky="w", padx=(0, 8), pady=4)
        entry = tk.Entry(frame, textvariable=var, width=campo.ancho)
        entry.grid(row=fila, column=col + 1, sticky="w", padx=(0, 18), pady=4)
        if campo.tipo == "fecha":
            entry.bind("<Return>", lambda _e: self._normalizar_fecha(entry, var))

    def _seccion_eventos(self, padre) -> None:
        frame = ttk.LabelFrame(padre, text="Fecha / Descripción", padding=10)
        frame.pack(fill="x", padx=12, pady=6)
        frame.columnconfigure(1, weight=1)

        self.eventos_frame = tk.Frame(frame)
        self.eventos_frame.grid(row=0, column=0, columnspan=3, sticky="ew")
        self.eventos_frame.columnconfigure(1, weight=1)

        tk.Button(frame, text="+ Agregar fila", command=self._agregar_fila_evento).grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(6, 0)
        )

    def _agregar_fila_evento(self, valores: Evento | None = None):
        fila = tk.Frame(self.eventos_frame)
        fila.pack(fill="x", pady=2)
        fecha_var = tk.StringVar(value=valores.fecha if valores else "")
        desc_var = tk.StringVar(value=valores.descripcion if valores else "")
        entry_fecha = tk.Entry(fila, textvariable=fecha_var, width=12)
        entry_fecha.pack(side="left")
        entry_desc = tk.Entry(fila, textvariable=desc_var)
        entry_desc.pack(side="left", fill="x", expand=True, padx=6)
        entry_fecha.bind("<Return>", lambda _e: self._normalizar_fecha(entry_fecha, fecha_var))
        quitar = tk.Button(fila, text="Quitar", width=8, command=lambda: self._quitar_fila(fila))
        quitar.pack(side="left")
        widgets = {"frame": fila, "fecha": fecha_var, "descripcion": desc_var}
        self.eventos_widgets.append(widgets)

    def _quitar_fila(self, fila) -> None:
        for widgets in self.eventos_widgets:
            if widgets["frame"] is fila:
                self.eventos_widgets.remove(widgets)
                break
        fila.destroy()
        if not self.eventos_widgets:  # siempre queda al menos una fila para escribir
            self._agregar_fila_evento()

    # ---------- carga / guardado ----------

    def _scroll(self, event) -> None:
        self.canvas.yview_scroll(-1 * (event.delta // 120), "units")

    def _mayusculas(self, var: tk.StringVar) -> None:
        """Apellido y nombre se ven en mayúscula mientras se escribe (como la planilla)."""
        texto = var.get()
        if texto != texto.upper():
            var.set(texto.upper())

    def _cargar(self, cliente: Cliente) -> None:
        for campo_columna, var in self.vars.items():
            var.set(getattr(cliente, campo_columna, "") or "")
        for columna, text in self.texts.items():
            text.insert("1.0", getattr(cliente, columna, "") or "")
        for evento in cliente.eventos:
            self._agregar_fila_evento(evento)

    def _normalizar_fecha(self, entry, var) -> None:
        """Al apretar Enter, DD/MM/AAAA se ve immediately formateado (si se puede)."""
        iso = fechas.a_iso(var.get())
        if iso:
            var.set(fechas.de_iso(iso))

    def armar_cliente(self) -> Cliente:
        """Arma el Cliente con lo escrito en el formulario."""
        cliente = self.cliente or Cliente()
        for columna, var in self.vars.items():
            setattr(cliente, columna, var.get().strip())
        for columna, text in self.texts.items():
            setattr(cliente, columna, text.get("1.0", "end").strip())
        cliente.eventos = [
            Evento(fecha=w["fecha"].get().strip(), descripcion=w["descripcion"].get().strip())
            for w in self.eventos_widgets
        ]
        return cliente

    def _guardar(self):
        cliente = self.armar_cliente()
        if not cliente.apellido.strip() and not cliente.nombre.strip():
            messagebox.showwarning("Falta el nombre", "Cargá al menos el apellido o el nombre.", parent=self)
            return

        self.guardar_btn.config(state="disabled", text="Guardando...")
        self.update_idletasks()
        try:
            if self.cliente:
                neon_db.actualizar_cliente(cliente)
            else:
                dups = neon_db.buscar_duplicados(cliente.nombre_completo, cliente.telefono)
                if dups and not self._confirmar_duplicado(dups):
                    return
                cliente.id = neon_db.crear_cliente(cliente)
        except neon_db.NeonError as exc:
            self.guardar_btn.config(state="normal", text="Guardar")
            messagebox.showerror("No se pudo guardar", str(exc), parent=self)
            return
        except Exception as exc:  # noqa: BLE001 - un error inesperado no debe cerrar la app
            self.guardar_btn.config(state="normal", text="Guardar")
            messagebox.showerror("Error inesperado", str(exc), parent=self)
            return

        if self.on_saved:
            self.on_saved(cliente)
        self.destroy()

    def _confirmar_duplicado(self, dups) -> bool:
        resumen = "\n".join(f"• {d.etiqueta_lista} — {d.telefono} ({d.fecha_alta})" for d in dups[:5])
        return messagebox.askyesno(
            "Posible duplicado",
            f"Ya hay {len(dups)} cliente(s) parecidos:\n\n{resumen}\n\n¿Guardar igual?",
            parent=self,
        )