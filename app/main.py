"""
main.py — Datathon Anonymizer v3
---------------------------------
Endpoints:
  POST   /api/upload              → Càrrega de múltiples CSVs, normalització i perfilat
  POST   /api/classify            → Classificació d'ítems (quasi_id / non_id)
  POST   /api/set-generalizations → Configuració de generalitzacions
  POST   /api/simulate-k          → Simulació de supressió per k=2..5
  POST   /api/anonymize           → Procés complet + generació d'informes
  GET    /api/download/csv/{sid}       → ZIP amb un CSV anonimitzat per fitxer original
  GET    /api/download/report/html/{sid} → Informe HTML
  GET    /api/download/report/md/{sid}   → Informe Markdown
  GET    /api/download/report/{sid}      → Informe JSON
  DELETE /api/session/{sid}        → Neteja sessió
"""

import csv as _csv
import io
import json
import uuid
import zipfile
import traceback
from datetime import datetime, timezone
from typing import List

import math
import numpy as np
import pandas as pd
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.modules.anonymizer import (
    normalize_columns, validate_dataframe, profile_items,
    compute_date_deltas, hash_patient_ids, impute_missing_values,
    apply_generalizations, apply_k_anonymity, compute_metrics,
    detect_date_format, DATE_FORMATS,
    propose_mapping, apply_user_mapping,
)
from app.modules.report_md   import generate_markdown_report
from app.modules.report_html import generate_html_report

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Datathon Anonymizer", version="3.0.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Garanteix que qualsevol excepció no controlada torni JSON i no el
    handler 500 default amb text pla 'Internal Server Error', que feia que
    el frontend mostrés 'Unexpected token I' en lloc d'un missatge útil."""
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {exc}"},
    )


def _to_json_safe(obj):
    """Casteja recursivament tipus numpy/pandas a tipus natius Python perquè
    la serialització JSON de FastAPI no peti silenciosament (cas vist: amb
    np.bool_ a /api/anonymize, corregit a f9e435b; reapareixia amb altres
    tipus numpy provinents de pandas)."""
    if isinstance(obj, dict):
        return {str(k): _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_json_safe(v) for v in obj]
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        v = float(obj)
        return None if (math.isnan(v) or math.isinf(v)) else v
    if isinstance(obj, np.ndarray):
        return _to_json_safe(obj.tolist())
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if obj is pd.NA or obj is pd.NaT:
        return None
    return obj


sessions: dict[str, dict] = {}
PREVIEW_ROWS = 8
_SOURCE_COL  = "_source_file"   # columna interna que recorda l'origen de cada fila

_REPORT_TITLES = {
    "ca": "Informe d'Anonimització de Dades Clíniques",
    "es": "Informe de Anonimización de Datos Clínicos",
    "en": "Clinical Data Anonymization Report",
}
_CONFIDENTIAL = {
    "ca": "DOCUMENT CONFIDENCIAL · ÚS INTERN",
    "es": "DOCUMENTO CONFIDENCIAL · USO INTERNO",
    "en": "CONFIDENTIAL DOCUMENT · INTERNAL USE",
}


# ── Models Pydantic ───────────────────────────────────────────────────────────

class ClassifyRequest(BaseModel):
    session_id:      str
    classifications: dict[str, str]

class GeneralizationConfig(BaseModel):
    session_id:      str
    generalizations: dict

class AnonymizeRequest(BaseModel):
    session_id: str
    k:          int
    lang:       str = "es"

class SimulateKRequest(BaseModel):
    session_id: str

class DateFormatRequest(BaseModel):
    session_id:  str
    date_format: str

class ConfirmMappingRequest(BaseModel):
    session_id: str
    mappings:   dict[str, dict[str, str]]   # {filename: {canonical: raw_col}}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_session(sid: str) -> dict:
    if sid not in sessions:
        raise HTTPException(404, detail=f"Sessió '{sid}' no trobada.")
    return sessions[sid]

def _df_preview(df: pd.DataFrame) -> dict:
    cols = [c for c in df.columns if c != _SOURCE_COL]
    preview = df[cols].head(PREVIEW_ROWS).copy().astype(str)
    return {"columns": list(preview.columns), "rows": preview.values.tolist()}

def _df_preview_raw(df: pd.DataFrame) -> dict:
    """Preview amb els noms de columna originals (abans del rename). S'usa al
    pas de confirmació del mapatge perquè l'usuari vegi exactament què té al
    seu CSV."""
    preview = df.head(PREVIEW_ROWS).copy().astype(str)
    return {"columns": list(preview.columns), "rows": preview.values.tolist()}

