from flask import Flask, jsonify, request, render_template, redirect, url_for, flash, session, send_file
import os
import csv
from datetime import datetime, date
from flask_cors import CORS
import pymysql
import os
import uuid
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta, date
from functools import wraps
import random
import string
from urllib.parse import urljoin
import urllib.parse
import importlib.util
from jinja2 import ChoiceLoader, FileSystemLoader
app = Flask(__name__)
import os
import os
import uuid
from werkzeug.utils import secure_filename
from flask import url_for, flash, redirect, render_template, request

def get_connection():
    if os.environ.get('RENDER'):
        import psycopg2
        from psycopg2.extras import RealDictCursor
        return psycopg2.connect(
            host=os.environ.get('DB_HOST'),
            database=os.environ.get('DB_NAME'),
            user=os.environ.get('DB_USER'),
            password=os.environ.get('DB_PASSWORD'),
            port=os.environ.get('DB_PORT'),
            cursor_factory=RealDictCursor
        )
    else:
        return pymysql.connect(
            host='127.0.0.1',
            user='root',
            password='',
            database='ginnasio',
            cursorclass=pymysql.cursors.DictCursor
        )

obtener_conexion = get_connection





# --- ConfiguraciÃ³n de uploads (pegar despuÃ©s de crear app = Flask(...)) ---
ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB mÃ¡ximo
# -------------------------------------------------------------------------

# Carpeta donde se guardarÃ¡n las fotos
UPLOAD_FOLDER = os.path.join('static', 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
   
   
app.secret_key = 'gimnasio_secret_key'
CORS(app)

_BASE_DIR = os.path.abspath(os.path.dirname(__file__))
_CMP_PATH = os.path.join(_BASE_DIR, 'gimnasio_app', 'comprobantes_module.py')
try:
    _spec = importlib.util.spec_from_file_location('comprobantes_module', _CMP_PATH)
    comprobantes_module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(comprobantes_module)
    crear_comprobante = getattr(comprobantes_module, 'crear_comprobante', None)
    active_gym_id = getattr(comprobantes_module, 'active_gym_id', lambda: 1)
    comprobantes_module.wire(app, obtener_conexion)
    app.jinja_loader = ChoiceLoader([
        app.jinja_loader,
        FileSystemLoader(os.path.join(_BASE_DIR, 'templates'))
    ])
except Exception:
    crear_comprobante = None
    active_gym_id = lambda: 1

# === Formato y sanitizaciÃ³n de moneda COP ===
def parse_cop(value):
    s = str(value or '').strip()
    # Remover prefijos y sÃ­mbolos
    s = s.replace('COP', '').replace('cop', '').replace('$', '')
    # Quitar espacios y separadores de miles
    s = s.replace(' ', '').replace('.', '')
    # Usar punto como separador decimal
    s = s.replace(',', '.')
    try:
        return float(s)
    except Exception:
        return 0.0

def format_cop(value):
    try:
        n = float(value or 0)
    except Exception:
        n = 0
    # Formatear con separador de miles como punto y sin decimales
    formatted = '{:,.0f}'.format(n).replace(',', '.')
    return f'COP ${formatted}'

# Registrar filtro para usar en Jinja: {{ monto|cop }}
app.jinja_env.filters['cop'] = format_cop

# ConfiguraciÃ³n de uploads
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# Utilidad para construir URL pÃºblica absoluta (evita 127.0.0.1)
# Generadores aleatorios para NIT y resoluciÃ³n DIAN
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def active_gym_id():
    try:
        return int(session.get('id_gimnasio') or 1)
    except Exception:
        return 1

def _has_column(conn, table, column):
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s",
            (table, column)
        )
        return cursor.fetchone() is not None
def _table_exists(conn, table):
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
            (table,)
        )
        return cursor.fetchone() is not None

def _get_gym(conn, id_gym):
    with conn.cursor() as cursor:
        cursor.execute("SELECT id_gimnasio, nombre, nit, direccion, telefono, ciudad, correo, logo, texto_legal, consecutivo_comprobante FROM gimnasios WHERE id_gimnasio=%s", (id_gym,))
        return cursor.fetchone()

def _inc_consecutivo(conn, id_gym):
    with conn.cursor() as cursor:
        cursor.execute("SELECT consecutivo_comprobante FROM gimnasios WHERE id_gimnasio=%s", (id_gym,))
        row = cursor.fetchone()
        actual = int(row['consecutivo_comprobante'] or 0) if row else 0
        nuevo = actual + 1
        cursor.execute("UPDATE gimnasios SET consecutivo_comprobante=%s WHERE id_gimnasio=%s", (nuevo, id_gym))
    conn.commit()
    return nuevo

def _pdf_path_for(id_gym, numero):
    base_dir = os.path.abspath(os.path.dirname(__file__))
    now = datetime.now()
    carpeta = os.path.join(base_dir, 'static', 'comprobantes', str(id_gym), f"{now.year}", f"{now.month:02d}")
    os.makedirs(carpeta, exist_ok=True)
    return os.path.join(carpeta, f"{numero}.pdf")

def _write_simple_pdf(path, lines):
    content_lines = []
    y = 780
    for ln in lines:
        safe = str(ln).replace('(', '\\(').replace(')', '\\)')
        content_lines.append(f"BT /F1 12 Tf 50 {y} Td ({safe}) Tj ET")
        y -= 18
    stream = "\n".join(content_lines)
    objects = []
    objects.append("1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append("2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objects.append("3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>endobj\n")
    objects.append("4 0 obj<< /Type /Font /Subtype /Type1 /Name /F1 /BaseFont /Helvetica >>endobj\n")
    objects.append(f"5 0 obj<< /Length {len(stream)} >>stream\n{stream}\nendstream endobj\n")
    xref = []
    pdf = "%PDF-1.4\n"
    offset = len(pdf)
    for obj in objects:
        xref.append(offset)
        pdf += obj
        offset = len(pdf)
    xref_pos = len(pdf)
    pdf += f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n"
    for off in xref:
        pdf += f"{off:010d} 00000 n \n"
    pdf += f"trailer<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF"
    with open(path, 'wb') as f:
        f.write(pdf.encode('latin-1', 'ignore'))

def crear_comprobante_pdf(conn, id_gym, tipo, id_pago, id_producto, cliente, descripcion, precio, cantidad):
    gym = _get_gym(conn, id_gym)
    consecutivo = _inc_consecutivo(conn, id_gym)
    numero = f"CP-{consecutivo:06d}"
    total = float(precio) * int(cantidad)
    ruta_pdf = _pdf_path_for(id_gym, numero)
    encabezado = [
        f"{gym['nombre']} - NIT {gym['nit']}",
        f"{gym['direccion']} - {gym['ciudad']} - Tel {gym['telefono']}",
        f"{gym['correo']}",
    ]
    cuerpo = [
        f"Comprobante: {numero}",
        f"Tipo: {tipo}",
        f"Cliente: {cliente}",
        f"Descripción: {descripcion}",
        f"Precio: {precio}",
        f"Cantidad: {cantidad}",
        f"Total: {total}",
        f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"{gym['texto_legal'] or ''}",
        "Comprobante interno — No es factura DIAN.",
    ]
    _write_simple_pdf(ruta_pdf, encabezado + [""] + cuerpo)
    web_ruta = '/' + os.path.relpath(ruta_pdf, os.path.abspath(os.path.dirname(__file__))).replace('\\','/')
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO comprobantes(id_gimnasio,id_pago,id_producto,tipo,descripcion,ruta_pdf,total,fecha_generado)
            VALUES(%s,%s,%s,%s,%s,%s,%s,NOW())
            """,
            (id_gym, id_pago, id_producto, tipo, descripcion, web_ruta, total)
        )
        id_comp = cursor.lastrowid
    conn.commit()
    return id_comp, numero, ruta_pdf

def _ensure_cfg(conn, id_gym):
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM comprobante_config WHERE id_gimnasio=%s", (id_gym,))
        row = cursor.fetchone()
        if not row:
            cursor.execute(
                """
                INSERT INTO comprobante_config(id_gimnasio,nombre_comprobante,logo_url,color_titulo,color_texto,texto_pie,mostrar_qr)
                VALUES(%s,%s,%s,%s,%s,%s,%s)
                """,
                (id_gym, 'Comprobante de pago', '', '#1E3A8A', '#0f172a', 'Gracias por preferirnos', 1)
            )
            conn.commit()
            cursor.execute("SELECT * FROM comprobante_config WHERE id_gimnasio=%s", (id_gym,))
            row = cursor.fetchone()
    return row

def _next_num(conn, id_gym):
    with conn.cursor() as cursor:
        cursor.execute("SELECT consecutivo FROM consecutivos_comprobantes WHERE id_gimnasio=%s", (id_gym,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("INSERT INTO consecutivos_comprobantes(id_gimnasio, consecutivo) VALUES(%s, %s)", (id_gym, 1))
            conn.commit()
            num = 1
        else:
            num = int(row['consecutivo']) + 1
            cursor.execute("UPDATE consecutivos_comprobantes SET consecutivo=%s WHERE id_gimnasio=%s", (num, id_gym))
            conn.commit()
    return f"CP-{num:06d}"

def crear_comprobante(obtener_con, id_gym, cliente, items, metodo_pago, descuento, id_vendedor, numero_referencia, url_for_func, render_template_func):
    import uuid as _uuid
    conn = obtener_con()
    try:
        subtotal = sum(float(i['precio_unitario']) * int(i['cantidad']) for i in items)
        descuento_val = float(descuento or 0)
        total = subtotal - descuento_val
        numero = _next_num(conn, id_gym)
        codigo_tx = str(_uuid.uuid4())[:12]
        with conn.cursor() as cursor:
            # Insertar encabezado del comprobante
            cursor.execute(
                """
                INSERT INTO comprobantes(id_gimnasio, numero, fecha, nombre_cliente, documento_cliente, correo_cliente, metodo_pago, subtotal, descuento, total_pagado, id_vendedor, codigo_transaccion, numero_referencia, qr_url)
                VALUES(%s,%s,NOW(),%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    id_gym, numero, (cliente or {}).get('nombre'), (cliente or {}).get('documento'), (cliente or {}).get('correo'),
                    metodo_pago, subtotal, descuento_val, total, id_vendedor, codigo_tx, numero_referencia, None
                )
            )
            id_comp = cursor.lastrowid
            
            # Insertar detalles
            for it in items:
                cant = int(it['cantidad'])
                pu = float(it['precio_unitario'])
                tot = cant * pu
                cursor.execute(
                    """
                    INSERT INTO comprobante_detalle(id_comprobante, cantidad, descripcion, precio_unitario, total)
                    VALUES(%s,%s,%s,%s,%s)
                    """,
                    (id_comp, cant, it['descripcion'], pu, tot)
                )
                
            # Generar PDF y actualizar ruta
            try:
                # Reutilizar lógica de PDF existente si es posible o usar una nueva unificada
                # Para mantener compatibilidad con lo que pide el usuario (no romper nada),
                # generaremos el PDF aquí usando los datos recién insertados.
                gym = _get_gym(conn, id_gym)
                ruta_pdf = _pdf_path_for(id_gym, numero)
                
                # Construir datos para PDF
                encabezado_pdf = [
                    f"{gym['nombre']} - NIT {gym['nit']}",
                    f"{gym['direccion']} - {gym['ciudad']} - Tel {gym['telefono']}",
                    f"{gym['correo']}",
                ]
                
                cuerpo_pdf = [
                    f"Comprobante: {numero}",
                    f"Cliente: {(cliente or {}).get('nombre')}",
                    f"Documento: {(cliente or {}).get('documento')}",
                    f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    "-" * 40,
                ]
                
                for it in items:
                    cuerpo_pdf.append(f"{it['cantidad']} x {it['descripcion']} - ${float(it['precio_unitario']):,.0f}")
                
                cuerpo_pdf.append("-" * 40)
                cuerpo_pdf.append(f"Subtotal: ${subtotal:,.0f}")
                if descuento_val > 0:
                    cuerpo_pdf.append(f"Descuento: -${descuento_val:,.0f}")
                cuerpo_pdf.append(f"TOTAL: ${total:,.0f}")
                cuerpo_pdf.append(f"Método de pago: {metodo_pago}")
                
                if gym.get('texto_legal'):
                    cuerpo_pdf.append(gym['texto_legal'])
                cuerpo_pdf.append("Comprobante interno — No es factura DIAN.")
                
                _write_simple_pdf(ruta_pdf, encabezado_pdf + [""] + cuerpo_pdf)
                web_ruta = '/' + os.path.relpath(ruta_pdf, os.path.abspath(os.path.dirname(__file__))).replace('\\','/')
                
                cursor.execute("UPDATE comprobantes SET ruta_pdf=%s WHERE id_comprobante=%s", (web_ruta, id_comp))
            except Exception as e:
                print(f"Error generando PDF: {e}")

        conn.commit()
        return id_comp
    except Exception as e:
        print(f"Error creando comprobante: {e}")
        return None
    finally:
        conn.close()

