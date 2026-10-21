# 🔐 Datathon Anonymizer

> Local and portable tool for preparing anonymized clinical datasets for health datathons.

**[🇪🇸 Castellano](docs/README.es.md) · [🇨🇦 Català](docs/README.ca.md)**

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.156-009688?logo=fastapi)](https://fastapi.tiangolo.com)
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

> **Port and network access**: by default the app only listens on the local machine (`"127.0.0.1:8092:8000"` in `docker-compose.yml`). To change the port, edit `8092`. If the tool runs on a server and must be reached from another workstation, change the mapping to `"8092:8000"` — deliberately, and only on a trusted internal network: the app has no authentication. With `docker run`, use `-p 127.0.0.1:8092:8000`.
>
> **Session lifetime**: data lives only in memory and is discarded after 120 minutes of inactivity (`SESSION_TTL_MINUTES` in `docker-compose.yml`), or immediately with "New session".

---

## Sample datasets

If you want to test the tool before using your own data, `sample_data/` contains synthetic datasets built on the **CCI-SNS catalogue** (5 domains, the 42 active variables with their provisional categories; copy in [`catalogo_cci_sns/`](catalogo_cci_sns/)). There is **one dataset per care line** — independent populations, so each one is a separate session:

| Line | Single file | Patients | Profile |
|---|---|---|---|
| AH — hospital care | [`AH/dataset_AH.csv`](https://raw.githubusercontent.com/Ps7Pep/local-anonymizer/refs/heads/main/sample_data/AH/dataset_AH.csv) | 2,000 | admission + reassessment, with time of day; acute episodes |
| AP — primary care | [`AP/dataset_AP.csv`](https://raw.githubusercontent.com/Ps7Pep/local-anonymizer/refs/heads/main/sample_data/AP/dataset_AP.csv) | 2,000 | younger, mostly autonomous |
| LE — long-term care | [`LE/dataset_LE.csv`](https://raw.githubusercontent.com/Ps7Pep/local-anonymizer/refs/heads/main/sample_data/LE/dataset_LE.csv) | 2,000 | elderly, dependent, frequent cognitive impairment |

**Multi-file mode:** each line is also split into 5 files, one per CCI-SNS domain (`<line>_D1_funcional_motor.csv` … `<line>_D5_social_contextual.csv`, same folder). Upload the 5 files of one line together (drag & drop several files, or Ctrl+click in the file picker): the result is identical to uploading that line's single file.

Format: `patient_id, fecha, variable, valor` — `variable` is the catalogue name and `valor` is what a clinical record would hold: the **raw instrument score** when the category defines a range (Barthel 0–100, MMSE 0–30, Braden, GAD-7, Zarit, BMI, glycaemia…), otherwise the category label. All data is entirely synthetic; no real patient information is involved.

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
patient_id,fecha,variable,valor
AH00042,2024-03-02 09:15,Actividades básicas de la vida diaria (ABVD),75
AH00042,2024-03-02 09:15,Estado cognitivo,22
AH00042,2024-03-02 09:15,Continencia,Incontinencia ocasional urinaria
AH00042,2024-03-02 09:15,Edad,81
AH00042,2024-03-06 11:40,Actividades básicas de la vida diaria (ABVD),85
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
| 🔑 Direct identifier (`pacient`) | HMAC-SHA256 with a random per-session key that is never stored (prefix `H-`) |
| 📅 Date (`data`) | Integer delta in **minutes** since each patient's first visit (preserves intra-day differences) |
| 🔍 Quasi-identifier | User-defined generalization + k-anonymity |
| ✅ Non-identifying | No changes |

### Phase 3 — Generalizations

For each quasi-identifier, the user defines how to group values:

- **Numeric variables** → custom intervals (e.g. age → `0-17`, `18-39`, `40-64`, `65+`)
- **Categorical variables** → mapping of original values to broader groups

Missing values (NaN) are automatically imputed on the original values, before generalization:
- Categorical → `Desconocido`
- Numeric → median of the observed set

Nothing falls out of a generalization silently: numeric values outside the cut points become `Fuera de rango`, non-numeric values in a binned item become `Desconocido`, and the counts (plus values without a category mapping) are shown in the results and in the report.

### Phase 4 — K-anonymity and results

- **Preview simulation**: shows the impact of k=2, 3, 4, 5 before running
- **Parameter k**: every quasi-identifier combination must appear in ≥ k patients
- **Longitudinal signature**: a patient's combination is the set of all values each quasi-identifier takes across their visits (e.g. age band `60-64 | 65+`), so k also holds when a quasi-identifier changes between visits
- **Suppression**: patients in groups below k are removed from the final dataset
- **Metrics**: patient flow, equivalence class distribution, suppressed groups

---

## Security guarantees

The protection offered by this process rests on **three independent and complementary layers**:

### Layer 1 — Technical (applied transformations)

| Transformation | Protection |
|---------------|------------|
| HMAC-SHA256 on patient ID (per-session secret key, discarded) | Pseudonymisation that cannot be reversed by dictionary attack |
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
│   ├── css/styles.css             # Styles (light institutional theme)
│   ├── fonts/                     # IBM Plex Sans/Mono, bundled (OFL) — no external requests
│   └── js/
│       ├── app.js                 # Frontend logic (vanilla JS)
│       └── i18n.js                # Translations: Catalan, Spanish, English
│
├── docs/
│   ├── README.es.md               # Spanish README
│   └── README.ca.md               # Catalan README
│
├── sample_data/
│   └── AH/ AP/ LE/                # One synthetic dataset per care line (2,000 patients each)
│                                  #   dataset_<line>.csv + 5 files, one per CCI-SNS domain
├── catalogo_cci_sns/              # CCI-SNS variables and provisional categories (copy; used by the generator)
│
├── generate_synthetic.py          # Generates the single-file synthetic dataset
├── generate_multifile_sample.py   # Splits it into the 4 thematic files (exact partition)
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

`generate_synthetic.py` reads the CCI-SNS catalogue in `catalogo_cci_sns/` and produces one dataset per care line (AH, AP, LE): 2,000 patients × 2 assessments × the 42 active variables, modelled on a real clinical extract:

- values are raw instrument scores (Barthel, Lawton, Braden, MNA-SF, MMSE, EVA, GAD-7, PHQ-9, DAST-10, Padua, glycaemia, Fried, number of drugs, BMI, MOS, De Jong Gierveld, Zarit, HLS19) whenever the category defines a range — applying the catalogue ranges gives exactly the category — and category labels otherwise. The generator stops if a scale no longer matches its variable's categories;
- each patient has a fixed profile (sex, migration, TSI, health literacy, caregiver, GMA); age is computed at each assessment from the birth date, so it can go up by one year;
- a latent complexity level per patient, different per line (LE > AH > AP), drives the clinical variables; acute situations (haemodynamic instability, delirium, acute pain…) depend on the line and are mostly hospital episodes;
- an assessment that was not done has no row; «No evaluable» appears only where the catalogue has it (more often with cognitive impairment); adult instruments are not recorded for minors.

`generate_multifile_sample.py` does **not** generate new data: it splits each line's dataset into 5 files, one per domain. The union of the 5 files is exactly the line's dataset, so uploading them together or the single file gives the same result.

```bash
# inside the container (the host needs no Python)
docker compose run --rm -v "${PWD}:/work" -w /work anonymizer \
  sh -c "python generate_synthetic.py && python generate_multifile_sample.py"
```

### Processing order

The tool follows the same logic you would apply to a real extract:

1. **Coherence first** — every value is read as text (patient IDs keep leading zeros and never turn into `12.0`), IDs are trimmed, rows without a patient or a variable are discarded and reported, and all files are combined into one dataset before anything is transformed.
2. **Transformations on the real IDs** — date deltas, imputation, generalization and k-anonymity.
3. **Pseudonymization last** — the HMAC is applied at the very end, only to the released records, with the same session key for every file, so a patient keeps the same `H-…` in every output table.

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
