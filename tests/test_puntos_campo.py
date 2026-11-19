import tempfile, unittest, zipfile, io
from pathlib import Path
import pandas as pd
import almacenamiento as a
from puntos import guardar_punto,consultar_puntos,ids_historicos,adjuntar_puntos,completar_punto
from nucleo import MODULOS

class TestPuntos(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.original=a.DB_PATH; a.DB_PATH=Path(self.tmp.name)/'test.db'
        self.data=dict(nombre_punto='Pozo uno',latitud='4.6',longitud='-74.1',codigo_oficial='')
    def tearDown(self): a.DB_PATH=self.original; self.tmp.cleanup()
    def test_nuevo_y_edicion(self):
        pid=guardar_punto('Leticia',self.data)
        self.assertTrue(pid.startswith('SIAMS-')); self.assertEqual(len(consultar_puntos('Leticia')),1)
        self.assertEqual(guardar_punto('Leticia',{**self.data,'nombre_punto':'Editado'},pid),pid)
        self.assertEqual(consultar_puntos('Leticia').iloc[0].nombre_punto,'Editado')
        self.assertTrue(consultar_puntos('Tumaco').empty)
    def test_validacion(self):
        for extra in ({'latitud':'nan'},{'longitud':181},{'latitud':''},{'precision_gps_m':-1},{'altitud_m':80}):
            with self.assertRaises(ValueError): guardar_punto('Leticia',{**self.data,**extra})
    def test_duplicados(self):
        guardar_punto('Leticia',{**self.data,'codigo_oficial':'A1'})
        for data in (self.data,{**self.data,'nombre_punto':'Otro','codigo_oficial':'a1'}):
            with self.assertRaises(ValueError): guardar_punto('Leticia',data)
    def test_historico_y_exportacion(self):
        r={'punto_id':'P-01','muestra_id':'M1','fecha':'2026-11-18','ph':7}
        a.guardar('muestreo','Leticia',[r]); self.assertEqual(ids_historicos('Leticia'),['P-01'])
        antes=a.consultar('muestreo','Leticia'); guardar_punto('Leticia',self.data,'P-01')
        pd.testing.assert_frame_equal(antes,a.consultar('muestreo','Leticia'))
        self.assertEqual(adjuntar_puntos(antes,'Leticia').iloc[0].latitud,4.6)
        with zipfile.ZipFile(io.BytesIO(a.crear_backup('Leticia'))) as z: self.assertIn('Leticia/puntos.csv',z.namelist())
    def test_completar(self):
        df=pd.DataFrame([{'muestra_id':'M1','punto_id':''},{'muestra_id':'','punto_id':''},{'muestra_id':'M2','punto_id':'otro'}])
        self.assertEqual(completar_punto(df,'muestreo','P1').punto_id.tolist(),['P1','','otro'])

if __name__=='__main__': unittest.main()
