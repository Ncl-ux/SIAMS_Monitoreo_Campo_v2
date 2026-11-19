"""Protocolo de campaña local; no modifica registros históricos ni envía datos."""
from contextlib import closing
from datetime import datetime, date, timedelta, timezone
from uuid import uuid4
import base64, binascii, csv, io, json, math, sqlite3, zipfile
import pandas as pd
from almacenamiento import conexion
from nucleo import SEDES

TZ = timezone(timedelta(hours=-5))
VERSION = '1.0'
CAMPOS = ['registro_id','version','dispositivo_id','sede','punto_id','nombre_punto','codigo_oficial','tipo_agua','frecuencia','inicio','fin','lluvia_mm','nivel_m','referencia_nivel','ce_us_cm','ph','temperatura_c','muestra_isotopica','frasco_id','laboratorio','delta18o','delta2h','d_excess','equipo','fecha_calibracion','operador','latitud','longitud','precision_gps_m','altitud_m','referencia_altitud','observaciones','qc_flag','creado','actualizado']
NUM = {'lluvia_mm','nivel_m','ce_us_cm','ph','temperatura_c','delta18o','delta2h','latitud','longitud','precision_gps_m','altitud_m'}
TIPOS = ['Lluvia','Subterránea','Superficial','Otra']
MAX_FOTOS = 5
MAX_BYTES = 2_000_000

def ahora(): return datetime.now(TZ).isoformat(timespec='seconds')
def texto(v): return '' if v is None else str(v).strip()
def numero(v):
    if v is None or texto(v)=='': return None
    try: n=float(texto(v).replace(',','.'))
    except (ValueError,TypeError): raise ValueError('Valor numérico inválido: '+texto(v)) from None
    if not math.isfinite(n): raise ValueError('No se aceptan números no finitos')
    return n

def fecha(v):
    try:
        x=datetime.fromisoformat(texto(v).replace('Z','+00:00'))
        if x.tzinfo is None: x=x.replace(tzinfo=TZ)
        return x.astimezone(TZ)
    except (ValueError,TypeError): return None

def calidad(r, instante=None):
    flags=[]
    def rango(c,a,b): return r.get(c) is not None and not a<=r[c]<=b
    for c,a,b,f in [('ph',0,14,'R_PH'),('ce_us_cm',0,100000,'R_CE'),('temperatura_c',-5,60,'R_TEMP'),('nivel_m',0,1000,'R_NIVEL'),('lluvia_mm',0,1000,'R_LLUVIA')]:
        if rango(c,a,b): flags.append(f)
    if rango('latitud',-5,14) or rango('longitud',-82,-66): flags.append('R_COORD')
    if rango('delta18o',-40,20) or rango('delta2h',-300,100): flags.append('R_ISO')
    if r.get('latitud') is None or r.get('longitud') is None: flags.append('F_GPS')
    ini,fin=fecha(r.get('inicio')),fecha(r.get('fin'))
    if not ini or not fin or fin<ini or ini>(instante or datetime.now(TZ)): flags.append('F_FECHA')
    if r.get('muestra_isotopica')=='Sí' and not r.get('frasco_id'): flags.append('F_FRASCO')
    cal=r.get('fecha_calibracion')
    if cal:
        try:
            dias=(ini.date()-date.fromisoformat(cal)).days if ini else None
            if dias is None or not 0<=dias<=365: flags.append('F_CALIB')
        except ValueError: flags.append('F_CALIB')
    if (r.get('tipo_agua')=='Lluvia' and r.get('lluvia_mm') is None) or (r.get('tipo_agua')=='Subterránea' and (r.get('nivel_m') is None or not r.get('referencia_nivel'))) or not r.get('tipo_agua'): flags.append('F_TIPO')
    return '|'.join(flags) or 'OK'

def validar_fotos(fotos):
    if not isinstance(fotos,list) or len(fotos)>MAX_FOTOS: raise ValueError('Máximo cinco fotos por registro')
    out=[]
    for f in fotos:
        if not isinstance(f,dict) or f.get('mime') not in ('image/jpeg','image/png','image/webp'): raise ValueError('Foto no admitida')
        try: raw=base64.b64decode(f.get('base64',''),validate=True)
        except (ValueError,TypeError,binascii.Error): raise ValueError('Foto inválida') from None
        signatures={'image/jpeg':raw.startswith(b'\xff\xd8\xff'),'image/png':raw.startswith(b'\x89PNG\r\n\x1a\n'),'image/webp':raw[:4]==b'RIFF' and raw[8:12]==b'WEBP'}
        if not raw or len(raw)>MAX_BYTES or not signatures[f['mime']]: raise ValueError('Foto inválida o superior a 2 MB')
        out.append({'nombre':texto(f.get('nombre'))[:150], 'mime':f['mime'],'base64':base64.b64encode(raw).decode('ascii')})
    return out

