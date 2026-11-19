"""SIAMS · Captura y análisis local de campo. Sin conexión a servicios externos."""
from __future__ import annotations
from datetime import date
from html import escape
import io
import pandas as pd
import altair as alt
import streamlit as st

from nucleo import (
    SEDES, MODULOS, MAGNITUDES, ETIQUETAS, validar_lote,
    estadistica_descriptiva, enriquecer_hidroquimica,
    correlaciones, tendencias_sondas, resumen_por_grupo,
)
from almacenamiento import consultar, guardar, borrar, crear_backup
from ejemplos import ejemplos
from puntos import adjuntar_puntos, completar_punto
from interfaz_puntos import mostrar_puntos, selector_punto
from interfaz_protocolo import mostrar_protocolo
from protocolo_campo import consultar_protocolo

st.set_page_config(page_title="SIAMS · Captura y análisis", page_icon="💧", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
  :root {--ink:#253036;--muted:#657178;--border:#DCE1E1;--paper:#FFFFFF;--brand:#495D59}
  .stApp {background:#F7F8F7}
  .block-container {max-width: 1560px; padding-top:1.65rem; padding-bottom:3rem}
  [data-testid="stSidebar"] {background:#F0F2F1; border-right:1px solid #DCE1E1}
  [data-testid="stSidebar"] .block-container {padding-top:1.25rem}
  [data-testid="stVerticalBlockBorderWrapper"] {border-color:#DFE3E2!important}
  .siams-heading {padding: 10px 0 18px; border-bottom:1px solid #DCE1E1; margin-bottom:12px}
  .siams-kicker {color:#64716D;letter-spacing:.13em;font-weight:700;font-size:.72rem;margin-bottom:9px}
  .siams-heading h1 {color:#273238;font-size:2.15rem;font-weight:700;letter-spacing:-.035em;margin:0}
  .siams-heading p {color:#68747A;font-size:.96rem;margin:9px 0 0}
  .siams-brand {font-size:1.5rem;font-weight:750;letter-spacing:-.04em;color:#273238}
  .siams-brand span {font-weight:400;color:#65746E}
  .siams-sidebar-meta {font-size:.76rem;letter-spacing:.06em;color:#6D7879;margin:6px 0 17px}
  .siams-small {color:#6B767A;font-size:.85rem}
  .siams-section {color:#334046;font-size:1.1rem;font-weight:650;margin:13px 0 8px}
  [data-testid="stMetric"] {background:#FFFFFF;border:1px solid #DFE3E2;border-radius:12px;padding:13px 17px;min-height:103px}
  [data-testid="stMetricLabel"] {color:#6B767A}
  [data-testid="stMetricValue"] {font-weight:650;letter-spacing:-.02em}
  [data-testid="stDataFrame"], [data-testid="stDataEditor"] {background:#FFFFFF; border:1px solid #DCE1E1; border-radius:12px;overflow:hidden}
  [data-testid="stTabs"] button {font-weight:600}
  .stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {background:#495D59;color:#FFFFFF;border:1px solid #495D59;border-radius:8px}
  .stButton > button[kind="secondary"], .stDownloadButton > button[kind="secondary"] {border:1px solid #D2D8D7;background:white;border-radius:8px}
  [data-testid="stFileUploader"] {border-color:#DCE1E1;border-radius:9px}
  hr {border-color:#E5E9E8!important}
  .local-label {background:#E9EEEB;color:#485C57;border-radius:99px;padding:4px 10px;font-size:.76rem;font-weight:600;display:inline-block}
</style>
""", unsafe_allow_html=True)


def titulo(texto):
    st.markdown(f'<div class="siams-section">{escape(texto)}</div>', unsafe_allow_html=True)


def csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8-sig")


def plantilla(modulo, n=2):
    spec = MODULOS[modulo]
    d = {}
    for c in spec["columnas"]:
        if c in spec["numeros"]:
            d[c] = pd.Series([float("nan")] * n, dtype="float64")
        elif c == "fecha":
            d[c] = pd.Series([date.today()] * n, dtype="object")
        elif c == "magnitud":
            d[c] = pd.Series(["Profundidad al agua"] * n, dtype="str")
        else:
            d[c] = pd.Series([""] * n, dtype="str")
    return pd.DataFrame(d)


def configuracion_columnas(modulo):
    cfg = {}
    for c in MODULOS[modulo]["columnas"]:
        label = ETIQUETAS.get(c, c)
        if c in MODULOS[modulo]["numeros"]:
            cfg[c] = st.column_config.NumberColumn(label, width="medium", format="%.3f", step=0.01)
        elif c == "fecha":
            cfg[c] = st.column_config.DateColumn(label, format="DD/MM/YYYY", width="small")
        elif c == "magnitud":
            cfg[c] = st.column_config.SelectboxColumn(label, options=list(MAGNITUDES), width="medium")
        elif c == "observaciones":
            cfg[c] = st.column_config.TextColumn(label, width="large")
        else:
            cfg[c] = st.column_config.TextColumn(label, width="medium" if c not in ("muestra_id", "punto_id") else "small")
    return cfg


def tabla_consulta(df, modulo, extra=None, alto=370):
    if df.empty:
        st.caption("Aún no hay registros para mostrar.")
        return
    keep = [c for c in ["id", *MODULOS[modulo]["columnas"], *(extra or [])] if c in df]
    visible = df[keep].rename(columns=ETIQUETAS)
    number_config = {ETIQUETAS.get(c, c):st.column_config.NumberColumn(ETIQUETAS.get(c, c),format="%.2f")
                    for c in MODULOS[modulo]["numeros"] + (extra or []) if c in df and c!="facies"}
    st.dataframe(visible, width="stretch", height=alto, hide_index=True, column_config=number_config)


def format_dec(df, cols):
    if df.empty:
        return df
    out = df.copy()
    for c in cols:
        if c in out:
            out[c] = pd.to_numeric(out[c], errors="coerce").round(3)
    return out


def grafico_barras(df, variable, titulo_grafico=None):
    valores = pd.to_numeric(df[variable], errors="coerce").dropna()
    if len(valores) < 2:
        st.caption("Se necesitan al menos dos lecturas para representar la distribución.")
        return
    series = pd.DataFrame({"valor":valores})
    grafico = alt.Chart(series).mark_bar(color="#61756F", cornerRadiusTopLeft=3,cornerRadiusTopRight=3).encode(
        x=alt.X("valor:Q", bin=alt.Bin(maxbins=15), title=ETIQUETAS.get(variable,variable)),
        y=alt.Y("count():Q", title="Frecuencia"),
        tooltip=[alt.Tooltip("count():Q", title="Frecuencia")]
    ).properties(height=255, title=titulo_grafico or "Distribución de mediciones")
    st.altair_chart(grafico.configure_view(stroke=None).configure_axis(labelColor="#596569",titleColor="#465358"),width="stretch")


def grafico_caja(df, variable, grupo):
    d = df[[grupo,variable]].copy()
    d[variable] = pd.to_numeric(d[variable],errors="coerce")
    d = d.dropna()
    if d.empty:
        return
    c = alt.Chart(d).mark_boxplot(color="#61756F", outliers=True).encode(
        x=alt.X(f"{grupo}:N", title=ETIQUETAS.get(grupo,grupo),axis=alt.Axis(labelAngle=-30)),
        y=alt.Y(f"{variable}:Q",title=ETIQUETAS.get(variable,variable))
    ).properties(height=270)
    st.altair_chart(c.configure_view(stroke=None),width="stretch")


def serie_temporal(df, modulo, variable, filtro_punto):
    col_t = MODULOS[modulo]["fecha"]
    d = df.copy()
    d[col_t] = pd.to_datetime(d[col_t],errors="coerce")
    d[variable] = pd.to_numeric(d[variable], errors="coerce")
    d = d.dropna(subset=[col_t,variable])
    if d.empty:
        st.caption("No hay valores para la combinación seleccionada.")
        return
    agrup = filtro_punto
    if agrup in d:
        d = d[[col_t,variable,agrup]]
        linea = alt.Chart(d).mark_line(point=True, color="#56736A", strokeWidth=2).encode(
            x=alt.X(f"{col_t}:T",title="Fecha y hora"), y=alt.Y(f"{variable}:Q",title=ETIQUETAS.get(variable,variable)),
            color=alt.Color(f"{agrup}:N",scale=alt.Scale(scheme="tableau10"),title="Punto / sensor"),
            tooltip=[alt.Tooltip(f"{col_t}:T",title="Fecha"),alt.Tooltip(f"{agrup}:N"),alt.Tooltip(f"{variable}:Q",format=".3f")]
        )
    else:
        linea = alt.Chart(d).mark_line(point=True, color="#56736A").encode(x=f"{col_t}:T",y=f"{variable}:Q")
    st.altair_chart(linea.properties(height=360).configure_view(stroke=None),width="stretch")


with st.sidebar:
    st.markdown('<div class="siams-brand">SIAMS <span>/ Campo</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="siams-sidebar-meta">LABORATORIO DE REGISTROS</div>', unsafe_allow_html=True)
    sede = st.selectbox("Sede de monitoreo", SEDES, label_visibility="visible")
    modulo = st.radio("Tipo de información", list(MODULOS), format_func=lambda k:MODULOS[k]["nombre"], index=0)
    st.divider()
    st.caption("Base de datos guardada en este equipo")
    total_sede = sum(len(consultar(m,sede)) for m in MODULOS)
    st.metric("Registros en la sede", f"{total_sede:,}")
    st.caption(f"Visitas del protocolo: {len(consultar_protocolo(sede))}")
    with st.expander("Conjunto de ejemplo"):
        st.caption("Datos simulados para explorar los cálculos.")
        if st.button("Incorporar ejemplo de Leticia", width="stretch"):
            cantidad = 0
            for mod, registros in ejemplos().items():
                try:
                    cantidad += guardar(mod, "Leticia", registros)
                except ValueError:
                    pass
            st.session_state.ultimo = f"Ejemplos añadidos: {cantidad}"
            st.rerun()
    st.download_button("Descargar respaldo de la sede", data=crear_backup(sede), file_name=f"SIAMS_respaldo_{sede.replace(' ','_')}.zip", mime="application/zip",width="stretch")
    st.caption("Sin conexión externa · Streamlit local")

spec = MODULOS[modulo]
df = consultar(modulo,sede)
if modulo == "hidroquimica":
    analitico = enriquecer_hidroquimica(df)
else:
    analitico = df.copy()

st.markdown(f'''<div class="siams-heading">
  <div class="siams-kicker">OBSERVATORIO DEL AGUA · {escape(sede.upper())}</div>
  <h1>{escape(spec['nombre'])}</h1>
  <p>Registro estructurado, consulta histórica y análisis estadístico de mediciones.</p>
</div>''', unsafe_allow_html=True)

# Indicadores sólo sobre el módulo elegido, sin valores inventados.
c1,c2,c3,c4 = st.columns(4)
c1.metric("Registros",f"{len(df):,}")
c2.metric("Puntos",f"{df['punto_id'].nunique() if 'punto_id' in df else 0:,}")
c3.metric("Variables medidas",f"{sum(df[c].notna().any() for c in spec['numeros']) if not df.empty else 0}")
if modulo == "sondas":
    c4.metric("Sensores",f"{df['sensor_id'].nunique() if not df.empty else 0:,}")
elif modulo == "hidroquimica":
    n_ok = int(analitico["error_balance_pct"].notna().sum()) if not df.empty else 0
    c4.metric("Balances calculados",str(n_ok))
else:
    c4.metric("Muestras únicas",f"{df['muestra_id'].nunique() if not df.empty else 0:,}")

p_reg,p_cons,p_est,p_series,p_puntos,p_protocolo = st.tabs(["01  Registrar", "02  Base de datos", "03  Estadística", "04  Gráficas y series", "05  Puntos y coordenadas", "06  Protocolo de campo"])

with p_protocolo:
    mostrar_protocolo(sede)

with p_puntos:
    mostrar_puntos(sede)

with p_reg:
    punto_predeterminado = selector_punto(sede, modulo)
    titulo("Plantilla editable")
    st.caption("Escribe directamente en las celdas, añade filas con el control de la tabla o pega un bloque desde Excel. Los campos no medidos pueden quedar vacíos.")
    if modulo == "sondas":
        st.caption("Cada lectura debe incluir referencia de medida: brocal, superficie del terreno, datum, etc.")
    elif modulo == "hidroquimica":
        st.caption("Registra concentraciones en mg/L. El balance iónico se calcula en la pestaña Estadística cuando se disponga de los iones principales.")
    if "version_editor" not in st.session_state:
        st.session_state.version_editor = {m:0 for m in MODULOS}
    with st.form(f"registro_{modulo}_{sede}"):
        editado = st.data_editor(plantilla(modulo),column_config=configuracion_columnas(modulo),
            column_order=spec["columnas"],num_rows="dynamic",width="stretch",height=310,
            hide_index=True,key=f"nuevo_{sede}_{modulo}_{st.session_state.version_editor[modulo]}")
        izquierda,derecha = st.columns([1,3])
        with izquierda:
            guardar_presionado = st.form_submit_button("Guardar registros", type="primary",width="stretch")
        with derecha:
            st.caption("Se guardan en la base SQLite local de este computador.")
    if guardar_presionado:
        nuevos, errores = validar_lote(modulo,completar_punto(editado,modulo,punto_predeterminado))
        if not errores:
            try:
                n = guardar(modulo,sede,nuevos)
                st.session_state.version_editor[modulo] += 1
                st.session_state.ultimo = f"{n} registros guardados"
                st.rerun()
            except ValueError as exc:
                errores = [str(exc)]
        if errores:
            st.markdown("**Revisa la tabla:**")
            for mensaje in errores[:8]:
                st.caption("• " + mensaje)
    if st.session_state.get("ultimo"):
        st.caption(st.session_state.pop("ultimo"))

    with st.expander("Importar una tabla CSV"):
        st.caption("También puedes cargar una tabla con las mismas columnas, sin conexión a internet.")
        st.download_button("Descargar formato CSV vacío",csv_bytes(plantilla(modulo,n=0)),file_name=f"plantilla_{modulo}.csv",mime="text/csv",key=f"plantilla_{modulo}")
        archivo = st.file_uploader("Seleccionar CSV",type=["csv"],key=f"subida_{modulo}_{sede}")
        if archivo is not None:
            try:
                crudo = pd.read_csv(archivo,sep=None,engine="python",dtype={"muestra_id":"string","punto_id":"string","sensor_id":"string"})
                faltan = [c for c in spec["columnas"] if c not in crudo.columns]
                if faltan:
                    st.caption("Columnas pendientes: " + ", ".join(faltan))
                else:
                    st.dataframe(crudo.head(20),width="stretch",hide_index=True)
                    if st.button("Incorporar CSV",type="primary",key=f"importar_{modulo}"):
                        registros, errores = validar_lote(modulo,crudo)
                        if errores:
                            for e in errores[:10]: st.caption("• " + e)
                        else:
                            try:
                                guardar(modulo,sede,registros)
                                st.session_state.ultimo = f"Importados {len(registros)} registros"
                                st.rerun()
                            except ValueError as exc:
                                st.caption(str(exc))
            except (ValueError,UnicodeError,pd.errors.ParserError) as exc:
                st.caption(f"No se pudo interpretar el archivo: {exc}")

with p_cons:
    titulo("Registros almacenados")
    if df.empty:
        st.caption("Esta sede aún no tiene registros de este módulo.")
    else:
        a,b = st.columns([1,2])
        with a:
            buscador = st.text_input("Buscar punto, muestra o sensor",placeholder="Código o texto")
        with b:
            st.caption(f"{len(df)} registros disponibles · última actualización: {df['creado'].max()[:16]}")
        vista = df.copy()
        if buscador.strip():
            busca = buscador.strip()
            matching = vista.astype(str).apply(lambda s:s.str.contains(busca,case=False,regex=False,na=False)).any(axis=1)
            vista = vista[matching]
        if modulo == "hidroquimica":
            vista = enriquecer_hidroquimica(vista)
        st.caption("El CSV incluye la ubicación actual del catálogo cuando está disponible; no representa una nueva medición GPS en cada visita.")
        tabla_consulta(vista,modulo,["error_balance_pct","facies"] if modulo=="hidroquimica" else None,alto=445)
        iz,de = st.columns([1,1])
        with iz:
            st.download_button("Exportar registros · CSV",data=csv_bytes(adjuntar_puntos(vista,sede)),file_name=f"siams_{sede}_{modulo}.csv",mime="text/csv",width="stretch")
        with de:
            with st.expander("Eliminar registros seleccionados"):
                claves = {f"#{int(row.id)} · {str(getattr(row, spec['clave']))}": int(row.id) for row in vista.itertuples(index=False)}
                seleccion = st.multiselect("Registros",list(claves),key=f"borrar_{modulo}_{sede}")
                confirma = st.checkbox("Confirmo la eliminación",key=f"confirmar_{modulo}_{sede}")
                if st.button("Eliminar seleccionados",disabled=not seleccion or not confirma,key=f"eliminar_{modulo}_{sede}"):
                    borrar(modulo,sede,[claves[x] for x in seleccion])
                    st.rerun()

with p_est:
    titulo("Resumen estadístico")
    if df.empty:
        st.caption("Registra al menos una medición para calcular los indicadores.")
    else:
        estad = estadistica_descriptiva(analitico,spec["numeros"])
        if not estad.empty:
            st.dataframe(format_dec(estad,["Media","Mediana","Desv. est.","Mínimo","P25","P75","Máximo","CV (%)"]),
                         width="stretch",hide_index=True,height=min(425,83+len(estad)*35))
            st.download_button("Exportar estadísticos · CSV",data=csv_bytes(estad),file_name=f"estadistica_{sede}_{modulo}.csv",mime="text/csv")
            st.caption("Desviación estándar muestral; CV = desviación / |media|; atípicos mediante regla 1,5 × IQR.")
        else:
            st.caption("Todavía no hay variables numéricas con datos.")
        st.divider()
        if modulo == "hidroquimica":
            titulo("Composición iónica y balance")
            quim = enriquecer_hidroquimica(df)
            cols = ["muestra_id","punto_id","cationes_meq_l","aniones_meq_l","error_balance_pct","facies"]
            q = quim[cols].copy().rename(columns={"muestra_id":"Muestra","punto_id":"Punto", "cationes_meq_l":"Cationes · meq/L", "aniones_meq_l":"Aniones · meq/L", "error_balance_pct":"Error de balance · %", "facies":"Facies preliminar"})
            st.dataframe(format_dec(q,["Cationes · meq/L","Aniones · meq/L","Error de balance · %"]),width="stretch",hide_index=True)
            completos = quim["error_balance_pct"].notna()
            dentro = int((quim.loc[completos,"error_balance_pct"].abs()<=5).sum())
            c1,c2 = st.columns(2)
            c1.metric("Balances calculables",int(completos.sum()))
            c2.metric("Dentro de ±5 %",dentro)
            st.caption("Cálculo orientativo en meq/L para Ca, Mg, Na, K, HCO₃, Cl y SO₄ (y NO₃ cuando está disponible). El límite de ±5 % es un criterio de revisión, no valida una muestra por sí solo. Las facies son preliminares.")
        if modulo == "sondas":
            titulo("Variaciones y tendencias por instrumento")
            tendencias = tendencias_sondas(df)
            if not tendencias.empty:
                st.dataframe(format_dec(tendencias,["Mínimo","Máximo","Promedio","Variación total","Pendiente por día"]),width="stretch",hide_index=True)
                st.download_button("Exportar tendencias · CSV",data=csv_bytes(tendencias),file_name=f"tendencias_{sede}.csv",mime="text/csv")
            st.caption("La pendiente es una regresión lineal de lectura frente al tiempo, expresada en unidad de la magnitud por día. Se calcula con al menos tres fechas distintas y no constituye una predicción.")
        st.divider()
        titulo("Estadísticos por punto o sensor")
        grupo = spec["agrupa"]
        variables = [c for c in spec["numeros"] if c in analitico and pd.to_numeric(analitico[c],errors="coerce").notna().any()]
        if variables:
            v_grupo = st.selectbox("Variable para comparar",variables,format_func=lambda c:ETIQUETAS.get(c,c),key=f"grupo_{modulo}")
            if modulo == "sondas":
                mag_grupo = st.selectbox("Magnitud",sorted(analitico["magnitud"].dropna().unique()),key="mag_estad_sonda")
                referencia_grupo = st.selectbox("Referencia",sorted(analitico.loc[analitico["magnitud"]==mag_grupo,"referencia"].dropna().unique()),key="ref_estad_sonda")
                por_grupo = analitico[(analitico["magnitud"]==mag_grupo)&(analitico["referencia"]==referencia_grupo)]
            else:
                por_grupo = analitico
            st.dataframe(format_dec(resumen_por_grupo(por_grupo,grupo,v_grupo),["Media","Mediana","Mínimo","Máximo","Desv. est."]),width="stretch",hide_index=True)
        st.divider()
        titulo("Correlaciones de Pearson")
        correl = correlaciones(analitico,spec["numeros"])
        if not correl.empty:
            st.dataframe(correl.round(3),width="stretch")
            st.caption("Correlaciones exploratorias. No implican causalidad; cada par requiere al menos tres observaciones.")
        else:
            st.caption("Se necesitan al menos dos variables con tres valores para calcular correlaciones.")

with p_series:
    titulo("Visualización de mediciones")
    if df.empty:
        st.caption("Los gráficos aparecerán cuando se registren mediciones.")
    else:
        if modulo=="sondas":
            magnitudes = sorted(df["magnitud"].dropna().unique().tolist())
            mag = st.selectbox("Magnitud registrada",magnitudes,key="plot_magnitud")
            subcon = df[df["magnitud"]==mag].copy()
            refs = sorted(subcon["referencia"].dropna().unique().tolist())
            ref = st.selectbox("Referencia de medición",refs,key="plot_referencia")
            subcon = subcon[subcon["referencia"]==ref]
            opciones = sorted(subcon["sensor_id"].dropna().unique().tolist())
            sensor = st.multiselect("Sensores",opciones,default=opciones[:3],key="plot_sensores")
            subcon = subcon[subcon["sensor_id"].isin(sensor)]
            if not subcon.empty:
                titulo("Serie temporal")
                serie_temporal(subcon,modulo,"lectura","sensor_id")
                titulo("Distribución")
                left,right = st.columns(2)
                with left:grafico_barras(subcon,"lectura")
                with right:grafico_caja(subcon,"lectura","sensor_id")
            st.caption("Se muestran series de una sola magnitud y referencia para evitar comparar medidas incompatibles.")
        else:
            vars_disp = [c for c in spec["numeros"] if pd.to_numeric(analitico[c],errors="coerce").notna().any()]
            if not vars_disp:
                st.caption("No hay parámetros numéricos disponibles para graficar.")
            else:
                variable = st.selectbox("Variable para analizar",vars_disp,format_func=lambda k:ETIQUETAS.get(k,k),key=f"plot_{modulo}")
                puntos = sorted(analitico["punto_id"].dropna().unique().tolist())
                seleccion_puntos = st.multiselect("Puntos",puntos,default=puntos,key=f"plot_puntos_{modulo}")
                subcon = analitico[analitico["punto_id"].isin(seleccion_puntos)]
                titulo("Evolución temporal")
                serie_temporal(subcon,modulo,variable,"punto_id")
                titulo("Distribución y diferencias entre puntos")
                l,r = st.columns(2)
                with l:grafico_barras(subcon,variable)
                with r:grafico_caja(subcon,variable,"punto_id")

st.divider()
st.markdown('<div class="siams-small">SIAMS · Registro y análisis local · Datos bajo control del equipo que ejecuta la aplicación</div>',unsafe_allow_html=True)
