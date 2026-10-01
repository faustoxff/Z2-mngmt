"""Generación del documento Word: completa la plantilla `plantilla/formulario.docx` (la planilla
de apertura de carpeta + el convenio de honorarios + la carta de solicitud de historia clínica)
con los datos de un cliente y lo guarda como .docx.

La idea es que el documento quede EXACTAMENTE igual que la plantilla — misma estética, mismo
letrado, mismo formato —: por eso no se arma un documento nuevo sino que se completan celdas y
párrafos de la plantilla original. Al completarlas se respeta el formato del texto que ya estaba
(la primera run de cada celda conserva su fuente, tamaño y color).

Requiere `python-docx` (ver requirements.txt).
"""
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import config
from models import Cliente

RAIZ = Path(__file__).resolve().parent
PLANTILLA = RAIZ / "plantilla" / "formulario.docx"

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


class DocumentoError(Exception):
    """No se pudo generar el documento. El mensaje se muestra directo en un messagebox."""


def _requerir_docx():
    try:
        from docx import Document
    except ImportError as exc:
        raise DocumentoError(
            "Falta instalar la librería python-docx:\n\npip install python-docx"
        ) from exc
    return Document


# ---------- texto: reemplazar sin perder el formato ----------


def _nodos_texto(parrafo):
    """Los nodos <w:t> del párrafo, en orden.

    OJO: no se puede usar `parrafo.runs`, porque ahí falta el texto que está dentro de
    hyperlinks, campos o etiquetas inteligentes. Con esa lista incompleta, las posiciones del
    texto no coinciden con las del párrafo real y el reemplazo cae en cualquier lado (pasó:
    al completar el ART de la carta se pisó la cláusula PRIMERA del convenio). Con los nodos
    <w:t> el texto concatenado sí es el texto real del párrafo."""
    from docx.oxml.ns import qn  # import local: _nodos_texto corre recién al completar algo

    return parrafo._p.findall(".//" + qn("w:t"))


def _texto_parrafo(parrafo) -> str:
    return "".join(n.text or "" for n in _nodos_texto(parrafo))


def _escribir_nodo(nodo, texto: str) -> None:
    nodo.text = texto
    # Sin esto, un texto con espacio al principio o al final se pierde al abrir en Word.
    if texto != texto.strip():
        nodo.set(qn("xml:space"), "preserve")


def _reemplazar(parrafo, patron: str, nuevo) -> bool:
    """Reemplaza en un párrafo lo que matchea `patron` (regex) por `nuevo`, conservando el
    formato de cada parte: el texto nuevo queda en el nodo donde arrancaba el match, y de los
    nodos que quedan parcialmente cubiertos se conserva solo la parte de afuera."""
    nodos = _nodos_texto(parrafo)
    texto = "".join(n.text or "" for n in nodos)
    m = re.search(patron, texto)
    if not m:
        return False
    inicio, fin = m.span()
    reemplazo = nuevo(m) if callable(nuevo) else nuevo

    cursor = 0
    escrito = False
    for nodo in nodos:
        t = nodo.text or ""
        n_ini, n_fin = cursor, cursor + len(t)
        cursor = n_fin
        if n_fin <= inicio or n_ini >= fin:
            continue  # este nodo está fuera del match: no se toca
        antes = t[: max(0, inicio - n_ini)]
        despues = t[max(0, fin - n_ini) :] if fin < n_fin else ""
        if not escrito:
            _escribir_nodo(nodo, antes + reemplazo + despues)
            escrito = True
        else:
            _escribir_nodo(nodo, antes + despues)
    return True


def _set_celda(celda, valor: str) -> None:
    """Escribe en una celda conservando el formato: se reutiliza la primera run (que es la que
    tiene la fuente/tamaño del placeholder) y se vacían las demás."""
    valor = "" if valor is None else str(valor)
    if celda.paragraphs:
        primero = celda.paragraphs[0]
        if primero.runs:
            primero.runs[0].text = valor
            for r in primero.runs[1:]:
                r.text = ""
        else:
            primero.add_run(valor)
        for p in celda.paragraphs[1:]:
            for r in p.runs:
                r.text = ""
    else:
        celda.text = valor


