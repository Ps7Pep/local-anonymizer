"""
generate_synthetic.py
---------------------
Genera un dataset sintètic de 2.000 pacients × 2 visites × 65 variables clíniques.
Els noms de variable s'extreuen directament de l'Excel de referència
(sample_data/Cataluña_Unificado.xlsx) i es netegen:
  - S'elimina el contingut entre parèntesis  →  "Etapa vital (desc...)" → "etapa_vital"
  - Es normalitzen accents i caràcters especials
  - Es minusculitza i s'estandarditza com a slug

Resultat: sample_data/dataset_2000p.csv
Format:   patient_id | data | variable | valor
"""

import re
import csv
import random
import unicodedata
from datetime import date, timedelta

try:
    from openpyxl import load_workbook
    OPENPYXL_OK = True
except ImportError:
    OPENPYXL_OK = False

random.seed(42)

# ── Neteja de noms de variable ────────────────────────────────────────────────

def clean_var_name(raw: str) -> str:
    """Converteix un nom de variable en slug net sense parèntesis ni accents."""
    # 1. Eliminar contingut entre parèntesis (incloent-los)
    name = re.sub(r'\s*\(.*?\)', '', str(raw))
    # 2. Eliminar punts i espais finals
    name = name.strip().rstrip('.')
    # 3. Normalitzar accents (NFD + eliminar diacrítics)
    name = unicodedata.normalize('NFKD', name)
    name = ''.join(c for c in name if not unicodedata.combining(c))
    # 4. Minúscules i substituir no-alfanumèrics per _
    name = name.lower()
    name = re.sub(r'[^a-z0-9]+', '_', name)
    name = re.sub(r'_+', '_', name).strip('_')
    return name


# ── Lectura de variables des de l'Excel ───────────────────────────────────────

def load_variables_from_excel(path: str) -> list[str]:
    """Extreu i neteja els noms de variable de la columna 'Variable' de l'Excel."""
    wb = load_workbook(path, read_only=True)
    ws = wb.active
    variables = []
    for row in ws.iter_rows(values_only=True):
        raw = row[1]
        if not raw:
            continue
        cleaned = clean_var_name(str(raw))
        if cleaned and cleaned not in ('variable',):
            variables.append(cleaned)
    wb.close()
    return variables


# ── Dominis de valors per variable ───────────────────────────────────────────

