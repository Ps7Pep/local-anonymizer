/**
 * app.js — Datathon Anonymizer v2
 * --------------------------------
 * Flux: Càrrega → Classificació → Generalització → K-anonimitat → Resultats
 */

'use strict';

// ── Estat ─────────────────────────────────────────────────────────────────────
var State = {
  sessionId:       null,
  items:           [],          // perfils dels ítems [{name, type, n_unique, values, stats, ...}]
  classifications: {},          // { item → 'quasi_id' | 'non_id' }
  generalizations: {},          // { item → { type, bins?, labels?, mapping?, unmapped_label? } }
  dateFormat:      'iso',       // 'iso' | 'dayfirst' | 'monthfirst'
  dateDetection:   null,        // { best, n_total, candidates, samples }
  nFiles:          1,           // nombre de CSVs pujats
  multifileConfirmed: false,    // gate per a multi-fitxer: confirmació explícita
};

// ── Utils ─────────────────────────────────────────────────────────────────────
function el(id)    { return document.getElementById(id); }
function esc(str)  {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function san(str)  { return String(str).replace(/[^a-zA-Z0-9_-]/g,'_'); }
function showErr(id, msg) { var e=el(id); if(e){e.textContent=msg; e.style.display='block';} }
function hideErr(id)      { var e=el(id); if(e) e.style.display='none'; }

function quasiItems() {
  return Object.entries(State.classifications).filter(function(e){return e[1]==='quasi_id';}).map(function(e){return e[0];});
}

// ── API ───────────────────────────────────────────────────────────────────────
async function api(path, method, body) {
  var opts = { method: method||'GET', headers: {} };
  if (body) { opts.headers['Content-Type']='application/json'; opts.body=JSON.stringify(body); }
  var res  = await fetch(path, opts);
  // Llegim primer com a text: si el servidor torna HTML/plain (cas del 500
  // default de Starlette), no volem petar amb "Unexpected token" — volem
  // ensenyar a l'usuari què ha passat.
  var raw  = await res.text();
  var data = null;
  try { data = raw ? JSON.parse(raw) : null; } catch (e) { /* not JSON */ }
  if (!res.ok) {
    var msg = (data && data.detail) ? data.detail
            : (raw ? raw.slice(0, 300) : 'Error '+res.status);
    throw new Error('['+res.status+'] '+msg);
  }
  return data;
}

// ── Navegació ─────────────────────────────────────────────────────────────────
function goToPhase(n) {
  document.querySelectorAll('.phase').forEach(function(p){ p.classList.remove('active'); });
  document.querySelectorAll('.step-item').forEach(function(s,i){
    s.classList.remove('active','done');
    if (i+1 < n)  s.classList.add('done');
    if (i+1 === n) s.classList.add('active');
  });
  el('phase-'+n).classList.add('active');
  window.scrollTo({top:0, behavior:'smooth'});

  if (n===2) renderClassify();
  if (n===3) renderGeneralizations();
}

// ── FASE 1 ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
  var zone  = el('upload-zone');
  var input = el('file-input');

  zone.addEventListener('dragover',  function(e){ e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', function(){ zone.classList.remove('drag-over'); });
  zone.addEventListener('drop', function(e){
    e.preventDefault(); zone.classList.remove('drag-over');
    var files = Array.from(e.dataTransfer.files).filter(function(f){ return f.name.toLowerCase().endsWith('.csv'); });
    if (files.length) doUpload(files);
  });
  input.addEventListener('change', function(){
    var files = Array.from(input.files);
    if (files.length) doUpload(files);
  });

  setLang('es');
});

async function doUpload(files) {
  // Validar que tots siguin CSV
  var nonCsv = files.filter(function(f){ return !f.name.toLowerCase().endsWith('.csv'); });
  if (nonCsv.length) {
    showErr('upload-error', t('errorOnlyCsv') + ': ' + nonCsv.map(function(f){return f.name;}).join(', '));
    return;
  }
  hideErr('upload-error');
  el('drop-title').textContent = '⏳ ' + t('uploading') + '...';

  // Amaguem qualsevol panel d'una pujada anterior
  el('upload-results').style.display = 'none';
  var mc = el('mapping-confirm-card'); if (mc) mc.style.display = 'none';

  // Mostrar llista de fitxers seleccionats
  var fl = el('files-list');
  fl.style.display = 'block';
  fl.innerHTML = '<div style="font-size:0.78rem;color:var(--text-muted);margin-bottom:0.3rem;">' +
    files.length + ' ' + t('filesSelected') + ':</div>' +
    files.map(function(f){
      return '<span style="display:inline-block;background:var(--surface2);border:1px solid var(--border);' +
        'border-radius:var(--r-sm);padding:0.15rem 0.55rem;margin:0.15rem;font-size:0.78rem;' +
        'font-family:var(--mono);color:var(--accent);">' + esc(f.name) + '</span>';
    }).join('');

  var fd = new FormData();
  files.forEach(function(f){ fd.append('files', f); });

  try {
    var res  = await fetch('/api/upload', { method:'POST', body:fd });
    var data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error');

    if (data.status === 'needs_mapping') {
      State.sessionId = data.session_id;
      renderMappingConfirm(data);
      return;
    }

    _applyUploadResponse(data);
  } catch(err) {
    showErr('upload-error', err.message);
    el('files-list').style.display = 'none';
  } finally {
    el('drop-title').setAttribute('data-lang','dropZoneTitle');
    el('drop-title').textContent = t('dropZoneTitle');
  }
}

function _applyUploadResponse(data) {
  State.sessionId          = data.session_id;
  State.items              = data.items;
  State.nFiles             = data.n_files || 1;
  State.dateFormat         = data.date_format    || 'iso';
  State.dateDetection      = data.date_detection || null;
  State.multifileConfirmed = false;

  State.classifications = {};
  data.items.forEach(function(item){ State.classifications[item.name] = 'non_id'; });

  var mc = el('mapping-confirm-card'); if (mc) mc.style.display = 'none';

  renderUpload(data);
  renderDateFormat();
  renderMultifileConfirm(data);
  updateContinueGate();
}

// ── Confirmació del mapatge de columnes ───────────────────────────────────────
function renderMappingConfirm(data) {
  var card = el('mapping-confirm-card');
  if (!card) return;
  card.style.display = 'block';

  var canonicals = ['pacient', 'data', 'item', 'valor'];

  var html = (data.files || []).map(function(f) {
    var ok       = !!f.alias_complete;
    var statusEm = ok ? '✅' : '⚠️';
    var statusTx = ok ? t('mapAliasOk') : t('mapNeedsReview');

    var previewHead = (f.preview.columns || []).map(function(c){ return '<th>' + esc(c) + '</th>'; }).join('');
    var previewRows = (f.preview.rows    || []).map(function(row){
      return '<tr>' + row.map(function(cell){ return '<td>' + esc(String(cell)) + '</td>'; }).join('') + '</tr>';
    }).join('');

    var selectors = canonicals.map(function(canon) {
      var sel = f.proposed_mapping[canon] || '';
      var opts = (f.raw_columns || []).map(function(rc) {
        return '<option value="' + esc(rc) + '"' + (rc === sel ? ' selected' : '') + '>' + esc(rc) + '</option>';
      }).join('');
      return '<div class="input-group">' +
        '<label style="font-family:var(--mono); color:var(--accent);">' + esc(canon) + '</label>' +
        '<select class="input-field map-select" data-file="' + esc(f.filename) + '" data-canonical="' + canon + '">' +
        opts +
        '</select>' +
        '</div>';
    }).join('');

    return '<div style="margin-bottom:1.4rem; padding-bottom:1.1rem; border-bottom:1px solid var(--border);">' +
      '<div style="font-family:var(--mono); color:var(--accent); font-weight:600; margin-bottom:0.45rem;">' +
        statusEm + ' ' + esc(f.filename) +
        ' <span style="color:var(--text-muted); font-weight:400; font-size:0.78rem;">— ' + esc(statusTx) + '</span>' +
      '</div>' +
      '<div class="table-wrap" style="margin-bottom:0.7rem;">' +
        '<table><thead><tr>' + previewHead + '</tr></thead><tbody>' + previewRows + '</tbody></table>' +
      '</div>' +
      '<div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:0.6rem;">' +
        selectors +
      '</div>' +
    '</div>';
  }).join('');

  el('mapping-confirm-body').innerHTML = html;
}

async function confirmMapping() {
  hideErr('mapping-error');

  var mappings = {};
  document.querySelectorAll('#mapping-confirm-body .map-select').forEach(function(sel) {
    var fname = sel.getAttribute('data-file');
    var canon = sel.getAttribute('data-canonical');
    if (!mappings[fname]) mappings[fname] = {};
    mappings[fname][canon] = sel.value;
  });

  // Validació local: una columna no es pot reutilitzar per a dos canonicals
  var dup = null;
  Object.keys(mappings).forEach(function(fname) {
    var vals = Object.values(mappings[fname]);
    if (new Set(vals).size !== vals.length) dup = fname;
  });
  if (dup) {
    showErr('mapping-error', t('mapDupErr') + ' (' + dup + ')');
    return;
  }

  try {
    var data = await api('/api/confirm-mapping', 'POST', {
      session_id: State.sessionId,
      mappings:   mappings,
    });
    _applyUploadResponse(data);
  } catch(err) {
    showErr('mapping-error', err.message);
  }
}

function renderUpload(data) {
  // Stats — afegim nº de fitxers si n'hi ha més d'un
  var dr = data.date_range;
  var dateStr = (dr && dr.min && dr.max) ? dr.min+' → '+dr.max : '—';
  var filesStr = data.n_files > 1 ? data.n_files + ' ' + t('files') : (data.filenames ? data.filenames[0] : '—');
  el('stats-grid').innerHTML =
    statBox(filesStr,                           t('statFiles'), '0.85rem') +
    statBox(data.n_patients.toLocaleString(),   t('statPatients')) +
    statBox(data.n_records.toLocaleString(),    t('statRecords')) +
    statBox(data.n_items,                       t('statItems'));

  // Items table
  el('items-tbody').innerHTML = data.items.map(function(item){
    var sample = '';
    if (item.type==='categorical' && item.values) {
      sample = item.values.slice(0,4).map(function(v){ return '<span class="tag">'+esc(v)+'</span>'; }).join(' ');
    } else if (item.stats) {
      sample = '<span class="tag">'+item.stats.min+'</span> … <span class="tag">'+item.stats.max+'</span>';
    }
    return '<tr>' +
      '<td style="color:var(--accent);font-family:var(--mono);font-weight:500;">'+esc(item.name)+'</td>' +
      '<td><span class="type-pill type-'+item.type+'">'+t(item.type)+'</span></td>' +
      '<td style="text-align:right;">'+item.n_unique+'</td>' +
      '<td style="text-align:right;">'+item.n_records+'</td>' +
      '<td>'+sample+'</td>' +
      '</tr>';
  }).join('');

  // Preview
  var pt = el('preview-table');
  pt.querySelector('thead').innerHTML = '<tr>'+data.preview.columns.map(function(c){ return '<th>'+esc(c)+'</th>'; }).join('')+'</tr>';
  pt.querySelector('tbody').innerHTML = data.preview.rows.map(function(row){
    return '<tr>'+row.map(function(cell){ return '<td>'+esc(String(cell))+'</td>'; }).join('')+'</tr>';
  }).join('');

  el('upload-results').style.display = 'block';
}

function statBox(val, lbl, fontSize) {
  var fs = fontSize ? 'font-size:'+fontSize+';' : '';
  return '<div class="stat-box"><div class="val" style="'+fs+'">'+val+'</div><div class="lbl">'+lbl+'</div></div>';
}

// ── Format de timestamp ───────────────────────────────────────────────────────
function renderDateFormat() {
  var det = State.dateDetection;
  if (!det) { el('date-format-card').style.display = 'none'; return; }
  el('date-format-card').style.display = 'block';

  // Botons actius segons el format triat
  document.querySelectorAll('#date-format-toggle .type-btn').forEach(function(b){
    b.classList.toggle('active', b.getAttribute('data-fmt') === State.dateFormat);
  });

  // Mostres parsejades
  var tbody = el('date-samples-table').querySelector('tbody');
  tbody.innerHTML = (det.samples || []).map(function(s){
    var ok    = s.ok && s.parsed;
    var icon  = ok ? '✅' : '❌';
    var pcell = ok ? esc(s.parsed) : '<span style="color:var(--danger);">' + t('dateUnparseable') + '</span>';
    return '<tr>' +
      '<td style="font-family:var(--mono);">' + esc(s.raw) + '</td>' +
      '<td style="font-family:var(--mono);">' + icon + '&nbsp;' + pcell + '</td>' +
      '</tr>';
  }).join('');

  // Avís si hi ha files no parsejables amb el format actiu
  var cand     = (det.candidates || {})[State.dateFormat] || {};
  var nFailed  = cand.n_failed || 0;
  var nTotal   = det.n_total   || 0;
  var hasTime  = cand.has_time;

  var warning = el('date-format-warning');
  if (nFailed > 0) {
    warning.style.display = 'block';
    warning.innerHTML = '⚠ ' + t('dateNatWarn1') + ' <strong>' + nFailed + '</strong> ' +
                        t('dateNatWarn2') + ' ' + nTotal + ' ' + t('dateNatWarn3');
  } else {
    warning.style.display = 'none';
  }

  // Estadístiques sota la taula
  var statsLine = nTotal + ' ' + t('dateStatRows') + ' · ' +
                  (nTotal - nFailed) + ' ' + t('dateStatOk') + ' · ' +
                  nFailed + ' ' + t('dateStatFail') + ' · ' +
                  (hasTime ? t('dateStatHasTime') : t('dateStatNoTime'));
  el('date-format-stats').textContent = statsLine;
}

// ── Confirmació multi-fitxer ──────────────────────────────────────────────────
function renderMultifileConfirm(data) {
  var card = el('multifile-confirm-card');
  if (!card) return;

  if (!data || (data.n_files || 1) < 2) {
    card.style.display = 'none';
    return;
  }
  card.style.display = 'block';
  el('multifile-n').textContent = data.n_files;

  // Taula amb estadístiques per fitxer
  var rows = (data.per_file_stats || []).map(function(s){
    return '<tr>' +
      '<td style="font-family:var(--mono);color:var(--accent);">' + esc(s.filename) + '</td>' +
      '<td style="text-align:right;">' + s.n_records.toLocaleString()  + '</td>' +
      '<td style="text-align:right;">' + s.n_patients.toLocaleString() + '</td>' +
      '<td style="text-align:right;">' + s.n_items.toLocaleString()    + '</td>' +
      '</tr>';
  }).join('');
  el('multifile-stats-table').querySelector('tbody').innerHTML = rows;

  // Resum d'overlap
  var rel = data.relationship || {};
  var nShared = rel.n_patients_shared_all || 0;
  var nUnion  = rel.n_patients_union      || 0;
  var pct     = rel.pct_patients_shared   || 0;
  var overlap = rel.overlapping_items     || [];

  var color = pct >= 90 ? 'var(--success)' : (pct >= 50 ? 'var(--amber)' : 'var(--danger)');
  var summary =
    '<div>' + t('mfSharedPatients') + ': <strong style="color:' + color + ';">' + nShared.toLocaleString() + '</strong>' +
    ' / ' + nUnion.toLocaleString() + ' (' + pct + '%)' +
    ' <span style="color:var(--text-muted);">— ' + t('mfSharedHint') + '</span></div>';

  if (overlap.length > 0) {
    var sample = overlap.slice(0, 5).map(esc).join(', ');
    var more   = overlap.length > 5 ? ' (+' + (overlap.length - 5) + ')' : '';
    summary +=
      '<div style="margin-top:0.4rem; color:var(--danger);">⚠ ' + t('mfOverlapWarn') +
      ' <strong>' + overlap.length + '</strong> ' + t('mfOverlapWarn2') + ': ' + sample + more + '</div>';
  }
  el('multifile-overlap-summary').innerHTML = summary;

  // Reset checkbox
  var cb = el('multifile-confirm-checkbox');
  if (cb) cb.checked = false;
  State.multifileConfirmed = false;
}

function updateContinueGate() {
  var cb  = el('multifile-confirm-checkbox');
  var btn = el('phase1-continue-btn');
  if (!btn) return;

  if (State.nFiles > 1) {
    State.multifileConfirmed = !!(cb && cb.checked);
    btn.disabled = !State.multifileConfirmed;
    btn.style.opacity = State.multifileConfirmed ? '1' : '0.5';
    btn.style.cursor  = State.multifileConfirmed ? 'pointer' : 'not-allowed';
  } else {
    btn.disabled = false;
    btn.style.opacity = '1';
    btn.style.cursor  = 'pointer';
  }
}

async function setDateFormat(fmt) {
  if (!State.sessionId) return;
  State.dateFormat = fmt;
  // Render òptic immediat dels botons; samples es refresquen amb la resposta del backend
  document.querySelectorAll('#date-format-toggle .type-btn').forEach(function(b){
    b.classList.toggle('active', b.getAttribute('data-fmt') === fmt);
  });
  try {
    var res = await api('/api/set-date-format', 'POST', {
      session_id:  State.sessionId,
      date_format: fmt,
    });
    State.dateDetection = res.date_detection;
    renderDateFormat();
  } catch(err) {
    showErr('upload-error', err.message);
  }
}

// ── FASE 2: Classificació ─────────────────────────────────────────────────────
function renderClassify() {
  var grid = el('classify-grid');
  grid.innerHTML = State.items.map(function(item) {
    var cls    = State.classifications[item.name] || 'non_id';
    var isQ    = cls === 'quasi_id';
    var sample = '';
    if (item.type==='categorical' && item.values) sample = item.values.slice(0,3).join(', ');
    else if (item.stats) sample = item.stats.min+' … '+item.stats.max;

    return '<div class="item-classify-row'+(isQ?' is-quasi':'') +'" id="row-'+san(item.name)+'">' +
      '<div>' +
        '<div class="item-name">'+esc(item.name)+'</div>' +
        '<div class="item-meta"><span class="type-pill type-'+item.type+'">'+t(item.type)+'</span> &nbsp;'+item.n_unique+' únics &nbsp;·&nbsp; '+esc(sample)+'</div>' +
      '</div>' +
      '<div class="role-toggle">' +
        '<button class="role-btn'+(isQ?' active-quasi':'')+'" onclick="setRole(\''+san(item.name)+'\',\''+esc(item.name)+'\',\'quasi_id\')" data-lang="roleQuasi">'+t('roleQuasi')+'</button>' +
        '<button class="role-btn'+(!isQ?' active-nonid':'')+'" onclick="setRole(\''+san(item.name)+'\',\''+esc(item.name)+'\',\'non_id\')"  data-lang="roleNonId">'+t('roleNonId')+'</button>' +
      '</div>' +
      '</div>';
  }).join('');
}

function setRole(rowId, itemName, role) {
  State.classifications[itemName] = role;
  var row = el('row-'+rowId);
  if (!row) return;
  row.classList.toggle('is-quasi', role==='quasi_id');
  var btns = row.querySelectorAll('.role-btn');
  btns[0].classList.toggle('active-quasi', role==='quasi_id');
  btns[0].classList.remove('active-nonid');
  btns[1].classList.toggle('active-nonid', role==='non_id');
  btns[1].classList.remove('active-quasi');
}

async function saveClassifications() {
  hideErr('classify-error');
  try {
    await api('/api/classify','POST',{
      session_id:      State.sessionId,
      classifications: State.classifications,
    });
    goToPhase(3);
  } catch(err) {
    showErr('classify-error', err.message);
  }
}

// ── FASE 3: Generalitzacions ──────────────────────────────────────────────────
function renderGeneralizations() {
  var quasi = quasiItems();
  el('no-quasi-alert').style.display = quasi.length===0 ? 'block' : 'none';

  var container = el('qi-blocks-container');
  container.innerHTML = '';

  quasi.forEach(function(itemName) {
    var profile = State.items.find(function(i){ return i.name===itemName; });
    if (!profile) return;
    container.appendChild(buildQiBlock(itemName, profile));
  });
}

function buildQiBlock(name, profile) {
  var block = document.createElement('div');
  block.className = 'qi-block';
  block.id = 'qi-block-'+san(name);

  var cfg         = State.generalizations[name] || {};
  var defaultType = profile.type==='numeric' ? 'bins' : 'mapping';
  var activeType  = cfg.type || defaultType;
  var cid         = san(name);

  block.innerHTML =
    '<div class="qi-block-header" onclick="toggleBlock(\''+cid+'\')">' +
      '<div>' +
        '<div class="qi-col-name">'+esc(name)+'</div>' +
        '<div class="qi-col-meta"><span class="type-pill type-'+profile.type+'">'+t(profile.type)+'</span>&nbsp; '+profile.n_unique+' valors únics</div>' +
      '</div>' +
      '<div class="qi-chevron open" id="chevron-'+cid+'">›</div>' +
    '</div>' +
    '<div class="qi-block-body open" id="body-'+cid+'">' +
      buildDistribution(profile) +
      '<div class="type-toggle">' +
        '<button class="type-btn'+(activeType==='bins'?' active':'')+'" onclick="switchType(\''+cid+'\',\''+esc(name)+'\',\'bins\')" data-lang="typeNumeric">'+t('typeNumeric')+'</button>' +
        '<button class="type-btn'+(activeType==='mapping'?' active':'')+'" onclick="switchType(\''+cid+'\',\''+esc(name)+'\',\'mapping\')" data-lang="typeCategorical">'+t('typeCategorical')+'</button>' +
      '</div>' +
      '<div id="qi-config-'+cid+'">' +
        buildTypeConfig(name, profile, activeType, cfg) +
      '</div>' +
    '</div>';

  return block;
}

function buildDistribution(profile) {
  if (profile.type==='categorical' && profile.value_counts) {
    var total = Object.values(profile.value_counts).reduce(function(a,b){return a+b;},0);
    var rows  = Object.entries(profile.value_counts).slice(0,12).map(function(e){
      var v=e[0], c=e[1], pct=Math.round(c/total*100);
      return '<div class="dist-row">' +
        '<div class="dist-label" title="'+esc(v)+'">'+esc(v)+'</div>' +
        '<div class="dist-bar"><div class="dist-fill" style="width:'+pct+'%;"></div></div>' +
        '<div class="dist-count">'+c+'</div>' +
        '</div>';
    }).join('');
    return '<div class="dist-wrap">'+rows+'</div>';
  }
  if (profile.type==='numeric' && profile.stats) {
    var s = profile.stats;
    return '<div style="font-size:0.78rem;color:var(--text-muted);margin-bottom:0.85rem;font-family:var(--mono);">' +
      'min: '+s.min+' &nbsp;·&nbsp; max: '+s.max+' &nbsp;·&nbsp; μ: '+s.mean+' &nbsp;·&nbsp; med: '+s.median +
      '</div>';
  }
  return '';
}

function buildTypeConfig(name, profile, type, cfg) {
  var cid = san(name);

  if (type==='bins') {
    var bins   = cfg.bins   ? cfg.bins.join(', ')   : '';
    var labels = cfg.labels ? cfg.labels.join(', ') : '';
    return '<div class="input-group">' +
        '<label data-lang="binsLabel">'+t('binsLabel')+'</label>' +
        '<input type="text" class="input-field" id="bins-'+cid+'" placeholder="0, 18, 40, 65, 120" value="'+esc(bins)+'">' +
        '<div class="input-help" data-lang="binsHelp">'+t('binsHelp')+'</div>' +
      '</div>' +
      '<div class="input-group">' +
        '<label data-lang="labelsLabel">'+t('labelsLabel')+'</label>' +
        '<input type="text" class="input-field" id="labels-'+cid+'" placeholder="0-17, 18-39, 40-64, 65+" value="'+esc(labels)+'">' +
        '<div class="input-help" data-lang="labelsHelp">'+t('labelsHelp')+'</div>' +
      '</div>';
  }

  if (type==='mapping') {
    var values          = (profile.values || []).slice(0, 50);
    var existingMapping = cfg.mapping || {};
    var unmapped        = cfg.unmapped_label || (LANG==='es' ? 'Otros' : LANG==='en' ? 'Others' : 'Altres');

    var rows = values.map(function(v) {
      return '<div class="mapping-grid">' +
        '<div class="mapping-orig" title="'+esc(v)+'">'+esc(v)+'</div>' +
        '<div class="mapping-arrow">→</div>' +
        '<input type="text" class="mapping-input" data-original="'+esc(v)+'" data-cid="'+cid+'" value="'+esc(existingMapping[v] !== undefined ? existingMapping[v] : v)+'" placeholder="...">' +
        '</div>';
    }).join('');

    return '<div class="input-help" style="margin-bottom:0.65rem;" data-lang="mappingHelp">'+t('mappingHelp')+'</div>' +
      rows +
      '<div class="input-group" style="margin-top:0.65rem;">' +
        '<label data-lang="unmappedLabel">'+t('unmappedLabel')+'</label>' +
        '<input type="text" class="input-field" id="unmapped-'+cid+'" value="'+esc(unmapped)+'">' +
      '</div>';
  }

  return '';
}

function toggleBlock(cid) {
  var body    = el('body-'+cid);
  var chevron = el('chevron-'+cid);
  var isOpen  = body.classList.contains('open');
  body.classList.toggle('open', !isOpen);
  chevron.classList.toggle('open', !isOpen);
}

function switchType(cid, name, type) {
  var profile = State.items.find(function(i){return i.name===name;});
  var cfg     = State.generalizations[name] || {};
  cfg.type    = type;
  State.generalizations[name] = cfg;

  // Actualitza botons
  var block = el('qi-block-'+cid);
  block.querySelectorAll('.type-btn').forEach(function(b){
    b.classList.toggle('active',
      (type==='bins'    && b.getAttribute('data-lang')==='typeNumeric') ||
      (type==='mapping' && b.getAttribute('data-lang')==='typeCategorical')
    );
  });

  el('qi-config-'+cid).innerHTML = buildTypeConfig(name, profile, type, cfg);
}

function collectGeneralizations() {
  quasiItems().forEach(function(name) {
    var cid     = san(name);
    var cfg     = State.generalizations[name] || {};
    var type    = cfg.type || ((State.items.find(function(i){return i.name===name;}) || {}).type==='numeric' ? 'bins' : 'mapping');

    if (type==='bins') {
      var bEl = el('bins-'+cid), lEl = el('labels-'+cid);
      if (bEl) cfg.bins   = bEl.value.split(',').map(function(s){return parseFloat(s.trim());}).filter(function(n){return !isNaN(n);});
      if (lEl) cfg.labels = lEl.value.split(',').map(function(s){return s.trim();}).filter(Boolean);
      cfg.type = 'bins';
    } else {
      var inputs  = document.querySelectorAll('[data-cid="'+cid+'"]');
      var mapping = {};
      inputs.forEach(function(inp){ if(inp.value.trim()) mapping[inp.dataset.original]=inp.value.trim(); });
      var unmEl = el('unmapped-'+cid);
      cfg.mapping        = mapping;
      cfg.unmapped_label = unmEl ? (unmEl.value.trim() || 'Altres') : 'Altres';
      cfg.type = 'mapping';
    }
    State.generalizations[name] = cfg;
  });
}

async function saveGeneralizations() {
  hideErr('gen-error');
  collectGeneralizations();

  // Validació bins
  var quasi = quasiItems();
  for (var i=0; i<quasi.length; i++) {
    var nm  = quasi[i];
    var cfg = State.generalizations[nm] || {};
    if (cfg.type==='bins') {
      if (!cfg.bins || cfg.bins.length<2) {
        showErr('gen-error', '"'+nm+'": cal almenys 2 punts de tall.');
        return;
      }
      if (!cfg.labels || cfg.labels.length !== cfg.bins.length-1) {
        showErr('gen-error', '"'+nm+'": cal exactament '+(cfg.bins.length-1)+' etiqueta/es.');
        return;
      }
    }
  }

  try {
    await api('/api/set-generalizations','POST',{
      session_id:      State.sessionId,
      generalizations: State.generalizations,
    });
    goToPhase(4);
  } catch(err) {
    showErr('gen-error', err.message);
  }
}

// ── Simulació de k ────────────────────────────────────────────────────────────
async function runSimulation() {
  var btn = el('sim-btn'), spinner = el('sim-spinner');
  btn.disabled = true;
  spinner.style.display = 'inline-block';
  try {
    var data = await api('/api/simulate-k', 'POST', { session_id: State.sessionId });
    renderSimulation(data);
    el('k-sim-card').style.display = 'block';
    el('k-sim-card').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } catch(err) {
    showErr('phase4-error', err.message);
  } finally {
    btn.disabled = false;
    spinner.style.display = 'none';
  }
}

function renderSimulation(data) {
  var sims = data.simulations;
  if (!sims || !sims.length) return;
  var maxPct = Math.max.apply(null, sims.map(function(s){ return s.pct_suppressed; }));
  var html = '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.65rem;margin-bottom:1rem;">';
  sims.forEach(function(s) {
    var pct   = s.pct_suppressed;
    var color = pct < 5 ? 'var(--success)' : pct < 20 ? 'var(--amber)' : 'var(--danger)';
    var barW  = maxPct > 0 ? Math.round(pct / maxPct * 100) : 0;
    html +=
      '<div style="background:var(--surface2);border:1px solid var(--border);border-radius:var(--r-sm);padding:0.9rem;text-align:center;">' +
        '<div style="font-size:1.5rem;font-weight:800;font-family:var(--mono);color:var(--accent);">k=' + s.k + '</div>' +
        '<div style="font-size:1.3rem;font-weight:800;font-family:var(--mono);color:' + color + ';margin:0.35rem 0;">' + s.n_patients_final + '</div>' +
        '<div style="font-size:0.68rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em;">' + t('resPatientsAfter') + '</div>' +
        '<div style="background:var(--surface3);border-radius:3px;height:5px;margin:0.6rem 0 0.35rem;overflow:hidden;">' +
          '<div style="background:' + color + ';width:' + barW + '%;height:100%;border-radius:3px;"></div>' +
        '</div>' +
        '<div style="font-size:0.75rem;color:' + color + ';font-weight:700;">' + pct + '% ' + t('resPct') + '</div>' +
        '<div style="font-size:0.68rem;color:var(--text-muted);margin-top:0.2rem;">' + s.conforming_groups + '/' + s.n_groups + ' ' + t('resGroups').toLowerCase() + '</div>' +
      '</div>';
  });
  html += '</div>';
  html += '<p style="font-size:0.78rem;color:var(--text-muted);">' + t('kSimNote') + '</p>';
  el('k-sim-content').innerHTML = html;
}

// ── FASE 4: K-anonimitat ──────────────────────────────────────────────────────
async function runAnonymization() {
  hideErr('phase4-error');
  var k = parseInt(el('k-value').value, 10);
  if (!k || k<2) { showErr('phase4-error', 'k ha de ser ≥ 2'); return; }

  var btn     = el('run-btn');
  var spinner = el('run-spinner');
  btn.disabled = true;
  spinner.style.display = 'inline-block';

  try {
    var metrics = await api('/api/anonymize','POST',{ session_id:State.sessionId, k:k, lang:LANG });
    renderResults(metrics);
    el('results-section').style.display = 'block';
    el('results-section').scrollIntoView({ behavior:'smooth' });
  } catch(err) {
    showErr('phase4-error', err.message);
  } finally {
    btn.disabled = false;
    spinner.style.display = 'none';
  }
}

function renderResults(m) {
  var pct      = m.pct_suppressed;
  var barColor = pct<5 ? 'var(--success)' : pct<20 ? 'var(--amber)' : 'var(--danger)';

  // Stats principals
  var stats = [
    { val: m.n_patients_orig,       lbl: t('resPatientsBefore'), color: 'var(--text)' },
    { val: m.n_patients_final,      lbl: t('resPatientsAfter'),  color: 'var(--success)' },
    { val: m.n_suppressed_patients, lbl: t('resSuppressed'),     color: 'var(--danger)' },
    { val: pct+'%',                 lbl: t('resPct'),            color: barColor },
    { val: m.n_records_orig,        lbl: t('resRecordsBefore'),  color: 'var(--text)' },
    { val: m.n_records_final,       lbl: t('resRecordsAfter'),   color: 'var(--success)' },
  ];
  el('result-stats-grid').innerHTML = stats.map(function(s){
    return '<div class="result-stat"><div class="val" style="color:'+s.color+';">'+(typeof s.val==='number'?s.val.toLocaleString():s.val)+'</div><div class="lbl">'+s.lbl+'</div></div>';
  }).join('');

  // Barra de pèrdua
  var lossBar = el('loss-bar');
  lossBar.style.width      = Math.min(pct,100)+'%';
  lossBar.style.background = barColor;
  el('loss-label').textContent = pct+'% de pacients eliminats per no complir k='+m.k_used;

  // Classes d'equivalència
  var eq   = m.equivalence_classes || {};
  var dist = eq.size_distribution  || {};
  var maxC = Math.max.apply(null, Object.values(dist).concat([1]));
  el('eq-distribution').innerHTML = Object.entries(dist)
    .sort(function(a,b){return parseInt(a[0])-parseInt(b[0]);})
    .map(function(e){
      var sz=e[0], cnt=e[1];
      return '<div class="dist-row">' +
        '<div class="dist-label">'+t('groupSize')+' '+sz+'</div>' +
        '<div class="dist-bar"><div class="dist-fill" style="width:'+Math.round(cnt/maxC*100)+'%;"></div></div>' +
        '<div class="dist-count">'+cnt+' '+t('groups')+'</div>' +
        '</div>';
    }).join('');

  // Grups eliminats
  var sg = m.suppressed_groups || [];
  if (sg.length) {
    var headers = Object.keys(sg[0]);
    el('suppressed-content').innerHTML =
      '<div class="table-wrap"><table>' +
      '<thead><tr>'+headers.map(function(h){return '<th>'+esc(h)+'</th>';}).join('')+'</tr></thead>' +
      '<tbody>'+sg.slice(0,25).map(function(row){
        return '<tr>'+Object.values(row).map(function(v){return '<td>'+esc(String(v))+'</td>';}).join('')+'</tr>';
      }).join('')+'</tbody>' +
      '</table></div>';
  } else {
    el('suppressed-content').innerHTML = '<p class="alert alert-success">'+t('noSuppressed')+'</p>';
  }

  // Descàrregues
  var sid = State.sessionId;
  el('download-grid').innerHTML =
    '<a class="download-card" href="/api/download/csv/'+sid+'" download>' +
      '<div class="download-icon">📄</div>' +
      '<h3>'+t('downloadCSV')+'</h3>' +
      '<p>'+(State.nFiles > 1 ? t('downloadCSVSubMulti') : t('downloadCSVSub'))+'</p>' +
    '</a>' +
    '<a class="download-card" href="/api/download/report/html/'+sid+'" download>' +
      '<div class="download-icon">📑</div>' +
      '<h3>'+t('downloadHTML')+'</h3>' +
      '<p>'+t('downloadHTMLSub')+'</p>' +
    '</a>' +
    '<a class="download-card" href="/api/download/report/'+sid+'" download>' +
      '<div class="download-icon">📋</div>' +
      '<h3>'+t('downloadReport')+'</h3>' +
      '<p>'+t('downloadReportSub')+'</p>' +
    '</a>';
}

// ── Nova sessió ───────────────────────────────────────────────────────────────
function startOver() {
  if (State.sessionId) fetch('/api/session/'+State.sessionId,{method:'DELETE'}).catch(function(){});
  State.sessionId=null; State.items=[]; State.classifications={}; State.generalizations={};
  State.dateFormat='iso'; State.dateDetection=null;
  State.nFiles=1; State.multifileConfirmed=false;
  var cb = el('multifile-confirm-checkbox'); if (cb) cb.checked = false;
  var mfc = el('multifile-confirm-card');    if (mfc) mfc.style.display = 'none';
  var mpc = el('mapping-confirm-card');      if (mpc) mpc.style.display = 'none';
  var fl  = el('files-list');                if (fl)  fl.style.display  = 'none';
  hideErr('upload-error');
  hideErr('mapping-error');
  el('upload-results').style.display='none';
  el('file-input').value='';
  el('results-section').style.display='none';
  goToPhase(1);
}
