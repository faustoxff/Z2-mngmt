"""Definición de TODOS los campos de un cliente, en una sola lista.

Es la fuente única de verdad: de acá salen las columnas de la tabla en Neon, los campos del
formulario y las filas de la impresión. Agregar un campo nuevo es agregar una línea acá y
nada más — el resto se arma solo (ver `neon_db.init_db`, que agrega las columnas que falten).

Origen de los campos: la planilla de una ART (con los mismos nombres para que sea fácil
encontrar cada cosa). Los tipos:
    texto  -> una línea (Entry)
    largo  -> varias líneas (Text)
    fecha  -> se muestra DD/MM/AAAA y se guarda AAAA-MM-DD
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Campo:
    columna: str  # nombre de la columna en Postgres
    etiqueta: str  # lo que se ve en el formulario
    tipo: str = "texto"  # texto | largo | fecha
    ancho: int = 24  # ancho del Entry, en caracteres (aprox.)
    pista: str = ""  # texto de ayuda debajo del campo


# (título de sección, [campos])
SECCIONES: list[tuple[str, list[Campo]]] = [
    (
        "Datos",
        [
            Campo("apellido", "Apellido", ancho=26),
            Campo("nombre", "Nombre", ancho=26),
            Campo("categoria", "Categoría", ancho=8),
            Campo("dni", "DNI", ancho=12),
            Campo("cuil", "CUIL", ancho=14),
            Campo("fecha_nacimiento", "Fecha de nacimiento", tipo="fecha", ancho=12),
            Campo("edad", "Edad", ancho=5),
            Campo("telefono", "Teléfono", ancho=14),
            Campo("contacto_alt", "Contacto alternativo", ancho=16),
            Campo("mail", "Mail", ancho=24),
            Campo("instagram", "Instagram", ancho=18),
        ],
    ),
    (
        "Domicilio",
        [
            Campo("domicilio", "Domicilio", ancho=34),
            Campo("ciudad", "Ciudad", ancho=18),
            Campo("domicilio_dni", "Domicilio DNI", ancho=16, pista="Ej: COINCIDE"),
            Campo("ciudad_dom_dni", "Ciudad dom. DNI", ancho=16),
        ],
    ),
    (
        "Carpeta",
        [
            Campo("numero", "N°", ancho=6),
            Campo("comision_medica", "Comisión médica", ancho=26),
            Campo("fecha_creacion_carpeta", "Fecha creación carpeta", tipo="fecha", ancho=14),
            Campo("notas", "Notas", tipo="largo", ancho=60),
        ],
    ),
    (
        "Accidente",
        [
            Campo("fecha_accidente", "Fecha accidente", tipo="fecha", ancho=12),
            Campo("art", "ART", ancho=16),
            Campo("lesion", "Lesión", ancho=20),
            Campo("prestador", "Prestador", ancho=26),
        ],
    ),
    (
        "Laboral",
        [
            Campo("empleador", "Empleador", ancho=34),
            Campo("actividad_laboral", "Actividad laboral", ancho=22),
            Campo("antiguedad_laboral", "Antigüedad laboral", ancho=12),
            Campo("sueldo", "Sueldo", ancho=16),
            Campo("capacidad_restante", "Capacidad restante", ancho=14),
        ],
    ),
    (
        "Siniestro",
        [
            Campo("tipo_siniestro", "Tipo de siniestro", ancho=26),
            Campo("descripcion_siniestro", "Descripción del siniestro", tipo="largo", ancho=60),
            Campo("lugar_hora_siniestro", "Lugar / hora del siniestro", ancho=22),
            Campo("miembro_habil", "Miembro hábil", ancho=12),
            Campo("operacion", "Operación", ancho=10),
            Campo("internacion", "Internación", ancho=10),
            Campo("sesiones_rehabilitacion", "Sesiones de rehabilitación", ancho=18),
        ],
    ),
    (
        "Estado",
        [
            Campo("atencion_abogado", "Atención abogado", ancho=22),
            Campo("recomendado", "Recomendado por", ancho=22),
            Campo("posible_alta", "Posible alta", ancho=12),
            Campo("hist_clinica", "Hist. clínica", ancho=12),
            Campo("alta_medica", "Alta médica", tipo="fecha", ancho=12),
            Campo("sin_con", "Sin / Con", ancho=10),
            Campo("secuelas", "Secuelas", ancho=20),
            Campo("vista_medica", "Vista médica", ancho=12),
            Campo("fecha_homologacion", "Fecha homologación", tipo="fecha", ancho=12),
        ],
    ),
]

TODOS_LOS_CAMPOS: list[Campo] = [c for _titulo, campos in SECCIONES for c in campos]

#: Campo por el que se detectan duplicados (además del teléfono).
CAMPO_BUSQUEDA_POR_NOMBRE = "apellido"


def columna_de(etiqueta: str) -> str:
    return next(c.columna for c in TODOS_LOS_CAMPOS if c.etiqueta == etiqueta)