def _unicas(fila):
    """Las celdas 'reales' de una fila. python-docx devuelve una celda repetida por cada
    columna que cubre un merge, así que hay que quedarse con la primera de cada grupo."""
    vistas, vistas_ids = [], set()
    for celda in fila.cells:
        if id(celda._tc) in vistas_ids:
            continue
        vistas_ids.add(id(celda._tc))
        vistas.append(celda)
    return vistas


def _buscar_fila(tabla, etiqueta: str):
    """La fila cuya primera celda es la etiqueta dada (ignorando tildes/mayúsculas y espacios)."""
    def norm(s):
        return re.sub(r"\s+", " ", s.strip().upper())

    objetivo = norm(etiqueta)
    for fila in tabla.rows:
        celdas = _unicas(fila)
        for celda in celdas:
            if norm(celda.text) == objetivo:
                return celdas
    return None


def _indice_de(celdas, etiqueta: str):
    """Posición de la etiqueta dentro de las celdas de una fila, o None si no está."""
    objetivo = etiqueta.strip().upper()
    for i, celda in enumerate(celdas):
        if celda.text.strip().upper() == objetivo:
            return i
    return None


def _fila_por_etiqueta(tabla, etiqueta: str):
    """(número de fila, celdas) de la fila que tiene la etiqueta en alguna de sus celdas."""
    for n, fila in enumerate(tabla.rows):
        celdas = _unicas(fila)
        if _indice_de(celdas, etiqueta) is not None:
            return n, celdas
    return None, None


# ---------- la tabla de la planilla ----------


