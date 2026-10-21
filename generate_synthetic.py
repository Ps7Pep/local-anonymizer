"""
generate_synthetic.py
---------------------
Genera el dataset sintètic de referència: 2.000 pacients × 2 visites × 65 variables
clíniques, en format llarg (patient_id, data, variable, valor):

    sample_data/dataset_2000p.csv

Segueix la lògica d'un extracte clínic real perquè la demo es comporti com ho
farien les dades d'una CCAA:
  - Cada pacient té un perfil fix (data de naixement, sexe, origen, nivell
    educatiu…): les variables demogràfiques NO canvien d'una visita a l'altra.
  - L'edat es calcula a cada visita a partir de la data de naixement, de manera
    que pot pujar un any entre visites, com passa a les dades reals.
  - Les variables clíniques sí que poden canviar entre visites.
  - Les absències de dades demogràfiques són per pacient (falta a totes les
    visites); les clíniques, per visita.
  - Les distribucions s'acosten a una població real (p. ex. «no_binario» és
    minoritari), així la k-anonimitat suprimeix els perfils realment rars.

`generate_multifile_sample.py` reparteix AQUEST mateix fitxer en 4 fitxers
temàtics: la unió dels 4 és exactament dataset_2000p.csv.

Ús (dins del contenidor; només llibreria estàndard):
    python generate_synthetic.py
"""

import csv
import random
from datetime import date, timedelta

SEED       = 42
N_PATIENTS = 2000
VISITS     = 2
OUTPUT     = "sample_data/dataset_2000p.csv"

# ── Variables, agrupades pels 4 blocs temàtics del mode multi-fitxer ──────────
# Font única: generate_multifile_sample.py reparteix el dataset amb aquests blocs.
BLOCKS = {
    "1_determinantes_sociales": [
        "sexo_y_o_genero", "edad", "situacion_de_convivencia", "migracion",
        "origen", "nivel_de_socioeconomico", "nivel_educativo",
        "cribado_de_pobreza", "alfabetizacion_en_salud", "barrera_idiomatica",
        "comunicacion_verbal", "cuidadora_informal_no_asalariada_disponible",
        "cuidadora_informal_asalariada_disponible",
        "red_de_apoyo_aislamiento_social", "soledad_no_deseada",
    ],
    "2_salud_mental_conductual": [
        "adherencia_terapeutica", "ansiedad", "depresion",
        "consumo_de_alcohol", "tabaquismo",
        "consumo_de_otras_sustancias_adictivas",
        "percepcion_sobre_la_salud_o_la_enfermedad",
        "estado_cognitivo", "riesgo_de_delirium",
        "agitacion", "agresividad", "conducta_erratica",
        "etapa_vital",
    ],
    "3_funcionalidad_autonomia": [
        "actividades_basicas_de_la_vida_diaria",
        "actividades_instrumentales_de_la_vida_diaria",
        "diversidad_funcional", "movilidad_deambulacion_transferencia",
        "continencia", "alteracion_del_patron_respiratorio",
        "riesgo_de_lesiones_por_presion_lesiones_relacionadas_con_la_dependencia",
        "riesgo_de_caidas", "deficit_de_vision", "deficit_de_audicion",
        "nivel_de_autocuidado", "sobrecarga_del_cuidador",
        "valoracion_de_riesgos_en_el_domicilio", "deterioro_global",
    ],
    "4_complejidad_clinica": [
        "dolor_cronico", "dolor_agudo", "indice_de_comorbilidad",
        "fragilidad", "insuficiencia_cronica_de_organo",
        "insuficiencia_cronica_de_aparato", "insuficiencia_cronica_de_sistema",
        "enfermedad_neoplasica", "polifarmacia", "medicacion_de_alto_riesgo",
        "cribado_nutricional", "disfagia", "deshidratacion",
        "valoracion_antropometrica", "riesgo_hemorragico_relevante",
        "riesgo_tromboembolico_relevante",
        "desbalance_hipoglucemico_significativo", "anticoagulacion",
        "infeccion_activa_en_curso", "inmunodepresion",
        "inestabilidad_hemodinamica", "cuidados_paliativos",
        "presencia_e_intesidad_de_sintomas",
    ],
}
VARIABLES = [v for block in BLOCKS.values() for v in block]