def generar_comprobante_unificado(conn, id_gym, tipo_origen, id_origen, cliente_data, items, metodo_pago, total_pagado, **kwargs):
    """
    Función unificada para generar comprobantes (Ventas y Membresías).
    Adaptada al esquema REAL de la base de datos:
    Tabla comprobantes: id_comprobante, id_gimnasio, id_pago, id_producto, tipo, descripcion, ruta_pdf, total, fecha_generado
    Tabla comprobante_detalle: id_detalle, id_comprobante, concepto, cantidad, precio_unitario, subtotal
    """
    # Validar datos mínimos
    if not items: return None
    
    gym = _get_gym(conn, id_gym)
    
    # Generar número consecutivo (solo para PDF y ruta, no hay columna 'numero' en tabla)
    consecutivo = _inc_consecutivo(conn, id_gym)
    numero = f"CP-{consecutivo:06d}"
    
    # Calcular totales
    subtotal_val = sum(float(i['precio_unitario']) * int(i['cantidad']) for i in items)
    if total_pagado is None: total_pagado = subtotal_val
    
    # Preparar datos para inserción
    id_pago_val = id_origen if tipo_origen == 'pago' else None
    id_producto_val = kwargs.get('id_producto')
    
    # Descripción general para la tabla comprobantes
    desc_general = items[0]['descripcion'] if items else f"Comprobante {tipo_origen}"
    if len(items) > 1:
        desc_general += f" y {len(items)-1} ítems más"
        
    # Ruta PDF temporal (se actualiza después)
    ruta_pdf_rel = "" 
    
    with conn.cursor() as cursor:
        # 1. Insertar en tabla comprobantes (Esquema VERIFICADO)
        cursor.execute(
            """
            INSERT INTO comprobantes(id_gimnasio, id_pago, id_producto, tipo, descripcion, ruta_pdf, total, fecha_generado)
            VALUES(%s, %s, %s, %s, %s, %s, %s, NOW())
            """,
            (id_gym, id_pago_val, id_producto_val, tipo_origen, desc_general, ruta_pdf_rel, total_pagado)
        )
        id_comp = cursor.lastrowid
        
        # 2. Insertar detalles (Esquema VERIFICADO: concepto en vez de descripcion)
        for it in items:
            cant = int(it['cantidad'])
            pu = float(it['precio_unitario'])
            tot = cant * pu
            cursor.execute(
                """
                INSERT INTO comprobante_detalle(id_comprobante, concepto, cantidad, precio_unitario, subtotal)
                VALUES(%s, %s, %s, %s, %s)
                """,
                (id_comp, it['descripcion'], cant, pu, tot)
            )
            
        # 3. Generar PDF
        try:
            ruta_pdf = _pdf_path_for(id_gym, numero)
            encabezado = [
                f"{gym['nombre']} - NIT {gym['nit']}",
                f"{gym['direccion']} - {gym['ciudad']} - Tel {gym['telefono']}",
                f"{gym['correo']}",
            ]
            cuerpo = [
                f"Comprobante: {numero}",
                f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                f"Cliente: {cliente_data.get('nombre') or 'Cliente General'}",
                f"Documento: {cliente_data.get('documento') or ''}",
                "-" * 30
            ]
            for it in items:
                cuerpo.append(f"{it['cantidad']} x {it['descripcion']} (${float(it['precio_unitario']):,.0f}) = ${float(it['precio_unitario'])*int(it['cantidad']):,.0f}")
            
            cuerpo.append("-" * 30)
            cuerpo.append(f"Total: ${total_pagado:,.0f}")
            cuerpo.append(f"Método: {metodo_pago}")
            if gym.get('texto_legal'): cuerpo.append(gym['texto_legal'])
            cuerpo.append("Comprobante interno — No es factura DIAN.")
            
            _write_simple_pdf(ruta_pdf, encabezado + [""] + cuerpo)
            web_ruta = '/' + os.path.relpath(ruta_pdf, os.path.abspath(os.path.dirname(__file__))).replace('\\','/')
            
            # Actualizar ruta_pdf
            cursor.execute("UPDATE comprobantes SET ruta_pdf=%s WHERE id_comprobante=%s", (web_ruta, id_comp))
            
        except Exception as e:
            print(f"Error generando PDF interno: {e}")
            # No fallamos la transacción si el PDF falla, pero es crítico para el usuario
            # Intentamos al menos dejar el registro
            
    conn.commit()
    return id_comp

@app.route('/finanzas/gimnasio/configurar', methods=['GET','POST'])
def configurar_gimnasio():
    conn = obtener_conexion()
    try:
        gid = active_gym_id()
        if request.method == 'POST':
            nombre = request.form.get('nombre') or ''
            nit = request.form.get('nit') or ''
            direccion = request.form.get('direccion') or ''
            telefono = request.form.get('telefono') or ''
            with conn.cursor() as cursor:
                cursor.execute("SELECT id_gimnasio FROM gimnasios WHERE id_gimnasio=%s", (gid,))
                row = cursor.fetchone()
                if row:
                    cursor.execute(
                        """
                        UPDATE gimnasios
                           SET nombre=%s, nit=%s, direccion=%s, telefono=%s
                         WHERE id_gimnasio=%s
                        """,
                        (nombre, nit, direccion, telefono, gid)
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO gimnasios(id_gimnasio, nombre, nit, direccion, telefono)
                        VALUES(%s,%s,%s,%s,%s)
                        """,
                        (gid, nombre, nit, direccion, telefono)
                    )
            conn.commit()
            flash("Configuración del gimnasio actualizada", "success")
            return redirect(url_for('configurar_gimnasio'))
        with conn.cursor() as cursor:
            cursor.execute("SELECT id_gimnasio, nombre, nit, direccion, telefono FROM gimnasios WHERE id_gimnasio=%s", (gid,))
            gym = cursor.fetchone() or {'id_gimnasio': gid, 'nombre': '', 'nit': '', 'direccion': '', 'telefono': ''}
        return render_template('configuracion_gimnasio.html', gym=gym)
    finally:
        conn.close()

@app.route('/finanzas/comprobantes')
def listar_comprobantes():
    conn = obtener_conexion()
    try:
        fi = request.args.get('fecha_inicio')
        ff = request.args.get('fecha_fin')
        mp = request.args.get('metodo_pago')
        nc = request.args.get('nombre_cliente')
        sql = "SELECT * FROM comprobantes WHERE 1=1"
        params = []
        if fi:
            sql += " AND DATE(fecha) >= %s"; params.append(fi)
        if ff:
            sql += " AND DATE(fecha) <= %s"; params.append(ff)
        if mp:
            sql += " AND metodo_pago = %s"; params.append(mp)
        if nc:
            sql += " AND nombre_cliente LIKE %s"; params.append(f"%{nc}%")
        sql += " ORDER BY fecha DESC"
        with conn.cursor() as cursor:
            cursor.execute(sql, tuple(params))
            comprobantes = cursor.fetchall()
        filtros = {'fecha_inicio': fi or '', 'fecha_fin': ff or '', 'metodo_pago': mp or '', 'nombre_cliente': nc or ''}
        return render_template('comprobantes_list.html', comprobantes=comprobantes, filtros=filtros)
    finally:
        conn.close()

@app.route('/comprobantes')
def comprobantes_home():
    return redirect(url_for('comprobantes_filtrar'))

@app.route('/comprobantes/filtrar')
def comprobantes_filtrar():
    conn = obtener_conexion()
    try:
        fi = request.args.get('fi')
        ff = request.args.get('ff')
        numero = request.args.get('numero')
        cliente = request.args.get('cliente')
        sql = "SELECT c.* FROM comprobantes c WHERE 1=1"
        params = []
        if fi:
            sql += " AND DATE(c.fecha_generado) >= %s"; params.append(fi)
        if ff:
            sql += " AND DATE(c.fecha_generado) <= %s"; params.append(ff)
        if numero:
            sql += " AND c.ruta_pdf LIKE %s"; params.append(f"%{numero}%")
        with conn.cursor() as cursor:
            cursor.execute(sql + " ORDER BY c.fecha_generado DESC", tuple(params))
            comprobantes = cursor.fetchall()
        filtros = {'fi': fi or '', 'ff': ff or '', 'numero': numero or '', 'cliente': cliente or ''}
        return render_template('comprobantes_list.html', comprobantes=comprobantes, filtros=filtros)
    finally:
        conn.close()

@app.route('/comprobantes/exportar')
def comprobantes_exportar():
    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id_comprobante, c.id_gimnasio,
                       c.total AS total_calc,
                       c.fecha_generado, c.ruta_pdf
                  FROM comprobantes c
              ORDER BY c.fecha_generado DESC
                """
            )
            rows = cursor.fetchall()
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        fname = f"comprobantes_{ts}.csv"
        tmp = os.path.join(os.path.abspath(os.path.dirname(__file__)), fname)
        with open(tmp, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['ID', 'Gimnasio', 'Total', 'Fecha', 'Ruta'])
            for r in rows:
                w.writerow([r['id_comprobante'], r['id_gimnasio'], r['total_calc'], r['fecha_generado'], r['ruta_pdf']])
        return send_file(tmp, as_attachment=True, download_name=fname, mimetype='text/csv')
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass
        conn.close()

@app.route('/comprobantes/<int:id_comprobante>')
def ver_comprobante(id_comprobante):
    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM comprobantes WHERE id_comprobante=%s", (id_comprobante,))
            comp = cursor.fetchone()
            if not comp:
                return redirect(url_for('listar_comprobantes'))
            
            # Obtener configuración
            # Usar _table_exists para evitar error si no existe la tabla de config
            if _table_exists(conn, 'comprobante_config'):
                cursor.execute("SELECT * FROM comprobante_config WHERE id_gimnasio=%s", (comp['id_gimnasio'],))
                cfg = cursor.fetchone() or _ensure_cfg(conn, comp['id_gimnasio'])
            else:
                cfg = {}

            # Obtener detalle
            cursor.execute("SELECT * FROM comprobante_detalle WHERE id_comprobante=%s", (id_comprobante,))
            detalle = cursor.fetchall()
            
        gym = _get_gym(conn, comp['id_gimnasio']) or {'nombre': 'Gimnasio', 'direccion': '', 'ciudad': '', 'telefono': '', 'correo': '', 'logo': '', 'texto_legal': ''}
        
        # Helper para configuración segura
        cfg = {
            'nombre_comprobante': cfg.get('nombre_comprobante', 'Comprobante'),
            'logo_url': cfg.get('logo_url') or gym.get('logo'),
            'color_titulo': cfg.get('color_titulo', '#1E3A8A'),
            'color_texto': cfg.get('color_texto', '#0f172a'),
            'texto_pie': cfg.get('texto_pie') or gym.get('texto_legal'),
            'mostrar_qr': cfg.get('mostrar_qr', 0)
        }

        # Calcular totales de respaldo
        total_calc = sum((float(row.get('total') or 0)) for row in detalle)
        
        # Determinar número de comprobante de forma segura
        numero_comp = comp.get('numero')
        if not numero_comp and comp.get('ruta_pdf'):
            try:
                numero_comp = os.path.basename(comp['ruta_pdf']).replace('.pdf','')
            except:
                numero_comp = f"ID-{id_comprobante}"
        if not numero_comp:
            numero_comp = f"ID-{id_comprobante}"

        comp_fmt = {
            'numero': numero_comp,
            'fecha': comp.get('fecha') or comp.get('fecha_generado') or datetime.now(),
            'id_gimnasio': comp['id_gimnasio'],
            'nombre_cliente': comp.get('nombre_cliente') or request.args.get('cliente') or '',
            'documento_cliente': comp.get('documento_cliente') or '',
            'correo_cliente': comp.get('correo_cliente') or '',
            'subtotal': comp.get('subtotal') or total_calc,
            'descuento': comp.get('descuento') or 0,
            'metodo_pago': comp.get('metodo_pago') or request.args.get('metodo') or '',
            'total_pagado': comp.get('total_pagado') or comp.get('total') or total_calc,
            'id_vendedor': comp.get('id_vendedor') or '',
            'codigo_transaccion': comp.get('codigo_transaccion') or '',
            'qr_url': comp.get('qr_url') or ''
        }
        data = {'gym': gym, 'cfg': cfg, 'comp': comp_fmt, 'detalle': detalle}
        return render_template('comprobante.html', data=data)
    finally:
        conn.close()

