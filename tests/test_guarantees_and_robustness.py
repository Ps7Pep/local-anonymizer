"""
Regression tests for the 2026-10-21 audit backlog (CLAUDE.md §14).

  B1  keyed patient hash: the key never leaves the process
  B2  no external network calls from the HTML report
  B3  imputation runs before generalization; nothing falls out of bins silently
  B4  k-anonymity over the full longitudinal QI signature
  B6  CSV-derived values cannot inject HTML into the report
  B7  no CORS headers
  B8  sessions expire
  +   duplicate filenames, non-ASCII download names, server-side validation
      of generalizations, stale generalizations of de-classified items

Run:  python -m pytest tests/test_guarantees_and_robustness.py -v
"""
import io
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
import app.main as main
from app.main import app, sessions
from app.modules.anonymizer import (
    apply_generalizations, apply_k_anonymity, impute_missing_values,
    OUT_OF_RANGE_LABEL, UNKNOWN_LABEL,
)
from app.modules.report_html import generate_html_report
from app.modules.report_md import generate_markdown_report

client = TestClient(app)


def _upload(csvs: dict[str, str]):
    files = [("files", (name, io.BytesIO(body.encode("utf-8")), "text/csv"))
             for name, body in csvs.items()]
    return client.post("/api/upload", files=files)


def _session_with(csv_body: str, quasi: set, generalizations: dict | None = None,
                  filename: str = "d.csv"):
    r = _upload({filename: csv_body})
    assert r.status_code == 200, r.text
    up = r.json()
    sid = up["session_id"]
    cls = {it["name"]: ("quasi_id" if it["name"] in quasi else "non_id") for it in up["items"]}
    assert client.post("/api/classify", json={"session_id": sid, "classifications": cls}).status_code == 200
    if generalizations is not None:
        r = client.post("/api/set-generalizations",
                        json={"session_id": sid, "generalizations": generalizations})
        assert r.status_code == 200, r.text
    return sid


# ── B3: imputation before generalization ─────────────────────────────────────

def test_numeric_nan_gets_median_bin_not_desconocido():
    df = pd.DataFrame({
        "pacient": ["A", "B", "C", "D"],
        "data":    [0, 0, 0, 0],
        "item":    ["edad"] * 4,
        "valor":   ["30", "35", np.nan, "38"],
    })
    df, imp = impute_missing_values(df, ["edad"])
    assert imp["edad"]["is_numeric"] and imp["edad"]["n_imputed"] == 1
    out, glog = apply_generalizations(df, {"edad": {"type": "bins", "bins": [0, 40, 120], "labels": ["<40", "40+"]}})
    assert out["valor"].tolist() == ["<40"] * 4
    assert glog["edad"] == {"type": "bins", "n_non_numeric": 0, "n_out_of_range": 0}


def test_numeric_item_with_many_nan_is_still_imputed_with_median():
    """Pre-fix the 80 % numeric threshold counted NaN rows in the denominator,
    so a numeric QI with > 20 % missing was treated as categorical."""
    vals = ["50", "60", "70", np.nan, np.nan, np.nan]
    df = pd.DataFrame({"pacient": list("ABCDEF"), "data": [0] * 6, "item": ["peso"] * 6, "valor": vals})
    out, imp = impute_missing_values(df, ["peso"])
    assert imp["peso"]["is_numeric"] is True
    assert out["valor"].tolist() == ["50", "60", "70", "60", "60", "60"]


def test_out_of_range_and_non_numeric_are_labelled_and_counted():
    df = pd.DataFrame({
        "pacient": list("ABCD"), "data": [0] * 4, "item": ["edad"] * 4,
        "valor":   ["10", "130", "abc", "50"],
    })
    out, glog = apply_generalizations(df, {"edad": {"type": "bins", "bins": [0, 18, 120], "labels": ["menor", "adulto"]}})
    assert out["valor"].tolist() == ["menor", OUT_OF_RANGE_LABEL, UNKNOWN_LABEL, "adulto"]
    assert glog["edad"]["n_out_of_range"] == 1
    assert glog["edad"]["n_non_numeric"] == 1


def test_mapping_keeps_desconocido_and_counts_unmapped():
    df = pd.DataFrame({
        "pacient": list("ABCD"), "data": [0] * 4, "item": ["origen"] * 4,
        "valor":   ["es", np.nan, "fr", "zz"],
    })
    df, _ = impute_missing_values(df, ["origen"])
    out, glog = apply_generalizations(df, {"origen": {
        "type": "mapping", "mapping": {"es": "UE", "fr": "UE"}, "unmapped_label": "Otros"}})
    assert out["valor"].tolist() == ["UE", UNKNOWN_LABEL, "UE", "Otros"]
    assert glog["origen"]["n_unmapped"] == 1


