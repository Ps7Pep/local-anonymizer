"""
report_html.py
--------------
Converteix l'informe Markdown a un document HTML estilitzat i autònom
(tot el CSS inclòs inline) pensat per ser imprès o exportat a PDF
des del navegador (Ctrl+P / Imprimir → Desar com a PDF).

No requereix cap dependència externa: usa la llibreria `markdown`
que ja forma part de l'entorn.
"""

import markdown as _md_lib


_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,wght@0,300;0,400;0,600;0,700;1,400&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --accent:   #004e8c;
  --accent2:  #006bb3;
  --border:   #d0dce8;
  --bg:       #ffffff;
  --surface:  #f4f8fc;
  --text:     #1a2030;
  --muted:    #5a6a80;
  --success:  #1a7a40;
  --danger:   #b52020;
  --amber:    #7a5000;
  --warn-bg:  #fffbf0;
  --warn-bdr: #e0c060;
}

*, *::before, *::after { box-sizing: border-box; }

html { font-size: 16px; }

body {
  font-family: 'Source Serif 4', Georgia, serif;
  font-size: 0.95rem;
  line-height: 1.75;
  color: var(--text);
  background: var(--bg);
  margin: 0;
  padding: 0;
}

/* ── Layout ──────────────────────────────────────────────────── */
.page-wrap {
  max-width: 820px;
  margin: 0 auto;
  padding: 3rem 3.5rem;
}

/* ── Cover ───────────────────────────────────────────────────── */
.cover {
  background: linear-gradient(135deg, #002850 0%, #004e8c 100%);
  color: white;
  padding: 3.5rem;
  border-radius: 8px;
  margin-bottom: 3rem;
  position: relative;
  overflow: hidden;
}
.cover::before {
  content: '';
  position: absolute;
  top: 0; left: 0;
  width: 6px; height: 100%;
  background: #00c2d4;
}
.cover h1 {
  font-size: 1.9rem;
  font-weight: 700;
  margin: 0 0 0.75rem 1rem;
  line-height: 1.25;
  letter-spacing: -0.02em;
  color: white;
  border: none;
  padding: 0;
}
.cover h1::after { display: none; }
.cover .meta {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.78rem;
  color: rgba(255,255,255,0.6);
  margin-left: 1rem;
  line-height: 1.8;
}
.cover .meta strong { color: rgba(255,255,255,0.9); }
.confidential {
  display: inline-block;
  margin-top: 1.25rem;
  margin-left: 1rem;
  background: rgba(255,255,255,0.12);
  border: 1px solid rgba(255,255,255,0.25);
  color: rgba(255,255,255,0.8);
  font-size: 0.72rem;
  font-family: 'JetBrains Mono', monospace;
  letter-spacing: 0.1em;
  padding: 0.25rem 0.75rem;
  border-radius: 3px;
  text-transform: uppercase;
}

/* ── Headings ────────────────────────────────────────────────── */
h1, h2, h3, h4 {
  font-family: 'Source Serif 4', Georgia, serif;
  color: var(--text);
  margin-top: 2.5rem;
  margin-bottom: 0.75rem;
  line-height: 1.3;
}
h1 { font-size: 1.6rem; font-weight: 700; }
h2 {
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--accent);
  padding-bottom: 0.4rem;
  border-bottom: 2px solid var(--accent);
  margin-top: 3rem;
}
h2::before {
  content: '';
  display: inline-block;
  width: 4px;
  height: 1em;
  background: #00c2d4;
  margin-right: 0.5rem;
  vertical-align: middle;
  border-radius: 2px;
}
h3 {
  font-size: 1rem;
  font-weight: 600;
  color: var(--accent2);
  margin-top: 2rem;
}
h4 {
  font-size: 0.92rem;
  font-weight: 600;
  color: var(--muted);
  margin-top: 1.5rem;
  font-style: italic;
}

/* ── Paragraphs ──────────────────────────────────────────────── */
p {
  margin: 0 0 1rem;
}

