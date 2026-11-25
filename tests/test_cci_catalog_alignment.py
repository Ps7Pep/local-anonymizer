"""
CCI-SNS catalogue alignment (v4.3.0).

The CCI-SNS portal maps each released age band to exactly one category of the
catalogue (Edad, D5V14) using closed codes. A band that crosses a catalogue
boundary (1, 2, 6, 12, 18, 65, 75, 90 years) can no longer be assigned, and the
whole variable is lost. So, for an item aligned with the catalogue:

  1. the only labels that can leave the tool are the nine catalogue bands,
     plus «Desconocido» and «Fuera de rango» (both unmapped in the portal);
  2. the backend accepts exactly that scheme, nothing else (no internal cuts);
  3. a missing age is not imputed (a median would get an invented category);
  4. when k fails, values are suppressed (→ «Desconocido») before patients,
     and categories are never merged.

Synthetic data only.

Run:  python -m pytest tests/test_cci_catalog_alignment.py -v
"""
import io
import math
import random
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from app.main import app, sessions
from app.modules.anonymizer import (
    CATALOG_SCHEMES, OUT_OF_RANGE_LABEL, UNKNOWN_LABEL,
    apply_generalizations, apply_k_anonymity,
)

client = TestClient(app)
SCHEME = CATALOG_SCHEMES["cci_sns_edad"]

# What the portal accepts, written independently of the scheme: closed intervals
# of completed years → closed code. Every released label must be one of these.
PORTAL_BANDS = [(0, 0, "0"), (1, 1, "1"), (2, 5, "2-5"), (6, 11, "6-11"), (12, 17, "12-17"),
                (18, 64, "18-64"), (65, 74, "65-74"), (75, 89, "75-89"), (90, 130, "90-130")]
PORTAL_CATEGORY = {"0": None, "1": "D5V14C03", "2-5": "D5V14C04", "6-11": "D5V14C05",
                   "12-17": "D5V14C06", "18-64": "D5V14C07", "65-74": "D5V14C08",
                   "75-89": "D5V14C09", "90-130": "D5V14C10"}
CATALOG_BOUNDARIES = {1, 2, 6, 12, 18, 65, 75, 90}
ALLOWED = {lbl for _, _, lbl in PORTAL_BANDS} | {UNKNOWN_LABEL, OUT_OF_RANGE_LABEL}

ALIGNED = {"type": "bins", "catalog": "cci_sns_edad",
           "bins": SCHEME["bins"], "labels": SCHEME["labels"], "suppress_value": True}


def _portal_label(age: float) -> str | None:
    years = math.floor(age)
    for lo, hi, lbl in PORTAL_BANDS:
        if lo <= years <= hi:
            return lbl
    return None


def _df(rows):
    return pd.DataFrame(rows, columns=["pacient", "data", "item", "valor"])


def _upload(csvs: dict[str, str]):
    files = [("files", (n, io.BytesIO(b.encode("utf-8")), "text/csv")) for n, b in csvs.items()]
    r = client.post("/api/upload", files=files)
    assert r.status_code == 200, r.text
    return r.json()


def _session(body: str, quasi: set, gens: dict | None = None):
    up = _upload({"d.csv": body})
    sid = up["session_id"]
    cls = {it["name"]: ("quasi_id" if it["name"] in quasi else "non_id") for it in up["items"]}
    r = client.post("/api/classify", json={"session_id": sid, "classifications": cls})
    assert r.status_code == 200, r.text
    if gens is not None:
        r = client.post("/api/set-generalizations", json={"session_id": sid, "generalizations": gens})
        assert r.status_code == 200, r.text
    return sid, r


# ── 1. The scheme is exactly the portal's ─────────────────────────────────────

def test_labels_are_exactly_the_portal_codes_in_ascii():
    assert SCHEME["labels"] == [lbl for _, _, lbl in PORTAL_BANDS]
    assert all(lbl.isascii() for lbl in SCHEME["labels"])          # ASCII hyphen, no en dash
    assert {c["id"] if c else None for c in SCHEME["categories"]} == set(PORTAL_CATEGORY.values())
    assert dict(zip(SCHEME["labels"], (c["id"] if c else None for c in SCHEME["categories"]))) == PORTAL_CATEGORY


def test_no_band_crosses_a_catalogue_boundary():
    """Each [a, b) band holds whole years of one portal interval only, and every
    catalogue boundary is a cut point."""
    bins = SCHEME["bins"]
    assert CATALOG_BOUNDARIES <= set(bins)
    for a, b in zip(bins, bins[1:]):
        assert not any(a < x < b for x in CATALOG_BOUNDARIES), (a, b)
        assert {_portal_label(y) for y in range(a, b)} == {_portal_label(a)}


