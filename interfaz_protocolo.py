import base64
from datetime import datetime
import pandas as pd
import streamlit as st
from puntos import consultar_puntos, ids_historicos, guardar_punto
from interfaz_puntos import _gps
from protocolo_campo import (TIPOS,NUM,TZ,MAX_BYTES,almacenar_lote,consultar_protocolo,actualizar_laboratorio,tabla,leer_json,exportar_csv,exportar_json,exportar_geojson,exportar_zip)
from nucleo import estadistica_descriptiva, correlaciones

VARIABLES=['lluvia_mm','nivel_m','ph','ce_us_cm','temperatura_c','delta18o','delta2h','d_excess']
LABELS=dict(lluvia_mm='Lluvia (mm)',nivel_m='Nivel (m)',ph='pH',ce_us_cm='CE (µS/cm)',temperatura_c='Temperatura (°C)',delta18o='δ18O (‰)',delta2h='δ2H (‰)',d_excess='Exceso de deuterio (‰)')

def mostrar_protocolo(sede):
    st.subheader('Protocolo integrado de campaña')
    st.caption('Captura de campo y laboratorio · UTC−05:00 · coordenadas WGS84 · las banderas QC conservan la medición original.')
    captura,consulta,lab,analisis,movil=st.tabs(['Captura','Registros y exportación','Laboratorio isotópico','Análisis','Importar / móvil'])
    registros=consultar_protocolo(sede)
    cat=consultar_puntos(sede); nombres=dict(zip(cat.punto_id,cat.nombre_punto)); fichas={r['punto_id']:r for r in cat.to_dict('records')}
    with captura:
        pref=f'protocolo_{sede}_'; v=st.session_state.get(pref+'v',0); k=f'{pref}{v}_'
        opciones=['']+sorted(set(nombres)|set(ids_historicos(sede))|{r['punto_id'] for r in registros})
        p=st.selectbox('Punto registrado (o nuevo)',opciones,format_func=lambda x:f'{nombres.get(x,x)} · {x}' if x else 'Nuevo punto / identificador manual',key=k+'p')
        k+=p+"_"
        ficha=fichas.get(p,{})
        gps=_gps(key=k+'gps',default=None)
        if gps and gps.get('nonce')!=st.session_state.get(k+'nonce'):
            st.session_state[k+'nonce']=gps['nonce']
            for c in ('latitud','longitud','precision_gps_m','altitud_m'):
                st.session_state[k+c]='' if gps.get(c) is None else str(gps[c])
            st.session_state[k+'referencia_altitud']='Elipsoidal WGS84' if gps.get('altitud_m') is not None else ''
        def campo(c,label,default='',**kwargs):
            val=ficha.get(c,default); val='' if val is None or pd.isna(val) else str(val)
            return st.text_input(label,value=val,key=k+c,**kwargs)
        with st.form(k+'form'):
            a,b=st.columns(2)
            with a:
                manual=st.text_input('ID del punto (vacío = generar uno nuevo)',disabled=bool(p),key=k+'manual')
                nombre=campo('nombre_punto','Nombre del punto',p)
                codigo=campo('codigo_oficial','Código oficial (opcional)')
                tipo=st.selectbox('Tipo de agua',TIPOS)
                frecuencia=st.text_input('Frecuencia',placeholder='Ej. evento, diaria, mensual')
                inicio=st.text_input('Inicio (AAAA-MM-DD HH:MM)',datetime.now(TZ).strftime('%Y-%m-%d %H:%M'))
                fin=st.text_input('Fin (AAAA-MM-DD HH:MM)',datetime.now(TZ).strftime('%Y-%m-%d %H:%M'))
                dispositivo=st.text_input('ID del dispositivo')
                operador=st.text_input('Operador *')
            with b:
                lluvia=st.text_input('Lluvia acumulada (mm)'); nivel=st.text_input('Nivel (m)'); ref=st.text_input('Referencia de nivel (brocal, etc.)')
                ce=st.text_input('CE (µS/cm)'); ph=st.text_input('pH'); temp=st.text_input('Temperatura (°C)')
                iso=st.radio('¿Se tomó muestra isotópica?', ['No','Sí'],horizontal=True)
                frasco=st.text_input('ID del frasco'); laboratorio=st.text_input('Laboratorio de destino'); equipo=st.text_input('Equipo multiparámetro'); cal=st.text_input('Fecha calibración (AAAA-MM-DD)')
            st.markdown('**Coordenadas de la visita**')
            st.caption('Si seleccionas un punto, se sugieren las coordenadas de su ficha; comprueba que corresponden a la visita. GPS puede requerir HTTPS.')
            a,b=st.columns(2)
            with a:
                lat=campo('latitud','Latitud'); alt=campo('altitud_m','Altitud (m)'); refalt=campo('referencia_altitud','Referencia de altitud')
            with b:
                lon=campo('longitud','Longitud'); prec=campo('precision_gps_m','Precisión horizontal (m)')
            fotos=st.file_uploader('Fotos (hasta 5, 2 MB por foto)',type=['jpg','jpeg','png','webp'],accept_multiple_files=True)
            obs=st.text_area('Observaciones'); guardar=st.form_submit_button('Guardar visita',type='primary')
        if guardar:
            try:
                from uuid import uuid4
                from protocolo_campo import normalizar
                pid=p or manual.strip() or 'SIAMS-'+uuid4().hex.upper()
                raw=dict(sede=sede,punto_id=pid,nombre_punto=nombre,codigo_oficial=codigo,tipo_agua=tipo,frecuencia=frecuencia,inicio=inicio,fin=fin,dispositivo_id=dispositivo,operador=operador,lluvia_mm=lluvia,nivel_m=nivel,referencia_nivel=ref,ce_us_cm=ce,ph=ph,temperatura_c=temp,muestra_isotopica=iso,frasco_id=frasco,laboratorio=laboratorio,equipo=equipo,fecha_calibracion=cal,latitud=lat,longitud=lon,precision_gps_m=prec,altitud_m=alt,referencia_altitud=refalt,observaciones=obs)
                if len(fotos)>5 or any(f.size>MAX_BYTES for f in fotos): raise ValueError('Máximo 5 fotos de 2 MB cada una')
                raw['fotos']=[dict(nombre=f.name,mime=f.type,base64=base64.b64encode(f.getvalue()).decode('ascii')) for f in fotos]
                r=normalizar(raw); almacenar_lote([r],sede)
                st.session_state[pref+'msg']=f"Visita guardada · {pid} · QC: {r['qc_flag']}"; st.session_state[pref+'v']=v+1; st.rerun()
            except ValueError as e: st.error(str(e))
        if msg:=st.session_state.pop(pref+'msg',None): st.success(msg)
    with consulta:
        df=tabla(registros); st.dataframe(df,width='stretch',hide_index=True)
        st.caption('Las exportaciones contienen coordenadas privadas: compartir únicamente con personas autorizadas. CSV y GeoJSON no contienen las imágenes.')
        for label,fn,ext,mime in [('CSV',exportar_csv,'csv','text/csv'),('JSON con fotos',exportar_json,'json','application/json'),('GeoJSON',exportar_geojson,'geojson','application/geo+json'),('Respaldo ZIP con fotos',exportar_zip,'zip','application/zip')]:
            st.download_button(label,fn(registros),f'siams_campana_{sede}.{ext}',mime=mime,key=f'prot_exp_{sede}_{ext}')
        if registros:
            r=st.selectbox('Ver evidencia',registros,format_func=lambda r:f"{r['punto_id']} · {r['inicio']} · {r['registro_id'][:8]}",key='prot_evidencia_'+sede)
            for f in r.get('fotos',[]): st.image(base64.b64decode(f['base64']),caption=f['nombre'])
    with lab:
        rr=[r for r in registros if r['muestra_isotopica']=='Sí']
        if rr:
            r=st.selectbox('Muestra de laboratorio',rr,format_func=lambda r:f"{r['frasco_id'] or '(sin frasco)'} · {r['punto_id']} · {r['inicio']}",key='prot_lab_'+sede)
            with st.form('lab_'+r['registro_id']):
                o=st.text_input('δ18O (‰)',value='' if r['delta18o'] is None else str(r['delta18o'])); h=st.text_input('δ2H (‰)',value='' if r['delta2h'] is None else str(r['delta2h']))
                guardar_lab=st.form_submit_button('Guardar resultados')
            if guardar_lab:
                try: actualizar_laboratorio(sede,r['registro_id'],o,h); st.rerun()
                except ValueError as e: st.error(str(e))
            st.caption(f"d-excess = δ2H − 8 × δ18O: {r['d_excess'] if r['d_excess'] is not None else 'Pendiente'} ‰ · QC: {r['qc_flag']}")
        else: st.info('No hay muestras isotópicas registradas.')
    with analisis:
        df=tabla(registros)
        if df.empty: st.info('Registra una visita para iniciar el análisis.')
        else:
            st.metric('Visitas',len(df)); st.metric('Registros con alertas QC',int((df.qc_flag!='OK').sum()))
            incluir=st.checkbox('Incluir registros con alertas QC',value=False,key='prot_qc_'+sede)
            tipos=st.multiselect('Tipos de agua',sorted(df.tipo_agua.unique()),default=sorted(df.tipo_agua.unique()),key='prot_tipos_'+sede)
            pts=st.multiselect('Puntos',sorted(df.punto_id.unique()),default=sorted(df.punto_id.unique()),key='prot_pts_'+sede)
            d=df[df.tipo_agua.isin(tipos)&df.punto_id.isin(pts)].copy(); d=d if incluir else d[d.qc_flag=='OK']
            if d.empty: st.info('Sin registros para los filtros seleccionados.')
            else:
                vars_stats=VARIABLES.copy()
                niveles=d[d.nivel_m.notna()]
                if len(niveles[['punto_id','referencia_nivel']].drop_duplicates())>1:
                    vars_stats.remove('nivel_m')
                    st.caption('El nivel se excluye de los estadísticos agrupados si mezcla puntos o referencias. Filtra un punto para analizar niveles comparables.')
                stats=estadistica_descriptiva(d,vars_stats)
                if not stats.empty:
                    stats['Variable']=stats['Variable'].replace(LABELS); st.dataframe(stats,width='stretch',hide_index=True)
                    st.download_button('Estadísticos CSV',stats.to_csv(index=False).encode('utf-8-sig'),f'estadistica_campana_{sede}.csv',key='prot_stats_'+sede)
                corr=correlaciones(d,vars_stats)
                if not corr.empty: st.dataframe(corr.rename(index=LABELS,columns=LABELS).round(3),width='stretch')
                disponibles=[c for c in VARIABLES if d[c].notna().any()]
                if disponibles:
                    var=st.selectbox('Serie temporal',disponibles,format_func=LABELS.get,key='prot_var_'+sede)
                    series=d.copy(); series['fecha']=pd.to_datetime(series.inicio,errors='coerce',utc=True).dt.tz_convert(TZ)
                    series=series.dropna(subset=['fecha',var])
                    if var=='nivel_m':
                        refs=sorted(series.referencia_nivel.unique()); ref=st.selectbox('Referencia del nivel',refs,key='prot_ref_'+sede) if refs else None
                        series=series[series.referencia_nivel==ref]
                    if not series.empty: st.line_chart(series,x='fecha',y=var,color='punto_id')
                iso=d.dropna(subset=['delta18o','delta2h'])
                if not iso.empty: st.markdown('**Relación isotópica δ18O – δ2H (‰)**'); st.scatter_chart(iso,x='delta18o',y='delta2h',color='punto_id')
            st.caption('Estadística descriptiva; no equivale a diagnóstico de calidad del agua ni a un modelo predictivo. Las alertas se excluyen por defecto.')
    with movil:
        st.markdown('**Importar registros del capturador móvil**')
        st.caption('Exporta JSON en el celular y transfiérelo a este computador. La importación no reemplaza registros existentes; los conflictos se rechazan.')
        archivo=st.file_uploader('JSON del capturador móvil',type=['json'],key='prot_import_'+sede)
        if archivo and st.button('Importar campaña',key='prot_import_btn_'+sede):
            try:
                n,omitidos=almacenar_lote(leer_json(archivo.getvalue()),sede); st.session_state["prot_import_msg_"+sede]=f"{n} importados; {omitidos} ya existentes."; st.rerun()
            except (ValueError,UnicodeError,TypeError) as e: st.error(str(e))
        if msg:=st.session_state.pop('prot_import_msg_'+sede,None): st.success(msg)
        st.caption('La captura autónoma se incluye en campo_movil/. Para instalarla en el celular se requiere servirla inicialmente por HTTPS, abrirla y comprobar que está lista sin conexión. No requiere exponer la base SQLite.')
