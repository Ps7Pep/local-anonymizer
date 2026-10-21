# 🔐 Datathon Anonymizer

> Local and portable tool for preparing anonymized clinical datasets for health datathons.

**[🇪🇸 Castellano](docs/README.es.md) · [🇨🇦 Català](docs/README.ca.md)**

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)](https://docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## What is it?

A web application **deployable locally with a single Docker command** that allows any healthcare centre to:

1. Upload a clinical CSV in standard long format
2. Classify variables as quasi-identifiers or non-identifying
3. Define generalizations for each quasi-identifier
4. Apply **k-anonymity** with suppression of non-conforming records
5. Download the anonymized dataset and a **complete report** for the Data Protection Officer

No data leaves the server. Everything runs locally, with no dependency on external services.

---

## Quick start

### Option A — Pre-built image (recommended, no internet required on the target machine)

```bash
# 1. Clone the repository (only needs docker-compose.yml and sample_data/)
git clone https://github.com/Ps7Pep/local-anonymizer.git
cd local-anonymizer

# 2. Pull the pre-built image and start
docker compose up -d

# 3. Open your browser
# → http://localhost:8092
```

### Option B — Build from source (requires internet)

```bash
git clone https://github.com/Ps7Pep/local-anonymizer.git
cd local-anonymizer
docker compose up --build -d
```

### Option C — Air-gapped / no internet server (SERGAS, hospital networks)

From a machine with internet access:
```bash
docker pull ghcr.io/ps7pep/local-anonymizer:latest
docker save ghcr.io/ps7pep/local-anonymizer:latest -o local-anonymizer.tar
```

Copy `local-anonymizer.tar` and `docker-compose.yml` to the target server, then:
```bash
docker load -i local-anonymizer.tar
docker compose up -d
```

To stop:
```bash
docker compose down
```

> **Custom port**: edit the left-hand port in `docker-compose.yml` (e.g. `"8092:8000"`)

---

## Sample datasets

If you want to test the tool before using your own data, you can download these synthetic datasets:

**Single-file mode** (one CSV with all variables):

- [`dataset_2000p.csv`](https://raw.githubusercontent.com/Ps7Pep/local-anonymizer/refs/heads/main/sample_data/dataset_2000p.csv) — 2,000 patients, all 65 clinical variables in one file

**Multi-file mode** (same patients, variables split across thematic files):

- [`1_determinantes_sociales.csv`](https://raw.githubusercontent.com/Ps7Pep/local-anonymizer/refs/heads/main/sample_data/1_determinantes_sociales.csv) — social determinants
- [`2_salud_mental_conductual.csv`](https://raw.githubusercontent.com/Ps7Pep/local-anonymizer/refs/heads/main/sample_data/2_salud_mental_conductual.csv) — mental and behavioural health
- [`3_funcionalidad_autonomia.csv`](https://raw.githubusercontent.com/Ps7Pep/local-anonymizer/refs/heads/main/sample_data/3_funcionalidad_autonomia.csv) — functionality and autonomy
- [`4_complejidad_clinica.csv`](https://raw.githubusercontent.com/Ps7Pep/local-anonymizer/refs/heads/main/sample_data/4_complejidad_clinica.csv) — clinical complexity

Upload all four together to test multi-file mode (drag & drop several files at once, or Ctrl+click in the file picker).

All datasets share the canonical 4-column format (`pacient`, `data`, `item`, `valor`) and contain entirely synthetic data. No real patient information is involved.

## Input CSV format

The tool accepts **one or more CSV files** in standard long format (one row per patient-date-variable).

> **⚠ One session = one dataset.** Multi-file mode is only for a single dataset split into thematic domains (same patient universe, different clinical variables in each file — e.g. social determinants in one file, functional autonomy in another). It is **not** for independent datasets such as one CSV per care line (primary care, hospital, long-term care). Independent datasets must be anonymized in **separate sessions**, otherwise the tool will mix their patient universes when applying k-anonymity. The frontend asks you to confirm this before processing when more than one file is uploaded.

If your data is split into related domain files, you can upload them all at once. The tool concatenates them internally, applies the anonymization pipeline on the combined dataset, and returns one anonymized CSV per original file.

**Requirements when uploading multiple files:**

- Each file must have **exactly 4 columns**: `pacient`, `data`, `item`, `valor`
- All files must share the **same patient identifier** (same values in the `pacient` column for the same patient)
- Variables must **not overlap** between files — each clinical variable should appear in only one file
- All files must describe the **same population** — if they don't (independent datasets, different care lines, different cohorts), process them in separate sessions

Column names are automatically detected via alias matching:

| Column | Accepted names | Description |
|--------|---------------|-------------|
| `pacient` | `patient_id`, `pacient_id`, `nhc`, `pid` | Unique patient identifier |
| `data` | `date`, `fecha`, `datetime`, `timestamp` | Visit or observation date |
| `item` | `variable`, `var`, `field`, `measure` | Clinical variable name |
| `valor` | `value`, `val`, `resultat`, `result` | Observed value |

The application automatically detects column name variants and normalises them internally.

**Custom column names are fine.** If one or more of your columns doesn't match the aliases above, the upload screen falls back to **positional inference** — it assumes the 1st column is `pacient`, the 2nd is `data`, the 3rd is `item` and the 4th is `valor` — and shows you a preview plus four dropdowns so you can confirm the assignment or pick a different column for any field before continuing. The upload never silently fails on unrecognised names; you either accept the proposal in one click or remap it explicitly.

### Example rows

```csv
patient_id,data,variable,valor
P0001,2023-02-15,estado_cognitivo,deterioro_leve
P0001,2023-02-15,edad,67
P0001,2023-02-15,fragilidad,fragil
P0001,2023-03-28,estado_cognitivo,deterioro_moderado
```

---

## Application flow

```
┌──────────────┐    ┌──────────────────┐    ┌──────────────────┐    ┌──────────────┐
│  1. Upload   │───▶│ 2. Classification│───▶│ 3. Generalization│───▶│ 4. K-anon.  │
│  CSV + profile│   │ QI / non-ID      │    │ bins / categories│    │ + results   │
└──────────────┘    └──────────────────┘    └──────────────────┘    └──────────────┘
```

### Phase 1 — Upload and profiling

- Accepts UTF-8, Latin-1, CP1252 encodings
- Automatically detects variable type (numeric vs. categorical)
- Shows statistics, value distribution and data preview
- **Column mapping confirmation**: column names are first matched against the alias table. If any of the four canonical columns (`pacient`, `data`, `item`, `valor`) can't be detected by name, the UI shows a preview of the file and four dropdowns pre-filled with a proposal based on column order — you confirm or adjust before continuing, so the upload never silently fails on unrecognised headers.
- **Timestamp format auto-detection**: tries ISO 8601, day-first (`DD/MM/YYYY`) and month-first (`MM/DD/YYYY`) on the `data` column, picks the format with fewest parse failures, and previews five sample values so you can override the choice if the interpretation is wrong. Timestamps with hours/minutes are supported and preserved at minute resolution.
- **Multi-file safety check**: when more than one CSV is uploaded, the UI shows per-file stats (records, unique patients, variables), the share of patients common to all files, and a list of variables appearing in more than one file. A confirmation checkbox is required before continuing — see [Input CSV format](#input-csv-format).

### Phase 2 — Variable classification

For each variable, the user indicates its role:

| Role | Automatic treatment |
|------|---------------------|
| 🔑 Direct identifier (`pacient`) | Irreversible SHA-256 hash (prefix `H-`) |
| 📅 Date (`data`) | Integer delta in **minutes** since each patient's first visit (preserves intra-day differences) |
| 🔍 Quasi-identifier | User-defined generalization + k-anonymity |
| ✅ Non-identifying | No changes |

### Phase 3 — Generalizations

For each quasi-identifier, the user defines how to group values:

- **Numeric variables** → custom intervals (e.g. age → `0-17`, `18-39`, `40-64`, `65+`)
- **Categorical variables** → mapping of original values to broader groups

Missing values (NaN) are automatically imputed:
- Categorical → `Desconocido`
- Numeric → median of the observed set

### Phase 4 — K-anonymity and results

- **Preview simulation**: shows the impact of k=2, 3, 4, 5 before running
- **Parameter k**: every quasi-identifier combination must appear in ≥ k patients
- **Suppression**: patients in groups below k are removed from the final dataset
- **Metrics**: patient flow, equivalence class distribution, suppressed groups

---

## Security guarantees

The protection offered by this process rests on **three independent and complementary layers**:

### Layer 1 — Technical (applied transformations)

| Transformation | Protection |
|---------------|------------|
| SHA-256 hash on patient ID | Irreversible pseudonymisation |
| Timestamp → integer minute delta (per patient) | Absolute dates destroyed; intra-day patterns preserved |
| Quasi-identifier generalization | Cross-linkage granularity eliminated |
| K-anonymity | Mathematical impossibility of singling out |

### Layer 2 — Statistical (sampling uncertainty)

The datathon dataset is a **random sample** of a much larger population. A potential attacker cannot know a priori whether a specific individual is in the dataset at all. This uncertainty — recognised by ENISA and the Article 29 Working Party as a re-identification risk mitigating factor — makes any re-identification attempt speculative and unreliable, regardless of the attacker's background knowledge.

### Layer 3 — Organizational (datathon environment)

- **Accredited participants**: access restricted to a pre-selected, registered group
- **Data Use Agreement**: all participants sign a binding commitment prohibiting any re-identification attempt
- **Secure infrastructure**: event hosted on **Instituto de Salud Carlos III (Madrid)** servers, managed by qualified ISCIII staff
- **Closed environment**: data cannot be extracted outside the controlled systems

> The combination of these three layers provides protection **substantially above** what GDPR and ENISA guidelines require for health research data.

---

## Generated outputs

| File | Format | For |
|------|--------|-----|
| `*_anonymized.csv` | CSV | Datathon participants (single file upload) |
| `datasets_anonymized.zip` | ZIP | Datathon participants (multiple file upload — one CSV per original file) |
| `*_report.html` (single file) / `anonymization_report.html` (multi-file) | Styled HTML | DPO (printable as PDF from browser) |
| `anonymization_report.json` | JSON | Audit and traceability |

### DPO report

The HTML report (printable as PDF via Ctrl+P) includes:

1. Executive summary with key metrics
2. Original dataset description
3. Applicable legal framework (GDPR, LOPDGDD, Art. 29 WP Opinion 05/2014)
4. Description of all applied transformations
5. Results and equivalence class distribution
6. Three-layer security guarantee analysis
7. Technical certification checklist

---

## Repository structure

```
local-anonymizer/
│
├── app/
│   ├── main.py                    # FastAPI: endpoints and session management
│   └── modules/
│       ├── anonymizer.py          # All anonymization logic
│       ├── report_md.py           # Markdown report generation (ca/es/en)
│       └── report_html.py         # Markdown → styled HTML conversion
│
├── static/
│   ├── index.html                 # 4-phase wizard interface
│   ├── css/styles.css             # Styles (clinical dark mode)
│   └── js/
│       ├── app.js                 # Frontend logic (vanilla JS)
│       └── i18n.js                # Translations: Catalan, Spanish, English
│
├── docs/
│   ├── README.es.md               # Spanish README
│   └── README.ca.md               # Catalan README
│
├── sample_data/
│   ├── dataset_2000p.csv          # Synthetic dataset — 2,000 patients (single file)
│   └── 1_… 4_….csv               # Same 2,000 patients split across 4 thematic files
│
├── generate_synthetic.py          # Script to regenerate the single-file dataset
├── generate_multifile_sample.py   # Script to regenerate the 4 thematic files
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## Technical architecture

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.12 + FastAPI |
| Frontend | Pure HTML/CSS/JS (no frameworks) |
| Container | Docker + Docker Compose |
| Python dependencies | pandas, numpy, fastapi, uvicorn, markdown |
| Session state | In-memory (not persisted) |
| Communication | REST JSON API |

The application has no database, uses no tracking cookies, and generates no persistent logs containing uploaded file data.

---

## Multilingual

The interface is available in **Catalan**, **Spanish** and **English**. Language is selected with the sidebar buttons and affects both the interface and the generated reports.

---

## Synthetic dataset generation

`generate_synthetic.py` produces the single-file dataset of 2,000 patients × 2 visits × 65 variables. `generate_multifile_sample.py` produces a 4-file split of the *same* 2,000 patients with the 65 variables distributed across 4 thematic files — ideal for testing the multi-file upload feature:

```bash
python3 generate_synthetic.py          # → sample_data/dataset_2000p.csv
python3 generate_multifile_sample.py   # → sample_data/1_…csv … 4_…csv (2,000 patients each)
```

---

## Requirements

- [Docker](https://docs.docker.com/get-docker/) ≥ 24.0
- [Docker Compose](https://docs.docker.com/compose/) ≥ 2.0
- No other dependencies on the host

---

## Legal framework

This project supports compliance with:

- **GDPR (EU Regulation 2016/679)** — Art. 89 and Recital 26 on processing for research
- **LOPDGDD (LO 3/2018)** — Spanish transposition of GDPR
- **Article 29 Working Party Opinion 05/2014** — k-anonymity as a recognised technique
- **ENISA guidelines** on health data anonymization

> ⚠️ This tool facilitates the technical process, but responsibility for variable classification and report validation rests with the centre's Data Protection Officer.

---

## Licence

MIT — Free for use, modification and distribution. Attribution appreciated.

---

## Contributions

Pull requests welcome. For major changes, please open an issue first.

---

*Built for healthcare centres wishing to participate in datathons while protecting their patients' privacy.*
