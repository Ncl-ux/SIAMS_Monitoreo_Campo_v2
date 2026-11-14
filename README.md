# SIAMS · Captura y análisis de monitoreo

Aplicación local en **Streamlit** para registrar muestreos de campo, resultados hidroquímicos y lecturas de sondas en tablas editables. Presenta estadísticas descriptivas, correlaciones, series temporales, balance iónico orientativo y tendencias de sensores. No consulta servidores externos durante el uso.

## Windows: instalación y arranque

1. Extrae el ZIP y abre la carpeta en VS Code.
2. Con **internet solo la primera vez**, ejecuta `INSTALAR_PRIMERA_VEZ.bat`. Requiere Python 3.11 o superior.
3. Ejecuta `INICIAR_OFFLINE.bat`. En el navegador abre `http://127.0.0.1:8501`.
4. A partir de ese momento puedes trabajar **sin internet** en ese mismo equipo. La aplicación seguirá necesitando que el servidor Streamlit local esté ejecutándose.

### Usarlo en campo desde un celular sin internet

Si tienes un portátil que ejecute la aplicación, conecta el portátil y el celular al **mismo punto de acceso Wi-Fi / hotspot local** (puede no tener internet). Ejecuta `INICIAR_RED_LOCAL.bat` en el portátil y encuentra su dirección IP con `ipconfig`. En el celular entra a `http://IP_DEL_PORTATIL:8501`. La red o el firewall deben permitir conexiones entre dispositivos. El portátil debe permanecer encendido. **Esto no instala la app en el celular**, y cualquier dispositivo en esa red que conozca la dirección podrá acceder a los datos: utiliza solo un hotspot privado y no lo expongas a internet. Para un dispositivo móvil que funcione completamente solo sin servidor se requiere otra implementación, por ejemplo una PWA.

También puedes instalar desde una terminal:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py --server.address 127.0.0.1
```

## Cómo usarlo

- Selecciona una **sede** y un **módulo** en la barra lateral.
- En **01 Registrar**, escribe en la tabla, pega desde Excel o importa un CSV con las columnas indicadas. Al guardar, los datos se almacenan localmente en SQLite.
- En **02 Base de datos**, consulta, busca, exporta y elimina registros seleccionados.
- En **03 Estadística**, revisa n, faltantes, media, mediana, desviación estándar muestral, mínimo, percentiles 25/75, máximo, CV, atípicos IQR, correlación Pearson y resumen por punto. La hidroquímica incluye error de balance iónico y facies exploratoria. Las sondas incluyen variación y pendiente lineal en unidades/día.
- En **04 Gráficas y series**, analiza series temporales, distribuciones y boxplots. Para las sondas selecciona magnitud y referencia compatibles.
- Descarga respaldos ZIP de CSV mediante la barra lateral. El botón de ejemplo inserta **datos ficticios** identificados como simulación.

## Dónde se guardan los datos

Los registros se almacenan en `datos_locales/siams.db` mediante **SQLite**; ese archivo no se sube a GitHub porque está excluido en `.gitignore`. Cada computador mantiene su propia base local. Haz respaldos regulares desde la aplicación; no elimines esa carpeta al actualizar el código. No almacenes información restringida en un equipo compartido sin las medidas institucionales correspondientes.

La aplicación **no sincroniza datos entre investigadores**. Publicar este mismo proyecto en Streamlit Community Cloud no lo convierte en una app offline y su disco no es un almacenamiento duradero; para producción multiusuario se necesita autenticación y una base de datos administrada.

## Alcance del análisis

- **Muestreo:** variables fisicoquímicas y resúmenes exploratorios por punto.
- **Hidroquímica:** calcula la diferencia de cargas `(Σcationes − Σaniones)/(Σcationes + Σaniones) × 100`, con concentraciones transformadas a meq/L y facies por grupo mayoritario (>50 %); no sustituye evaluación experta ni control de laboratorio. Sin siete iones principales completos el balance no se calcula.
- **Sondas:** calcula pendientes con regresión lineal para al menos tres marcas temporales distintas. El valor no equivale a una predicción ni convierte automáticamente profundidad a cota.

## Estructura

- `app.py`: vistas y tablas de Streamlit.
- `nucleo.py`: validación, estadísticas y cálculos de hidroquímica y sondas.
- `almacenamiento.py`: SQLite, exportación CSV y respaldo ZIP.
- `ejemplos.py`: datos ficticios para ilustrar el flujo.
- `tests/`: pruebas del núcleo y la persistencia local.

## Licencias y uso

Prototipo de trabajo. La configuración está pensada para una estación de campo local; no habilita publicación automática de registros ni captura de datos personales por internet.
