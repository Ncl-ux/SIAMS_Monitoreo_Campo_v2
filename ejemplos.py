"""Datos ficticios exclusivamente para demostrar las gráficas."""
from datetime import date, datetime, timedelta
import math
from nucleo import normalizar_fila


def ejemplos():
    base = date(2026, 11, 3)
    muestreo, hidro, sondas = [], [], []
    for i in range(8):
        p = "NUMAE" if i < 4 else "RÍO-01"
        muestreo.append(normalizar_fila("muestreo", {
            "muestra_id":f"SIM-{i+1:03d}","punto_id":p,"fecha":base+timedelta(days=i),"responsable":"Ejemplo",
            "ph":round(6.2 + .15*i,2), "ce_us_cm":130+i*15, "temperatura_c":25.4+.17*i,
            "oxigeno_mg_l":5.4-.11*i, "turbidez_ntu":4+i%3, "observaciones":"SIMULACIÓN"}))
        hidro.append(normalizar_fila("hidroquimica", {
            "muestra_id":f"SIM-{i+1:03d}","punto_id":p,"fecha":base+timedelta(days=i),
            "ca_mg_l":20+i,"mg_mg_l":6+.4*i,"na_mg_l":12+.9*i,"k_mg_l":1.5,
            "hco3_mg_l":73+i*4,"cl_mg_l":15+i,"so4_mg_l":11+i,"no3_mg_l":1.2+i*.1,"fe_mg_l":.2+i*.03,"observaciones":"SIMULACIÓN"}))
    for j in range(24):
        sondas.append(normalizar_fila("sondas", {
            "punto_id":"NUMAE","sensor_id":"S-01","fecha_hora":(datetime(2026,11,3,8)+timedelta(hours=6*j)).strftime("%Y-%m-%d %H:%M"),
            "magnitud":"Profundidad al agua", "lectura":round(2.5+.009*j+0.07*math.sin(j/2),3),
            "referencia":"Brocal","temperatura_c":26.2+.04*j,"observaciones":"SIMULACIÓN"}))
    return {"muestreo":muestreo,"hidroquimica":hidro,"sondas":sondas}
