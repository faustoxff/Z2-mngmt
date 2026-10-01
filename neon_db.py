"""Acceso a Neon (Postgres en la nube). NO hay base local: esta app lee y escribe siempre
contra Neon, que es la única fuente de datos.

El esquema de la tabla `clientes` se arma a partir de `campos.py`: si le falta alguna columna
(porque se agregó un campo nuevo a la app después de haber creado la tabla), `init_db()` la
agrega sola con ALTER TABLE ... ADD COLUMN IF NOT EXISTS. Los datos viejos nunca se borran.

Modelo de datos hacia la app vieja del padre: esta app es la ÚNICA que escribe acá. La otra
app (GestorClientes, que sigue con su SQLite local) solo LEE esta tabla para avisar de
duplicados — nunca sube sus clientes. Por eso las funciones de escritura están separadas de
las de lectura.
"""
from contextlib import contextmanager
from typing import Iterable, Optional

import campos
import config
import fechas
from models import Cliente, Evento

TIMEOUT_CONEXION = 15  # segundos — si no hay internet, no dejamos la UI colgada


class NeonError(Exception):
    """Error de conexión, de red, o de Neon en sí. El mensaje está pensado para mostrarse
    directo en un messagebox, sin que la app se caiga."""


def _requerir_psycopg2():
    try:
        import psycopg2
    except ImportError as exc:
        raise NeonError(
            "Falta instalar la librería psycopg2-binary:\n\npip install psycopg2-binary"
        ) from exc
    return psycopg2


def _conectar(psycopg2):
    connection_string = config.obtener_connection_string()
    if not connection_string:
        raise NeonError(
            "No está configurada la conexión.\n\n"
            "Abrí Conexión y pegá la cadena de conexión "
            "(postgresql://usuario:password@host/db)."
        )
    try:
        # DictCursor: las filas llegan como dict (fila["columna"]), que es lo que espera el
        # código de lectura. Con el cursor normal de psycopg2 solo se accede por posición.
        from psycopg2.extras import DictCursor

        return psycopg2.connect(
            connection_string, connect_timeout=TIMEOUT_CONEXION, cursor_factory=DictCursor
        )
    except psycopg2.Error as exc:
        raise NeonError(f"No se pudo conectar (revisá la conexión a internet):\n{exc}") from exc


@contextmanager
def get_conn():
    """Conexión nueva por operación (psycopg2 no es thread-safe si se comparte una conexión).
    Commit automático al salir del bloque sin excepción."""
    psycopg2 = _requerir_psycopg2()
    conn = _conectar(psycopg2)
    try:
        yield conn
        conn.commit()
    except psycopg2.Error as exc:
        conn.rollback()
        raise NeonError(f"Error de la base:\n{exc}") from exc
    finally:
        conn.close()


def probar_conexion() -> None:
    """Chequea que arrive a Neon (o lanza NeonError)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")


# ---------- Normalización ----------
# Misma lógica que la app vieja del padre, para que las comparaciones de duplicados den igual
# desde los dos lados.


def normalizar_nombre(nombre: str) -> str:
    """MAYÚSCULAS, sin tildes/diacríticos y con espacios múltiples colapsados."""
    if not nombre:
        return ""
    import unicodedata

    s = nombre.strip().upper()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.split())


def normalizar_telefono(contacto: str) -> str:
    """Saca espacios, guiones y paréntesis, para comparar teléfonos escritos distinto."""
    if not contacto:
        return ""
    for ch in (" ", "-", "(", ")"):
        contacto = contacto.replace(ch, "")
    return contacto.strip()


# ---------- Esquema ----------


def init_db() -> None:
    """Crea lo que falte (tablas, columnas). Idempotente: se puede llamar en cada arranque."""
    columnas = [c.columna for c in campos.TODOS_LOS_CAMPOS]
    with get_conn() as conn:
        with conn.cursor() as cur:
            definicion = ",\n                    ".join(f'"{c}" TEXT NOT NULL DEFAULT \'\'' for c in columnas)
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS clientes (
                    id SERIAL PRIMARY KEY,
                    {definicion},
                    contacto_normalizado TEXT NOT NULL DEFAULT '',
                    fecha_alta TIMESTAMPTZ NOT NULL DEFAULT now(),
                    fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            # Por si la tabla ya existía de una versión anterior de la app con menos campos.
            for c in columnas:
                cur.execute(f'ALTER TABLE clientes ADD COLUMN IF NOT EXISTS "{c}" TEXT NOT NULL DEFAULT \'\'')
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_clientes_contacto_norm ON clientes(contacto_normalizado)"
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_clientes_fecha_alta ON clientes(fecha_alta DESC)")

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS cliente_eventos (
                    id SERIAL PRIMARY KEY,
                    cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
                    fecha TEXT NOT NULL DEFAULT '',
                    descripcion TEXT NOT NULL DEFAULT '',
                    orden INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_eventos_cliente ON cliente_eventos(cliente_id, orden)"
            )


# ---------- Escritura (solo esta app escribe acá) ----------


def _valores(cliente: Cliente) -> dict:
    """Arma el dict columna -> valor a partir de un Cliente, pasando fechas a ISO."""
    datos = {}
    for campo in campos.TODOS_LOS_CAMPOS:
        valor = getattr(cliente, campo.columna, "") or ""
        datos[campo.columna] = fechas.a_iso(valor) if campo.tipo == "fecha" else valor
    return datos


def crear_cliente(cliente: Cliente) -> int:
    """Inserta un cliente (y sus eventos) y devuelve su id en Neon."""
    datos = _valores(cliente)
    datos["contacto_normalizado"] = normalizar_telefono(datos.get("telefono", ""))
    columnas = list(datos)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO clientes ({', '.join(columnas)}) "
                f"VALUES ({', '.join(['%s'] * len(columnas))}) RETURNING id",
                [datos[c] for c in columnas],
            )
            cliente_id = cur.fetchone()[0]
            _guardar_eventos(cur, cliente_id, cliente.eventos)
    return cliente_id


def actualizar_cliente(cliente: Cliente) -> None:
    """Actualiza todos los campos del cliente y reemplaza su lista de eventos."""
    datos = _valores(cliente)
    datos["contacto_normalizado"] = normalizar_telefono(datos.get("telefono", ""))
    setear = ", ".join(f'"{c}" = %s' for c in datos)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE clientes SET {setear}, fecha_actualizacion = now() WHERE id = %s",
                [*datos.values(), cliente.id],
            )
            cur.execute("DELETE FROM cliente_eventos WHERE cliente_id = %s", (cliente.id,))
            _guardar_eventos(cur, cliente.id, cliente.eventos)


def _guardar_eventos(cur, cliente_id: int, eventos: Iterable[Evento]) -> None:
    for orden, ev in enumerate(eventos):
        if not (ev.fecha.strip() or ev.descripcion.strip()):
            continue  # fila vacía (el usuario la agregó y no la llenó) — no se guarda
        cur.execute(
            "INSERT INTO cliente_eventos (cliente_id, fecha, descripcion, orden) VALUES (%s, %s, %s, %s)",
            (cliente_id, fechas.a_iso(ev.fecha), ev.descripcion.strip(), orden),
        )


def eliminar_cliente(cliente_id: int) -> None:
    """Borra el cliente y sus eventos (los eventos se van por ON DELETE CASCADE)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM clientes WHERE id = %s", (cliente_id,))


