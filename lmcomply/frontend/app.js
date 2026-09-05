const $ = s => document.querySelector(s);
function escapeHtml(v) { return String(v ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
let ocrWorker = null, ruleChart = null, severityChart = null;
async function api(url, options = {}) { const r = await fetch(url, options); if (!r.ok) { let m = `Request failed (${r.status})`; try { m = (await r.json()).detail || m; } catch (_) {} throw new Error(m); } return r.json(); }

document.querySelectorAll('.tab').forEach(b => b.onclick = () => { document.querySelectorAll('.tab').forEach(x => x.classList.remove('active')); document.querySelectorAll('.page').forEach(x => x.classList.add('hidden')); b.classList.add('active'); $('#' + b.dataset.tab).classList.remove('hidden'); if (b.dataset.tab === 'history') loadHistory(); if (b.dataset.tab === 'dash') loadDash(); });
async function browserOCR(file) { if (typeof Tesseract === 'undefined') return ''; $('#go').textContent = 'OCR in browser…'; if (!ocrWorker) ocrWorker = await Tesseract.createWorker('eng'); const { data } = await ocrWorker.recognize(file); return data.text || ''; }

$('#go').onclick = async () => {
  const file = $('#img').files[0]; if (!file) return alert('Pick a label photo first.'); if (file.size > 10 * 1024 * 1024) return alert('Image must be 10 MB or smaller.');
  const button = $('#go'); button.disabled = true; $('#error').textContent = '';
  try {
    let ocrText = $('#demo').value.trim(); if (!ocrText) { try { ocrText = await browserOCR(file); } catch (e) { console.warn(e); } }
    const fd = new FormData(); fd.append('file', file); fd.append('category', $('#category').value); if ($('#ppm').value) fd.append('px_per_mm', $('#ppm').value); fd.append('demo_text', ocrText); button.textContent = 'Analyzing image…';
    const result = await api('/api/scan', { method: 'POST', body: fd });
    $('#result').classList.remove('hidden'); $('#status').textContent = result.status; $('#status').className = result.status === 'COMPLIANT' ? 'ok' : 'bad';
    $('#extracted').textContent = JSON.stringify(result.extracted, null, 2);
    $('#viol').innerHTML = result.violations.length ? result.violations.map(v => `<li class="${escapeHtml(v.severity)}"><b>[${escapeHtml(v.severity)}]</b> ${escapeHtml(v.rule_id)} — ${escapeHtml(v.message)}</li>`).join('') : '<li class="ok">No critical or major issues flagged. Continue manual inspection.</li>';
    $('#pdf').href = '/api/report/' + encodeURIComponent(result.scan_id) + '.pdf'; $('#confidence').textContent = `OCR confidence: ${Math.round((result.extracted.ocr_confidence || 0) * 100)}% • Engine: ${result.engine}`;
  } catch (e) { $('#error').textContent = e.message; $('#result').classList.add('hidden'); } finally { button.disabled = false; button.textContent = 'Analyze Label'; }
};

async function loadHistory() {
  try {
    const params = new URLSearchParams(); if ($('#search').value.trim()) params.set('q', $('#search').value.trim()); if ($('#statusFilter').value) params.set('status', $('#statusFilter').value);
    const rows = await api('/api/scans?' + params.toString());
    $('#tbl').innerHTML = '<tr><th>ID</th><th>Product</th><th>Category</th><th>Status</th><th>Date</th><th>Report</th></tr>' + rows.map(s => `<tr><td>${escapeHtml(s.id)}</td><td>${escapeHtml(s.product_name)}</td><td>${escapeHtml(s.category)}</td><td class="${s.status === 'COMPLIANT' ? 'ok' : 'bad'}">${escapeHtml(s.status)}</td><td>${escapeHtml(new Date(s.created_at * 1000).toLocaleString())}</td><td><a href="/api/report/${encodeURIComponent(s.id)}.pdf" target="_blank" rel="noopener">PDF</a></td></tr>`).join('');
  } catch (e) { $('#tbl').innerHTML = `<tr><td colspan="6" class="bad">${escapeHtml(e.message)}</td></tr>`; }
}
$('#refresh').onclick = loadHistory;
$('#search').onkeydown = e => { if (e.key === 'Enter') loadHistory(); };

async function loadDash() {
  try {
    const d = await api('/api/dashboard'); $('#k_total').textContent = d.total_scans; $('#k_nc').textContent = d.non_compliant; $('#k_rate').textContent = d.compliance_rate + '%';
    if (ruleChart) ruleChart.destroy(); if (severityChart) severityChart.destroy();
    ruleChart = new Chart($('#ch_rule'), {type:'bar', data:{labels:d.violations_by_rule.map(x=>x.rule_id), datasets:[{label:'Findings',data:d.violations_by_rule.map(x=>x.c)}]}, options:{responsive:true,maintainAspectRatio:false}});
    severityChart = new Chart($('#ch_sev'), {type:'doughnut',data:{labels:d.violations_by_severity.map(x=>x.severity),datasets:[{data:d.violations_by_severity.map(x=>x.c)}]},options:{responsive:true,maintainAspectRatio:false}});
  } catch (e) { console.error(e); }
}
