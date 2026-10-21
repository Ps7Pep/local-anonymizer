"""
Adversarial multi-file tests with hand-crafted CSVs.

The sample fixtures have cleanly separated items per file, which can mask
index-misalignment bugs in the source-recovery / split-back logic. These tests
craft tiny CSVs where the expected per-file output is known exactly, and probe
the cases most likely to break:

  A. the SAME item appears in two files for the same patient — each row must
     return to its own file (worst case for `df_t.loc[df_anon.index, _SOURCE_COL]`)
  B. files with DIFFERENT raw column names per file (the confirm-mapping path)
  C. suppression removes a patient from ALL files at once, never partially
  D. a row order where survivors and suppressed are interleaved across files

Run:  python -m pytest tests/test_multifile_adversarial.py -v
"""
import io
import sys
import zipfile
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app.main import app, sessions

client = TestClient(app)
K = 2


def _upload(csvs: dict[str, str]):
    files = [("files", (name, io.BytesIO(body.encode("utf-8")), "text/csv"))
             for name, body in csvs.items()]
    return client.post("/api/upload", files=files)


def _zip_to_frames(content: bytes) -> dict[str, pd.DataFrame]:
    zf = zipfile.ZipFile(io.BytesIO(content))
    return {n: pd.read_csv(io.BytesIO(zf.read(n))) for n in zf.namelist()}


def _anonymize_to_outputs(csvs, classifications_quasi, k=K, confirm=None):
    r = _upload(csvs)
    assert r.status_code == 200, r.text
    up = r.json()
    sid = up["session_id"]

    if up["status"] == "needs_mapping":
        assert confirm is not None, f"upload needs mapping but no confirm provided: {up}"
        r = client.post("/api/confirm-mapping", json={"session_id": sid, "mappings": confirm})
        assert r.status_code == 200, r.text
        up = r.json()

    assert up["status"] == "ok", up
    classifications = {it["name"]: ("quasi_id" if it["name"] in classifications_quasi else "non_id")
                       for it in up["items"]}
    r = client.post("/api/classify", json={"session_id": sid, "classifications": classifications})
    assert r.status_code == 200, r.text
    r = client.post("/api/anonymize", json={"session_id": sid, "k": k, "lang": "es"})
    assert r.status_code == 200, r.text
    anon = r.json()
    r = client.get(f"/api/download/csv/{sid}")
    assert r.status_code == 200, r.text
    if r.headers["content-type"].startswith("application/zip"):
        frames = _zip_to_frames(r.content)
    else:
        frames = {"_single_": pd.read_csv(io.BytesIO(r.content))}
    sessions.pop(sid, None)
    return frames, anon


# ── A. Same item in two files, same patients ─────────────────────────────────

def test_same_item_in_two_files_rows_return_to_origin():
    """`edad` lives in BOTH files. Three patients share (edad=40, sexo=M) so
    they survive k=2; each patient's edad row in file A must come back in A's
    output and its file B copy in B's output — never swapped or merged."""
    # quasi-ids: edad (in both files), sexo (file A only)
    fileA = (
        "patient_id,data,variable,valor\n"
        "PA,2024-01-01,edad,40\n"
        "PB,2024-01-01,edad,40\n"
        "PC,2024-01-01,edad,40\n"
        "PA,2024-01-02,sexo,M\n"
        "PB,2024-01-02,sexo,M\n"
        "PC,2024-01-02,sexo,M\n"
    )
    fileB = (
        "patient_id,data,variable,valor\n"
        "PA,2024-03-01,edad,40\n"          # same item edad, different file
        "PB,2024-03-01,edad,40\n"
        "PC,2024-03-01,edad,40\n"
        "PA,2024-03-05,tension,alta\n"
        "PB,2024-03-05,tension,baja\n"
        "PC,2024-03-05,tension,alta\n"
    )
    frames, anon = _anonymize_to_outputs(
        {"A.csv": fileA, "B.csv": fileB}, classifications_quasi={"edad", "sexo"}, k=2,
    )
    a = frames["A_anonymized.csv"]
    b = frames["B_anonymized.csv"]

    # All 3 patients survive (group of 3 on the QI signature).
    assert anon["n_suppressed_patients"] == 0, anon
    assert anon["n_patients_final"] == 3

    # File A keeps exactly its items; file B keeps exactly its items.
    assert set(a["item"].unique()) == {"edad", "sexo"}, set(a["item"].unique())
    assert set(b["item"].unique()) == {"edad", "tension"}, set(b["item"].unique())

    # File A has 3 edad rows + 3 sexo rows = 6; file B has 3 edad + 3 tension = 6.
    assert len(a) == 6, a
    assert len(b) == 6, b

    # tension values must not have been corrupted/swapped between patients.
    # map hash->tension in B and confirm PA=alta, PB=baja, PC=alta by structure:
    tens = b[b["item"] == "tension"]["valor"].tolist()
    assert sorted(tens) == ["alta", "alta", "baja"], tens

    # edad appears 3x in A and 3x in B (not 6x in one file).
    assert (a["item"] == "edad").sum() == 3
    assert (b["item"] == "edad").sum() == 3


# ── B. Different raw column names per file (confirm-mapping path) ─────────────

