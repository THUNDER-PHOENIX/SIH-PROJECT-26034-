const $ = s => document.querySelector(s);

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
}

let ocrWorker = null;
let ruleChart = null;
let severityChart = null;

async function api(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try { message = (await response.json()).detail || message; } catch (_) {}
    throw new Error(message);
  }
  return response.json();
}

document.querySelectorAll('.tab').forEach(button => {
  button.onclick = () => {
    document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
    document.querySelectorAll('.page').forEach(x => x.classList.add('hidden'));
    button.classList.add('active');
    $('#' + button.dataset.tab).classList.remove('hidden');
    if (button.dataset.tab === 'history') loadHistory();
    if (button.dataset.tab === 'dash') loadDash();
  };
});

async function browserOCR(file) {
  if (typeof Tesseract === 'undefined') return '';
  $('#go').textContent = 'OCR in browser…';
  if (!ocrWorker) ocrWorker = await Tesseract.createWorker('eng');
  const { data } = await ocrWorker.recognize(file);
  return data.text || '';
}

$('#go').onclick = async () => {
  const file = $('#img').files[0];
  if (!file) return alert('Pick a label photo first.');
  if (file.size > 10 * 1024 * 1024) return alert('Image must be 10 MB or smaller.');

  const button = $('#go');
  button.disabled = true;
  $('#error').textContent = '';
  try {
    let ocrText = $('#demo').value.trim();
    if (!ocrText) {
      try { ocrText = await browserOCR(file); } catch (e) { console.warn('Browser OCR failed', e); }
    }

    const fd = new FormData();
    fd.append('file', file);
    if ($('#ppm').value) fd.append('px_per_mm', $('#ppm').value);
    fd.append('demo_text', ocrText);
    button.textContent = 'Analyzing…';

    const result = await api('/api/scan', { method: 'POST', body: fd });
    $('#result').classList.remove('hidden');
    $('#status').textContent = result.status + (result.engine ? ` (${result.engine})` : '');
    $('#status').className = result.status === 'COMPLIANT' ? 'ok' : 'bad';
    $('#extracted').textContent = JSON.stringify(result.extracted, null, 2);
    $('#viol').innerHTML = result.violations.length
      ? result.violations.map(v => `<li class="${escapeHtml(v.severity)}"><b>[${escapeHtml(v.severity)}]</b> Rule ${escapeHtml(v.rule_id)}: ${escapeHtml(v.message)}</li>`).join('')
      : '<li class="ok">No critical or major violations detected.</li>';
    $('#pdf').href = '/api/report/' + encodeURIComponent(result.scan_id) + '.pdf';
    $('#confidence').textContent = `OCR confidence: ${Math.round((result.extracted.ocr_confidence || 0) * 100)}%`;
  } catch (error) {
    $('#error').textContent = error.message;
    $('#result').classList.add('hidden');
  } finally {
    button.disabled = false;
    button.textContent = 'Analyze Label';
  }
};

async function loadHistory() {
  try {
    const rows = await api('/api/scans');
    $('#tbl').innerHTML = '<tr><th>ID</th><th>Product</th><th>Status</th><th>Date</th><th>Report</th></tr>' +
      rows.map(s => `<tr><td>${escapeHtml(s.id)}</td><td>${escapeHtml(s.product_name)}</td><td class="${s.status === 'COMPLIANT' ? 'ok' : 'bad'}">${escapeHtml(s.status)}</td><td>${escapeHtml(new Date(s.created_at * 1000).toLocaleString())}</td><td><a href="/api/report/${encodeURIComponent(s.id)}.pdf" target="_blank">PDF</a></td></tr>`).join('');
  } catch (e) { $('#tbl').innerHTML = `<tr><td colspan="5" class="bad">${escapeHtml(e.message)}</td></tr>`; }
}

async function loadDash() {
  try {
    const d = await api('/api/dashboard');
    $('#k_total').textContent = d.total_scans;
    $('#k_nc').textContent = d.non_compliant;
    $('#k_rate').textContent = d.compliance_rate + '%';
    if (ruleChart) ruleChart.destroy();
    if (severityChart) severityChart.destroy();
    ruleChart = new Chart($('#ch_rule'), { type: 'bar', data: { labels: d.violations_by_rule.map(x => x.rule_id), datasets: [{ label: 'Violations', data: d.violations_by_rule.map(x => x.c) }] }, options: { responsive: true, maintainAspectRatio: false } });
    severityChart = new Chart($('#ch_sev'), { type: 'doughnut', data: { labels: d.violations_by_severity.map(x => x.severity), datasets: [{ data: d.violations_by_severity.map(x => x.c) }] }, options: { responsive: true, maintainAspectRatio: false } });
  } catch (e) { console.error(e); }
}
