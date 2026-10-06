/* Julien's AI Brief — shared helpers (no build step, no frameworks). */
(function () {
  'use strict';

  const NAME = "Julien's AI Brief";
  const BYLINE = 'by Julien Hovan';
  const API_BASE = 'https://ai-news-signup.julienh15.workers.dev';
  const TURNSTILE_SITEKEY = '0x4AAAAAACJzh42Fo2l_kMqP';
  const TURNSTILE_SRC = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';

  // Site root (the directory holding site.js), so links work from docs/ and docs/archive/.
  const ROOT = new URL('.', document.currentScript.src).href;

  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const MONTHS_LONG = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
    'August', 'September', 'October', 'November', 'December'];
  const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  function escapeHtml(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
  }

  // Escape text and wrap case-insensitive matches of `query` in <mark>.
  function highlight(text, query) {
    text = String(text == null ? '' : text);
    if (!query) return escapeHtml(text);
    const lower = text.toLowerCase();
    const q = query.toLowerCase();
    let out = '';
    let i = 0;
    let at;
    while ((at = lower.indexOf(q, i)) !== -1) {
      out += escapeHtml(text.slice(i, at)) + '<mark>' + escapeHtml(text.slice(at, at + q.length)) + '</mark>';
      i = at + q.length;
    }
    return out + escapeHtml(text.slice(i));
  }

  function parseDay(ymd) {
    const [y, m, d] = String(ymd).split('-').map(Number);
    return new Date(y, (m || 1) - 1, d || 1);
  }

  // "Sep 29 – Oct 1, 2026", "Sep 22 – 24, 2026", "Dec 30, 2025 – Jan 1, 2026"
  function formatDateRange(start, end) {
    const a = parseDay(start);
    const b = parseDay(end || start);
    const ma = MONTHS[a.getMonth()];
    const mb = MONTHS[b.getMonth()];
    if (a.getFullYear() !== b.getFullYear()) {
      return `${ma} ${a.getDate()}, ${a.getFullYear()} – ${mb} ${b.getDate()}, ${b.getFullYear()}`;
    }
    if (a.getTime() === b.getTime()) return `${ma} ${a.getDate()}, ${a.getFullYear()}`;
    if (a.getMonth() === b.getMonth()) return `${ma} ${a.getDate()} – ${b.getDate()}, ${b.getFullYear()}`;
    return `${ma} ${a.getDate()} – ${mb} ${b.getDate()}, ${b.getFullYear()}`;
  }

  // "Thu, Oct 1, 2026"
  function formatDay(dateish) {
    const d = typeof dateish === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(dateish) ? parseDay(dateish) : new Date(dateish);
    if (isNaN(d)) return '';
    return `${DAYS[d.getDay()]}, ${MONTHS[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
  }

  // "October 2026"
  function monthLabel(ymd) {
    const d = parseDay(ymd);
    return `${MONTHS_LONG[d.getMonth()]} ${d.getFullYear()}`;
  }

  function rangeOf(report) {
    return formatDateRange(report.date_range_start, report.date_range_end);
  }

  // Headline if the report has one, otherwise the formatted date range.
  function headingOf(report) {
    return (report.headline && String(report.headline).trim()) || rangeOf(report);
  }

  function itemsLabel(report) {
    const n = Number(report.total_items);
    return n ? `${n.toLocaleString('en-US')} items scanned` : '';
  }

  function listOf(value) {
    return Array.isArray(value) ? value.filter((v) => typeof v === 'string' && v.trim()) : [];
  }

  function issueHref(id) {
    return ROOT + 'issue.html' + (id ? '?id=' + encodeURIComponent(id) : '');
  }

  function reportUrl(id) {
    return `${API_BASE}/archive/${encodeURIComponent(id)}`;
  }

  // Newest first: date_range_end desc, then generated_at desc.
  function compareReports(a, b) {
    if (a.date_range_end !== b.date_range_end) return a.date_range_end < b.date_range_end ? 1 : -1;
    const ga = String(a.generated_at || '');
    const gb = String(b.generated_at || '');
    return ga === gb ? 0 : ga < gb ? 1 : -1;
  }

  // Keep one report per date range (the latest generated_at). Expects sorted input.
  function dedupe(sorted) {
    const seen = new Set();
    return sorted.filter((r) => {
      const key = r.date_range_start + '|' + r.date_range_end;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  let archivePromise = null;

  // Resolves to { reports: deduped newest-first list, all: every report incl. duplicates }.
  function fetchArchive() {
    if (!archivePromise) {
      archivePromise = fetch(`${API_BASE}/archive`)
        .then((res) => {
          if (!res.ok) throw new Error(`Archive request failed (${res.status})`);
          return res.json();
        })
        .then((body) => {
          if (!body || !body.success || !body.data || !Array.isArray(body.data.reports)) {
            throw new Error((body && body.error) || 'Unexpected archive response');
          }
          const all = body.data.reports.filter((r) => r && r.id && r.date_range_end).slice().sort(compareReports);
          return { reports: dedupe(all), all, updatedAt: body.data.updated_at };
        });
      archivePromise.catch(() => { archivePromise = null; });
    }
    return archivePromise;
  }

  // Card used on the home "Recent issues" grid and the archive (cards view).
  function issueCardHtml(report, opts) {
    opts = opts || {};
    const q = opts.query || '';
    const hasHeadline = !!(report.headline && String(report.headline).trim());
    const stories = listOf(report.top_stories).slice(0, 3);
    const tags = listOf(report.tags);
    const dateLine = hasHeadline ? rangeOf(report) : 'Published ' + formatDay(report.generated_at || report.date_range_end);
    let body = '';
    if (stories.length) {
      body = `<ul>${stories.map((s) => `<li>${highlight(s, q)}</li>`).join('')}</ul>`;
    } else if (report.tldr) {
      body = `<p class="tldr-line">${highlight(report.tldr, q)}</p>`;
    }
    return `
<article class="issue">
  <div class="date"><span>${escapeHtml(dateLine)}</span>${opts.isNew ? '<span class="new">NEW</span>' : ''}<span class="count">${escapeHtml(itemsLabel(report))}</span></div>
  <h4><a href="${escapeHtml(issueHref(report.id))}">${highlight(headingOf(report), q)}</a></h4>
  ${body}
  ${tags.length ? `<div class="chips">${tags.map((t) => `<span class="chip">${escapeHtml(t)}</span>`).join('')}</div>` : ''}
</article>`;
  }

  // ---------- signup ----------

  let turnstilePromise = null;

  function loadTurnstile() {
    if (window.turnstile) return Promise.resolve(window.turnstile);
    if (!turnstilePromise) {
      turnstilePromise = new Promise((resolve, reject) => {
        const s = document.createElement('script');
        s.src = TURNSTILE_SRC;
        s.async = true;
        s.onload = () => (window.turnstile ? resolve(window.turnstile) : reject(new Error('Turnstile unavailable')));
        s.onerror = () => { turnstilePromise = null; reject(new Error('Turnstile failed to load')); };
        document.head.appendChild(s);
      });
    }
    return turnstilePromise;
  }

  let signupCount = 0;

  // Render an email + Subscribe form into `container`. Name field and Turnstile
  // reveal on first focus (or first submit), each form gets its own widget.
  function mountSignup(container, opts) {
    opts = opts || {};
    const n = ++signupCount;
    const emailId = opts.emailId || `signup-email-${n}`;
    const nameId = `signup-name-${n}`;
    container.classList.add('signup-wrap');
    container.innerHTML = `
<form class="signup" novalidate>
  <label class="visually-hidden" for="${emailId}">Email address</label>
  <input id="${emailId}" type="email" name="email" placeholder="you@example.com" autocomplete="email" required>
  <button class="btn" type="submit">Subscribe</button>
</form>
<div class="signup-extra">
  <label class="visually-hidden" for="${nameId}">First name (optional)</label>
  <input id="${nameId}" type="text" name="name" placeholder="First name (optional)" autocomplete="given-name">
  <div class="ts-slot"></div>
</div>
<p class="form-error" role="alert" aria-live="polite"></p>`;

    const form = container.querySelector('form');
    const email = container.querySelector('input[type="email"]');
    const nameInput = container.querySelector(`#${nameId}`);
    const button = form.querySelector('button');
    const extra = container.querySelector('.signup-extra');
    const slot = container.querySelector('.ts-slot');
    const error = container.querySelector('.form-error');
    let token = null;
    let widgetId = null;
    let revealed = false;

    function showError(msg) { error.textContent = msg || ''; }

    function reveal() {
      if (revealed) return;
      revealed = true;
      extra.classList.add('show');
      loadTurnstile()
        .then((ts) => {
          widgetId = ts.render(slot, {
            sitekey: TURNSTILE_SITEKEY,
            theme: 'auto',
            callback: (t) => {
              token = t;
              if (/verification/.test(error.textContent)) showError('');
            },
            'expired-callback': () => { token = null; },
            'error-callback': () => { token = null; },
          });
        })
        .catch(() => {
          slot.classList.add('hidden');
          showError('Could not load the verification widget. Disable blockers or try again later.');
        });
    }

    email.addEventListener('focus', reveal);

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      showError('');
      reveal();
      const value = email.value.trim();
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
        showError('Enter a valid email address.');
        email.focus();
        return;
      }
      if (!token) {
        showError('One more step: complete the verification below.');
        return;
      }
      button.disabled = true;
      button.classList.add('loading');
      try {
        const name = nameInput.value.trim();
        const res = await fetch(`${API_BASE}/subscribe`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: value, name: name || undefined, turnstileToken: token }),
        });
        let data = {};
        try { data = await res.json(); } catch (_) { /* non-JSON error body */ }
        if (res.ok) {
          window.location.href = ROOT + 'success.html';
          return;
        }
        showError(data.error || data.message || 'Something went wrong. Please try again.');
      } catch (_) {
        showError('Unable to connect. Check your connection and try again.');
      }
      // Turnstile tokens are single-use, so get a fresh one before retrying.
      token = null;
      if (window.turnstile && widgetId !== null) window.turnstile.reset(widgetId);
      button.disabled = false;
      button.classList.remove('loading');
    });

    return { form, email };
  }

  window.Brief = {
    NAME, BYLINE, API_BASE, ROOT,
    escapeHtml, highlight, formatDateRange, formatDay, monthLabel, parseDay,
    rangeOf, headingOf, itemsLabel, listOf, issueHref, reportUrl,
    compareReports, dedupe, fetchArchive, issueCardHtml, mountSignup,
  };
})();
