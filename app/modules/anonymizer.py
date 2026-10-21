"""
anonymizer.py
-------------
Nucli de la lògica d'anonimització:
  - Normalització i validació del CSV d'entrada (4 columnes)
  - Perfilat d'ítems (detecció numèric vs categòric)
  - Detecció i parsing del format de timestamp (ISO / dayfirst / monthfirst)
  - Transformació de dates → delta enter de minuts per pacient
  - Hash SHA-256 irreversible de l'identificador de pacient
  - Imputació de NaN als quasi-identificadors
  - Generalitzacions (bins numèrics / mapeig categòric)
  - K-anonimitat per supressió
  - Càlcul de mètriques comparatives
"""

import hashlib
import re
import pandas as pd
import numpy as np

# ── Àlies de columnes acceptades ─────────────────────────────────────────────
COL_ALIASES = {
    "pacient": {"pacient", "patient", "patient_id", "pacient_id", "nhc", "pid", "id", "id_pacient"},
    "data":    {"data", "date", "fecha", "datetime", "timestamp", "dt"},
    "item":    {"item", "variable", "var", "camp", "field", "measure"},
    "valor":   {"valor", "value", "val", "resultat", "result"},
}

_NULL_STRINGS = {"", "nan", "NaN", "None"}


def _coerce_str(series: pd.Series) -> pd.Series:
    """Casteja a str preservant NaN.

    Necessari als identificadors textuals (`pacient`, `item`): sense això,
    operacions com `sorted(series.unique())`, `groupby(...)` o `unstack()`
    fallen amb `TypeError: '<' not supported between instances of 'float'
    and 'str'` quan la columna barreja tipus (NaN+str, int+str, ...).
    """
    return series.where(series.isna(), series.astype(str))

# ── Detecció i parsing de format de timestamp ────────────────────────────────
DATE_FORMATS = ("iso", "dayfirst", "monthfirst")

_DATE_FORMAT_LABELS = {
    "iso":        "ISO 8601 (YYYY-MM-DD [HH:MM[:SS]])",
    "dayfirst":   "Day first (DD/MM/YYYY [HH:MM[:SS]])",
    "monthfirst": "Month first (MM/DD/YYYY [HH:MM[:SS]])",
}


# Patró ISO 8601 al començament (YYYY-MM-DD…). Necessari per rebutjar inputs
# clarament ISO quan l'usuari ha escollit dayfirst/monthfirst: pandas els parsejaria
# silenciosament i la selecció de l'usuari quedaria sense efecte.
_ISO_LIKE_RE = re.compile(r"^\s*\d{4}-\d{1,2}-\d{1,2}")


def _parse_dates(series: pd.Series, fmt: str) -> pd.Series:
    """Parseja una sèrie segons el format escollit. Sempre retorna datetime64[ns, UTC].

    `utc=True` és imprescindible: si la columna barreja timestamps naive i
    tz-aware (cas real vist a CCAA: `2024-10-02 00:00:00` + `2024-09-16
    19:08:17+00:00` en el mateix CSV), `utc=False` força un dtype `object`
    amb datetimes Python mixtos i `groupby.transform("min")` peta amb
    `agg function failed [how->min,dtype->object]`. Naive → s'assumeix UTC;
    no afecta la utilitat perquè el pipeline només usa deltes per pacient.
    """
    if fmt == "iso":
        # format="ISO8601" (pandas ≥ 2.0) — accepta data sola, data+hora, micros, zona horària
        return pd.to_datetime(series, format="ISO8601", errors="coerce", utc=True)
    if fmt in ("dayfirst", "monthfirst"):
        parsed = pd.to_datetime(series, dayfirst=(fmt == "dayfirst"), errors="coerce", utc=True)
        iso_mask = series.astype(str).str.match(_ISO_LIKE_RE).fillna(False)
        return parsed.mask(iso_mask)
    # fallback: parsing per defecte de pandas
    return pd.to_datetime(series, errors="coerce", utc=True)


