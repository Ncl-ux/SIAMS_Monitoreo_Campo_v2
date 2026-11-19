# SIAMS · Protocolo de campo

Actualización incremental para SIAMS_Monitoreo_Campo_v2, rama main. Conserva las tres áreas anteriores y el catálogo de puntos. La tabla `protocolo_campo` es independiente; no duplica automáticamente las mediciones en muestreo, hidroquímica o sondas. Las visitas se consultan y analizan en la pestaña 06. Los resultados isotópicos se completan en laboratorio. El d-excess se calcula en ‰. Las banderas QC señaladas en la página pública son criterios de revisión, no de rechazo. Se excluyen los registros señalados del análisis por defecto.

## Instalación y pruebas

Con Streamlit detenido y el entorno virtual activado, ejecutar `python ruta/aplicar_protocolo.py --destino .`. El instalador crea un respaldo local del código y SQLite fuera del repo. Ejecutar `python -m unittest discover -s tests`, luego `python -m streamlit run app.py`. Verificar una visita de prueba y eliminarla antes de usar datos reales (no hay borrado desde el módulo por ahora; usar una DB de ensayo con SIAMS_DB_PATH).

## Captura móvil autónoma

La carpeta `campo_movil/` es una PWA estática propia, sin fuentes externas, sin envío al servidor. Almacena registros y fotos en IndexedDB. No necesita Streamlit en funcionamiento una vez preparada. Para probar en el PC: `python -m http.server 8765 --directory campo_movil`, abrir http://localhost:8765/. Para celular, publicar **solo** el directorio campo_movil en un hosting estático HTTPS que autorice el equipo; no publicar datos_locales, archivos JSON reales ni SQLite. Abrir desde el móvil, esperar confirmación de caché, instalar/agregar a inicio según navegador, activar modo avión, reabrir, registrar un ensayo, cerrar/reabrir y exportar JSON. La ubicación exige permiso y puede fallar; ingresar manualmente si ocurre. No se ha desplegado ni probado en celulares reales. Borrar datos del navegador, desinstalar o una política de almacenamiento puede eliminar registros; respaldar después de cada campaña.

Importar el JSON de cada dispositivo en Streamlit, pestaña 06 > Importar / móvil, seleccionando la sede correspondiente. Un archivo con varias sedes se debe separar por sede (o exportar por sede desde el capturador). Si el mismo ID tiene cambios, la importación se detiene sin sobrescribir. El catálogo de puntos móvil se genera a partir de visitas en ese dispositivo; no se sincroniza automáticamente con el catálogo de escritorio. Reutilizar ID cuando se trabaje desde varios dispositivos.

## Esquema y privacidad

CSV, JSON y GeoJSON incluyen todos los campos visibles en el formulario público y campos internos adicionales. El orden/nombre exacto de columnas del CSV v1.0 original no se pudo verificar desde la página pública; por tanto no se garantiza compatibilidad byte a byte ni con un importador externo. El JSON de esta PWA sí corresponde al importador incluido. Las fotos permanecen en IndexedDB o SQLite y en JSON/ZIP; no van en CSV ni GeoJSON. Los rangos QC siguen los visibles en https://observatorio-siams.vercel.app/campo/. Usar solo coordenadas autorizadas. No hacer commit de registros, fotos o respaldos reales. No hay autenticación institucional ni envío automático implementados.
