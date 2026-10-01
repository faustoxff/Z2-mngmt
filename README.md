# Clientes en Neon

App de escritorio para **cargar clientes que se guardan directamente en Neon (Postgres en la
nube)**. No hay base de datos local: Neon es la única fuente de datos.

Misma tecnología que la app de la PC de tu papá (Python + Tkinter), pero con los campos de la
planilla de siniestros de ART y con impresión.

## Stack

- Python 3 + Tkinter (stdlib, sin dependencias extra para la interfaz)
- Neon (Postgres) vía `psycopg2-binary`

## Correr en desarrollo

```bash
python3 -m venv .venv
source .venv/bin/activate          # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Configurar la conexión a Neon

Botón **"Conexión"** (arriba a la derecha) → se pega la cadena de conexión del panel de Neon →
**Probar** → **Guardar**. La cadena se ve así:

```
postgresql://usuario:password@ep-xxx-pooler.region.aws.neon.tech/neondb?sslmode=require
```

Queda guardada solo en esta computadora:

- Windows: `%APPDATA%\ClientesNeon\config.json`
- Linux/Mac: `~/.local/share/ClientesNeon/config.json`

También se puede dejar en la variable de entorno `NEON_DATABASE_URL` (tiene prioridad sobre el
archivo), que es lo cómodo para empaquetar o para correr en CI.

## Los campos

**Todos los campos están definidos en un solo lugar: `campos.py`.** De ahí salen las columnas de
la tabla en Neon, los campos del formulario y las filas de la impresión. Para agregar un campo
nuevo se agrega **una línea** en `campos.py` y la app lo crea sola en la base (agrega la columna
con `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`) y lo muestra en el formulario.

Secciones, con los nombres de la planilla:

| Sección | Campos |
| --- | --- |
| Cliente (arriba) | Apellido, Nombre |
| Datos | Categoría, DNI, CUIL, Fecha de nacimiento, Edad, Teléfono, Contacto alternativo, Mail, Instagram |
| Domicilio | Domicilio, Ciudad, Domicilio DNI, Ciudad dom. DNI |
| Carpeta | N°, Comisión médica, Fecha creación carpeta, Notas |
| Accidente | Fecha accidente, ART, Lesión, Prestador |
| Laboral | Empleador, Actividad laboral, Antigüedad laboral, Sueldo, Capacidad restante |
| Siniestro | Tipo de siniestro, Descripción del siniestro, Lugar / hora del siniestro, Miembro hábil, Operación, Internación, Sesiones de rehabilitación |
| Estado | Atención abogado, Recomendado por, Posible alta, Hist. clínica, Alta médica, Sin / Con, Secuelas, Vista médica, Fecha homologación |
| Fecha / Descripción | filas múltiples (botón "+ Agregar fila") |

Además, solo de la app (no están en la planilla): `fecha_alta` y `fecha_actualizacion`
(automáticas) y `contacto_normalizado` (el teléfono sin espacios, guiones ni paréntesis, que
sirve para buscar duplicados).

**Fechas**: en pantalla se escriben y se ven como `DD/MM/AAAA` (la de la planilla) y en Neon se
guardan como `AAAA-MM-DD`, que es lo que permite ordenarlas y filtrarlas bien con SQL
(`fechas.py` hace la conversión). Las que se escriban mal se guardan tal cual, para no perder
información.

## Qué hace la app

- **Nuevo cliente**: abre el formulario con todos los campos, en secciones, con scroll.
  Apellido y nombre van arriba, en grande.
- **Aviso de duplicados**: al guardar, busca por teléfono normalizado y, si no encuentra, por
  apellido + nombre (sin tildes, sin distinguir mayúsculas). Si hay coincidencia, muestra
  cuáles son y deja decidir con un sí/no — no bloquea la carga.
- **Listado** de todos los clientes, con buscador por apellido, nombre, teléfono o DNI.
  Doble clic = editar, Supr = borrar.
- **Imprimir**: abre el cliente en el navegador con el mismo diseño de la planilla, listo para
  imprimir o guardar como PDF. Las celdas vacías se imprimen con un guion, para que se note qué
  falta completar.
- **Documento**: completa la plantilla de Word y lo abre con el programa de Word. Ver abajo.

Sin internet o sin conexión configurada, la app **igual abre** y avisa — no se cae.

## El botón "Documento" (el .docx del expediente)

Aparte de la planilla, la plantilla `plantilla/formulario.docx` (copia de
`Descargas/FORMULARIOS APERTURA CARPETA.docx`) trae las otras dos piezas del expediente:

1. la **planilla** de apertura de carpeta (la tabla),
2. el **CONVENIO DE HONORARIOS** del estudio,
3. la carta de **SOLICITO HISTORIA CLINICA** al prestador.

El botón "Documento" abre la plantilla, completa la planilla con los datos del cliente,
actualiza los campos REF del convenio y de la carta, y guarda el resultado como
`APELLIDO NOMBRE.docx` en la carpeta de documentos (por defecto `~/Clientes`, se cambia con
`config.guardar_carpeta_documentos()`), abriendo el archivo con el programa que el sistema
tenga por defecto.

La plantilla **no se modifica nunca**: se abre y se guarda en otro archivo.

### Ojo con los campos REF de Word

En el convenio y en la carta los datos del cliente no están escritos: son **campos REF** que
apuntan a marcadores (`APELLIDO`, `NOMBRES`, `DNI`, `DOMICILIO`, `CIUDAD`, `FECHACARPETA`,
`ACCIDENTE`, `ART`, `CLINICA`, `OPERACION`, `INTERNACION`) ubicados en la planilla. Por eso:

- El nombre del Cliente, su DNI, su domicilio, la fecha de firma del convenio y el motivo del
  siniestro se actualizan **solos** al llenar la planilla.
- `documento._actualizar_campos_ref` actualiza además el **texto guardado** como resultado de
  cada campo, para que el documento quede bien aunque el programa no refresque los campos al
  abrirlo (Word los refresca al imprimir, pero no siempre al abrir).

Esto importa: si en vez de actualizar el resultado del campo se escribe el dato "al lado" o se
vacía el resultado, el valor aparece duplicado (`ART: SMGSMG`), porque el programa vuelve a
resolver el campo y lo pone al lado del texto escrito.

## El esquema en Neon

`clientes` (una fila por cliente, columnas = los campos de `campos.py` + las 3 de control) y
`cliente_eventos` (las filas de Fecha / Descripción, con `ON DELETE CASCADE`: si se borra un
cliente, sus eventos se van con él). Las crea sola `neon_db.init_db()`.

## Cómo se relaciona con la app de tu papá (futuro)

Esta app es la **única que escribe** en la tabla `clientes`. La app vieja (`Papa app local`,
que sigue con su SQLite local) no comparte ni sube sus datos: lo único que va a hacer es
**leer** esta tabla para chequear duplicados y avisarle antes de cargar uno que ya existe acá.

Para eso `neon_db.py` expone `buscar_duplicados(nombre, telefono)`, que ya devuelve los
clientes coincidentes usando la misma normalización que usa esta app. La app vieja va a
encontrar los clientes por apellido y nombre (columnas `apellido` y `nombre`) o por teléfono
(columna `telefono` / `contacto_normalizado`).