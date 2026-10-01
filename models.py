"""Modelos de datos. Los campos del cliente salen de `campos.py` — acá se listan uno por uno
para que el autocompletado y los errores de tipeo los marque el editor."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Evento:
    """Una fila de la tabla Fecha / Descripción del final de la planilla (ej. "SE LLEVA COPIA DE
    HISTORIA CLINICA"). Es una lista aparte porque hay clientes con varias."""

    id: Optional[int] = None
    fecha: str = ""
    descripcion: str = ""
    orden: int = 0


@dataclass
class Cliente:
    id: Optional[int] = None
    # --- Cliente ---
    apellido: str = ""
    nombre: str = ""
    categoria: str = ""
    dni: str = ""
    cuil: str = ""
    fecha_nacimiento: str = ""
    edad: str = ""
    telefono: str = ""
    contacto_alt: str = ""
    mail: str = ""
    instagram: str = ""
    # --- Domicilio ---
    domicilio: str = ""
    ciudad: str = ""
    domicilio_dni: str = ""
    ciudad_dom_dni: str = ""
    # --- Carpeta ---
    numero: str = ""
    comision_medica: str = ""
    fecha_creacion_carpeta: str = ""
    notas: str = ""
    # --- Accidente ---
    fecha_accidente: str = ""
    art: str = ""
    lesion: str = ""
    prestador: str = ""
    # --- Laboral ---
    empleador: str = ""
    actividad_laboral: str = ""
    antiguedad_laboral: str = ""
    sueldo: str = ""
    capacidad_restante: str = ""
    # --- Siniestro ---
    tipo_siniestro: str = ""
    descripcion_siniestro: str = ""
    lugar_hora_siniestro: str = ""
    miembro_habil: str = ""
    operacion: str = ""
    internacion: str = ""
    sesiones_rehabilitacion: str = ""
    # --- Estado ---
    atencion_abogado: str = ""
    recomendado: str = ""
    posible_alta: str = ""
    hist_clinica: str = ""
    alta_medica: str = ""
    sin_con: str = ""
    secuelas: str = ""
    vista_medica: str = ""
    fecha_homologacion: str = ""
    # --- Solo lectura / derivados ---
    fecha_alta: str = ""
    eventos: list[Evento] = field(default_factory=list)

    @property
    def nombre_completo(self) -> str:
        return " ".join(p for p in (self.apellido, self.nombre) if p).strip()

    @property
    def etiqueta_lista(self) -> str:
        """Como se muestra el cliente en la lista de la ventana principal."""
        return self.nombre_completo or f"Cliente #{self.id}"