@app.route('/comprobantes/<int:id_comprobante>/pdf')
def descargar_comprobante_pdf(id_comprobante):
    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT ruta_pdf FROM comprobantes WHERE id_comprobante=%s", (id_comprobante,))
            row = cursor.fetchone()
            if not row:
                return redirect(url_for('comprobantes_home'))
            path = os.path.join(os.path.abspath(os.path.dirname(__file__)), row['ruta_pdf'].lstrip('/'))
        return send_file(path, as_attachment=True, download_name=os.path.basename(path), mimetype='application/pdf')
    finally:
        conn.close()

@app.route('/finanzas/comprobantes/configurar', methods=['GET','POST'])
def configurar_comprobantes():
    conn = obtener_conexion()
    try:
        gid = active_gym_id()
        if request.method == 'POST':
            nombre_gimnasio = request.form.get('nombre_gimnasio') or ''
            nit = request.form.get('nit') or ''
            direccion = request.form.get('direccion') or ''
            telefono = request.form.get('telefono') or ''
            logo = request.form.get('logo') or ''
            with conn.cursor() as cursor:
                if _table_exists(conn, 'comprobante_config'):
                    has_nombre_gimnasio = _has_column(conn, 'comprobante_config', 'nombre_gimnasio')
                    cursor.execute("SELECT 1 FROM comprobante_config WHERE id_gimnasio=%s", (gid,))
                    row = cursor.fetchone()
                    if row:
                        if has_nombre_gimnasio:
                            cursor.execute(
                                """
                                UPDATE comprobante_config
                                   SET nombre_gimnasio=%s, nit=%s, direccion=%s, telefono=%s, logo=%s
                                 WHERE id_gimnasio=%s
                                """,
                                (nombre_gimnasio, nit, direccion, telefono, logo, gid)
                            )
                        else:
                            cursor.execute(
                                """
                                UPDATE comprobante_config
                                   SET nombre=%s, nit=%s, direccion=%s, telefono=%s, logo=%s
                                 WHERE id_gimnasio=%s
                                """,
                                (nombre_gimnasio, nit, direccion, telefono, logo, gid)
                            )
                    else:
                        if has_nombre_gimnasio:
                            cursor.execute(
                                """
                                INSERT INTO comprobante_config(id_gimnasio, nombre_gimnasio, nit, direccion, telefono, logo)
                                VALUES (%s,%s,%s,%s,%s,%s)
                                """,
                                (gid, nombre_gimnasio, nit, direccion, telefono, logo)
                            )
                        else:
                            cursor.execute(
                                """
                                INSERT INTO comprobante_config(id_gimnasio, nombre, nit, direccion, telefono, logo)
                                VALUES (%s,%s,%s,%s,%s,%s)
                                """,
                                (gid, nombre_gimnasio, nit, direccion, telefono, logo)
                            )
                else:
                    cursor.execute(
                        """
                        UPDATE gimnasios
                           SET nombre=%s, nit=%s, direccion=%s, telefono=%s, logo=%s
                         WHERE id_gimnasio=%s
                        """,
                        (nombre_gimnasio, nit, direccion, telefono, logo, gid)
                    )
            conn.commit()
            flash("Configuración de comprobantes guardada", "success")
            return redirect(url_for('configurar_comprobantes'))
        with conn.cursor() as cursor:
            if _table_exists(conn, 'comprobante_config'):
                if _has_column(conn, 'comprobante_config', 'nombre_gimnasio'):
                    cursor.execute("SELECT nombre_gimnasio, nit, direccion, telefono, logo FROM comprobante_config WHERE id_gimnasio=%s", (gid,))
                    cfg = cursor.fetchone() or {}
                    cfg = cfg or {}
                else:
                    cursor.execute("SELECT nombre, nit, direccion, telefono, logo FROM comprobante_config WHERE id_gimnasio=%s", (gid,))
                    row = cursor.fetchone() or {}
                    cfg = {
                        'nombre_gimnasio': row.get('nombre') or '',
                        'nit': row.get('nit') or '',
                        'direccion': row.get('direccion') or '',
                        'telefono': row.get('telefono') or '',
                        'logo': row.get('logo') or ''
                    }
            else:
                cursor.execute("SELECT nombre, nit, direccion, telefono, logo FROM gimnasios WHERE id_gimnasio=%s", (gid,))
                row = cursor.fetchone() or {}
                cfg = {
                    'nombre_gimnasio': row.get('nombre') or '',
                    'nit': row.get('nit') or '',
                    'direccion': row.get('direccion') or '',
                    'telefono': row.get('telefono') or '',
                    'logo': row.get('logo') or ''
                }
        return render_template('comprobante_config.html', cfg=cfg)
    finally:
        conn.close()

