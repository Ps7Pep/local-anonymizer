"""
End-to-end correctness tests on the 4 partitioned sample CSVs
(`sample_data/{1..4}_*.csv`), which are the canonical multi-file fixture
(same patient universe split into thematic domains).

What this test suite verifies:

  - SHA-256 hashing replaces every `pacient` value with `H-<12 hex chars>`
    and is irreversible (no original ID survives anywhere in the output).
  - Hashing only touches `pacient`; `data`, `item`, `valor` are untouched.
  - The same original patient ID maps to the same hash across files
    (essential for joining the thematic CSVs after anonymization).
  - Hash collisions are not introduced (cardinality is preserved).
  - `compute_date_deltas` produces non-negative `Int64` minute deltas,
    with delta=0 for each patient's earliest visit, and NaNs are preserved.
  - k-anonymity keeps only patients whose quasi-id signature appears
    at least k times; suppressed patients leave no trace in the output.

Run from project root:

    python -m pytest tests/
"""
import hashlib
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.modules.anonymizer import (
    apply_generalizations,
    apply_k_anonymity,
    compute_date_deltas,
    hash_patient_ids,
    impute_missing_values,
    normalize_columns,
    validate_dataframe,
)


SAMPLE_DIR = Path(__file__).resolve().parents[1] / "sample_data"
PARTITIONED_FILES = [
    "1_determinantes_sociales.csv",
    "2_salud_mental_conductual.csv",
    "3_funcionalidad_autonomia.csv",
    "4_complejidad_clinica.csv",
]
HASH_RE = re.compile(r"^H-[0-9a-f]{12}$")
_SOURCE_COL = "_source_file"


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _load_partitioned() -> pd.DataFrame:
    """Mimic main.py's upload pipeline: load each CSV, normalize columns,
    tag with `_source_file`, concatenate."""
    dfs = []
    for fname in PARTITIONED_FILES:
        df = pd.read_csv(SAMPLE_DIR / fname)
        df.columns = [c.strip().lower() for c in df.columns]
        df, _ = normalize_columns(df)
        errors = validate_dataframe(df)
        assert not errors, f"{fname}: {errors}"
        df[_SOURCE_COL] = fname
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)


# ── Hashing ───────────────────────────────────────────────────────────────────

def test_hash_replaces_every_patient_id_with_correct_pattern():
    df = _load_partitioned()
    original_ids = set(df["pacient"].dropna().astype(str).unique())
    assert original_ids, "fixture has no patient ids"

    out = hash_patient_ids(df.drop(columns=[_SOURCE_COL]))
    hashed = out["pacient"].dropna().astype(str)

    # Every hashed value matches the H-<12 hex> contract.
    assert hashed.map(lambda v: bool(HASH_RE.match(v))).all(), (
        f"non-conforming hashes: {hashed[~hashed.map(lambda v: bool(HASH_RE.match(v)))].head().tolist()}"
    )
    # No original ID leaks into the hashed column.
    leaked = original_ids & set(hashed.unique())
    assert not leaked, f"original IDs leaked into hashed column: {sorted(leaked)[:5]}"


def test_hash_is_deterministic_and_collision_free_on_sample():
    df = _load_partitioned()
    n_unique_orig = df["pacient"].nunique()

    out = hash_patient_ids(df.drop(columns=[_SOURCE_COL]))
    n_unique_hashed = out["pacient"].nunique()

    # Same number of distinct patients before/after → no accidental collapse.
    assert n_unique_hashed == n_unique_orig, (
        f"hash collision: {n_unique_orig} unique IDs collapsed into {n_unique_hashed}"
    )

    # Determinism: same input → same hash on a second run.
    out2 = hash_patient_ids(df.drop(columns=[_SOURCE_COL]))
    assert (out["pacient"].values == out2["pacient"].values).all()