def _llenar_tabla(tabla, c: Cliente) -> None:
    def por_etiqueta(etiqueta: str, valor: str, con_dato_previo: bool = False) -> None:
        """Escribe el valor en la celda siguiente a la etiqueta; si el documento de ejemplo ya
        traía un dato en esa celda, se reemplaza ahí mismo."""
        celdas = _buscar_fila(tabla, etiqueta)
        if not celdas:
            return
        i = next(
            (k for k, celda in enumerate(celdas) if celda.text.strip().upper() == etiqueta.strip().upper()),
            None,
        )
        if i is None or i + 1 >= len(celdas):
            return
        _set_celda(celdas[i + 1], valor)

    # Encabezado: apellido (fila 0), nombre y categoría (fila 1).
    filas = list(tabla.rows)
    _set_celda(_unicas(filas[0])[0], (c.apellido or "").upper())
    _set_celda(_unicas(filas[0])[-1], "")  # la celda de la derecha del encabezado va vacía
    cab = _unicas(filas[1])
    if len(cab) >= 3:
        _set_celda(cab[1], (c.nombre or "").upper())
        _set_celda(cab[2], f"CAT {c.categoria}".strip())

    # Datos personales: dos pares por fila.
    por_etiqueta("TELEFONO", c.telefono)
    por_etiqueta("CONTACTO ALT.", c.contacto_alt)
    por_etiqueta("DNI", c.dni)
    por_etiqueta("CUIL", c.cuil)
    por_etiqueta("FECHA DE NACIMIENTO", c.fecha_nacimiento)
    por_etiqueta("EDAD", c.edad)
    por_etiqueta("DOMICILIO", c.domicilio)
    por_etiqueta("CIUDAD", c.ciudad)
    por_etiqueta("DOMICILIO DNI", c.domicilio_dni)
    por_etiqueta("CIUDAD DOM. DNI", c.ciudad_dom_dni)
    por_etiqueta("COMISION MEDICA", c.comision_medica)
    por_etiqueta("MAIL", c.mail)
    por_etiqueta("FECHA CREACION CARPETA", c.fecha_creacion_carpeta)
    por_etiqueta("INSTAGRAM", c.instagram)

    # Accidente (la celda de la derecha es el número de expediente).
    por_etiqueta("FECHA ACCIDENTE", c.fecha_accidente)
    celdas = _buscar_fila(tabla, "FECHA ACCIDENTE")
    if celdas and len(celdas) >= 3:
        _set_celda(celdas[2], c.numero)
    por_etiqueta("ART", c.art)
    por_etiqueta("LESION", c.lesion)
    por_etiqueta("PRESTADOR", c.prestador)
    por_etiqueta("SUELDO", c.sueldo)
    por_etiqueta("EMPLEADOR", c.empleador)
    por_etiqueta("ACTIVIDAD LABORAL", c.actividad_laboral)
    por_etiqueta("ANTIGÜEDAD LABORAL", c.antiguedad_laboral)
    por_etiqueta("CAPACIDAD RESTANTE", c.capacidad_restante)

    # Siniestro.
    por_etiqueta("TIPO DE SINIESTRO", c.tipo_siniestro)
    por_etiqueta("DESCRIPCION SINIESTRO", c.descripcion_siniestro)
    por_etiqueta("LUGAR / HORA SINIESTRO", c.lugar_hora_siniestro)
    por_etiqueta("MIEMBRO HABIL", c.miembro_habil)
    por_etiqueta("OPERACIÓN", c.operacion)
    por_etiqueta("INTERNACION", c.internacion)
    por_etiqueta("SESIONES REHABILITACION", c.sesiones_rehabilitacion)

    # --- Bloque de abajo: acá el valor NO siempre está al lado de la etiqueta ---
    # "ATENCION ABOGADO" y "RECOMENDADO" tienen la etiqueta en una fila y el dato en la fila de
    # abajo (misma columna), mientras que "HIST. CLINICA" sí tiene la celda de valor al lado.
    n_abogado, fila = _fila_por_etiqueta(tabla, "ATENCION ABOGADO")
    if fila:
        abajo = _unicas(list(tabla.rows)[n_abogado + 1]) if n_abogado + 1 < len(filas) else []
        # La primera celda de la fila de abajo es el dato del abogado (en la plantilla venía el
        # del ejemplo), y la última es el de "RECOMENDADO".
        if abajo:
            _set_celda(abajo[0], c.atencion_abogado)
            _set_celda(abajo[-1], c.recomendado)
        i_hist = _indice_de(fila, "HIST. CLINICA")
        if i_hist is not None and i_hist + 1 < len(fila):
            _set_celda(fila[i_hist + 1], c.hist_clinica)

    # POSIBLE ALTA / ALTA MEDICA: etiqueta y valor en la misma fila.
    por_etiqueta("POSIBLE ALTA", c.posible_alta)
    por_etiqueta("ALTA MEDICA", c.alta_medica)

    # VISTA MEDICA (celdas chicas de al lado) y FECHA HOMOLOGACION (fila de abajo).
    por_etiqueta("VISTA MEDICA", c.vista_medica)
    n_hom, _fila_hom = _fila_por_etiqueta(tabla, "FECHA HOMOLOGACION")
    if n_hom is not None and n_hom + 1 < len(filas):
        siguiente = _unicas(list(tabla.rows)[n_hom + 1])
        if siguiente:
            _set_celda(siguiente[0], c.fecha_homologacion)

    # Tabla Fecha / Descripción: se limpian todas las filas y se escriben los eventos.
    filas_eventos = [f for f in filas if len(_unicas(f)) >= 2]
    encabezado = next(
        (i for i, f in enumerate(filas_eventos) if _unicas(f)[0].text.strip().upper() == "FECHA"), None
    )
    if encabezado is not None:
        for fila in filas_eventos[encabezado + 1 :]:
            celdas = _unicas(fila)
            _set_celda(celdas[0], "")
            _set_celda(celdas[1], "")
        for evento, fila in zip(c.eventos, filas_eventos[encabezado + 1 :]):
            celdas = _unicas(fila)
            _set_celda(celdas[0], evento.fecha)
            _set_celda(celdas[1], evento.descripcion)