def _date_range(df: pd.DataFrame, date_format: str = "iso") -> dict:
    try:
        from app.modules.anonymizer import _parse_dates
        parsed = _parse_dates(df["data"], date_format)
        if parsed.notna().sum() == 0:
            return {"min": None, "max": None}
        return {"min": str(parsed.min().date()), "max": str(parsed.max().date())}
    except Exception:
        return {"min": None, "max": None}

def _read_csv(content: bytes) -> pd.DataFrame:
    """Llegeix un CSV tolerant a encodings i a cometes mal balancejades.

    Tres nivells de tolerància (provats per cada encoding):
      1. Parser C (ràpid, estricte amb cometes). Cobreix la majoria de CSVs.
      2. Parser Python amb `on_bad_lines='skip'`: salta línies malformades en
         lloc de petar. Activat quan el parser C llança ParserError, típicament
         per cometes desbalancejades que fusionen línies.
      3. Parser Python amb `quoting=QUOTE_NONE`: tracta les cometes com a text
         literal. Últim recurs per CSVs amb cometes dobles literals dins valors
         no quotejats (cas vist a Osakidetza) i per cometes que obren a meitat
         de valor i mai es tanquen — el parser python amb skip salta totes les
         línies fusionades, QUOTE_NONE les recupera.

    `low_memory` només és vàlid amb el parser C; passar-lo al parser python
    fa petar amb ValueError i els fallbacks tolerants no s'executen mai.
    """
    encodings = ("utf-8", "utf-8-sig", "latin-1", "cp1252")
    last_err: Exception | None = None

    def _try_read(enc: str, **kwargs) -> pd.DataFrame:
        if kwargs.get("engine") is None:
            kwargs.setdefault("low_memory", False)
        df = pd.read_csv(io.BytesIO(content), encoding=enc, **kwargs)
        df.columns = [c.strip().lower() for c in df.columns]
        return df

    for enc in encodings:
        try:
            return _try_read(enc)
        except UnicodeDecodeError:
            continue
        except pd.errors.ParserError as e:
            last_err = e
            # Per cometes desbalancejades (típic: cometa obre i no tanca dins
            # de la fila) el parser python amb on_bad_lines='skip' descarta
            # totes les línies fusionades en lloc de salvar-les. QUOTE_NONE
            # és l'única estratègia que recupera el contingut original, així
            # que el fem servir directament en aquest cas.
            try:
                return _try_read(
                    enc, engine="python",
                    quoting=_csv.QUOTE_NONE, on_bad_lines="skip",
                )
            except UnicodeDecodeError:
                continue
            except Exception as e2:
                last_err = e2
                try:
                    return _try_read(enc, engine="python", on_bad_lines="skip")
                except UnicodeDecodeError:
                    continue
                except Exception as e3:
                    last_err = e3
                    continue

    detail = f": {last_err}" if last_err else "."
    raise ValueError(f"No s'ha pogut llegir el fitxer (encoding o format no reconegut){detail}")

def _stream(content: str | bytes, media_type: str, filename: str) -> StreamingResponse:
    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

