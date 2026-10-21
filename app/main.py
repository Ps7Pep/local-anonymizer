"""
main.py — Datathon Anonymizer
------------------------------
Endpoints:
  POST   /api/upload              → Càrrega de múltiples CSVs, normalització i perfilat
  POST   /api/confirm-mapping     → Confirmació del mapatge de columnes (si els àlies no cobreixen)
  POST   /api/set-date-format     → Override del format de timestamp
  POST   /api/classify            → Classificació d'ítems (quasi_id / non_id)
  POST   /api/set-generalizations → Configuració de generalitzacions
  POST   /api/simulate-k          → Simulació de supressió per k=2..5
  POST   /api/anonymize           → Procés complet + generació d'informes
  GET    /api/download/csv/{sid}       → CSV (un fitxer) o ZIP amb un CSV per fitxer original
  GET    /api/download/report/html/{sid} → Informe HTML
  GET    /api/download/report/md/{sid}   → Informe Markdown
  GET    /api/download/report/{sid}      → Informe JSON
  DELETE /api/session/{sid}        → Neteja sessió
  GET    /api/health               → Healthcheck del contenidor

Els endpoints que fan feina de pandas són `def` (no `async def`): FastAPI els
executa al threadpool i no bloquegen l'event loop mentre es processa un CSV gran.
"""

import csv as _csv
import io
import json
import mimetypes
import os
import re
import threading
import time
import uuid
import zipfile
import traceback
from collections import Counter
from datetime import datetime, timezone
from typing import List
from urllib.parse import quote

import math
import numpy as np
import pandas as pd
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import __version__
from app.modules.anonymizer import (
    validate_dataframe, profile_items,
    compute_date_deltas, hash_patient_ids, new_hash_key, impute_missing_values,
    apply_generalizations, apply_k_anonymity, compute_metrics,
    detect_date_format, DATE_FORMATS, _parse_dates,
    propose_mapping, apply_user_mapping,
)
from app.modules.report_md   import generate_markdown_report
from app.modules.report_html import generate_html_report

# ── App ───────────────────────────────────────────────────────────────────────
# Sense CORS: el frontend es serveix des del mateix origen, i cap altra web
# oberta al navegador de l'usuari ha de poder cridar l'API.
app = FastAPI(title="Datathon Anonymizer", version=__version__)
# La imatge slim no porta /etc/mime.types: sense això les fonts surten com a octet-stream
mimetypes.add_type("font/woff2", ".woff2")
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


# ── Sessions ──────────────────────────────────────────────────────────────────
# En memòria i amb caducitat per inactivitat: un dataset oblidat no es queda
# per sempre a la RAM del contenidor. Configurable amb SESSION_TTL_MINUTES.
sessions: dict[str, dict] = {}
_sessions_lock      = threading.Lock()
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_MINUTES", "120")) * 60

PREVIEW_ROWS = 8
_SOURCE_COL  = "_source_file"   # columna interna que recorda l'origen de cada fila
_CANONICALS  = ("pacient", "data", "item", "valor")

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


def _purge_expired_sessions() -> None:
    cutoff = time.monotonic() - SESSION_TTL_SECONDS
    with _sessions_lock:
        for sid in [s for s, v in sessions.items() if v.get("_last_access", 0) < cutoff]:
            del sessions[sid]