def detect_date_format(series: pd.Series) -> dict:
    """
    Prova ISO, dayfirst i monthfirst sobre la columna 'data'.
    Retorna estadístiques per cadascun (n_failed, has_time) i el millor candidat.

    Empats es resolen preferint ISO (etiqueta més clara) i després dayfirst
    (format clínic europeu més habitual).
    """
    s = series.copy()
    non_null_mask = s.notna() & ~s.astype(str).str.strip().isin(_NULL_STRINGS)
    n_total = int(non_null_mask.sum())

    candidates: dict[str, dict] = {}
    for fmt in DATE_FORMATS:
        parsed = _parse_dates(s, fmt)
        n_failed = int((non_null_mask & parsed.isna()).sum())
        try:
            has_time = bool(
                (
                    (parsed.dt.hour != 0)
                    | (parsed.dt.minute != 0)
                    | (parsed.dt.second != 0)
                ).any()
            )
        except Exception:
            has_time = False
        candidates[fmt] = {
            "n_parsed": n_total - n_failed,
            "n_failed": n_failed,
            "has_time": has_time,
            "label":    _DATE_FORMAT_LABELS[fmt],
        }

    zero_fail = [f for f in DATE_FORMATS if candidates[f]["n_failed"] == 0]
    if zero_fail:
        for preferred in ("iso", "dayfirst", "monthfirst"):
            if preferred in zero_fail:
                best = preferred
                break
    else:
        priority = {"dayfirst": 0, "iso": 1, "monthfirst": 2}
        best = min(DATE_FORMATS, key=lambda f: (candidates[f]["n_failed"], priority[f]))

    # Mostres: 5 primers valors no nuls amb el seu parsing segons el millor candidat
    parsed_best = _parse_dates(s, best)
    sample_idx = s[non_null_mask].index[:5]
    samples = []
    for i in sample_idx:
        raw = str(s.loc[i])
        out = parsed_best.loc[i]
        samples.append({
            "raw":    raw,
            "parsed": "" if pd.isna(out) else out.strftime("%Y-%m-%d %H:%M:%S"),
            "ok":     bool(pd.notna(out)),
        })

    return {
        "best":       best,
        "n_total":    n_total,
        "candidates": candidates,
        "samples":    samples,
    }


# ── Normalització i validació ─────────────────────────────────────────────────

def _alias_match(raw_columns: list[str]) -> dict[str, str]:
    """Retorna {raw_col: canonical} pels noms que coincideixin amb algun àlies.

    Reservat: cada raw_col es mapeja com a màxim una vegada, i cada canonical
    com a màxim una vegada (la primera columna que el reclama guanya).
    """
    rename_map: dict[str, str] = {}
    cols_lower = {c: c.strip().lower() for c in raw_columns}
    for canonical, aliases in COL_ALIASES.items():
        for orig_col, lower_col in cols_lower.items():
            if (
                lower_col in aliases
                and canonical not in rename_map.values()
                and orig_col not in rename_map
            ):
                rename_map[orig_col] = canonical
                break
    return rename_map


def propose_mapping(raw_columns: list[str]) -> tuple[dict[str, str | None], bool]:
    """Proposa un mapatge {canonical: raw_col} en dues passades:

      1. Coincidència per àlies (case-insensitive sobre el nom de la columna).
      2. Fallback posicional: per als canonicals que el pas 1 no ha cobert,
         assigna en ordre (pacient → data → item → valor) les columnes raw
         que encara no s'han consumit.

    Retorna `(mapping, alias_complete)`. Si `alias_complete` és True, el pas 1
    ja ha cobert els 4 canonicals i el frontend pot continuar sense demanar
    confirmació; si és False, cal ensenyar la proposta a l'usuari perquè la
    validi o la corregeixi.
    """
    alias_match = _alias_match(raw_columns)
    mapping: dict[str, str | None] = {c: None for c in ("pacient", "data", "item", "valor")}
    for raw, canon in alias_match.items():
        mapping[canon] = raw
    alias_complete = all(v is not None for v in mapping.values())

    if not alias_complete:
        used = set(alias_match.keys())
        unmatched = [c for c in raw_columns if c not in used]
        for canonical in ("pacient", "data", "item", "valor"):
            if mapping[canonical] is None and unmatched:
                mapping[canonical] = unmatched.pop(0)

    return mapping, alias_complete


