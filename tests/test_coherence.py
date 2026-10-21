"""
Coherence-first pipeline, as with a real extract:

  1. the dataset is made coherent before anything else (IDs read as text,
     trimmed, rows that cannot be attributed dropped and reported, files
     combined),
  2. dates / imputation / generalization / k-anonymity run on the real IDs,
  3. the patient hash is applied LAST, only to the released records, with
     one session key for every file.

Also pins the synthetic sample (CCI-SNS catalogue, one dataset per care line):
the 5 domain files of each line are an exact partition of its dataset, and
demographics are stable per patient.

Run:  python -m pytest tests/test_coherence.py -v
"""
import csv
import hashlib
import hmac
import io
import sys
import zipfile
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
import app.main as main
from app.main import app, sessions

client = TestClient(app)
SAMPLE_DIR = Path(__file__).resolve().parents[1] / "sample_data"
LINES = ("AH", "AP", "LE")
DOMAINS = ("D1_funcional_motor", "D2_cognitivo_mental_conductual", "D3_soporte_vital_riesgo_clinico",
           "D4_comorbilidad_cronicidad", "D5_social_contextual")


def _single(line):
    return SAMPLE_DIR / line / f"dataset_{line}.csv"


def _parts(line):
    return [SAMPLE_DIR / line / f"{line}_{d}.csv" for d in DOMAINS]


def _upload(csvs: dict[str, str]):
    files = [("files", (n, io.BytesIO(b.encode("utf-8")), "text/csv")) for n, b in csvs.items()]
    r = client.post("/api/upload", files=files)
    assert r.status_code == 200, r.text
    return r.json()


def _run(up: dict, quasi: set, k: int = 2):
    sid = up["session_id"]
    cls = {it["name"]: ("quasi_id" if it["name"] in quasi else "non_id") for it in up["items"]}
    assert client.post("/api/classify", json={"session_id": sid, "classifications": cls}).status_code == 200
    r = client.post("/api/anonymize", json={"session_id": sid, "k": k, "lang": "es"})
    assert r.status_code == 200, r.text
    return r.json()


def _h(key: bytes, pid: str) -> str:
    return "H-" + hmac.new(key, pid.encode(), hashlib.sha256).hexdigest()[:12]


# ── 1. Coherence before anything else ─────────────────────────────────────────

def test_numeric_ids_with_a_gap_stay_the_same_patient_across_files():
    """Pre-fix: pandas read file A's IDs as float because of the empty one
    (`12` → `12.0`) while file B kept ints, so no patient matched across
    files and each got two different hashes."""
    a = "patient_id,fecha,variable,valor\n0012,2024-01-01,edad,40\n7,2024-01-01,edad,40\n,2024-01-02,edad,60\n"
    b = "patient_id,fecha,variable,valor\n0012,2024-02-01,sexo,M\n7,2024-02-01,sexo,M\n"
    up = _upload({"A.csv": a, "B.csv": b})
    assert up["relationship"]["n_patients_shared_all"] == 2, up["relationship"]
    assert up["relationship"]["pct_patients_shared"] == 100.0
    assert up["coherence"]["n_dropped_rows"] == 1
    assert up["coherence"]["dropped_rows"] == {"A.csv": {"without_patient": 1, "without_item": 0}}

    _run(up, {"edad", "sexo"})
    key = sessions[up["session_id"]]["hash_key"]
    zf = zipfile.ZipFile(io.BytesIO(client.get(f"/api/download/csv/{up['session_id']}").content))
    out = {n: pd.read_csv(io.BytesIO(zf.read(n)), dtype=str) for n in zf.namelist()}
    expected = {_h(key, "0012"), _h(key, "7")}     # leading zeros kept in what gets hashed
    assert set(out["A_anonymized.csv"]["pacient"]) == expected
    assert set(out["B_anonymized.csv"]["pacient"]) == expected
    sessions.pop(up["session_id"], None)


def test_whitespace_around_ids_does_not_split_a_patient():
    a = "patient_id,fecha,variable,valor\nP1 ,2024-01-01,edad,40\n P2,2024-01-01,edad,40\n"
    b = "patient_id,fecha,variable,valor\nP1,2024-02-01,sexo,M\nP2,2024-02-01,sexo,M\n"
    up = _upload({"A.csv": a, "B.csv": b})
    assert up["n_patients"] == 2
    assert up["relationship"]["pct_patients_shared"] == 100.0
    sessions.pop(up["session_id"], None)


def test_values_are_released_exactly_as_written():
    """Reading as text: no `40` → `40.0`, no `007` → `7` in the output."""
    body = "patient_id,fecha,variable,valor\nP1,2024-01-01,codigo,007\nP2,2024-01-01,codigo,007\nP1,2024-01-02,peso,70\nP2,2024-01-02,peso,\n"
    up = _upload({"d.csv": body})
    _run(up, set())
    text = client.get(f"/api/download/csv/{up['session_id']}").content.decode("utf-8-sig")
    assert ",codigo,007" in text and ",peso,70\n" in text.replace("\r\n", "\n")
    sessions.pop(up["session_id"], None)


