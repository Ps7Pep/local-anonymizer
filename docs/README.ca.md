# 🔐 Local Anonymizer

> Eina local i portable per anonimitzar datasets clínics abans de compartir-los a la fase post-Datathon InCa i als pilots del projecte TSI.

**[🇬🇧 English](../README.md) · [🇪🇸 Castellano](README.es.md)**

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.156-009688?logo=fastapi)](https://fastapi.tiangolo.com)
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

> **Port i accés per xarxa**: per defecte l'app només escolta a la mateixa màquina (`"127.0.0.1:8092:8000"` al `docker-compose.yml`). Per canviar el port, modifica `8092`. Si l'eina corre en un servidor i s'hi accedeix des d'un altre equip, canvia el mapatge a `"8092:8000"` — deliberadament i només en una xarxa interna de confiança: l'app no té autenticació. Amb `docker run`, fes servir `-p 127.0.0.1:8092:8000`.
>
> **Durada de la sessió**: les dades només viuen en memòria i es descarten després de 120 minuts d'inactivitat (`SESSION_TTL_MINUTES` al `docker-compose.yml`), o a l'instant amb «Nova sessió».

---

## Datasets d'exemple

Si vols provar l'eina abans d'utilitzar les teves pròpies dades, `sample_data/` conté datasets sintètics construïts sobre el **catàleg CCI-SNS** (5 dominis, les 42 variables actives amb les seves categories provisionals; còpia a `catalogo_cci_sns/`). Hi ha **un dataset per línia assistencial** — poblacions independents, així que cadascun és una sessió diferent:

| Línia | Fitxer únic | Pacients | Perfil |
|---|---|---|---|
| AH — atenció hospitalària | [`AH/dataset_AH.csv`](https://raw.githubusercontent.com/Ps7Pep/local-anonymizer/refs/heads/main/sample_data/AH/dataset_AH.csv) | 2.000 | ingrés + revaloració, amb hora; episodis aguts |
| AP — atenció primària | [`AP/dataset_AP.csv`](https://raw.githubusercontent.com/Ps7Pep/local-anonymizer/refs/heads/main/sample_data/AP/dataset_AP.csv) | 2.000 | més joves, majoritàriament autònoms |
| LE — llarga estada | [`LE/dataset_LE.csv`](https://raw.githubusercontent.com/Ps7Pep/local-anonymizer/refs/heads/main/sample_data/LE/dataset_LE.csv) | 2.000 | grans, dependents, deteriorament cognitiu freqüent |

**Mode multi-fitxer:** cada línia també està repartida en 5 fitxers, un per domini CCI-SNS (`<línia>_D1_funcional_motor.csv` … `<línia>_D5_social_contextual.csv`, a la mateixa carpeta). Puja alhora els 5 fitxers d'una línia (arrossega diversos fitxers, o Ctrl+clic al selector): el resultat és idèntic al del fitxer únic d'aquesta línia.

Format: `patient_id, fecha, variable, valor` — `variable` és el nom del catàleg i `valor` és el que hi hauria al registre clínic: la **puntuació crua de l'instrument** quan la categoria defineix un rang (Barthel 0–100, MMSE 0–30, Braden, GAD-7, Zarit, IMC, glucèmia…) i, si no, l'etiqueta de la categoria. Dades completament sintètiques; no inclouen informació real de pacients.

## Format del CSV d'entrada

L'eina accepta **un o més fitxers CSV** en format llarg (una fila per pacient-data-variable).

> **⚠ Una sessió = un dataset.** El mode multi-fitxer és només per a un mateix dataset trossejat en dominis temàtics (mateix univers de pacients, variables clíniques diferents a cada fitxer — p. ex. determinants socials en un, autonomia funcional en un altre). **No** és per a datasets independents com un CSV per línia assistencial (atenció primària, hospitalària, sociosanitària). Els datasets independents s'han d'anonimitzar en **sessions separades**; si no, l'eina barrejarà els seus universos de pacients al aplicar la k-anonimitat. El frontend et demana confirmar-ho abans de processar quan puges més d'un fitxer.

Si les teves dades estan repartides en fitxers temàtics relacionats, pots pujar-los tots alhora. L'eina els combina internament i retorna un CSV anonimitzat per cada fitxer original.

**Requisits quan es pugen múltiples fitxers:**

- Només s'usen les **4 columnes esperades**: `pacient`, `data`, `item`, `valor`. Qualsevol altra columna s'ignora i no arriba a la sortida; els seus noms es mostren després de la càrrega i consten a l'informe
- Indica la **línia assistencial al nom del fitxer** (p. ex. `dataset_AH.csv`; AH, AP o LE): les sortides conserven el nom original i el CSV no porta columna de línia
- Tots els fitxers han de compartir el **mateix identificador de pacient**
- Les variables **no s'han de repetir** entre fitxers
- Tots els fitxers han de descriure la **mateixa població** — si no és així (datasets independents, línies assistencials diferents, cohorts diferents), processa cadascun en una sessió separada

L'aplicació detecta automàticament les variantes del nom de columna i les normalitza internament. El nom de les variables clíniques pot ser qualsevol — l'app s'adapta al contingut de cada fitxer.

**Els noms de columna personalitzats també valen.** Si alguna de les 4 columnes no coincideix amb cap dels àlies anteriors, la pantalla de càrrega fa una **inferència posicional** — assumeix que la 1a columna és `pacient`, la 2a `data`, la 3a `item` i la 4a `valor` — i mostra una previsualització amb quatre desplegables perquè confirmis l'assignació o triïs una altra columna per a cada camp abans de continuar. La càrrega no falla mai silenciosament per noms no reconeguts: o acceptes la proposta amb un clic o la corregeixes explícitament.

### Exemple de files

```csv
patient_id,fecha,variable,valor
AH00042,2024-03-02 09:15,Actividades básicas de la vida diaria (ABVD),75
AH00042,2024-03-02 09:15,Estado cognitivo,22
AH00042,2024-03-02 09:15,Continencia,Incontinencia ocasional urinaria
AH00042,2024-03-02 09:15,Edad,81
AH00042,2024-03-06 11:40,Actividades básicas de la vida diaria (ABVD),85
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
| 🔑 Identificador directe (`pacient`) | HMAC-SHA256 amb clau aleatòria de sessió que mai es desa (prefix `H-`) |
| 📅 Data (`data`) | Delta enter en **minuts** des de la primera visita del pacient (preserva diferències intra-dia) |
| 🔍 Quasi-identificador | Generalització definida per l'usuari + k-anonimitat |
| ✅ No identificatiu | Sense canvis |

### Fase 3 — Generalitzacions

Per a cada quasi-identificador, l'usuari defineix com agrupar els valors:

- **Variables numèriques** → intervals personalitzats (ex: edat → `0-17`, `18-39`, `40-64`, `65+`)
- **Variables categòriques** → mapeig de valors originals a categories més àmplies

Els valors absents (NaN) s'imputen automàticament sobre els valors originals, abans de generalitzar:
- Categòrics → `Desconocido`
- Numèrics → mediana del conjunt observat

Res no queda fora d'una generalització en silenci: els valors numèrics fora dels punts de tall passen a `Fuera de rango`, els no numèrics en un ítem amb intervals a `Desconocido`, i els recomptes (i els valors sense categoria assignada) es mostren als resultats i a l'informe.

### Fase 4 — K-anonimitat i resultats

- **Simulació prèvia**: mostra l'impacte de k=2, 3, 4, 5 abans d'executar
- **Paràmetre k**: cada combinació de quasi-identificadors ha de tenir ≥ k pacients
- **Signatura longitudinal**: la combinació d'un pacient és el conjunt de tots els valors que pren cada quasi-identificador al llarg de les seves visites (p. ex. franja d'edat `60-64 | 65+`), de manera que k es compleix també quan un quasi-identificador canvia entre visites
- **Supressió**: els pacients en grups per sota de k s'eliminen del dataset final
- **Mètriques**: flux de pacients, distribució de classes d'equivalència, grups suprimits

---

## Garanties de seguretat

La protecció que ofereix aquest procés es fonamenta en **tres capes independents i complementàries**:

### Capa 1 — Tècnica (transformacions aplicades)

| Transformació | Protecció |
|--------------|-----------|
| HMAC-SHA256 de l'identificador (clau secreta de sessió, descartada) | Pseudonimització no reversible per atac de diccionari |
| Timestamp → delta enter en minuts (per pacient) | Dates absolutes destruïdes; patrons intra-dia preservats |
| Generalització de quasi-IDs | Granularitat de creuament eliminada |
| K-anonimitat | Cap perfil de quasi-identificadors compartit per menys de k pacients |

### Capa 2 — Estadística (incertesa de presència)

Cada dataset correspon a una extracció acotada: una línia assistencial i, a les noves extraccions, l'any 2024. Quan l'extracció és una **mostra** de la població de referència, un potencial atacant no pot saber a priori si una persona concreta és al dataset, un factor mitigador del risc de reidentificació reconegut per l'ENISA i el Grup de Treball de l'Article 29. Si l'extracció inclou tota la població de la línia i del període, aquesta incertesa no s'aplica i la protecció descansa en les capes 1 i 3.

### Capa 3 — Organitzacional (entorn del projecte)

- **Participants acreditats**: accés només després de signar l'Acord d'ús de dades i confidencialitat de la fase post-Datathon InCa i dels pilots TSI, com a màxim fins al 31 de maig de 2027
- **Finalitat limitada**: revisió i harmonització de variables, ponderació i desenvolupament, avaluació i validació de models sobre complexitat i necessitats de cures
- **Prohibició de reidentificació i de creuaments**: es prohibeix qualsevol intent de reidentificació i la combinació amb fonts externes
- **Entorn segur**: es treballa al SharePoint del projecte i en aplicacions publicades a Red SARA (ISCIII); descàrregues només quan sigui imprescindible, en equips corporatius, mai en dispositius personals, serveis al núvol o eines externes, inclosa la IA generativa

> La valoració final del risc residual correspon al Delegat/ada de Protecció de Dades de cada centre.

---

## Quasi-identificadors recomanats

| Variable | Risc | Recomanació |
|----------|------|-------------|
| `edad` | 🔴 Alt | Sempre QI; generalitzar en rangs de ≥15 anys |
| `sexo_y_o_genero` | 🔴 Alt | Sempre QI |
| `nivel_educativo` | 🟡 Mitjà | QI si el dataset té <500 pacients |
| `situacion_de_convivencia` | 🟡 Mitjà | QI si el dataset té <500 pacients |
| `origen` | 🟡 Mitjà | QI en poblacions locals petites |
| `estado_cognitivo` | 🟢 Baix | Opcional |
| Resta de variables | 🟢 Molt baix | No identificatives, excepte text lliure, que mai s'ha d'incloure |

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
│   └── AH/ AP/ LE/                # Un dataset sintètic per línia assistencial (2.000 pacients)
│                                  #   dataset_<línia>.csv + 5 fitxers, un per domini CCI-SNS
├── catalogo_cci_sns/              # Variables i categories provisionals CCI-SNS (còpia; les fa servir el generador)
│
├── generate_synthetic.py          # Genera el dataset sintètic (perfil fix per pacient)
├── generate_multifile_sample.py   # El reparteix en els 4 fitxers temàtics (partició exacta)
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

*Construït per a centres sanitaris que comparteixen dades clíniques per a recerca preservant la privacitat dels seus pacients.*