def apply_user_mapping(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    """Renombra columnes segons un mapatge explícit `{canonical: raw_col}` i
    castia `pacient`/`item` a str preservant NaN. El mapatge ha d'estar
    validat (4 canonicals coberts, sense duplicats) abans de cridar.
    """
    rename = {raw: canon for canon, raw in mapping.items() if raw}
    df = df.rename(columns=rename)
    for col in ("pacient", "item"):
        if col in df.columns:
            df[col] = _coerce_str(df[col])
    return df


def normalize_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Renombra les columnes als noms canònics només per àlies i estabilitza
    els tipus identificadors. Sense fallback posicional — això es decideix a
    `propose_mapping`, i si cal confirmació passa per `apply_user_mapping`.

    A més del rename, casteja `pacient` i `item` a str (preservant NaN) perquè
    qualsevol sort/groupby/unstack downstream no peti si la columna barreja
    tipus (NaN+str, int+str). `valor` no es toca: pot legítimament barrejar
    numèrics i categòrics i ja s'estringa puntualment on cal.
    """
    rename_map = _alias_match(list(df.columns))
    if rename_map:
        df = df.rename(columns=rename_map)
    for col in ("pacient", "item"):
        if col in df.columns:
            df[col] = _coerce_str(df[col])
    return df, rename_map


def validate_dataframe(df: pd.DataFrame) -> list[str]:
    """Retorna una llista d'errors de validació (buida si tot és correcte)."""
    errors = []
    missing = {"pacient", "data", "item", "valor"} - set(df.columns)
    if missing:
        errors.append(
            f"Columnes no reconegudes: {', '.join(sorted(missing))}. "
            "Cal tenir: pacient/patient_id, data/date, item/variable, valor/value."
        )
    if df.empty:
        errors.append("El fitxer és buit.")
    return errors


# ── Perfilat d'ítems ──────────────────────────────────────────────────────────

def _is_numeric(series: pd.Series) -> bool:
    non_null = series.dropna().astype(str)
    if len(non_null) == 0:
        return False
    return (pd.to_numeric(non_null, errors="coerce").notna().sum() / len(non_null)) > 0.8


def profile_items(df: pd.DataFrame) -> list[dict]:
    """Retorna el perfil estadístic de cada ítem únic del dataset."""
    profiles = []
    item_str = _coerce_str(df["item"])
    for item_name in sorted(item_str.dropna().unique()):
        subset  = df.loc[item_str == item_name, "valor"]
        is_num  = _is_numeric(subset)
        profile = {
            "name":      item_name,
            "type":      "numeric" if is_num else "categorical",
            "n_records": int(len(subset)),
            "n_unique":  int(subset.nunique()),
        }
        if is_num:
            num = pd.to_numeric(subset, errors="coerce").dropna()
            profile["stats"] = {
                "min":    _safe_num(num.min()),
                "max":    _safe_num(num.max()),
                "mean":   _safe_num(num.mean()),
                "median": _safe_num(num.median()),
                "std":    _safe_num(num.std()),
            }
            try:
                counts, edges = np.histogram(num, bins=min(10, profile["n_unique"]))
                profile["histogram"] = {
                    "counts": counts.tolist(),
                    "edges":  [round(float(e), 2) for e in edges],
                }
            except Exception:
                pass
        else:
            vc = subset.value_counts()
            profile["values"]       = sorted(str(v) for v in subset.dropna().unique())
            profile["value_counts"] = {str(k): int(v) for k, v in vc.items()}
        profiles.append(profile)
    return profiles


# ── Transformació de dates ────────────────────────────────────────────────────

def compute_date_deltas(df: pd.DataFrame, date_format: str = "iso") -> pd.DataFrame:
    """
    Converteix 'data' a minuts enters transcorreguts des de la primera visita
    de cada pacient.

    Si el timestamp original no porta hora (només data), el delta serà múltiple
    de 1440 (minuts/dia). Si porta hora/minuts, es preserva la granularitat fina,
    cosa que permet ordenar correctament visites del mateix dia.

    Files amb timestamp no parsejable es queden com a <NA>.
    """
    df     = df.copy()
    df["pacient"] = _coerce_str(df["pacient"])
    parsed = _parse_dates(df["data"], date_format)
    ref    = parsed.groupby(df["pacient"]).transform("min")
    delta  = (parsed - ref).dt.total_seconds()
    df["data"] = delta.div(60).round().astype("Int64")
    return df


# ── Hash de pacient ───────────────────────────────────────────────────────────

def hash_patient_ids(df: pd.DataFrame) -> pd.DataFrame:
    """Substitueix 'pacient' pel hash SHA-256 truncat irreversible (prefix H-)."""
    df = df.copy()
    df["pacient"] = df["pacient"].apply(
        lambda v: "H-" + hashlib.sha256(str(v).encode()).hexdigest()[:12]
        if pd.notna(v) else v
    )
    return df


# ── Imputació de valors absents ───────────────────────────────────────────────

def impute_missing_values(df: pd.DataFrame, quasi_id_items: list[str]) -> tuple[pd.DataFrame, dict]:
    """
    Imputa NaN als quasi-identificadors per evitar supressió innecessària:
      - Categòrics → "Desconocido"
      - Numèrics   → mediana observada

    Retorna (df_imputat, log).
    """
    df  = df.copy()
    log = {}

    for item_name in quasi_id_items:
        mask = df["item"] == item_name
        if not mask.any():
            continue

        vals      = df.loc[mask, "valor"]
        null_mask = mask & (vals.isna() | vals.astype(str).str.strip().isin(_NULL_STRINGS))
        n_null    = int(null_mask.sum())

        if n_null == 0:
            continue

        num_vals = pd.to_numeric(vals, errors="coerce")
        is_num   = bool((num_vals.notna().sum() / len(vals)) > 0.8)

        if is_num:
            median_val = num_vals.median()
            fill_val   = (str(int(median_val))
                          if num_vals.dropna().apply(lambda x: x == int(x)).all()
                          else str(round(median_val, 2)))
            strategy = f"mediana ({fill_val})"
        else:
            fill_val = "Desconocido"
            strategy = "Desconocido"

        df.loc[null_mask, "valor"] = fill_val
        log[item_name] = {"n_imputed": n_null, "strategy": strategy, "is_numeric": is_num}

    return df, log


# ── Generalitzacions ──────────────────────────────────────────────────────────

def apply_generalizations(df: pd.DataFrame, configs: dict) -> pd.DataFrame:
    """Aplica bins o mapeig categòric als quasi-IDs segons la configuració de l'usuari."""
    df = df.copy()
    for item_name, cfg in configs.items():
        mask = df["item"] == item_name
        if not mask.any():
            continue
        t = cfg.get("type")
        if t == "bins":
            df.loc[mask, "valor"] = pd.cut(
                pd.to_numeric(df.loc[mask, "valor"], errors="coerce"),
                bins=cfg["bins"], labels=cfg["labels"],
                right=False, include_lowest=True,
            ).astype(str)
        elif t == "mapping":
            unmapped = cfg.get("unmapped_label", "Altres")
            mapping  = cfg.get("mapping", {})
            df.loc[mask, "valor"] = df.loc[mask, "valor"].astype(str).map(
                lambda v: mapping.get(v, unmapped)
            )
    return df


# ── K-anonimitat ──────────────────────────────────────────────────────────────

def apply_k_anonymity(df: pd.DataFrame, quasi_id_items: list[str], k: int) -> dict:
    """
    Aplica k-anonimitat per supressió. Elimina tots els registres dels pacients
    que no pertanyen a un grup d'equivalència amb almenys k membres.
    """
    if not quasi_id_items:
        n = int(df["pacient"].nunique())
        return {
            "df_anonymized": df, "n_patients_orig": n, "n_patients_final": n,
            "n_records_orig": len(df), "n_records_final": len(df),
            "n_suppressed_patients": 0, "pct_suppressed": 0.0,
            "equivalence_classes": {}, "suppressed_groups": [], "k_used": k,
            "warning": "Cap quasi-identificador definit.",
        }

    df = df.copy()
    df["pacient"] = _coerce_str(df["pacient"])
    df["item"]    = _coerce_str(df["item"])
    qi_df = df[df["item"].isin(quasi_id_items)].copy()
    qi_df["valor"] = qi_df["valor"].astype(str)

    # Reindex sobre tots els pacients del df: si un pacient no té cap fila per
    # a cap QI, ha d'aparèixer al pivot amb "NaN" a tots els QI i passar pel
    # filtre de k igual que qualsevol altre. Sense això, aquests pacients
    # cauen silenciosament del recompte i n_suppressed + n_final < n_orig.
    all_patients = df["pacient"].drop_duplicates()
    pivot = (
        qi_df.groupby(["pacient", "item"])["valor"]
        .first().unstack(fill_value="NaN")
        .reindex(all_patients, fill_value="NaN").reset_index()
    )
    for col in quasi_id_items:
        if col not in pivot.columns:
            pivot[col] = "NaN"

    group_sizes = (
        pivot.groupby(quasi_id_items, dropna=False)["pacient"]
        .count().reset_index(name="_count_")
    )
    pivot_m = pivot.merge(group_sizes, on=quasi_id_items, how="left")

    conform  = set(pivot_m[pivot_m["_count_"] >= k]["pacient"])
    suppress = set(pivot_m[pivot_m["_count_"] <  k]["pacient"])

    df_anon  = df[df["pacient"].isin(conform)].copy()
    n_orig   = int(df["pacient"].nunique())
    n_supp   = len(suppress)
    pct_supp = round(n_supp / n_orig * 100, 2) if n_orig else 0.0

    size_dist = group_sizes["_count_"].value_counts().sort_index()
    eq_stats  = {
        "total_groups":            int(len(group_sizes)),
        "conforming_groups":       int((group_sizes["_count_"] >= k).sum()),
        "suppressed_groups_count": int((group_sizes["_count_"] <  k).sum()),
        "size_distribution":       {str(int(s)): int(c) for s, c in size_dist.items()},
        "min_size":                int(group_sizes["_count_"].min()),
        "max_size":                int(group_sizes["_count_"].max()),
        "mean_size":               round(float(group_sizes["_count_"].mean()), 2),
    }

    suppressed_groups = [
        {str(kk): (int(vv) if kk == "_count_" else str(vv)) for kk, vv in row.items()}
        for row in group_sizes[group_sizes["_count_"] < k]
            .sort_values("_count_").head(30).to_dict(orient="records")
    ]

    return {
        "df_anonymized":          df_anon,
        "n_patients_orig":        n_orig,
        "n_patients_final":       len(conform),
        "n_records_orig":         len(df),
        "n_records_final":        len(df_anon),
        "n_suppressed_patients":  n_supp,
        "pct_suppressed":         pct_supp,
        "equivalence_classes":    eq_stats,
        "suppressed_groups":      suppressed_groups,
        "k_used":                 k,
    }


# ── Mètriques comparatives ────────────────────────────────────────────────────

def compute_metrics(df_orig: pd.DataFrame, df_anon: pd.DataFrame,
                    quasi_id_items: list[str], k_result: dict) -> dict:
    """Mètriques comparatives entre el dataset original i l'anonimitzat."""
    visits_orig = df_orig.groupby("pacient")["data"].nunique()
    return {
        "n_patients_orig":       int(df_orig["pacient"].nunique()),
        "n_patients_final":      int(df_anon["pacient"].nunique()) if len(df_anon) else 0,
        "n_suppressed_patients": k_result.get("n_suppressed_patients", 0),
        "pct_suppressed":        k_result.get("pct_suppressed", 0.0),
        "n_records_orig":        len(df_orig),
        "n_records_final":       len(df_anon),
        "n_items":               int(df_orig["item"].nunique()),
        "n_quasi_ids":           len(quasi_id_items),
        "quasi_id_items":        quasi_id_items,
        "k_used":                k_result.get("k_used"),
        "visits_per_patient_orig": {
            "min":  int(visits_orig.min())              if len(visits_orig) else 0,
            "max":  int(visits_orig.max())              if len(visits_orig) else 0,
            "mean": round(float(visits_orig.mean()), 2) if len(visits_orig) else 0,
        },
        "equivalence_classes": k_result.get("equivalence_classes", {}),
        "suppressed_groups":   k_result.get("suppressed_groups", []),
    }


# ── Helper ────────────────────────────────────────────────────────────────────

def _safe_num(val) -> float | None:
    try:
        v = float(val)
        return None if (np.isnan(v) or np.isinf(v)) else round(v, 4)
    except Exception:
        return None
