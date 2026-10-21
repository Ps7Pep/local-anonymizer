"""
Regression tests: phase-1 upload used to crash with

    TypeError: '<' not supported between instances of 'float' and 'str'

when the input CSV had mixed-type identifier columns (NaN + strings, ints +
strings, etc.). The fix coerces `pacient` and `item` to str (preserving NaN)
in `normalize_columns`, and adds defensive coercion inside `profile_items`,
`compute_date_deltas` and `apply_k_anonymity`.

Run from the project root:

    python -m pytest tests/
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Allow `python -m pytest tests/` to find the `app` package without install.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.modules.anonymizer import (
    apply_k_anonymity,
    apply_user_mapping,
    compute_date_deltas,
    normalize_columns,
    profile_items,
    propose_mapping,
)


def _mixed_df() -> pd.DataFrame:
    """Long-format dataset with deliberately mixed types in identifier columns."""
    return pd.DataFrame({
        "pacient": ["P1", "P1", "P2", "P2", "P3", "P3", 404, 404],
        "data":    ["2020-01-01", "2020-01-02", "2020-01-01", "2020-01-03",
                    "2020-01-04", "2020-01-05", "2020-01-06", "2020-01-07"],
        "item":    ["age", "sex", "age", 7, "age", np.nan, "age", "sex"],
        "valor":   [30, "M", 45, "high", "desconocido", "X", 50, "M"],
    })


def test_normalize_columns_coerces_identifiers_preserving_nan():
    df, _ = normalize_columns(_mixed_df())
    assert all(isinstance(v, str) for v in df["pacient"].dropna())
    assert all(isinstance(v, str) for v in df["item"].dropna())
    # NaN survives the cast (not stringified to "nan").
    assert df["item"].isna().sum() == 1


def test_profile_items_handles_mixed_item_dtypes():
    """Original repro: `sorted(df['item'].unique())` raised on str+int+NaN."""
    df, _ = normalize_columns(_mixed_df())
    profiles = profile_items(df)
    names = {p["name"] for p in profiles}
    assert {"age", "sex", "7"}.issubset(names)


def test_profile_items_robust_without_normalize_columns():
    """Defense in depth: the function must also be safe if called directly."""
    profile_items(_mixed_df())


def test_compute_date_deltas_handles_mixed_pacient_groupby():
    """`groupby('pacient')` on str+int used to fail under pandas 2.x."""
    df, _ = normalize_columns(_mixed_df())
    out = compute_date_deltas(df, date_format="iso")
    assert str(out["data"].dtype) == "Int64"


def test_apply_k_anonymity_handles_mixed_types_end_to_end():
    df, _ = normalize_columns(_mixed_df())
    df = compute_date_deltas(df, date_format="iso")
    out = apply_k_anonymity(df, quasi_id_items=["age", "sex"], k=2)
    assert out["k_used"] == 2
    assert out["n_patients_orig"] >= out["n_patients_final"]


# ──────────────────────────────────────────────────────────────────────────────
# Column-mapping proposal — handles CSVs whose columns don't match any alias.
# ──────────────────────────────────────────────────────────────────────────────

def test_propose_mapping_all_aliases_match():
    mapping, complete = propose_mapping(["patient_id", "fecha", "variable", "value"])
    assert complete is True
    assert mapping == {
        "pacient": "patient_id",
        "data":    "fecha",
        "item":    "variable",
        "valor":   "value",
    }


def test_propose_mapping_partial_alias_falls_back_to_position():
    # 'fecha' is an alias; the other 3 names are unknown, so positional fallback
    # fills pacient → 1st unmatched, item → 2nd, valor → 3rd, in column order.
    mapping, complete = propose_mapping(["nº historia", "fecha", "campo medido", "resultado obtenido"])
    assert complete is False
    assert mapping == {
        "pacient": "nº historia",
        "data":    "fecha",
        "item":    "campo medido",
        "valor":   "resultado obtenido",
    }


def test_propose_mapping_no_alias_match_uses_pure_position():
    mapping, complete = propose_mapping(["a", "b", "c", "d"])
    assert complete is False
    assert mapping == {"pacient": "a", "data": "b", "item": "c", "valor": "d"}


def test_apply_user_mapping_renames_and_coerces():
    df = pd.DataFrame({
        "Edad": [30, 45, 60],
        "Cuando": ["2020-01-01", "2020-02-01", "2020-03-01"],
        "Que": ["x", "y", "z"],
        "Cuanto": [1, 2, 3],
    })
    df2 = apply_user_mapping(df, {
        "pacient": "Edad",
        "data":    "Cuando",
        "item":    "Que",
        "valor":   "Cuanto",
    })
    assert set(df2.columns) == {"pacient", "data", "item", "valor"}
    # pacient was coerced to str
    assert all(isinstance(v, str) for v in df2["pacient"].dropna())


def test_profile_items_mixed_valor_does_not_crash():
    """Mixed `valor` (numbers + strings like 'desconocido') must not break profiling."""
    df, _ = normalize_columns(pd.DataFrame({
        "pacient": ["P1", "P2", "P3", "P4", "P5"],
        "data":    ["2020-01-01"] * 5,
        "item":    ["age"] * 5,
        "valor":   [30, 45, "desconocido", np.nan, 60],
    }))
    profiles = profile_items(df)
    age = next(p for p in profiles if p["name"] == "age")
    # `_is_numeric` requires >80% parseable; 3/5 = 60%, so it falls to categorical.
    assert age["type"] in {"numeric", "categorical"}