def _store_session(sid: str, sess: dict) -> None:
    _purge_expired_sessions()
    sess["_last_access"] = time.monotonic()
    with _sessions_lock:
        sessions[sid] = sess


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
    _purge_expired_sessions()
    sess = sessions.get(sid)
    if sess is None:
        raise HTTPException(404, detail="Sessió no trobada o caducada. Comença una sessió nova.")
    if "_pending_mapping" in sess:
        raise HTTPException(409, detail="Cal confirmar primer el mapatge de columnes.")
    sess["_last_access"] = time.monotonic()
    return sess

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

    Tot es llegeix com a TEXT (`dtype=str`): si pandas endevina tipus, una
    columna d'IDs numèrica amb algun buit es converteix en float (`12` →
    `12.0`) i `0012` perd els zeros. En mode multi-fitxer el mateix pacient
    acabaria sent dues persones diferents (per a k i per al hash). Els valors
    numèrics ja es converteixen on cal (`pd.to_numeric`), i a la sortida es
    conserva exactament el text original.
    """
    encodings = ("utf-8", "utf-8-sig", "latin-1", "cp1252")
    last_err: Exception | None = None

    def _try_read(enc: str, **kwargs) -> pd.DataFrame:
        if kwargs.get("engine") is None:
            kwargs.setdefault("low_memory", False)
        df = pd.read_csv(io.BytesIO(content), encoding=enc, dtype=str, **kwargs)
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

def _safe_basename(name: str | None) -> str:
    """Nom de fitxer sense components de ruta: acaba dins del ZIP de sortida i
    no ha de poder escriure fora del directori on l'usuari l'extregui."""
    base = re.split(r"[\\/]", name or "")[-1].strip()
    return base or "dataset.csv"

def _stem(fname: str) -> str:
    return re.sub(r"\.csv$", "", fname, flags=re.IGNORECASE)

def _stream(content: str | bytes, media_type: str, filename: str) -> StreamingResponse:
    # Les capçaleres HTTP són latin-1: un nom com «càrrega_ñ.csv» o amb
    # cometes trencava la resposta. Fallback ASCII + filename* (RFC 5987).
    fallback = re.sub(r"[^A-Za-z0-9._-]", "_", filename)
    disposition = f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename)}"
    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={"Content-Disposition": disposition},
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

def _validate_generalizations(gens: dict) -> list[str]:
    """Valida l'estructura abans de desar-la: un bin mal format petava més
    tard dins de `pd.cut` amb un 500 poc entenedor."""
    errors = []
    for name, cfg in gens.items():
        if not isinstance(cfg, dict):
            errors.append(f"'{name}': configuració no vàlida.")
            continue
        t = cfg.get("type")
        if t == "bins":
            bins, labels = cfg.get("bins"), cfg.get("labels")
            try:
                bins = [float(b) for b in bins]
            except (TypeError, ValueError):
                errors.append(f"'{name}': els punts de tall han de ser numèrics.")
                continue
            if len(bins) < 2:
                errors.append(f"'{name}': cal almenys 2 punts de tall.")
            elif any(b2 <= b1 for b1, b2 in zip(bins, bins[1:])):
                errors.append(f"'{name}': els punts de tall han de ser estrictament creixents.")
            elif not isinstance(labels, list) or len(labels) != len(bins) - 1:
                errors.append(f"'{name}': cal exactament {len(bins) - 1} etiqueta/es.")
        elif t == "mapping":
            if not isinstance(cfg.get("mapping", {}), dict):
                errors.append(f"'{name}': el mapatge ha de ser un objecte {{valor: categoria}}.")
        else:
            errors.append(f"'{name}': tipus de generalització desconegut ({t!r}).")
    return errors

def _transform(sess: dict) -> tuple[pd.DataFrame, list[str], dict, dict, dict]:
    """Capa 1 compartida per simulate-k i anonymize, en l'ordre documentat:
    deltes de data → imputació (sobre valors originals) → generalització.
    Treballa sobre els IDs reals: el hash s'aplica a `anonymize`, al final.

    Només s'apliquen generalitzacions dels ítems que ara són quasi-ID: si
    l'usuari en desclassifica un, la seva configuració antiga no ha de
    modificar un ítem que es publica sense canvis.
    """
    quasi = [k for k, v in sess["classifications"].items() if v == "quasi_id"]
    gens  = {k: v for k, v in sess["generalizations"].items() if k in quasi}
    df = sess["df_original"].drop(columns=[_SOURCE_COL], errors="ignore")
    df = compute_date_deltas(df, date_format=sess.get("date_format", "iso"))
    df, imputation_log     = impute_missing_values(df, quasi)
    df, generalization_log = apply_generalizations(df, gens)
    return df, quasi, gens, imputation_log, generalization_log


# ── Ruta arrel ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def root():
    with open("static/index.html", encoding="utf-8") as f:
        return f.read()


@app.get("/api/health")
def health():
    return {"status": "ok", "version": __version__}


# ── Endpoint 1: Càrrega (múltiples fitxers) ───────────────────────────────────

@app.post("/api/upload")
def upload(files: List[UploadFile] = File(...)):
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

        names = [_safe_basename(f.filename) for f in files]
        dupes = sorted(n for n, c in Counter(names).items() if c > 1)
        if dupes:
            # El nom de fitxer és la clau del mapatge i de la separació de sortida.
            raise HTTPException(
                400, detail=f"Hi ha fitxers amb el mateix nom ({', '.join(dupes)}); reanomena'ls abans de pujar-los.",
            )

        files_info: list[dict] = []
        needs_confirmation = False

        for upload_file, fname in zip(files, names):
            content = upload_file.file.read()
            df_raw  = _read_csv(content)
            raw_columns = list(df_raw.columns)

            if len(raw_columns) < 4:
                raise HTTPException(
                    400,
                    detail=(
                        f"Fitxer '{fname}': cal almenys 4 columnes "
                        f"(pacient, data, item, valor); se n'han trobat {len(raw_columns)}."
                    ),
                )

            mapping, alias_complete = propose_mapping(raw_columns)
            files_info.append({
                "filename":         fname,
                "df_raw":           df_raw,
                "raw_columns":      raw_columns,
                "proposed_mapping": mapping,
                "alias_complete":   alias_complete,
            })
            if not alias_complete:
                needs_confirmation = True

        sid = str(uuid.uuid4())

        if needs_confirmation:
            _store_session(sid, {"_pending_mapping": files_info})
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
def confirm_mapping(req: ConfirmMappingRequest):
    """Aplica el mapatge confirmat per l'usuari a una sessió pendent i continua
    amb el perfilat. Valida que cada fitxer tingui els 4 canonicals coberts,
    sense duplicats, i amb columnes que existeixin al CSV original."""
    _purge_expired_sessions()
    pending = sessions.get(req.session_id)
    if not pending or "_pending_mapping" not in pending:
        raise HTTPException(404, "Sessió pendent de confirmació no trobada, caducada o ja confirmada.")

    files_info = pending["_pending_mapping"]

    for f in files_info:
        m = req.mappings.get(f["filename"])
        if not m:
            raise HTTPException(400, f"Manca mapatge per al fitxer '{f['filename']}'.")
        missing = [c for c in _CANONICALS if not m.get(c)]
        if missing:
            raise HTTPException(
                400,
                detail=(
                    f"Fitxer '{f['filename']}': cal assignar una columna a "
                    f"{', '.join(missing)}."
                ),
            )
        values = [m[c] for c in _CANONICALS]
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
    el cas que l'usuari ha confirmat el mapatge via /api/confirm-mapping.

    És el pas de COHERÈNCIA, abans de qualsevol transformació: IDs nets i
    comparables entre fitxers, files sense pacient o sense variable
    descartades (no es poden atribuir a ningú) i comptades, i tots els
    fitxers combinats en un sol dataset perquè dates, imputació i k es
    calculin sobre l'univers complet de cada pacient."""
    dfs         = []
    filenames   = []
    col_mappings: dict[str, dict[str, str]] = {}   # {filename: {canonical: raw_col}}
    dropped:      dict[str, dict[str, int]] = {}   # {filename: {without_patient, without_item}}

    for info in files_info:
        fname   = info["filename"]
        mapping = {c: mappings[fname][c] for c in _CANONICALS}
        df = apply_user_mapping(info["df_raw"].copy(), mapping)

        if {"pacient", "item"} <= set(df.columns):
            no_patient = df["pacient"].isna()
            no_item    = df["item"].isna() & ~no_patient
            if no_patient.any() or no_item.any():
                dropped[fname] = {"without_patient": int(no_patient.sum()),
                                  "without_item":    int(no_item.sum())}
                df = df[~(no_patient | no_item)].reset_index(drop=True)

        errors = validate_dataframe(df)
        if errors:
            raise HTTPException(400, detail=f"Fitxer '{fname}': {' | '.join(errors)}")

        df[_SOURCE_COL] = fname
        dfs.append(df)
        filenames.append(fname)
        col_mappings[fname] = mapping

    df = pd.concat(dfs, ignore_index=True)

    # Files idèntiques (mateix pacient, data, variable i valor): es conserven,
    # però s'informa — en multi-fitxer solen indicar taules que se solapen.
    coherence = {
        "dropped_rows":          dropped,
        "n_dropped_rows":        sum(d["without_patient"] + d["without_item"] for d in dropped.values()),
        "n_duplicate_rows":      int(df.duplicated(subset=list(_CANONICALS)).sum()),
    }

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

    _store_session(sid, {
        "df_original":        df,
        "filenames":          filenames,
        "col_mappings":       col_mappings,
        "coherence":          coherence,
        "hash_key":           new_hash_key(),   # mai surt de la memòria del procés
        "date_range":         dr,
        "date_format":        date_format,
        "date_detection":     date_detection,
        "items":              items,
        "classifications":    {},
        "generalizations":    {},
        "dfs_anonymized":     None,
        "metrics":            None,
        "imputation_log":     {},
        "generalization_log": {},
        "report_md":          None,
        "report_html":        None,
    })

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
        "col_mappings":    col_mappings,
        "coherence":       coherence,
    }


