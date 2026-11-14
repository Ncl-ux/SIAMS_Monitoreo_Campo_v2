"""Validación, fórmulas y estadísticas del capturador de SIAMS (100 % local)."""
from __future__ import annotations
from datetime import date, datetime
import math
import pandas as pd
import numpy as np

SEDES = ["Leticia", "Tumaco", "Bogotá", "Medellín", "San Andrés", "Arauca", "La Paz"]
MODULOS = {
    "muestreo": {
        "nombre": "Muestreo de campo", "clave": "muestra_id", "agrupa": "punto_id", "fecha": "fecha",
        "columnas": ["muestra_id", "punto_id", "fecha", "responsable", "ph", "ce_us_cm", "temperatura_c", "oxigeno_mg_l", "turbidez_ntu", "observaciones"],
        "numeros": ["ph", "ce_us_cm", "temperatura_c", "oxigeno_mg_l", "turbidez_ntu"],
        "requeridos": ["muestra_id", "punto_id", "fecha"],
    },
    "hidroquimica": {
        "nombre": "Hidroquímica", "clave": "muestra_id", "agrupa": "punto_id", "fecha": "fecha",
        "columnas": ["muestra_id", "punto_id", "fecha", "ca_mg_l", "mg_mg_l", "na_mg_l", "k_mg_l", "hco3_mg_l", "cl_mg_l", "so4_mg_l", "no3_mg_l", "fe_mg_l", "observaciones"],
        "numeros": ["ca_mg_l", "mg_mg_l", "na_mg_l", "k_mg_l", "hco3_mg_l", "cl_mg_l", "so4_mg_l", "no3_mg_l", "fe_mg_l"],
        "requeridos": ["muestra_id", "punto_id", "fecha"],
    },
    "sondas": {
        "nombre": "Sondas y transductores", "clave": "sensor_id", "agrupa": "sensor_id", "fecha": "fecha_hora",
        "columnas": ["punto_id", "sensor_id", "fecha_hora", "magnitud", "lectura", "referencia", "temperatura_c", "observaciones"],
        "numeros": ["lectura", "temperatura_c"],
        "requeridos": ["punto_id", "sensor_id", "fecha_hora", "magnitud", "referencia", "lectura"],
    },
}
MAGNITUDES = {
    "Profundidad al agua": "m",
    "Cota del agua": "m s. n. m.",
    "Presión": "kPa",
    "Conductividad": "µS/cm",
    "Temperatura": "°C",
}
ETIQUETAS = {
    "muestra_id": "Código de muestra", "punto_id": "Punto de monitoreo", "fecha": "Fecha", "fecha_hora": "Fecha y hora",
    "responsable": "Responsable", "ph": "pH", "ce_us_cm": "Conductividad · µS/cm", "temperatura_c": "Temperatura · °C",
    "oxigeno_mg_l": "Oxígeno disuelto · mg/L", "turbidez_ntu": "Turbidez · NTU", "observaciones": "Observaciones",
    "ca_mg_l": "Calcio · mg/L", "mg_mg_l": "Magnesio · mg/L", "na_mg_l": "Sodio · mg/L",
    "k_mg_l": "Potasio · mg/L", "hco3_mg_l": "Bicarbonato · mg/L", "cl_mg_l": "Cloruro · mg/L",
    "so4_mg_l": "Sulfato · mg/L", "no3_mg_l": "Nitrato · mg/L", "fe_mg_l": "Hierro · mg/L",
    "sensor_id": "Sonda / sensor", "magnitud": "Magnitud", "lectura": "Lectura", "referencia": "Referencia / datum",
    "unidad": "Unidad", "error_balance_pct": "Error balance · %", "facies": "Facies preliminar",
}
RANGOS = {"ph": (0, 14), "ce_us_cm": (0, None), "oxigeno_mg_l": (0, None), "turbidez_ntu": (0, None),
          "temperatura_c": (-40, 100), **{k: (0, None) for k in MODULOS["hidroquimica"]["numeros"]}}


def vacio(v):
    if v is None:
        return True
    try:
        r = pd.isna(v)
        if isinstance(r, (bool, np.bool_)) and r:
            return True
    except (ValueError, TypeError):
        pass
    return isinstance(v, str) and not v.strip()


def texto(v):
    return "" if vacio(v) else str(v).strip()


def numero(v, campo):
    if vacio(v):
        return None
    try:
        n = float(str(v).strip().replace(",", "."))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{ETIQUETAS.get(campo, campo)}: número no válido") from exc
    if not math.isfinite(n):
        raise ValueError(f"{ETIQUETAS.get(campo, campo)}: valor no finito")
    minimo, maximo = RANGOS.get(campo, (None, None))
    if minimo is not None and n < minimo or maximo is not None and n > maximo:
        raise ValueError(f"{ETIQUETAS.get(campo, campo)}: fuera del intervalo permitido")
    return n