def _make_domains(variables: list[str]) -> dict:
    """
    Assigna dominis de valors a cada variable.
    Les variables numèriques conegudes reben rangs (min, max).
    La resta reben llistes de valors categòrics.
    """
    NUMERIC = {
        "edad":                      (18, 95),
        "dolor_agudo":               (0, 10),
        "dolor_cronico":             (0, 10),
        "indice_de_comorbilidad":    (0, 8),
        "presencia_e_intesidad_de_sintomas": (0, 10),
        "presencia_e_intensidad_de_sintomas": (0, 10),
        "valoracion_antropometrica": (40, 120),
    }
    BINARY   = ["si", "no"]
    BINARY_VARS = {
        "ansiedad", "anticoagulacion", "agitacion", "agresividad",
        "barrera_idiomatica", "conducta_erratica",
        "consumo_de_otras_sustancias_adictivas",
        "cuidadora_informal_asalariada_disponible",
        "cuidadora_informal_no_asalariada_disponible",
        "cuidados_paliativos", "deshidratacion",
        "desbalance_hipoglucemico_significativo", "disfagia",
        "enfermedad_neoplasica", "inmunodepresion",
        "inestabilidad_hemodinamica", "infeccion_activa_en_curso",
        "insuficiencia_cronica_de_aparato", "insuficiencia_cronica_de_organo",
        "insuficiencia_cronica_de_sistema", "medicacion_de_alto_riesgo",
        "migracion", "polifarmacia", "riesgo_de_delirium",
        "riesgo_hemorragico_relevante", "riesgo_tromboembolico_relevante",
        "soledad_no_deseada", "tabaquismo", "depresion", "etapa_vital",
    }
    CATEGORICAL = {
        "actividades_basicas_de_la_vida_diaria":
            ["independiente", "dependencia_leve", "dependencia_moderada",
             "dependencia_severa", "dependencia_total"],
        "actividades_instrumentales_de_la_vida_diaria":
            ["independiente", "dependencia_leve", "dependencia_moderada", "dependencia_severa"],
        "adherencia_terapeutica":   ["alta", "media", "baja"],
        "alfabetizacion_en_salud":  ["alta", "media", "baja"],
        "alteracion_del_patron_respiratorio":
            ["no", "leve", "moderada", "grave"],
        "comunicacion_verbal":      ["normal", "moderada", "limitada", "nula"],
        "consumo_de_alcohol":       ["no", "moderado", "riesgo", "perjudicial"],
        "continencia":              ["continente", "parcial", "incontinencia"],
        "cribado_de_pobreza":       ["negativo", "positivo"],
        "cribado_nutricional":      ["sin_riesgo", "riesgo_leve", "riesgo_moderado", "riesgo_alto"],
        "deficit_de_audicion":      ["no", "leve", "moderada", "grave"],
        "deficit_de_vision":        ["no", "leve", "moderada", "grave"],
        "deterioro_global":         ["no", "leve", "moderado", "grave"],
        "diversidad_funcional":     ["no", "fisica", "sensorial", "cognitiva", "multiple"],
        "estado_cognitivo":
            ["sin_deterioro", "deterioro_leve", "deterioro_moderado", "deterioro_severo"],
        "fragilidad":               ["robusta", "prefragil", "fragil"],
        "movilidad_deambulacion_transferencia":
            ["independiente", "ayuda_tecnica", "supervision", "dependiente"],
        "nivel_de_autocuidado":     ["alto", "medio", "bajo"],
        "nivel_de_socioeconomico":  ["alto", "medio", "bajo"],
        "nivel_educativo":          ["sin_estudios", "primaria", "secundaria", "universitaria"],
        "origen":
            ["espanya", "ue", "america_latina", "africa", "asia", "altres"],
        "percepcion_sobre_la_salud_o_la_enfermedad":
            ["positiva", "neutra", "negativa"],
        "red_de_apoyo_aislamiento_social":
            ["buena", "moderada", "escasa", "aislamiento"],
        "riesgo_de_caidas":         ["bajo", "medio", "alto"],
        "riesgo_de_lesiones_por_presion_lesiones_relacionadas_con_la_dependencia":
            ["bajo", "medio", "alto"],
        "sexo_y_o_genero":          ["hombre", "mujer", "no_binario"],
        "situacion_de_convivencia": ["solo", "familia", "pareja", "residencia", "otros"],
        "sobrecarga_del_cuidador":  ["no", "leve", "moderada", "severa"],
        "valoracion_de_riesgos_en_el_domicilio": ["bajo", "medio", "alto"],
    }

    # Probabilitats de NaN realistes per variable
    NAN_PROBS = {
        "valoracion_de_riesgos_en_el_domicilio": 0.25,
        "sobrecarga_del_cuidador":               0.30,
        "alfabetizacion_en_salud":               0.20,
        "etapa_vital":                           0.15,
        "cribado_de_pobreza":                    0.20,
        "barrera_idiomatica":                    0.10,
        "valoracion_antropometrica":             0.15,
        "dolor_cronico":                         0.12,
        "red_de_apoyo_aislamiento_social":       0.10,
    }

    domains = {}
    for var in variables:
        if var in NUMERIC:
            domains[var] = {"type": "numeric", "range": NUMERIC[var], "nan_prob": NAN_PROBS.get(var, 0)}
        elif var in BINARY_VARS:
            domains[var] = {"type": "binary",  "values": BINARY,     "nan_prob": NAN_PROBS.get(var, 0)}
        elif var in CATEGORICAL:
            domains[var] = {"type": "categorical", "values": CATEGORICAL[var], "nan_prob": NAN_PROBS.get(var, 0)}
        else:
            # Variable no reconeguda → binari per defecte
            domains[var] = {"type": "binary", "values": BINARY, "nan_prob": 0}

    return domains


