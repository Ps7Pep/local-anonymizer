"""
generate_multifile_sample.py
-----------------------------
Genera 4 CSVs sintètics amb els mateixos 2.000 pacients i 2 visites,
però amb les 65 variables repartides en 4 blocs temàtics:

  1_determinantes_sociales.csv    — determinants socials i demogràfics
  2_salud_mental_conductual.csv   — salut mental, conductual i percepció
  3_funcionalidad_autonomia.csv   — funcionalitat i autonomia
  4_complejidad_clinica.csv       — complexitat clínica i risc

Format idèntic al dataset original: patient_id, data, variable, valor
Mateix identificador de pacient a tots 4 fitxers (per poder fer join).
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from generate_synthetic import (
    load_variables_from_excel, _make_domains, _gen_value,
    generate_dataset
)
import csv
import random
from datetime import date, timedelta

random.seed(42)

# ── Blocs temàtics ─────────────────────────────────────────────────────────────
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

# ── Generació ──────────────────────────────────────────────────────────────────

def generate_multifile(n_patients=2000, visits=2, output_dir="sample_data"):
    # Carrega tots els dominis d'una vegada
    all_vars = []
    for block_vars in BLOCKS.values():
        all_vars.extend(block_vars)
    domains = _make_domains(all_vars)

    # Genera perfils i visites de tots els pacients una sola vegada
    # perquè l'edat i altres perfils siguin consistents entre fitxers
    base = date(2023, 1, 1)
    patient_profiles = {}
    patient_visits   = {}

    for i in range(1, n_patients + 1):
        pid  = f"P{i:04d}"
        edad = random.randint(18, 92)
        patient_profiles[pid] = {"edad": edad}

        first = base + timedelta(days=random.randint(0, 365))
        visit_dates = [first]
        for _ in range(visits - 1):
            visit_dates.append(visit_dates[-1] + timedelta(days=random.randint(20, 180)))
        patient_visits[pid] = [v.strftime("%Y-%m-%d") for v in visit_dates]

    # Genera un CSV per bloc
    os.makedirs(output_dir, exist_ok=True)
    totals = {}

    for block_name, block_vars in BLOCKS.items():
        rows = []
        for pid, profile in patient_profiles.items():
            for visit_date in patient_visits[pid]:
                for var in block_vars:
                    val = _gen_value(var, domains[var], profile)
                    rows.append({
                        "patient_id": pid,
                        "data":       visit_date,
                        "variable":   var,
                        "valor":      val if val is not None else "",
                    })

        random.shuffle(rows)
        out_path = os.path.join(output_dir, f"{block_name}.csv")
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["patient_id", "data", "variable", "valor"]
            )
            writer.writeheader()
            writer.writerows(rows)

        totals[block_name] = len(rows)
        print(f"✅  {block_name}.csv  →  {len(rows):,} registres  ({len(block_vars)} variables)")

    print(f"\nTotal: {sum(totals.values()):,} registres · {n_patients} pacients · {visits} visites")
    print(f"Mateixos {n_patients} patient_id a tots 4 fitxers → es pot fer join directament")


if __name__ == "__main__":
    generate_multifile(n_patients=2000, visits=2)