def _build_zip(csv_map: dict[str, bytes]) -> bytes:
    """Construeix un ZIP en memòria amb un CSV per entrada del dict.

    Els valors han d'estar ja codificats com a bytes (preferiblement utf-8-sig
    perquè Excel a Windows obri els CSVs sense corrompre accents)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname, csv_bytes in csv_map.items():
            zf.writestr(fname, csv_bytes)
    return buf.getvalue()


# ── Ruta arrel ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("static/index.html", encoding="utf-8") as f:
        return f.read()


# ── Endpoint 1: Càrrega (múltiples fitxers) ───────────────────────────────────

@app.post("/api/upload")
async def upload(files: List[UploadFile] = File(...)):
    """
    Accepta un o més fitxers CSV en format llarg estàndard (4 columnes).

    Per a cada fitxer es proposa un mapatge canonical → raw_col:
      1. Coincidència per àlies (`patient_id` → `pacient`, `fecha` → `data`, ...).
      2. Si en falta algun, fallback posicional (1a → pacient, 2a → data, ...).

    Si TOTS els fitxers tenen els 4 canonicals coberts pel pas 1, es continua
    com sempre i es retorna `status: "ok"` amb tot el perfilat.

    Si algun fitxer requereix fallback posicional, es deixa la sessió en estat
    pendent i es retorna `status: "needs_mapping"` amb la proposta + preview
    per fitxer. El frontend l'ensenya i confirma via /api/confirm-mapping.
    """
    try:
        if not files:
            raise HTTPException(400, "Cal adjuntar almenys un fitxer CSV.")

        files_info: list[dict] = []
        needs_confirmation = False

        for upload_file in files:
            content = await upload_file.read()
            df_raw  = _read_csv(content)
            raw_columns = list(df_raw.columns)

            if len(raw_columns) < 4:
                raise HTTPException(
                    400,
                    detail=(
                        f"Fitxer '{upload_file.filename}': cal almenys 4 columnes "
                        f"(pacient, data, item, valor); se n'han trobat {len(raw_columns)}."
                    ),
                )

            mapping, alias_complete = propose_mapping(raw_columns)
            files_info.append({
                "filename":         upload_file.filename,
                "df_raw":           df_raw,
                "raw_columns":      raw_columns,
                "proposed_mapping": mapping,
                "alias_complete":   alias_complete,
            })
            if not alias_complete:
                needs_confirmation = True

        sid = str(uuid.uuid4())

        if needs_confirmation:
            sessions[sid] = {"_pending_mapping": files_info}
            return {
                "session_id": sid,
                "status":     "needs_mapping",
                "files": [
                    {
                        "filename":         f["filename"],
                        "raw_columns":      f["raw_columns"],
                        "proposed_mapping": f["proposed_mapping"],
                        "alias_complete":   f["alias_complete"],
                        "preview":          _df_preview_raw(f["df_raw"]),
                    }
                    for f in files_info
                ],
            }

        mappings = {f["filename"]: f["proposed_mapping"] for f in files_info}
        return _finalize_upload(sid, files_info, mappings)

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, detail=str(e))


@app.post("/api/confirm-mapping")
async def confirm_mapping(req: ConfirmMappingRequest):
    """Aplica el mapatge confirmat per l'usuari a una sessió pendent i continua
    amb el perfilat. Valida que cada fitxer tingui els 4 canonicals coberts,
    sense duplicats, i amb columnes que existeixin al CSV original."""
    if (
        req.session_id not in sessions
        or "_pending_mapping" not in sessions[req.session_id]
    ):
        raise HTTPException(404, "Sessió pendent de confirmació no trobada o ja confirmada.")

    files_info = sessions[req.session_id]["_pending_mapping"]
    canonicals = ("pacient", "data", "item", "valor")

    for f in files_info:
        m = req.mappings.get(f["filename"])
        if not m:
            raise HTTPException(400, f"Manca mapatge per al fitxer '{f['filename']}'.")
        missing = [c for c in canonicals if not m.get(c)]
        if missing:
            raise HTTPException(
                400,
                detail=(
                    f"Fitxer '{f['filename']}': cal assignar una columna a "
                    f"{', '.join(missing)}."
                ),
            )
        values = [m[c] for c in canonicals]
        if len(set(values)) != len(values):
            raise HTTPException(
                400,
                detail=(
                    f"Fitxer '{f['filename']}': no es pot assignar la mateixa "
                    "columna a més d'un camp."
                ),
            )
        unknown = [v for v in values if v not in f["raw_columns"]]
        if unknown:
            raise HTTPException(
                400,
                detail=(
                    f"Fitxer '{f['filename']}': columnes desconegudes "
                    f"({', '.join(unknown)})."
                ),
            )

    return _finalize_upload(req.session_id, files_info, req.mappings)


def _finalize_upload(
    sid: str,
    files_info: list[dict],
    mappings: dict[str, dict[str, str]],
) -> dict:
    """Aplica els mapatges definitius, concatena, perfila i deixa la sessió en
    l'estat estàndard d'upload. Compartit entre el cas àlies-complet (auto) i
    el cas que l'usuari ha confirmat el mapatge via /api/confirm-mapping."""
    dfs                = []
    filenames          = []
    col_mapping_global: dict[str, str] = {}

    for info in files_info:
        fname   = info["filename"]
        mapping = mappings[fname]
        df = apply_user_mapping(info["df_raw"].copy(), mapping)

        errors = validate_dataframe(df)
        if errors:
            raise HTTPException(400, detail=f"Fitxer '{fname}': {' | '.join(errors)}")

        df[_SOURCE_COL] = fname
        dfs.append(df)
        filenames.append(fname)

        for canon, raw in mapping.items():
            if raw and canon not in col_mapping_global.values():
                col_mapping_global[raw] = canon

    df = pd.concat(dfs, ignore_index=True)

    # ── Diagnòstic de relació entre fitxers (només té sentit si N > 1) ────────
    per_file_stats = []
    per_file_patient_sets: list[set] = []
    per_file_item_sets:    list[set] = []
    for raw_df, fname in zip(dfs, filenames):
        pset = set(raw_df["pacient"].dropna().astype(str).unique())
        iset = set(raw_df["item"].dropna().astype(str).unique())
        per_file_patient_sets.append(pset)
        per_file_item_sets.append(iset)
        per_file_stats.append({
            "filename":   fname,
            "n_records":  int(len(raw_df)),
            "n_patients": int(len(pset)),
            "n_items":    int(len(iset)),
        })

    if len(filenames) > 1:
        shared_all = set.intersection(*per_file_patient_sets) if per_file_patient_sets else set()
        union_all  = set.union(*per_file_patient_sets)       if per_file_patient_sets else set()
        n_shared_all = len(shared_all)
        n_union      = len(union_all)
        pct_shared   = round(n_shared_all / n_union * 100, 1) if n_union else 0.0

        from collections import Counter
        item_counter = Counter()
        for iset in per_file_item_sets:
            for it in iset:
                item_counter[it] += 1
        overlapping_items = sorted([i for i, c in item_counter.items() if c > 1])

        relationship = {
            "n_patients_shared_all": n_shared_all,
            "n_patients_union":      n_union,
            "pct_patients_shared":   pct_shared,
            "overlapping_items":     overlapping_items,
            "n_overlapping_items":   len(overlapping_items),
        }
    else:
        relationship = None

    items          = profile_items(df)
    date_detection = detect_date_format(df["data"])
    date_format    = date_detection["best"]
    dr             = _date_range(df, date_format)

    sessions[sid] = {
        "df_original":     df,
        "filenames":       filenames,
        "col_mapping":     col_mapping_global,
        "date_range":      dr,
        "date_format":     date_format,
        "date_detection":  date_detection,
        "items":           items,
        "classifications": {},
        "generalizations": {},
        "dfs_anonymized":  None,
        "metrics":         None,
        "imputation_log":  {},
        "report_md":       None,
        "report_html":     None,
    }

    return {
        "session_id":      sid,
        "status":          "ok",
        "filenames":       filenames,
        "n_files":         len(filenames),
        "n_records":       len(df),
        "n_patients":      int(df["pacient"].nunique()),
        "n_items":         len(items),
        "date_range":      dr,
        "date_format":     date_format,
        "date_detection":  date_detection,
        "items":           items,
        "preview":         _df_preview(df),
        "per_file_stats":  per_file_stats,
        "relationship":    relationship,
        "col_mapping":     col_mapping_global,
    }