# ── Perfil fix per pacient (mateix valor a totes les visites) ─────────────────
# (valor, pes relatiu)
STABLE = {
    "sexo_y_o_genero":         [("mujer", 52), ("hombre", 47.5), ("no_binario", 0.5)],
    "origen":                  [("espanya", 85), ("america_latina", 6), ("ue", 4),
                                ("africa", 3), ("asia", 1.5), ("altres", 0.5)],
    "nivel_de_socioeconomico": [("alto", 20), ("medio", 55), ("bajo", 25)],
    "situacion_de_convivencia":[("familia", 40), ("pareja", 30), ("solo", 20),
                                ("residencia", 7), ("otros", 3)],
    "alfabetizacion_en_salud": [("alta", 30), ("media", 50), ("baja", 20)],
}
# migracion, barrera_idiomatica i nivel_educativo també són fixos, però depenen
# d'altres atributs del perfil (origen, edat): es calculen a `make_profile`.
DERIVED_STABLE = {"migracion", "barrera_idiomatica", "nivel_educativo"}

# ── Variables que canvien per visita ──────────────────────────────────────────
NUMERIC = {
    "dolor_agudo":                       (0, 10),
    "dolor_cronico":                     (0, 10),
    "indice_de_comorbilidad":            (0, 8),
    "presencia_e_intesidad_de_sintomas": (0, 10),
    "valoracion_antropometrica":         (40, 120),
}
CATEGORICAL = {
    "actividades_basicas_de_la_vida_diaria":
        ["independiente", "dependencia_leve", "dependencia_moderada",
         "dependencia_severa", "dependencia_total"],
    "actividades_instrumentales_de_la_vida_diaria":
        ["independiente", "dependencia_leve", "dependencia_moderada", "dependencia_severa"],
    "adherencia_terapeutica":   ["alta", "media", "baja"],
    "alteracion_del_patron_respiratorio": ["no", "leve", "moderada", "grave"],
    "comunicacion_verbal":      ["normal", "moderada", "limitada", "nula"],
    "consumo_de_alcohol":       ["no", "moderado", "riesgo", "perjudicial"],
    "continencia":              ["continente", "parcial", "incontinencia"],
    "cribado_de_pobreza":       ["negativo", "positivo"],
    "cribado_nutricional":      ["sin_riesgo", "riesgo_leve", "riesgo_moderado", "riesgo_alto"],
    "deficit_de_audicion":      ["no", "leve", "moderada", "grave"],
    "deficit_de_vision":        ["no", "leve", "moderada", "grave"],
    "deterioro_global":         ["no", "leve", "moderado", "grave"],
    "diversidad_funcional":     ["no", "fisica", "sensorial", "cognitiva", "multiple"],
    "estado_cognitivo":         ["sin_deterioro", "deterioro_leve", "deterioro_moderado", "deterioro_severo"],
    "fragilidad":               ["robusta", "prefragil", "fragil"],
    "movilidad_deambulacion_transferencia":
        ["independiente", "ayuda_tecnica", "supervision", "dependiente"],
    "nivel_de_autocuidado":     ["alto", "medio", "bajo"],
    "percepcion_sobre_la_salud_o_la_enfermedad": ["positiva", "neutra", "negativa"],
    "red_de_apoyo_aislamiento_social": ["buena", "moderada", "escasa", "aislamiento"],
    "riesgo_de_caidas":         ["bajo", "medio", "alto"],
    "riesgo_de_lesiones_por_presion_lesiones_relacionadas_con_la_dependencia":
        ["bajo", "medio", "alto"],
    "sobrecarga_del_cuidador":  ["no", "leve", "moderada", "severa"],
    "valoracion_de_riesgos_en_el_domicilio": ["bajo", "medio", "alto"],
}
# La resta són binàries si/no; prevalença de «si» per defecte, amb excepcions
BINARY_DEFAULT_PREV = 0.25
BINARY_PREV = {
    "cuidados_paliativos": 0.05, "enfermedad_neoplasica": 0.15,
    "infeccion_activa_en_curso": 0.10, "inestabilidad_hemodinamica": 0.05,
    "polifarmacia": 0.45, "anticoagulacion": 0.20, "tabaquismo": 0.18,
}