@app.after_request
def agregar_encabezados(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Filtro global: exigir sesiÃ³n para acceder a rutas protegidas
@app.before_request
def requerir_login_global():
    # Endpoints pÃºblicos que no requieren sesiÃ³n
    allowlist = {"login", "register", "forgot", "reset_password", "static"}
    ep = request.endpoint
    # Permitir archivos estÃ¡ticos o endpoints explÃ­citos en la lista blanca
    if ep in allowlist or (request.path or "").startswith("/static/"):
        return
    # Si no hay usuario en sesiÃ³n, redirigir a login
    if "usuario" not in session:
        return redirect(url_for("login"))

# Decorador para proteger rutas
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# -------------------
# Dashboard principal
# -------------------
@app.route('/')
@login_required
def index():
    conn = None
    try:
        conn = obtener_conexion()
        with conn.cursor() as cursor:
            # Total de clientes
            cursor.execute("SELECT COUNT(*) AS total FROM clientes")
            total_miembros = cursor.fetchone()['total']

            # Nuevas inscripciones este mes
            cursor.execute("""
                SELECT COUNT(*) AS nuevos
                  FROM clientes
                 WHERE MONTH(fecha_registro)=MONTH(CURRENT_DATE())
                   AND YEAR(fecha_registro)=YEAR(CURRENT_DATE())
            """)
            nuevas_inscripciones = cursor.fetchone()['nuevos']

            # Miembros activos (conteo)
            cursor.execute("""
                SELECT COUNT(DISTINCT id_cliente) AS activos
                  FROM membresias
                 WHERE fecha_fin >= CURRENT_DATE()
            """)
            miembros_activos = cursor.fetchone()['activos']

            # Listado de clientes activos con detalles y foto
            cursor.execute("""
                SELECT
                    c.*, 
                    t.nombre    AS tipo_membresia,
                    m.fecha_fin AS proximo_pago
                FROM clientes c
                JOIN membresias m ON c.id_cliente = m.id_cliente
                LEFT JOIN tipos_membresia t ON m.id_tipo_membresia = t.id_tipo_membresia
                WHERE m.fecha_fin >= CURRENT_DATE()
                ORDER BY c.nombre ASC
            """)
            clientes_activos = cursor.fetchall()

            # Normalizar foto_url y estado
            for cliente in clientes_activos:
                cliente['estado_pago'] = 'activo'
                foto_nombre = cliente.get('foto')
                if foto_nombre:
                    if foto_nombre.startswith('uploads/'):
                        cliente['foto_url'] = url_for('static', filename=foto_nombre)
                    else:
                        cliente['foto_url'] = url_for('static', filename=f"uploads/{foto_nombre}")
                else:
                    cliente['foto_url'] = url_for('static', filename='img/default-user.png')

            # Pagos prÃ³ximos a vencer
            cursor.execute("""
                SELECT
                    c.*,                   -- todos los datos del cliente
                    m.id_membresia,
                    m.fecha_fin,
                    t.nombre    AS tipo_membresia,
                    t.precio    AS costo
                FROM membresias m
                JOIN clientes c ON m.id_cliente = c.id_cliente
                JOIN tipos_membresia t ON m.id_tipo_membresia = t.id_tipo_membresia
                WHERE m.fecha_fin < CURRENT_DATE()
                ORDER BY m.fecha_fin DESC
            """)
            membresias_vencidas = cursor.fetchall()

            # Foto y campos derivados para recordatorio
            for m in membresias_vencidas:
                foto_nombre = m.get('foto')
                if foto_nombre:
                    if foto_nombre.startswith('uploads/'):
                        m['foto_url'] = url_for('static', filename=foto_nombre)
                    else:
                        m['foto_url'] = url_for('static', filename=f"uploads/{foto_nombre}")
                else:
                    m['foto_url'] = url_for('static', filename='img/default-user.png')

            # Ingresos del dÃ­a
            cursor.execute("SELECT SUM(monto) AS total FROM pagos WHERE DATE(fecha_pago)=CURRENT_DATE()")
            ingresos = cursor.fetchone()
            ingresos_dia = ingresos['total'] or 0

        return render_template('dashboard.html',
            total_miembros=total_miembros,
            nuevas_inscripciones=nuevas_inscripciones,
            miembros_activos=miembros_activos,
            membresias_vencidas=membresias_vencidas,
            clientes_activos=clientes_activos,
            ingresos_dia=ingresos_dia
        )
    except Exception as e:
        return jsonify({"message": f"Error: {e}"}), 500
    finally:
        if conn:
            conn.close()

# -------- RUTAS PARA CLIENTES --------
@app.route('/clientes', methods=['GET'])
def obtener_clientes():
    conn = None
    try:
        conn = obtener_conexion()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT
                  c.*,
                  t.nombre     AS tipo_membresia,
                  m.fecha_fin  AS proximo_pago
                FROM clientes c
                LEFT JOIN membresias m ON c.id_cliente = m.id_cliente
                LEFT JOIN tipos_membresia t ON m.id_tipo_membresia = t.id_tipo_membresia
                ORDER BY c.fecha_registro DESC
            """)
            clientes = cursor.fetchall()

            # Procesar cada cliente
            for cliente in clientes:
                # Estado de pago
                if cliente.get('proximo_pago'):
                    cliente['estado_pago'] = "activo" if cliente['proximo_pago'] >= date.today() else "vencido"
                else:
                    cliente['estado_pago'] = "sin registro"

                # Progreso fÃ­sico (placeholder)
                cliente['progreso_fisico'] = 0

                # Foto: soporte para nombre de archivo o ruta ya guardada
                foto_nombre = cliente.get('foto')
                if foto_nombre:
                    if foto_nombre.startswith('uploads/'):
                        cliente['foto_url'] = url_for('static', filename=foto_nombre)
                    else:
                        cliente['foto_url'] = url_for('static', filename=f'uploads/{foto_nombre}')
                else:
                    # asegura que static/default.jpg exista
                    cliente['foto_url'] = url_for('static', filename='default.jpg')

                # Medidas corporales: traer Ãºltimo registro si existe
                try:
                    cursor.execute(
                        "SELECT peso, altura, imc, cintura, pecho, brazo, pierna, observaciones FROM medidas_corporales WHERE id_cliente=%s ORDER BY id_medida DESC LIMIT 1",
                        (cliente['id_cliente'],)
                    )
                    cliente['medidas'] = cursor.fetchone() or {}
                except Exception:
                    try:
                        cursor.execute(
                            "SELECT peso, altura, imc, cintura, pecho, brazo, pierna, observaciones FROM medidas_corporales WHERE id_cliente=%s ORDER BY id DESC LIMIT 1",
                            (cliente['id_cliente'],)
                        )
                        cliente['medidas'] = cursor.fetchone() or {}
                    except Exception:
                        cliente['medidas'] = {}

        return render_template('clientes.html', clientes=clientes)

    except Exception as e:
        flash(f"Error al cargar clientes: {e}", "danger")
        return redirect(url_for('index'))
    finally:
        if conn:
            conn.close()

@app.route('/clientes/nuevo', methods=['GET', 'POST'])
def nuevo_cliente():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        apellido = request.form.get('apellido')
        identificacion = request.form.get('identificacion')
        genero = request.form.get('genero')
        fecha_nacimiento = request.form.get('fecha_nacimiento')
        telefono = request.form.get('telefono')
        # Campos opcionales: email y direcciÃ³n pueden faltar porque se retiraron del formulario
        email = request.form.get('email', '')
        direccion = request.form.get('direccion', '')
        enfermedades = request.form.get('enfermedades')
        alergias = request.form.get('alergias')
        fracturas = request.form.get('fracturas')
        observaciones = request.form.get('observaciones_medicas')

        # Medidas corporales (opcional)
        def to_decimal(val):
            try:
                if val is None or val == '':
                    return None
                return float(val)
            except Exception:
                return None

        peso = to_decimal(request.form.get('peso'))
        altura = to_decimal(request.form.get('altura'))
        imc = to_decimal(request.form.get('imc'))
        cintura = to_decimal(request.form.get('cintura'))
        pecho = to_decimal(request.form.get('pecho'))
        brazo = to_decimal(request.form.get('brazo'))
        pierna = to_decimal(request.form.get('pierna'))
        observaciones_medidas = request.form.get('observaciones_medidas')

        foto = request.files.get('foto')
        nombre_foto = None

        if foto and foto.filename != '' and allowed_file(foto.filename):
            filename = secure_filename(foto.filename)
            if identificacion:
                filename = f"{identificacion}_{filename}"
            else:
                filename = f"{uuid.uuid4().hex[:8]}_{filename}"
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            foto.save(save_path)
            nombre_foto = filename

        conn = obtener_conexion()
        try:
            with conn.cursor() as cursor:
                sql = """
                    INSERT INTO clientes (
                        nombre, apellido, identificacion, genero, fecha_nacimiento,
                        telefono, email, direccion, foto, enfermedades, alergias,
                        fracturas, observaciones_medicas
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (
                    nombre, apellido, identificacion, genero, fecha_nacimiento,
                    (telefono or ''), (email or ''), (direccion or ''), nombre_foto, (enfermedades or ''),
                    (alergias or ''), (fracturas or ''), (observaciones or '')
                ))

                id_cliente = cursor.lastrowid

                # Insertar medidas corporales si hay datos
                if any(v is not None for v in [peso, altura, imc, cintura, pecho, brazo, pierna]) or (observaciones_medidas and observaciones_medidas.strip()):
                    sql_medidas = """
                        INSERT INTO medidas_corporales (
                            id_cliente, peso, altura, imc, cintura, pecho, brazo, pierna, observaciones
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(sql_medidas, (
                        id_cliente, peso, altura, imc, cintura, pecho, brazo, pierna, observaciones_medidas
                    ))
            conn.commit()
            flash("âœ… Cliente registrado exitosamente", "success")
            return redirect(url_for('obtener_clientes'))   # <--- IMPORTANTE
        except Exception as e:
            flash(f"âŒ Error al registrar cliente: {e}", "danger")
            return redirect(url_for('nuevo_cliente'))
        finally:
            conn.close()

    return render_template('nuevo_cliente.html')



@app.route('/clientes/editar/<int:id>', methods=['GET', 'POST'])
def editar_cliente(id):
    conn = None
    try:
        conn = obtener_conexion()
        with conn.cursor() as cursor:
            if request.method == 'POST':
                nombre = request.form['nombre']
                apellido = request.form['apellido']
                email = request.form['email']
                telefono = request.form['telefono']
                direccion = request.form['direccion']
                cursor.execute(
                    "UPDATE clientes SET nombre=%s, apellido=%s, email=%s, telefono=%s, direccion=%s WHERE id_cliente=%s",
                    (nombre, apellido, email, telefono, direccion, id)
                )
                conn.commit()
                flash("Cliente actualizado con Ã©xito", "success")
                return redirect(url_for('obtener_clientes'))
            else:
                cursor.execute("SELECT * FROM clientes WHERE id_cliente = %s", (id,))
                cliente = cursor.fetchone()
                return render_template('editar_cliente.html', cliente=cliente)
    except Exception as e:
        flash(f"Error al editar cliente: {e}", "danger")
        return redirect(url_for('obtener_clientes'))
    finally:
        if conn: conn.close()

@app.route('/clientes/eliminar/<int:id>', methods=['POST'])
def eliminar_cliente(id):
    conn = None
    try:
        conn = obtener_conexion()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM clientes WHERE id_cliente = %s", (id,))
            conn.commit()
            flash("Cliente eliminado con Ã©xito", "success")
            return redirect(url_for('obtener_clientes'))
    except Exception as e:
        flash(f"Error al eliminar cliente: {e}", "danger")
        return redirect(url_for('obtener_clientes'))
    finally:
        if conn: conn.close()
# -------- finanza --------



# -------- RUTAS PARA ENTRENADORES --------
@app.route('/entrenadores')
def obtener_entrenadores():
    try:
        conn = obtener_conexion()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM entrenadores")
            entrenadores = cursor.fetchall()
        return render_template('entrenadores.html', entrenadores=entrenadores)
    except Exception as e:
        flash(f"Error: {e}", "danger")
        return redirect(url_for('index'))
    finally:
        conn.close()

@app.route('/entrenadores/nuevo', methods=['GET', 'POST'])
def nuevo_entrenador():
    if request.method == 'POST':
        try:
            conn = obtener_conexion()
            with conn.cursor() as cursor:
                nombre = request.form['nombre']
                apellido = request.form['apellido']
                especialidad = request.form['especialidad']
                email = request.form['email']
                telefono = request.form['telefono']
                cursor.execute(
                    "INSERT INTO entrenadores (nombre, apellido, especialidad, email, telefono) VALUES (%s,%s,%s,%s,%s)",
                    (nombre, apellido, especialidad, email, telefono)
                )
                conn.commit()
                flash("Entrenador agregado con Ã©xito", "success")
                return redirect(url_for('obtener_entrenadores'))
        except Exception as e:
            flash(f"Error: {e}", "danger")
            return render_template('nuevo_entrenador.html')
        finally:
            conn.close()
    return render_template('nuevo_entrenador.html')

@app.route('/entrenadores/editar/<int:id>', methods=['GET','POST'])
def editar_entrenador(id):
    try:
        conn = obtener_conexion()
        with conn.cursor() as cursor:
            if request.method == 'POST':
                nombre, apellido = request.form['nombre'], request.form['apellido']
                especialidad, email = request.form['especialidad'], request.form['email']
                telefono = request.form['telefono']
                cursor.execute(
                    "UPDATE entrenadores SET nombre=%s,apellido=%s,especialidad=%s,email=%s,telefono=%s WHERE id_entrenador=%s",
                    (nombre, apellido, especialidad, email, telefono, id)
                )
                conn.commit()
                flash("Entrenador actualizado con Ã©xito", "success")
                return redirect(url_for('obtener_entrenadores'))
            cursor.execute("SELECT * FROM entrenadores WHERE id_entrenador=%s", (id,))
            entrenador = cursor.fetchone()
            return render_template('editar_entrenador.html', entrenador=entrenador)
    except Exception as e:
        flash(f"Error: {e}", "danger")
        return redirect(url_for('obtener_entrenadores'))
    finally:
        conn.close()

@app.route('/entrenadores/eliminar/<int:id>', methods=['POST'])
def eliminar_entrenador(id):
    try:
        conn = obtener_conexion()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM entrenadores WHERE id_entrenador=%s", (id,))
            conn.commit()
            flash("Entrenador eliminado con Ã©xito", "success")
            return redirect(url_for('obtener_entrenadores'))
    except Exception as e:
        flash(f"Error: {e}", "danger")
        return redirect(url_for('obtener_entrenadores'))
    finally:
        conn.close()

@app.route('/entrenadores/<int:id_entrenador>/asignar', methods=['GET','POST'])
def asignar_clase_entrenador(id_entrenador):
    """Crear una sesiÃ³n (clase) para un entrenador y asignarla a un cliente.
    AdemÃ¡s, permite registrar una rutina semanal bÃ¡sica con ejercicios predeterminados editables.
    """
    conn = obtener_conexion()
    try:
        with conn.cursor() as cur:
            # Datos del entrenador
            cur.execute("SELECT * FROM entrenadores WHERE id_entrenador=%s", (id_entrenador,))
            entrenador = cur.fetchone()
            if not entrenador:
                flash("Entrenador no encontrado", "danger")
                return redirect(url_for('obtener_entrenadores'))

            if request.method == 'POST':
                # Crear clase individual
                nombre_clase = request.form.get('nombre_clase') or f"SesiÃ³n con {entrenador['nombre']}"
                id_cliente = request.form['id_cliente']
                fecha_hora = request.form['fecha_hora']
                duracion = request.form.get('duracion') or 60
                cur.execute(
                    "INSERT INTO clases (nombre_clase,id_entrenador,fecha_hora,duracion,max_participantes) VALUES (%s,%s,%s,%s,%s)",
                    (nombre_clase, id_entrenador, fecha_hora, duracion, 1)
                )
                id_clase = cur.lastrowid

                # Inscribir cliente a la clase
                cur.execute(
                    "INSERT INTO inscripciones (id_cliente,id_clase) VALUES (%s,%s)",
                    (id_cliente, id_clase)
                )

                # Registrar rutina semanal opcional (Lunes-Viernes)
                fecha_inicio = request.form.get('fecha_inicio')
                if fecha_inicio:
                    fi = datetime.strptime(fecha_inicio, "%Y-%m-%d").date()
                    ff = fi + timedelta(days=6)
                    titulo = request.form.get('titulo_rutina') or f"Plan semanal de {entrenador['nombre']}"
                    descripcion = request.form.get('descripcion_rutina') or "Rutina generada desde Entrenadores"
                    cur.execute(
                        """
                        INSERT INTO rutinas_personalizadas
                          (titulo, descripcion, id_cliente, id_entrenador, fecha_inicio, fecha_fin, duracion_dias)
                        VALUES (%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (titulo, descripcion, id_cliente, id_entrenador, fi, ff, 7)
                    )
                    id_rutina = cur.lastrowid

                    dias = ["Lunes","Martes","Miercoles","Jueves","Viernes"]
                    for d in dias:
                        hora = request.form.get(f"hora_{d}") or None
                        ejercicios = request.form.get(f"ej_{d}") or None
                        if hora or ejercicios:
                            cur.execute(
                                "INSERT INTO rutina_horarios (id_rutina, dia_semana, hora_programada, ejercicios) VALUES (%s,%s,%s,%s)",
                                (id_rutina, d, hora, ejercicios)
                            )

                conn.commit()
                flash("Clase asignada y rutina registrada (si se indicÃ³) correctamente", "success")
                return redirect(url_for('obtener_entrenadores'))

            # GET: datos para el formulario
            cur.execute("SELECT id_cliente, nombre, apellido FROM clientes ORDER BY nombre ASC")
            clientes = cur.fetchall()
            defaults = {
                'Lunes': 'Pecho 4x12 + Cardio 20m',
                'Martes': 'Espalda 4x12 + Core 3x15',
                'Miercoles': 'Piernas 4x12 + Estiramientos',
                'Jueves': 'Hombros 4x12 + Cardio 15m',
                'Viernes': 'Full body 3x12 + Abdominales 3x20'
            }
            return render_template('asignar_clase_entrenador.html', entrenador=entrenador, clientes=clientes, defaults=defaults)
    except Exception as e:
        flash(f"Error: {e}", "danger")
        return redirect(url_for('obtener_entrenadores'))
    finally:
        conn.close()
# -------- RUTAS PARA CLASES --------
@app.route('/clases')
def obtener_clases():
    try:
        conn = obtener_conexion()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT c.*, e.nombre AS nombre_entrenador, e.apellido AS apellido_entrenador
                FROM clases c
                LEFT JOIN entrenadores e ON c.id_entrenador=e.id_entrenador
                ORDER BY c.fecha_hora
            """)
            clases = cursor.fetchall()
            cursor.execute("SELECT id_entrenador,nombre,apellido FROM entrenadores")
            entrenadores = cursor.fetchall()
        return render_template('clases.html', clases=clases, entrenadores=entrenadores)
    except Exception as e:
        flash(f"Error: {e}", "danger")
        return redirect(url_for('index'))
    finally:
        conn.close()

@app.route('/clases/nueva', methods=['GET','POST'])
def nueva_clase():
    if request.method=='POST':
        try:
            conn = obtener_conexion()
            with conn.cursor() as cursor:
                data = (request.form['nombre_clase'], request.form['id_entrenador'],
                        request.form['fecha_hora'], request.form['duracion'],
                        request.form['max_participantes'])
                cursor.execute(
                    "INSERT INTO clases (nombre_clase,id_entrenador,fecha_hora,duracion,max_participantes) VALUES (%s,%s,%s,%s,%s)",
                    data
                )
                conn.commit()
                flash("Clase agregada con Ã©xito","success")
                return redirect(url_for('obtener_clases'))
        except Exception as e:
            flash(f"Error: {e}","danger")
            return redirect(url_for('obtener_clases'))
        finally:
            conn.close()
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        cursor.execute("SELECT id_entrenador,nombre,apellido FROM entrenadores")
        entrenadores = cursor.fetchall()
    conn.close()
    return render_template('nueva_clase.html', entrenadores=entrenadores)

@app.route('/clases/editar/<int:id>', methods=['GET','POST'])
def editar_clase(id):
    try:
        conn = obtener_conexion()
        with conn.cursor() as cursor:
            if request.method=='POST':
                data = (request.form['nombre_clase'],request.form['id_entrenador'],
                        request.form['fecha_hora'],request.form['duracion'],
                        request.form['max_participantes'],id)
                cursor.execute(
                    "UPDATE clases SET nombre_clase=%s,id_entrenador=%s,fecha_hora=%s,duracion=%s,max_participantes=%s WHERE id_clase=%s",
                    data
                )
                conn.commit()
                flash("Clase actualizada con Ã©xito","success")
                return redirect(url_for('obtener_clases'))
            cursor.execute("SELECT * FROM clases WHERE id_clase=%s",(id,))
            clase = cursor.fetchone()
            cursor.execute("SELECT id_entrenador,nombre,apellido FROM entrenadores")
            entrenadores = cursor.fetchall()
        return render_template('editar_clase.html',clase=clase,entrenadores=entrenadores)
    except Exception as e:
        flash(f"Error: {e}","danger")
        return redirect(url_for('obtener_clases'))
    finally:
        conn.close()

@app.route('/clases/eliminar/<int:id>', methods=['POST'])
def eliminar_clase(id):
    try:
        conn = obtener_conexion()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM clases WHERE id_clase=%s",(id,))
            conn.commit()
            flash("Clase eliminada con Ã©xito","success")
            return redirect(url_for('obtener_clases'))
    except Exception as e:
        flash(f"Error: {e}","danger")
        return redirect(url_for('obtener_clases'))
    finally:
        conn.close()
        
# Ingresos y gastos en la misma vista



# -------- RUTAS PARA GASTOS --------
@app.route('/productos')
def obtener_productos():
    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            # Productos
            cursor.execute("SELECT * FROM producto ORDER BY creado_en DESC")
            productos = cursor.fetchall()

            # Crear tabla de promociones si no existe
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS promociones (
                    id_promocion INT AUTO_INCREMENT PRIMARY KEY,
                    id_producto INT NOT NULL,
                    precio_promocional DECIMAL(10,2) NOT NULL,
                    frase VARCHAR(255),
                    incluir_foto TINYINT(1) DEFAULT 1,
                    activo TINYINT(1) DEFAULT 1,
                    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Promociones activas
            cursor.execute(
                """
                SELECT p.*, pr.nombre, pr.precio AS precio_base, pr.foto
                  FROM promociones p
                  JOIN producto pr ON p.id_producto = pr.id_producto
                 WHERE p.activo = 1
                 ORDER BY p.creado_en DESC
                """
            )
            promociones = cursor.fetchall()

            # Clientes para envÃ­o masivo
            cursor.execute("SELECT id_cliente, nombre, apellido, telefono, email FROM clientes ORDER BY nombre ASC")
            clientes = cursor.fetchall()
        # Base pÃºblica para compartir enlaces (opcional, via variable de entorno)
        share_base = os.environ.get('SHARE_BASE_URL')

        return render_template('productos.html', productos=productos, promociones=promociones, clientes=clientes, share_base=share_base)
    finally:
        conn.close()


@app.route('/productos/nuevo', methods=['GET','POST'])
def nuevo_producto():
    if request.method == 'POST':
        nombre = request.form['nombre']
        descripcion = request.form['descripcion']
        precio = parse_cop(request.form['precio'])
        stock = request.form['stock']

        foto = request.files.get('foto')
        filename = None
        if foto and foto.filename != '':
            filename = secure_filename(foto.filename)
            foto.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn = obtener_conexion()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO producto(nombre, descripcion, precio, stock, foto)
                    VALUES (%s,%s,%s,%s,%s)
                """, (nombre, descripcion, precio, stock, filename))
            conn.commit()
            flash("Producto agregado con Ã©xito", "success")
            return redirect(url_for('obtener_productos'))
        finally:
            conn.close()
    return render_template('nuevo_producto.html')


