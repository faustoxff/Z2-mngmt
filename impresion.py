"""Impresión de un cliente: arma un HTML con el MISMO diseño de la planilla (las mismas celdas,
en el mismo lugar) y lo abre en el navegador, donde el botón "Imprimir" lo saca por impresora o
a PDF. Mismo criterio que usa la app de la PC de tu papá: sin librerías pesadas tipo reportlab.

Los valores salen del Cliente por nombre de columna (ver `campos.py`); si un campo está vacío
se imprime un guion, para que se vea que la celda está sin completar."""
import html
import tempfile
import webbrowser
from typing import Iterable, Optional

from models import Cliente

Vacio = "—"  # lo que se ve en una celda sin completar


def _v(cliente: Cliente, columna: str, defecto: str = "") -> str:
    """Valor de un campo, escapado para HTML. Si está vacío, devuelve el guion."""
    valor = getattr(cliente, columna, "") or defecto
    return html.escape(str(valor).strip()) if str(valor).strip() else Vacio


# ---- La grilla de la planilla: etiqueta | valor | etiqueta | valor ----

_ESTILO = """
  @page { size: A4 portrait; margin: 10mm; }
  * { box-sizing: border-box; }
  body { font-family: Arial, Helvetica, sans-serif; font-size: 9pt; color: #000; margin: 0; }
  .hoja { width: 198mm; margin: 0 auto; }
  table { border-collapse: collapse; width: 100%; margin-bottom: 4px; }
  td, th { border: 1px solid #333; padding: 2px 4px; vertical-align: top; }
  th { background: #f0f0f0; text-align: left; font-weight: bold; white-space: nowrap; }
  /* Los labels largos ("FECHA CREACION CARPETA", "SESIONES REHABILITACION") tienen que poder
     partirse en dos líneas: con nowrap se cortaban contra el borde de la celda. */
  th.largo { white-space: normal; }
  td.v { width: auto; }
  .alto td, .alto th { padding: 6px 5px; }
  .titulo { font-size: 26pt; font-weight: bold; letter-spacing: 1px; }
  .subtitulo { font-size: 15pt; }
  .gris { background: #d9d9d9; }
  .rojo { color: #e11d1d; font-weight: bold; font-size: 12pt; }
  .mini { display: inline-block; width: 34px; height: 18px; border: 1px solid #333; }
  button { font-size: 1rem; padding: 8px 16px; margin-bottom: 16px; }
  @media print { button { display: none; } .hoja { page-break-after: always; } }
"""


def _celda(etiqueta: str, valor: str, colspan: int = 1) -> str:
    """Una celda etiqueta + una celda valor. La etiqueta va con el texto tal cual (acentos
    incluidos) y se escapa acá, una sola vez."""
    return f"<th>{html.escape(etiqueta)}</th><td class='v' colspan='{colspan}'>{valor}</td>"


def _fila(etiqueta: str, valor: str, etiqueta2: str = "", valor2: str = "", clase: str = "") -> str:
    """Fila con dos pares etiqueta/valor (o uno solo si no se pasa el segundo)."""
    if not etiqueta2:
        return f"<tr class='{clase}'>{_celda(etiqueta, valor, 3)}</tr>"
    return (
        f"<tr class='{clase}'>{_celda(etiqueta, valor)}{_celda(etiqueta2, valor2)}</tr>"
    )


def _fila_larga(etiqueta: str, valor: str) -> str:
    """Fila de un solo par, con etiqueta que puede partirse en dos líneas (para los labels
    largos como "FECHA CREACION CARPETA")."""
    return f"<tr><th class='largo'>{html.escape(etiqueta)}</th><td class='v' colspan='3'>{valor}</td></tr>"


# ---------- bloques de la planilla ----------


def _bloque_encabezado(c: Cliente) -> str:
    """La fila de arriba: apellido (grande, a la izquierda), nombre (al centro, sobre gris) y
    la categoría a la derecha, con elApplicable rojo. El número de expediente va en el bloque
    del accidente, que es donde está en la planilla."""
    return f"""
    <table>
      <colgroup><col style='width:32%'><col style='width:46%'><col style='width:22%'></colgroup>
      <tr>
        <td class='titulo'>{_v(c, "apellido")}</td>
        <td class='subtitulo gris' align='center'>{_v(c, "nombre")}</td>
        <td align='center'><span class='rojo'>&#9654;</span><br><b>CAT</b> {_v(c, "categoria")}</td>
      </tr>
    </table>
    """


def _bloque_personales(c: Cliente) -> str:
    """Datos personales, con la grilla de dos pares (izquierda/derecha) de la planilla."""
    return f"""
    <table>
      {_fila("TELEFONO", _v(c, "telefono"), "CONTACTO ALT.", _v(c, "contacto_alt"))}
      {_fila("DNI", _v(c, "dni"), "CUIL", _v(c, "cuil"))}
      {_fila("FECHA DE NACIMIENTO", _v(c, "fecha_nacimiento"), "EDAD", _v(c, "edad"))}
      {_fila("DOMICILIO", _v(c, "domicilio"), "CIUDAD", _v(c, "ciudad"))}
      {_fila("DOMICILIO DNI", _v(c, "domicilio_dni"), "CIUDAD DOM. DNI", _v(c, "ciudad_dom_dni"))}
      {_fila("COMISION MEDICA", _v(c, "comision_medica"), "MAIL", _v(c, "mail"))}
      <tr><th class='largo'>FECHA CREACION CARPETA</th><td class='v'>{_v(c, "fecha_creacion_carpeta")}</td>
          <th>INSTAGRAM</th><td class='v'>{_v(c, "instagram")}</td></tr>
    </table>
    """