def fecha_iso(v, con_hora=False):
    if vacio(v):
        raise ValueError("Fecha obligatoria")
    try:
        if isinstance(v, (date, datetime, pd.Timestamp)):
            f = pd.Timestamp(v)
        else:
            raw = texto(v)
            f = pd.to_datetime(raw, errors="raise", dayfirst=False)
        if pd.isna(f):
            raise ValueError("Fecha inválida")
        if f.tzinfo is not None:
            # Fechas de sondas: preservar la fecha y hora local explícita
            f = f.tz_localize(None)
        return f.strftime("%Y-%m-%d %H:%M") if con_hora else f.strftime("%Y-%m-%d")
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("Fecha inválida; usa AAAA-MM-DD o AAAA-MM-DD HH:MM") from exc


def clave_registro(modulo, reg):
    if modulo == "sondas":
        return "|".join([reg["punto_id"], reg["sensor_id"], reg["fecha_hora"], reg["magnitud"]])
    return reg["muestra_id"]


def normalizar_fila(modulo, raw):
    spec = MODULOS[modulo]
    # La fila vacía del editor no cuenta como registro
    if not any(not vacio(raw.get(c)) for c in spec["columnas"] if c not in ("fecha", "fecha_hora", "magnitud")):
        return None
    r = {}
    for c in spec["columnas"]:
        if c in spec["numeros"]:
            r[c] = numero(raw.get(c), c)
        elif c == "fecha":
            r[c] = fecha_iso(raw.get(c))
        elif c == "fecha_hora":
            r[c] = fecha_iso(raw.get(c), True)
        else:
            r[c] = texto(raw.get(c))
    faltantes = [ETIQUETAS.get(c, c) for c in spec["requeridos"] if vacio(r.get(c))]
    if faltantes:
        raise ValueError("Completa: " + ", ".join(faltantes))
    if modulo == "sondas":
        if r["magnitud"] not in MAGNITUDES:
            raise ValueError("Selecciona una magnitud de sonda")
        r["unidad"] = MAGNITUDES[r["magnitud"]]
        if r["lectura"] is None:
            raise ValueError("Ingresa la lectura")
        if r["magnitud"] in ("Profundidad al agua", "Presión", "Conductividad") and r["lectura"] < 0:
            raise ValueError("La lectura no puede ser negativa para esta magnitud")
    return r


def validar_lote(modulo, df):
    registros, errores, llaves = [], [], set()
    for pos, (_, row) in enumerate(df.iterrows(), start=1):
        try:
            r = normalizar_fila(modulo, row.to_dict())
            if r is None:
                continue
            llave = clave_registro(modulo, r)
            if llave in llaves:
                raise ValueError("Registro repetido dentro de la tabla")
            llaves.add(llave)
            registros.append(r)
        except ValueError as exc:
            errores.append(f"Fila {pos}: {exc}")
    if not registros and not errores:
        errores.append("No se ingresaron registros")
    return registros, errores


EQUIVALENTES = {
    "ca_mg_l": 20.039, "mg_mg_l": 12.1525, "na_mg_l": 22.9898, "k_mg_l": 39.0983,
    "hco3_mg_l": 61.0168, "cl_mg_l": 35.453, "so4_mg_l": 48.03, "no3_mg_l": 62.0049,
}
CATIONES = ["ca_mg_l", "mg_mg_l", "na_mg_l", "k_mg_l"]
ANIONES = ["hco3_mg_l", "cl_mg_l", "so4_mg_l"]


def enriquecer_hidroquimica(df):
    """Balance iónico solo con 7 iones principales completos; facies orientativa."""
    out = df.copy()
    if out.empty:
        for col in ("cationes_meq_l", "aniones_meq_l", "error_balance_pct", "facies"):
            out[col] = pd.Series(dtype="float64" if col != "facies" else "object")
        return out
    for c in EQUIVALENTES:
        out[c] = pd.to_numeric(out.get(c, pd.Series(index=out.index, dtype=float)), errors="coerce")
    ok = out[CATIONES + ANIONES].notna().all(axis=1)
    ca = sum(out[c].fillna(0) / EQUIVALENTES[c] for c in CATIONES)
    an = sum(out[c].fillna(0) / EQUIVALENTES[c] for c in ANIONES)
    an = an + out["no3_mg_l"].fillna(0) / EQUIVALENTES["no3_mg_l"]
    ok = ok & ((ca + an) > 0)
    out["cationes_meq_l"] = ca.where(ok)
    out["aniones_meq_l"] = an.where(ok)
    out["error_balance_pct"] = (100 * (ca - an) / (ca + an).replace(0, np.nan)).where(ok).round(2)
    facies = []
    for i in out.index:
        if not bool(ok.loc[i]):
            facies.append("Sin iones completos")
            continue
        cc = {"Ca": out.at[i, "ca_mg_l"] / EQUIVALENTES["ca_mg_l"],
              "Mg": out.at[i, "mg_mg_l"] / EQUIVALENTES["mg_mg_l"],
              "Na+K": out.at[i, "na_mg_l"] / EQUIVALENTES["na_mg_l"] + out.at[i, "k_mg_l"] / EQUIVALENTES["k_mg_l"]}
        aa = {"HCO₃": out.at[i, "hco3_mg_l"] / EQUIVALENTES["hco3_mg_l"],
              "Cl": out.at[i, "cl_mg_l"] / EQUIVALENTES["cl_mg_l"],
              "SO₄": out.at[i, "so4_mg_l"] / EQUIVALENTES["so4_mg_l"]}
        cdom = max(cc, key=cc.get) if sum(cc.values()) > 0 and max(cc.values()) / sum(cc.values()) > .5 else "Mixta"
        adom = max(aa, key=aa.get) if sum(aa.values()) > 0 and max(aa.values()) / sum(aa.values()) > .5 else "Mixta"
        facies.append(f"{cdom} – {adom}")
    out["facies"] = facies
    return out