# ---------- el convenio y la carta ----------


def _llenar_parrafos(doc, c: Cliente) -> int:
    """Completa el convenio y la carta. Devuelve cuántos campos REF se actualizaron."""
    hoy = datetime.now()
    hoy_palabras = f"{hoy.day} de {MESES[hoy.month - 1]} de {hoy.year}"

    # ---- Campos REF: el corazón de que el documento quede coherente ----
    # La plantilla no repite los datos a mano: el convenio y la carta los muestran con campos
    # REF que apuntan a marcadores (bookmarks) ubicados en la PLANILLA. Entonces lo correcto NO
    # es escribir el nombre del cliente en el convenio, sino:
    #   1) llenar la planilla (lo hace _llenar_tabla, y de ahí toman los marcadores), y
    #   2) actualizar el texto que Word tiene guardado como resultado de cada campo, para que
    #      quede bien tanto si el programa refresca los campos al abrir como si no lo hace.
    # Si se hace mal (escribir el dato al lado del campo, o vaciar su resultado), el valor
    # aparece duplicado: "ART: SMGSMG".
    valores = {
        "APELLIDO": (c.apellido or "").upper(),
        "NOMBRES": (c.nombre or "").upper(),
        "DNI": c.dni,
        "DOMICILIO": c.domicilio,
        "CIUDAD": (c.ciudad or "").upper(),
        "FECHACARPETA": c.fecha_creacion_carpeta,
        "ACCIDENTE": c.fecha_accidente,
        "ART": c.art,
        "CLINICA": (c.prestador or "").upper(),
        "OPERACION": c.operacion,
        "INTERNACION": c.internacion,
    }
    actualizados = 0
    for parrafo in doc.paragraphs:
        actualizados += _actualizar_campos_ref(parrafo, valores)
    for tabla in doc.tables:
        for fila in tabla.rows:
            for celda in fila.cells:
                for parrafo in celda.paragraphs:
                    actualizados += _actualizar_campos_ref(parrafo, valores)

    # Estas dos líneas NO son campos: son texto común, así que se reemplazan el párrafo.
    reemplazos = [
        (
            r"^MOTIVO:.*$",
            f"MOTIVO: {c.notas or 'interconsulta con mi médico de cabecera y letrado patrocinante.'}",
        ),
        (r"^Saludos atentamente,.*$", f"Saludos atentamente, Mar del Plata, {hoy_palabras}"),
    ]
    for patron, nuevo_texto in reemplazos:
        for parrafo in doc.paragraphs:
            if re.search(patron, _texto_parrafo(parrafo)):
                _reemplazar(parrafo, patron, nuevo_texto)
                break

    return actualizados