def test_duplicate_rows_are_reported_not_silently_kept():
    a = "patient_id,fecha,variable,valor\nP1,2024-01-01,edad,40\nP2,2024-01-01,edad,40\n"
    up = _upload({"A.csv": a, "B.csv": a.replace("edad", "edad")})   # same rows twice
    assert up["coherence"]["n_duplicate_rows"] == 2
    sessions.pop(up["session_id"], None)


def test_coherence_is_in_report_and_json():
    a = "patient_id,fecha,variable,valor\nP1,2024-01-01,edad,40\nP2,2024-01-01,edad,40\n,2024-01-01,edad,50\n"
    up = _upload({"A.csv": a})
    _run(up, {"edad"})
    sid = up["session_id"]
    assert client.get(f"/api/download/report/{sid}").json()["coherence"]["n_dropped_rows"] == 1
    md = client.get(f"/api/download/report/md/{sid}").text
    assert "Filas descartadas (sin paciente o sin variable) | 1 |" in md
    # methodology follows the real order: coherence first, pseudonymization last
    assert md.index("Fase 1 — Normalización y coherencia") < md.index("Fase 5 — K-anonimidad") \
        < md.index("Fase 6 — Seudonimización")
    sessions.pop(sid, None)


# ── 3. Hash last, only on released records ────────────────────────────────────

def test_hash_runs_after_k_anonymity_on_released_patients_only(monkeypatch):
    seen = []
    real = main.hash_patient_ids
    def spy(df, key):
        seen.append(set(df["pacient"]))
        return real(df, key)
    monkeypatch.setattr(main, "hash_patient_ids", spy)

    body = ("patient_id,fecha,variable,valor\n"
            "PA,2024-01-01,sexo,M\nPB,2024-01-01,sexo,M\nPX,2024-01-01,sexo,X\n")
    up = _upload({"d.csv": body})
    res = _run(up, {"sexo"}, k=2)
    assert res["n_suppressed_patients"] == 1
    assert seen == [{"PA", "PB"}], seen          # PX (suppressed) never reaches the hash
    sessions.pop(up["session_id"], None)


# ── Synthetic sample follows the same logic ──────────────────────────────────

def _rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return [tuple(r.values()) for r in csv.DictReader(f)]


def test_sample_files_are_an_exact_partition_of_each_line_dataset():
    for line in LINES:
        single = Counter(_rows(_single(line)))
        parts = Counter()
        for f in _parts(line):
            parts += Counter(_rows(f))
        assert parts == single, line
        items_per_file = [{r[2] for r in _rows(f)} for f in _parts(line)]
        assert sum(len(s) for s in items_per_file) == len(set().union(*items_per_file)), f"{line}: variable in >1 file"


def test_care_lines_are_independent_populations():
    ids = [{r[0] for r in _rows(_single(line))} for line in LINES]
    assert all(len(s) == 2000 for s in ids)
    assert not (ids[0] & ids[1]) and not (ids[0] & ids[2]) and not (ids[1] & ids[2])


def test_sample_demographics_are_stable_per_patient():
    for line in LINES:
        df = pd.read_csv(_single(line), dtype=str, keep_default_na=False)
        df = df[df["valor"] != ""]
        for var in ("Sexo / Género", "Migración / Origen", "Nivel socioeconómico", "Índice de comorbilidad"):
            per_patient = df[df["variable"] == var].groupby("patient_id")["valor"].nunique()
            assert (per_patient == 1).all(), f"{line} · {var}: changes between visits for {int((per_patient > 1).sum())} patients"
        # age is derived from a birth date: it can only stay or go up by one between visits
        edad = df[df["variable"] == "Edad"].assign(v=lambda d: d["valor"].astype(int)).sort_values("fecha")
        span = edad.groupby("patient_id")["v"].agg(lambda s: s.iloc[-1] - s.iloc[0])
        assert set(span.unique()) <= {0, 1}, line


def test_single_file_and_domain_files_give_the_same_result():
    quasi = {"Edad", "Sexo / Género"}
    with open(_single("AH"), encoding="utf-8") as f:
        single = _run(_upload({"dataset_AH.csv": f.read()}), quasi, k=5)
    parts = {}
    for path in _parts("AH"):
        with open(path, encoding="utf-8") as f:
            parts[path.name] = f.read()
    up = _upload(parts)
    assert up["relationship"]["pct_patients_shared"] == 100.0
    multi = _run(up, quasi, k=5)
    for key in ("n_patients_orig", "n_patients_final", "n_records_orig", "n_records_final"):
        assert single[key] == multi[key], key
    for sid in list(sessions):
        sessions.pop(sid, None)