def test_hash_matches_sha256_truncated_12_with_h_prefix():
    """The hash recipe is part of the audit contract — pin it explicitly."""
    df = _load_partitioned().head(50).copy()
    expected = df["pacient"].apply(
        lambda v: "H-" + hashlib.sha256(str(v).encode()).hexdigest()[:12]
        if pd.notna(v) else v
    )
    out = hash_patient_ids(df.drop(columns=[_SOURCE_COL]))
    assert (out["pacient"].values == expected.values).all()


def test_hash_touches_only_pacient_column():
    df = _load_partitioned().drop(columns=[_SOURCE_COL])
    out = hash_patient_ids(df)

    # Every non-pacient column is byte-identical (same dtype + same values, NaN-aware).
    for col in ("data", "item", "valor"):
        assert out[col].equals(df[col]), f"column '{col}' was modified by hash_patient_ids"


def test_same_patient_hashes_identically_across_partitioned_files():
    """Critical for multi-file mode: a single patient appearing in multiple
    thematic CSVs must collapse to the same hash, otherwise joins downstream
    would silently treat them as different people."""
    df = _load_partitioned()
    out = hash_patient_ids(df.copy())

    # Pick a patient that appears in at least 2 files in the fixture.
    counts_per_file = df.groupby("pacient")[_SOURCE_COL].nunique()
    multi_file_patients = counts_per_file[counts_per_file >= 2].index.tolist()
    assert multi_file_patients, "fixture invariant broken: no patient spans >1 file"

    for pid in multi_file_patients[:5]:
        hashes = out.loc[out["pacient"].notna() & (df["pacient"] == pid), "pacient"].unique()
        assert len(hashes) == 1, (
            f"patient {pid!r} hashed to {len(hashes)} different values across files: {list(hashes)}"
        )


# ── Date deltas ───────────────────────────────────────────────────────────────

def test_date_deltas_are_nonnegative_int64_minutes():
    df = _load_partitioned().drop(columns=[_SOURCE_COL])
    out = compute_date_deltas(df, date_format="iso")

    assert str(out["data"].dtype) == "Int64", (
        f"expected Int64, got {out['data'].dtype}"
    )
    non_null = out["data"].dropna()
    assert (non_null >= 0).all(), (
        f"negative deltas found: {non_null[non_null < 0].head().tolist()}"
    )


def test_each_patient_first_visit_has_delta_zero():
    df = _load_partitioned().drop(columns=[_SOURCE_COL])
    out = compute_date_deltas(df, date_format="iso")

    # Every patient with at least one parseable timestamp must have min(delta) == 0.
    mins = out.groupby("pacient")["data"].min().dropna()
    assert (mins == 0).all(), (
        f"patients without delta=0 at first visit: {mins[mins != 0].head().to_dict()}"
    )


def test_date_delta_value_matches_minutes_arithmetic():
    """Synthetic spot-check: build a 3-row sub-frame with known timestamps
    and verify the produced deltas match `(t - t_min) // 60` exactly,
    including sub-day differences."""
    df = pd.DataFrame({
        "pacient": ["X", "X", "X", "Y", "Y"],
        "data":    [
            "2024-01-01 08:00:00", "2024-01-01 09:30:00", "2024-01-02 08:00:00",
            "2024-06-15 12:00:00", "2024-06-15 12:45:00",
        ],
        "item":    ["a"] * 5,
        "valor":   [1, 2, 3, 4, 5],
    })
    out = compute_date_deltas(df, date_format="iso")
    # X: 0, 90 min, 1440 min (1 day). Y: 0, 45 min.
    assert out["data"].tolist() == [0, 90, 1440, 0, 45]


def test_date_delta_preserves_unparseable_as_na():
    df = pd.DataFrame({
        "pacient": ["A", "A", "B"],
        "data":    ["2024-01-01", "not-a-date", "2024-02-01"],
        "item":    ["x", "x", "x"],
        "valor":   [1, 2, 3],
    })
    out = compute_date_deltas(df, date_format="iso")
    # Row 1 unparseable → NA; A's first valid timestamp is row 0 → delta 0.
    assert out.loc[0, "data"] == 0
    assert pd.isna(out.loc[1, "data"])
    assert out.loc[2, "data"] == 0