@app.route('/productos/editar/<int:id_producto>', methods=['GET','POST'])
def editar_producto(id_producto):
    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM producto WHERE id_producto=%s", (id_producto,))
            producto = cursor.fetchone()

        if request.method == 'POST':
            nombre = request.form['nombre']
            descripcion = request.form['descripcion']
            precio = parse_cop(request.form['precio'])
            stock = request.form['stock']

            foto = request.files.get('foto')
            filename = producto['foto']
            if foto and foto.filename != '':
                filename = secure_filename(foto.filename)
                foto.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE producto SET nombre=%s, descripcion=%s, precio=%s, stock=%s, foto=%s, actualizado_en=NOW()
                    WHERE id_producto=%s
                """, (nombre, descripcion, precio, stock, filename, id_producto))
            conn.commit()
            flash("Producto actualizado con Ã©xito", "success")
            return redirect(url_for('obtener_productos'))

        return render_template('editar_producto.html', producto=producto)
    finally:
        conn.close()


# -------- Promocionar producto --------
@app.route('/productos/promocionar/<int:id_producto>', methods=['POST'])
def promocionar_producto(id_producto):
    # Valores del formulario
    frase = request.form.get('frase', '').strip()
    incluir_foto = 1 if request.form.get('incluir_foto') == 'on' else 0
    try:
        precio_promocional = parse_cop(request.form.get('precio_promocional', '0'))
    except Exception:
        precio_promocional = 0

    if precio_promocional <= 0:
        flash('El precio promocional debe ser mayor a cero', 'danger')
        return redirect(url_for('obtener_productos'))

    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            # Asegurar existencia de tabla
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS promociones (
                    id_promocion INT AUTO_INCREMENT PRIMARY KEY,
                    id_producto INT NOT NULL,
                    precio_promocional DECIMAL(10,2) NOT NULL,
                    frase VARCHAR(255),
                    incluir_foto TINYINT(1) DEFAULT 1,
                    activo TINYINT(1) DEFAULT 1,
                    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cursor.execute(
                """
                INSERT INTO promociones(id_producto, precio_promocional, frase, incluir_foto, activo)
                VALUES (%s, %s, %s, %s, 1)
                """,
                (id_producto, precio_promocional, frase, incluir_foto)
            )
        conn.commit()
        flash('PromociÃ³n creada para el producto', 'success')
    except Exception as e:
        flash(f'Error al crear la promociÃ³n: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('obtener_productos'))


# -------- Desactivar promociÃ³n --------
@app.route('/promociones/desactivar/<int:id_promocion>', methods=['POST'])
def desactivar_promocion(id_promocion):
    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE promociones SET activo=0 WHERE id_promocion=%s", (id_promocion,))
        conn.commit()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


@app.route('/productos/eliminar/<int:id_producto>', methods=['POST'])
def eliminar_producto(id_producto):
    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM producto WHERE id_producto=%s", (id_producto,))
        conn.commit()
        flash("Producto eliminado con Ã©xito", "success")
    finally:
        conn.close()
    return redirect(url_for('obtener_productos'))

# -------- PÃ¡gina compartible de promociÃ³n (Open Graph) --------
@app.route('/promo/<int:id_promocion>')
def promo_share(id_promocion):
    conn = obtener_conexion()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.*, pr.nombre, pr.descripcion, pr.foto
                  FROM promociones p
                  JOIN producto pr ON p.id_producto = pr.id_producto
                 WHERE p.id_promocion = %s
                """,
                (id_promocion,)
            )
            promo = cur.fetchone()

        if not promo:
            return render_template('promo_share.html', promo=None, image_url=None, title='PromociÃ³n no encontrada')

        # Construye URL absoluta de imagen usando dominio pÃºblico si estÃ¡ configurado
        share_base = os.environ.get('SHARE_BASE_URL')
        base = share_base or request.url_root
        image_url = None
        if promo.get('incluir_foto') and promo.get('foto'):
            image_url = urljoin(base, url_for('static', filename=f"uploads/{promo['foto']}"))

        title = f"PromociÃ³n: {promo['nombre']}"
        return render_template('promo_share.html', promo=promo, image_url=image_url, title=title)
    except Exception as e:
        flash(f"Error al generar pÃ¡gina de promociÃ³n: {e}", "danger")
        return redirect(url_for('obtener_productos'))
    finally:
        conn.close()


# =================== VENTAS (Producto -> Finanzas) ===================
@app.route('/ventas/nueva/<int:id_producto>', methods=['GET','POST'])
def nueva_venta(id_producto):
    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM producto WHERE id_producto=%s", (id_producto,))
            producto = cursor.fetchone()
            cursor.execute("SELECT id_cliente, nombre, apellido, telefono, email FROM clientes ORDER BY nombre ASC")
            clientes = cursor.fetchall()

        if request.method == 'POST':
            cantidad = int(request.form['cantidad'])
            total = float(producto['precio']) * cantidad
            id_cliente = request.form.get('id_cliente')
            metodo_pago = request.form.get('metodo_pago') or 'Efectivo'
            efectivo_recibido = request.form.get('efectivo_recibido')
            try:
                efectivo_val = float(efectivo_recibido) if efectivo_recibido else None
            except:
                efectivo_val = None
            cambio = (efectivo_val - total) if (efectivo_val is not None) else None

            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO ventas(id_producto, cantidad, total) VALUES (%s,%s,%s)",
                               (id_producto, cantidad, total))
                id_venta = cursor.lastrowid
                cursor.execute("UPDATE producto SET stock = stock - %s WHERE id_producto=%s",
                               (cantidad, id_producto))

                # Insertar ingreso en FINANZAS (CRÍTICO: antes del commit)
                cursor.execute(
                    """
                    INSERT INTO finanzas(tipo, descripcion, monto, fecha, origen)
                    VALUES ('ingreso', %s, %s, NOW(), 'producto')
                    """,
                    (f"Venta de {producto['nombre']}", total)
                )

            conn.commit()
            
            id_comp = None
            try:
                cliente_data = {}
                if id_cliente:
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT nombre, apellido, identificacion, email FROM clientes WHERE id_cliente=%s", (id_cliente,))
                        cli = cursor.fetchone() or {}
                        nombre_cli = (cli.get('nombre') or '') + ' ' + (cli.get('apellido') or '')
                        cliente_data = {'nombre': nombre_cli.strip(), 'documento': cli.get('identificacion'), 'correo': cli.get('email')}
                
                items = [{
                    'cantidad': cantidad,
                    'descripcion': producto['nombre'],
                    'precio_unitario': float(producto['precio'])
                }]
                
                gid = active_gym_id()
                # Usar la nueva función unificada
                id_comp = generar_comprobante_unificado(
                    conn,
                    gid,
                    'venta',
                    None, # No hay id_pago previo en ventas directas
                    cliente_data,
                    items,
                    metodo_pago, # Asegurarse de tener metodo_pago en este contexto
                    float(producto['precio']) * int(cantidad),
                    id_producto=id_producto
                )
            except Exception as e:
                print(f"Error generando comprobante venta: {e}")
                id_comp = None

            flash("Venta registrada y añadida a finanzas", "success")
            if id_comp:
                return redirect(url_for('ver_comprobante', id_comprobante=id_comp, back=url_for('obtener_productos')))
            return redirect(url_for('obtener_productos'))

        return render_template('nueva_venta.html', producto=producto, clientes=clientes)
    finally:
        conn.close()


# -------- FACTURA: VENTA --------
# -------- FACTURA: PAGO/MEMBRESÃA --------
# -------- IMAGEN DE FACTURA: VENTA --------
# -------- IMAGEN DE FACTURA: PAGO --------
# =================== PAGOS MEMBRESÃAS (Ingreso -> Finanzas) ===================