def test_duplicate_bin_labels_are_allowed():
    df = pd.DataFrame({"pacient": list("AB"), "data": [0, 0], "item": ["x", "x"], "valor": ["1", "5"]})
    out, _ = apply_generalizations(df, {"x": {"type": "bins", "bins": [0, 2, 4, 10], "labels": ["a", "b", "a"]}})
    assert out["valor"].tolist() == ["a", "a"]


# ── B4: longitudinal QI signature ─────────────────────────────────────────────

def test_k_anonymity_uses_every_value_of_a_longitudinal_qi():
    """P1..P3 always 'M'. P4 is 'M' at the first visit and 'F' later: with
    `.first()` P4 looked identical to P1..P3 and survived k=2 while its 'F'
    row was released. Its real signature {F, M} is unique → suppressed."""
    df = pd.DataFrame({
        "pacient": ["P1", "P2", "P3", "P4", "P4"],
        "data":    [0, 0, 0, 0, 100],
        "item":    ["sexo"] * 5,
        "valor":   ["M", "M", "M", "M", "F"],
    })
    res = apply_k_anonymity(df, ["sexo"], k=2)
    assert set(res["df_anonymized"]["pacient"]) == {"P1", "P2", "P3"}
    assert res["n_suppressed_patients"] == 1
    assert res["suppressed_groups"][0]["sexo"] == "F | M"


def test_k_anonymity_groups_identical_longitudinal_signatures():
    df = pd.DataFrame({
        "pacient": ["P1", "P1", "P2", "P2"],
        "data":    [0, 100, 50, 0],             # order of visits differs
        "item":    ["edad"] * 4,
        "valor":   ["60-64", "65+", "65+", "60-64"],
    })
    res = apply_k_anonymity(df, ["edad"], k=2)
    assert res["n_suppressed_patients"] == 0


def test_k_anonymity_with_quasi_id_absent_from_data():
    df = pd.DataFrame({"pacient": ["A", "B"], "data": [0, 0], "item": ["x", "x"], "valor": ["1", "2"]})
    res = apply_k_anonymity(df, ["no_existe"], k=2)
    assert res["n_patients_final"] == 2      # everyone shares the all-"NaN" signature


# ── B1 / end-to-end through the API ───────────────────────────────────────────

CSV_SMALL = (
    "patient_id,fecha,variable,valor\n"
    "P1,2024-01-01,edad,30\nP2,2024-01-01,edad,35\nP3,2024-01-01,edad,\nP4,2024-01-01,edad,150\n"
    "P1,2024-01-01,sexo,M\nP2,2024-01-01,sexo,M\nP3,2024-01-01,sexo,M\nP4,2024-01-01,sexo,M\n"
)


def test_hash_key_never_leaves_the_server():
    sid = _session_with(CSV_SMALL, {"edad", "sexo"},
                        {"edad": {"type": "bins", "bins": [0, 40, 120], "labels": ["<40", "40+"]},
                         "sexo": {"type": "mapping", "mapping": {"M": "M"}, "unmapped_label": "Otros"}})
    key_hex = sessions[sid]["hash_key"].hex()
    r = client.post("/api/anonymize", json={"session_id": sid, "k": 2, "lang": "es"})
    assert r.status_code == 200, r.text
    bodies = [r.text] + [client.get(p + sid).text for p in (
        "/api/download/report/", "/api/download/report/html/", "/api/download/report/md/", "/api/download/csv/")]
    assert all(key_hex not in b for b in bodies)
    report = json.loads(bodies[1])
    assert "HMAC" in report["patient_hash"]
    # B3 through the API: P3's missing age → median (35) → "<40"; P4 (150) → out of range
    assert report["imputation_log"]["edad"]["strategy"] == "mediana (35)"
    assert report["generalization_log"]["edad"]["n_out_of_range"] == 1
    sessions.pop(sid, None)


def test_stale_generalization_of_declassified_item_is_ignored():
    sid = _session_with(CSV_SMALL, {"sexo"},
                        {"edad": {"type": "bins", "bins": [0, 40, 200], "labels": ["<40", "40+"]},
                         "sexo": {"type": "mapping", "mapping": {"M": "M"}, "unmapped_label": "Otros"}})
    assert client.post("/api/anonymize", json={"session_id": sid, "k": 2, "lang": "es"}).status_code == 200
    out = pd.read_csv(io.BytesIO(client.get(f"/api/download/csv/{sid}").content))
    # edad is non_id now → published unchanged, not binned
    assert set(out.loc[out["item"] == "edad", "valor"].dropna().astype(int)) == {30, 35, 150}
    sessions.pop(sid, None)


