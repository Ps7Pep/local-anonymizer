"""
generate_synthetic.py
---------------------
Genera els datasets sintètics de demostració a partir del catàleg CCI-SNS
(`catalogo_cci_sns/`: 5 dominis, 42 variables actives amb les seves categories
provisionals). Un dataset per línia assistencial — són poblacions independents,
i a l'eina cada una és una sessió:

    sample_data/AH/dataset_AH.csv   atenció hospitalària
    sample_data/AP/dataset_AP.csv   atenció primària
    sample_data/LE/dataset_LE.csv   llarga estada / sociosanitari

Format llarg, com una extracció d'una CCAA: patient_id, fecha, variable, valor.
`variable` és el nom de la variable al catàleg i `valor` és el que hi hauria al
registre clínic:
  - la PUNTUACIÓ CRUA de l'instrument quan la categoria en defineix el rang
    (Barthel 0–100, MMSE 0–30, Braden, GAD-7, Zarit, IMC, glucèmia…);
  - l'ETIQUETA de la categoria per a la resta (codis tancats, «No evaluable»…).
Aplicant els trams del catàleg a la puntuació s'obté exactament la categoria.

Segueix la lògica d'un extracte real:
  - Perfil fix per pacient (sexe, migració, TSI, alfabetització, cuidador, GMA);
    l'edat es calcula a cada valoració a partir de la data de naixement.
  - Un nivell latent de complexitat per pacient, diferent per línia (LE > AH > AP),
    condiciona les variables clíniques; entre valoracions evoluciona poc.
  - Una valoració no feta no té fila; «No evaluable» només on el catàleg ho preveu
    (més freqüent si hi ha deteriorament cognitiu); els instruments d'adults
    (Barthel, MMSE, GAD-7…) no es registren en menors.

`generate_multifile_sample.py` reparteix cada dataset en 5 fitxers, un per domini.

Ús (dins del contenidor; només llibreria estàndard):
    python generate_synthetic.py
"""

import csv
import os
import random
import re
import unicodedata
from datetime import date, datetime, timedelta

SEED        = 20261021
N_PATIENTS  = 2000                    # per línia
CATALOG_DIR = "catalogo_cci_sns"
OUTPUT_DIR  = "sample_data"
FIELDS      = ["patient_id", "fecha", "variable", "valor"]

LINES = {
    "AH": {
        # (edat mínima, màxima, pes) a la primera valoració
        "ages":   [(0, 1, 2), (2, 17, 6), (18, 64, 37), (65, 74, 19), (75, 89, 29), (90, 100, 7)],
        "latent": [(0.30, 2, 7), (0.35, 4, 5), (0.25, 6, 3), (0.10, 10, 2)],   # mescla de betes
        "gamma":  (1.2, 2.0),           # asimetria: com més alta, més població a les categories lleus
        "acute":  1.0,                  # pes de la complexitat en les variables agudes (ACUTE)
        "drift":  (-0.03, 0.08),        # a l'alta, de mitjana una mica millor
        "female": 0.50,
        "with_time": True,              # ingrés + revaloració, amb hora
        "gap_days": (1, 10),
    },
    "AP": {
        "ages":   [(0, 1, 3), (2, 17, 12), (18, 64, 50), (65, 74, 15), (75, 89, 17), (90, 100, 3)],
        "latent": [(0.50, 2, 8), (0.30, 4, 5), (0.15, 6, 3), (0.05, 10, 2)],
        "gamma":  (1.5, 2.5),
        "acute":  0.45,
        "drift":  (0.01, 0.05),
        "female": 0.53,
        "with_time": False,
        "gap_days": (30, 180),
    },
    "LE": {
        "ages":   [(50, 64, 8), (65, 74, 17), (75, 89, 50), (90, 102, 25)],
        "latent": [(0.10, 2, 7), (0.25, 4, 5), (0.35, 6, 3), (0.30, 10, 2)],
        "gamma":  (1.0, 1.6),
        "acute":  0.55,
        "drift":  (0.03, 0.06),
        "female": 0.66,
        "with_time": False,
        "gap_days": (30, 120),
    },
}

# ── Escales: valors crus possibles per a cada categoria AVALUABLE, en l'ordre
# del catàleg. None = la categoria no té rang i es registra amb l'etiqueta.
def _r(lo, hi, step=1):
    n = int(round((hi - lo) / step))
    return [round(lo + i * step, 2) for i in range(n + 1)]

_HLS = [round(k * 100 / 12, 2) for k in range(13)]          # HLS19-Q12: 12 ítems → 0, 8.33 … 100

