"""Persistencia SQLite local. Los datos nunca se envían a internet desde este módulo."""
from __future__ import annotations
from contextlib import closing
from datetime import datetime
from pathlib import Path
import io
import json
import os
import sqlite3
import zipfile
import pandas as pd
from nucleo import MODULOS, SEDES, clave_registro

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("SIAMS_DB_PATH", str(ROOT / "datos_locales" / "siams.db")))


def conexion():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    cx = sqlite3.connect(DB_PATH, timeout=15)
    cx.execute("PRAGMA busy_timeout=15000")
    cx.execute("""CREATE TABLE IF NOT EXISTS registros (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sede TEXT NOT NULL, modulo TEXT NOT NULL, clave TEXT NOT NULL,
        datos TEXT NOT NULL, creado TEXT NOT NULL,
        UNIQUE(sede, modulo, clave)
    )""")
    cx.commit()
    return cx


def guardar(modulo, sede, registros):
    if modulo not in MODULOS or sede not in SEDES:
        raise ValueError("Sede o módulo desconocido")
    if not registros:
        return 0
    # En una transacción: todos los registros o ninguno.
    cx = conexion()
    try:
        with cx:
            for r in registros:
                cx.execute("INSERT INTO registros (sede,modulo,clave,datos,creado) VALUES (?,?,?,?,?)",
                    (sede, modulo, clave_registro(modulo,r), json.dumps(r, ensure_ascii=False, allow_nan=False), datetime.now().isoformat(timespec="seconds")))
        return len(registros)
    except sqlite3.IntegrityError as exc:
        raise ValueError("Hay códigos o lecturas que ya existen; revisa los identificadores y las fechas") from exc
    finally:
        cx.close()


def consultar(modulo, sede):
    if modulo not in MODULOS or sede not in SEDES:
        raise ValueError("Sede o módulo desconocido")
    with closing(conexion()) as cx, cx:
        filas = cx.execute("SELECT id, datos, creado FROM registros WHERE sede=? AND modulo=? ORDER BY id", (sede, modulo)).fetchall()
    registros = [{"id": id_, **json.loads(raw), "creado": creado} for id_, raw, creado in filas]
    cols = ["id"] + MODULOS[modulo]["columnas"] + (["unidad"] if modulo == "sondas" else []) + ["creado"]
    return pd.DataFrame(registros).reindex(columns=cols)


def borrar(modulo, sede, ids):
    # Eliminar únicamente las filas elegidas en la sede y módulo actuales.
    ids = [int(v) for v in ids]
    if not ids:
        return 0
    with closing(conexion()) as cx, cx:
        cur = cx.executemany("DELETE FROM registros WHERE id=? AND sede=? AND modulo=?", [(i, sede, modulo) for i in ids])
        return cur.rowcount


def crear_backup(sede=None):
    from protocolo_campo import consultar_protocolo, exportar_json, exportar_csv, exportar_geojson
    from puntos import consultar_puntos
    sedes = [sede] if sede else SEDES
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for s in sedes:
            visitas=consultar_protocolo(s)
            carpeta=s.replace(" ", "_")
            zf.writestr(f"{carpeta}/protocolo.json", exportar_json(visitas))
            zf.writestr(f"{carpeta}/protocolo.csv", exportar_csv(visitas))
            zf.writestr(f"{carpeta}/protocolo.geojson", exportar_geojson(visitas))
            zf.writestr(f"{s.replace(' ', '_')}/puntos.csv", consultar_puntos(s).to_csv(index=False).encode("utf-8-sig"))
            for m in MODULOS:
                df = consultar(m, s)
                zf.writestr(f"{s.replace(' ', '_')}/{m}.csv", df.to_csv(index=False).encode("utf-8-sig"))
    return buffer.getvalue()