# ── Endpoint 1b: Override del format de timestamp ────────────────────────────

@app.post("/api/set-date-format")
async def set_date_format(req: DateFormatRequest):
    sess = _get_session(req.session_id)
    if req.date_format not in DATE_FORMATS:
        raise HTTPException(
            400,
            detail=f"date_format ha de ser un de: {', '.join(DATE_FORMATS)}",
        )
    sess["date_format"] = req.date_format

    # Recalculem el rang de dates i mostres parsejades amb el nou format
    sess["date_range"] = _date_range(sess["df_original"], req.date_format)
    redetection = detect_date_format(sess["df_original"]["data"])
    redetection["best"] = req.date_format     # respectem la tria manual
    # Regenerem mostres amb el format escollit per l'usuari
    from app.modules.anonymizer import _parse_dates
    s = sess["df_original"]["data"]
    parsed_user = _parse_dates(s, req.date_format)
    non_null = s.notna() & ~s.astype(str).str.strip().isin({"", "nan", "NaN", "None"})
    sample_idx = s[non_null].index[:5]
    samples = []
    for i in sample_idx:
        out = parsed_user.loc[i]
        samples.append({
            "raw":    str(s.loc[i]),
            "parsed": "" if pd.isna(out) else out.strftime("%Y-%m-%d %H:%M:%S"),
            "ok":     bool(pd.notna(out)),
        })
    redetection["samples"] = samples
    sess["date_detection"] = redetection

    return {
        "ok":             True,
        "date_format":    req.date_format,
        "date_range":     sess["date_range"],
        "date_detection": redetection,
    }


# ── Endpoint 2: Classificació ─────────────────────────────────────────────────

