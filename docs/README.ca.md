# 🔐 Datathon Anonymizer

> Eina local i portable per a la preparació de datasets clínics anonimitzats per a datathons sanitaris.

**[🇬🇧 English](../README.md) · [🇪🇸 Castellano](README.es.md)**

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)](https://docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](../LICENSE)

---

## Què és?

Una aplicació web **desplegable en local amb un sol comandament Docker** que permet a qualsevol centre sanitari:

1. Carregar un CSV de dades clíniques en format llarg estàndard
2. Classificar les variables com a quasi-identificadors o no identificatives
3. Definir generalitzacions per a cada quasi-identificador
4. Aplicar **k-anonimitat** amb supressió de registres no conformes
5. Descarregar el dataset anonimitzat i un **informe complet** per al Delegat de Protecció de Dades

Cap dada surt del servidor. Tot s'executa en local, sense cap dependència de serveis externs.

---

## Inici ràpid

```bash
# 1. Clona el repositori
git clone https://github.com/Ps7Pep/local-anonymizer.git
cd local-anonymizer

# 2. Arrenca l'aplicació
docker compose up --build -d

# 3. Obre el navegador
# → http://localhost:8092
```

Per aturar:

```bash
docker compose down
```

> **Port personalitzat**: modifica el port esquerre al `docker-compose.yml` (ex: `"8092:8000"`)

---

## Datasets d'exemple

Si vols provar l'eina abans d'utilitzar les teves pròpies dades, pots descarregar aquests datasets sintètics:

**Mode de fitxer únic** (un sol CSV amb totes les variables):

- [`dataset_2000p.csv`](https://raw.githubusercontent.com/Ps7Pep/local-anonymizer/refs/heads/main/sample_data/dataset_2000p.csv) — 2.000 pacients, les 65 variables clíniques en un sol fitxer

**Mode multi-fitxer** (mateixos pacients, variables repartides en fitxers temàtics):

- [`1_determinantes_sociales.csv`](https://raw.githubusercontent.com/Ps7Pep/local-anonymizer/refs/heads/main/sample_data/1_determinantes_sociales.csv) — determinants socials
- [`2_salud_mental_conductual.csv`](https://raw.githubusercontent.com/Ps7Pep/local-anonymizer/refs/heads/main/sample_data/2_salud_mental_conductual.csv) — salut mental i conductual
- [`3_funcionalidad_autonomia.csv`](https://raw.githubusercontent.com/Ps7Pep/local-anonymizer/refs/heads/main/sample_data/3_funcionalidad_autonomia.csv) — funcionalitat i autonomia
- [`4_complejidad_clinica.csv`](https://raw.githubusercontent.com/Ps7Pep/local-anonymizer/refs/heads/main/sample_data/4_complejidad_clinica.csv) — complexitat clínica

Puja'ls tots quatre alhora per provar el mode multi-fitxer (arrossega i deixa anar diversos fitxers a la vegada, o Ctrl+clic al selector de fitxers).

Tots els datasets segueixen el format canònic de 4 columnes (`pacient`, `data`, `item`, `valor`) i contenen dades completament sintètiques. No inclouen informació real de pacients.

## Format del CSV d'entrada

L'eina accepta **un o més fitxers CSV** en format llarg (una fila per pacient-data-variable).

> **⚠ Una sessió = un dataset.** El mode multi-fitxer és només per a un mateix dataset trossejat en dominis temàtics (mateix univers de pacients, variables clíniques diferents a cada fitxer — p. ex. determinants socials en un, autonomia funcional en un altre). **No** és per a datasets independents com un CSV per línia assistencial (atenció primària, hospitalària, sociosanitària). Els datasets independents s'han d'anonimitzar en **sessions separades**; si no, l'eina barrejarà els seus universos de pacients al aplicar la k-anonimitat. El frontend et demana confirmar-ho abans de processar quan puges més d'un fitxer.

Si les teves dades estan repartides en fitxers temàtics relacionats, pots pujar-los tots alhora. L'eina els combina internament i retorna un CSV anonimitzat per cada fitxer original.

**Requisits quan es pugen múltiples fitxers:**

- Cada fitxer ha de tenir **exactament 4 columnes**: `pacient`, `data`, `item`, `valor`
- Tots els fitxers han de compartir el **mateix identificador de pacient**
- Les variables **no s'han de repetir** entre fitxers
- Tots els fitxers han de descriure la **mateixa població** — si no és així (datasets independents, línies assistencials diferents, cohorts diferents), processa cadascun en una sessió separada

L'aplicació detecta automàticament les variantes del nom de columna i les normalitza internament. El nom de les variables clíniques pot ser qualsevol — l'app s'adapta al contingut de cada fitxer.

**Els noms de columna personalitzats també valen.** Si alguna de les 4 columnes no coincideix amb cap dels àlies anteriors, la pantalla de càrrega fa una **inferència posicional** — assumeix que la 1a columna és `pacient`, la 2a `data`, la 3a `item` i la 4a `valor` — i mostra una previsualització amb quatre desplegables perquè confirmis l'assignació o triïs una altra columna per a cada camp abans de continuar. La càrrega no falla mai silenciosament per noms no reconeguts: o acceptes la proposta amb un clic o la corregeixes explícitament.

### Exemple de files

```csv
patient_id,data,variable,valor
P0001,2023-02-15,estado_cognitivo,deterioro_leve
P0001,2023-02-15,edad,67
P0001,2023-02-15,fragilidad,fragil
P0001,2023-03-28,estado_cognitivo,deterioro_moderado
```

---

## Flux de l'aplicació

```
┌──────────────┐    ┌─────────────────┐    ┌──────────────────┐    ┌──────────────┐
│  1. Càrrega  │───▶│ 2. Classificació│───▶│ 3. Generalització│───▶│ 4. k-anon.  │
│  CSV + perfil│    │ QI / no-ID      │    │ bins / categories│    │ + resultats │
└──────────────┘    └─────────────────┘    └──────────────────┘    └──────────────┘
```

### Fase 1 — Càrrega i perfilat

- Accepta codificacions UTF-8, Latin-1, CP1252
- Detecta automàticament el tipus de cada variable (numèrica vs. categòrica)
- Mostra estadístiques, distribució de valors i previsualització
- **Confirmació del mapatge de columnes**: els noms es busquen primer a la taula d'àlies. Si alguna de les 4 columnes canòniques (`pacient`, `data`, `item`, `valor`) no es detecta pel nom, la interfície mostra una previsualització del fitxer i quatre desplegables precarregats amb una proposta basada en l'ordre de les columnes — confirmes o ajustes abans de continuar, de manera que la càrrega no falli mai silenciosament per capçaleres desconegudes.
- **Auto-detecció del format de timestamp**: prova ISO 8601, day-first (`DD/MM/AAAA`) i month-first (`MM/DD/AAAA`) sobre la columna `data`, escull el format amb menys errors de parsing i mostra cinc valors d'exemple perquè puguis forçar una altra opció si la interpretació no és correcta. S'admeten timestamps amb hora/minut i es conserven amb resolució de minuts.
- **Comprovació de seguretat multi-fitxer**: en pujar més d'un CSV, la interfície mostra estadístiques per fitxer (registres, pacients únics, variables), la proporció de pacients comuns a tots els fitxers i la llista de variables que apareixen en més d'un. Cal marcar una casella de confirmació abans de continuar — vegeu [Format del CSV d'entrada](#format-del-csv-dentrada).

### Fase 2 — Classificació de variables

Per a cada variable, l'usuari indica el seu rol:

| Rol | Tractament automàtic |
|-----|---------------------|
| 🔑 Identificador directe (`pacient`) | Hash SHA-256 irreversible (prefix `H-`) |
| 📅 Data (`data`) | Delta enter en **minuts** des de la primera visita del pacient (preserva diferències intra-dia) |
| 🔍 Quasi-identificador | Generalització definida per l'usuari + k-anonimitat |
| ✅ No identificatiu | Sense canvis |

### Fase 3 — Generalitzacions

Per a cada quasi-identificador, l'usuari defineix com agrupar els valors:

- **Variables numèriques** → intervals personalitzats (ex: edat → `0-17`, `18-39`, `40-64`, `65+`)
- **Variables categòriques** → mapeig de valors originals a categories més àmplies

Els valors absents (NaN) s'imputen automàticament:
- Categòrics → `Desconocido`
- Numèrics → mediana del conjunt observat

### Fase 4 — K-anonimitat i resultats

- **Simulació prèvia**: mostra l'impacte de k=2, 3, 4, 5 abans d'executar
- **Paràmetre k**: cada combinació de quasi-identificadors ha de tenir ≥ k pacients
- **Supressió**: els pacients en grups per sota de k s'eliminen del dataset final
- **Mètriques**: flux de pacients, distribució de classes d'equivalència, grups suprimits

---

## Garanties de seguretat

La protecció que ofereix aquest procés es fonamenta en **tres capes independents i complementàries**:

### Capa 1 — Tècnica (transformacions aplicades)

| Transformació | Protecció |
|--------------|-----------|
| Hash SHA-256 de l'identificador | Pseudonimització irreversible |
| Timestamp → delta enter en minuts (per pacient) | Dates absolutes destruïdes; patrons intra-dia preservats |
| Generalització de quasi-IDs | Granularitat de creuament eliminada |
| K-anonimitat | Impossibilitat matemàtica de singularització |

### Capa 2 — Estadística (incertesa de mostreig)

El dataset del datathon és una **mostra aleatòria** d'una població clínica molt més gran. Un potencial atacant no pot saber a priori si una persona concreta és al dataset. Aquesta incertesa — reconeguda per l'ENISA i el Grup de Treball de l'Article 29 com a factor mitigador del risc de reidentificació — fa que qualsevol intent de reidentificació sigui especulatiu i poc fiable, independentment del coneixement previ de l'atacant.

### Capa 3 — Organitzacional (entorn del Datathon)

- **Participants acreditats**: l'accés al dataset és restringit a un grup limitat, prèviament identificat i registrat
- **Acord d'ús de dades (DUA)**: tots els participants signen un compromís formal que prohibeix expressament qualsevol intent d'identificació d'individus, amb sancions en cas d'incompliment
- **Infraestructura segura**: l'esdeveniment té lloc als servidors de l'**Instituto de Salud Carlos III (Madrid)**, gestionats pel seu propi personal qualificat
- **Entorn tancat**: les dades no poden ser exportades fora dels sistemes controlats de l'organització durant el Datathon

> La combinació d'aquestes tres capes proporciona una protecció **substancialment superior** al que exigeixen el RGPD i les guies de l'ENISA per al tractament de dades de salut amb finalitats d'investigació.

---

## Quasi-identificadors recomanats

| Variable | Risc | Recomanació |
|----------|------|-------------|
| `edad` | 🔴 Alt | Sempre QI; generalitzar en rangs de ≥15 anys |
| `sexo_y_o_genero` | 🔴 Alt | Sempre QI |
| `nivel_educativo` | 🟡 Mitjà | QI si el dataset té <500 pacients |
| `situacion_de_convivencia` | 🟡 Mitjà | QI si el dataset té <500 pacients |
| `origen` | 🟡 Mitjà | QI en poblacions locals petites |
| `estado_cognitivo` | 🟢 Baix | Opcional; amb el mostreig ja hi ha protecció suficient |
| Resta de variables | 🟢 Molt baix | No identificatives en context de datathon |

Amb 2.000 pacients d'una comunitat gran, `edad` + `sexo_y_o_genero` amb k=3 ofereix una protecció molt robusta.

---

## Sortides generades

| Fitxer | Format | Per a qui |
|--------|--------|-----------|
| `*_anonymized.csv` | CSV | Participants (un sol fitxer pujat) |
| `datasets_anonymized.zip` | ZIP | Participants (múltiples fitxers — un CSV per fitxer original) |
| `*_report.html` (single) / `anonymization_report.html` (multi) | HTML estilitzat | DPD (imprimible com a PDF des del navegador) |
| `anonymization_report.json` | JSON | Auditoria i traçabilitat |

---

## Estructura del repositori

```
local-anonymizer/
│
├── app/
│   ├── main.py                    # FastAPI: endpoints i gestió de sessions
│   └── modules/
│       ├── anonymizer.py          # Tota la lògica d'anonimització
│       ├── report_md.py           # Generació d'informe Markdown (ca/es/en)
│       └── report_html.py         # Conversió Markdown → HTML estilitzat
│
├── static/
│   ├── index.html                 # Interfície wizard de 4 fases
│   ├── css/styles.css             # Estils (dark mode clínic)
│   └── js/
│       ├── app.js                 # Lògica frontend (vanilla JS)
│       └── i18n.js                # Traduccions: català, castellà, anglès
│
├── docs/
│   ├── README.es.md               # README en castellà
│   └── README.ca.md               # Aquest fitxer
│
├── sample_data/
│   ├── dataset_2000p.csv          # Dataset sintètic — 2.000 pacients (un fitxer)
│   └── 1_… 4_….csv               # Els mateixos 2.000 pacients en 4 fitxers temàtics
│
├── generate_synthetic.py          # Script per regenerar el dataset d'un fitxer
├── generate_multifile_sample.py   # Script per regenerar els 4 fitxers temàtics
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md                      # README principal (anglès)
```

---

## Requisits

- [Docker](https://docs.docker.com/get-docker/) ≥ 24.0
- [Docker Compose](https://docs.docker.com/compose/) ≥ 2.0
- Cap altra dependència al host

---

## Marc legal

Aquest projecte ajuda a complir amb:

- **RGPD (Reglament UE 2016/679)** — Art. 89 i Recital 26 sobre tractament per a recerca
- **LOPDGDD (LO 3/2018)** — Transposició espanyola del RGPD
- **Dictamen 05/2014 del Grup de Treball de l'Art. 29** — k-anonimitat com a tècnica reconeguda
- **Guies ENISA** sobre anonimització de dades sanitàries

> ⚠️ Aquesta eina facilita el procés tècnic, però la responsabilitat de la classificació de les variables i la validació de l'informe recau en el Delegat de Protecció de Dades del centre.

---

## Llicència

MIT — Lliure per a ús, modificació i distribució. Atribució apreciada.

---

*Construït per a centres sanitaris que volen participar en datathons preservant la privacitat dels seus pacients.*
