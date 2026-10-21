"""
generate_multifile_sample.py
-----------------------------
Reparteix sample_data/dataset_2000p.csv en 4 fitxers temàtics:

  1_determinantes_sociales.csv    — determinants socials i demogràfics
  2_salud_mental_conductual.csv   — salut mental, conductual i percepció
  3_funcionalidad_autonomia.csv   — funcionalitat i autonomia
  4_complejidad_clinica.csv       — complexitat clínica i risc

No genera dades noves: és una partició exacta del dataset únic (cada fila va a
un sol fitxer segons la seva variable). Així els 4 fitxers són coherents entre
ells i amb el fitxer únic — mateixos pacients, mateixes dates de visita, mateixos
valors — tal com ho serien les taules d'un mateix extracte real. Pujar els 4
junts o el fitxer únic ha de donar exactament el mateix resultat.

Ús (després de generate_synthetic.py):
    python generate_multifile_sample.py
"""

import csv
import os

from generate_synthetic import BLOCKS, OUTPUT as SOURCE

OUTPUT_DIR = "sample_data"


def split(source: str = SOURCE, output_dir: str = OUTPUT_DIR) -> dict[str, int]:
    block_of = {var: block for block, variables in BLOCKS.items() for var in variables}

    with open(source, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        per_block: dict[str, list[dict]] = {b: [] for b in BLOCKS}
        for row in reader:
            block = block_of.get(row["variable"])
            if block is None:
                raise ValueError(f"Variable sense bloc temàtic: {row['variable']!r}")
            per_block[block].append(row)

    totals = {}
    for block, rows in per_block.items():
        path = os.path.join(output_dir, f"{block}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        totals[block] = len(rows)
        print(f"{block}.csv  →  {len(rows):,} registres  ({len(BLOCKS[block])} variables)")
    return totals


if __name__ == "__main__":
    totals = split()
    print(f"\nTotal: {sum(totals.values()):,} registres = {SOURCE} (partició exacta)")