def test_invalid_generalizations_are_rejected_with_400():
    sid = _session_with(CSV_SMALL, {"edad"})
    for bad in (
        {"edad": {"type": "bins", "bins": [0, 40, 30], "labels": ["a", "b"]}},
        {"edad": {"type": "bins", "bins": [0, 40], "labels": ["a", "b"]}},
        {"edad": {"type": "bins", "bins": ["x", 40], "labels": ["a"]}},
        {"edad": {"type": "nope"}},
    ):
        r = client.post("/api/set-generalizations", json={"session_id": sid, "generalizations": bad})
        assert r.status_code == 400, (bad, r.text)
    sessions.pop(sid, None)


# ── B6 / B2: report safety ────────────────────────────────────────────────────

def test_report_escapes_csv_values_and_makes_no_external_calls():
    payload = '<img src=x onerror=alert(1)>'
    md = generate_markdown_report(
        lang="es", filename=f"{payload}.csv",
        col_mappings={f"{payload}.csv": {"pacient": "p`id", "data": "d", "item": "i", "valor": "v"}},
        classifications={payload: "quasi_id", "x|y": "non_id"},
        generalizations={payload: {"type": "mapping", "mapping": {"`a`<b>": payload}, "unmapped_label": "<i>u</i>"}},
        imputation_log={}, generalization_log={},
        metrics={"k_used": 2, "quasi_id_items": [payload],
                 "suppressed_groups": [{payload: f"{payload} | <script>x</script>", "_count_": 1}]},
        date_range={"min": "2024-01-01", "max": "2024-02-01"},
        all_items=[payload, "x|y"], version="test",
    )
    html = generate_html_report(md, title="t", filename=f"{payload}.csv",
                                generated_at="now", tool="tool", lang="es")
    assert "<img" not in html and "<script" not in html and "<i>u" not in html
    assert "&lt;img" in html
    assert "googleapis" not in html and "@import" not in html and 'lang="es"' in html


def test_report_falls_back_to_spanish_for_unknown_lang():
    md = generate_markdown_report(
        lang="xx", filename="f.csv", col_mappings={}, classifications={}, generalizations={},
        imputation_log={}, metrics={"k_used": 2}, date_range={}, all_items=[],
    )
    assert md.startswith("# Informe de Anonimización")


# ── B7 / B8 / misc API robustness ─────────────────────────────────────────────

def test_no_cors_headers():
    r = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert r.status_code == 200
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}


def test_expired_sessions_are_purged():
    sid = _session_with(CSV_SMALL, {"sexo"})
    sessions[sid]["_last_access"] -= main.SESSION_TTL_SECONDS + 1
    r = client.post("/api/simulate-k", json={"session_id": sid})
    assert r.status_code == 404
    assert sid not in sessions


def test_pending_mapping_session_cannot_be_used_before_confirmation():
    r = _upload({"a.csv": "a,b,c,d\nP1,2024-01-01,x,1\n"})
    up = r.json()
    assert up["status"] == "needs_mapping"
    r = client.post("/api/classify", json={"session_id": up["session_id"], "classifications": {}})
    assert r.status_code == 409
    sessions.pop(up["session_id"], None)


def test_duplicate_filenames_are_rejected():
    files = [("files", ("dir1/x.csv", io.BytesIO(CSV_SMALL.encode()), "text/csv")),
             ("files", ("x.csv", io.BytesIO(CSV_SMALL.encode()), "text/csv"))]
    r = client.post("/api/upload", files=files)
    assert r.status_code == 400 and "x.csv" in r.json()["detail"]


def test_non_ascii_filename_download_and_report_mapping_per_file():
    sid = _session_with(CSV_SMALL, {"sexo"}, filename="càrrega «ñ».CSV")
    assert client.post("/api/anonymize", json={"session_id": sid, "k": 2, "lang": "ca"}).status_code == 200
    r = client.get(f"/api/download/csv/{sid}")
    assert r.status_code == 200
    cd = r.headers["content-disposition"]
    assert "filename*=UTF-8''c%C3%A0rrega" in cd and cd.endswith("_anonymized.csv")
    md = client.get(f"/api/download/report/md/{sid}").text
    assert "`patient_id`" in md and "`fecha`" in md
    sessions.pop(sid, None)
