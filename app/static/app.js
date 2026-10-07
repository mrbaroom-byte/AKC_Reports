/* Shared helpers: escaping, number formats, requests, toasts and the confirm/ask dialog. */
const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const AR_DIG = '٠١٢٣٤٥٦٧٨٩';
/* «1,234.5», «١٢٣٫٤», «%7.24-», «(3.1)» -> number, or null */
function toNum(v) {
  if (v === null || v === undefined) return null;
  if (typeof v === 'number') return isFinite(v) ? v : null;
  let t = String(v).trim().replace(/[٠-٩]/g, d => AR_DIG.indexOf(d)).replace('٫', '.').replace(/[٬,\s]/g, '');
  if (!t) return null;
  const neg = /^\(.*\)$/.test(t) || /-$/.test(t.replace(/%/g, '')) || /^-/.test(t.replace(/%/g, ''));
  const m = t.match(/\d+(?:\.\d+)?/); if (!m) return null;
  const n = Number(m[0]); return neg ? -n : n;
}
const nf = (v, dp = 0) => v === null || v === undefined || v === '' || !isFinite(v) ? '—' : Number(v).toLocaleString('en-US', {minimumFractionDigits: dp, maximumFractionDigits: dp});
const pc = (v, dp = 2) => v === null || v === undefined || !isFinite(v) ? '—' : (v > 0 ? '+' : '') + Number(v).toFixed(dp) + '%';

async function api(url, body, opts = {}) {
  const r = await fetch(url, {method: opts.method || 'POST', headers: {'Content-Type': 'application/json'}, body: opts.method === 'GET' ? undefined : JSON.stringify(body || {})});
  if (r.status === 401) { location.href = '/login'; throw new Error('login'); }
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.msg || ('تعذّر الإجراء (' + r.status + ').'));
  return j;
}
const getj = url => api(url, null, {method: 'GET'});

function toast(msg, kind = '', ms = 3800) {
  let box = $('.toasts'); if (!box) { box = document.createElement('div'); box.className = 'toasts'; box.setAttribute('role', 'status'); box.setAttribute('aria-live', 'polite'); document.body.appendChild(box); }
  const t = document.createElement('div'); t.className = 'toast ' + kind; t.textContent = msg; box.appendChild(t);
  setTimeout(() => { t.classList.add('out'); setTimeout(() => t.remove(), 250); }, ms);
}

/* ask({title, text, ok, cancel, input:'placeholder', required}) -> Promise<string|true|null> */
function ask(o) {
  return new Promise(res => {
    const d = document.createElement('dialog');
    d.innerHTML = `<form method="dialog"><div class="dh"><h2>${esc(o.title)}</h2></div><div class="db">${o.html || (o.text ? '<p style="margin:0">' + esc(o.text) + '</p>' : '')}
      ${o.input !== undefined ? `<textarea name="v" placeholder="${esc(o.input)}"></textarea>` : ''}</div>
      <div class="df"><button class="btn" value="cancel" type="submit">${esc(o.cancel || 'رجوع')}</button><button class="btn ${o.tone || 'primary'}" value="ok" type="submit">${esc(o.ok || 'متابعة')}</button></div></form>`;
    document.body.appendChild(d);
    const ta = $('textarea', d);
    d.addEventListener('close', () => { const ok = d.returnValue === 'ok'; const v = ta ? ta.value.trim() : true; d.remove(); res(ok ? v : null); });
    $('form', d).addEventListener('submit', e => {
      if (e.submitter && e.submitter.value === 'ok' && o.required && ta && ta.value.trim().length < o.required) { e.preventDefault(); ta.classList.add('bad'); ta.focus(); }
    });
    d.showModal(); (ta || $('[value=ok]', d)).focus();
  });
}

function busy(btn, on, label) {
  if (!btn) return;
  if (on) { btn.dataset.html = btn.innerHTML; btn.disabled = true; btn.innerHTML = '<span class="spin"></span>' + esc(label || btn.textContent); }
  else { btn.disabled = false; if (btn.dataset.html) btn.innerHTML = btn.dataset.html; }
}