SCALES = {
    "D1V01": [[100], [95], _r(65, 90, 5), _r(25, 60, 5), _r(0, 20, 5)],      # Barthel (de 5 en 5)
    "D1V02": [[8], [6, 7], [4, 5], [2, 3], [0, 1]],                          # Lawton
    "D1V03": [[0], [1], [2], [3], [4]],                                      # AM-PAC (codi 0–4)
    "D1V04": [_r(0, 2), _r(3, 11)],                                          # Downton
    "D1V05": [_r(19, 23), _r(15, 18), [13, 14], _r(10, 12), _r(6, 9)],       # Braden
    "D1V11": [_r(12, 14), _r(8, 11), _r(0, 7)],                              # MNA-SF
    "D1V13": [_r(0, 2), _r(3, 40)],                                          # EAT-10
    "D2V01": [_r(25, 30), _r(20, 24), _r(14, 19), _r(0, 13)],                # MMSE
    "D2V06": [[0], _r(5, 44), _r(45, 74), _r(75, 100)],                      # EVA 0–100
    "D2V08": [_r(0, 4), _r(5, 9), _r(10, 14), _r(15, 21)],                   # GAD-7
    "D2V09": [_r(0, 4), _r(5, 9), _r(10, 14), _r(15, 19), _r(20, 27)],       # PHQ-9
    "D2V12": [[0], [1, 2], _r(3, 5), _r(6, 10)],                             # DAST-10
    "D3V06": [_r(0, 3), _r(4, 20)],                                          # Padua
    "D3V07": [_r(70, 179), _r(180, 400), _r(54, 69), _r(35, 53), None, None],# glucèmia mg/dL; nivell 3 i crisi: esdeveniments
    "D4V02": [[0], [1, 2], _r(3, 5)],                                        # Fried
    "D4V07": [_r(0, 4), _r(5, 9), _r(10, 20)],                               # nre. de fàrmacs
    "D4V08": [_r(18.5, 29.9, 0.1), _r(14.5, 18.4, 0.1) + _r(30.0, 42.0, 0.1)],  # IMC
    "D5V01": [_r(57, 95), _r(19, 56)],                                       # MOS
    "D5V02": [_r(0, 2), _r(3, 8), [9, 10], [11]],                            # De Jong Gierveld
    "D5V05": [_r(22, 46), _r(47, 55), _r(56, 110)],                          # Zarit
    "D5V09": [[h for h in _HLS if h > 83.33], [h for h in _HLS if 66.67 < h <= 83.33],
              [h for h in _HLS if 50 < h <= 66.67], [h for h in _HLS if h <= 50]],  # HLS19-Q12
}

# Instruments d'adults: no es registren en menors de 18 anys
ADULT_ONLY = {"D1V01", "D1V02", "D1V11", "D1V13", "D2V01", "D2V07", "D2V08", "D2V09",
              "D2V12", "D3V06", "D4V02", "D5V01", "D5V02", "D5V09"}
# Valoracions que no es poden fer bé si el pacient no es comunica (més «No evaluable»)
COMMUNICATION_DEPENDENT = {"D1V14", "D2V02", "D2V06", "D2V07", "D2V12"}
# Situacions agudes: depenen sobretot de la línia (hospital), no de la complexitat
# crònica; a AP i LE són poc freqüents encara que el pacient sigui complex
ACUTE = {"D1V07", "D1V12", "D2V02", "D2V03", "D2V06", "D3V01", "D3V07"}
# Perfil fix del pacient: mateix valor a totes les valoracions
STABLE = {"D5V15", "D5V13", "D5V10", "D5V08", "D5V09", "D5V03", "D4V01"}
# Sempre registrades (dades administratives)
ALWAYS = {"D5V14", "D5V15"}
# Registres amb el camp de valor buit (per demostrar la imputació als quasi-identificadors)
EMPTY_VALUE_PROB = {"D5V08": 0.015, "D5V13": 0.015}


# ── Catàleg ───────────────────────────────────────────────────────────────────

def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    words = [w for w in re.split(r"[^a-z0-9]+", text) if w and w != "y"]
    return "_".join(words)