# ── Endpoint 1b: Override del format de timestamp ────────────────────────────

@app.post("/api/set-date-format")
def set_date_format(req: DateFormatRequest):
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
def classify(req: ClassifyRequest):
    sess = _get_session(req.session_id)
    sess["classifications"] = req.classifications
    quasi = [k for k, v in req.classifications.items() if v == "quasi_id"]
    return {"ok": True, "quasi_profiles": [i for i in sess["items"] if i["name"] in quasi]}


# ── Endpoint 3: Generalitzacions ──────────────────────────────────────────────

@app.post("/api/set-generalizations")
def set_generalizations(req: GeneralizationConfig):
    sess   = _get_session(req.session_id)
    errors = _validate_generalizations(req.generalizations)
    if errors:
        raise HTTPException(400, detail=" | ".join(errors))
    sess["generalizations"] = req.generalizations
    return {"ok": True}


# ── Endpoint 4: Simulació de k ────────────────────────────────────────────────

@app.post("/api/simulate-k")
def simulate_k(req: SimulateKRequest):
    sess = _get_session(req.session_id)
    if not sess["classifications"]:
        raise HTTPException(400, "Cal classificar els ítems primer.")
    try:
        # Simulem sobre el dataset combinat (sense hash: no afecta els grups)
        df_t, quasi, _, _, _ = _transform(sess)

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
def anonymize(req: AnonymizeRequest):
    sess = _get_session(req.session_id)
    if req.k < 2:
        raise HTTPException(400, "k ha de ser ≥ 2.")
    if not sess["classifications"]:
        raise HTTPException(400, "Cal classificar els ítems primer.")
    try:
        classifications = sess["classifications"]

        # ── Procés sobre el dataset combinat ──────────────────────────────────
        # Els índexs de df_original es conserven a tot el pipeline: s'usen per
        # recuperar la columna _source_file sobre el df anonimitzat.
        df_t = sess["df_original"]
        df_core, quasi, generalizations, imputation_log, generalization_log = _transform(sess)

        k_result = apply_k_anonymity(df_core, quasi, req.k)
        metrics  = compute_metrics(df_core, k_result["df_anonymized"], quasi, k_result)

        # Hash al final de tot, un cop el dataset és coherent, agrupat i
        # k-anònim: només es pseudonimitzen els registres que es publiquen, i
        # amb la mateixa clau de sessió per a tots els fitxers, de manera que un
        # pacient conserva el mateix H-… a cada taula de sortida.
        df_anon = hash_patient_ids(k_result["df_anonymized"], sess["hash_key"])

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

        sess["dfs_anonymized"]     = dfs_anonymized
        sess["metrics"]            = metrics
        sess["imputation_log"]     = imputation_log
        sess["generalization_log"] = generalization_log
        sess["applied_generalizations"] = generalizations

        # ── Generar informes ──────────────────────────────────────────────────
        now_str       = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        all_items     = [i["name"] for i in sess["items"]]
        filenames_str = ", ".join(sess["filenames"])
        lang          = req.lang if req.lang in _REPORT_TITLES else "es"

        sess["report_md"] = generate_markdown_report(
            lang               = lang,
            filename           = filenames_str,
            col_mappings       = sess["col_mappings"],
            coherence          = sess["coherence"],
            classifications    = classifications,
            generalizations    = generalizations,
            imputation_log     = imputation_log,
            generalization_log = generalization_log,
            metrics            = metrics,
            date_range         = sess["date_range"],
            all_items          = all_items,
            version            = __version__,
        )
        sess["report_html"] = generate_html_report(
            markdown_text      = sess["report_md"],
            title              = _REPORT_TITLES[lang],
            filename           = filenames_str,
            generated_at       = now_str,
            tool               = f"Datathon Anonymizer v{__version__}",
            confidential_label = _CONFIDENTIAL[lang],
            lang               = lang,
        )

        result = {k: v for k, v in metrics.items() if not isinstance(v, pd.DataFrame)}
        result["imputation_log"]     = imputation_log
        result["generalization_log"] = generalization_log
        result["n_files"]            = len(sess["filenames"])
        result["filenames"]          = sess["filenames"]
        return _to_json_safe(result)

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, detail=str(e))


