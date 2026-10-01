"""Rutas de datos y configuración. Todo se guarda en la carpeta de datos del usuario
(Windows: %APPDATA%\\ClientesNeon, Linux/Mac: ~/.local/share/ClientesNeon), así la app
funciona bien sin importar desde dónde se ejecute."""
import json
import os
import sys
from pathlib import Path

APP_NAME = "ClientesNeon"


def get_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path.home() / ".local" / "share"
    data_dir = base / APP_NAME
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


CONFIG_PATH = get_data_dir() / "config.json"


def _leer_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _escribir_config(datos: dict) -> None:
    try:
        CONFIG_PATH.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass  # no crashear si no se puede escribir (disco lleno, permisos, etc.)


def obtener_connection_string() -> str:
    """Cadena de conexión de Neon (postgresql://usuario:password@host/db). Se puede configurar
    desde Configuración > Conexión a Neon dentro de la app, o dejar puesta en la variable de
    entorno NEON_DATABASE_URL (útil para Empaquetado/GitHub). Si nunca se configuró, vacío."""
    return os.environ.get("NEON_DATABASE_URL", "").strip() or _leer_config().get(
        "neon_connection_string", ""
    )


def guardar_connection_string(connection_string: str) -> None:
    datos = _leer_config()
    datos["neon_connection_string"] = connection_string.strip()
    _escribir_config(datos)


def obtener_carpeta_documentos() -> Path:
    """Dónde se guardan los .docx generados. Por defecto, una carpeta "Clientes" en Descargas
    (que es donde se los busca después para imprimir o mandar). Se puede cambiar desde
    Configuración → Carpeta de documentos."""
    guardada = _leer_config().get("carpeta_documentos", "")
    if guardada:
        return Path(guardada)
    descargas = Path.home() / "Downloads"
    base = descargas if descargas.is_dir() else Path.home()
    return base / "Clientes"


def guardar_carpeta_documentos(carpeta: str) -> None:
    datos = _leer_config()
    datos["carpeta_documentos"] = carpeta.strip()
    _escribir_config(datos)