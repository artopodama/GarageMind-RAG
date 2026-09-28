(() => {
  'use strict';

  const DATA = {
    Toyota: ['Corolla', 'Camry', 'RAV4', 'Prius'],
    Honda: ['Civic', 'CR-V', 'Accord'],
    Ford: ['F-150', 'Escape', 'Explorer'],
    Subaru: ['Outback', 'Forester'],
  };
  const YEARS = [2024, 2023, 2022, 2021, 2020, 2019, 2018];

  const INTENTS = [
    {
      id: 'tyre', safety: true, keys: ['tyre pressure', 'tire pressure', 'psi', 'tyre', 'tire'],
      ans: v => `The recommended cold tyre pressure for the ${v} is 32 psi front and rear for normal loads. Always check the tyre placard on the driver's-side door jamb, and inflate only when the tyres are cold.`,
      title: 'Tyres & Wheels', ref: 'p.214',
      ex: '“Recommended tyre inflation pressure (cold): Front 32 psi (220 kPa), Rear 32 psi (220 kPa). Refer to the tyre and loading information label on the driver\'s door pillar for vehicle-specific values.”',
    },
    {
      id: 'brake', safety: true, keys: ['brake fluid', 'brake'],
      ans: v => `For the ${v}, replace the brake fluid every 3 years or 45,000 km, whichever comes first, using DOT 3 or SAE J1703 fluid. Do not mix fluid types, and never let the reservoir run dry.`,
      title: 'Maintenance & Care', ref: 'p.176',
      ex: '“Brake fluid: Inspect at every service. Replace every 36 months regardless of mileage. Use only DOT 3 brake fluid from a sealed container.”',
    },
    {
      id: 'coolant', safety: true, keys: ['coolant', 'antifreeze', 'fluid capacity', 'capacity'],
      ans: v => `The engine coolant capacity for the ${v} is approximately 6.4 L of Super Long Life Coolant (or equivalent, pre-mixed). Only remove the radiator cap or add coolant when the engine is completely cold.`,
      title: 'Fluid Capacities', ref: 'p.240',
      ex: '“Engine coolant capacity (with heater): 6.4 L. Use Toyota Super Long Life Coolant or similar high-quality ethylene-glycol based non-silicate coolant. WARNING: Do not remove the cap while hot.”',
    },
    {
      id: 'oil_light', safety: false, keys: ['oil warning', 'oil light', 'oil pressure light', 'warning light', 'dashboard light'],
      ans: v => `On the ${v}, the oil pressure warning light means engine oil pressure has dropped too low. Pull over safely as soon as possible, switch off the engine, and check the oil level. Do not keep driving — low oil pressure can cause serious engine damage.`,
      title: 'Warning Lights & Indicators', ref: 'p.88',
      ex: '“Oil pressure warning light: If this light illuminates while driving, stop the vehicle in a safe place immediately and turn off the engine. Continuing to drive may cause severe engine damage.”',
    },
    {
      id: 'oil_change', safety: false, keys: ['change oil', 'oil change', 'change the oil', 'oil interval', 'how often oil', 'service interval'],
      ans: v => `For the ${v} under normal driving, change the engine oil and filter every 10,000 km or 12 months, whichever comes first. Under severe conditions (short trips, towing, dusty roads), shorten this to every 5,000 km or 6 months.`,
      title: 'Maintenance Schedule', ref: 'p.162',
      ex: '“Engine oil & filter: Replace every 10,000 km or 12 months. Severe operating conditions: every 5,000 km or 6 months. Use 0W-20 full-synthetic oil.”',
    },
    {
      id: 'wiper', safety: false, keys: ['wiper', 'windshield', 'windscreen', 'blade'],
      ans: v => `To replace the wiper blades on the ${v}: lift the wiper arm away from the glass, press the release tab on the blade, slide the old blade down and off, then click the new blade into place until it locks. Gently lower the arm back onto the glass.`,
      title: 'Maintenance & Care', ref: 'p.198',
      ex: '“Wiper blade replacement: Raise the wiper arm. Press the lock lever and slide the blade assembly downward. Install the new blade in reverse order, ensuring it clicks into position.”',
    },
  ];

  const LOADING_STEPS = ['Scoping to your vehicle', 'Searching manual', 'Checking sources'];

  const state = {
    vehicle: null,
    messages: [],
    input: '',
    selOpen: false,
    selMake: null,
    pendingQuestion: null,
    expanded: {},
  };

  const el = {
    chip: document.getElementById('vehicleChip'),
    chipLabel: document.getElementById('chipLabel'),
    selectorPanel: document.getElementById('selectorPanel'),
    selectorBack: document.getElementById('selectorBack'),
    selectorTitle: document.getElementById('selectorTitle'),
    selectorList: document.getElementById('selectorList'),
    messages: document.getElementById('messages'),
    emptyState: document.getElementById('emptyState'),
    messageList: document.getElementById('messageList'),
    exampleChips: document.getElementById('exampleChips'),
    input: document.getElementById('input'),
    sendBtn: document.getElementById('sendBtn'),
    pickVehicleCard: document.getElementById('pickVehicleCard'),
    justAskCard: document.getElementById('justAskCard'),
  };

  const uid = () => Math.random().toString(36).slice(2, 9);
  const vLabel = v => { const x = v || state.vehicle; return x ? `${x.year} ${x.make} ${x.model}` : null; };
  const escapeHtml = s => s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  function parseVehicle(textIn) {
    const t = textIn.toLowerCase();
    const ym = t.match(/(20[0-2]\d)/);
    let make = null, model = null;
    for (const mk of Object.keys(DATA)) {
      if (t.includes(mk.toLowerCase())) { make = mk; break; }
    }
    if (make) {
      for (const md of DATA[make]) {
        if (t.includes(md.toLowerCase().replace('-', '')) || t.includes(md.toLowerCase())) { model = md; break; }
      }
    }
    if (make && model) {
      const year = ym ? +ym[1] : YEARS[1];
      return { make, model, year };
    }
    return null;
  }

  function detectIntent(textIn) {
    const t = textIn.toLowerCase();
    if (/^(hi|hey|hello|thanks|thank you|yo|good (morning|afternoon))\b/.test(t)) return { id: 'greeting' };
    for (const it of INTENTS) {
      if (it.keys.some(k => t.includes(k))) return it;
    }
    return { id: 'refusal' };
  }

  // Message DOM nodes are created once and patched in place -- rebuilding the
  // whole list on every update (e.g. a single citation toggle) restarted the
  // fadeUp animation on every row at once, which briefly flashed the entire
  // conversation to opacity 0.
  const messageNodes = new Map();

  function mountMessageNode(m) {
    const wrapper = document.createElement('div');
    wrapper.innerHTML = messageRowHtml(m);
    const node = wrapper.firstElementChild;
    messageNodes.set(m.id, node);
    el.messageList.appendChild(node);
  }

  function patchMessageNode(id) {
    const m = state.messages.find(m => m.id === id);
    if (!m) return;
    const wrapper = document.createElement('div');
    wrapper.innerHTML = messageRowHtml(m);
    const node = wrapper.firstElementChild;
    const old = messageNodes.get(id);
    messageNodes.set(id, node);
    if (old && old.parentNode) old.replaceWith(node);
    else el.messageList.appendChild(node);
  }

  function push(msg) {
    state.messages.push(msg);
    el.emptyState.style.display = 'none';
    mountMessageNode(msg);
    renderExampleChips();
    scrollToBottom();
  }
  function updateMessage(id, patch) {
    const m = state.messages.find(m => m.id === id);
    if (m) Object.assign(m, patch);
    patchMessageNode(id);
    scrollToBottom();
  }
  function scrollToBottom() { el.messages.scrollTop = el.messages.scrollHeight; }

  function send(raw) {
    const text = (raw !== undefined ? raw : state.input).trim();
    if (!text) return;
    push({ id: uid(), role: 'user', text });
    state.input = '';
    el.input.value = '';
    el.input.style.height = 'auto';
    updateSendState();

    const parsed = parseVehicle(text);
    const pending = state.pendingQuestion;
    if (parsed) {
      state.vehicle = parsed;
      state.pendingQuestion = null;
      renderChip();
      renderExampleChips();
      if (pending) { setTimeout(() => answer(pending, parsed), 250); return; }
    }

    const intent = detectIntent(text);
    if (intent.id === 'greeting') {
      setTimeout(() => push({
        id: uid(), role: 'assistant', kind: 'clarify',
        text: state.vehicle
          ? `Hi! Ask me anything about your ${vLabel()} — tyre pressure, service intervals, warning lights and more.`
          : "Hi! Tell me your car's make, model and year, or just ask a question and I'll request it only if needed.",
      }), 350);
      return;
    }

    const v = parsed || state.vehicle;
    if (intent.id !== 'refusal' && !v) {
      setTimeout(() => push({
        id: uid(), role: 'assistant', kind: 'clarify',
        text: 'Happy to check that — which car is it? Tell me the make, model and year (e.g. "2020 Toyota Corolla").',
      }), 350);
      state.pendingQuestion = text;
      return;
    }
    answer(text, v);
  }

  // Ask the real RAG backend. Falls back to the local canned answers (mock)
  // only if the API is unreachable, so the page still demos when opened
  // standalone (e.g. as a static file with no server).
  async function callAsk(text, v) {
    const body = { question: text };
    if (v) { body.make = v.make; body.model = v.model; body.year = v.year; }
    const res = await fetch('/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return res.json();
  }

  function answer(text, v) {
    const id = uid();
    push({ id, role: 'assistant', kind: 'loading', step: 0 });

    // Cycle the three loading steps and hold on the last until the reply lands.
    let step = 0;
    const timer = setInterval(() => {
      step = Math.min(step + 1, 2);
      updateMessage(id, { step });
    }, 620);

    callAsk(text, v)
      .then(data => { clearInterval(timer); renderApiResult(id, data); })
      .catch(() => {
        clearInterval(timer);
        updateMessage(id, {
          kind: 'refusal',
          step: undefined,
          text: 'The assistant is currently unavailable. Please try again later.'
        });
      });
  }

  function renderApiResult(id, data) {
    if (data.refused) {
      updateMessage(id, { kind: 'refusal', step: undefined, text: data.text });
      return;
    }
    const sources = (data.sources || []).map(s => ({
      label: s.label || [s.make, s.model, s.variant].filter(Boolean).join(' '),
      url: s.source_url || '',
      section: s.section || '',
      variant: s.variant || '',
    }));
    updateMessage(id, {
      kind: 'answer', step: undefined,
      safety: !!data.safety_critical,
      text: data.text,
      sources,
      excerpt: data.top_passage || '',
      scoped: !!data.scoped,
    });
  }

  // Offline fallback: the original simulated answer, reshaped to the same
  // {sources, excerpt} model the API path uses so rendering is unified.
  function mockAnswerInto(id, text, v) {
    const intent = detectIntent(text);
    const label = vLabel(v);
    if (intent.id === 'refusal') {
      updateMessage(id, {
        kind: 'refusal', step: undefined,
        text: `I looked through the ${label || 'vehicle'} owner's manual and couldn't find guidance on that. It may fall outside official manual coverage — for example modifications, repairs, or diagnosis beyond routine care.`,
      });
      return;
    }
    updateMessage(id, {
      kind: 'answer', step: undefined, safety: intent.safety,
      text: intent.ans(label || 'your vehicle'),
      sources: [{ label: `${label || 'Vehicle'} — ${intent.title}`, url: '', section: intent.ref, variant: '' }],
      excerpt: intent.ex,
      scoped: !!v,
    });
  }

  function toggleCite(id) {
    state.expanded[id] = !state.expanded[id];
    patchMessageNode(id);
  }

  // --- Vehicle selector ---
  function openSelector() { state.selOpen = true; state.selMake = null; renderChip(); }
  function toggleSelector() { state.selOpen = !state.selOpen; state.selMake = null; renderChip(); }
  function pickVehicle(v) {
    const pending = state.pendingQuestion;
    state.vehicle = v;
    state.selOpen = false;
    state.selMake = null;
    state.pendingQuestion = null;
    renderChip();
    renderExampleChips();
    if (pending) setTimeout(() => answer(pending, v), 250);
  }

  function renderChip() {
    el.chipLabel.textContent = vLabel() || 'Select your vehicle';
    el.chip.setAttribute('aria-expanded', String(state.selOpen));
    el.selectorPanel.hidden = !state.selOpen;
    if (!state.selOpen) return;

    el.selectorList.innerHTML = '';
    if (!state.selMake) {
      el.selectorTitle.textContent = 'Select make';
      el.selectorBack.hidden = true;
      for (const mk of Object.keys(DATA)) {
        el.selectorList.appendChild(selectorItem(mk, () => { state.selMake = mk; renderChip(); }));
      }
    } else {
      el.selectorTitle.textContent = state.selMake;
      el.selectorBack.hidden = false;
      for (const md of DATA[state.selMake]) {
        for (const y of YEARS) {
          const make = state.selMake;
          el.selectorList.appendChild(selectorItem(`${y} ${md}`, () => pickVehicle({ make, model: md, year: y })));
        }
      }
    }
  }

  function selectorItem(label, onClick) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'selector-item';
    btn.innerHTML = `<span>${escapeHtml(label)}</span><svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M9 6l6 6-6 6" stroke="#B4BCC4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
    // stopPropagation: this click rebuilds the panel's DOM synchronously (renderChip()),
    // so by the time the click bubbles to the document outside-click listener, e.target
    // has already been removed from the tree and would look like an "outside" click.
    btn.addEventListener('click', e => { e.stopPropagation(); onClick(); });
    return btn;
  }

  // --- Message rendering ---
  const AVATAR_HTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="13" r="8" stroke="#1F3A5F" stroke-width="1.7"/><path d="M12 13 L16.5 9" stroke="#2E5E4E" stroke-width="1.9" stroke-linecap="round"/><circle cx="12" cy="13" r="1.5" fill="#1F3A5F"/></svg>';
  const CITE_ICON = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none"><rect x="5" y="3" width="14" height="18" rx="2" stroke="#2E5E4E" stroke-width="1.7"/><path d="M8.5 8h7M8.5 12h7M8.5 16h4" stroke="#2E5E4E" stroke-width="1.5" stroke-linecap="round"/></svg>';
  const CARET_ICON = '<svg width="11" height="11" viewBox="0 0 24 24" fill="none"><path d="M6 9l6 6 6-6" stroke="#2E5E4E" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  const SHIELD_ICON = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><path d="M12 3l7 3v5c0 4.5-3 7.7-7 9-4-1.3-7-4.5-7-9V6l7-3z" fill="#2E5E4E"/><path d="M9 12l2 2 4-4" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  const WARNING_ICON = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><path d="M12 3.5L22 20H2L12 3.5z" fill="#C8891A"/><path d="M12 10v4" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/><circle cx="12" cy="17" r="1.1" fill="#fff"/></svg>';
  const WRENCH_ICON = '<svg width="17" height="17" viewBox="0 0 24 24" fill="none"><path d="M14.5 3.5a4 4 0 00-1 5.3l-8 8 2.4 2.4 8-8a4 4 0 005.3-1L17 6.6l-2.5 2.5-1.6-1.6L15.4 5z" stroke="#9A6712" stroke-width="1.4" stroke-linejoin="round"/></svg>';
  const VEHICLE_CHOOSE_ICON = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none"><rect x="3" y="11" width="18" height="6" rx="2" stroke="#1F3A5F" stroke-width="1.7"/><path d="M6 11l2-4h8l2 4" stroke="#1F3A5F" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  function messageRowHtml(m) {
    if (m.role === 'user') {
      return `<div class="message-row user"><div class="bubble">${escapeHtml(m.text)}</div></div>`;
    }

    let inner = '';
    if (m.kind === 'loading') {
      const steps = LOADING_STEPS.map((label, i) => {
        const doneState = i < m.step ? 'done' : i === m.step ? 'active' : '';
        const glyph = i < m.step ? '✓' : '→';
        return `<div class="loading-step ${doneState}"><span class="dot ${doneState}">${glyph}</span><span>${label}</span></div>`;
      }).join('');
      inner = `<div class="loading-card">${steps}</div>`;
    } else if (m.kind === 'clarify') {
      inner = `<div class="clarify-card"><span>${escapeHtml(m.text)}</span>
        <button class="cite-btn choose-vehicle" type="button" data-action="open-selector">${VEHICLE_CHOOSE_ICON}Choose vehicle</button></div>`;
    } else if (m.kind === 'answer') {
      const expanded = !!state.expanded[m.id];
      const sources = m.sources || [];
      const primary = sources[0];
      const chip = primary
        ? `<button class="cite-btn ${expanded ? 'expanded' : ''}" type="button" data-action="toggle-cite" data-id="${m.id}">
            ${CITE_ICON}<span>${escapeHtml(primary.label)}${sources.length > 1 ? ` +${sources.length - 1}` : ''}</span><span class="caret">${CARET_ICON}</span>
          </button>` : '';
      let excerptBlock = '';
      if (expanded && primary) {
        const extra = sources.slice(1).map(s =>
          `<div class="excerpt-more">${escapeHtml(s.label)}${s.url ? ` — <a href="${escapeHtml(s.url)}" target="_blank" rel="noopener">view</a>` : ''}</div>`).join('');
        excerptBlock = `<div class="excerpt">
            <div class="excerpt-label">Source excerpt · ${escapeHtml(primary.section || primary.variant || 'manual')}</div>
            ${m.excerpt ? `<div class="excerpt-body">${escapeHtml(m.excerpt)}</div>` : ''}
            ${primary.url ? `<a class="excerpt-link" href="${escapeHtml(primary.url)}" target="_blank" rel="noopener">View in manual ↗</a>` : ''}
            ${extra}
          </div>`;
      }
      inner = `<div class="card">
        ${m.safety ? `<div class="safety-bar">${SHIELD_ICON}<span>GROUNDED &amp; VERIFIED · SAFETY-CRITICAL</span></div>` : ''}
        <div class="card-body">
          <div class="answer-text">${escapeHtml(m.text)}</div>
          ${chip}
          ${excerptBlock}
        </div>
      </div>`;
    } else if (m.kind === 'refusal') {
      inner = `<div class="refusal-card">
        <div class="warn-bar">${WARNING_ICON}<span>NOT COVERED IN THE MANUAL</span></div>
        <div class="card-body">
          <div class="answer-text">${escapeHtml(m.text)}</div>
          <div class="next-step">${WRENCH_ICON}<span>Best next step: contact a certified technician or your dealer.</span></div>
        </div>
      </div>`;
    }

    return `<div class="message-row assistant"><div class="avatar">${AVATAR_HTML}</div><div class="reply">${inner}</div></div>`;
  }

  function renderExampleChips() {
    if (state.messages.length >= 6) { el.exampleChips.innerHTML = ''; return; }
    const hasVehicle = !!state.vehicle;
    const chips = hasVehicle
      ? ["What's the recommended tyre pressure?", 'When is my next oil change due?', 'How often should I change the brake fluid?', "What's the engine coolant capacity?"]
      : ["What's my tyre pressure?", 'What does the oil warning light mean?', 'How often should I change the brake fluid?', 'How do I replace my wiper blades?'];
    el.exampleChips.innerHTML = chips.map(c => `<button class="example-chip" type="button">${escapeHtml(c)}</button>`).join('');
    el.exampleChips.querySelectorAll('.example-chip').forEach((btn, i) => btn.addEventListener('click', () => send(chips[i])));
  }

  function updateSendState() {
    el.sendBtn.disabled = state.input.trim().length === 0;
  }

  // --- Event wiring ---
  el.chip.addEventListener('click', toggleSelector);
  el.selectorBack.addEventListener('click', e => { e.stopPropagation(); state.selMake = null; renderChip(); });
  document.addEventListener('click', e => {
    if (state.selOpen && !el.chip.contains(e.target) && !el.selectorPanel.contains(e.target)) {
      state.selOpen = false;
      renderChip();
    }
  });

  el.pickVehicleCard.addEventListener('click', e => { e.stopPropagation(); openSelector(); });
  el.justAskCard.addEventListener('click', () => el.input.focus());

  el.input.addEventListener('input', e => {
    state.input = e.target.value;
    updateSendState();
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
  });
  el.input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  });
  el.sendBtn.addEventListener('click', () => send());

  el.messageList.addEventListener('click', e => {
    const target = e.target.closest('[data-action]');
    if (!target) return;
    // stopPropagation: without it, this same click bubbles to the document
    // outside-click listener below, which sees a target outside the chip/panel
    // (this button lives in the message list) and immediately closes the
    // selector it just opened.
    e.stopPropagation();
    if (target.dataset.action === 'toggle-cite') toggleCite(target.dataset.id);
    if (target.dataset.action === 'open-selector') openSelector();
  });

  // Reflowing text at a new viewport width changes the messages container's
  // scrollHeight (e.g. a phone rotation mid-conversation), so re-pin to bottom.
  window.addEventListener('resize', scrollToBottom);

  renderExampleChips();
  renderChip();
  updateSendState();
})();