# Probabilitat de valor absent. Variables del perfil fix: per pacient;
# la resta: per visita.
NAN_PROBS = {
    "alfabetizacion_en_salud":               0.20,
    "barrera_idiomatica":                    0.10,
    "valoracion_de_riesgos_en_el_domicilio": 0.25,
    "sobrecarga_del_cuidador":               0.30,
    "etapa_vital":                           0.15,
    "cribado_de_pobreza":                    0.20,
    "valoracion_antropometrica":             0.15,
    "dolor_cronico":                         0.12,
    "red_de_apoyo_aislamiento_social":       0.10,
}


def _weighted(rng: random.Random, options):
    values, weights = zip(*options)
    return rng.choices(values, weights=weights)[0]


def age_at(birth: date, when: date) -> int:
    return when.year - birth.year - ((when.month, when.day) < (birth.month, birth.day))


def make_profile(rng: random.Random, first_visit: date) -> dict:
    """Atributs del pacient que no canvien entre visites."""
    age0  = rng.randint(18, 92)
    birth = first_visit - timedelta(days=int(age0 * 365.25) + rng.randint(0, 364))
    p = {"birth": birth}
    for var, options in STABLE.items():
        p[var] = _weighted(rng, options)

    foreign = p["origen"] != "espanya"
    p["migracion"] = "si" if foreign and rng.random() < 0.9 else "no"
    if p["origen"] in ("africa", "asia", "altres"):
        p["barrera_idiomatica"] = "si" if rng.random() < 0.6 else "no"
    else:
        p["barrera_idiomatica"] = "si" if foreign and rng.random() < 0.1 else "no"
    # Cohorts més grans: menys estudis superiors
    age = age_at(birth, first_visit)
    p["nivel_educativo"] = _weighted(rng,
        [("sin_estudios", 15), ("primaria", 45), ("secundaria", 30), ("universitaria", 10)] if age >= 70 else
        [("sin_estudios", 3), ("primaria", 22), ("secundaria", 45), ("universitaria", 30)])

    for var in list(STABLE) + sorted(DERIVED_STABLE):
        if rng.random() < NAN_PROBS.get(var, 0):
            p[var] = None          # absent a totes les visites
    return p


def visit_value(rng: random.Random, var: str, age: int):
    """Valor d'una variable que pot canviar entre visites."""
    if rng.random() < NAN_PROBS.get(var, 0):
        return None
    if var in NUMERIC:
        lo, hi = NUMERIC[var]
        return str(max(lo, min(hi, round(rng.gauss((lo + hi) / 2, (hi - lo) / 5)))))
    if var == "fragilidad":
        w = [0.70, 0.25, 0.05] if age < 40 else [0.40, 0.40, 0.20] if age < 65 else [0.15, 0.35, 0.50]
        return rng.choices(CATEGORICAL[var], weights=w)[0]
    if var == "estado_cognitivo":
        w = [0.75, 0.15, 0.07, 0.03] if age < 60 else [0.45, 0.30, 0.17, 0.08] if age < 75 else [0.20, 0.30, 0.30, 0.20]
        return rng.choices(CATEGORICAL[var], weights=w)[0]
    if var in CATEGORICAL:
        return rng.choice(CATEGORICAL[var])
    return "si" if rng.random() < BINARY_PREV.get(var, BINARY_DEFAULT_PREV) else "no"


def generate_rows(n_patients: int = N_PATIENTS, visits: int = VISITS, seed: int = SEED) -> list[dict]:
    rng  = random.Random(seed)
    base = date(2023, 1, 1)
    rows = []
    for i in range(1, n_patients + 1):
        pid   = f"P{i:04d}"
        dates = [base + timedelta(days=rng.randint(0, 365))]
        for _ in range(visits - 1):
            dates.append(dates[-1] + timedelta(days=rng.randint(20, 180)))
        profile = make_profile(rng, dates[0])

        for visit_date in dates:
            age = age_at(profile["birth"], visit_date)
            for var in VARIABLES:
                if var == "edad":
                    val = str(age)
                elif var in profile:
                    val = profile[var]
                else:
                    val = visit_value(rng, var, age)
                rows.append({
                    "patient_id": pid,
                    "data":       visit_date.isoformat(),
                    "variable":   var,
                    "valor":      "" if val is None else val,
                })
    rng.shuffle(rows)
    return rows


def write_csv(rows: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["patient_id", "data", "variable", "valor"])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    rows = generate_rows()
    write_csv(rows, OUTPUT)
    print(f"Dataset generat: {len(rows):,} registres")
    print(f"  {N_PATIENTS} pacients × {VISITS} visites × {len(VARIABLES)} variables → {OUTPUT}")
