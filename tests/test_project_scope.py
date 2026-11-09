"""
Post-Datathon InCa / TSI scope (v4.2.0):

  - only the 4 format columns travel: anything else is dropped at upload,
    reported by name, and never reaches any output
  - the DPO report describes the project environment set by the Data Use
    Agreement, not the June 2026 datathon
"""
import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
LEAK = "Juan Perez llama al 600123123"


def _rows(sep=","):
    out = []
    for p in range(1, 13):
        pid = f"{p:04d}"
        d = "2024-03-%02d 09:15" % (p % 25 + 1)
        out.append(sep.join([pid, d, "Edad", "70"]))
        out.append(sep.join([pid, d, "Sexo", "F" if p % 2 else "M"]))
        out.append(sep.join([pid, d, "Barthel", str(40 + p)]))
    return out


def _with_extra(head):
    return head + ",observaciones\n" + "\n".join(r + "," + LEAK for r in _rows()) + "\n"


def _finish(data, lang="es"):
    sid = data["session_id"]
    cl = {i["name"]: ("quasi_id" if i["name"] == "Edad" else "non_id") for i in data["items"]}
    assert client.post("/api/classify", json={"session_id": sid, "classifications": cl}).status_code == 200
    gens = {"Edad": {"type": "bins", "bins": [0, 65, 120], "labels": ["<65", "65+"]}}
    assert client.post("/api/set-generalizations", json={"session_id": sid, "generalizations": gens}).status_code == 200
    r = client.post("/api/anonymize", json={"session_id": sid, "k": 2, "lang": lang})
    assert r.status_code == 200, r.text
    return sid


def _upload(files):
    r = client.post("/api/upload", files=[("files", (n, c.encode(), "text/csv")) for n, c in files.items()])
    assert r.status_code == 200, r.text
    return r.json()


def _text(resp):
    return resp.content.decode("utf-8-sig")


def test_extra_column_never_reaches_any_output():
    data = _upload({"dataset_AH.csv": _with_extra("patient_id,fecha,variable,valor")})
    assert data["coherence"]["ignored_columns"] == {"dataset_AH.csv": ["observaciones"]}
    assert data["coherence"]["n_ignored_columns"] == 1
    assert data["preview"]["columns"] == ["pacient", "data", "item", "valor"]

    sid = _finish(data)
    csv = _text(client.get(f"/api/download/csv/{sid}"))
    assert csv.splitlines()[0] == "pacient,data,item,valor"
    for path in ("csv/", "report/html/", "report/md/", "report/"):
        assert LEAK not in _text(client.get(f"/api/download/{path}{sid}"))


def test_extra_column_dropped_after_confirmed_mapping():
    data = _upload({"d.csv": _with_extra("col_a,col_b,col_c,col_d")})
    assert data["status"] == "needs_mapping"
    r = client.post("/api/confirm-mapping", json={
        "session_id": data["session_id"],
        "mappings": {"d.csv": {"pacient": "col_a", "data": "col_b", "item": "col_c", "valor": "col_d"}},
    })
    assert r.status_code == 200, r.text
    sid = _finish(r.json())
    assert _text(client.get(f"/api/download/csv/{sid}")).splitlines()[0] == "pacient,data,item,valor"


def test_extra_column_dropped_in_every_file_of_a_zip():
    data = _upload({
        "AH_D1.csv": "patient_id,fecha,variable,valor,nota\n" + "\n".join(r + "," + LEAK for r in _rows() if "Sexo" not in r) + "\n",
        "AH_D5.csv": "patient_id,fecha,variable,valor\n" + "\n".join(r for r in _rows() if "Sexo" in r) + "\n",
    })
    assert data["coherence"]["ignored_columns"] == {"AH_D1.csv": ["nota"]}
    sid = _finish(data)
    zf = zipfile.ZipFile(io.BytesIO(client.get(f"/api/download/csv/{sid}").content))
    assert sorted(zf.namelist()) == ["AH_D1_anonymized.csv", "AH_D5_anonymized.csv"]
    for name in zf.namelist():
        text = zf.read(name).decode("utf-8-sig")
        assert text.splitlines()[0] == "pacient,data,item,valor"
        assert LEAK not in text


def test_file_with_only_the_format_columns_reports_nothing_ignored():
    data = _upload({"d.csv": "patient_id,fecha,variable,valor\n" + "\n".join(_rows()) + "\n"})
    assert data["coherence"]["ignored_columns"] == {}
    assert data["coherence"]["n_ignored_columns"] == 0


def test_output_keeps_the_care_line_from_the_file_name():
    data = _upload({"dataset_LE.csv": "patient_id,fecha,variable,valor\n" + "\n".join(_rows()) + "\n"})
    sid = _finish(data)
    assert "dataset_LE_anonymized.csv" in client.get(f"/api/download/csv/{sid}").headers["content-disposition"]


@pytest.mark.parametrize("lang,required", [
    ("es", ["post-Datathon InCa", "EU Health Hub", "Red SARA", "SharePoint", "31 de mayo de 2027", "Columnas ignoradas"]),
    ("ca", ["post-Datathon InCa", "EU Health Hub", "Red SARA", "SharePoint", "31 de maig de 2027", "Columnes ignorades"]),
    ("en", ["post-Datathon InCa", "EU Health Hub", "Red SARA", "SharePoint", "31 May 2027", "Ignored columns"]),
])
def test_report_describes_the_project_environment(lang, required):
    data = _upload({"dataset_AH.csv": _with_extra("patient_id,fecha,variable,valor")})
    sid = _finish(data, lang)
    md = _text(client.get(f"/api/download/report/md/{sid}"))
    for text in required:
        assert text in md, text
    assert "observaciones" in md
    for stale in ("Datathon Anonymizer", "SFTP", "Madrid", "muestra aleatoria", "mostra aleatòria",
                  "random sample", "uso en el Datathon", "ús en el Datathon", "use in the Datathon",
                  "no exportables", "Non-exportable"):
        assert stale not in md, stale
