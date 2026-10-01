"""Ventana principal: la lista de clientes (que se lee de Neon) y los botones para cargar,
editar, borrar e imprimir. El alta/edición pasa por el formulario completo (ui/cliente_form.py)."""
import tkinter as tk
from tkinter import messagebox, ttk

import config
import documento
import impresion
import neon_db
from ui.cliente_form import ClienteForm
from ui.config_popup import ConfigPopup


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Clientes")
        self.geometry("860x600")
        self.minsize(700, 480)

        self.clientes: list = []

        self._construir_ui()
        self._refrescar_conexion()
        self.cargar_clientes()

    def _construir_ui(self):
        # ---- Barra superior: estado de la conexión ----
        top = tk.Frame(self)
        top.pack(fill="x", padx=10, pady=(8, 0))
        self.estado_label = tk.Label(top, text="", anchor="w")
        self.estado_label.pack(side="left")
        tk.Button(top, text="Conexión", command=self._abrir_config).pack(side="right")
        tk.Button(top, text="Refrescar", command=self.cargar_clientes).pack(side="right", padx=6)

        # ---- Botones de acción ----
        acciones = tk.Frame(self)
        acciones.pack(fill="x", padx=10, pady=(10, 0))
        self.nuevo_btn = tk.Button(acciones, text="Nuevo cliente", command=self._nuevo, width=15)
        self.nuevo_btn.pack(side="left")
        self.nuevo_btn.bind("<Return>", lambda _e: self._nuevo())
        tk.Button(acciones, text="Editar", command=self._editar, width=11).pack(side="left", padx=6)
        tk.Button(acciones, text="Borrar", command=self._borrar, width=11).pack(side="left")
        tk.Button(acciones, text="Documento", command=self._documento, width=11).pack(side="left", padx=6)
        tk.Button(acciones, text="Imprimir", command=self._imprimir, width=11).pack(side="left")

        # ---- Buscador ----
        buscar_bar = tk.Frame(self)
        buscar_bar.pack(fill="x", padx=10, pady=(10, 0))
        tk.Label(buscar_bar, text="Buscar:").pack(side="left")
        self.buscar_var = tk.StringVar()
        self.buscar_var.trace_add("write", lambda *_: self.cargar_clientes())
        buscar_entry = tk.Entry(buscar_bar, textvariable=self.buscar_var, width=34)
        buscar_entry.pack(side="left", padx=6)

        # ---- Listado ----
        lista_frame = tk.Frame(self)
        lista_frame.pack(fill="both", expand=True, padx=10, pady=8)
        tree_frame = tk.Frame(lista_frame)
        tree_frame.pack(fill="both", expand=True)

        columnas = ("nombre", "telefono", "dni", "accidente", "id")
        self.tree = ttk.Treeview(
            tree_frame, columns=columnas, show="headings", selectmode="browse", height=14
        )
        self.tree.heading("nombre", text="Apellido y nombre")
        self.tree.heading("telefono", text="Teléfono")
        self.tree.heading("dni", text="DNI")
        self.tree.heading("accidente", text="Fecha accidente")
        self.tree.heading("id", text="ID")
        self.tree.column("nombre", width=280)
        self.tree.column("telefono", width=130)
        self.tree.column("dni", width=110)
        self.tree.column("accidente", width=120, anchor="center")
        self.tree.column("id", width=50, anchor="center", stretch=False)
        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self._editar())
        self.tree.bind("<Delete>", lambda _e: self._borrar())

        # ---- Pie ----
        self.pie_label = tk.Label(self, text="", anchor="w", fg="#6b7280")
        self.pie_label.pack(fill="x", padx=10, pady=(0, 8))

    # ---------- conexión ----------

    def _refrescar_conexion(self):
        if not config.obtener_connection_string():
            self.estado_label.config(text="● Sin configurar — abrí Conexión", fg="#f59e0b")
            return
        self.estado_label.config(text="● Conectando...", fg="#6b7280")
        self.update_idletasks()
        try:
            neon_db.probar_conexion()
        except neon_db.NeonError:
            self.estado_label.config(text="● Sin conexión", fg="#ef4444")
            return
        self.estado_label.config(text="● Conectado", fg="#16a34a")

    def _abrir_config(self):
        ConfigPopup(self, on_saved=lambda: (self._refrescar_conexion(), self.cargar_clientes()))

    # ---------- datos ----------

    def cargar_clientes(self, mensaje: str = ""):
        self.tree.delete(*self.tree.get_children())
        if not config.obtener_connection_string():
            self.pie_label.config(text="Configurá la conexión para ver los clientes.", fg="#f59e0b")
            return
        try:
            self.clientes = neon_db.listar_clientes(self.buscar_var.get().strip() or None)
        except neon_db.NeonError as exc:
            self.clientes = []
            self.pie_label.config(text="No se pudieron leer los clientes.", fg="#ef4444")
            messagebox.showerror("Error", str(exc))
            return

        for c in self.clientes:
            self.tree.insert(
                "",
                "end",
                iid=str(c.id),
                values=(c.nombre_completo, c.telefono, c.dni, c.fecha_accidente, c.id),
            )
        if not self.clientes and not mensaje:
            mensaje = "No hay clientes cargados todavía."
        self.pie_label.config(
            text=mensaje or f"{len(self.clientes)} cliente(s).", fg="#6b7280"
        )

    def _seleccionado(self) -> object | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Nada seleccionado", "Elegí un cliente de la lista primero.")
            return None
        return next((c for c in self.clientes if str(c.id) == sel[0]), None)

    # ---------- acciones ----------

    def _nuevo(self):
        ClienteForm(self, on_saved=self._tras_guardar)

    def _editar(self):
        cliente = self._seleccionado()
        if cliente:
            ClienteForm(self, on_saved=self._tras_guardar, cliente=cliente)

    def _tras_guardar(self, cliente) -> None:
        """Vuelve a la lista y deja el cliente guardado seleccionado, para verlo de una."""
        self.cargar_clientes(f"Cliente guardado: {cliente.etiqueta_lista}")
        if cliente.id and self.tree.exists(str(cliente.id)):
            self.tree.selection_set(str(cliente.id))
            self.tree.see(str(cliente.id))

    def _borrar(self):
        cliente = self._seleccionado()
        if not cliente:
            return
        if not messagebox.askyesno(
            "Borrar cliente",
            f"¿Borrar a {cliente.etiqueta_lista}?\n\nEsto borra el dato para siempre.",
        ):
            return
        try:
            neon_db.eliminar_cliente(cliente.id)
        except neon_db.NeonError as exc:
            messagebox.showerror("Error", str(exc))
            return
        self.cargar_clientes("Cliente borrado.")

    def _imprimir(self):
        cliente = self._seleccionado()
        if not cliente:
            return
        impresion.imprimir_cliente(cliente)

    def _documento(self):
        """Genera el .docx completo (planilla + convenio + carta) desde la plantilla."""
        cliente = self._seleccionado()
        if not cliente:
            return
        try:
            ruta = documento.generar_documento(cliente)
        except documento.DocumentoError as exc:
            messagebox.showerror("No se pudo generar el documento", str(exc))
            return
        messagebox.showinfo(
            "Documento listo",
            f"Se guardó en:\n{ruta}\n\nSe abrió con el programa de Word.",
        )
        documento.abrir_documento(ruta)