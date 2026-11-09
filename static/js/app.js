/**
 * app.js — Local Anonymizer
 * -----------------------------
 * Flux: Càrrega → Classificació → Generalització → K-anonimitat → Resultats
 */

'use strict';

// ── Estat ─────────────────────────────────────────────────────────────────────
var State = {
  sessionId:       null,
  items:           [],          // perfils dels ítems [{name, type, n_unique, values, stats, ...}]
  classifications: {},          // { item → 'quasi_id' | 'non_id' }
  generalizations: {},          // { item → { type, bins?, labels?, labelsInput?, mapping?, unmapped_label? } }
  dateFormat:      'iso',       // 'iso' | 'dayfirst' | 'monthfirst'
  detectedFormat:  'iso',       // el que va proposar el backend, per marcar-lo a la UI
  dateDetection:   null,        // { best, n_total, candidates, samples }
  dateRange:       null,
  nFiles:          1,           // nombre de CSVs pujats
  multifileConfirmed: false,    // gate per a multi-fitxer: confirmació explícita
  phase:           1,
  // Últimes respostes del backend: permeten tornar a pintar en canviar d'idioma
  uploadData:      null,
  mappingData:     null,
  lastSim:         null,
  lastMetrics:     null,
  lastLang:        null,        // idioma amb què es van generar els informes
};

// Més valors que això en un QI categòric no és una variable sinó text lliure;
// els que no es mostren van a l'etiqueta de no assignats (i es diu a la UI).
var MAPPING_MAX_VALUES = 1000;
// Per sota d'aquest nombre de registres un valor es marca com a «pocs registres»
// (és el k recomanat: són els valors que acabaran en grups massa petits).
var RARE_COUNT = 5;
// Fragments de noms de variable que solen ser quasi-identificadors. Només
// serveixen per mostrar un suggeriment: la decisió és sempre de l'usuari.
var QI_HINTS = ['edad', 'edat', 'age', 'sexo', 'sexe', 'sex', 'genero', 'gender', 'nacional',
  'origen', 'origin', 'pais', 'country', 'postal', 'zip', 'municip', 'localidad', 'poblacion',
  'provincia', 'comarca', 'region', 'etnia', 'raza', 'ethnic', 'civil', 'educa', 'estudi',
  'ocupacion', 'profesi', 'laboral', 'empleo', 'idioma', 'migra', 'nacimiento', 'birth',
  'convivencia', 'socioeconom'];