def _actualizar_campos_ref(parrafo, valores: dict) -> int:
    """Actualiza el texto guardado como resultado de los campos REF del párrafo.

    Un campo REF en el XML es una secuencia de runs: "begin" (fldChar), la instrucción
    (instrText, del tipo " REF ART " + chr(92) + "* MERGEFORMAT "), "separate", el RESULTADO
    (lo que se ve hasta que el programa refresca el campo) y "end". Lo que hay que cambiar es
    el resultado, que es lo único que se ve sin refrescar.

    Devuelve -1 si el párrafo tiene un campo REF que no sabemos completar (para avisar en vez de
    dejar pegado un dato del cliente de ejemplo)."""
    from docx.oxml.ns import qn

    actualizados = 0
    runs = parrafo._p.findall(qn("w:r"))
    i = 0
    while i < len(runs):
        fld = runs[i].find(qn("w:fldChar"))
        if fld is None or fld.get(qn("w:fldCharType")) != "begin":
            i += 1
            continue

        # Recorrer hasta el cierre del campo, juntando la instrucción.
        j, instr, cierre = i + 1, "", None
        while j < len(runs):
            instr_txt = runs[j].find(qn("w:instrText"))
            if instr_txt is not None:
                instr += instr_txt.text or ""
            f = runs[j].find(qn("w:fldChar"))
            if f is not None and f.get(qn("w:fldCharType")) == "end":
                cierre = j
                break
            j += 1
        if cierre is None:
            break

        m = re.search(r"REF\s+(\S+)", instr)
        if not m:
            i = cierre + 1
            continue
        nombre = m.group(1)
        if nombre not in valores:
            return -1  # REF desconocido: mejor no tocarlo
        valor = valores[nombre] or ""

        # El resultado es lo que está entre "separate" y "end".
        primero_resultado = None
        for k in range(i, cierre):
            f = runs[k].find(qn("w:fldChar"))
            if f is not None and f.get(qn("w:fldCharType")) == "separate":
                primero_resultado = k + 1
                break
        if primero_resultado is None:
            i = cierre + 1
            continue

        escrito = False
        for k in range(primero_resultado, cierre):
            for nodo in runs[k].findall(qn("w:t")):
                if not escrito:
                    _escribir_nodo(nodo, valor)
                    escrito = True
                else:
                    _escribir_nodo(nodo, "")  # runs de más del resultado: vacíos
        if not escrito:
            # El campo no tenía run de resultado: se le agrega uno antes del cierre.
            from docx.text.run import Run

            nuevo_run = parrafo._p.makeelement(qn("w:r"), {})
            runs[cierre].addprevious(nuevo_run)
            Run(nuevo_run, parrafo).text = valor
        actualizados += 1
        i = cierre + 1
    return actualizados


# ---------- archivo ----------


def _carpeta_destino() -> Path:
    carpeta = config.obtener_carpeta_documentos()
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def generar_documento(cliente: Cliente) -> Path:
    """Completa la plantilla con los datos del cliente y devuelve la ruta del .docx generado."""
    Document = _requerir_docx()
    if not PLANTILLA.exists():
        raise DocumentoError(
            f"No se encuentra la plantilla del formulario:\n{PLANTILLA}"
        )
    try:
        doc = Document(str(PLANTILLA))
    except Exception as exc:  # noqa: BLE001 - plantilla corrupta o python-docx incompatible
        raise DocumentoError(f"No se pudo abrir la plantilla:\n{exc}") from exc

    if not doc.tables:
        raise DocumentoError("La plantilla no tiene la tabla de la planilla.")
    _llenar_tabla(doc.tables[0], cliente)
    _llenar_parrafos(doc, cliente)

    nombre = f"{cliente.apellido or 'Cliente'} {cliente.nombre or cliente.id}".strip()
    limpio = re.sub(r'[\\/:*?"<>|]+', "-", nombre).strip()
    ruta = _carpeta_destino() / f"{limpio}.docx"
    try:
        doc.save(str(ruta))
    except OSError as exc:
        raise DocumentoError(f"No se pudo guardar el documento:\n{exc}") from exc
    return ruta


def abrir_documento(ruta: Path) -> None:
    """Abre el .docx con el programa que el sistema tenga por defecto (Word, LibreOffice...)."""
    ruta = Path(ruta)
    if sys.platform == "win32":
        import os

        os.startfile(str(ruta))  # noqa: S606 - es lo que hace el sistema con un doble clic
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(ruta)])
        return
    # Linux: el que sea xdg-open, si está; si no, se avisa con la ruta para abrirlo a mano.
    for ejecutable in ("xdg-open", "gio"):
        if shutil.which(ejecutable):
            args = [ejecutable, "open", str(ruta)] if ejecutable == "gio" else [ejecutable, str(ruta)]
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return