def estadistica_descriptiva(df, columnas):
    registros = []
    n_total = len(df)
    for c in columnas:
        if c not in df:
            continue
        x = pd.to_numeric(df[c], errors="coerce").dropna()
        if x.empty:
            continue
        q1, q3 = x.quantile(.25), x.quantile(.75)
        iqr = q3 - q1
        desv = float(x.std(ddof=1)) if len(x) >= 2 else np.nan
        media = float(x.mean())
        outliers = int(((x < q1 - 1.5*iqr) | (x > q3 + 1.5*iqr)).sum()) if len(x) >= 4 else 0
        registros.append({"Variable": ETIQUETAS.get(c, c), "n": len(x), "Faltantes": n_total-len(x),
            "Media": media, "Mediana": float(x.median()), "Desv. est.": desv,
            "Mínimo": float(x.min()), "P25": float(q1), "P75": float(q3), "Máximo": float(x.max()),
            "CV (%)": 100*desv/abs(media) if math.isfinite(desv) and abs(media)>1e-12 else np.nan,
            "Atípicos IQR": outliers})
    return pd.DataFrame(registros)


def correlaciones(df, columnas):
    campos = [c for c in columnas if c in df and pd.to_numeric(df[c], errors="coerce").count() >= 3]
    if len(campos) < 2:
        return pd.DataFrame()
    numeric = df[campos].apply(pd.to_numeric, errors="coerce")
    # 3 pares mínimos para cada correlación; columnas constantes devuelven NaN
    return numeric.corr(method="pearson", min_periods=3).rename(index=ETIQUETAS, columns=ETIQUETAS)


def tendencias_sondas(df):
    columnas = ["Punto", "Sensor", "Magnitud", "Referencia", "n", "Primer registro", "Último registro", "Mínimo", "Máximo", "Promedio", "Variación total", "Pendiente por día"]
    if df.empty:
        return pd.DataFrame(columns=columnas)
    d = df.copy()
    d["fecha_hora"] = pd.to_datetime(d["fecha_hora"], errors="coerce")
    d["lectura"] = pd.to_numeric(d["lectura"], errors="coerce")
    d = d.dropna(subset=["fecha_hora", "lectura"])
    out = []
    for (punto, sensor, mag, ref), g in d.groupby(["punto_id", "sensor_id", "magnitud", "referencia"], dropna=False):
        g = g.sort_values("fecha_hora")
        x = (g["fecha_hora"] - g["fecha_hora"].min()).dt.total_seconds().to_numpy() / 86400
        y = g["lectura"].to_numpy(dtype=float)
        pendiente = float(np.polyfit(x, y, 1)[0]) if len(np.unique(x)) >= 3 else np.nan
        out.append({"Punto":punto,"Sensor":sensor,"Magnitud":mag,"Referencia":ref,"n":len(g),
                    "Primer registro":g["fecha_hora"].iloc[0].strftime("%Y-%m-%d %H:%M"),
                    "Último registro":g["fecha_hora"].iloc[-1].strftime("%Y-%m-%d %H:%M"),
                    "Mínimo":float(y.min()),"Máximo":float(y.max()),"Promedio":float(y.mean()),
                    "Variación total":float(y[-1]-y[0]),"Pendiente por día":pendiente})
    return pd.DataFrame(out, columns=columnas)


def resumen_por_grupo(df, grupo, variable):
    if df.empty or grupo not in df or variable not in df:
        return pd.DataFrame()
    d = df[[grupo, variable]].copy()
    d[variable] = pd.to_numeric(d[variable], errors="coerce")
    z = d.groupby(grupo, dropna=False)[variable].agg(["count", "mean", "median", "min", "max", "std"]).reset_index()
    return z.rename(columns={grupo:ETIQUETAS.get(grupo, grupo), "count":"n", "mean":"Media", "median":"Mediana", "min":"Mínimo", "max":"Máximo", "std":"Desv. est."})