# =================== FINANZAS (Ingresos + Gastos) ===================
@app.route('/finanzas')
def finanzas():
    conn = obtener_conexion()
    try:
        # NOTA: La tabla finanzas es global y contiene ingresos y gastos.
        # No filtramos por id_gimnasio porque la tabla no tiene esa columna.
        fecha = request.args.get('fecha')
        mes = request.args.get('mes')
        
        where = "WHERE 1=1"
        params = []
        
        if fecha:
            where += " AND DATE(fecha)=%s"
            params.append(fecha)
        elif mes:
            where += " AND DATE_FORMAT(fecha,'%Y-%m')=%s"
            params.append(mes)
            
        with conn.cursor() as cursor:
            # 1. Obtener Movimientos (Ingresos y Gastos) de la tabla finanzas
            sql = f"""
                SELECT id_finanza, tipo, descripcion, monto, origen, fecha
                FROM finanzas
                {where}
                ORDER BY fecha DESC
            """
            cursor.execute(sql, tuple(params))
            movimientos = cursor.fetchall()
            
            # 2. Calcular Totales
            # Ingresos
            sql_ing = f"SELECT COALESCE(SUM(monto),0) as total FROM finanzas {where} AND tipo='ingreso'"
            cursor.execute(sql_ing, tuple(params))
            row_ing = cursor.fetchone()
            total_ingresos = row_ing['total'] if row_ing else 0
            
            # Gastos
            sql_gas = f"SELECT COALESCE(SUM(monto),0) as total FROM finanzas {where} AND tipo='gasto'"
            cursor.execute(sql_gas, tuple(params))
            row_gas = cursor.fetchone()
            total_gastos = row_gas['total'] if row_gas else 0

        return render_template('finanzas.html', movimientos=movimientos,
                               total_ingresos=total_ingresos, total_gastos=total_gastos)
    finally:
        conn.close()

# =================== BACKUP/DESCARGA ===================
@app.route('/backup/descargar')
def descargar_backup():
    try:
        import shutil, os
        from datetime import datetime
        # Carpeta del proyecto Python (plantillas, estÃ¡ticos, app)
        base_dir = os.path.abspath(os.path.dirname(__file__))
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        zip_base = os.path.join(base_dir, f"gimnasio_app_backup_{timestamp}")
        # Crear ZIP del proyecto (carpeta actual)
        shutil.make_archive(zip_base, 'zip', base_dir)
        zip_path = f"{zip_base}.zip"
        # Enviar como archivo descargable
        return send_file(zip_path, as_attachment=True, download_name=os.path.basename(zip_path), mimetype='application/zip')
    except Exception as e:
        flash(f"Error al generar backup: {e}", "danger")
        return redirect(url_for('index'))


# =================== GASTOS MANUALES ===================
@app.route('/finanzas/nuevo_gasto', methods=['GET','POST'])
def nuevo_gasto():
    if request.method == 'POST':
        descripcion = request.form['descripcion']
        monto = parse_cop(request.form['monto'])
        conn = obtener_conexion()
        try:
            with conn.cursor() as cursor:
                # Insertar en finanzas (tipo='gasto', origen='otro')
                cursor.execute(
                    """
                    INSERT INTO finanzas(tipo, descripcion, monto, fecha, origen)
                    VALUES ('gasto', %s, %s, NOW(), 'otro')
                    """,
                    (descripcion, monto)
                )
            conn.commit()
            flash("Gasto agregado correctamente", "success")
            return redirect(url_for('finanzas'))
        finally:
            conn.close()
    return render_template('nuevo_gasto.html')


@app.route('/finanzas/editar/<int:id>', methods=['GET','POST'])
def editar_gasto(id):
    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            if _has_column(conn, 'gastos', 'id_gimnasio'):
                cursor.execute("SELECT * FROM gastos WHERE id_gasto=%s AND id_gimnasio=%s", (id, active_gym_id()))
            else:
                cursor.execute("SELECT * FROM gastos WHERE id_gasto=%s", (id,))
            gasto = cursor.fetchone()
        if not gasto:
            flash("No se puede editar este registro", "danger")
            return redirect(url_for('finanzas'))

        if request.method == 'POST':
            descripcion = request.form['descripcion']
            monto = parse_cop(request.form['monto'])

            with conn.cursor() as cursor:
                if _has_column(conn, 'gastos', 'id_gimnasio'):
                    cursor.execute(
                        """
                        UPDATE gastos SET descripcion=%s, monto=%s, fecha=NOW()
                         WHERE id_gasto=%s AND id_gimnasio=%s
                        """,
                        (descripcion, monto, id, active_gym_id())
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE gastos SET descripcion=%s, monto=%s, fecha=NOW()
                         WHERE id_gasto=%s
                        """,
                        (descripcion, monto, id)
                    )
            conn.commit()
            flash("Gasto actualizado", "success")
            return redirect(url_for('finanzas'))

        return render_template('editar_gasto.html', gasto=gasto)
    finally:
        conn.close()


@app.route('/finanzas/eliminar/<int:id>', methods=['POST'])
def eliminar_gasto(id):
    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            if _has_column(conn, 'gastos', 'id_gimnasio'):
                cursor.execute("DELETE FROM gastos WHERE id_gasto=%s AND id_gimnasio=%s", (id, active_gym_id()))
            else:
                cursor.execute("DELETE FROM gastos WHERE id_gasto=%s", (id,))
        conn.commit()
        flash("Gasto eliminado", "success")
    finally:
        conn.close()
    return redirect(url_for('finanzas'))

# -------- RUTAS PARA INSCRIPCIONES --------
@app.route('/inscripciones')
def obtener_inscripciones():
    try:
        conn = obtener_conexion()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT i.*, c.nombre AS nombre_cliente, c.apellido AS apellido_cliente, cl.nombre_clase
                FROM inscripciones i
                JOIN clientes c ON i.id_cliente=c.id_cliente
                JOIN clases cl ON i.id_clase=cl.id_clase
                ORDER BY i.fecha_inscripcion DESC
            """)
            inscripciones = cursor.fetchall()
            cursor.execute("SELECT id_cliente,nombre,apellido FROM clientes")
            clientes = cursor.fetchall()
            cursor.execute("SELECT id_clase,nombre_clase,fecha_hora FROM clases WHERE fecha_hora>NOW()")
            clases = cursor.fetchall()
        return render_template('inscripciones.html', inscripciones=inscripciones, clientes=clientes, clases=clases)
    except Exception as e:
        flash(f"Error: {e}","danger")
        return redirect(url_for('index'))
    finally:
        conn.close()

@app.route('/inscripciones/nueva', methods=['GET','POST'])
def nueva_inscripcion():
    if request.method=='POST':
        try:
            conn = obtener_conexion()
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO inscripciones (id_cliente,id_clase) VALUES (%s,%s)",
                    (request.form['id_cliente'],request.form['id_clase'])
                )
                conn.commit()
                flash("InscripciÃ³n realizada con Ã©xito","success")
                return redirect(url_for('obtener_inscripciones'))
        except Exception as e:
            flash(f"Error: {e}","danger")
            return redirect(url_for('obtener_inscripciones'))
        finally:
            conn.close()
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        cursor.execute("SELECT id_cliente,nombre,apellido FROM clientes")
        clientes = cursor.fetchall()
        cursor.execute("SELECT id_clase,nombre_clase,fecha_hora FROM clases WHERE fecha_hora>NOW()")
        clases = cursor.fetchall()
    conn.close()
    return render_template('nueva_inscripcion.html', clientes=clientes, clases=clases)

@app.route('/inscripciones/eliminar/<int:id>', methods=['POST'])
def eliminar_inscripcion(id):
    try:
        conn = obtener_conexion()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM inscripciones WHERE id_inscripcion=%s",(id,))
            conn.commit()
            flash("InscripciÃ³n eliminada con Ã©xito","success")
            return redirect(url_for('obtener_inscripciones'))
    except Exception as e:
        flash(f"Error: {e}","danger")
        return redirect(url_for('obtener_inscripciones'))
    finally:
        conn.close()

# -------- RUTAS PARA MEMBRESIAS --------
# ------------------ LISTAR MEMBRESÃAS ------------------
@app.route('/membresias')
def obtener_membresias():
    try:
        conn = obtener_conexion()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    m.id_membresia,
                    c.nombre AS nombre_cliente,
                    c.apellido AS apellido_cliente,
                    t.nombre AS tipo_membresia,
                    t.duracion_dias,
                    m.fecha_inicio,
                    m.fecha_fin
                FROM membresias m
                JOIN clientes c ON m.id_cliente = c.id_cliente
                LEFT JOIN tipos_membresia t ON m.id_tipo_membresia = t.id_tipo_membresia
                ORDER BY m.fecha_fin DESC
            """)
            membresias = cursor.fetchall()

        # ðŸ”¹ Si no hay tipo, significa que fue personalizada â†’ calcular dÃ­as y mostrarlo
        for m in membresias:
            if not m['tipo_membresia']:
                dias = (m['fecha_fin'] - m['fecha_inicio']).days
                m['tipo_membresia'] = f"Pase Diario ({dias} dÃ­as)"

        # ðŸ”¹ Agregar fecha actual al contexto
        hoy = date.today()
        return render_template('membresias.html', membresias=membresias, hoy=hoy)
    except Exception as e:
        flash(f"Error: {e}", "danger")
        return redirect(url_for('index'))
    finally:
        if conn: conn.close()



# ------------------ NUEVA MEMBRESÃA ------------------



@app.route('/membresias/nueva', methods=['GET','POST'])
def nueva_membresia():
    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            if request.method == 'POST':
                id_cliente = request.form['id_cliente']
                id_tipo = request.form.get('id_tipo_membresia')
                dias_personalizados = request.form.get('dias_personalizados')
                fecha_inicio = request.form['fecha_inicio']
                monto = parse_cop(request.form['monto'])
                metodo_pago = request.form['metodo_pago']
                numero_referencia = request.form.get('numero_referencia') or None

                # Calcular fecha de fin
                fecha_inicio_dt = datetime.strptime(fecha_inicio, "%Y-%m-%d")
                fecha_fin = None
                dias_tipo = None
                nombre_tipo = None

                if id_tipo == "personalizado" and dias_personalizados:
                    fecha_fin_dt = fecha_inicio_dt + timedelta(days=int(dias_personalizados))
                    fecha_fin = fecha_fin_dt.strftime("%Y-%m-%d")
                    id_tipo = None  # No se asocia a un tipo predefinido
                    dias_tipo = int(dias_personalizados)
                    nombre_tipo = "Personalizado"
                elif id_tipo:  
                    cursor.execute("SELECT nombre, duracion_dias FROM tipos_membresia WHERE id_tipo_membresia=%s", (id_tipo,))
                    tipo = cursor.fetchone()
                    if tipo:
                        dias = int(tipo['duracion_dias'])
                        fecha_fin_dt = fecha_inicio_dt + timedelta(days=dias)
                        fecha_fin = fecha_fin_dt.strftime("%Y-%m-%d")
                        dias_tipo = dias
                        nombre_tipo = tipo['nombre']

                # 1) Insertar membresía
                cursor.execute("""
                    INSERT INTO membresias (id_cliente, id_tipo_membresia, fecha_inicio, fecha_fin)
                    VALUES (%s, %s, %s, %s)
                """, (id_cliente, id_tipo, fecha_inicio, fecha_fin))
                id_membresia = cursor.lastrowid

                # 2) Insertar pago asociado
                cursor.execute("""
                    INSERT INTO pagos (id_cliente, id_membresia, monto, metodo_pago, numero_referencia)
                    VALUES (%s, %s, %s, %s, %s)
                """, (id_cliente, id_membresia, monto, metodo_pago, numero_referencia))
                id_pago_nuevo = cursor.lastrowid # Capturar ID del pago
                conn.commit()

                # 3) Registrar ingreso en finanzas (lógica implícita o manejada por triggers/vistas) y generar comprobante
                cursor.execute("SELECT nombre, apellido, identificacion, email FROM clientes WHERE id_cliente=%s", (id_cliente,))
                cli = cursor.fetchone() or {'nombre':'Cliente','apellido':'', 'identificacion':'', 'email':''}
                cli_identificacion = cli.get('identificacion')
                cli_email = cli.get('email')

                def etiqueta(d):
                    try:
                        d = int(d) if d is not None else None
                    except Exception:
                        d = None
                    if d is None: return 'personalizada'
                    if d <= 1: return 'por día'
                    if d == 15: return 'quincenal'
                    if 28 <= d <= 31: return 'mensual'
                    return f"{d} días"

                freq = etiqueta(dias_tipo)
                nombre_completo = f"{cli['nombre']} {cli['apellido']}".strip()
                # descripcion = f"Membresía {nombre_tipo or 'N/A'} ({freq}) - {nombre_completo}"
                # origen = f"membresía {freq}"
                
                # --- Generar Comprobante para la Membresía ---
                id_comp = None
                try:
                    # Preparar datos unificados
                    cliente_data = {
                        'nombre': nombre_completo,
                        'documento': cli_identificacion,
                        'correo': cli_email
                    }
                    items_comp = [{
                        'cantidad': 1,
                        'descripcion': f"Membresía {nombre_tipo or 'N/A'} ({freq})",
                        'precio_unitario': float(monto)
                    }]
                    
                    id_comp = generar_comprobante_unificado(
                        conn,
                        active_gym_id(),
                        'pago', # Tipo origen
                        id_pago_nuevo, # ID de la tabla pagos recién insertado
                        cliente_data,
                        items_comp,
                        metodo_pago,
                        float(monto)
                    )
                except Exception as e:
                    print(f"Error generando comprobante membresía: {e}")
                    id_comp = None
                # ---------------------------------------------

                # Insertar ingreso en FINANZAS (CRÍTICO: antes del commit)
                cursor.execute(
                    """
                    INSERT INTO finanzas(tipo, descripcion, monto, fecha, origen)
                    VALUES ('ingreso', %s, %s, NOW(), 'membresia')
                    """,
                    (f"Membresía {nombre_tipo or 'N/A'} ({freq}) - {nombre_completo}", monto)
                )
                
                conn.commit()

                flash("Membresía y pago registrados con éxito ✅", "success")
                if id_comp:
                    return redirect(url_for('ver_comprobante', id_comprobante=id_comp, back=url_for('obtener_membresias')))
                return redirect(url_for('obtener_membresias'))

            # ðŸ”¹ Obtener clientes
            cursor.execute("SELECT id_cliente, nombre, apellido FROM clientes")
            clientes = cursor.fetchall()

            # ðŸ”¹ Obtener tipos de membresÃ­a
            cursor.execute("SELECT id_tipo_membresia, nombre, duracion_dias FROM tipos_membresia")
            tipos = cursor.fetchall()

        return render_template('nueva_membresia.html', clientes=clientes, tipos=tipos)
    except Exception as e:
        flash(f"Error: {e}", "danger")
        return redirect(url_for('obtener_membresias'))
    finally:
        conn.close()



# ------------------ EDITAR MEMBRESÃA ------------------
@app.route('/membresias/editar/<int:id>', methods=['GET', 'POST'])
def editar_membresia(id):
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM membresias WHERE id_membresia=%s", (id,))
        membresia = cursor.fetchone()
        cursor.execute("SELECT id_cliente,nombre,apellido FROM clientes")
        clientes = cursor.fetchall()
        cursor.execute("SELECT * FROM tipos_membresia")
        tipos = cursor.fetchall()

    if request.method == 'POST':
        id_cliente = request.form['id_cliente']
        id_tipo = request.form['id_tipo_membresia']
        fecha_inicio = request.form['fecha_inicio']
        fecha_fin = request.form['fecha_fin']

        conn = obtener_conexion()
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE membresias
                SET id_cliente=%s, id_tipo_membresia=%s, fecha_inicio=%s, fecha_fin=%s
                WHERE id_membresia=%s
            """, (id_cliente, id_tipo, fecha_inicio, fecha_fin, id))
            conn.commit()
        flash("MembresÃ­a actualizada con Ã©xito", "success")
        return redirect(url_for('obtener_membresias'))

    return render_template('editar_membresia.html', membresia=membresia, clientes=clientes, tipos=tipos)


