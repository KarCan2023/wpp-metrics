
# 📊 Resumen mensual Treble.ai — Streamlit

App sencilla para cargar tu export de **Treble.ai** (CSV/XLSX), escoger **año** y **mes**, y obtener:
- ✅ Conteo total de registros (y celulares únicos) del mes
- ✅ Conteos por valor para columnas clave (estado de despliegue, conversación, sesión, `deployment_squad`, etc.)
- ✅ Tendencias mensuales (MoM) para toda la base (barras y líneas)
- ✅ Descargas: CSV, ZIP de conteos y Excel con múltiples hojas

> **Suposición:** cada fila representa un mensaje/evento/disparo dentro del mes. Si tu definición de “WhatsApp enviados” es distinta, puedes filtrar/ajustar la export o indicarme la columna que lo distingue para adaptar la lógica.

---

## 🚀 Deploy en Streamlit Cloud (gratis)
1. Sube estos archivos a un repo público en GitHub, por ejemplo: `carlos/treble-monthly-summary`
2. Ve a [share.streamlit.io](https://share.streamlit.io/) y conecta el repo.
3. En “Main file path” pon `app.py`. La versión de Python la detecta automáticamente.
4. ¡Listo! Compártelo con tu equipo.

## 🧰 Uso local
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 📂 Formato esperado
Columnas sugeridas (no todas son obligatorias):  
`Celular, Fecha del despliegue, Estado del despliegue, Estado de la conversación, Estado de la sesión, última actividad, deployment_squad, hubspot_firstname, hubspot_mensaje_2, hubspot_treble_avances_emp_0, hubspot_transferir_asesor`

- La **columna de fecha** se puede elegir en la UI (por defecto intenta detectar `Fecha del despliegue`).
- Se aceptan CSV y XLSX. Para XLSX puedes especificar el nombre de la hoja.

## ✍️ Notas
- La app autodetecta formato de fecha (día/mes/año o mes/día/año). Si ves meses raros, revisa tu export.
- El **resumen del mes** muestra:
  - Total de **registros** (filas) y **celulares únicos**
  - Conteo por valor de las columnas seleccionadas
- La sección **Tendencias** muestra totales por mes y un pivot Mes × Valor por columna.

## 🔧 Personalizaciones comunes
- Cambiar la columna base para “mensajes enviados” si tienes un campo booleano/estado específico.
- Aplicar filtros permanentes (por ejemplo, `Estado del despliegue == 'ENVIADO'`).
- Conectar a Google Sheets directamente (se puede añadir `gspread` + credenciales de servicio).

---

Hecho con ❤️ por y para operadores de growth que necesitan reportes rápidos y sin rodeos.
