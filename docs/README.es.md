# 🔐 Datathon Anonymizer

> Herramienta local y portable para la preparación de datasets clínicos anonimizados para datathons sanitarios.

**[🇬🇧 English](../README.md) · [🇨🇦 Català](README.ca.md)**

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)](https://docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](../LICENSE)

---

## ¿Qué es?

Una aplicación web **desplegable en local con un único comando Docker** que permite a cualquier centro sanitario:

1. Cargar un CSV de datos clínicos en formato largo estándar
2. Clasificar las variables como cuasi-identificadores o no identificativas
3. Definir generalizaciones para cada cuasi-identificador
4. Aplicar **k-anonimidad** con supresión de registros no conformes
5. Descargar el dataset anonimizado y un **informe completo** para el Delegado de Protección de Datos

Ningún dato sale del servidor. Todo se ejecuta en local, sin dependencia de servicios externos.

---

## Inicio rápido

```bash
# 1. Clona el repositorio
git clone https://github.com/Ps7Pep/local-anonymizer.git
cd local-anonymizer

# 2. Arranca la aplicación
docker compose up --build -d

# 3. Abre el navegador
# → http://localhost:8092
```

Para detener:

```bash
docker compose down
```

> **Puerto personalizado**: modifica el puerto izquierdo en `docker-compose.yml` (ej: `"8092:8000"`)

---

## Datasets de ejemplo

Si quieres probar la herramienta antes de utilizar tus propios datos, puedes descargar estos datasets sintéticos:

**Modo de fichero único** (un solo CSV con todas las variables):

- [`dataset_2000p.csv`](https://raw.githubusercontent.com/Ps7Pep/local-anonymizer/refs/heads/main/sample_data/dataset_2000p.csv) — 2.000 pacientes, las 65 variables clínicas en un único fichero

**Modo multi-fichero** (mismos pacientes, variables repartidas en ficheros temáticos):

- [`1_determinantes_sociales.csv`](https://raw.githubusercontent.com/Ps7Pep/local-anonymizer/refs/heads/main/sample_data/1_determinantes_sociales.csv) — determinantes sociales
- [`2_salud_mental_conductual.csv`](https://raw.githubusercontent.com/Ps7Pep/local-anonymizer/refs/heads/main/sample_data/2_salud_mental_conductual.csv) — salud mental y conductual
- [`3_funcionalidad_autonomia.csv`](https://raw.githubusercontent.com/Ps7Pep/local-anonymizer/refs/heads/main/sample_data/3_funcionalidad_autonomia.csv) — funcionalidad y autonomía
- [`4_complejidad_clinica.csv`](https://raw.githubusercontent.com/Ps7Pep/local-anonymizer/refs/heads/main/sample_data/4_complejidad_clinica.csv) — complejidad clínica

Súbelos los cuatro a la vez para probar el modo multi-fichero (arrastra y suelta varios ficheros al mismo tiempo, o Ctrl+clic en el selector de ficheros).

Todos los datasets siguen el formato canónico de 4 columnas (`pacient`, `data`, `item`, `valor`) y contienen datos completamente sintéticos. No incluyen información real de pacientes.

## Formato del CSV de entrada

La herramienta acepta **uno o más ficheros CSV** en formato largo (una fila por paciente-fecha-variable).

> **⚠ Una sesión = un dataset.** El modo multi-fichero es solo para un mismo dataset dividido en dominios temáticos (mismo universo de pacientes, variables clínicas distintas en cada fichero — p. ej. determinantes sociales en uno, autonomía funcional en otro). **No** es para datasets independientes como un CSV por línea asistencial (atención primaria, hospitalaria, sociosanitaria). Los datasets independientes deben anonimizarse en **sesiones separadas**; de lo contrario, la herramienta mezclará sus universos de pacientes al aplicar la k-anonimidad. El frontend te pide confirmarlo antes de procesar cuando subes más de un fichero.

Si tus datos están repartidos en ficheros temáticos relacionados, puedes subirlos todos a la vez. La herramienta los combina internamente y devuelve un CSV anonimizado por cada fichero original.

**Requisitos cuando se suben múltiples ficheros:**

- Cada fichero debe tener **exactamente 4 columnas**: `pacient`, `data`, `item`, `valor`
- Todos los ficheros deben compartir el **mismo identificador de paciente**
- Las variables **no deben repetirse** entre ficheros
- Todos los ficheros deben describir la **misma población** — si no es así (datasets independientes, líneas asistenciales distintas, cohortes distintas), procesa cada uno en una sesión separada

La aplicación detecta automáticamente las variantes del nombre de columna y las normaliza internamente. El nombre de las variables clínicas puede ser cualquiera — la app se adapta al contenido de cada fichero.

**Los nombres de columna personalizados también valen.** Si alguna de las 4 columnas no coincide con los alias anteriores, la pantalla de carga hace una **inferencia posicional** — asume que la 1ª columna es `pacient`, la 2ª `data`, la 3ª `item` y la 4ª `valor` — y muestra una previsualización con cuatro desplegables para que confirmes la asignación o elijas otra columna para cada campo antes de continuar. La carga nunca falla silenciosamente por nombres no reconocidos: o aceptas la propuesta con un clic o la corriges explícitamente.

### Ejemplo de filas

```csv
patient_id,data,variable,valor
P0001,2023-02-15,estado_cognitivo,deterioro_leve
P0001,2023-02-15,edad,67
P0001,2023-02-15,fragilidad,fragil
P0001,2023-03-28,estado_cognitivo,deterioro_moderado
```

---

## Flujo de la aplicación

```
┌──────────────┐    ┌──────────────────┐    ┌──────────────────┐    ┌──────────────┐
│  1. Carga    │───▶│ 2. Clasificación │───▶│ 3. Generalización│───▶│ 4. K-anon.  │
│  CSV + perfil│    │ QI / no-ID       │    │ bins / categorías│    │ + resultados│
└──────────────┘    └──────────────────┘    └──────────────────┘    └──────────────┘
```

### Fase 1 — Carga y perfilado

- Acepta codificaciones UTF-8, Latin-1, CP1252
- Detecta automáticamente el tipo de cada variable (numérica vs. categórica)
- Muestra estadísticas, distribución de valores y previsualización
- **Confirmación del mapeo de columnas**: los nombres se buscan primero en la tabla de alias. Si alguna de las 4 columnas canónicas (`pacient`, `data`, `item`, `valor`) no se detecta por el nombre, la interfaz muestra una previsualización del fichero y cuatro desplegables precargados con una propuesta basada en el orden de las columnas — confirmas o ajustas antes de continuar, de modo que la carga nunca falle silenciosamente por cabeceras desconocidas.
- **Auto-detección del formato de timestamp**: prueba ISO 8601, day-first (`DD/MM/AAAA`) y month-first (`MM/DD/AAAA`) sobre la columna `data`, escoge el formato con menos errores de parsing y muestra cinco valores de ejemplo para que puedas forzar otra opción si la interpretación no es correcta. Se admiten timestamps con hora/minuto y se conservan con resolución de minutos.
- **Comprobación de seguridad multi-fichero**: al subir más de un CSV, la interfaz muestra estadísticas por fichero (registros, pacientes únicos, variables), la proporción de pacientes comunes a todos los ficheros y la lista de variables que aparecen en más de uno. Se requiere marcar una casilla de confirmación antes de continuar — ver [Formato del CSV de entrada](#formato-del-csv-de-entrada).

### Fase 2 — Clasificación de variables

Para cada variable, el usuario indica su rol:

| Rol | Tratamiento automático |
|-----|----------------------|
| 🔑 Identificador directo (`pacient`) | Hash SHA-256 irreversible (prefijo `H-`) |
| 📅 Fecha (`data`) | Delta entero en **minutos** desde la primera visita del paciente (preserva diferencias intra-día) |
| 🔍 Cuasi-identificador | Generalización definida por el usuario + k-anonimidad |
| ✅ No identificativo | Sin cambios |

### Fase 3 — Generalizaciones

Para cada cuasi-identificador, el usuario define cómo agrupar los valores:

- **Variables numéricas** → intervalos personalizados (ej: edad → `0-17`, `18-39`, `40-64`, `65+`)
- **Variables categóricas** → mapeo de valores originales a categorías más amplias

Los valores ausentes (NaN) se imputan automáticamente:
- Categóricos → `Desconocido`
- Numéricos → mediana del conjunto observado

### Fase 4 — K-anonimidad y resultados

- **Simulación previa**: muestra el impacto de k=2, 3, 4, 5 antes de ejecutar
- **Parámetro k**: cada combinación de cuasi-identificadores debe tener ≥ k pacientes
- **Supresión**: los pacientes en grupos por debajo de k se eliminan del dataset final
- **Métricas**: flujo de pacientes, distribución de clases de equivalencia, grupos suprimidos

---

## Garantías de seguridad

La protección que ofrece este proceso se sustenta en **tres capas independientes y complementarias**:

### Capa 1 — Técnica (transformaciones aplicadas)

| Transformación | Protección |
|---------------|------------|
| Hash SHA-256 del identificador | Seudonimización irreversible |
| Timestamp → delta entero en minutos (por paciente) | Fechas absolutas destruidas; patrones intra-día preservados |
| Generalización de cuasi-IDs | Granularidad de cruce eliminada |
| K-anonimidad | Imposibilidad matemática de singularización |

### Capa 2 — Estadística (incertidumbre de muestreo)

El dataset del datathon es una **muestra aleatoria** de una población clínica mucho mayor. Un potencial atacante no puede saber a priori si una persona concreta está en el dataset. Esta incertidumbre — reconocida por la ENISA y el Grupo de Trabajo del Artículo 29 como factor mitigador del riesgo de reidentificación — hace que cualquier intento de reidentificación sea especulativo y poco fiable, independientemente del conocimiento previo del atacante.

### Capa 3 — Organizacional (entorno del Datathon)

- **Participantes acreditados**: acceso restringido a un grupo limitado, previamente identificado y registrado
- **Acuerdo de uso de datos (DUA)**: todos los participantes firman un compromiso formal que prohíbe expresamente cualquier intento de identificación de individuos, con sanciones en caso de incumplimiento
- **Infraestructura segura**: el evento tiene lugar en los servidores del **Instituto de Salud Carlos III (Madrid)**, gestionados por su propio personal cualificado
- **Entorno cerrado**: los datos no pueden ser exportados fuera de los sistemas controlados de la organización durante el Datathon

> La combinación de estas tres capas proporciona una protección **sustancialmente superior** a lo que exigen el RGPD y las guías de la ENISA para el tratamiento de datos de salud con fines de investigación.

---

## Cuasi-identificadores recomendados

| Variable | Riesgo | Recomendación |
|----------|--------|---------------|
| `edad` | 🔴 Alto | Siempre QI; generalizar en rangos de ≥15 años |
| `sexo_y_o_genero` | 🔴 Alto | Siempre QI |
| `nivel_educativo` | 🟡 Medio | QI si el dataset tiene <500 pacientes |
| `situacion_de_convivencia` | 🟡 Medio | QI si el dataset tiene <500 pacientes |
| `origen` | 🟡 Medio | QI en poblaciones locales pequeñas |
| `estado_cognitivo` | 🟢 Bajo | Opcional; con el muestreo ya hay protección suficiente |
| Resto de variables | 🟢 Muy bajo | No identificativas en contexto de datathon |

Con 2.000 pacientes de una comunidad grande, `edad` + `sexo_y_o_genero` con k=3 ofrece una protección muy robusta.

---

## Salidas generadas

| Fichero | Formato | Para quién |
|---------|---------|-----------|
| `*_anonymized.csv` | CSV | Participantes (un solo fichero subido) |
| `datasets_anonymized.zip` | ZIP | Participantes (múltiples ficheros — un CSV por fichero original) |
| `*_report.html` (single) / `anonymization_report.html` (multi) | HTML estilizado | DPD (imprimible como PDF desde el navegador) |
| `anonymization_report.json` | JSON | Auditoría y trazabilidad |

---

## Estructura del repositorio

```
local-anonymizer/
│
├── app/
│   ├── main.py                    # FastAPI: endpoints y gestión de sesiones
│   └── modules/
│       ├── anonymizer.py          # Toda la lógica de anonimización
│       ├── report_md.py           # Generación de informe Markdown (ca/es/en)
│       └── report_html.py         # Conversión Markdown → HTML estilizado
│
├── static/
│   ├── index.html                 # Interfaz wizard de 4 fases
│   ├── css/styles.css             # Estilos (dark mode clínico)
│   └── js/
│       ├── app.js                 # Lógica frontend (vanilla JS)
│       └── i18n.js                # Traducciones: catalán, castellano, inglés
│
├── docs/
│   ├── README.es.md               # Este fichero
│   └── README.ca.md               # README en catalán
│
├── sample_data/
│   ├── dataset_2000p.csv          # Dataset sintético — 2.000 pacientes (un fichero)
│   └── 1_… 4_….csv               # Los mismos 2.000 pacientes en 4 ficheros temáticos
│
├── generate_synthetic.py          # Script para regenerar el dataset de un fichero
├── generate_multifile_sample.py   # Script para regenerar los 4 ficheros temáticos
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md                      # README principal (inglés)
```

---

## Requisitos

- [Docker](https://docs.docker.com/get-docker/) ≥ 24.0
- [Docker Compose](https://docs.docker.com/compose/) ≥ 2.0
- Sin otras dependencias en el host

---

## Marco legal

Este proyecto ayuda a cumplir con:

- **RGPD (Reglamento UE 2016/679)** — Art. 89 y Considerando 26 sobre tratamiento para investigación
- **LOPDGDD (LO 3/2018)** — Transposición española del RGPD
- **Dictamen 05/2014 del Grupo de Trabajo del Art. 29** — k-anonimidad como técnica reconocida
- **Guías ENISA** sobre anonimización de datos sanitarios

> ⚠️ Esta herramienta facilita el proceso técnico, pero la responsabilidad de la clasificación de variables y la validación del informe recae en el Delegado de Protección de Datos del centro.

---

## Licencia

MIT — Libre para uso, modificación y distribución. Se agradece la atribución.

---

*Construido para centros sanitarios que desean participar en datathons protegiendo la privacidad de sus pacientes.*