# ------------------ ELIMINAR MEMBRESÃA ------------------
@app.route('/membresias/eliminar/<int:id>', methods=['POST'])
def eliminar_membresia(id):
    try:
        conn = obtener_conexion()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM membresias WHERE id_membresia=%s", (id,))
            conn.commit()
        flash("MembresÃ­a eliminada con Ã©xito", "success")
        return redirect(url_for('obtener_membresias'))
    except Exception as e:
        flash(f"Error: {e}", "danger")
        return redirect(url_for('obtener_membresias'))
    finally:
        if conn: conn.close()

# -------- RUTAS PARA PAGOS --------
# ------------------ LISTAR PAGOS ------------------
@app.route('/pagos')
def obtener_pagos():
    try:
        conn = obtener_conexion()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT
                  p.*, 
                  c.nombre     AS nombre_cliente,
                  c.apellido   AS apellido_cliente,
                  t.nombre     AS tipo_membresia
                FROM pagos p
                JOIN clientes c ON p.id_cliente = c.id_cliente
                LEFT JOIN membresias m ON p.id_membresia = m.id_membresia
                LEFT JOIN tipos_membresia t ON m.id_tipo_membresia = t.id_tipo_membresia
                ORDER BY p.fecha_pago DESC
            """)
            pagos = cursor.fetchall()

            cursor.execute("SELECT id_cliente,nombre,apellido FROM clientes")
            clientes = cursor.fetchall()

            cursor.execute("""
                SELECT
                  m.id_membresia,
                  t.nombre AS tipo_membresia,
                  m.fecha_inicio,
                  m.fecha_fin
                FROM membresias m
                JOIN tipos_membresia t ON m.id_tipo_membresia=t.id_tipo_membresia
                WHERE m.fecha_fin>=CURRENT_DATE()
            """)
            membresias = cursor.fetchall()

        return render_template('pagos.html', pagos=pagos, clientes=clientes, membresias=membresias)
    except Exception as e:
        flash(f"Error: {e}", "danger")
        return redirect(url_for('index'))
    finally:
        if conn: conn.close()


# ------------------ NUEVO PAGO ------------------
@app.route('/pagos/nuevo', methods=['GET','POST'])
def nuevo_pago():
    if request.method=='POST':
        try:
            conn = obtener_conexion()
            with conn.cursor() as cursor:
                id_cliente = request.form['id_cliente']
                id_memb = request.form.get('id_membresia') or None
                monto = parse_cop(request.form['monto'])
                metodo = request.form['metodo_pago']

                cursor.execute("""
                    INSERT INTO pagos (id_cliente,id_membresia,monto,metodo_pago)
                    VALUES (%s,%s,%s,%s)
                """, (id_cliente, id_memb, monto, metodo))
                id_pago = cursor.lastrowid
                conn.commit()

                # Registrar ingreso en finanzas (si estÃ¡ asociado a una membresÃ­a)
                cursor.execute("SELECT nombre, apellido FROM clientes WHERE id_cliente=%s", (id_cliente,))
                cli = cursor.fetchone() or {'nombre':'Cliente','apellido':''}
                frecuencia = 'general'
                nombre_tipo = 'N/A'
                if id_memb:
                    cursor.execute("""
                        SELECT t.nombre, t.duracion_dias
                          FROM membresias m
                          JOIN tipos_membresia t ON m.id_tipo_membresia=t.id_tipo_membresia
                         WHERE m.id_membresia=%s
                    """, (id_memb,))
                    tipo = cursor.fetchone()
                    if tipo:
                        d = int(tipo['duracion_dias']) if tipo['duracion_dias'] is not None else None
                        if d is None:
                            frecuencia = 'personalizada'
                        elif d <= 1:
                            frecuencia = 'por dÃ­a'
                        elif d == 15:
                            frecuencia = 'quincenal'
                        elif 28 <= d <= 31:
                            frecuencia = 'mensual'
                        else:
                            frecuencia = f"{d} dÃ­as"
                        nombre_tipo = tipo['nombre']

                descripcion = f"Pago de membresÃ­a {nombre_tipo} ({frecuencia}) - {cli['nombre']} {cli['apellido']}"
                origen = f"membresÃ­a {frecuencia}" if id_memb else "pago"
                # Ingreso reflejado en comprobantes; no se registra en tabla finanzas
                conn.commit()

                flash("Pago registrado con Ã©xito âœ…", "success")
                return redirect(url_for('obtener_pagos'))
        except Exception as e:
            flash(f"Error: {e}", "danger")
            return redirect(url_for('obtener_pagos'))
        finally:
            if conn: conn.close()

    conn = obtener_conexion()
    with conn.cursor() as cursor:
        cursor.execute("SELECT id_cliente,nombre,apellido FROM clientes")
        clientes = cursor.fetchall()

        cursor.execute("""
            SELECT
              m.id_membresia,
              t.nombre AS tipo_membresia,
              m.fecha_inicio,
              m.fecha_fin
            FROM membresias m
            JOIN tipos_membresia t ON m.id_tipo_membresia=t.id_tipo_membresia
            WHERE m.fecha_fin>=CURRENT_DATE()
        """)
        membresias = cursor.fetchall()
    conn.close()

    return render_template('nuevo_pago.html', clientes=clientes, membresias=membresias)


# ------------------ ELIMINAR PAGO ------------------
@app.route('/pagos/eliminar/<int:id>', methods=['POST'])
def eliminar_pago(id):
    try:
        conn = obtener_conexion()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM pagos WHERE id_pago=%s", (id,))
            conn.commit()
            flash("Pago eliminado con Ã©xito", "success")
            return redirect(url_for('obtener_pagos'))
    except Exception as e:
        flash(f"Error: {e}", "danger")
        return redirect(url_for('obtener_pagos'))
    finally:
        if conn: conn.close()


# -------- RUTAS PARA PRODUCTOS --------
# =================== PRODUCTOS ===================


 
# =================== VENTAS ===================

# ----------------------------
# RUTINAS PERSONALIZADAS
# ----------------------------
# LISTADO
@app.route("/rutinas")
def rutinas():
    conn = obtener_conexion()
    rutinas = []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT r.id_rutina, r.titulo, r.descripcion,
                       r.fecha_inicio, r.fecha_fin,
                       c.id_cliente, c.nombre AS cliente_nombre, c.apellido AS cliente_apellido,
                       e.id_entrenador, e.nombre AS entrenador_nombre, e.apellido AS entrenador_apellido
                FROM rutinas_personalizadas r
                JOIN clientes c ON r.id_cliente = c.id_cliente
                JOIN entrenadores e ON r.id_entrenador = e.id_entrenador
                ORDER BY r.creado_en DESC
            """)
            rutinas = cur.fetchall()
    finally:
        conn.close()
    return render_template("rutinas.html", rutinas=rutinas)


# NUEVA
@app.route("/rutinas/nueva", methods=["GET", "POST"])
def rutinas_nueva():
    conn = obtener_conexion()
    try:
        if request.method == "POST":
            titulo = request.form["titulo"]
            descripcion = request.form.get("descripcion")
            id_cliente = request.form["id_cliente"]
            id_entrenador = request.form["id_entrenador"]
            fecha_inicio = request.form["fecha_inicio"]

            fi = datetime.strptime(fecha_inicio, "%Y-%m-%d").date()
            fecha_fin = fi + timedelta(days=29)

            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO rutinas_personalizadas
                      (titulo, descripcion, id_cliente, id_entrenador, fecha_inicio, fecha_fin, duracion_dias)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                """, (titulo, descripcion, id_cliente, id_entrenador, fecha_inicio, fecha_fin, 30))
                id_rutina = cur.lastrowid

                # Horarios de lunes a sÃ¡bado
                dias = ["Lunes","Martes","Miercoles","Jueves","Viernes","Sabado"]
                for d in dias:
                    hora = request.form.get(f"hora_{d}") or None
                    ejercicios = request.form.get(f"ej_{d}") or None
                    if hora or ejercicios:
                        cur.execute("""
                            INSERT INTO rutina_horarios (id_rutina, dia_semana, hora_programada, ejercicios)
                            VALUES (%s,%s,%s,%s)
                        """, (id_rutina, d, hora, ejercicios))
            conn.commit()
            flash("Rutina creada correctamente", "success")
            return redirect(url_for("rutinas"))
        else:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM clientes ORDER BY nombre")
                clientes = cur.fetchall()
                cur.execute("SELECT * FROM entrenadores ORDER BY nombre")
                entrenadores = cur.fetchall()
            return render_template("nueva_rutina.html", clientes=clientes, entrenadores=entrenadores)
    finally:
        conn.close()


# VER DETALLE
@app.route("/rutinas/<int:id_rutina>")
def rutinas_ver(id_rutina):
    conn = obtener_conexion()
    rutina, horarios, asistencias_dict = None, [], {}
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT r.*, c.id_cliente, c.nombre AS cliente_nombre, c.apellido AS cliente_apellido,
                       e.nombre AS entrenador_nombre, e.apellido AS entrenador_apellido
                FROM rutinas_personalizadas r
                JOIN clientes c ON r.id_cliente = c.id_cliente
                JOIN entrenadores e ON r.id_entrenador = e.id_entrenador
                WHERE r.id_rutina=%s
            """, (id_rutina,))
            rutina = cur.fetchone()

            if not rutina:
                flash("Rutina no encontrada", "danger")
                return redirect(url_for("rutinas"))

            cur.execute("SELECT * FROM rutina_horarios WHERE id_rutina=%s", (id_rutina,))
            horarios = cur.fetchall()

            cur.execute("SELECT * FROM asistencia_rutina WHERE id_rutina=%s", (id_rutina,))
            asistencias = cur.fetchall()
            asistencias_dict = {a["fecha"].isoformat(): a for a in asistencias}
    finally:
        conn.close()

    # Generar lista de fechas (lunes a sÃ¡bado) para el mes
    fechas = []
    fecha = rutina["fecha_inicio"]
    while fecha <= rutina["fecha_fin"]:
        if fecha.weekday() < 6:  # lunes=0 .. sÃ¡bado=5
            fechas.append(fecha)
        fecha += timedelta(days=1)

    return render_template("ver_rutina.html",
                           rutina=rutina,
                           horarios=horarios,
                           asistencias_dict=asistencias_dict,
                           fechas=fechas,
                           datetime=datetime)


