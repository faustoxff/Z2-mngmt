"""Popup para configurar y probar la conexión a Neon."""
import tkinter as tk
from tkinter import messagebox

import config
import neon_db


class ConfigPopup(tk.Toplevel):
    def __init__(self, master, on_saved=None):
        super().__init__(master)
        self.on_saved = on_saved
        self.title("Conexión a Neon")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        pad = {"padx": 10, "pady": 6}

        tk.Label(
            self,
            text=(
                "Cadena de conexión de Neon (postgresql://usuario:password@host/db).\n"
                "Se consigue en el panel de Neon → Connect. Queda guardada solo en esta\n"
                "computadora."
            ),
            justify="left",
            anchor="w",
        ).grid(row=0, column=0, columnspan=2, sticky="w", **pad)

        self.cs_var = tk.StringVar(value=config.obtener_connection_string())
        self.cs_entry = tk.Entry(self, textvariable=self.cs_var, width=52, show="*")
        self.cs_entry.grid(row=1, column=0, columnspan=2, sticky="ew", **pad)
        self.cs_entry.bind("<Return>", lambda _e: self._probar())

        ver_btn = tk.Button(self, text="Mostrar", width=10, command=self._alternar_visible)
        ver_btn.grid(row=2, column=1, sticky="e", padx=(0, 10), pady=(0, 6))

        self.resultado_label = tk.Label(self, text="", fg="#6b7280", anchor="w")
        self.resultado_label.grid(row=3, column=0, columnspan=2, sticky="w", **pad)

        btn_frame = tk.Frame(self)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=(4, 10))
        tk.Button(btn_frame, text="Probar", command=self._probar, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Guardar", command=self._guardar, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cerrar", command=self.destroy, width=12).pack(side="left", padx=5)

        self.cs_entry.focus_set()

    def _alternar_visible(self):
        self.cs_entry.config(show="" if self.cs_entry.cget("show") else "*")

    def _probar(self):
        config.guardar_connection_string(self.cs_var.get())
        self.resultado_label.config(text="Conectando...", fg="#6b7280")
        self.update_idletasks()
        try:
            producto = neon_db.probar_conexion()
        except neon_db.NeonError as exc:
            self.resultado_label.config(text="Falló la conexión", fg="#ef4444")
            messagebox.showerror("No se pudo conectar", str(exc), parent=self)
            return
        self.resultado_label.config(text=f"Conectado a {producto}", fg="#16a34a")

    def _guardar(self):
        config.guardar_connection_string(self.cs_var.get())
        messagebox.showinfo("Guardado", "Conexión a Neon guardada.", parent=self)
        if self.on_saved:
            self.on_saved()
        self.destroy()