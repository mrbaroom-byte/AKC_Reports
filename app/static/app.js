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

/* ask({title, text|html, ok, cancel, input:'placeholder', value, dir, required, wide, collect(d)}) -> Promise<string|true|null>
   collect(d) runs before the dialog closes; its result is left on o.collected */
function ask(o) {
  return new Promise(res => {
    const d = document.createElement('dialog'); if (o.wide) d.className = 'wide';
    d.innerHTML = `<form method="dialog"><div class="dh"><h2>${esc(o.title)}</h2></div><div class="db">${o.html || (o.text ? '<p style="margin:0">' + esc(o.text) + '</p>' : '')}
      ${o.input !== undefined ? `<textarea name="v" dir="${esc(o.dir || 'auto')}" placeholder="${esc(o.input)}"></textarea>` : ''}</div>
      <div class="df"><button class="btn" value="cancel" type="submit">${esc(o.cancel || 'رجوع')}</button><button class="btn ${o.tone || 'primary'}" value="ok" type="submit">${esc(o.ok || 'متابعة')}</button></div></form>`;
    document.body.appendChild(d);
    const ta = $('textarea', d); if (ta && o.value) { ta.value = o.value; ta.style.minHeight = '260px'; }
    d.addEventListener('close', () => { const ok = d.returnValue === 'ok'; if (ok && o.collect) o.collected = o.collect(d); const v = ta ? ta.value.trim() : true; d.remove(); res(ok ? v : null); });
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

/* theme: system / light / dark, remembered in a cookie so the server renders the same theme (no flash) */
(function () {
  const NAMES = {system: 'تلقائي', light: 'فاتح', dark: 'داكن'}, ORDER = ['system', 'light', 'dark'];
  function apply(t) {
    const r = document.documentElement;
    if (t === 'system') r.removeAttribute('data-theme'); else r.dataset.theme = t;
    const b = document.getElementById('themeBtn'); if (!b) return;
    b.dataset.v = t; b.querySelectorAll('svg').forEach(s => s.style.display = s.dataset.i === t ? '' : 'none');
    const label = 'المظهر' + ': ' + NAMES[t]; b.setAttribute('aria-label', label); b.title = label;
  }
  document.addEventListener('DOMContentLoaded', () => {
    const b = document.getElementById('themeBtn'); if (!b) return;
    apply(b.dataset.v || 'system');
    b.addEventListener('click', () => {
      const t = ORDER[(ORDER.indexOf(b.dataset.v || 'system') + 1) % 3]; apply(t);
      document.cookie = 'theme=' + t + ';path=/;max-age=31536000;samesite=lax' + (location.protocol === 'https:' ? ';secure' : '');
    });
  });
})();

/* ---------- assistant panel ---------- */
(function () {
  const KEY = 'akc-asst';
  let msgs = []; try { msgs = JSON.parse(sessionStorage.getItem(KEY) || '[]'); } catch (e) { msgs = []; }
  const save = () => { try { sessionStorage.setItem(KEY, JSON.stringify(msgs.slice(-30))); } catch (e) {} };
  const md = t => esc(t).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/^- (.*)$/gm, '<li>$1</li>').replace(/(<li>.*<\/li>\n?)+/g, m => '<ul>' + m + '</ul>').replace(/\n/g, '<br>');
  function draw() {
    const box = $('#asstMsgs'); if (!box) return;
    box.innerHTML = msgs.map(m => `<div class="m ${m.role}">${m.role === 'user' ? esc(m.content) : md(m.content)}${(m.actions || []).map(a => a.kind === 'edit'
      ? `<div class="act">عُدّل ${esc(a.label || a.fund + ' · ' + a.q)} (${a.n} تغيير) <button type="button" class="btn sm" data-undo="${a.undo}" ${a.undone ? 'disabled' : ''}>${a.undone ? 'تم التراجع' : 'تراجع'}</button>${document.body.dataset.fund === a.fund && document.body.dataset.q === a.q ? ' <button type="button" class="btn sm" data-reload>تحديث الصفحة</button>' : ''}</div>`
      : `<div class="act">أُضيف إلى مسودة تصحيح ${esc(a.fund)} · ${esc(a.q)} (${a.n} تغيير) <a class="btn sm" href="/r/${esc(a.fund)}/${esc(a.q)}">فتح البيان</a></div>`).join('')}</div>`).join('');
    $('#asstSugg').hidden = msgs.length > 0; box.scrollTop = box.scrollHeight;
  }
  function open(v) {
    const p = $('#asst'), b = $('#asstBtn'); if (!p) return;
    p.hidden = !v; b.setAttribute('aria-expanded', v ? 'true' : 'false'); if (v) { draw(); $('#asstIn').focus(); } else b.focus();
  }
  async function send(text) {
    text = (text || '').trim(); if (!text) return;
    msgs.push({role: 'user', content: text}); save(); draw(); $('#asstIn').value = '';
    const go = $('#asstGo'); busy(go, true, '…');
    const wait = document.createElement('div'); wait.className = 'm assistant wait'; wait.innerHTML = '<span class="spin"></span>'; $('#asstMsgs').appendChild(wait);
    try {
      const r = await api('/api/assistant', {messages: msgs.map(m => ({role: m.role, content: m.content})), page: {fund: document.body.dataset.fund, q: document.body.dataset.q}});
      msgs.push({role: 'assistant', content: r.text || '—', actions: r.actions || []});
    } catch (e) { msgs.push({role: 'assistant', content: e.message}); }
    finally { busy(go, false); save(); draw(); }
  }
  document.addEventListener('DOMContentLoaded', () => {
    if (!$('#asst')) return;
    $('#asstBtn').addEventListener('click', () => open($('#asst').hidden));
    $('#asstX').addEventListener('click', () => open(false));
    $('#asstNew').addEventListener('click', () => { msgs = []; save(); draw(); $('#asstIn').focus(); });
    $('#asstF').addEventListener('submit', e => { e.preventDefault(); send($('#asstIn').value); });
    $('#asstIn').addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send($('#asstIn').value); } });
    $$('#asstSugg .chip').forEach(c => c.addEventListener('click', () => send(c.textContent)));
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && !$('#asst').hidden) open(false); });
    $('#asstMsgs').addEventListener('click', async e => {
      const u = e.target.closest('[data-undo]'); if (u) {
        try { await api('/api/assistant/undo/' + u.dataset.undo); msgs.forEach(m => (m.actions || []).forEach(a => { if (String(a.undo) === u.dataset.undo) a.undone = true; })); save(); draw(); toast('تم التراجع عن التعديل.'); }
        catch (err) { toast(err.message, 'bad'); }
      }
      if (e.target.closest('[data-reload]')) location.reload();
    });
  });
})();