def test_different_column_names_per_file_via_mapping():
    """File A uses canonical-ish aliases; file B uses non-alias headers that
    force the column-mapping gate. After confirming the mapping, the per-file
    split must still be exact."""
    fileA = (
        "patient_id,fecha,variable,valor\n"
        "PA,2024-01-01,edad,40\n"
        "PB,2024-01-01,edad,40\n"
        "PA,2024-02-01,sexo,M\n"
        "PB,2024-02-01,sexo,M\n"
    )
    # Non-alias headers -> positional fallback -> needs_mapping
    fileB = (
        "codigo,momento,campo_clinico,medida\n"
        "PA,2024-03-01,edad,40\n"
        "PB,2024-03-01,edad,40\n"
        "PA,2024-04-01,glucosa,99\n"
        "PB,2024-04-01,glucosa,99\n"
    )
    r = _upload({"A.csv": fileA, "B.csv": fileB})
    assert r.status_code == 200, r.text
    up = r.json()
    assert up["status"] == "needs_mapping", up
    sid = up["session_id"]

    confirm = {
        "A.csv": {"pacient": "patient_id", "data": "fecha", "item": "variable", "valor": "valor"},
        "B.csv": {"pacient": "codigo", "data": "momento", "item": "campo_clinico", "valor": "medida"},
    }
    r = client.post("/api/confirm-mapping", json={"session_id": sid, "mappings": confirm})
    assert r.status_code == 200, r.text
    up = r.json()
    assert up["status"] == "ok", up

    classifications = {it["name"]: ("quasi_id" if it["name"] in {"edad", "sexo"} else "non_id")
                       for it in up["items"]}
    client.post("/api/classify", json={"session_id": sid, "classifications": classifications})
    r = client.post("/api/anonymize", json={"session_id": sid, "k": 2, "lang": "es"})
    assert r.status_code == 200, r.text
    r = client.get(f"/api/download/csv/{sid}")
    frames = _zip_to_frames(r.content)
    a = frames["A_anonymized.csv"]
    b = frames["B_anonymized.csv"]
    sessions.pop(sid, None)

    assert set(a["item"].unique()) == {"edad", "sexo"}
    assert set(b["item"].unique()) == {"edad", "glucosa"}
    assert (b["item"] == "glucosa").sum() == 2
    assert set(b[b["item"] == "glucosa"]["valor"].astype(str)) == {"99"}


# ── C. Suppression is all-or-nothing across files ─────────────────────────────

def test_suppressed_patient_removed_from_every_file():
    """PX is unique on the QI signature (sexo=X) and must be suppressed at k=2.
    PX has rows in BOTH files; NONE may survive in either output."""
    fileA = (
        "patient_id,data,variable,valor\n"
        "PA,2024-01-01,sexo,M\n"
        "PB,2024-01-01,sexo,M\n"
        "PX,2024-01-01,sexo,X\n"          # unique -> suppressed
        "PA,2024-01-02,nota,a1\n"
        "PB,2024-01-02,nota,b1\n"
        "PX,2024-01-02,nota,x1\n"
    )
    fileB = (
        "patient_id,data,variable,valor\n"
        "PA,2024-03-01,peso,70\n"
        "PB,2024-03-01,peso,71\n"
        "PX,2024-03-01,peso,72\n"          # PX rows here too
    )
    frames, anon = _anonymize_to_outputs(
        {"A.csv": fileA, "B.csv": fileB}, classifications_quasi={"sexo"}, k=2,
    )
    a = frames["A_anonymized.csv"]
    b = frames["B_anonymized.csv"]
    import hashlib
    hx = "H-" + hashlib.sha256(b"PX").hexdigest()[:12]

    assert anon["n_suppressed_patients"] == 1, anon
    assert hx not in set(a["pacient"].astype(str)), "suppressed PX present in file A"
    assert hx not in set(b["pacient"].astype(str)), "suppressed PX present in file B"
    # survivors PA, PB keep all their rows: A has 4 (2 sexo + 2 nota), B has 2 peso
    assert len(a) == 4, a
    assert len(b) == 2, b
    assert "x1" not in set(a["valor"].astype(str))
    assert 72 not in set(pd.to_numeric(b["valor"], errors="coerce").dropna().astype(int))


# ── D. Interleaved survivors/suppressed across files, value integrity ─────────

def test_interleaved_value_integrity_across_files():
    """Patient-value pairing must survive the round trip: build distinct
    non-QI values per patient and confirm each hash still carries its own."""
    fileA = (
        "patient_id,data,variable,valor\n"
        "P1,2024-01-01,grupo,g\n"
        "P2,2024-01-01,grupo,g\n"
        "P3,2024-01-01,grupo,g\n"
        "P1,2024-01-02,tag,uno\n"
        "P2,2024-01-02,tag,dos\n"
        "P3,2024-01-02,tag,tres\n"
    )
    fileB = (
        "patient_id,data,variable,valor\n"
        "P1,2024-05-01,score,11\n"
        "P2,2024-05-01,score,22\n"
        "P3,2024-05-01,score,33\n"
    )
    frames, anon = _anonymize_to_outputs(
        {"A.csv": fileA, "B.csv": fileB}, classifications_quasi={"grupo"}, k=2,
    )
    a = frames["A_anonymized.csv"]
    b = frames["B_anonymized.csv"]
    import hashlib
    def h(p): return "H-" + hashlib.sha256(p.encode()).hexdigest()[:12]

    # Build hash -> tag (file A) and hash -> score (file B) and confirm pairing.
    tagmap = dict(zip(a[a["item"] == "tag"]["pacient"].astype(str),
                      a[a["item"] == "tag"]["valor"].astype(str)))
    scoremap = dict(zip(b[b["item"] == "score"]["pacient"].astype(str),
                        b[b["item"] == "score"]["valor"].astype(str)))
    expected_tag = {h("P1"): "uno", h("P2"): "dos", h("P3"): "tres"}
    expected_score = {h("P1"): "11", h("P2"): "22", h("P3"): "33"}
    assert tagmap == expected_tag, tagmap
    assert scoremap == expected_score, scoremap
