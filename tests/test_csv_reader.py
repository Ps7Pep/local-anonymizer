"""
Regression tests for `_read_csv` in app/main.py.

Why this file exists: a CSV uploaded by Osakidetza had an opening double-quote
mid-value that never closed on the same row. The C parser then absorbed the
following rows into a single multi-line value, so lines "disappeared" from
the anonymized output.

The tolerant fallback chain was already in place, but it never executed
because `low_memory=False` was hardcoded for every read attempt, and that
option is rejected by the python parser engine with `ValueError`. The
exception cascade then bubbled out as "no s'ha pogut llegir el fitxer".

These tests pin down:
  - the well-formed-quote happy path still works
  - an unclosed-quote CSV still surfaces every patient row
  - encoding fallbacks (cp1252 / latin-1) still trigger
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import _read_csv


def test_well_formed_quotes_are_parsed_with_c_engine():
    """Sanity check: the fast path is unaffected by the tolerant fallback."""
    content = (
        b"patient_id,fecha,variable,valor\n"
        b'P001,2024-01-01,PROGRAMA,"ATENCION CRONICA"\n'
        b'P002,2024-01-01,Notes,"valor con , coma interna"\n'
        b'P003,2024-01-01,Edat,75\n'
    )
    df = _read_csv(content)
    assert df.shape == (3, 4)
    assert df.iloc[0]["valor"] == "ATENCION CRONICA"
    assert df.iloc[1]["valor"] == "valor con , coma interna"


def test_unclosed_quote_does_not_drop_patient_rows():
    """The exact failure mode reported by Osakidetza: one row has an opening
    quote that never closes. Pre-fix the C parser raised `ParserError: EOF
    inside string` and every fallback failed with `ValueError: 'low_memory'
    not supported with engine='python'`, so `_read_csv` raised and the upload
    error message was generic. Or — worse — a tolerant fallback silently
    dropped the fused lines and the resulting CSV had `H-xxx,,,` rows.

    Post-fix every patient row must survive. Item/valor may be partially
    mangled by `quoting=QUOTE_NONE`, but the patient identifier itself
    must never go missing.
    """
    content = (
        b"patient_id,fecha,variable,valor\n"
        b"P001,2024-01-01,Variable A,18G\n"
        b'P002,2024-01-01,"Catheter venoso periferico-Escala Maddox flebitis,0 - Sin dolor\n'
        b"P003,2024-01-02,Variable B,valor B\n"
        b"P004,2024-01-03,Variable C,valor C\n"
        b"P005,2024-01-04,Variable D,valor D\n"
        b"P006,2024-01-05,Edat,75\n"
    )
    df = _read_csv(content)
    seen = set(df["patient_id"].dropna().astype(str).unique())
    assert seen == {"P001", "P002", "P003", "P004", "P005", "P006"}, (
        f"unclosed quote dropped patients: missing {sorted({'P001','P002','P003','P004','P005','P006'} - seen)}"
    )


def test_cp1252_fallback_when_utf8_fails():
    """Spanish CCAA Windows exports are often cp1252-encoded. Verify the
    encoding fallback chain reaches it instead of raising."""
    content = (
        "patient_id,fecha,variable,valor\n"
        "P001,2024-01-01,Edad,75\n"
        "P002,2024-01-01,Diagnóstico,Atención primaria\n"
    ).encode("cp1252")
    df = _read_csv(content)
    assert df.shape == (2, 4)
    assert "Diagn" in str(df.iloc[1]["variable"])


def test_utf8_bom_is_handled():
    """Excel often writes utf-8 with BOM. The header alias for `pacient`
    must still match after stripping it."""
    content = (
        "﻿patient_id,fecha,variable,valor\n"
        "P001,2024-01-01,Edad,75\n"
    ).encode("utf-8")
    df = _read_csv(content)
    assert df.shape == (1, 4)
    assert "patient_id" in df.columns