def _bloque_accidente(c: Cliente) -> str:
    """Accidente: las primeras dos filas tienen la celda del número de expediente a la
    derecha (en la planilla es la celda con el número grande)."""
    return f"""
    <table>
      <colgroup><col style='width:26%'><col style='width:60%'><col style='width:14%'></colgroup>
      <tr>
        <th>FECHA ACCIDENTE</th><td class='v'>{_v(c, "fecha_accidente")}</td>
        <td class='v' align='center' rowspan='2'><b>N&#186;</b> {_v(c, "numero")}</td>
      </tr>
      <tr><th>ART</th><td class='v'>{_v(c, "art")}</td></tr>
      {_fila("LESION", _v(c, "lesion"))}
      {_fila("PRESTADOR", _v(c, "prestador"))}
      {_fila("SUELDO", _v(c, "sueldo"))}
      {_fila("EMPLEADOR", _v(c, "empleador"))}
      {_fila("ACTIVIDAD LABORAL", _v(c, "actividad_laboral"))}
      {_fila("ANTIGÜEDAD LABORAL", _v(c, "antiguedad_laboral"))}
      {_fila("CAPACIDAD RESTANTE", _v(c, "capacidad_restante"))}
    </table>
    """


def _bloque_siniestro(c: Cliente) -> str:
    return f"""
    <table>
      {_fila("TIPO DE SINIESTRO", _v(c, "tipo_siniestro"))}
      {_fila("DESCRIPCION SINIESTRO", _v(c, "descripcion_siniestro"), clase="alto")}
      {_fila("LUGAR / HORA SINIESTRO", _v(c, "lugar_hora_siniestro"))}
      {_fila("MIEMBRO HABIL", _v(c, "miembro_habil"))}
      {_fila("OPERACION", _v(c, "operacion"))}
      {_fila("INTERNACION", _v(c, "internacion"))}
      {_fila_larga("SESIONES REHABILITACION", _v(c, "sesiones_rehabilitacion"))}
    </table>
    """


def _bloque_estado(c: Cliente) -> str:
    """La grilla de tres columnas de abajo: abogado / clínica / recomendado, con la fila de
    vistas médicas y la fecha de homologación."""
    # En la planilla la celda "SIN - CON" tiene adentro "SECUELAS": son el mismo dato, así que
    # se muestra el campo Secuelas y, si está vacío, el de Sin/Con.
    sin_con = (c.secuelas or "").strip() or (c.sin_con or "").strip()
    return f"""
    <table>
      <colgroup>
        <col style='width:17%'><col style='width:19%'>
        <col style='width:17%'><col style='width:15%'>
        <col style='width:14%'><col style='width:18%'>
      </colgroup>
      <tr>
        <th>ATENCION ABOGADO</th><td class='v'>{_v(c, "atencion_abogado")}</td>
        <th>HIST. CLINICA</th><td class='v'>{_v(c, "hist_clinica")}</td>
        <th>RECOMENDADO</th><td class='v'>{_v(c, "recomendado")}</td>
      </tr>
      <tr>
        <th>POSIBLE ALTA</th><td class='v'>{_v(c, "posible_alta")}</td>
        <th>ALTA MEDICA</th><td class='v'>{_v(c, "alta_medica")}</td>
        <th>SIN - CON</th><td class='v'>{_v_x(sin_con)}</td>
      </tr>
      <tr>
        <th>VISTA MEDICA</th>
        <td class='v' colspan='3'>{_v(c, "vista_medica")}
          <span class='mini'></span><span class='mini'></span><span class='mini'></span>
        </td>
        <th>FECHA HOMOLOGACION</th>
        <td class='v'>{_v(c, "fecha_homologacion")}</td>
      </tr>
    </table>
    """


def _bloque_eventos(c: Cliente) -> str:
    if not c.eventos:
        return ""
    filas = "".join(
        f"<tr><th>{_v_x(e.fecha)}</th><td class='v'>{_v_x(e.descripcion)}</td></tr>"
        for e in c.eventos
    )
    return f"""
    <table>
      <colgroup><col style='width:22%'><col style='width:78%'></colgroup>
      <tr><th>FECHA</th><th class='v' align='center'>DESCRIPCION</th></tr>
      {filas}
    </table>
    """


def _v_x(valor: Optional[str]) -> str:
    return html.escape(str(valor).strip()) if valor and str(valor).strip() else Vacio


def _bloque_notas(c: Cliente) -> str:
    if not (c.notas or "").strip():
        return ""
    return f"<table><tr><th>NOTAS</th><td class='v'>{_v(c, 'notas')}</td></tr></table>"


def cliente_html(c: Cliente) -> str:
    """El HTML de un cliente, con el diseño de la planilla."""
    return (
        "<div class='hoja'>"
        + _bloque_encabezado(c)
        + _bloque_personales(c)
        + _bloque_accidente(c)
        + _bloque_siniestro(c)
        + _bloque_estado(c)
        + _bloque_eventos(c)
        + _bloque_notas(c)
        + "</div>"
    )


def _abrir(contenido: str, titulo: str) -> None:
    paginas = (
        "<!doctype html><html lang='es'><head><meta charset='utf-8'>"
        f"<title>{html.escape(titulo)}</title><style>{_ESTILO}</style></head><body>"
        "<button onclick='window.print()'>Imprimir</button>"
        f"{contenido}</body></html>"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(paginas)
        path = f.name
    webbrowser.open(f"file://{path}")


def imprimir_cliente(cliente: Cliente) -> None:
    _abrir(cliente_html(cliente), cliente.nombre_completo or "Cliente")


def imprimir_varios(clientes: Iterable[Cliente]) -> None:
    clientes = list(clientes)
    if clientes:
        _abrir("".join(cliente_html(c) for c in clientes), "Clientes")