/* EventHub frontend – vanilla JS. One file, one init function per page (body[data-page]). */
(() => {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const page = document.body.dataset.page;

  // ---------- tiny DOM helper (textContent only -> no XSS) ----------
  function h(tag, attrs = {}, ...kids) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null || v === false) continue;
      if (k === 'class') e.className = v;
      else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v === true ? '' : v);
    }
    for (const k of kids.flat()) if (k != null && k !== false) e.append(k.nodeType ? k : document.createTextNode(String(k)));
    return e;
  }

  // ---------- API client with CSRF ----------
  let csrf = null;
  async function token() {
    if (!csrf) csrf = (await (await fetch('/csrf-token', { credentials: 'same-origin' })).json()).csrf_token;
    return csrf;
  }
  async function api(path, { method = 'GET', body } = {}) {
    const opts = { method, credentials: 'same-origin', headers: {} };
    if (method !== 'GET') {
      opts.headers['Content-Type'] = 'application/json';
      try { opts.headers['X-CSRF-Token'] = await token(); } catch { throw { status: 0, error: 'Cannot reach the server. Is it running?' }; }
      if (body !== undefined) opts.body = JSON.stringify(body);
    }
    let res;
    try { res = await fetch(path, opts); } catch { throw { status: 0, error: 'Cannot reach the server. Is it running?' }; }
    let data = {};
    try { data = await res.json(); } catch { /* non-JSON */ }
    if (!res.ok) { if (res.status === 403) csrf = null; throw { status: res.status, ...data }; }
    return data;
  }

  // ---------- formatting helpers ----------
  const fmtDate = d => new Date(d + 'T00:00:00').toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
  const fmtTime = t => { const [H, M] = t.split(':').map(Number); return `${((H + 11) % 12) + 1}:${String(M).padStart(2, '0')} ${H < 12 ? 'AM' : 'PM'}`; };
  const imgFor = c => `/assets/${String(c).toLowerCase()}.svg`;
  const qs = k => new URLSearchParams(location.search).get(k);

  function say(el, text, type = 'err') { if (!el) return; el.className = `alert ${type}`; el.textContent = text || ''; }
  function toast(text) { const t = h('div', { class: 'toast', role: 'status' }, text); document.body.append(t); setTimeout(() => t.remove(), 2800); }
  function busy(btn, on, label) {
    btn.disabled = on;
    if (on) { btn.dataset.label = btn.textContent; btn.replaceChildren(h('span', { class: 'spin' }), ' ', label || 'Please wait…'); }
    else btn.textContent = btn.dataset.label || btn.textContent;
  }
  function seatBar(ev) {
    const pct = Math.min(100, Math.round((ev.registered / ev.seat_limit) * 100));
    const bar = h('div', { class: 'bar' + (ev.available <= ev.seat_limit * 0.15 ? ' low' : ''), role: 'progressbar', 'aria-valuemin': 0, 'aria-valuemax': ev.seat_limit, 'aria-valuenow': ev.registered, 'aria-label': 'Seats filled' }, h('i'));
    requestAnimationFrame(() => { bar.firstChild.style.width = pct + '%'; });
    return bar;
  }
  const seatsBadge = ev => ev.is_full ? h('span', { class: 'badge err' }, 'Event Full')
    : h('span', { class: 'badge ' + (ev.available <= ev.seat_limit * 0.15 ? 'warn' : 'ok') }, `${ev.available} of ${ev.seat_limit} seats left`);

  // mobile menu (all pages)
  const burger = $('#burger');
  if (burger) burger.addEventListener('click', () => {
    const open = $('#menu').classList.toggle('open'); burger.setAttribute('aria-expanded', open);
  });

  // ---------- field validation (mirrors backend rules) ----------
  const RULES = {
    name: v => !v.trim() ? 'Name is required.' : v.trim().length > 60 ? 'Name must be at most 60 characters.'
      : !/^[\p{L}][\p{L} .'-]*$/u.test(v.trim()) || (v.match(/\p{L}/gu) || []).length < 2 ? 'Use letters and spaces only (at least 2 letters).' : '',
    email: v => !v.trim() ? 'Email is required.' : !/^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$/.test(v.trim()) || v.includes('..') ? 'Enter a valid email (e.g. name@example.com).' : '',
    phone: v => { const p = v.replace(/[\s-]/g, '').replace(/^\+91/, ''); return !p ? 'Phone is required.' : !/^[1-9]\d{9}$/.test(p) ? 'Phone must be exactly 10 digits.' : ''; },
    college: v => v.trim().length > 100 ? 'College must be at most 100 characters.' : v.trim() && !/^[\p{L}\p{N}_\s.,&'()/-]+$/u.test(v.trim()) ? 'College contains invalid characters.' : '',
  };
  function setErr(form, field, msg, errPrefix = 'err-') {
    const box = $('#' + errPrefix + field, form); if (!box) return;
    box.textContent = msg || '';
    box.closest('.field').classList.toggle('bad', !!msg);
  }

  // ====================== HOME ======================
  async function initHome() {
    const grid = $('#events'), msg = $('#eventsMsg');
    let all = [], cat = 'All', term = '';
    grid.replaceChildren(h('div', { class: 'skeleton' }), h('div', { class: 'skeleton' }), h('div', { class: 'skeleton' }));
    try { all = (await api('/events')).events; } catch (e) { grid.replaceChildren(); say(msg, e.error || 'Could not load events.'); return; }
    const cats = ['All', ...new Set(all.map(e => e.category))];
    const chips = $('#chips');
    const draw = () => {
      chips.replaceChildren(...cats.map(c => h('button', { class: 'chip', type: 'button', 'aria-pressed': c === cat, onclick: () => { cat = c; draw(); } }, c)));
      const list = all.filter(e => (cat === 'All' || e.category === cat) && (e.title + ' ' + e.venue).toLowerCase().includes(term));
      grid.replaceChildren(...(list.length ? list.map(card) : [h('div', { class: 'empty' }, 'No events match your search.')]));
    };
    const card = ev => h('article', { class: 'card' },
      h('img', { class: 'img', src: imgFor(ev.category), alt: '', loading: 'lazy' }),
      h('div', { class: 'body' }, h('span', { class: 'badge' }, ev.category), h('h3', {}, ev.title),
        h('div', { class: 'meta' }, h('div', {}, h('b', {}, fmtDate(ev.date)), ' · ', fmtTime(ev.time)), h('div', {}, ev.venue)),
        seatBar(ev), seatsBadge(ev),
        h('div', { class: 'actions' }, h('a', { class: 'btn sec', href: `/event.html?id=${ev.id}` }, 'View details'),
          ev.is_full ? h('span', { class: 'btn', 'aria-disabled': 'true' }, 'Event Full') : h('a', { class: 'btn', href: `/register.html?event_id=${ev.id}` }, 'Register'))));
    $('#q').addEventListener('input', e => { term = e.target.value.trim().toLowerCase(); draw(); });
    const seats = all.reduce((s, e) => s + e.available, 0);
    $('#heroStats').replaceChildren(...[[all.length, 'upcoming events'], [seats, 'open seats'], [cats.length - 1, 'categories']].map(([n, l]) => h('div', {}, h('b', {}, n), h('span', {}, l))));
    draw();
  }

  // ====================== EVENT DETAIL ======================
  async function initEvent() {
    const box = $('#eventBox'), id = qs('id');
    try {
      const ev = (await api('/events/' + encodeURIComponent(id))).event;
      document.title = ev.title + ' – EventHub'; $('#crumb').textContent = ev.title;
      box.replaceChildren(h('div', { class: 'detail' },
        h('div', { class: 'panel' }, h('img', { class: 'cover', src: imgFor(ev.category), alt: '' }),
          h('span', { class: 'badge' }, ev.category), h('h1', {}, ev.title), h('p', {}, ev.description),
          h('h2', {}, 'Schedule'),
          ev.schedule.length ? h('ul', { class: 'timeline' }, ev.schedule.map(line => { const [t, ...r] = line.split(' | '); return r.length ? h('li', {}, h('b', {}, t), r.join(' | ')) : h('li', {}, line); })) : h('p', { class: 'meta' }, 'Schedule to be announced.')),
        h('aside', { class: 'panel sticky' }, h('h2', {}, 'Event info'),
          h('div', { class: 'meta' }, h('div', {}, 'Date: ', h('b', {}, fmtDate(ev.date))), h('div', {}, 'Time: ', h('b', {}, fmtTime(ev.time))), h('div', {}, 'Venue: ', h('b', {}, ev.venue))),
          h('p', {}, seatsBadge(ev)), seatBar(ev),
          h('p', { class: 'meta' }, `${ev.registered} registered · ${ev.available} remaining`),
          ev.is_full ? h('span', { class: 'btn block', 'aria-disabled': 'true' }, 'Event Full') : h('a', { class: 'btn block', href: `/register.html?event_id=${ev.id}` }, 'Register now'))));
    } catch (e) {
      box.replaceChildren();
      say($('#eventMsg'), e.status === 404 ? 'Event not found. It may have been removed.' : (e.error || 'Could not load the event.'));
      box.append(h('a', { class: 'btn sec', href: '/' }, '← Back to events'));
    }
  }

  // ====================== REGISTER ======================
  async function initRegister() {
    const form = $('#regForm'), msg = $('#formMsg'), btn = $('#submitBtn'), id = qs('event_id');
    let ev;
    try {
      ev = (await api('/events/' + encodeURIComponent(id))).event;
      $('#regTitle').textContent = 'Register: ' + ev.title;
      $('#regSub').textContent = `${fmtDate(ev.date)} · ${fmtTime(ev.time)} · ${ev.venue}`;
      if (ev.is_full) { say(msg, 'Event Full: no seats are left for this event.'); form.hidden = true; return; }
    } catch (e) { say(msg, e.status === 404 ? 'Event not found.' : (e.error || 'Could not load the event.')); form.hidden = true; return; }

    for (const f of Object.keys(RULES)) $('#' + f).addEventListener('blur', () => setErr(form, f, RULES[f](form[f].value)));
    form.addEventListener('submit', async e => {
      e.preventDefault(); say(msg, '');
      let bad = false;
      for (const f of Object.keys(RULES)) { const m = RULES[f](form[f].value); setErr(form, f, m); bad = bad || !!m; }
      if (bad) { say(msg, 'Please fix the highlighted fields.'); form.querySelector('.bad input')?.focus(); return; }
      busy(btn, true, 'Registering…');                         // blocks double submission
      try {
        const data = await api('/register', { method: 'POST', body: { event_id: Number(id), name: form.name.value, email: form.email.value, phone: form.phone.value, college: form.college.value, ticket_type: form.ticket_type.value } });
        sessionStorage.setItem('lastReg', JSON.stringify(data.registration));
        location.href = '/success.html';
      } catch (err) {
        busy(btn, false);
        if (err.errors) for (const [f, m] of Object.entries(err.errors)) setErr(form, f, m);
        say(msg, err.error || 'Registration failed.');
        if (err.status === 409 && /Full/i.test(err.error || '')) form.hidden = true;
      }
    });
  }

  // ====================== SUCCESS ======================
  function initSuccess() {
    let r; try { r = JSON.parse(sessionStorage.getItem('lastReg')); } catch { r = null; }
    if (!r) { location.replace('/'); return; }
    $('#regCode').textContent = r.reg_code;
    $('#summary').replaceChildren(...[['Event', r.event_title], ['Date', `${fmtDate(r.date)} · ${fmtTime(r.time)}`], ['Venue', r.venue], ['Name', r.name], ['Email', r.email], ['Ticket', r.ticket_type]]
      .map(([k, v]) => h('div', {}, h('span', {}, k), h('b', {}, v))));
    $('#copyBtn').addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(r.reg_code); toast('Registration ID copied'); } catch { toast('Select the ID and copy it manually'); }
    });
    $('#cancelBtn').addEventListener('click', async e => {
      if (!confirm('Cancel this registration? Your seat will be released.')) return;
      busy(e.target, true, 'Cancelling…');
      try { const d = await api('/cancel', { method: 'POST', body: { reg_code: r.reg_code, email: r.email } }); say($('#cancelMsg'), d.message, 'ok'); sessionStorage.removeItem('lastReg'); e.target.remove(); $('#copyBtn').remove(); }
      catch (err) { busy(e.target, false); say($('#cancelMsg'), err.error || 'Could not cancel.'); }
    });
  }

  // ====================== ORGANIZER LOGIN ======================
  function initLogin() {
    const form = $('#loginForm'), msg = $('#loginMsg'), btn = $('#loginBtn');
    form.addEventListener('submit', async e => {
      e.preventDefault(); say(msg, '');
      if (!form.username.value.trim() || !form.password.value) { say(msg, 'Enter your username and password.'); return; }
      busy(btn, true, 'Signing in…');
      try { await api('/organizer/login', { method: 'POST', body: { username: form.username.value, password: form.password.value } }); csrf = null; location.href = '/organizer.html'; }
      catch (err) { busy(btn, false); say(msg, err.error || 'Login failed.'); }
    });
  }

  // ====================== DASHBOARD ======================
  async function initDashboard() {
    const state = { events: [], eventId: '', q: '' };
    const guard = e => { if (e.status === 401) { location.replace('/organizer_login.html'); return true; } return false; };
    try { $('#who').textContent = 'Signed in as ' + (await api('/organizer/session')).username; } catch (e) { guard(e); return; }

    $('#logoutBtn').addEventListener('click', async () => { try { await api('/organizer/logout', { method: 'POST' }); } catch { /* ignore */ } csrf = null; location.href = '/organizer_login.html'; });

    async function loadEvents() {
      try {
        const d = await api('/organizer/events'); state.events = d.events;
        $('#kpis').replaceChildren(...[['Events', d.totals.events], ['Registrations', d.totals.registrations], ['Checked in', d.totals.checked_in], ['Seats remaining', d.totals.remaining]]
          .map(([l, n]) => h('div', { class: 'kpi' }, h('span', {}, l), h('b', {}, n))));
        $('#evRows').replaceChildren(...state.events.map(ev => h('tr', {},
          h('td', {}, h('b', {}, ev.title), h('div', { class: 'meta' }, ev.category)),
          h('td', {}, fmtDate(ev.date), h('div', { class: 'meta' }, fmtTime(ev.time))), h('td', {}, ev.venue),
          h('td', {}, `${ev.registered} / ${ev.seat_limit}`, h('div', { class: 'mini' }, seatBar(ev))),
          h('td', {}, ev.is_full ? h('span', { class: 'badge err' }, 'Full') : h('span', { class: 'badge ok' }, ev.available + ' left')),
          h('td', {}, h('div', { class: 'cell-actions' },
            h('button', { class: 'btn sec sm', type: 'button', onclick: () => { state.eventId = String(ev.id); $('#evSelect').value = state.eventId; loadRegs(); $('#participants').scrollIntoView(); } }, 'Participants'),
            h('button', { class: 'btn sec sm', type: 'button', onclick: () => openDialog(ev) }, 'Edit'))))));
        const sel = $('#evSelect'), cur = state.eventId;
        sel.replaceChildren(h('option', { value: '' }, 'All events'), ...state.events.map(ev => h('option', { value: ev.id }, ev.title)));
        sel.value = cur;
      } catch (e) { if (!guard(e)) toast(e.error || 'Could not load events'); }
    }

    async function loadRegs() {
      const p = new URLSearchParams(); if (state.eventId) p.set('event_id', state.eventId); if (state.q) p.set('q', state.q);
      $('#exportBtn').href = '/organizer/export?' + p;
      try {
        const d = await api('/organizer/registrations?' + p);
        $('#regRows').replaceChildren(...(d.registrations.length ? d.registrations.map(row) : [h('tr', {}, h('td', { colspan: 8, class: 'empty' }, 'No participants found.'))]));
        $('#regCount').textContent = `${d.total} confirmed registration(s)` + (d.event ? ` for ${d.event.title} · ${d.event.available} seats remaining` : '') + (d.count !== d.total ? ` (${d.count - d.total} cancelled)` : '');
      } catch (e) { if (!guard(e)) toast(e.error || 'Could not load registrations'); }
    }
    const row = r => {
      const cx = r.status === 'cancelled';
      return h('tr', { class: cx ? 'cx' : '' }, h('td', {}, h('code', {}, r.reg_code)), h('td', {}, r.name), h('td', {}, r.email), h('td', {}, r.phone), h('td', {}, r.college || '—'), h('td', {}, r.ticket_type),
        h('td', {}, cx ? h('span', { class: 'badge gray' }, 'Cancelled') : r.checked_in ? h('span', { class: 'badge ok' }, 'Checked in') : h('span', { class: 'badge' }, 'Registered')),
        h('td', {}, cx ? '' : h('div', { class: 'cell-actions' },
          h('button', { class: 'btn sec sm', type: 'button', onclick: () => act(`/organizer/registrations/${r.id}/checkin`, { checked_in: !r.checked_in }) }, r.checked_in ? 'Undo check-in' : 'Check in'),
          h('button', { class: 'btn danger sm', type: 'button', onclick: () => confirm(`Cancel ${r.name}'s registration?`) && act(`/organizer/registrations/${r.id}/cancel`) }, 'Cancel'))));
    };
    async function act(url, body) {
      try { await api(url, { method: 'POST', body: body || {} }); await Promise.all([loadEvents(), loadRegs()]); } catch (e) { if (!guard(e)) toast(e.error || 'Action failed'); }
    }

    $('#evSelect').addEventListener('change', e => { state.eventId = e.target.value; loadRegs(); });
    let timer; $('#pq').addEventListener('input', e => { clearTimeout(timer); timer = setTimeout(() => { state.q = e.target.value.trim(); loadRegs(); }, 250); });

    // ---- create / edit event dialog ----
    const dlg = $('#evDialog'), form = $('#evForm'); let editing = null;
    const F = ['title', 'category', 'seat_limit', 'date', 'time', 'venue', 'description', 'schedule'];
    function openDialog(ev) {
      editing = ev || null; say($('#evMsg'), ''); $('#dlgTitle').textContent = ev ? 'Edit event' : 'New event';
      for (const f of F) { $('#e_' + f).value = ev ? (f === 'schedule' ? ev.schedule.join('\n') : ev[f]) : (f === 'category' ? 'Workshop' : ''); setErr(form, f, ''); }
      dlg.showModal();
    }
    $('#newEvent').addEventListener('click', () => openDialog(null));
    $('#evCancel').addEventListener('click', () => dlg.close());
    form.addEventListener('submit', async e => {
      e.preventDefault(); const btn = $('#evSave'); say($('#evMsg'), '');
      const body = Object.fromEntries(F.map(f => [f, $('#e_' + f).value]));
      busy(btn, true, 'Saving…');
      try {
        await api(editing ? `/organizer/events/${editing.id}` : '/organizer/events', { method: editing ? 'PUT' : 'POST', body });
        dlg.close(); toast(editing ? 'Event updated' : 'Event created'); await Promise.all([loadEvents(), loadRegs()]);
      } catch (err) {
        if (guard(err)) return;
        for (const f of F) setErr(form, f, (err.errors || {})[f] || '');
        say($('#evMsg'), err.error || 'Could not save the event.');
      } finally { busy(btn, false); }
    });

    await loadEvents(); await loadRegs();
  }

  ({ home: initHome, event: initEvent, register: initRegister, success: initSuccess, login: initLogin, dashboard: initDashboard }[page] || (() => {}))();
})();
