import sys
from pathlib import Path
from datetime import date
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
import pytest
from nucleo import (normalizar_fila, validar_lote, enriquecer_hidroquimica,
                    estadistica_descriptiva, correlaciones, tendencias_sondas)
import almacenamiento


def muestra(id_="M01", ph=7):
    return {"muestra_id":id_,"punto_id":"P01","fecha":date(2026,11,13),"ph":ph,"ce_us_cm":120}


def quimica():
    return {"muestra_id":"M01", "punto_id":"P01","fecha":"2026-11-13",
            "ca_mg_l":40.078,"mg_mg_l":0,"na_mg_l":0,"k_mg_l":0,
            "hco3_mg_l":61.0168,"cl_mg_l":35.453,"so4_mg_l":0,"no3_mg_l":0}


def sonda(fecha_hora="2026-11-13 12:00", valor=2.4):
    return {"punto_id":"NUMAE","sensor_id":"SON-1","fecha_hora":fecha_hora,
            "magnitud":"Profundidad al agua","lectura":valor,"referencia":"Brocal"}


def test_muestra_normalizada():
    r=normalizar_fila("muestreo",muestra())
    assert r["ph"] == 7
    assert r["fecha"] == "2026-11-13"


def test_datos_vacios_ignorar():
    assert normalizar_fila("muestreo",{"fecha":date(2026,11,13)}) is None


def test_limite_ph():
    with pytest.raises(ValueError):
        normalizar_fila("muestreo",muestra(ph=14.1))


def test_duplicados_en_mismo_lote():
    nuevos, errores = validar_lote("muestreo",pd.DataFrame([muestra(),muestra()]))
    assert len(nuevos) == 1 and len(errores) == 1


def test_fecha_y_unidad_sonda():
    r = normalizar_fila("sondas",sonda())
    assert r["fecha_hora"] == "2026-11-13 12:00"
    assert r["unidad"] == "m"


def test_lectura_negativa():
    with pytest.raises(ValueError):
        normalizar_fila("sondas",sonda(valor=-2))


def test_balance_ionico_electroneutro():
    d = enriquecer_hidroquimica(pd.DataFrame([normalizar_fila("hidroquimica",quimica())]))
    assert abs(d.loc[0,"error_balance_pct"]) < .001
    assert d.loc[0,"facies"].startswith("Ca")


def test_balance_incompleto_sin_calculo():
    r = quimica();r.pop("so4_mg_l")
    d = enriquecer_hidroquimica(pd.DataFrame([normalizar_fila("hidroquimica",r)]))
    assert np.isnan(d.loc[0,"error_balance_pct"])


def test_balance_lado_cero_sin_division_cero():
    r = quimica();r["ca_mg_l"]=0
    d = enriquecer_hidroquimica(pd.DataFrame([normalizar_fila("hidroquimica",r)]))
    assert d.loc[0,"error_balance_pct"] == -100


def test_descriptiva_y_atipicos():
    d = pd.DataFrame({"ph":[1,1,1,1,10]})
    s = estadistica_descriptiva(d,["ph"])
    assert s.loc[0,"Atípicos IQR"] == 1
    assert s.loc[0,"Media"] == 2.8


def test_correlaciones_minimo():
    d=pd.DataFrame({"ph":[1,2,3],"ce_us_cm":[2,4,6]})
    c=correlaciones(d,["ph","ce_us_cm"])
    assert abs(c.iloc[0,1]-1)<1e-8


def test_tendencia_por_dia():
    reg = [normalizar_fila("sondas",sonda(f"2026-11-{13+i:02d} 12:00",2.4+i*.1)) for i in range(3)]
    t=tendencias_sondas(pd.DataFrame(reg))
    assert abs(t.loc[0,"Pendiente por día"] - .1)<1e-8
    assert abs(t.loc[0,"Variación total"]-.2)<1e-8


def test_persistencia_y_respaldo(monkeypatch,tmp_path):
    monkeypatch.setattr(almacenamiento,"DB_PATH",tmp_path / "datos" / "test.db")
    a=normalizar_fila("muestreo",muestra())
    assert almacenamiento.guardar("muestreo","Leticia",[a]) == 1
    tabla = almacenamiento.consultar("muestreo","Leticia")
    assert len(tabla)==1 and tabla.iloc[0]["muestra_id"]=="M01"
    import zipfile, io
    with zipfile.ZipFile(io.BytesIO(almacenamiento.crear_backup("Leticia"))) as zipf:
        assert "Leticia/muestreo.csv" in zipf.namelist()
    assert almacenamiento.borrar("muestreo","Leticia",[int(tabla.iloc[0]["id"])]) == 1
    assert almacenamiento.consultar("muestreo","Leticia").empty


def test_sqlite_no_guardado_parcial(monkeypatch,tmp_path):
    monkeypatch.setattr(almacenamiento,"DB_PATH",tmp_path/"db.sqlite")
    uno=normalizar_fila("muestreo",muestra())
    dos=normalizar_fila("muestreo",muestra("M02"))
    almacenamiento.guardar("muestreo","Leticia",[uno])
    with pytest.raises(ValueError):
        almacenamiento.guardar("muestreo","Leticia",[dos,uno])
    assert len(almacenamiento.consultar("muestreo","Leticia")) == 1