# ── Descàrregues ──────────────────────────────────────────────────────────────

@app.get("/api/download/csv/{session_id}")
def download_csv(session_id: str):
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
        return _stream(csv_bytes, "text/csv; charset=utf-8", _stem(fname) + "_anonymized.csv")
    else:
        csv_map: dict[str, bytes] = {}
        for fname, df in dfs.items():
            csv_map[_stem(fname) + "_anonymized.csv"] = df.to_csv(index=False).encode("utf-8-sig")
        zip_bytes = _build_zip(csv_map)
        return _stream(zip_bytes, "application/zip", "datasets_anonymized.zip")


def _report_filename(filenames: list[str], ext: str) -> str:
    """
    Per a un sol fitxer pujat, l'informe pren el seu nom («dataset_X_report.html»).
    Per a multi-fitxer, un nom genèric («anonymization_report.html») per evitar
    que sembli que l'informe només cobreix el primer fitxer.
    """
    if filenames and len(filenames) == 1:
        return _stem(filenames[0]) + f"_report.{ext}"
    return f"anonymization_report.{ext}"


@app.get("/api/download/report/html/{session_id}")
def download_html(session_id: str):
    sess = _get_session(session_id)
    if not sess.get("report_html"):
        raise HTTPException(400, "Cal executar l'anonimització primer.")
    return _stream(sess["report_html"], "text/html; charset=utf-8",
                   _report_filename(sess["filenames"], "html"))


