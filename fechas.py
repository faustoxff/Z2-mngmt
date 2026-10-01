"""Conversión de fechas entre como las ve el usuario (DD/MM/AAAA) y como se guardan en Neon
(AAAA-MM-DD, ISO). En Neon siempre se guarda ISO: así las fechas se pueden ordenar y filtrar
bien con SQL. Lo demás (separadores, texto de libre) se guarda tal cual lo escribió el usuario.
"""
from datetime import date, datetime

_SEPARADORES = ("-", "/", ".", " ")


def formatear_fecha(fecha_iso: str) -> str:
    """AAAA-MM-DD (o con hora) -> DD/MM/AAAA. Si no parece una fecha, la devuelve igual."""
    if not fecha_iso:
        return ""
    fecha = str(fecha_iso).split("T")[0].strip()
    partes = fecha.split("-")
    if len(partes) != 3:
        return fecha
    anio, mes, dia = partes
    return f"{dia}/{mes}/{anio}"


def a_iso(texto: str) -> str:
    """DD/MM/AAAA, DD-MM-AAAA, DD.MM.AAAA o AAAA-MM-DD -> AAAA-MM-DD.

    Devuelve "" si está vacío, y el texto original (sin tocar) si no se puede interpretar como
    fecha: mejor guardar algo raro que perder lo que el usuario escribió."""
    if not texto:
        return ""
    texto = texto.strip()
    for sep in _SEPARADORES[1:]:
        texto = texto.replace(sep, "-")
    partes = texto.split("-")
    if len(partes) == 3:
        if len(partes[0]) == 4:  # ya viene en ISO
            anio, mes, dia = partes
        else:
            dia, mes, anio = partes
        try:
            return date(int(anio), int(mes), int(dia)).isoformat()
        except (ValueError, TypeError):
            return texto
    return texto


def de_iso(fecha_iso: str) -> str:
    """AAAA-MM-DD -> DD/MM/AAAA, para mostrar en los campos de texto."""
    return formatear_fecha(fecha_iso)


def ahora_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")