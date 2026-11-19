"""Catálogo local de puntos; conserva los identificadores históricos de mediciones."""
from contextlib import closing
from datetime import datetime
import json
import math
import sqlite3
from uuid import uuid4
import pandas as pd
from almacenamiento import conexion
from nucleo import SEDES

CAMPOS = ['punto_id','nombre_punto','codigo_oficial','latitud','longitud','altitud_m','referencia_altitud','precision_gps_m','origen_coordenadas','fecha_coordenadas','descripcion_ubicacion','actualizado']
META = CAMPOS[1:]

def _tabla(cx):
    cx.execute('''CREATE TABLE IF NOT EXISTS puntos_monitoreo (
        sede TEXT NOT NULL, punto_id TEXT NOT NULL, nombre_punto TEXT NOT NULL,
        codigo_oficial TEXT NOT NULL DEFAULT '', latitud REAL NOT NULL, longitud REAL NOT NULL,
        altitud_m REAL, referencia_altitud TEXT NOT NULL DEFAULT '', precision_gps_m REAL,
        origen_coordenadas TEXT NOT NULL, fecha_coordenadas TEXT NOT NULL,
        descripcion_ubicacion TEXT NOT NULL DEFAULT '', actualizado TEXT NOT NULL,
        PRIMARY KEY(sede,punto_id))''')
    cx.execute('''CREATE UNIQUE INDEX IF NOT EXISTS puntos_codigo_oficial
        ON puntos_monitoreo(sede, codigo_oficial COLLATE NOCASE) WHERE codigo_oficial <> '' ''')

def _sede(sede):
    if sede not in SEDES: raise ValueError('Sede desconocida')

def consultar_puntos(sede):
    _sede(sede)
    with closing(conexion()) as cx, cx:
        _tabla(cx)
        return pd.read_sql_query('SELECT '+','.join(CAMPOS)+' FROM puntos_monitoreo WHERE sede=? ORDER BY nombre_punto,punto_id',cx,params=(sede,))

def ids_historicos(sede):
    _sede(sede)
    with closing(conexion()) as cx:
        filas = cx.execute('SELECT datos FROM registros WHERE sede=?',(sede,)).fetchall()
    return sorted({str(p).strip() for (raw,) in filas if (p:=json.loads(raw).get('punto_id')) and str(p).strip()})

def _numero(v,nombre, minimo=None,maximo=None,obligatorio=False):
    if v is None or str(v).strip()=='':
        if obligatorio: raise ValueError(f'{nombre}: obligatorio')
        return None
    try: x=float(str(v).strip().replace(',','.'))
    except (ValueError,TypeError): raise ValueError(f'{nombre}: número inválido') from None
    if not math.isfinite(x) or (minimo is not None and x<minimo) or (maximo is not None and x>maximo):
        raise ValueError(f'{nombre}: fuera del rango permitido')
    return x

def guardar_punto(sede, datos, punto_id=None):
    _sede(sede)
    nombre=str(datos.get('nombre_punto') or '').strip()
    if not nombre: raise ValueError('Ingresa el nombre del punto')
    lat=_numero(datos.get('latitud'),'Latitud',-90,90,True)
    lon=_numero(datos.get('longitud'),'Longitud',-180,180,True)
    alt=_numero(datos.get('altitud_m'),'Altitud')
    precision=_numero(datos.get('precision_gps_m'),'Precisión GPS',0)
    referencia=str(datos.get('referencia_altitud') or '').strip()
    if alt is not None and not referencia: raise ValueError('Especifica la referencia de altitud')
    origen=datos.get('origen_coordenadas','Manual')
    if origen not in ('Manual','GPS del dispositivo'): raise ValueError('Origen de coordenadas desconocido')
    fecha=str(datos.get('fecha_coordenadas') or datetime.now().astimezone().isoformat(timespec='seconds'))
    try: datetime.fromisoformat(fecha.replace('Z','+00:00'))
    except ValueError: raise ValueError('Fecha de coordenadas inválida') from None
    codigo=str(datos.get('codigo_oficial') or '').strip()
    descripcion=str(datos.get('descripcion_ubicacion') or '').strip()
    if punto_id is not None and not str(punto_id).strip(): raise ValueError('Identificador vacío')
    historicos=set(ids_historicos(sede))
    with closing(conexion()) as cx:
        with cx:
            _tabla(cx)
            cx.execute('BEGIN IMMEDIATE') if not cx.in_transaction else None
            existentes={r[0] for r in cx.execute('SELECT punto_id FROM puntos_monitoreo WHERE sede=?',(sede,))}
            if punto_id is None:
                punto_id='SIAMS-'+uuid4().hex.upper()
                while punto_id in existentes or punto_id in historicos: punto_id='SIAMS-'+uuid4().hex.upper()
            elif punto_id not in existentes and punto_id not in historicos:
                raise ValueError('El identificador histórico no existe en esta sede')
            duplicado=cx.execute('''SELECT punto_id FROM puntos_monitoreo WHERE sede=? AND punto_id<>?
                AND nombre_punto COLLATE NOCASE=? AND abs(latitud-?)<0.000001 AND abs(longitud-?)<0.000001''',(sede,punto_id,nombre,lat,lon)).fetchone()
            if duplicado: raise ValueError(f'Ya existe un punto con ese nombre y ubicación: {duplicado[0]}')
            valores=(sede,punto_id,nombre,codigo,lat,lon,alt,referencia if alt is not None else '',precision,origen,fecha,descripcion,datetime.now().astimezone().isoformat(timespec='seconds'))
            try:
                cx.execute('INSERT INTO puntos_monitoreo (sede,'+','.join(CAMPOS)+') VALUES ('+','.join('?' for _ in valores)+') ON CONFLICT(sede,punto_id) DO UPDATE SET '+','.join(f'{c}=excluded.{c}' for c in META),valores)
            except sqlite3.IntegrityError as exc: raise ValueError('Ese código oficial ya está asociado a otro punto de la sede') from exc
    return punto_id

def adjuntar_puntos(df,sede):
    """Metadatos actuales del catálogo; no implican coordenadas medidas en cada visita."""
    if 'punto_id' not in df: return df.copy()
    catalogo=consultar_puntos(sede)
    return df.drop(columns=[c for c in META if c in df],errors='ignore').merge(catalogo,on='punto_id',how='left',validate='many_to_one')

def completar_punto(df,modulo,punto_id):
    """Rellena únicamente filas activas sin código y conserva los ingresados explícitamente."""
    from nucleo import MODULOS,vacio
    out=df.copy()
    if not punto_id: return out
    utiles=[c for c in MODULOS[modulo]['columnas'] if c not in ('fecha','fecha_hora','magnitud','punto_id')]
    for idx,row in out.iterrows():
        if vacio(row.get('punto_id')) and any(not vacio(row.get(c)) for c in utiles): out.at[idx,'punto_id']=punto_id
    return out