def load_catalog(catalog_dir: str = CATALOG_DIR) -> list[dict]:
    """Variables actives amb les seves categories, en l'ordre del catàleg."""
    with open(os.path.join(catalog_dir, "variables_cci_sns.csv"), newline="", encoding="utf-8") as f:
        variables = [r for r in csv.DictReader(f) if r["activa"] == "1"]
    cats: dict[str, list[dict]] = {}
    with open(os.path.join(catalog_dir, "categorias_cci_sns_provisional.csv"), newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            cats.setdefault(r["var_id"], []).append(r)

    out = []
    for v in variables:
        vc = sorted(cats.get(v["var_id"], []), key=lambda c: int(c["orden"]))
        if not vc:
            raise ValueError(f"{v['var_id']} és activa però no té categories al catàleg")
        evaluable = [c["categoria"] for c in vc if c["no_evaluable"] != "1"]
        scale = SCALES.get(v["var_id"])
        if scale is not None and len(scale) != len(evaluable):
            raise ValueError(f"{v['var_id']}: l'escala té {len(scale)} trams però el catàleg "
                             f"{len(evaluable)} categories avaluables — revisa SCALES")
        out.append({
            "id":         v["var_id"],
            "domain_id":  v["dominio_id"],
            "domain":     v["dominio"],
            "name":       v["variable"],
            "evaluable":  evaluable,
            "no_eval":    next((c["categoria"] for c in vc if c["no_evaluable"] == "1"), None),
            "has_ref":    any(c["es_referencia"] == "1" for c in vc),
            "scale":      scale,
        })
    return out


def domain_files(catalog: list[dict]) -> dict[str, str]:
    """{domain_id: sufix de fitxer}, p. ex. D1 → 'D1_funcional_motor'."""
    return {v["domain_id"]: f"{v['domain_id']}_{slug(v['domain'])}" for v in catalog}


# ── Generació ─────────────────────────────────────────────────────────────────

def _clip(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def _weighted(rng, options):
    values, weights = zip(*options)
    return rng.choices(values, weights=weights)[0]


def age_at(birth: date, when: date) -> int:
    return when.year - birth.year - ((when.month, when.day) < (birth.month, birth.day))


def _fmt(x) -> str:
    return str(int(x)) if float(x).is_integer() else f"{x:.2f}".rstrip("0").rstrip(".")


def _ordinal(rng, z, n, a, gamma):
    """Índex de categoria (0 = referència) segons la complexitat z. gamma > 1
    concentra la població a les categories lleus, com en una població real."""
    s = _clip(0.5 + a * (z - 0.5) + rng.gauss(0, 0.15), 0.0, 0.999) ** gamma
    return min(int(s * n), n - 1)


def _value(rng, var, idx):
    """Valor cru de la categoria idx: puntuació dins del seu tram, o l'etiqueta."""
    if var["scale"] is not None and var["scale"][idx] is not None:
        return _fmt(rng.choice(var["scale"][idx]))
    return var["evaluable"][idx]


def make_profile(rng, line_cfg, catalog_by_id, first_visit: date) -> dict:
    lo, hi, _ = _weighted(rng, [((a, b, w), w) for a, b, w in line_cfg["ages"]])
    age0  = rng.randint(lo, hi)
    birth = first_visit - timedelta(days=int(age0 * 365.25) + rng.randint(0, 364))
    w, a, b = _weighted(rng, [(m, m[0]) for m in line_cfg["latent"]])
    age_f = _clip((age0 - 40) / 55)
    z = _clip(0.75 * rng.betavariate(a, b) + 0.25 * age_f)

    female  = rng.random() < line_cfg["female"]
    migrant = rng.random() < (0.05 if line_cfg is LINES["LE"] else 0.11)
    p = {"birth": birth, "z": z, "age0": age0, "female": female}

    p["D5V15"] = "Femenino" if female else "Masculino"
    p["D5V13"] = "No evaluable" if rng.random() < 0.02 else ("Sí" if migrant else "No")
    p["D5V10"] = ("No evaluable" if rng.random() < 0.02 else
                  "Sí" if rng.random() < (0.35 if migrant else 0.01) else "No")
    p["D5V08"] = ("No disponible / no evaluable" if rng.random() < 0.02 else _weighted(rng,
                  [("TSI 002-01", 68), ("TSI 002-02", 24), ("TSI 005-03", 1), ("TSI 001", 3), ("TSI 006", 4)]
                  if age0 >= 65 else
                  [("TSI 003", 30), ("TSI 004", 48), ("TSI 005-00", 3), ("TSI 001", 12), ("TSI 006", 7)]))
    p["D5V03"] = "No dispone de cuidador" if rng.random() < 0.2 else "Dispone de cuidador"
    hls = catalog_by_id["D5V09"]
    p["D5V09"] = _value(rng, hls, _ordinal(rng, 0.35 + 0.3 * age_f, len(hls["evaluable"]), 0.8, 1.2))

    # GMA (morbiditat): estable en el període; embaràs només en dones de 15 a 49
    if age0 < 18:
        gma = [(0, 50), (1, 30), (3, 15), (4, 5)]
    else:
        gma = [(0, max(2, 25 - 30 * z)), (1, 10), (3, 25), (4, 15 + 25 * z),
               (5, 5 + 35 * z), (6, 3 + 8 * z)]
        if female and 15 <= age0 <= 49:
            gma.append((2, 8))
    p["D4V01"] = catalog_by_id["D4V01"]["evaluable"][_weighted(rng, gma)]
    return p


def visit_value(rng, var, params, z, age):
    """Valor d'una variable que pot canviar entre valoracions."""
    vid, n = var["id"], len(var["evaluable"])
    if var["no_eval"]:
        p_ne = 0.02 + (0.10 if vid in COMMUNICATION_DEPENDENT and z > 0.75 else 0)
        if rng.random() < p_ne:
            return var["no_eval"]
    z = z * params["acute"]
    if vid == "D5V14":
        return str(age)
    if vid == "D1V08":   # tipus × gravetat (no ordinal): gravetat segons z, tipus a l'atzar
        sev = _ordinal(rng, z, 4, params["a"], params["gamma"])
        if sev == 0:
            return var["evaluable"][0]
        kind = _weighted(rng, [(0, 50), (1, 30), (2, 20)])          # física, sensorial, mixta
        return var["evaluable"][1 + (sev - 1) * 3 + kind]
    if vid == "D3V07":   # glucèmia: majoritàriament normal, alteracions segons z
        idx = _weighted(rng, [(0, 1.0), (1, 0.04 + 0.12 * z), (2, 0.02), (3, 0.008), (4, 0.003), (5, 0.003)])
        return _value(rng, var, idx)
    if vid == "D4V08":   # IMC: 60 % de les alteracions són obesitat, 40 % baix pes
        if _ordinal(rng, z, 2, params["a"], params["gamma"]) == 0:
            return _value(rng, var, 0)
        return _fmt(rng.choice(_r(30.0, 42.0, 0.1) if rng.random() < 0.6 else _r(14.5, 18.4, 0.1)))
    return _value(rng, var, _ordinal(rng, z, n, params["a"], params["gamma"]))


def generate_rows(line: str, catalog: list[dict], n_patients: int = N_PATIENTS, seed: int = SEED) -> list[dict]:
    cfg  = LINES[line]
    rng  = random.Random(f"{seed}-{line}")
    by_id = {v["id"]: v for v in catalog}
    # paràmetres per variable i línia: pendent, asimetria i completesa del registre
    params = {v["id"]: {"a": rng.uniform(0.7, 1.3),
                        "gamma": rng.uniform(*cfg["gamma"]) + (0.6 if v["id"] in ACUTE else 0),
                        "acute": cfg["acute"] if v["id"] in ACUTE else 1.0,
                        "recorded": 1.0 if v["id"] in ALWAYS else rng.uniform(0.75, 0.97)}
              for v in catalog}

    rows = []
    for i in range(1, n_patients + 1):
        pid = f"{line}{i:05d}"
        day = date(2024, 1, 1) + timedelta(days=rng.randint(0, 365))
        if cfg["with_time"]:
            first = datetime(day.year, day.month, day.day, rng.randint(0, 23), rng.randint(0, 59))
            second = (first + timedelta(days=rng.randint(*cfg["gap_days"]))).replace(
                hour=rng.randint(8, 21), minute=rng.randint(0, 59))
            visits = [first, second]
        else:
            visits = [day, day + timedelta(days=rng.randint(*cfg["gap_days"]))]
        profile = make_profile(rng, cfg, by_id, day)

        z = profile["z"]
        for when in visits:
            when_date = when.date() if isinstance(when, datetime) else when
            age   = age_at(profile["birth"], when_date)
            stamp = when.strftime("%Y-%m-%d %H:%M") if cfg["with_time"] else when.isoformat()
            for var in catalog:
                vid = var["id"]
                if age < 18 and vid in ADULT_ONLY:
                    continue
                if rng.random() >= params[vid]["recorded"]:
                    continue                                   # valoració no feta: sense fila
                if rng.random() < EMPTY_VALUE_PROB.get(vid, 0):
                    val = ""
                elif vid in STABLE:
                    val = profile[vid]
                else:
                    val = visit_value(rng, var, params[vid], z, age)
                rows.append({"patient_id": pid, "fecha": stamp, "variable": var["name"], "valor": val})
            z = _clip(z + rng.gauss(*cfg["drift"]))
    rng.shuffle(rows)
    return rows


def write_csv(rows: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def dataset_path(line: str) -> str:
    return os.path.join(OUTPUT_DIR, line, f"dataset_{line}.csv")


if __name__ == "__main__":
    catalog = load_catalog()
    for line in LINES:
        rows = generate_rows(line, catalog)
        write_csv(rows, dataset_path(line))
        print(f"{dataset_path(line)}: {len(rows):,} registres · {N_PATIENTS} pacients · "
              f"{len(catalog)} variables")