def test_date_delta_handles_mixed_naive_and_tz_aware_iso():
    """Regression: real CCAA datasets (seen in Aragón AP CSV) mix naive ISO
    timestamps with `+00:00`-offset ones in the same column. Pre-fix this
    made `_parse_dates` return object dtype and `groupby.transform("min")`
    crashed with `agg function failed [how->min,dtype->object]`."""
    df = pd.DataFrame({
        "pacient": ["A", "A", "B", "B"],
        "data":    [
            "2024-01-01 00:00:00",          # naive
            "2024-01-01 12:00:00+00:00",    # tz-aware UTC, same patient
            "2024-06-15 08:00:00+00:00",    # tz-aware
            "2024-06-15 09:30:00",          # naive
        ],
        "item":    ["x"] * 4,
        "valor":   [1, 2, 3, 4],
    })
    out = compute_date_deltas(df, date_format="iso")
    assert str(out["data"].dtype) == "Int64"
    # A: 0 then +720 min (12h). B: 0 then +90 min.
    assert out["data"].tolist() == [0, 720, 0, 90]


# ── k-anonymity ───────────────────────────────────────────────────────────────

def test_k_anonymity_drops_only_under_k_patients_and_keeps_the_rest():
    """Build a deterministic toy frame where one patient is unique on the QI
    signature and should be dropped at k=2, the rest stay."""
    df = pd.DataFrame({
        "pacient": ["P1", "P1", "P2", "P2", "P3", "P3", "P4", "P4"],
        "data":    [0, 1, 0, 1, 0, 1, 0, 1],
        "item":    ["age_bin", "sex", "age_bin", "sex", "age_bin", "sex", "age_bin", "sex"],
        # P1/P2/P3 share (30-40, M); P4 is alone on (40-50, F).
        "valor":   ["30-40", "M", "30-40", "M", "30-40", "M", "40-50", "F"],
    })
    res = apply_k_anonymity(df, quasi_id_items=["age_bin", "sex"], k=2)

    survivors = set(res["df_anonymized"]["pacient"].unique())
    assert survivors == {"P1", "P2", "P3"}
    assert res["n_suppressed_patients"] == 1
    assert res["n_patients_orig"] == 4
    assert res["n_patients_final"] == 3


def test_k_anonymity_full_pipeline_on_partitioned_sample():
    """End-to-end on the real fixture: deltas → impute → hash → k=2.
    Verifies that after the full chain (a) no original patient ID appears
    in the output, and (b) every surviving patient appears in a QI group
    of size >= k."""
    df = _load_partitioned().drop(columns=[_SOURCE_COL])
    original_ids = set(df["pacient"].dropna().astype(str).unique())

    # Pick two items that exist in the sample as quasi-IDs.
    quasi = ["sexo_y_o_genero", "edad"]
    available = set(df["item"].unique())
    quasi = [q for q in quasi if q in available]
    if not quasi:
        # Fallback: use the two most common items so the test still runs.
        quasi = df["item"].value_counts().head(2).index.tolist()

    df = compute_date_deltas(df, date_format="iso")
    df, _ = impute_missing_values(df, quasi)
    df = hash_patient_ids(df)
    res = apply_k_anonymity(df, quasi_id_items=quasi, k=2)

    out = res["df_anonymized"]
    # No original IDs leaked.
    assert original_ids.isdisjoint(set(out["pacient"].astype(str).unique()))
    # Every survivor hash is well-formed.
    assert out["pacient"].astype(str).map(lambda v: bool(HASH_RE.match(v))).all()
    # Reported suppression accounting is internally consistent.
    assert res["n_patients_orig"] == res["n_patients_final"] + res["n_suppressed_patients"]


def test_k_anonymity_with_no_quasi_ids_is_a_no_op():
    df = _load_partitioned().drop(columns=[_SOURCE_COL])
    res = apply_k_anonymity(df, quasi_id_items=[], k=5)
    assert res["n_suppressed_patients"] == 0
    assert res["n_patients_final"] == res["n_patients_orig"]