@app.post("/api/classify")
async def classify(req: ClassifyRequest):
    sess = _get_session(req.session_id)
    sess["classifications"] = req.classifications
    quasi = [k for k, v in req.classifications.items() if v == "quasi_id"]
    return {"ok": True, "quasi_profiles": [i for i in sess["items"] if i["name"] in quasi]}


# ── Endpoint 3: Generalitzacions ──────────────────────────────────────────────

@app.post("/api/set-generalizations")
async def set_generalizations(req: GeneralizationConfig):
    _get_session(req.session_id)["generalizations"] = req.generalizations
    return {"ok": True}


# ── Endpoint 4: Simulació de k ────────────────────────────────────────────────

@app.post("/api/simulate-k")
async def simulate_k(req: SimulateKRequest):
    sess = _get_session(req.session_id)
    if not sess["classifications"]:
        raise HTTPException(400, "Cal classificar els ítems primer.")
    try:
        quasi = [k for k, v in sess["classifications"].items() if v == "quasi_id"]
        # Simulem sobre el dataset combinat (sense la columna interna)
        df_t  = sess["df_original"].drop(columns=[_SOURCE_COL], errors="ignore")
        df_t  = compute_date_deltas(df_t, date_format=sess.get("date_format", "iso"))
        if sess["generalizations"]:
            df_t = apply_generalizations(df_t, sess["generalizations"])
        df_t, _ = impute_missing_values(df_t, quasi)

        simulations = []
        for k in [2, 3, 4, 5]:
            kr = apply_k_anonymity(df_t, quasi, k)
            eq = kr["equivalence_classes"]
            simulations.append({
                "k":                k,
                "n_patients_orig":  kr["n_patients_orig"],
                "n_patients_final": kr["n_patients_final"],
                "n_suppressed":     kr["n_suppressed_patients"],
                "pct_suppressed":   kr["pct_suppressed"],
                "n_groups":         eq.get("total_groups", 0),
                "conforming_groups":eq.get("conforming_groups", 0),
                "size_distribution":eq.get("size_distribution", {}),
            })
        return {"quasi_ids": quasi, "simulations": simulations}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, detail=str(e))


# ── Endpoint 5: Anonimització ─────────────────────────────────────────────────

@app.post("/api/anonymize")
async def anonymize(req: AnonymizeRequest):
    sess = _get_session(req.session_id)
    if req.k < 2:
        raise HTTPException(400, "k ha de ser ≥ 2.")
    if not sess["classifications"]:
        raise HTTPException(400, "Cal classificar els ítems primer.")
    try:
        classifications = sess["classifications"]
        generalizations = sess["generalizations"]
        quasi           = [k for k, v in classifications.items() if v == "quasi_id"]

        # ── Procés sobre el dataset combinat ──────────────────────────────────
        # Conservem la columna _source_file durant tot el procés
        df_t = sess["df_original"].copy()
        df_core = df_t.drop(columns=[_SOURCE_COL])

        df_core = compute_date_deltas(df_core, date_format=sess.get("date_format", "iso"))
        if generalizations:
            df_core = apply_generalizations(df_core, generalizations)
        df_core, imputation_log = impute_missing_values(df_core, quasi)
        df_core = hash_patient_ids(df_core)

        k_result = apply_k_anonymity(df_core, quasi, req.k)
        df_anon  = k_result["df_anonymized"]
        metrics  = compute_metrics(df_core, df_anon, quasi, k_result)

        # Recuperem la columna d'origen sobre el df anonimitzat
        # (els índexos es conserven de pd.concat, podem fer join per índex)
        df_anon_with_src = df_anon.copy()
        df_anon_with_src[_SOURCE_COL] = df_t.loc[df_anon.index, _SOURCE_COL].values

        # ── Separar per fitxer original ───────────────────────────────────────
        dfs_anonymized = {}
        for fname in sess["filenames"]:
            dfs_anonymized[fname] = (
                df_anon_with_src[df_anon_with_src[_SOURCE_COL] == fname]
                .drop(columns=[_SOURCE_COL])
                .reset_index(drop=True)
            )

        sess["dfs_anonymized"] = dfs_anonymized
        sess["metrics"]        = metrics
        sess["imputation_log"] = imputation_log

        # ── Generar informes ──────────────────────────────────────────────────
        now_str      = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        all_items    = [i["name"] for i in sess["items"]]
        orig_pacient = next(
            (o for o, c in sess["col_mapping"].items() if c == "pacient"), "patient_id"
        )
        filenames_str = ", ".join(sess["filenames"])

        report_kwargs = dict(
            lang             = req.lang,
            filename         = filenames_str,
            col_mapping      = sess["col_mapping"],
            classifications  = classifications,
            generalizations  = generalizations,
            imputation_log   = imputation_log,
            metrics          = {**metrics, "suppressed_groups": k_result.get("suppressed_groups", [])},
            date_range       = sess["date_range"],
            all_items        = all_items,
            orig_pacient_col = orig_pacient,
        )
        sess["report_md"]   = generate_markdown_report(**report_kwargs)
        sess["report_html"] = generate_html_report(
            markdown_text      = sess["report_md"],
            title              = _REPORT_TITLES.get(req.lang, _REPORT_TITLES["es"]),
            filename           = filenames_str,
            generated_at       = now_str,
            confidential_label = _CONFIDENTIAL.get(req.lang, _CONFIDENTIAL["es"]),
        )

        result = {k: v for k, v in metrics.items() if not isinstance(v, pd.DataFrame)}
        result["imputation_log"] = imputation_log
        result["n_files"]        = len(sess["filenames"])
        result["filenames"]      = sess["filenames"]
        return _to_json_safe(result)

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, detail=str(e))


