
const $ = s => document.querySelector(s);
document.querySelectorAll('.tab').forEach(b => b.onclick = () => {
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
  document.querySelectorAll('.page').forEach(x => x.classList.add('hidden'));
  b.classList.add('active'); $('#' + b.dataset.tab).classList.remove('hidden');
  if (b.dataset.tab === 'history') loadHistory();
  if (b.dataset.tab === 'dash') loadDash();
});

let ocrWorker = null;
async function browserOCR(file) {
  if (typeof Tesseract === 'undefined') return '';
  $('#go').textContent = 'OCR in browser…';
  if (!ocrWorker) ocrWorker = await Tesseract.createWorker('eng');
  const { data } = await ocrWorker.recognize(file);
  return data.text || '';
}

$('#go').onclick = async () => {
  const f = $('#img').files[0];
  if (!f) return alert('Pick a label photo first');
  let ocrText = $('#demo').value.trim();
  if (!ocrText) { try { ocrText = await browserOCR(f); } catch (e) { console.warn(e); } }
  const fd = new FormData();
  fd.append('file', f);
  if ($('#ppm').value) fd.append('px_per_mm', $('#ppm').value);
  fd.append('demo_text', ocrText);   // backend: uses this if server OCR empty
  $('#go').textContent = 'Analyzing…';
  const r = await fetch('/api/scan', {method: 'POST', body: fd}).then(r => r.json());
  $('#go').textContent = 'Analyze Label';
  $('#result').classList.remove('hidden');
  $('#status').textContent = r.status + (r.engine ? ' (' + r.engine + ')' : '');
  $('#status').className = r.status === 'COMPLIANT' ? 'ok' : 'bad';
  $('#extracted').textContent = JSON.stringify(r.extracted, null, 2);
  $('#viol').innerHTML = r.violations.length
    ? r.violations.map(v => `<li class="${v.severity}"><b>[${v.severity}]</b> Rule ${v.rule_id}: ${v.message}</li>`).join('')
    : '<li class="ok">No violations detected.</li>';
  $('#pdf').href = '/api/report/' + r.scan_id + '.pdf';
};

async function loadHistory() {
  const rows = await fetch('/api/scans').then(r => r.json());
  $('#tbl').innerHTML = '<tr><th>ID</th><th>Product</th><th>Status</th><th>Date</th><th></th></tr>' +
    rows.map(s => `<tr><td>${s.id}</td><td>${s.product_name}</td>
      <td class="${s.status === 'COMPLIANT' ? 'ok' : 'bad'}">${s.status}</td>
      <td>${new Date(s.created_at * 1000).toLocaleString()}</td>
      <td><a href="/api/report/${s.id}.pdf" target="_blank">PDF</a></td></tr>`).join('');
}

async function loadDash() {
  const d = await fetch('/api/dashboard').then(r => r.json());
  $('#k_total').textContent = d.total_scans;
  $('#k_nc').textContent = d.non_compliant;
  $('#k_rate').textContent = d.compliance_rate + '%';
  new Chart($('#ch_rule'), {type: 'bar', data: {
    labels: d.violations_by_rule.map(x => x.rule_id),
    datasets: [{label: 'Violations', data: d.violations_by_rule.map(x => x.c), backgroundColor: '#e05d44'}]}});
  new Chart($('#ch_sev'), {type: 'doughnut', data: {
    labels: d.violations_by_severity.map(x => x.severity),
    datasets: [{data: d.violations_by_severity.map(x => x.c),
      backgroundColor: ['#c0392b', '#e67e22', '#f1c40f', '#7f8c8d']} ]}});
}