def normalizar(raw):
    r={c:numero(raw.get(c)) if c in NUM else texto(raw.get(c)) for c in CAMPOS if c not in ('qc_flag','d_excess')}
    if r['sede'] not in SEDES: raise ValueError('Sede desconocida')
    if not r['punto_id'] or not r['operador']: raise ValueError('Ingresa el punto y el operador')
    if r['tipo_agua'] not in TIPOS: raise ValueError('Selecciona un tipo de agua')
    if r['muestra_isotopica'] not in ('Sí','No'): raise ValueError('Indica si tomó muestra isotópica')
    if r['precision_gps_m'] is not None and r['precision_gps_m']<0: raise ValueError('Precisión GPS negativa')
    for c in ('inicio','fin'):
        f=fecha(r[c]); r[c]=f.isoformat(timespec='seconds') if f else r[c]
    r['registro_id']=r['registro_id'] or str(uuid4())
    if len(r['registro_id'])>128: raise ValueError('ID de registro demasiado largo')
    r['version']=VERSION
    r['creado']=r['creado'] or ahora(); r['actualizado']=r['actualizado'] or r['creado']
    r['d_excess']=round(r['delta2h']-8*r['delta18o'],6) if r['delta2h'] is not None and r['delta18o'] is not None else None
    r['qc_flag']=calidad(r)
    r['fotos']=validar_fotos(raw.get('fotos',[]))
    return r

def _tabla(cx):
    cx.execute('CREATE TABLE IF NOT EXISTS protocolo_campo (registro_id TEXT PRIMARY KEY, sede TEXT NOT NULL, datos TEXT NOT NULL)')

def almacenar_lote(registros,sede=None):
    if not isinstance(registros,list): raise ValueError('Se esperaba una lista de registros')
    nuevos=[normalizar(x) for x in registros]
    if sede and any(r['sede']!=sede for r in nuevos): raise ValueError('El archivo contiene registros de otra sede')
    n=0; omitidos=0
    with closing(conexion()) as cx,cx:
        _tabla(cx)
        for r in nuevos:
            old=cx.execute('SELECT datos FROM protocolo_campo WHERE registro_id=?',(r['registro_id'],)).fetchone()
            if old:
                previo=json.loads(old[0]); comparar=lambda d:{k:v for k,v in d.items() if k not in ('qc_flag','actualizado')}
                if comparar(previo)!=comparar(r): raise ValueError('ID existente con datos diferentes; no se sobrescribió: '+r['registro_id'])
                omitidos+=1; continue
            cx.execute('INSERT INTO protocolo_campo VALUES (?,?,?)',(r['registro_id'],r['sede'],json.dumps(r,ensure_ascii=False,allow_nan=False))); n+=1
    return n,omitidos

def consultar_protocolo(sede):
    with closing(conexion()) as cx,cx:
        _tabla(cx)
        return [json.loads(x[0]) for x in cx.execute('SELECT datos FROM protocolo_campo WHERE sede=? ORDER BY rowid DESC',(sede,))]

def actualizar_laboratorio(sede,rid,o,h):
    with closing(conexion()) as cx,cx:
        _tabla(cx); cx.execute('BEGIN IMMEDIATE')
        row=cx.execute('SELECT datos FROM protocolo_campo WHERE sede=? AND registro_id=?',(sede,rid)).fetchone()
        if not row: raise ValueError('Registro inexistente')
        r=json.loads(row[0]); r.update(delta18o=o,delta2h=h,actualizado=ahora()); r=normalizar(r)
        cx.execute('UPDATE protocolo_campo SET datos=? WHERE registro_id=? AND sede=?',(json.dumps(r,ensure_ascii=False,allow_nan=False),rid,sede))
    return r

def tabla(registros): return pd.DataFrame([{c:r.get(c) for c in CAMPOS} for r in registros],columns=CAMPOS)
def exportar_csv(registros): return tabla(registros).to_csv(index=False).encode('utf-8-sig')
def exportar_json(registros): return json.dumps({'formato':'SIAMS-campo','version':VERSION,'registros':registros},ensure_ascii=False,allow_nan=False,indent=2).encode('utf-8')
def leer_json(raw):
    d=json.loads(raw); registros=d.get('registros') if isinstance(d,dict) else d
    if not isinstance(registros,list) or any(not isinstance(r,dict) or not r.get('registro_id') for r in registros): raise ValueError('JSON de campaña inválido o sin IDs')
    return registros

def exportar_geojson(registros):
    fs=[]
    for r in registros:
        x,y=r.get('longitud'),r.get('latitud')
        if x is None or y is None or not (-180<=x<=180 and -90<=y<=90): continue
        fs.append({'type':'Feature','geometry':{'type':'Point','coordinates':[x,y]},'properties':{k:v for k,v in r.items() if k!='fotos'}})
    return json.dumps({'type':'FeatureCollection','features':fs},ensure_ascii=False,allow_nan=False,indent=2).encode('utf-8')

def exportar_zip(registros):
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('campana.csv',exportar_csv(registros)); z.writestr('campana.json',exportar_json(registros)); z.writestr('campana.geojson',exportar_geojson(registros))
        for i,r in enumerate(registros,1):
            for j,f in enumerate(r.get('fotos',[]),1): z.writestr(f'fotos/registro_{i:05d}_{j}.{ {"image/jpeg":"jpg","image/png":"png","image/webp":"webp"}[f["mime"]]}',base64.b64decode(f['base64']))
    return buf.getvalue()