# ── Descàrregues ──────────────────────────────────────────────────────────────

@app.get("/api/download/csv/{session_id}")
async def download_csv(session_id: str):
    """
    Si hi ha un sol fitxer retorna un CSV directament.
    Si n'hi ha més d'un, retorna un ZIP amb un CSV anonimitzat per fitxer original.
    """
    sess = _get_session(session_id)
    if sess["dfs_anonymized"] is None:
        raise HTTPException(400, "Cal executar l'anonimització primer.")

    dfs = sess["dfs_anonymized"]

    # BOM UTF-8 a la sortida: Excel a Windows obre CSVs sense BOM com a cp1252
    # i corromp accents (`Catéter` → `CatÃ©ter`). El BOM força la detecció UTF-8.
    if len(dfs) == 1:
        fname, df = next(iter(dfs.items()))
        csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
        out_name = fname.replace(".csv", "") + "_anonymized.csv"
        return _stream(csv_bytes, "text/csv; charset=utf-8", out_name)
    else:
        csv_map: dict[str, bytes] = {}
        for fname, df in dfs.items():
            out_name = fname.replace(".csv", "") + "_anonymized.csv"
            csv_map[out_name] = df.to_csv(index=False).encode("utf-8-sig")
        zip_bytes = _build_zip(csv_map)
        return _stream(zip_bytes, "application/zip", "datasets_anonymized.zip")


def _report_filename(filenames: list[str], ext: str) -> str:
    """
    Per a un sol fitxer pujat, l'informe pren el seu nom («dataset_X_report.html»).
    Per a multi-fitxer, un nom genèric («anonymization_report.html») per evitar
    que sembli que l'informe només cobreix el primer fitxer.
    """
    if filenames and len(filenames) == 1:
        return filenames[0].replace(".csv", "") + f"_report.{ext}"
    return f"anonymization_report.{ext}"


@app.get("/api/download/report/html/{session_id}")
async def download_html(session_id: str):
    sess = _get_session(session_id)
    if not sess.get("report_html"):
        raise HTTPException(400, "Cal executar l'anonimització primer.")
    return _stream(sess["report_html"], "text/html",
                   _report_filename(sess["filenames"], "html"))


@app.get("/api/download/report/md/{session_id}")
async def download_md(session_id: str):
    sess = _get_session(session_id)
    if not sess.get("report_md"):
        raise HTTPException(400, "Cal executar l'anonimització primer.")
    return _stream(sess["report_md"], "text/markdown",
                   _report_filename(sess["filenames"], "md"))


@app.get("/api/download/report/{session_id}")
async def download_json(session_id: str):
    sess = _get_session(session_id)
    if sess["metrics"] is None:
        raise HTTPException(400, "Cal executar l'anonimització primer.")
    report = {
        "filenames":       sess["filenames"],
        "date_format":     sess.get("date_format"),
        "date_range":      sess.get("date_range"),
        "classifications": sess["classifications"],
        "generalizations": sess["generalizations"],
        "metrics":         sess["metrics"],
    }
    return _stream(
        json.dumps(report, ensure_ascii=False, indent=2),
        "application/json", "anonymization_report.json",
    )


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    sessions.pop(session_id, None)
    return {"ok": True}