def test_every_age_lands_in_its_portal_band():
    rng = random.Random(1)
    ages = list(range(0, 131)) + [rng.uniform(0, 131) for _ in range(3000)] + [64.999, 0.01, 130.99]
    df = _df([(f"P{i}", 0, "Edad", str(a)) for i, a in enumerate(ages)])
    out, log = apply_generalizations(df, {"Edad": ALIGNED})
    for age, lbl in zip(ages, out["valor"]):
        assert lbl == _portal_label(age), (age, lbl)
    assert log["Edad"] == {"type": "bins", "n_non_numeric": 0, "n_out_of_range": 0}


def test_unmappable_values_never_get_a_band():
    vals = ["-1", "-0.5", "131", "131.5", "200", "", None, "81 años", "abc", "NaN"]
    df = _df([(f"P{i}", 0, "Edad", v) for i, v in enumerate(vals)])
    out, log = apply_generalizations(df, {"Edad": ALIGNED})
    assert list(out["valor"]) == [OUT_OF_RANGE_LABEL] * 5 + [UNKNOWN_LABEL] * 5
    assert log["Edad"]["n_out_of_range"] == 5 and log["Edad"]["n_non_numeric"] == 5


def test_scheme_wins_over_whatever_the_config_carries():
    """Defence in depth: even if a config slipped past validation, an aligned
    item is cut with the catalogue scheme."""
    bad = dict(ALIGNED, bins=[0, 40, 131], labels=["0-39", "40-130"])
    df = _df([("P1", 0, "Edad", "50")])
    out, _ = apply_generalizations(df, {"Edad": bad})
    assert out["valor"].iloc[0] == "18-64"


# ── 2. Backend accepts exactly the scheme ─────────────────────────────────────

CSV_SMALL = ("patient_id,fecha,variable,valor\n"
             "P1,2024-01-01,Edad,30\nP2,2024-01-01,Edad,35\nP3,2024-01-01,Edad,\nP4,2024-01-01,Edad,70\n"
             "P1,2024-01-01,Sexo,M\nP2,2024-01-01,Sexo,M\nP3,2024-01-01,Sexo,F\nP4,2024-01-01,Sexo,F\n")


@pytest.mark.parametrize("cfg", [
    # internal cuts inside a catalogue band (18-39 / 40-64): rejected, no subdivisions
    dict(ALIGNED, bins=[0, 1, 2, 6, 12, 18, 40, 65, 75, 90, 131],
         labels=["0", "1", "2-5", "6-11", "12-17", "18-39", "40-64", "65-74", "75-89", "90-130"]),
    dict(ALIGNED, labels=["0", "1", "2–5", "6–11", "12–17", "18–64", "65–74", "75–89", "90–130"]),  # en dash
    dict(ALIGNED, bins=[0, 1, 2, 6, 12, 18, 65, 75, 131], labels=SCHEME["labels"][:-2] + ["75-130"]),
    dict(ALIGNED, bins=[0, 1, 2, 6, 12, 18, 65, 75, 90, 120]),
    dict(ALIGNED, labels=list(reversed(SCHEME["labels"]))),
    dict(ALIGNED, bins=None),
    dict(ALIGNED, catalog="cci_sns_edad_v2"),
    {"type": "mapping", "catalog": "cci_sns_edad", "mapping": {}},
    dict(ALIGNED, suppress_value="yes"),
])
def test_anything_but_the_exact_scheme_is_a_400(cfg):
    sid, _ = _session(CSV_SMALL, {"Edad"})
    r = client.post("/api/set-generalizations", json={"session_id": sid, "generalizations": {"Edad": cfg}})
    assert r.status_code == 400, r.text
    sessions.pop(sid, None)


def test_exact_scheme_is_accepted():
    sid, r = _session(CSV_SMALL, {"Edad"}, {"Edad": ALIGNED})
    assert r.status_code == 200
    sessions.pop(sid, None)


def test_classify_hands_the_scheme_to_the_frontend():
    up = _upload({"d.csv": CSV_SMALL})
    r = client.post("/api/classify", json={"session_id": up["session_id"],
                                           "classifications": {"Edad": "quasi_id", "Sexo": "non_id"}})
    assert r.json()["catalog_schemes"]["cci_sns_edad"]["labels"] == SCHEME["labels"]
    sessions.pop(up["session_id"], None)


# ── 3. No imputation on aligned items ─────────────────────────────────────────