# ── Generació de valors ───────────────────────────────────────────────────────

def _gen_value(var: str, domain: dict, patient_profile: dict) -> str | None:
    """Genera un valor coherent per a la variable donada."""
    if random.random() < domain["nan_prob"]:
        return None

    t = domain["type"]

    if t == "numeric":
        lo, hi = domain["range"]
        if var == "edad":
            return str(patient_profile["edad"])
        val = random.gauss((lo + hi) / 2, (hi - lo) / 5)
        return str(max(lo, min(hi, round(val))))

    elif t in ("binary", "categorical"):
        vals = domain["values"]
        edad = patient_profile.get("edad", 50)

        # Correlacions bàsiques amb l'edat per a algunes variables
        if var == "fragilidad":
            if edad < 40:   w = [0.70, 0.25, 0.05]
            elif edad < 65: w = [0.40, 0.40, 0.20]
            else:           w = [0.15, 0.35, 0.50]
            return random.choices(vals, weights=w)[0]

        if var == "estado_cognitivo":
            if edad < 60:   w = [0.75, 0.15, 0.07, 0.03]
            elif edad < 75: w = [0.45, 0.30, 0.17, 0.08]
            else:           w = [0.20, 0.30, 0.30, 0.20]
            return random.choices(vals, weights=w)[0]

        return random.choice(vals)

    return None


# ── Generació del dataset ─────────────────────────────────────────────────────

def generate_dataset(
    variables: list[str],
    n_patients: int = 2000,
    visits_per_patient: int = 2,
    output_path: str = "sample_data/dataset_2000p.csv",
):
    domains = _make_domains(variables)
    rows    = []
    base    = date(2023, 1, 1)

    for i in range(1, n_patients + 1):
        pid     = f"P{i:04d}"
        profile = {"edad": random.randint(18, 92)}

        # Dates de visita separades almenys 20 dies
        first_visit = base + timedelta(days=random.randint(0, 365))
        visits = [first_visit]
        for _ in range(visits_per_patient - 1):
            visits.append(visits[-1] + timedelta(days=random.randint(20, 180)))

        for visit_date in visits:
            date_str = visit_date.strftime("%Y-%m-%d")
            for var in variables:
                val = _gen_value(var, domains[var], profile)
                rows.append({
                    "patient_id": pid,
                    "data":       date_str,
                    "variable":   var,
                    "valor":      val if val is not None else "",
                })

    random.shuffle(rows)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["patient_id", "data", "variable", "valor"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ Dataset generat: {len(rows):,} registres")
    print(f"   {n_patients} pacients × {visits_per_patient} visites × {len(variables)} variables")
    print(f"   → {output_path}")


# ── Punt d'entrada ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os, sys

    excel_path = "sample_data/Cataluña_Unificado.xlsx"

    if OPENPYXL_OK and os.path.exists(excel_path):
        print(f"📋 Llegint variables des de {excel_path}...")
        variables = load_variables_from_excel(excel_path)
        print(f"   {len(variables)} variables detectades")
    else:
        print("⚠ Excel no trobat o openpyxl no disponible. Usa la llista predefinida.")
        # Fallback: llista mínima predefinida
        variables = [
            "sexo_y_o_genero", "edad", "situacion_de_convivencia", "migracion",
            "nivel_educativo", "nivel_de_socioeconomico", "estado_cognitivo",
            "fragilidad", "indice_de_comorbilidad", "dolor_agudo", "dolor_cronico",
            "ansiedad", "depresion", "polifarmacia", "medicacion_de_alto_riesgo",
        ]

    generate_dataset(variables, n_patients=2000, visits_per_patient=2)