# EDITAR
@app.route("/rutinas/editar/<int:id_rutina>", methods=["GET", "POST"])
def rutinas_editar(id_rutina):
    conn = obtener_conexion()
    try:
        with conn.cursor() as cur:
            if request.method == "POST":
                titulo = request.form["titulo"]
                descripcion = request.form.get("descripcion")
                id_cliente = request.form["id_cliente"]
                id_entrenador = request.form["id_entrenador"]
                fecha_inicio = request.form["fecha_inicio"]

                fi = datetime.strptime(fecha_inicio, "%Y-%m-%d").date()
                fecha_fin = fi + timedelta(days=29)

                cur.execute("""
                    UPDATE rutinas_personalizadas
                    SET titulo=%s, descripcion=%s, id_cliente=%s, id_entrenador=%s,
                        fecha_inicio=%s, fecha_fin=%s, duracion_dias=%s
                    WHERE id_rutina=%s
                """, (titulo, descripcion, id_cliente, id_entrenador, fecha_inicio, fecha_fin, 30, id_rutina))

                cur.execute("DELETE FROM rutina_horarios WHERE id_rutina=%s", (id_rutina,))
                dias = ["Lunes","Martes","Miercoles","Jueves","Viernes","Sabado"]
                for d in dias:
                    hora = request.form.get(f"hora_{d}") or None
                    ejercicios = request.form.get(f"ej_{d}") or None
                    if hora or ejercicios:
                        cur.execute("""
                            INSERT INTO rutina_horarios (id_rutina, dia_semana, hora_programada, ejercicios)
                            VALUES (%s,%s,%s,%s)
                        """, (id_rutina, d, hora, ejercicios))
                conn.commit()
                flash("Rutina actualizada", "success")
                return redirect(url_for("rutinas_ver", id_rutina=id_rutina))
            else:
                cur.execute("SELECT * FROM rutinas_personalizadas WHERE id_rutina=%s", (id_rutina,))
                rutina = cur.fetchone()
                cur.execute("SELECT * FROM clientes ORDER BY nombre")
                clientes = cur.fetchall()
                cur.execute("SELECT * FROM entrenadores ORDER BY nombre")
                entrenadores = cur.fetchall()
                cur.execute("SELECT * FROM rutina_horarios WHERE id_rutina=%s", (id_rutina,))
                horarios = cur.fetchall()
                return render_template("editar_rutina.html",
                                       rutina=rutina, clientes=clientes,
                                       entrenadores=entrenadores, horarios=horarios)
    finally:
        conn.close()


# ELIMINAR
@app.route("/rutinas/eliminar/<int:id_rutina>")
def rutinas_eliminar(id_rutina):
    conn = obtener_conexion()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rutinas_personalizadas WHERE id_rutina=%s", (id_rutina,))
        conn.commit()
        flash("Rutina eliminada", "success")
    finally:
        conn.close()
    return redirect(url_for("rutinas"))


# ASISTENCIA (JSON)
@app.route("/rutinas/marcar_asistencia", methods=["POST"])
def rutinas_marcar_asistencia():
    data = request.get_json()
    id_rutina = data.get("id_rutina")
    fecha = data.get("fecha")
    dia_semana = data.get("dia_semana")
    presente = data.get("presente", 0)
    hora = data.get("hora_realizacion")

    conn = obtener_conexion()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id_asistencia FROM asistencia_rutina WHERE id_rutina=%s AND fecha=%s",
                        (id_rutina, fecha))
            existe = cur.fetchone()
            if existe:
                cur.execute("""
                    UPDATE asistencia_rutina
                    SET presente=%s, hora_realizada=%s, dia_semana=%s
                    WHERE id_asistencia=%s
                """, (presente, hora, dia_semana, existe["id_asistencia"]))
            else:
                cur.execute("""
                    INSERT INTO asistencia_rutina (id_rutina, fecha, dia_semana, hora_realizada, presente)
                    VALUES (%s,%s,%s,%s,%s)
                """, (id_rutina, fecha, dia_semana, hora, presente))
        conn.commit()
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
    finally:
        conn.close()

    return jsonify({"status": "ok"})



@app.route('/membresias/proximas_vencer')
def proximas_membresias_vencer():
    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT
                    m.id_membresia,
                    c.nombre,
                    c.apellido,
                    t.nombre AS tipo_membresia,
                    m.fecha_fin
                FROM membresias m
                JOIN clientes c ON m.id_cliente = c.id_cliente
                LEFT JOIN tipos_membresia t ON m.id_tipo_membresia = t.id_tipo_membresia
                WHERE m.fecha_fin BETWEEN CURRENT_DATE() AND DATE_ADD(CURRENT_DATE(), INTERVAL 30 DAY)
                ORDER BY m.fecha_fin ASC
            """)
            membresias = cursor.fetchall()
        return render_template('proximas_membresias_vencer.html', membresias=membresias)
    finally:
        conn.close()

# -------- RUTAS PARA LOGIN, REGISTRO Y RECUPERACIÃ“N --------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        password = request.form['password']
        conn = obtener_conexion()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM usuarios WHERE usuario=%s AND password=%s", (usuario, password))
                user = cursor.fetchone()
                if user:
                    session['usuario'] = usuario
                    flash('Bienvenido, sesiÃ³n iniciada correctamente', 'success')
                    return redirect(url_for('index'))
                else:
                    flash('Usuario o contraseÃ±a incorrectos', 'danger')
        finally:
            conn.close()
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    flash('SesiÃ³n cerrada', 'info')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        usuario = request.form['usuario']
        email = request.form['email']
        password = request.form['password']
        conn = obtener_conexion()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM usuarios WHERE usuario=%s OR email=%s", (usuario, email))
                existe = cursor.fetchone()
                if existe:
                    flash('El usuario o correo ya existe', 'danger')
                else:
                    cursor.execute("INSERT INTO usuarios (usuario, email, password) VALUES (%s, %s, %s)", (usuario, email, password))
                    conn.commit()
                    flash('Cuenta creada correctamente, ahora puedes iniciar sesiÃ³n', 'success')
                    return redirect(url_for('login'))
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/forgot', methods=['GET', 'POST'])
def forgot():
    if request.method == 'POST':
        email = request.form['email']
        conn = obtener_conexion()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM usuarios WHERE email=%s", (email,))
                user = cursor.fetchone()
                if user:
                    # Simula envÃ­o de correo con cÃ³digo temporal
                    temp_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                    session['reset_email'] = email
                    session['reset_code'] = temp_code
                    flash(f'Se ha enviado un cÃ³digo de recuperaciÃ³n a tu correo: {temp_code}', 'info')
                    return redirect(url_for('reset_password'))
                else:
                    flash('Correo no encontrado', 'danger')
        finally:
            conn.close()
    return render_template('forgot.html')

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        code = request.form['code']
        password = request.form['password']
        if code == session.get('reset_code'):
            email = session.get('reset_email')
            conn = obtener_conexion()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE usuarios SET password=%s WHERE email=%s", (password, email))
                    conn.commit()
                    flash('ContraseÃ±a restablecida correctamente', 'success')
                    session.pop('reset_email', None)
                    session.pop('reset_code', None)
                    return redirect(url_for('login'))
            finally:
                conn.close()
        else:
            flash('CÃ³digo incorrecto', 'danger')
    return render_template('reset_password.html')

 
@app.route('/finanzas/configuracion', methods=['GET','POST'])
def finanzas_configuracion():
    conn = obtener_conexion()
    try:
        gid = active_gym_id()
        if request.method == 'POST':
            nombre = request.form.get('nombre')
            nit = request.form.get('nit')
            direccion = request.form.get('direccion')
            telefono = request.form.get('telefono')
            ciudad = request.form.get('ciudad')
            correo = request.form.get('correo')
            logo = request.form.get('logo')
            texto_legal = request.form.get('texto_legal')
            consecutivo = int(request.form.get('consecutivo_comprobante') or 0)
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE gimnasios
                       SET nombre=%s, nit=%s, direccion=%s, telefono=%s, ciudad=%s, correo=%s, logo=%s, texto_legal=%s, consecutivo_comprobante=%s
                     WHERE id_gimnasio=%s
                    """,
                    (nombre, nit, direccion, telefono, ciudad, correo, logo, texto_legal, consecutivo, gid)
                )
            conn.commit()
            flash("Configuración del gimnasio actualizada", "success")
            return redirect(url_for('configurar_comprobantes'))
        gym = _get_gym(conn, gid)
        return render_template('configuracion_gimnasio.html', gym=gym)
    finally:
        conn.close()

# filtrado se maneja en /finanzas

@app.route('/finanzas/exportar')
def finanzas_exportar():
    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id_comprobante as id, tipo, total as monto, fecha_generado as fecha FROM comprobantes ORDER BY fecha_generado DESC")
            rows = cursor.fetchall()
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        fname = f"finanzas_{ts}.csv"
        tmp = os.path.join(os.path.abspath(os.path.dirname(__file__)), fname)
        with open(tmp, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['ID', 'Tipo', 'Monto', 'Fecha'])
            for r in rows:
                w.writerow([r['id'], r['tipo'], r['monto'], r['fecha']])
        return send_file(tmp, as_attachment=True, download_name=fname, mimetype='text/csv')
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass
        conn.close()

@app.route('/pago/nuevo', methods=['POST'])
def pago_nuevo():
    id_gimnasio = int(request.form.get('id_gimnasio') or active_gym_id())
    id_pago = int(request.form.get('id_pago') or 0)
    cliente = request.form.get('cliente') or ''
    descripcion = request.form.get('descripcion') or 'Pago membresía'
    precio = float(request.form.get('precio') or request.form.get('monto') or 0)
    cantidad = int(request.form.get('cantidad') or 1)
    
    conn = obtener_conexion()
    try:
        items = [{'descripcion': descripcion, 'cantidad': cantidad, 'precio_unitario': precio}]
        cliente_data = {'nombre': cliente}
        
        id_comp = generar_comprobante_unificado(
            conn, id_gimnasio, 'pago', id_pago, cliente_data, items, 'Efectivo', precio * cantidad
        )
        flash("Comprobante generado", "success")
        return redirect(url_for('ver_comprobante', id_comprobante=id_comp, back=url_for('finanzas')))
    except Exception as e:
        flash(f"Error generando comprobante: {e}", "danger")
        return redirect(url_for('finanzas'))
    finally:
        conn.close()

@app.route('/venta/nueva', methods=['POST'])
def venta_nueva():
    id_gimnasio = int(request.form.get('id_gimnasio') or active_gym_id())
    id_producto = int(request.form.get('id_producto') or 0)
    cliente = request.form.get('cliente') or ''
    descripcion = request.form.get('descripcion') or 'Venta producto'
    precio = float(request.form.get('precio') or 0)
    cantidad = int(request.form.get('cantidad') or 1)
    
    conn = obtener_conexion()
    try:
        items = [{'descripcion': descripcion, 'cantidad': cantidad, 'precio_unitario': precio}]
        cliente_data = {'nombre': cliente}
        
        id_comp = generar_comprobante_unificado(
            conn, id_gimnasio, 'venta', None, cliente_data, items, 'Efectivo', precio * cantidad, id_producto=id_producto
        )
        flash("Comprobante generado", "success")
        return redirect(url_for('ver_comprobante', id_comprobante=id_comp, back=url_for('finanzas')))
    except Exception as e:
        flash(f"Error generando comprobante: {e}", "danger")
        return redirect(url_for('finanzas'))
    finally:
        conn.close()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
