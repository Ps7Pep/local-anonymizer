"""
generate_multifile_sample.py
-----------------------------
Reparteix cada dataset de línia (sample_data/<línia>/dataset_<línia>.csv) en
5 fitxers, un per domini del catàleg CCI-SNS:

  <línia>_D1_funcional_motor.csv
  <línia>_D2_cognitivo_mental_conductual.csv
  <línia>_D3_soporte_vital_riesgo_clinico.csv
  <línia>_D4_comorbilidad_cronicidad.csv
  <línia>_D5_social_contextual.csv

No genera dades noves: és una partició exacta del dataset de la línia (cada fila
va al fitxer del domini de la seva variable). Els 5 fitxers són coherents entre
ells — mateixos pacients, mateixes dates, mateixos valors — com les taules d'un
mateix extracte, i pujar-los junts dona el mateix resultat que el fitxer únic.

Ús (després de generate_synthetic.py):
    python generate_multifile_sample.py
"""

import csv
import os

from generate_synthetic import FIELDS, LINES, dataset_path, domain_files, load_catalog


def split(line: str, catalog: list[dict]) -> dict[str, int]:
    domain_of = {v["name"]: v["domain_id"] for v in catalog}
    suffix    = domain_files(catalog)
    source    = dataset_path(line)
    per_domain: dict[str, list[dict]] = {d: [] for d in suffix}

    with open(source, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            domain = domain_of.get(row["variable"])
            if domain is None:
                raise ValueError(f"{source}: variable fora del catàleg: {row['variable']!r}")
            per_domain[domain].append(row)

    totals = {}
    for domain, rows in per_domain.items():
        path = os.path.join(os.path.dirname(source), f"{line}_{suffix[domain]}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        totals[path] = len(rows)
    return totals


if __name__ == "__main__":
    catalog = load_catalog()
    for line in LINES:
        totals = split(line, catalog)
        for path, n in totals.items():
            print(f"{path}: {n:,} registres")
        print(f"  = {sum(totals.values()):,} registres de {dataset_path(line)} (partició exacta)\n")
