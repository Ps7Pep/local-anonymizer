# CCI-SNS catalogue (copy)

Variables and **provisional** categories of the CCI-SNS model (Patient Complexity and Nursing Care
Needs), copied verbatim from the `cci-sns-portal` project, `pesos/data/`, commit `c9b16d0`
(2026-10-16):

| File | Content |
|---|---|
| `variables_cci_sns.csv` | 5 domains, 64 variables (`activa = 1` → 42 in use), definitions and references |
| `categorias_cci_sns_provisional.csv` | categories of each active variable: order, criterion (instrument range), reference and «No evaluable» |

Only `generate_synthetic.py` reads them, to build the synthetic demo datasets in `sample_data/`.
They are not part of the application and are not copied into the Docker image.

When the catalogue changes in `cci-sns-portal`, copy both files again and run the generators
(see the main README). The generator stops if an instrument scale no longer matches the categories
of its variable.