def test_missing_age_is_not_imputed_when_aligned():
    sid, _ = _session(CSV_SMALL, {"Edad", "Sexo"},
                      {"Edad": ALIGNED, "Sexo": {"type": "mapping", "mapping": {"M": "M", "F": "F"}}})
    res = client.post("/api/anonymize", json={"session_id": sid, "k": 2, "lang": "es"}).json()
    assert "Edad" not in res["imputation_log"]
    assert res["generalization_log"]["Edad"]["n_non_numeric"] == 1
    df_out = sessions[sid]["dfs_anonymized"]["d.csv"]
    # P3's empty age stays «Desconocido» (the median, 35, would have become «18-64»);
    # P4 (70, F) is alone at k=2, loses the age value and joins P3
    edad = df_out[df_out["item"] == "Edad"]["valor"].value_counts().to_dict()
    assert edad == {"18-64": 2, UNKNOWN_LABEL: 2}, edad
    assert res["n_suppressed_patients"] == 0 and res["value_suppressed"] == {"Edad": 1}
    sessions.pop(sid, None)


def test_non_aligned_numeric_item_is_still_imputed():
    sid, _ = _session(CSV_SMALL, {"Edad"},
                      {"Edad": {"type": "bins", "bins": [0, 50, 131], "labels": ["<50", "50+"]}})
    res = client.post("/api/anonymize", json={"session_id": sid, "k": 2, "lang": "es"}).json()
    assert res["imputation_log"]["Edad"]["strategy"] == "mediana (35)"
    sessions.pop(sid, None)


# ── 4. Value suppression before patient suppression ──────────────────────────

def _rows_for(patients):
    """patients: {pid: {item: value or [values per visit]}}"""
    rows = []
    for pid, items in patients.items():
        for item, v in items.items():
            for visit, val in enumerate(v if isinstance(v, list) else [v]):
                rows.append((pid, visit * 1440, item, val))
            rows.append((pid, 0, "barthel", "60"))
    return _df(rows)


def test_rare_ages_lose_the_value_not_the_patient():
    df = _rows_for({
        "A": {"Edad": "18-64", "Sexo": "M"}, "B": {"Edad": "18-64", "Sexo": "M"},
        "C": {"Edad": "90-130", "Sexo": "M"},       # alone in its band
        "D": {"Edad": "2-5", "Sexo": "M"},          # alone in its band
    })
    plain = apply_k_anonymity(df, ["Edad", "Sexo"], 2)
    assert plain["n_suppressed_patients"] == 2

    res = apply_k_anonymity(df, ["Edad", "Sexo"], 2, ["Edad"])
    out = res["df_anonymized"]
    assert res["n_suppressed_patients"] == 0
    assert res["n_value_suppressed_patients"] == 2 and res["value_suppressed"] == {"Edad": 2}
    assert res["n_value_suppressed_records"] == 2
    edad = out[out["item"] == "Edad"].set_index("pacient")["valor"].to_dict()
    assert edad == {"A": "18-64", "B": "18-64", "C": UNKNOWN_LABEL, "D": UNKNOWN_LABEL}
    # the rest of C and D is released untouched
    assert set(out[out["item"] == "barthel"]["pacient"]) == {"A", "B", "C", "D"}


def test_patient_is_removed_when_value_suppression_is_not_enough():
    df = _rows_for({
        "A": {"Edad": "18-64", "Sexo": "M"}, "B": {"Edad": "18-64", "Sexo": "M"},
        "C": {"Edad": "90-130", "Sexo": "X"},       # still alone as (Desconocido, X)
    })
    res = apply_k_anonymity(df, ["Edad", "Sexo"], 2, ["Edad"])
    assert res["n_suppressed_patients"] == 1 and res["n_value_suppressed_patients"] == 0
    assert "C" not in set(res["df_anonymized"]["pacient"])


def test_no_record_is_invented_for_a_patient_without_the_item():
    df = _rows_for({"A": {"Sexo": "M"}, "B": {"Sexo": "M"}, "C": {"Sexo": "F"},
                    "D": {"Edad": "18-64", "Sexo": "M"}, "E": {"Edad": "18-64", "Sexo": "M"}})
    res = apply_k_anonymity(df, ["Edad", "Sexo"], 2, ["Edad"])
    out = res["df_anonymized"]
    assert "C" not in set(out["pacient"])                       # nothing to suppress → removed
    assert set(out[out["item"] == "Edad"]["pacient"]) == {"D", "E"}