// ── Utils ─────────────────────────────────────────────────────────────────────
function el(id)    { return document.getElementById(id); }
function esc(str)  {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function fmt(key, vars) {
  var s = t(key);
  Object.keys(vars || {}).forEach(function(k){ s = s.split('{'+k+'}').join(vars[k]); });
  return s;
}
function locale() { return LANG === 'ca' ? 'ca-ES' : LANG === 'en' ? 'en-GB' : 'es-ES'; }
function nf(n)    { return Number(n).toLocaleString(locale(), { maximumFractionDigits: 2 }); }
function showErr(id, msg) { var e=el(id); if(e){e.textContent=msg; e.style.display='block';} }
function hideErr(id)      { var e=el(id); if(e) e.style.display='none'; }
function show(id, display) { el(id).style.display = display || 'block'; }
function hide(id)          { el(id).style.display = 'none'; }

function quasiItems() {
  return Object.entries(State.classifications).filter(function(e){return e[1]==='quasi_id';}).map(function(e){return e[0];});
}

// Els noms d'ítem venen del CSV (cometes, espais, accents...): mai no van dins
// d'un onclick ni d'un id. Al DOM es referencien per la seva posició a State.items.
function itemIdx(name) {
  for (var i = 0; i < State.items.length; i++) { if (State.items[i].name === name) return i; }
  return -1;
}
function cidOf(name)       { return 'i' + itemIdx(name); }
function itemFromEl(node, selector) {
  var holder = node.closest(selector);
  return holder ? State.items[parseInt(holder.getAttribute('data-idx'), 10)] : null;
}
function normName(s) {
  return String(s).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
}
function looksLikeQuasi(name) {
  var tokens = normName(name).split(/[^a-z0-9]+/).filter(Boolean);
  return tokens.some(function(tk){
    return tk === 'cp' || QI_HINTS.some(function(h){ return tk.indexOf(h) === 0; });
  });
}

// ── API ───────────────────────────────────────────────────────────────────────
async function api(path, method, body) {
  var opts = { method: method||'GET', headers: {} };
  if (body instanceof FormData) { opts.body = body; }
  else if (body) { opts.headers['Content-Type']='application/json'; opts.body=JSON.stringify(body); }
  var res  = await fetch(path, opts);
  // Llegim primer com a text: si el servidor torna HTML/plain (cas del 500
  // default de Starlette o d'un 413 d'un proxy), no volem petar amb
  // "Unexpected token" — volem ensenyar a l'usuari què ha passat.
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
  // Sortir de la fase 3 sense desar no ha de perdre el que s'hi ha escrit
  if (el('phase-3').classList.contains('active')) collectGeneralizations();
  State.phase = n;
  document.querySelectorAll('.phase').forEach(function(p){ p.classList.remove('active'); });
  document.querySelectorAll('.step-item').forEach(function(s,i){
    s.classList.remove('active','done');
    if (i+1 < n)  s.classList.add('done');
    if (i+1 === n) s.classList.add('active');
    var btn = s.querySelector('.step-btn');
    if (i+1 === n) btn.setAttribute('aria-current', 'step'); else btn.removeAttribute('aria-current');
  });
  el('phase-'+n).classList.add('active');
  window.scrollTo({top:0, behavior:'smooth'});

  if (n===2) renderClassify();
  if (n===3) renderGeneralizations();
  if (n===4) {
    updateRunLabel();
    if (!State.lastSim) runSimulation();
  }
}

// Des de la barra lateral només es pot tornar enrere: avançar passa pels
// botons «Desar i continuar», que són els que envien la configuració al servidor.
function navStep(n) {
  if (n < State.phase) goToPhase(n);
}

// ── Canvi d'idioma ────────────────────────────────────────────────────────────
// setLang (i18n.js) només tradueix els elements estàtics amb data-lang; el
// contingut generat aquí es torna a pintar des de l'estat.
function onLangChange() {
  var mc = el('mapping-confirm-card');
  if (State.mappingData && mc && mc.style.display !== 'none') {
    renderMappingConfirm(State.mappingData, collectMappings());
  }
  if (State.uploadData) {
    var cb      = el('multifile-confirm-checkbox');
    var checked = !!(cb && cb.checked);
    renderUpload(State.uploadData);
    renderDateFormat();
    renderMultifileConfirm(State.uploadData);
    if (cb) cb.checked = checked;
    updateContinueGate();
  }
  if (State.items.length) renderClassify();
  if (el('qi-blocks-container').children.length) {
    collectGeneralizations();
    renderGeneralizations();
  }
  updateRunLabel();
  if (State.lastSim)     renderSimulation(State.lastSim);
  if (State.lastMetrics) renderResults(State.lastMetrics);
}

// ── FASE 1 ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
  var zone  = el('upload-zone');
  var input = el('file-input');

  zone.addEventListener('dragover',  function(e){ e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', function(){ zone.classList.remove('drag-over'); });
  zone.addEventListener('drop', function(e){
    e.preventDefault(); zone.classList.remove('drag-over');
    var files = Array.from(e.dataTransfer.files);
    if (files.length) doUpload(files);
  });
  input.addEventListener('change', function(){
    var files = Array.from(input.files);
    if (files.length) doUpload(files);
  });

  setLang('es');
});

function renderFileChips(names) {
  el('files-list').innerHTML = names.map(function(n){ return '<span class="file-chip">'+esc(n)+'</span>'; }).join('');
}

async function doUpload(files) {
  // Validar que tots siguin CSV
  var nonCsv = files.filter(function(f){ return !f.name.toLowerCase().endsWith('.csv'); });
  if (nonCsv.length) {
    showErr('upload-error', t('errorOnlyCsv') + ': ' + nonCsv.map(function(f){return f.name;}).join(', '));
    return;
  }
  hideErr('upload-error');
  el('drop-title').textContent = t('uploading') + '…';

  // Amaguem qualsevol panel d'una pujada anterior
  hide('upload-results');
  hide('mapping-confirm-card');

  var fd = new FormData();
  files.forEach(function(f){ fd.append('files', f); });

  try {
    var data = await api('/api/upload', 'POST', fd);
    hide('upload-zone');
    renderFileChips(files.map(function(f){ return f.name; }));
    show('file-summary', 'flex');

    if (data.status === 'needs_mapping') {
      State.sessionId   = data.session_id;
      State.mappingData = data;
      renderMappingConfirm(data);
      return;
    }

    _applyUploadResponse(data);
  } catch(err) {
    showErr('upload-error', err.message);
  } finally {
    el('drop-title').textContent = t('dropZoneTitle');
    el('file-input').value = '';
  }
}

function _applyUploadResponse(data) {
  State.sessionId          = data.session_id;
  State.items              = data.items;
  State.nFiles             = data.n_files || 1;
  State.dateFormat         = data.date_format    || 'iso';
  State.detectedFormat     = State.dateFormat;
  State.dateDetection      = data.date_detection || null;
  State.dateRange          = data.date_range     || null;
  State.multifileConfirmed = false;
  State.uploadData         = data;
  State.mappingData        = null;

  State.classifications = {};
  State.generalizations = {};
  data.items.forEach(function(item){ State.classifications[item.name] = 'non_id'; });
  el('qi-blocks-container').innerHTML = '';
  el('item-filter').value = '';
  el('filter-quasi').checked = false;
  resetPhase4();

  hide('mapping-confirm-card');
  renderFileChips(data.filenames || []);

  renderUpload(data);
  renderDateFormat();
  renderMultifileConfirm(data);
  updateContinueGate();
}

// ── Confirmació del mapatge de columnes ───────────────────────────────────────
function renderMappingConfirm(data, selections) {
  show('mapping-confirm-card');
  selections = selections || {};

  var canonicals = ['pacient', 'data', 'item', 'valor'];

  var html = (data.files || []).map(function(f) {
    var statusTx = f.alias_complete ? t('mapAliasOk') : t('mapNeedsReview');

    var previewHead = (f.preview.columns || []).map(function(c){ return '<th>' + esc(c) + '</th>'; }).join('');
    var previewRows = (f.preview.rows    || []).map(function(row){
      return '<tr>' + row.map(function(cell){ return '<td>' + esc(String(cell)) + '</td>'; }).join('') + '</tr>';
    }).join('');

    var current = selections[f.filename] || {};
    var selectors = canonicals.map(function(canon, ci) {
      var sel = current[canon] || f.proposed_mapping[canon] || '';
      var sid = 'map-' + ci + '-' + (data.files.indexOf(f));
      var opts = (f.raw_columns || []).map(function(rc) {
        return '<option value="' + esc(rc) + '"' + (rc === sel ? ' selected' : '') + '>' + esc(rc) + '</option>';
      }).join('');
      return '<div class="input-group">' +
        '<label for="'+sid+'">' + t('mapField_'+canon) + ' <code>' + canon + '</code></label>' +
        '<select id="'+sid+'" class="input-field map-select" data-file="' + esc(f.filename) + '" data-canonical="' + canon + '">' +
        opts +
        '</select>' +
        '</div>';
    }).join('');

    return '<div style="margin-bottom:22px;">' +
      '<div style="margin-bottom:8px;"><span class="file-chip">' + esc(f.filename) + '</span>' +
        ' <span class="input-help">' + esc(statusTx) + '</span></div>' +
      '<div class="table-wrap" style="margin-bottom:12px;">' +
        '<table><thead><tr>' + previewHead + '</tr></thead><tbody>' + previewRows + '</tbody></table>' +
      '</div>' +
      '<div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:12px;">' +
        selectors +
      '</div>' +
    '</div>';
  }).join('');

  el('mapping-confirm-body').innerHTML = html;
}

function collectMappings() {
  var mappings = {};
  document.querySelectorAll('#mapping-confirm-body .map-select').forEach(function(sel) {
    var fname = sel.getAttribute('data-file');
    var canon = sel.getAttribute('data-canonical');
    if (!mappings[fname]) mappings[fname] = {};
    mappings[fname][canon] = sel.value;
  });
  return mappings;
}

async function confirmMapping() {
  hideErr('mapping-error');

  var mappings = collectMappings();

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
  var dr = State.dateRange;
  var dateStr = (dr && dr.min && dr.max) ? dr.min + ' → ' + dr.max : '—';
  el('stats-grid').innerHTML =
    statBox(nf(data.n_patients), t('statPatients')) +
    statBox(nf(data.n_records),  t('statRecords')) +
    statBox(nf(data.n_items),    t('statItems')) +
    statBox(dateStr,             t('statDates'), true);

  // Coherència: el que s'ha descartat o detectat abans de transformar res
  var coh   = data.coherence || {};
  var notes = [];
  if (coh.n_dropped_rows)   notes.push(fmt('coherenceDropped', {n: nf(coh.n_dropped_rows)}));
  if (coh.n_duplicate_rows) notes.push(fmt('coherenceDupes',   {n: nf(coh.n_duplicate_rows)}));
  var ignored = [];
  Object.keys(coh.ignored_columns || {}).forEach(function(f){
    coh.ignored_columns[f].forEach(function(c){ if (ignored.indexOf(c) === -1) ignored.push(c); });
  });
  if (ignored.length) notes.push(fmt('coherenceIgnored', {cols: ignored.join(', ')}));
  el('coherence-alert').style.display = notes.length ? 'block' : 'none';
  el('coherence-alert').innerHTML = notes.map(esc).join('<br>');

  // Items table
  el('items-tbody').innerHTML = data.items.map(function(item){
    var sample = '';
    if (item.type==='categorical' && item.values) {
      sample = item.values.slice(0,4).map(function(v){ return '<span class="tag">'+esc(v)+'</span>'; }).join('');
      if (item.values.length > 4) sample += ' <span class="input-help">+' + (item.values.length - 4) + '</span>';
    } else if (item.stats) {
      sample = '<span class="mono">' + item.stats.min + ' … ' + item.stats.max + '</span>';
    }
    return '<tr>' +
      '<td class="mono" style="font-weight:500;">'+esc(item.name)+'</td>' +
      '<td><span class="type-pill type-'+item.type+'">'+t(item.type)+'</span></td>' +
      '<td class="num">'+nf(item.n_unique)+'</td>' +
      '<td class="num">'+nf(item.n_records)+'</td>' +
      '<td class="sample">'+sample+'</td>' +
      '</tr>';
  }).join('');
  el('items-count').textContent = nf(data.items.length);

  // Preview
  var pt = el('preview-table');
  pt.querySelector('thead').innerHTML = '<tr>'+data.preview.columns.map(function(c){ return '<th>'+esc(c)+'</th>'; }).join('')+'</tr>';
  pt.querySelector('tbody').innerHTML = data.preview.rows.map(function(row){
    return '<tr>'+row.map(function(cell){ return '<td class="mono">'+esc(String(cell))+'</td>'; }).join('')+'</tr>';
  }).join('');

  show('upload-results', 'flex');
}

function statBox(val, lbl, small) {
  return '<div class="stat-box"><div class="lbl">'+lbl+'</div><div class="val'+(small?' small':'')+'">'+val+'</div></div>';
}

// ── Format de timestamp ───────────────────────────────────────────────────────
function renderDateFormat() {
  var det = State.dateDetection;
  if (!det) { hide('date-format-card'); return; }
  show('date-format-card');

  // Botons actius segons el format triat; el detectat porta una marca
  document.querySelectorAll('#date-format-toggle .type-btn').forEach(function(b){
    var f = b.getAttribute('data-fmt');
    b.classList.toggle('active', f === State.dateFormat);
    b.setAttribute('aria-pressed', f === State.dateFormat ? 'true' : 'false');
    b.querySelector('.detected').textContent = f === State.detectedFormat ? '· ' + t('dateDetected') : '';
  });

  // Mostres parsejades
  var tbody = el('date-samples-table').querySelector('tbody');
  tbody.innerHTML = (det.samples || []).map(function(s){
    var ok    = s.ok && s.parsed;
    var pcell = ok ? esc(s.parsed) : '<span style="color:var(--danger);">' + t('dateUnparseable') + '</span>';
    return '<tr>' +
      '<td class="mono">' + esc(s.raw) + '</td>' +
      '<td class="mono">' + pcell + '</td>' +
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
    warning.innerHTML = t('dateNatWarn1') + ' <strong>' + nf(nFailed) + '</strong> ' +
                        t('dateNatWarn2') + ' ' + nf(nTotal) + ' ' + t('dateNatWarn3');
  } else {
    warning.style.display = 'none';
  }

  el('date-format-stats').textContent =
    nf(nTotal) + ' ' + t('dateStatRows') + ' · ' +
    nf(nTotal - nFailed) + ' ' + t('dateStatOk') + ' · ' +
    nf(nFailed) + ' ' + t('dateStatFail') + ' · ' +
    (hasTime ? t('dateStatHasTime') : t('dateStatNoTime'));
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
      '<td class="mono">' + esc(s.filename) + '</td>' +
      '<td class="num">' + nf(s.n_records)  + '</td>' +
      '<td class="num">' + nf(s.n_patients) + '</td>' +
      '<td class="num">' + nf(s.n_items)    + '</td>' +
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
    '<div>' + t('mfSharedPatients') + ': <strong style="color:' + color + ';">' + nf(nShared) + ' / ' + nf(nUnion) + ' (' + nf(pct) + ' %)</strong>' +
    ' <span style="color:var(--text-muted);">— ' + t('mfSharedHint') + '</span></div>';

  if (overlap.length > 0) {
    var sample = overlap.slice(0, 5).map(function(o){ return '<code>'+esc(o)+'</code>'; }).join(', ');
    var more   = overlap.length > 5 ? ' (+' + (overlap.length - 5) + ')' : '';
    summary +=
      '<div style="margin-top:6px; color:var(--danger);">' + t('mfOverlapWarn') +
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
  State.multifileConfirmed = State.nFiles > 1 ? !!(cb && cb.checked) : true;
  btn.disabled = !State.multifileConfirmed;
  el('continue-hint').style.display = State.multifileConfirmed ? 'none' : 'inline';
}

async function setDateFormat(fmtName) {
  if (!State.sessionId) return;
  State.dateFormat = fmtName;
  renderDateFormat();
  try {
    var res = await api('/api/set-date-format', 'POST', {
      session_id:  State.sessionId,
      date_format: fmtName,
    });
    State.dateDetection = res.date_detection;
    State.dateRange     = res.date_range;
    renderDateFormat();
    if (State.uploadData) renderUpload(State.uploadData);
  } catch(err) {
    showErr('upload-error', err.message);
  }
}

// ── FASE 2: Classificació ─────────────────────────────────────────────────────
function updateQuasiCounter() {
  el('quasi-counter').textContent = fmt('quasiCounter', {n: quasiItems().length});
}

function renderClassify() {
  var grid      = el('classify-grid');
  var query     = normName(el('item-filter').value.trim());
  var onlyQuasi = el('filter-quasi').checked;
  var nPatients = (State.uploadData && State.uploadData.n_patients) || 0;

  var rows = State.items.map(function(item, idx) {
    var isQ = (State.classifications[item.name] || 'non_id') === 'quasi_id';
    if (onlyQuasi && !isQ) return '';
    if (query && normName(item.name).indexOf(query) === -1) return '';

    var sample = '';
    if (item.type==='categorical' && item.values) sample = item.values.slice(0,3).join(', ');
    else if (item.stats) sample = item.stats.min+' … '+item.stats.max;

    var badges = '';
    if (looksLikeQuasi(item.name)) badges += '<span class="badge badge-suggest">'+t('badgeSuggested')+'</span>';
    if (item.type === 'categorical' && nPatients >= 20 && item.n_unique >= nPatients * 0.5) {
      badges += '<span class="badge badge-warn">'+t('badgeNearUnique')+'</span>';
    }

    return '<div class="item-classify-row'+(isQ?' is-quasi':'') +'" data-idx="'+idx+'">' +
      '<div class="item-main">' +
        '<div class="item-name">'+esc(item.name)+badges+'</div>' +
        '<div class="item-meta"><span class="type-pill type-'+item.type+'">'+t(item.type)+'</span> &nbsp;'+nf(item.n_unique)+' '+t('uniqueValues')+(sample ? ' · '+esc(sample) : '')+'</div>' +
      '</div>' +
      '<div class="role-toggle" role="group" aria-label="'+esc(item.name)+'">' +
        '<button type="button" class="role-btn'+(isQ?' active-quasi':'')+'" aria-pressed="'+isQ+'" onclick="setRole(this,\'quasi_id\')">'+t('roleQuasi')+'</button>' +
        '<button type="button" class="role-btn'+(!isQ?' active-nonid':'')+'" aria-pressed="'+(!isQ)+'" onclick="setRole(this,\'non_id\')">'+t('roleNonId')+'</button>' +
      '</div>' +
      '</div>';
  }).join('');

  grid.innerHTML = rows || '<div class="empty">'+t('noMatches')+'</div>';
  updateQuasiCounter();
}

function setRole(btn, role) {
  var item = itemFromEl(btn, '.item-classify-row');
  if (!item) return;
  State.classifications[item.name] = role;
  var row = btn.closest('.item-classify-row');
  row.classList.toggle('is-quasi', role==='quasi_id');
  var btns = row.querySelectorAll('.role-btn');
  btns[0].classList.toggle('active-quasi', role==='quasi_id');
  btns[0].setAttribute('aria-pressed', role==='quasi_id' ? 'true' : 'false');
  btns[1].classList.toggle('active-nonid', role==='non_id');
  btns[1].setAttribute('aria-pressed', role==='non_id' ? 'true' : 'false');
  updateQuasiCounter();
}

async function saveClassifications() {
  hideErr('classify-error');
  try {
    await api('/api/classify','POST',{
      session_id:      State.sessionId,
      classifications: State.classifications,
    });
    resetPhase4();
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
    refreshBlockHints(cidOf(itemName));
  });
}

function buildQiBlock(name, profile) {
  var cid   = cidOf(name);
  var block = document.createElement('div');
  block.className = 'qi-block';
  block.id = 'qi-block-'+cid;
  block.setAttribute('data-idx', itemIdx(name));

  var cfg         = State.generalizations[name] || {};
  var defaultType = profile.type==='numeric' ? 'bins' : 'mapping';
  var activeType  = cfg.type || defaultType;

  block.innerHTML =
    '<button type="button" class="qi-block-header" aria-expanded="true" aria-controls="body-'+cid+'" onclick="toggleBlock(\''+cid+'\')">' +
      '<span>' +
        '<span class="qi-col-name" style="display:block;">'+esc(name)+'</span>' +
        '<span class="qi-col-meta" style="display:block;"><span class="type-pill type-'+profile.type+'">'+t(profile.type)+'</span>&nbsp; '+nf(profile.n_unique)+' '+t('uniqueValues')+'</span>' +
      '</span>' +
      '<span class="qi-chevron open" id="chevron-'+cid+'" aria-hidden="true"></span>' +
    '</button>' +
    '<div class="qi-block-body open" id="body-'+cid+'">' +
      buildDistribution(profile) +
      '<div class="segmented" role="group">' +
        '<button type="button" class="type-btn'+(activeType==='bins'?' active':'')+'" data-type="bins" onclick="switchType(this,\'bins\')">'+t('typeNumeric')+'</button>' +
        '<button type="button" class="type-btn'+(activeType==='mapping'?' active':'')+'" data-type="mapping" onclick="switchType(this,\'mapping\')">'+t('typeCategorical')+'</button>' +
      '</div>' +
      '<div id="qi-config-'+cid+'" style="display:flex; flex-direction:column; gap:14px;">' +
        buildTypeConfig(name, profile, activeType, cfg) +
      '</div>' +
    '</div>';

  return block;
}

// Els categòrics no porten distribució aquí: la llista de mapatge ja mostra
// el recompte de cada valor al costat del camp on s'agrupa.
function buildDistribution(profile) {
  if (profile.type==='numeric' && profile.stats) {
    var s = profile.stats;
    return '<div class="range-line">'+t('rangeObserved')+': '+nf(s.min)+' – '+nf(s.max)+' · '+t('medianShort')+' '+nf(s.median)+'</div>';
  }
  return '';
}

// ── Intervals: etiquetes automàtiques, suggeriment i previsualització ────────
function parseNumList(str) {
  return String(str || '').split(',').map(function(s){ return parseFloat(s.trim()); }).filter(function(n){ return !isNaN(n); });
}
function parseLabelList(str) {
  return String(str || '').split(',').map(function(s){ return s.trim(); }).filter(Boolean);
}
function autoLabels(bins) {
  var out = [];
  for (var i = 0; i < bins.length - 1; i++) {
    var a = bins[i], b = bins[i+1];
    // [a, b) amb enters → «a–(b-1)», que és com es llegeix una franja d'edat
    out.push(Number.isInteger(a) && Number.isInteger(b) && b - a > 1 ? a + '–' + (b - 1) : a + '–' + b);
  }
  return out;
}
function niceStep(raw) {
  var p = Math.pow(10, Math.floor(Math.log10(raw)));
  var m = raw / p;
  return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 5 ? 5 : 10) * p;
}
function suggestBins(btn) {
  var profile = itemFromEl(btn, '.qi-block');
  if (!profile || !profile.stats) return;
  var min = profile.stats.min, max = profile.stats.max;
  var step  = niceStep(Math.max((max - min) / 5, 1e-9));
  var start = Math.floor(min / step) * step;
  var bins  = [];
  // L'últim tall ha de superar el màxim: els intervals són [a, b)
  for (var v = start; v <= max + step / 2 && bins.length < 40; v += step) bins.push(+v.toFixed(6));
  if (bins[bins.length - 1] <= max) bins.push(+(bins[bins.length - 1] + step).toFixed(6));
  var cid = cidOf(profile.name);
  el('bins-'+cid).value = bins.join(', ');
  el('labels-'+cid).value = '';
  updateBinsPreview(btn);
}
function updateBinsPreview(node) {
  var profile = itemFromEl(node, '.qi-block');
  if (!profile) return;
  var cid    = cidOf(profile.name);
  var bins   = parseNumList(el('bins-'+cid).value);
  var labels = parseLabelList(el('labels-'+cid).value);
  var box    = el('bins-preview-'+cid);
  if (bins.length < 2) { box.innerHTML = '<div class="input-help">'+t('binsNeedTwo')+'</div>'; return; }
  for (var j = 1; j < bins.length; j++) {
    if (bins[j] <= bins[j-1]) { box.innerHTML = '<div class="alert alert-danger">'+t('errBinsOrder')+'</div>'; return; }
  }
  if (!labels.length) labels = autoLabels(bins);
  var chips = labels.slice(0, bins.length - 1).map(function(l, i){
    return '<span class="bin-chip">'+esc(l)+' <span>['+nf(bins[i])+', '+nf(bins[i+1])+')</span></span>';
  }).join('');
  var warns = '';
  var s = profile.stats || {};
  if (s.min !== null && s.min !== undefined && s.min < bins[0]) warns += '<div class="alert alert-warn">'+fmt('binsBelow', {v: nf(bins[0]), min: nf(s.min)})+'</div>';
  if (s.max !== null && s.max !== undefined && s.max >= bins[bins.length-1]) warns += '<div class="alert alert-warn">'+fmt('binsAbove', {v: nf(bins[bins.length-1]), max: nf(s.max)})+'</div>';
  if (labels.length !== bins.length - 1) warns += '<div class="alert alert-danger">'+fmt('errLabelsCount', {n: bins.length - 1})+'</div>';
  box.innerHTML = '<div class="input-help" style="font-weight:600;">'+t('binsPreview')+'</div><div class="bin-chips">'+chips+'</div>'+warns;
}

// ── Categories: recompte de categories resultants ────────────────────────────
function updateMappingSummary(node) {
  var profile = itemFromEl(node, '.qi-block');
  if (!profile) return;
  var cid     = cidOf(profile.name);
  var inputs  = document.querySelectorAll('[data-cid="'+cid+'"]');
  var targets = new Set();
  var blank   = (profile.values || []).length > inputs.length;
  inputs.forEach(function(inp){ var v = inp.value.trim(); if (v) targets.add(v); else blank = true; });
  if (blank) targets.add('\u0000unmapped');
  el('mapping-summary-'+cid).textContent = fmt('mappingSummary', {n: nf((profile.values || []).length), m: nf(targets.size)});
}

function buildTypeConfig(name, profile, type, cfg) {
  var cid = cidOf(name);

  if (type==='bins') {
    var bins   = cfg.bins ? cfg.bins.join(', ') : '';
    var labels = cfg.labelsInput !== undefined ? cfg.labelsInput : (cfg.labels ? cfg.labels.join(', ') : '');
    var canSuggest = profile.stats && profile.stats.min !== null && profile.stats.max !== null;
    return '<div class="input-group">' +
        '<label for="bins-'+cid+'">'+t('binsLabel')+'</label>' +
        '<div class="input-row">' +
          '<input type="text" class="input-field" id="bins-'+cid+'" placeholder="0, 18, 40, 65, 120" value="'+esc(bins)+'" oninput="updateBinsPreview(this)">' +
          (canSuggest ? '<button type="button" class="btn btn-outline btn-sm" onclick="suggestBins(this)">'+t('btnSuggestBins')+'</button>' : '') +
        '</div>' +
        '<div class="input-help">'+t('binsHelp')+'</div>' +
      '</div>' +
      '<div class="input-group">' +
        '<label for="labels-'+cid+'">'+t('labelsLabel')+'</label>' +
        '<input type="text" class="input-field" id="labels-'+cid+'" placeholder="0-17, 18-39, 40-64, 65+" value="'+esc(labels)+'" oninput="updateBinsPreview(this)">' +
        '<div class="input-help">'+t('labelsHelp')+'</div>' +
      '</div>' +
      '<div class="bins-preview" id="bins-preview-'+cid+'" aria-live="polite"></div>';
  }

  if (type==='mapping') {
    var all             = profile.values || [];
    var values          = all.slice(0, MAPPING_MAX_VALUES);
    var counts          = profile.value_counts || {};
    var existingMapping = cfg.mapping || {};
    var unmapped        = cfg.unmapped_label || t('unmappedDefault');

    var rows = values.map(function(v, vi) {
      var c    = counts[v] || 0;
      var rare = c < RARE_COUNT;
      var iid  = 'map-'+cid+'-'+vi;
      return '<div class="mapping-grid'+(rare?' rare':'')+'">' +
        '<label class="mapping-orig" for="'+iid+'" title="'+esc(v)+'">'+esc(v)+'</label>' +
        '<div class="mapping-count"'+(rare?' title="'+t('mappingRare')+'"':'')+'>'+nf(c)+'</div>' +
        '<div class="mapping-arrow" aria-hidden="true">→</div>' +
        '<input type="text" id="'+iid+'" class="mapping-input" data-original="'+esc(v)+'" data-cid="'+cid+'" value="'+esc(existingMapping[v] !== undefined ? existingMapping[v] : v)+'" oninput="updateMappingSummary(this)">' +
        '</div>';
    }).join('');
    var truncated = all.length > values.length
      ? '<div class="alert alert-warn">'+fmt('mappingTruncated', {shown: nf(values.length), total: nf(all.length)})+'</div>'
      : '';

    return '<div class="input-help">'+t('mappingHelp')+'</div>' +
      truncated +
      '<div class="mapping-summary" id="mapping-summary-'+cid+'" aria-live="polite"></div>' +
      '<div class="mapping-list">' + rows + '</div>' +
      '<div class="input-group">' +
        '<label for="unmapped-'+cid+'">'+t('unmappedLabel')+'</label>' +
        '<input type="text" class="input-field" id="unmapped-'+cid+'" value="'+esc(unmapped)+'" style="max-width:360px;">' +
      '</div>';
  }

  return '';
}

// Les previsualitzacions es calculen un cop el bloc ja és al DOM
function refreshBlockHints(cid) {
  var b = el('bins-'+cid);
  if (b) updateBinsPreview(b);
  var m = el('mapping-summary-'+cid);
  if (m) updateMappingSummary(m);
}

function toggleBlock(cid) {
  var body    = el('body-'+cid);
  var chevron = el('chevron-'+cid);
  var isOpen  = body.classList.contains('open');
  body.classList.toggle('open', !isOpen);
  chevron.classList.toggle('open', !isOpen);
  el('qi-block-'+cid).querySelector('.qi-block-header').setAttribute('aria-expanded', String(!isOpen));
}

function switchType(btn, type) {
  var profile = itemFromEl(btn, '.qi-block');
  if (!profile) return;
  var name = profile.name, cid = cidOf(name);
  var cfg  = State.generalizations[name] || {};
  cfg.type = type;
  State.generalizations[name] = cfg;

  // Actualitza botons
  el('qi-block-'+cid).querySelectorAll('.type-btn').forEach(function(b){
    b.classList.toggle('active', b.getAttribute('data-type') === type);
  });

  el('qi-config-'+cid).innerHTML = buildTypeConfig(name, profile, type, cfg);
  refreshBlockHints(cid);
}

function collectGeneralizations() {
  quasiItems().forEach(function(name) {
    var cid     = cidOf(name);
    if (!el('qi-block-'+cid)) return;   // QI encara no pintat: res a llegir del DOM
    var cfg     = State.generalizations[name] || {};
    var type    = cfg.type || ((State.items.find(function(i){return i.name===name;}) || {}).type==='numeric' ? 'bins' : 'mapping');

    if (type==='bins') {
      var bEl = el('bins-'+cid), lEl = el('labels-'+cid);
      if (bEl) cfg.bins = parseNumList(bEl.value);
      if (lEl) {
        // Etiquetes buides = automàtiques; es recorda el que va escriure l'usuari
        cfg.labelsInput = lEl.value;
        var typed  = parseLabelList(lEl.value);
        cfg.labels = typed.length ? typed : autoLabels(cfg.bins || []);
      }
      cfg.type = 'bins';
    } else {
      var inputs  = document.querySelectorAll('[data-cid="'+cid+'"]');
      var mapping = {};
      inputs.forEach(function(inp){ if(inp.value.trim()) mapping[inp.dataset.original]=inp.value.trim(); });
      var unmEl = el('unmapped-'+cid);
      cfg.mapping        = mapping;
      cfg.unmapped_label = unmEl ? (unmEl.value.trim() || t('unmappedDefault')) : t('unmappedDefault');
      cfg.type = 'mapping';
    }
    State.generalizations[name] = cfg;
  });
}

async function saveGeneralizations() {
  hideErr('gen-error');
  collectGeneralizations();

  // Validació bins + només s'envien les configuracions dels QI actuals
  var quasi   = quasiItems();
  var payload = {};
  for (var i=0; i<quasi.length; i++) {
    var nm  = quasi[i];
    var cfg = State.generalizations[nm] || {};
    if (cfg.type==='bins') {
      if (!cfg.bins || cfg.bins.length<2) {
        showErr('gen-error', '"'+nm+'": '+t('errBinsMin'));
        return;
      }
      for (var j=1; j<cfg.bins.length; j++) {
        if (cfg.bins[j] <= cfg.bins[j-1]) {
          showErr('gen-error', '"'+nm+'": '+t('errBinsOrder'));
          return;
        }
      }
      if (!cfg.labels || cfg.labels.length !== cfg.bins.length-1) {
        showErr('gen-error', '"'+nm+'": '+fmt('errLabelsCount', {n: cfg.bins.length-1}));
        return;
      }
      payload[nm] = { type: 'bins', bins: cfg.bins, labels: cfg.labels };
    } else {
      payload[nm] = { type: 'mapping', mapping: cfg.mapping || {}, unmapped_label: cfg.unmapped_label };
    }
  }

  try {
    await api('/api/set-generalizations','POST',{
      session_id:      State.sessionId,
      generalizations: payload,
    });
    resetPhase4();
    goToPhase(4);
  } catch(err) {
    showErr('gen-error', err.message);
  }
}

// ── Simulació de k ────────────────────────────────────────────────────────────
function currentK() { return parseInt(el('k-value').value, 10); }

function updateRunLabel() {
  var k = currentK();
  el('run-label').textContent = fmt('btnRun', {k: (k && k >= 2) ? k : '—'});
}

function onKChange() {
  updateRunLabel();
  if (State.lastSim) renderSimulation(State.lastSim);
}

function pickK(k) {
  el('k-value').value = k;
  onKChange();
}

async function runSimulation() {
  var btn = el('sim-btn'), spinner = el('sim-spinner');
  btn.disabled = true;
  spinner.style.display = 'inline-block';
  hideErr('phase4-error');
  el('k-sim-content').innerHTML = '<div class="sim-note">'+t('simLoading')+'…</div>';
  try {
    var data = await api('/api/simulate-k', 'POST', { session_id: State.sessionId });
    State.lastSim = data;
    renderSimulation(data);
  } catch(err) {
    el('k-sim-content').innerHTML = '';
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
  var k = currentK();
  var rows = sims.map(function(s) {
    var chosen = s.k === k;
    var barW   = maxPct > 0 ? Math.round(s.pct_suppressed / maxPct * 100) : 0;
    return '<tr'+(chosen?' class="chosen"':'')+'>' +
      '<td><button type="button" class="k-pick" aria-label="'+fmt('simUseK', {k: s.k})+'" aria-pressed="'+chosen+'" onclick="pickK('+s.k+')">k = '+s.k+'</button>' +
        (chosen ? ' <span class="input-help">'+t('simChosen')+'</span>' : '') + '</td>' +
      '<td class="num">'+nf(s.n_patients_final)+'</td>' +
      '<td class="num">'+nf(s.n_suppressed)+'</td>' +
      '<td><div class="loss-cell"><div class="bar"><div style="width:'+barW+'%;"></div></div><span>'+nf(s.pct_suppressed)+' %</span></div></td>' +
      '<td class="num">'+nf(s.conforming_groups)+' / '+nf(s.n_groups)+'</td>' +
      '</tr>';
  }).join('');
  el('k-sim-content').innerHTML =
    '<div class="table-wrap"><table class="sim-table" style="min-width:560px;">' +
      '<thead><tr>' +
        '<th>'+t('simColK')+'</th>' +
        '<th class="num">'+t('simColFinal')+'</th>' +
        '<th class="num">'+t('simColSupp')+'</th>' +
        '<th style="width:34%;">'+t('simColLoss')+'</th>' +
        '<th class="num">'+t('simColGroups')+'</th>' +
      '</tr></thead><tbody>'+rows+'</tbody></table></div>' +
    '<div class="sim-note">'+t('kSimNote')+'</div>';
}

// ── FASE 4: K-anonimitat ──────────────────────────────────────────────────────
// Si canvien classificació o generalitzacions, la simulació i els resultats
// anteriors ja no corresponen a la configuració actual.
function resetPhase4() {
  State.lastSim = null;
  State.lastMetrics = null;
  el('k-sim-content').innerHTML = '';
  hide('results-section');
  hideErr('phase4-error');
}

async function runAnonymization() {
  hideErr('phase4-error');
  var k = currentK();
  if (!k || k<2) { showErr('phase4-error', t('errKMin')); return; }

  var btn     = el('run-btn');
  var spinner = el('run-spinner');
  btn.disabled = true;
  spinner.style.display = 'inline-block';

  try {
    var metrics = await api('/api/anonymize','POST',{ session_id:State.sessionId, k:k, lang:LANG });
    State.lastMetrics = metrics;
    State.lastLang    = LANG;
    renderResults(metrics);
    show('results-section', 'flex');
    el('results-section').scrollIntoView({ behavior:'smooth' });
  } catch(err) {
    showErr('phase4-error', err.message);
  } finally {
    btn.disabled = false;
    spinner.style.display = 'none';
  }
}

function renderGenLog(log) {
  var lines = Object.keys(log || {}).map(function(item) {
    var g = log[item], parts = [];
    if (g.n_out_of_range) parts.push(nf(g.n_out_of_range) + ' ' + t('genLogOutOfRange'));
    if (g.n_non_numeric)  parts.push(nf(g.n_non_numeric)  + ' ' + t('genLogNonNumeric'));
    if (g.n_unmapped)     parts.push(nf(g.n_unmapped)     + ' ' + t('genLogUnmapped'));
    return parts.length ? '<li><code>'+esc(item)+'</code>: '+parts.join(' · ')+'</li>' : '';
  }).join('');
  var box = el('gen-log-alert');
  box.style.display = lines ? 'block' : 'none';
  box.innerHTML = lines ? t('genLogTitle') + '<ul>' + lines + '</ul>' : '';
}

function outputNames() {
  var names = (State.uploadData && State.uploadData.filenames) || [];
  var stem  = names.length === 1 ? names[0].replace(/\.csv$/i, '') : null;
  return {
    csv:  stem ? stem + '_anonymized.csv' : 'datasets_anonymized.zip',
    html: stem ? stem + '_report.html'    : 'anonymization_report.html',
    json: 'anonymization_report.json',
  };
}

function downloadRow(href, icon, title, sub) {
  return '<div class="download-row">' + icon +
    '<div class="dl-text"><div class="dl-title">'+title+'</div><div class="dl-sub">'+sub+'</div></div>' +
    '<a class="btn btn-outline btn-sm" href="'+href+'" download>'+t('btnDownload')+'</a>' +
    '</div>';
}

var ICON_FILE = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path><path d="M14 3v6h6"></path></svg>';
var ICON_DOC  = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path><path d="M14 3v6h6M8 13h8M8 17h5"></path></svg>';
var ICON_JSON = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 3H7a2 2 0 0 0-2 2v4a2 2 0 0 1-2 2 2 2 0 0 1 2 2v4a2 2 0 0 0 2 2h1M16 3h1a2 2 0 0 1 2 2v4a2 2 0 0 0 2 2 2 2 0 0 0-2 2v4a2 2 0 0 1-2 2h-1"></path></svg>';

function renderResults(m) {
  var pct = m.pct_suppressed;

  renderGenLog(m.generalization_log);

  var hl = el('high-loss-alert');
  if (pct >= 20) {
    hl.style.display = 'block';
    hl.innerHTML = fmt('highLoss', {pct: nf(pct)}) +
      ' <button type="button" class="btn btn-link" onclick="goToPhase(3)">'+t('btnBackToGen')+'</button>';
  } else {
    hl.style.display = 'none';
  }

  el('result-stats-grid').innerHTML =
    '<div><div class="lbl">'+t('resPatients')+'</div><div class="val">'+nf(m.n_patients_orig)+' → '+nf(m.n_patients_final)+'</div></div>' +
    '<div><div class="lbl">'+t('resRecords')+'</div><div class="val">'+nf(m.n_records_orig)+' → '+nf(m.n_records_final)+'</div></div>' +
    '<div><div class="lbl">'+t('resSuppressed')+'</div><div class="val'+(m.n_suppressed_patients ? ' danger' : '')+'">'+nf(m.n_suppressed_patients)+' <span style="font-size:14px;">('+nf(pct)+' %)</span></div></div>';

  el('loss-bar').style.width   = Math.min(pct,100)+'%';
  el('loss-label').textContent = fmt('lossLabel', {pct: nf(pct), k: m.k_used});

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
        '<div class="dist-bar"><div class="dist-fill" style="width:'+Math.round(cnt/maxC*100)+'%;'+(parseInt(sz,10) < m.k_used ? 'background:var(--danger);' : '')+'"></div></div>' +
        '<div class="dist-count">'+nf(cnt)+' '+t('groups')+'</div>' +
        '</div>';
    }).join('');

  // Grups eliminats
  var sg = m.suppressed_groups || [];
  if (sg.length) {
    var headers = Object.keys(sg[0]);
    el('suppressed-content').innerHTML =
      '<div class="table-wrap"><table>' +
      '<thead><tr>'+headers.map(function(h){return '<th>'+esc(h==='_count_' ? t('groupSize') : h)+'</th>';}).join('')+'</tr></thead>' +
      '<tbody>'+sg.slice(0,25).map(function(row){
        return '<tr>'+Object.values(row).map(function(v){return '<td class="mono">'+esc(String(v))+'</td>';}).join('')+'</tr>';
      }).join('')+'</tbody>' +
      '</table></div>';
  } else {
    el('suppressed-content').innerHTML = '<p class="alert alert-success">'+t('noSuppressed')+'</p>';
  }

  // Descàrregues
  var sid   = encodeURIComponent(State.sessionId);
  var names = outputNames();
  var mono  = function(s){ return '<span class="mono">'+esc(s)+'</span>'; };
  el('download-grid').innerHTML =
    downloadRow('/api/download/csv/'+sid, ICON_FILE, t('downloadCSV'),
      (State.nFiles > 1 ? t('downloadCSVSubMulti') : t('downloadCSVSub')) + ' · ' + mono(names.csv)) +
    downloadRow('/api/download/report/html/'+sid, ICON_DOC, t('downloadHTML'), t('downloadHTMLSub') + ' · ' + mono(names.html)) +
    downloadRow('/api/download/report/'+sid, ICON_JSON, t('downloadReport'), t('downloadReportSub') + ' · ' + mono(names.json));
  el('report-lang-note').textContent = fmt('reportLangNote', {lang: t('lang_' + (State.lastLang || LANG))});
}

// ── Nova sessió ───────────────────────────────────────────────────────────────
function startOver() {
  if (State.sessionId) fetch('/api/session/'+encodeURIComponent(State.sessionId),{method:'DELETE'}).catch(function(){});
  State.sessionId=null; State.items=[]; State.classifications={}; State.generalizations={};
  State.dateFormat='iso'; State.detectedFormat='iso'; State.dateDetection=null; State.dateRange=null;
  State.nFiles=1; State.multifileConfirmed=false;
  State.uploadData=null; State.mappingData=null; State.lastLang=null;
  var cb = el('multifile-confirm-checkbox'); if (cb) cb.checked = false;
  hide('multifile-confirm-card');
  hide('mapping-confirm-card');
  hide('file-summary');
  show('upload-zone');
  el('files-list').innerHTML = '';
  hideErr('upload-error');
  hideErr('mapping-error');
  hide('upload-results');
  el('file-input').value='';
  el('qi-blocks-container').innerHTML='';
  el('k-value').value = 5;
  resetPhase4();
  goToPhase(1);
}