/* ── Tables ──────────────────────────────────────────────────── */
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
  margin: 1.25rem 0;
  font-family: 'Source Serif 4', Georgia, serif;
}
thead tr {
  background: var(--accent);
  color: white;
}
thead th {
  padding: 0.55rem 0.9rem;
  text-align: left;
  font-weight: 600;
  font-size: 0.8rem;
  letter-spacing: 0.03em;
  border: none;
}
tbody tr:nth-child(even) { background: var(--surface); }
tbody tr:hover { background: #e8f0f8; }
tbody td {
  padding: 0.5rem 0.9rem;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
  color: var(--text);
}
tbody tr:last-child td { border-bottom: none; }

/* ── Code ────────────────────────────────────────────────────── */
code {
  font-family: 'JetBrains Mono', 'Courier New', monospace;
  font-size: 0.82em;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 3px;
  padding: 0.1em 0.35em;
  color: var(--accent2);
}
pre {
  background: #f0f4f8;
  border: 1px solid var(--border);
  border-left: 4px solid var(--accent);
  border-radius: 4px;
  padding: 1rem 1.25rem;
  overflow-x: auto;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.82rem;
  line-height: 1.6;
  color: var(--text);
  margin: 1rem 0;
}
pre code {
  background: none;
  border: none;
  padding: 0;
  font-size: inherit;
  color: inherit;
}

/* ── Blockquote (advertiments) ───────────────────────────────── */
blockquote {
  background: var(--warn-bg);
  border-left: 4px solid var(--warn-bdr);
  margin: 1.25rem 0;
  padding: 0.75rem 1.25rem;
  border-radius: 0 4px 4px 0;
  color: var(--amber);
  font-style: italic;
  font-size: 0.9rem;
}
blockquote p { margin: 0; color: var(--amber); }

/* ── Lists ───────────────────────────────────────────────────── */
ul, ol {
  padding-left: 1.75rem;
  margin: 0.5rem 0 1rem;
}
li {
  margin-bottom: 0.4rem;
  line-height: 1.65;
}

/* ── Checklist ───────────────────────────────────────────────── */
.checklist {
  background: #f0faf5;
  border: 1px solid #a0d4b8;
  border-radius: 6px;
  padding: 1.25rem 1.5rem;
  margin: 1rem 0;
}
.checklist li {
  list-style: none;
  padding-left: 1.75rem;
  position: relative;
  margin-bottom: 0.6rem;
}
.checklist li::before {
  content: '☐';
  position: absolute;
  left: 0;
  color: var(--success);
  font-size: 1rem;
}

/* ── HR ──────────────────────────────────────────────────────── */
hr {
  border: none;
  border-top: 1px solid var(--border);
  margin: 2rem 0;
}

/* ── Strong / em ─────────────────────────────────────────────── */
strong { font-weight: 700; color: var(--text); }
em { font-style: italic; color: var(--muted); }

/* ── Print ───────────────────────────────────────────────────── */
@media print {
  body { font-size: 0.88rem; }
  .page-wrap { padding: 1.5rem 2rem; max-width: 100%; }
  .cover { border-radius: 0; margin-bottom: 2rem; }
  h2 { page-break-before: auto; }
  h2, h3 { page-break-after: avoid; }
  table, pre, blockquote { page-break-inside: avoid; }
  thead { display: table-header-group; }
  a { color: var(--accent); text-decoration: none; }
}

/* ── Page numbers (print only) ───────────────────────────────── */
@page {
  size: A4;
  margin: 2cm 2.5cm;
  @bottom-center {
    content: counter(page) " / " counter(pages);
    font-family: 'JetBrains Mono', monospace;
    font-size: 8pt;
    color: #888;
  }
}
"""


def generate_html_report(
    markdown_text: str,
    title: str,
    filename: str,
    generated_at: str,
    tool: str = "Datathon Anonymizer v2.0",
    confidential_label: str = "DOCUMENT CONFIDENCIAL · ÚS INTERN",
) -> str:
    """
    Converteix el text Markdown de l'informe a un HTML autònom i estilitzat.

    El document resultant:
    - Té tot el CSS inclòs inline (no requereix connexió a internet per visualitzar-se)
    - Carrega les fonts de Google Fonts (necessita connexió per veure-les en tota qualitat,
      però degrada graciosament a Georgia/serif sense connexió)
    - Imprimeix correctament des del navegador (Ctrl+P → Desar com a PDF)
    - No mostra els símbols Markdown (#, ##, **, etc.)
    """

    # Eliminem la primera línia (# Títol) perquè la posem a la portada
    lines = markdown_text.strip().split('\n')
    if lines and lines[0].startswith('# '):
        title_from_md = lines[0][2:].strip()
        body_md = '\n'.join(lines[1:]).strip()
    else:
        title_from_md = title
        body_md = markdown_text

    # Eliminem les metadades de capçalera (línies **Generat el:**, etc.)
    body_lines = body_md.split('\n')
    clean_lines = []
    skip_meta = True
    for line in body_lines:
        if skip_meta and (line.startswith('**') or line.strip() == '' or line.startswith('---')):
            if line.strip() == '---':
                skip_meta = False
            continue
        else:
            skip_meta = False
        clean_lines.append(line)
    body_md = '\n'.join(clean_lines)

    # Convertim Markdown → HTML
    body_html = _md_lib.markdown(
        body_md,
        extensions=['tables', 'toc', 'fenced_code', 'nl2br', 'sane_lists'],
        extension_configs={
            'toc': {'title': '', 'toc_depth': 3},
        }
    )

    # Post-processem: convertim checkboxes [ ] i [x]
    body_html = body_html.replace(
        '<li>[ ] ', '<li class="check-item">☐ '
    ).replace(
        '<li>[x] ', '<li class="check-item">☑ '
    )

    # Post-processem advertiments (⚠ en blockquote)
    # (ja els converteix markdown en <blockquote>)

    html = f"""<!DOCTYPE html>
<html lang="ca">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title_from_md}</title>
  <style>{_CSS}</style>
</head>
<body>
<div class="page-wrap">

  <!-- PORTADA -->
  <div class="cover">
    <h1>{title_from_md}</h1>
    <div class="meta">
      <strong>{filename}</strong><br>
      {generated_at}<br>
      {tool}
    </div>
    <div class="confidential">{confidential_label}</div>
  </div>

  <!-- CONTINGUT DE L'INFORME -->
  {body_html}

</div>
</body>
</html>"""

    return html