def test_longitudinal_signature_suppresses_every_visit_value():
    df = _rows_for({
        "A": {"Edad": ["18-64", "18-64"]}, "B": {"Edad": ["18-64", "18-64"]},
        "C": {"Edad": ["18-64", "65-74"]},          # crossed 65 between visits: unique set
        "D": {"Edad": UNKNOWN_LABEL},
    })
    res = apply_k_anonymity(df, ["Edad"], 2, ["Edad"])
    out = res["df_anonymized"]
    c = out[(out["pacient"] == "C") & (out["item"] == "Edad")]["valor"]
    assert list(c) == [UNKNOWN_LABEL, UNKNOWN_LABEL]           # joins D, never a merged band
    assert res["n_suppressed_patients"] == 0


def test_value_suppression_works_on_mapping_items_too():
    df = _rows_for({"A": {"Sexo": "M", "Origen": "ES"}, "B": {"Sexo": "M", "Origen": "ES"},
                    "C": {"Sexo": "M", "Origen": "MA"}, "D": {"Sexo": "M", "Origen": "PE"}})
    res = apply_k_anonymity(df, ["Sexo", "Origen"], 2, ["Origen"])
    assert res["n_suppressed_patients"] == 0 and res["value_suppressed"] == {"Origen": 2}


def _random_dataset(rng: random.Random, n: int) -> pd.DataFrame:
    rows = []
    for i in range(n):
        pid = f"P{i:04d}"
        a0 = rng.choice([rng.randint(0, 1), rng.randint(2, 17), rng.randint(18, 100), rng.randint(90, 110)])
        sexo = rng.choice(["M", "F", "F", "M", "X"])
        for visit in range(rng.randint(1, 3)):
            age = rng.choice([str(a0 + visit // 2), "", "noventa", str(rng.uniform(-3, 140))]) \
                if rng.random() < 0.05 else str(a0 + visit // 2)
            rows += [(pid, visit * 1440, "Edad", age), (pid, visit * 1440, "Sexo", sexo),
                     (pid, visit * 1440, "barthel", str(rng.randint(0, 100)))]
    return _df(rows)


@pytest.mark.parametrize("seed", range(12))
def test_released_ages_are_only_catalogue_bands_and_output_is_k_anonymous(seed):
    rng = random.Random(seed)
    k = rng.randint(2, 5)
    df, _ = apply_generalizations(_random_dataset(rng, rng.randint(30, 400)),
                                  {"Edad": ALIGNED, "Sexo": {"type": "mapping", "mapping": {"M": "M", "F": "F"}}})
    quasi = ["Edad", "Sexo"]
    plain = apply_k_anonymity(df, quasi, k)
    res   = apply_k_anonymity(df, quasi, k, ["Edad"])
    out   = res["df_anonymized"]

    # 1. only the nine bands + Desconocido / Fuera de rango, never a merged band
    assert set(out.loc[out["item"] == "Edad", "valor"]) <= ALLOWED
    # 2. the release really is k-anonymous over the published values
    assert apply_k_anonymity(out, quasi, k)["n_suppressed_patients"] == 0
    # 3. patients that met k without help are released exactly as before
    kept = set(plain["df_anonymized"]["pacient"])
    assert kept <= set(out["pacient"])
    cols = ["pacient", "data", "item", "valor"]
    before = plain["df_anonymized"][cols].sort_values(cols).reset_index(drop=True)
    after  = out[out["pacient"].isin(kept)][cols].sort_values(cols).reset_index(drop=True)
    pd.testing.assert_frame_equal(before, after)
    # 4. counts add up; value suppression never loses more patients. (A patient
    #    can also be saved unchanged, when suppressed values join its group.)
    assert res["n_patients_final"] + res["n_suppressed_patients"] == res["n_patients_orig"]
    assert res["n_suppressed_patients"] <= plain["n_suppressed_patients"]
    assert res["n_patients_final"] - plain["n_patients_final"] >= res["n_value_suppressed_patients"]


# ── 5. End to end: API, sample data, report ──────────────────────────────────

def _run_api(body: str, filename: str, k: int):
    up = _upload({filename: body})
    sid = up["session_id"]
    quasi = {"Edad", "Sexo / Género"}
    cls = {it["name"]: ("quasi_id" if it["name"] in quasi else "non_id") for it in up["items"]}
    client.post("/api/classify", json={"session_id": sid, "classifications": cls})
    gens = {"Edad": ALIGNED,
            "Sexo / Género": {"type": "mapping", "mapping": {"Femenino": "F", "Masculino": "M"},
                              "unmapped_label": "Otros", "suppress_value": False}}
    r = client.post("/api/set-generalizations", json={"session_id": sid, "generalizations": gens})
    assert r.status_code == 200, r.text
    sim = client.post("/api/simulate-k", json={"session_id": sid}).json()
    res = client.post("/api/anonymize", json={"session_id": sid, "k": k, "lang": "es"}).json()
    return sid, sim, res


@pytest.fixture(scope="module")
def sample_run():
    body = (ROOT / "sample_data" / "AH" / "dataset_AH.csv").read_text(encoding="utf-8")
    sid, sim, res = _run_api(body, "dataset_AH.csv", k=5)
    yield sid, sim, res
    sessions.pop(sid, None)


def test_sample_dataset_releases_only_catalogue_bands(sample_run):
    sid, sim, res = sample_run
    assert sim["suppress_value_items"] == ["Edad"]
    assert all("n_value_suppressed" in s for s in sim["simulations"])

    out = pd.read_csv(io.BytesIO(client.get(f"/api/download/csv/{sid}").content), dtype=str,
                      keep_default_na=False)
    ages = out.loc[out["item"] == "Edad", "valor"]
    assert len(ages) and set(ages) <= ALLOWED, set(ages) - ALLOWED
    assert res["n_patients_final"] + res["n_suppressed_patients"] == res["n_patients_orig"]


def test_report_carries_the_catalogue_reference_table(sample_run):
    sid, _, res = sample_run
    md = client.get(f"/api/download/report/md/{sid}").text
    assert f"catálogo del {SCHEME['catalog_date']}" in md
    assert "| \\[90, 131) | `90-130` | `D5V14C10` Edad muy avanzada |" in md
    assert "| \\[1, 2) | `1` | `D5V14C03` Lactante |" in md
    assert "| \\[0, 1) | `0` | _sin categoría" in md
    assert "Valores ausentes no imputados" in md
    assert "Excepción — ítems alineados con el catálogo CCI-SNS" in md
    if res["n_value_suppressed_patients"]:
        assert "Pacientes con valor suprimido" in md

    html = client.get(f"/api/download/report/html/{sid}").text
    assert "D5V14C10" in html and "Edad muy avanzada" in html

    js = client.get(f"/api/download/report/{sid}").json()
    ref = js["catalog_reference"]["cci_sns_edad"]
    assert ref["labels"] == SCHEME["labels"] and ref["catalog_date"] == SCHEME["catalog_date"]
    assert js["generalizations"]["Edad"]["catalog"] == "cci_sns_edad"
    assert "n_value_suppressed_patients" in js["metrics"]


def test_report_without_catalogue_items_has_no_catalogue_section():
    sid, _ = _session(CSV_SMALL, {"Edad"},
                      {"Edad": {"type": "bins", "bins": [0, 50, 131], "labels": ["<50", "50+"]}})
    client.post("/api/anonymize", json={"session_id": sid, "k": 2, "lang": "es"})
    md = client.get(f"/api/download/report/md/{sid}").text
    assert "catálogo CCI-SNS" not in md and "D5V14" not in md
    assert client.get(f"/api/download/report/{sid}").json()["catalog_reference"] == {}
    sessions.pop(sid, None)


# ── 6. The scheme still matches the catalogue copy ───────────────────────────
# The catalogue and the generator are not baked into the image (CI mounts only
# tests/): these run when the repo is mounted, and the generator runs the same
# check before producing any sample.

_CATALOG = ROOT / "catalogo_cci_sns" / "categorias_cci_sns_provisional.csv"
needs_catalog = pytest.mark.skipif(not _CATALOG.exists() or not (ROOT / "generate_synthetic.py").exists(),
                                   reason="catalogue copy / generator not mounted")


@needs_catalog
def test_scheme_matches_the_catalogue_copy():
    import generate_synthetic
    generate_synthetic.check_catalog_schemes(str(_CATALOG.parent))


@needs_catalog
@pytest.mark.parametrize("old,new", [
    ("65–74 años", "65–79 años"),                 # a boundary moves
    ("Edad muy avanzada", "Muy mayor"),           # a category is renamed
    ("D5V14,7,Adulto,18–64 años", "D5V14,7,Adulto,18–49 años\nD5V14,11,Adulto maduro,50–64 años"),
])
def test_generator_stops_when_the_catalogue_drifts(tmp_path, old, new):
    import generate_synthetic
    text = _CATALOG.read_text(encoding="utf-8")
    assert old in text
    (tmp_path / _CATALOG.name).write_text(text.replace(old, new, 1), encoding="utf-8")
    with pytest.raises(ValueError):
        generate_synthetic.check_catalog_schemes(str(tmp_path))
