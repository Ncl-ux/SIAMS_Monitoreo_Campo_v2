from pathlib import Path
from datetime import datetime
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from puntos import consultar_puntos,ids_historicos,guardar_punto

_gps=components.declare_component('siams_gps_local',path=str(Path(__file__).parent/'gps_campo'))

def selector_punto(sede,modulo):
    cat=consultar_puntos(sede)
    nombres=dict(zip(cat.punto_id,cat.nombre_punto))
    opciones=['']+sorted(set(nombres)|set(ids_historicos(sede)))
    return st.selectbox('Punto de monitoreo predeterminado (opcional)',opciones,format_func=lambda p: f'{nombres[p]} · {p}' if p in nombres else (f'{p} · sin ficha' if p else 'Escribir el código en la tabla'),key=f'punto_pred_{sede}_{modulo}',help='Completa los códigos vacíos de filas con mediciones al guardar; no reemplaza códigos escritos.')

def mostrar_puntos(sede):
    st.subheader('Catálogo de puntos de monitoreo')
    st.caption('Coordenadas geográficas WGS 84 / EPSG:4326, en grados decimales. No publiques ubicaciones privadas sin autorización.')
    cat=consultar_puntos(sede)
    registrados={r['punto_id']:r for r in cat.to_dict('records')}
    historicos=set(ids_historicos(sede))
    opciones=['']+sorted(set(registrados)|historicos)
    p=st.selectbox('Registrar o actualizar un punto',opciones,format_func=lambda k: (f"{registrados[k]['nombre_punto']} · {k}" if k in registrados else f'{k} · completar ficha') if k else 'Nuevo punto (código SIAMS automático)',key=f'catalogo_sel_{sede}')
    actual=registrados.get(p,{})
    pref=f'catalogo_{sede}_{p or "nuevo"}_'
    version=st.session_state.get(pref+'version',0)
    pref+=str(version)+'_'
    gps=_gps(key=pref+'gps',default=None)
    def inicial(c):
        v=actual.get(c,'')
        return '' if v is None or pd.isna(v) else str(v)
    if gps and gps.get('nonce')!=st.session_state.get(pref+'nonce'):
        st.session_state[pref+'nonce']=gps['nonce']
        for c in ('latitud','longitud','altitud_m','precision_gps_m'):
            st.session_state[pref+c]='' if gps.get(c) is None else f'{gps[c]:.8f}'.rstrip('0').rstrip('.')
        st.session_state[pref+'referencia_altitud']='Elipsoidal WGS 84 (GPS)' if gps.get('altitud_m') is not None else ''
    st.caption('GPS funciona únicamente si el navegador permite ubicación. Por HTTP en red local puede estar bloqueado; siempre puedes pegar coordenadas de una aplicación GPS offline.')
    a,b=st.columns(2)
    with a:
        nombre=st.text_input('Nombre del punto *',value=inicial('nombre_punto') or p,key=pref+'nombre')
        lat=st.text_input('Latitud *',value=inicial('latitud'),key=pref+'latitud')
        alt=st.text_input('Altitud (m), opcional',value=inicial('altitud_m'),key=pref+'altitud_m')
    with b:
        codigo=st.text_input('Código oficial (opcional)',value=inicial('codigo_oficial'),key=pref+'codigo')
        lon=st.text_input('Longitud *',value=inicial('longitud'),key=pref+'longitud')
        precision=st.text_input('Precisión horizontal (m), opcional',value=inicial('precision_gps_m'),key=pref+'precision_gps_m')
    ref=st.text_input('Referencia de altitud (obligatoria si indicas altitud)',value=inicial('referencia_altitud'),key=pref+'referencia_altitud',placeholder='Ej. ortométrica sobre nivel del mar, datum conocido')
    desc=st.text_area('Descripción de la ubicación',value=inicial('descripcion_ubicacion'),key=pref+'desc')
    guardar=st.button('Guardar ficha del punto',type='primary',key=pref+'guardar')
    if guardar:
        datos=dict(nombre_punto=nombre,codigo_oficial=codigo,latitud=lat,longitud=lon,altitud_m=alt,precision_gps_m=precision,referencia_altitud=ref,descripcion_ubicacion=desc)
        def iguales(a,b):
            try: return abs(float(str(a).replace(',','.'))-float(b))<1e-7
            except (ValueError,TypeError): return False
        if gps and iguales(lat,gps.get('latitud')) and iguales(lon,gps.get('longitud')):
            datos.update(origen_coordenadas='GPS del dispositivo',fecha_coordenadas=gps['fecha_coordenadas'])
        elif actual and iguales(lat,actual.get('latitud')) and iguales(lon,actual.get('longitud')):
            datos.update(origen_coordenadas=actual['origen_coordenadas'],fecha_coordenadas=actual['fecha_coordenadas'])
        else:
            datos.update(origen_coordenadas='Manual',fecha_coordenadas=datetime.now().astimezone().isoformat(timespec='seconds'))
        try:
            pid=guardar_punto(sede,datos,p or None)
            st.session_state[f'catalogo_msg_{sede}']=f'Ficha guardada: {pid}'
            st.session_state[f'catalogo_{sede}_{p or "nuevo"}_version']=version+1
            st.rerun()
        except ValueError as e: st.error(str(e))
    if msg:=st.session_state.pop(f'catalogo_msg_{sede}',None): st.success(msg)
    st.divider()
    st.markdown('**Puntos registrados**')
    st.dataframe(cat,hide_index=True,width='stretch')
    st.download_button('Exportar catálogo · CSV',cat.to_csv(index=False).encode('utf-8-sig'),file_name=f'puntos_{sede}.csv',mime='text/csv',key=f'catalogo_csv_{sede}')
    sin_ficha=sorted(historicos-set(registrados))
    if sin_ficha: st.caption('Puntos históricos pendientes de georreferenciar: '+', '.join(sin_ficha))