# ---------- Lectura ----------


def _fila_a_cliente(fila) -> Cliente:
    """Arma un Cliente desde una fila de la tabla clientes (por nombre de columna)."""
    datos = dict(fila)
    cliente = Cliente(id=datos.get("id"))
    for campo in campos.TODOS_LOS_CAMPOS:
        valor = datos.get(campo.columna) or ""
        setattr(cliente, campo.columna, fechas.de_iso(valor) if campo.tipo == "fecha" else valor)
    fecha = datos.get("fecha_alta")
    cliente.fecha_alta = fecha.strftime("%d/%m/%Y %H:%M") if fecha is not None else ""
    return cliente


def listar_clientes(texto: Optional[str] = None) -> list[Cliente]:
    """Clientes del más nuevo al más viejo. `texto` filtra por apellido, nombre o teléfono."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            if texto:
                like = f"%{texto.strip()}%"
                cur.execute(
                    "SELECT * FROM clientes WHERE apellido ILIKE %s OR nombre ILIKE %s "
                    "OR telefono ILIKE %s OR dni ILIKE %s "
                    "ORDER BY fecha_alta DESC, id DESC",
                    (like, like, like, like),
                )
            else:
                cur.execute("SELECT * FROM clientes ORDER BY fecha_alta DESC, id DESC")
            clientes = [_fila_a_cliente(f) for f in cur.fetchall()]
    _cargar_eventos(clientes)
    return clientes


def obtener_cliente(cliente_id: int) -> Optional[Cliente]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM clientes WHERE id = %s", (cliente_id,))
            fila = cur.fetchone()
            if not fila:
                return None
            cliente = _fila_a_cliente(fila)
    _cargar_eventos([cliente])
    return cliente


def _cargar_eventos(clientes: list[Cliente]) -> None:
    """Carga la lista Fecha/Descripción de varios clientes de una sola consulta (evita traer una
    fila de la tabla por cada cliente)."""
    if not clientes:
        return
    ids = [c.id for c in clientes]
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, cliente_id, fecha, descripcion, orden FROM cliente_eventos "
                "WHERE cliente_id = ANY(%s) ORDER BY cliente_id, orden, id",
                (ids,),
            )
            por_cliente: dict = {i: [] for i in ids}
            for f in cur.fetchall():
                por_cliente.setdefault(f["cliente_id"], []).append(
                    Evento(id=f["id"], fecha=fechas.de_iso(f["fecha"]),
                           descripcion=f["descripcion"], orden=f["orden"])
                )
    for c in clientes:
        c.eventos = por_cliente.get(c.id, [])


def buscar_duplicados(nombre: str, telefono: str = "") -> list[Cliente]:
    """Chequeo NO bloqueante: primero por teléfono normalizado, y si no matchea, por nombre
    completo (normalizado, sin tildes ni mayúsculas).

    Esta es la función que la app vieja de tu papá va a usar contra esta misma tabla para
    avisarle si el cliente que está por cargar ya existe acá."""
    tel_norm = normalizar_telefono(telefono)
    nombre_norm = normalizar_nombre(nombre)

    with get_conn() as conn:
        with conn.cursor() as cur:
            if tel_norm:
                cur.execute(
                    "SELECT * FROM clientes WHERE contacto_normalizado = %s ORDER BY fecha_alta DESC",
                    (tel_norm,),
                )
                filas = cur.fetchall()
                if filas:
                    return [_fila_a_cliente(f) for f in filas]

            if nombre_norm:
                # apellido y nombre van en columnas separadas, así que no se puede comparar
                # con SQL directo: se traen y se comparan en Python (es lo mismo que hace la
                # app vieja, y así se ignora tildes con unicodedata).
                cur.execute("SELECT * FROM clientes")
                coincidencias = [
                    _fila_a_cliente(f)
                    for f in cur.fetchall()
                    if normalizar_nombre(f["apellido"] + " " + (f["nombre"] or "")) == nombre_norm
                ]
                return coincidencias

    return []


def contar_clientes() -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM clientes")
            return cur.fetchone()[0]