@app.get("/api/download/report/md/{session_id}")
def download_md(session_id: str):
    sess = _get_session(session_id)
    if not sess.get("report_md"):
        raise HTTPException(400, "Cal executar l'anonimització primer.")
    return _stream(sess["report_md"], "text/markdown; charset=utf-8",
                   _report_filename(sess["filenames"], "md"))


@app.get("/api/download/report/{session_id}")
def download_json(session_id: str):
    sess = _get_session(session_id)
    if sess["metrics"] is None:
        raise HTTPException(400, "Cal executar l'anonimització primer.")
    report = {
        "tool_version":       __version__,
        "filenames":          sess["filenames"],
        "col_mappings":       sess["col_mappings"],
        "coherence":          sess["coherence"],
        "date_format":        sess.get("date_format"),
        "date_range":         sess.get("date_range"),
        "patient_hash":       "HMAC-SHA256, per-session random key (not retained), truncated to 12 hex, prefix H-",
        "classifications":    sess["classifications"],
        "generalizations":    sess.get("applied_generalizations", {}),
        "imputation_log":     sess["imputation_log"],
        "generalization_log": sess["generalization_log"],
        "metrics":            sess["metrics"],
    }
    return _stream(
        json.dumps(_to_json_safe(report), ensure_ascii=False, indent=2),
        "application/json", "anonymization_report.json",
    )


@app.delete("/api/session/{session_id}")
def delete_session(session_id: str):
    with _sessions_lock:
        sessions.pop(session_id, None)
    return {"ok": True}
