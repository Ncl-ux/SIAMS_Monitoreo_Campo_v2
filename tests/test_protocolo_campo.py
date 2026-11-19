import unittest, tempfile, json, io, zipfile
from pathlib import Path
import almacenamiento as a
import protocolo_campo as p

class TestProtocolo(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.original=a.DB_PATH; a.DB_PATH=Path(self.tmp.name)/'test.db'
    def tearDown(self):
        a.DB_PATH=self.original; self.tmp.cleanup()
    def base(self,**kwargs):
        r=dict(sede='Leticia',punto_id='POZO-01',operador='Prueba',tipo_agua='Subterránea',inicio='2025-01-01T08:00:00-05:00',fin='2025-01-01T09:00:00-05:00',nivel_m=4,referencia_nivel='brocal',ph=7,latitud=-4,longitud=-70,muestra_isotopica='Sí',frasco_id='F-01',fecha_calibracion='2024-12-30'); r.update(kwargs); return r
    def test_qc(self):
        r=p.normalizar(self.base()); self.assertEqual(r['qc_flag'],'OK'); self.assertIsNone(r['d_excess']); self.assertEqual(r['inicio'],'2025-01-01T08:00:00-05:00')
        r=p.normalizar(self.base(ph=20,nivel_m=-1,latitud=None,longitud=-90,frasco_id='',fecha_calibracion='2025-01-03',fin='2024-01-01',delta18o=-55)); self.assertEqual(set(r['qc_flag'].split('|')),{'R_PH','R_NIVEL','R_COORD','R_ISO','F_GPS','F_FECHA','F_FRASCO','F_CALIB'})
        self.assertIn('F_TIPO',p.normalizar(self.base(tipo_agua='Lluvia'))['qc_flag'])
    def test_laboratorio(self):
        r=p.normalizar(self.base()); p.almacenar_lote([r]); q=p.actualizar_laboratorio('Leticia',r['registro_id'],-8,-54); self.assertEqual(q['d_excess'],10); self.assertEqual(q['qc_flag'],'OK'); self.assertEqual(p.consultar_protocolo('Leticia')[0]['delta18o'],-8)
    def test_reimportacion(self):
        r=p.normalizar(self.base()); self.assertEqual(p.almacenar_lote([r]),(1,0)); self.assertEqual(p.almacenar_lote(p.leer_json(p.exportar_json([r]))),(0,1)); q=dict(r,ph=8); self.assertRaises(ValueError,p.almacenar_lote,[q]); self.assertEqual(p.consultar_protocolo('Leticia')[0]['ph'],7)
    def test_atomicidad(self):
        r=p.normalizar(self.base()); p.almacenar_lote([r]); nuevo=p.normalizar(self.base(punto_id='OTRO')); self.assertRaises(ValueError,p.almacenar_lote,[nuevo,dict(r,ph=8)]); self.assertEqual(len(p.consultar_protocolo('Leticia')),1)
    def test_fotos_exportaciones(self):
        f={'nombre':'test.png','mime':'image/png','base64':'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aMZkAAAAASUVORK5CYII='}; r=p.normalizar(self.base(fotos=[f])); p.almacenar_lote([r]); rr=p.consultar_protocolo('Leticia'); self.assertEqual(p.leer_json(p.exportar_json(rr))[0]['fotos'],[f]); self.assertEqual(json.loads(p.exportar_geojson(rr))['features'][0]['geometry']['coordinates'],[-70,-4]); self.assertIn('qc_flag',p.exportar_csv(rr).decode('utf-8-sig')); z=zipfile.ZipFile(io.BytesIO(p.exportar_zip(rr))); self.assertIn('fotos/registro_00001_1.png',z.namelist()); self.assertIn('Leticia/protocolo.json',zipfile.ZipFile(io.BytesIO(a.crear_backup('Leticia'))).namelist()); self.assertRaises(ValueError,p.normalizar,self.base(fotos=[dict(f,base64='bad')]))
    def test_separacion(self):
        a.guardar('muestreo','Leticia',[{'muestra_id':'M1','punto_id':'POZO-01','fecha':'2025-01-01','ph':7}]); p.almacenar_lote([self.base()]); self.assertEqual(len(a.consultar('muestreo','Leticia')),1); self.assertEqual(len(p.consultar_protocolo('Leticia')),1); self.assertEqual(p.consultar_protocolo('Tumaco'),[])
    def test_validacion(self):
        for q in [self.base(ph='nan'),self.base(operador=''),self.base(precision_gps_m=-1)]: self.assertRaises(ValueError,p.normalizar,q)
        self.assertRaises(ValueError,p.almacenar_lote,[self.base()], 'Tumaco')
if __name__=='__main__': unittest.main()
