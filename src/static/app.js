  const $ = (id) => document.getElementById(id);

  // ================= Theme =================
  const THEME_KEY = "ep-theme";

  function currentTheme() {
    try { return localStorage.getItem(THEME_KEY) || "system"; } catch (e) { return "system"; }
  }

  function setTheme(mode) {
    if (mode !== "light" && mode !== "dark" && mode !== "system") mode = "system";
    try {
      if (mode === "system") localStorage.removeItem(THEME_KEY);
      else localStorage.setItem(THEME_KEY, mode);
    } catch (e) { /* private mode etc. */ }
    if (mode === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = mode;
    syncThemeButtons(mode);
  }

  function syncThemeButtons(mode) {
    mode = mode || currentTheme();
    document.querySelectorAll(".theme-switch button").forEach((b) => {
      b.classList.toggle("active", b.dataset.themeVal === mode);
    });
  }

  // Keep the active-state label honest if the OS flips while set to System.
  try {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
      if (currentTheme() === "system") syncThemeButtons("system");
    });
  } catch (e) { /* older webview */ }
  syncThemeButtons();

  // ================= Settings drawer =================
  const DRAWER_KEY = "ep-drawer-manual"; // reused pattern key prefix below
  let _drawerLastFocus = null;

  function openDrawer(sectionId) {
    const prev = document.activeElement;
    _drawerLastFocus = (prev && prev !== document.body && prev !== $("drawer")) ? prev : $("settings-btn");
    $("scrim").classList.add("open");
    $("drawer").classList.add("open");
    document.addEventListener("keydown", _drawerKeydown, true);
    $("drawer").focus();
    if (sectionId) {
      const target = $(sectionId === "event" ? "drawer-event" : sectionId);
      if (target) setTimeout(() => target.scrollIntoView({ block: "start" }), 60);
    }
  }

  function closeDrawer() {
    $("scrim").classList.remove("open");
    $("drawer").classList.remove("open");
    document.removeEventListener("keydown", _drawerKeydown, true);
    const back = _drawerLastFocus && document.contains(_drawerLastFocus) ? _drawerLastFocus : $("settings-btn");
    _drawerLastFocus = null;
    if (back) back.focus();
  }

  function _drawerKeydown(e) {
    if (e.key === "Escape") { e.preventDefault(); closeDrawer(); return; }
    if (e.key !== "Tab") return;
    const drawer = $("drawer");
    const focusables = drawer.querySelectorAll(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    if (!focusables.length) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    const active = document.activeElement;
    if (e.shiftKey && (active === first || active === drawer)) {
      e.preventDefault(); last.focus();
    } else if (!e.shiftKey && (active === last || !drawer.contains(active))) {
      e.preventDefault(); first.focus();
    }
  }

  // ================= Manual-entry <details> persistence (open by default) =================
  const MANUAL_KEY = "ep-manual-open";
  (function initManualDetails() {
    const d = $("manual-entry");
    try { d.open = localStorage.getItem(MANUAL_KEY) !== "0"; } catch (e) { d.open = true; }
    d.addEventListener("toggle", () => {
      try { localStorage.setItem(MANUAL_KEY, d.open ? "1" : "0"); } catch (e) {}
    });
  })();

  // ================= Scan section — opens automatically when an event is connected =================
  function _syncScanSection(connected) {
    const sz = $("scan-section");
    if (sz) sz.open = !!connected;
  }

  const log = (msg, kind = "") => {
    const el = $("log");
    const time = new Date().toLocaleTimeString();
    const line = document.createElement("div");
    line.className = "entry";
    const ts = document.createElement("span");
    ts.className = "ts";
    ts.textContent = "[" + time + "]";
    const body = document.createElement("span");
    if (kind) body.className = kind;
    body.textContent = msg;
    line.append(ts, body);
    el.prepend(line);
  };

  function toast(msg, kind = "ok") {
    const wrap = $("toasts");
    const t = document.createElement("div");
    t.className = "toast " + kind;
    const icon = document.createElement("span");
    icon.className = "t-icon";
    icon.setAttribute("aria-hidden", "true");
    const body = document.createElement("span");
    body.textContent = (kind === "ok" ? "✓ " : kind === "warn" ? "! " : "× ") + msg;
    t.append(icon, body);
    wrap.appendChild(t);
    setTimeout(() => {
      t.classList.add("leaving");
      setTimeout(() => t.remove(), 160);
    }, 4200);
  }

  async function refresh() {
    try {
      const r = await fetch("/health");
      const j = await r.json();
      $("info-printer").textContent = j.printer || "—";
      $("info-outdir").textContent = j.output_dir || "—";
      $("port").textContent = location.host;
      $("health-dot").className = "dot ok";
      $("health-text").textContent = "Ready";
    } catch (e) {
      $("health-dot").className = "dot err";
      $("health-text").textContent = "Not responding";
      log("health check failed: " + e, "err");
    }
    try {
      const r = await fetch("/printers");
      const j = await r.json();
      $("info-default").textContent = j.default_printer || "—";
    } catch (e) { /* ignore */ }
    try {
      const r = await fetch("/server/status");
      const j = await r.json();
      $("info-pid").textContent = j.pid;
      $("info-uptime").textContent = formatUptime(j.uptime_seconds);
    } catch (e) { /* ignore */ }
  }

  function formatUptime(sec) {
    if (sec == null) return "—";
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    if (h) return h + "h " + m + "m";
    if (m) return m + "m " + s + "s";
    return s + "s";
  }

  let lastPreviewBlobUrl = null;

  function buildPayload(forPreview) {
    const ticketVisible = !$("f-ticket").closest("label").hidden;
    const ticket = ticketVisible ? $("f-ticket").value.trim() : "";
    const name = $("f-name").value.trim();
    return {
      // Ticket ID only feeds the QR; when hidden, an internal id is generated.
      ticket_id: ticket || (forPreview ? "PREVIEW" : "MANUAL-" + Date.now()),
      name: name || (forPreview ? "Sample Name" : ""),
      company: $("f-company").value.trim() || null,
      title: $("f-title").value.trim() || null,
      country: $("f-country").value.trim() || null,
      table_no: $("f-table").value.trim() || null,
      ticket_type: $("f-type").value,
      custom: customValues,
    };
  }

  // ================= Layout editor =================
  const EL_LABELS = {
    name: "Name",
    role: "Role / ticket type",
    company: "Company",
    title: "Position",
    country: "Country",
    table_no: "Table Number",
    qr: "QR code",
  };
  const EL_BACKEND_KEYS = {
    name: "attendee_name",
    role: "ticket_type",
    company: "company",
    title: "title",
    country: "country",
    table_no: "table_number",
  };
  let layoutElements = [];
  let customFieldDefs = {}; // id -> {label, backend_key}
  let customValues = {};    // id -> value typed in manual entry
  let elementScales = {};   // id -> size multiplier (1 = auto default)
  let sizingMode = false;   // Adjust-size mode: sliders shown, drag disabled

  function elLabel(el) {
    if (customFieldDefs[el]) return customFieldDefs[el].label || "New field";
    return EL_LABELS[el] || el;
  }


  const PAPER_PRESETS = {
    sticker: { width_mm: 100, height_mm: 80 },
    card: { width_mm: 104, height_mm: 155 },
  };

  function matchPreset(w, h) {
    for (const [key, p] of Object.entries(PAPER_PRESETS)) {
      if (Math.abs(p.width_mm - w) < 0.2 && Math.abs(p.height_mm - h) < 0.2) return key;
    }
    return "custom";
  }

  function _syncPreviewSize() {
    const w = parseFloat($("lay-w").value);
    const h = parseFloat($("lay-h").value);
    $("preview-size").textContent = (isFinite(w) && isFinite(h)) ? (w + " × " + h + " mm") : "";
  }

  function applyPaperPreset() {
    const key = $("lay-preset").value;
    const custom = key === "custom";
    $("paper-custom").style.display = custom ? "" : "none";
    if (!custom) {
      $("lay-w").value = PAPER_PRESETS[key].width_mm;
      $("lay-h").value = PAPER_PRESETS[key].height_mm;
    }
    _syncPreviewSize();
    schedulePreview();
  }

  function renderLayoutEditor(layout) {
    if (layout && layout.paper) {
      $("lay-w").value = layout.paper.width_mm;
      $("lay-h").value = layout.paper.height_mm;
      $("lay-preset").value = matchPreset(layout.paper.width_mm, layout.paper.height_mm);
      $("paper-custom").style.display = $("lay-preset").value === "custom" ? "" : "none";
      customFieldDefs = {};
      for (const [id, def] of Object.entries(layout.custom_fields || {})) {
        if (typeof def === "string") customFieldDefs[id] = { label: def, backend_key: "" };
        else customFieldDefs[id] = { label: def.label || id, backend_key: def.backend_key || "" };
      }
      elementScales = {};
      for (const [id, s] of Object.entries(layout.element_scales || {})) {
        const n = parseFloat(s);
        if (isFinite(n) && n > 0) elementScales[id] = Math.min(2, Math.max(0.5, n));
      }
      layoutElements = (layout.elements || []).filter((e) => elLabel(e));
    }
    _syncPreviewSize();
    const list = $("layout-list");
    list.innerHTML = "";
    const disabled = Object.keys(EL_LABELS)
      .concat(Object.keys(customFieldDefs))
      .filter((e, i, arr) => arr.indexOf(e) === i && !layoutElements.includes(e));
    layoutElements.forEach((el) => {
      const row = layoutRow(el, true);
      list.appendChild(row);
      attachCustomInputs(row, el);
    });
    disabled.forEach((el) => {
      const row = layoutRow(el, false);
      list.appendChild(row);
      attachCustomInputs(row, el);
    });
    syncManualFields();
    renderCustomFieldManager();
    syncSizingButton();
  }

  function syncSizingButton() {
    const btn = $("sizing-toggle");
    if (btn) {
      btn.classList.toggle("active", sizingMode);
      btn.textContent = sizingMode ? "Done adjusting" : "Adjust size";
      btn.setAttribute("aria-pressed", sizingMode ? "true" : "false");
    }
    const resetBtn = $("sizing-reset");
    if (resetBtn) resetBtn.style.display = sizingMode ? "" : "none";
    const layoutResetBtn = $("layout-reset");
    if (layoutResetBtn) layoutResetBtn.style.display = sizingMode ? "none" : "";
    const list = $("layout-list");
    if (list) list.classList.toggle("sizing-mode", sizingMode);
  }

  // Reset every element's size override back to automatic (100%).
  function resetSizes() {
    if (!Object.keys(elementScales).length) { toast("Sizes are already at default", "warn"); return; }
    if (!confirm("Reset all text sizes back to automatic?")) return;
    elementScales = {};
    renderLayoutEditor();
    schedulePreview();
    toast("Sizes reset to automatic");
  }

  // Reset the whole layout: paper, element order/selection, sizes, and
  // custom fields all go back to the built-in default.
  const DEFAULT_LAYOUT_STATE = {
    paper: { width_mm: 100, height_mm: 80 },
    elements: ["name", "role", "company", "qr"],
    custom_fields: {},
    element_scales: {},
  };

  function resetLayout() {
    if (!confirm("Reset the whole layout to default? Paper size, field order, sizes and custom fields will be restored.")) return;
    layoutElements = DEFAULT_LAYOUT_STATE.elements.slice();
    customFieldDefs = {};
    elementScales = {};
    customValues = {};
    sizingMode = false;
    renderLayoutEditor(DEFAULT_LAYOUT_STATE);
    schedulePreview();
    toast("Layout reset to default — press Save layout to keep it");
  }

  // ================= Manual entry follows badge layout =================
  const FIELD_FOR_EL = {
    name: "f-name",
    role: "f-type",
    company: "f-company",
    title: "f-title",
    country: "f-country",
    table_no: "f-table",
  };

  function syncManualFields() {
    let hiddenCount = 0;
    for (const [el, id] of Object.entries(FIELD_FOR_EL)) {
      const input = $(id);
      const label = input.closest("label");
      const show = layoutElements.includes(el);
      label.hidden = !show;
      input.disabled = !show;
      if (!show) hiddenCount++;
    }
    // Ticket ID only feeds the QR code — hide it when QR isn't on the badge.
    // Must also disable it: a hidden-but-required enabled input would block
    // form submission with no visible error.
    const ticketInput = $("f-ticket");
    const ticketVisible = layoutElements.includes("qr");
    const ticketLabel = ticketInput.closest("label");
    ticketLabel.hidden = !ticketVisible;
    ticketInput.disabled = !ticketVisible;
    if (!ticketVisible) hiddenCount++;
    // Position / Table No. row: collapse to one column when only one remains
    const titleShown = !$("f-title").closest("label").hidden;
    const tableShown = !$("f-table").closest("label").hidden;
    $("f-title").closest(".field-row").classList.toggle("single", titleShown !== tableShown);
    const note = $("manual-layout-note");
    if (note) {
      note.hidden = hiddenCount === 0;
      note.textContent = "Only fields used by your badge layout are shown — change it in Settings → Badge layout.";
    }
    renderCustomEntryFields();
  }

  // ================= Custom field manual-entry inputs =================
  function renderCustomEntryFields() {
    const wrap = $("custom-entry-fields");
    if (!wrap) return;
    wrap.innerHTML = "";
    const shown = layoutElements.filter((el) => customFieldDefs[el] && customFieldDefs[el].label);
    for (const el of shown) {
      const def = customFieldDefs[el];
      const label = document.createElement("label");
      label.textContent = def.label;
      const input = document.createElement("input");
      input.type = "text";
      input.dataset.customEl = el;
      input.value = customValues[el] || "";
      input.placeholder = def.label;
      input.addEventListener("input", () => {
        customValues[el] = input.value.trim();
        schedulePreview();
      });
      label.appendChild(input);
      wrap.appendChild(label);
    }
    wrap.style.display = shown.length ? "" : "none";
  }

  let _layoutDragEl = null;
  const MAX_CUSTOM_FIELDS = 6;

  function attachCustomInputs(row, el) {
    if (!customFieldDefs[el]) return;
    const def = customFieldDefs[el];

    const del = document.createElement("button");
    del.type = "button";
    del.className = "custom-del";
    del.textContent = "×";
    del.title = "Remove custom field";
    del.setAttribute("aria-label", "Remove custom field " + (def.label || ""));
    del.onclick = () => {
      delete customFieldDefs[el];
      layoutElements = layoutElements.filter((e) => e !== el);
      delete customValues[el];
      renderLayoutEditor();
      schedulePreview();
    };
    row.appendChild(del);

    function buildView() {
      const label = document.createElement("span");
      label.className = "el-label custom-editable";
      label.textContent = def.label;
      label.title = "Click to edit";
      const hint = document.createElement("span");
      hint.className = "key-hint";
      hint.textContent = def.backend_key ? "(" + def.backend_key + ")" : "(no key)";
      label.appendChild(hint);
      label.addEventListener("click", () => {
        const edit = buildEdit();
        row.replaceChild(edit, label);
        edit.querySelector("input").focus();
      });
      return label;
    }

    function collapseToView() {
      const val = labelInput.value.trim();
      if (!val) return false;
      def.label = val;
      def.backend_key = keyInput.value.trim();
      const edit = row.querySelector(".custom-inputs");
      const view = buildView();
      row.replaceChild(view, edit);
      renderCustomEntryFields();
      schedulePreview();
      return true;
    }

    const labelInput = document.createElement("input");
    const keyInput = document.createElement("input");

    function buildEdit() {
      const inputs = document.createElement("div");
      inputs.className = "custom-inputs";

      labelInput.type = "text";
      labelInput.className = "row-input";
      labelInput.value = def.label;
      labelInput.placeholder = "Custom Field";
      labelInput.setAttribute("aria-label", "Custom field label");
      labelInput.addEventListener("input", () => {
        def.label = labelInput.value.trim();
      });

      keyInput.type = "text";
      keyInput.className = "row-input";
      keyInput.value = def.backend_key;
      keyInput.placeholder = "custom_field";
      keyInput.setAttribute("aria-label", "EventzFlow field key for scan mapping");
      keyInput.addEventListener("input", () => {
        def.backend_key = keyInput.value.trim();
      });

      [labelInput, keyInput].forEach((inp) => {
        inp.addEventListener("keydown", (e) => {
          if (e.key === "Enter") { e.preventDefault(); inp.blur(); }
        });
      });
      inputs.addEventListener("focusout", () => {
        setTimeout(() => {
          if (!inputs.contains(document.activeElement)) collapseToView();
        }, 0);
      });

      inputs.appendChild(labelInput);
      inputs.appendChild(keyInput);
      return inputs;
    }

    const labelSpan = row.querySelector(".el-label");
    if (def.label) {
      const view = buildView();
      row.replaceChild(view, labelSpan);
    } else {
      const edit = buildEdit();
      row.replaceChild(edit, labelSpan);
      labelInput.focus();
    }

    // Typing in the inputs shouldn't start a row drag
    row.addEventListener("focusin", () => { row.draggable = false; });
    row.addEventListener("focusout", () => {
      if (layoutElements.includes(el)) row.draggable = true;
    });
  }

  function renderCustomFieldManager() {
    const wrap = $("custom-fields-manager");
    if (!wrap) return;
    wrap.innerHTML = "";
    const count = Object.keys(customFieldDefs).length;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "ghost add-custom";
    btn.textContent = "+ Add custom field";
    btn.disabled = count >= MAX_CUSTOM_FIELDS;
    btn.onclick = () => {
      let id;
      do { id = "custom_" + Math.random().toString(16).slice(2, 8); } while (customFieldDefs[id]);
      customFieldDefs[id] = { label: "", backend_key: "" };
      if (!layoutElements.includes(id)) layoutElements.push(id);
      renderLayoutEditor();
      schedulePreview();
      const row = document.querySelector('.layout-el[data-el="' + id + '"]');
      const input = row && row.querySelector(".custom-inputs input");
      if (input) { input.focus(); }
    };
    wrap.appendChild(btn);
    if (count) {
      const note = document.createElement("span");
      note.className = "custom-count";
      note.textContent = count + "/" + MAX_CUSTOM_FIELDS + " custom fields";
      wrap.appendChild(note);
    }
  }

  // Adjust-size mode is off by default. Turning it on reveals the sliders,
  // hides the drag handles + backend-key hints (more room), and disables
  // row drag-and-drop so sliding never moves a row. Re-render on toggle.
  function toggleSizingMode() {
    sizingMode = !sizingMode;
    renderLayoutEditor();
  }

  // Per-element size slider: 50%–200% of the auto-fit size. 100% means
  // "no override" and isn't persisted.
  function scaleControl(el) {
    const wrap = document.createElement("span");
    wrap.className = "el-scale";
    wrap.title = "Size relative to automatic";

    const slider = document.createElement("input");
    slider.type = "range";
    slider.min = "50";
    slider.max = "200";
    slider.step = "5";
    slider.value = String(Math.round((elementScales[el] || 1) * 100));
    slider.setAttribute("aria-label", "Size for " + elLabel(el));

    const val = document.createElement("span");
    val.className = "el-scale-val";
    val.textContent = slider.value + "%";

    slider.addEventListener("input", () => {
      val.textContent = slider.value + "%";
      const scale = parseInt(slider.value, 10) / 100;
      if (scale === 1) delete elementScales[el];
      else elementScales[el] = scale;
      schedulePreview();
    });
    slider.addEventListener("dblclick", () => {
      slider.value = "100";
      slider.dispatchEvent(new Event("input"));
    });

    wrap.appendChild(slider);
    wrap.appendChild(val);
    return wrap;
  }

  function layoutRow(el, enabled) {
    const row = document.createElement("div");
    row.className = "layout-el" + (enabled ? "" : " off");
    const handle = document.createElement("span");
    handle.className = "drag-handle";
    handle.setAttribute("aria-hidden", "true");
    handle.innerHTML = '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="9" cy="5" r="1.7"/><circle cx="15" cy="5" r="1.7"/><circle cx="9" cy="12" r="1.7"/><circle cx="15" cy="12" r="1.7"/><circle cx="9" cy="19" r="1.7"/><circle cx="15" cy="19" r="1.7"/></svg>';
    if (!sizingMode) row.appendChild(handle);
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = enabled;
    cb.onchange = () => {
      if (cb.checked) layoutElements.push(el);
      else layoutElements = layoutElements.filter((e) => e !== el);
      renderLayoutEditor();
      schedulePreview();
    };
    const label = document.createElement("span");
    label.className = "el-label";
    label.textContent = elLabel(el);
    if (EL_BACKEND_KEYS[el] && !sizingMode) {
      const hint = document.createElement("span");
      hint.className = "key-hint";
      hint.textContent = "(" + EL_BACKEND_KEYS[el] + ")";
      label.appendChild(hint);
    }
    row.appendChild(cb);
    row.appendChild(label);
    if (enabled && sizingMode) {
      row.appendChild(scaleControl(el));
    }
    if (enabled) {
      row.dataset.el = el;
      if (sizingMode) {
        row.classList.add("sizing");
      } else {
        row.draggable = true;
      }
      row.addEventListener("dragstart", (e) => {
        if (sizingMode || e.target.closest("input, button, select")) { e.preventDefault(); return; }
        _layoutDragEl = row;
        row.classList.add("dragging");
        e.dataTransfer.effectAllowed = "move";
        try { e.dataTransfer.setData("text/plain", el); } catch (err) {}
      });
      row.addEventListener("dragend", () => {
        row.classList.remove("dragging");
        _layoutDragEl = null;
        _commitLayoutOrder();
      });
    }
    return row;
  }

  function _commitLayoutOrder() {
    document.querySelectorAll(".layout-el").forEach((r) => r.classList.remove("drag-over-top", "drag-over-bottom"));
    const rows = $("layout-list").querySelectorAll(".layout-el:not(.off)");
    const order = Array.from(rows).map((r) => r.dataset.el);
    if (order.length && order.join() !== layoutElements.join()) {
      layoutElements = order;
      schedulePreview();
    }
    renderLayoutEditor();
  }

  (function initLayoutDnd() {
    const list = $("layout-list");
    list.addEventListener("dragover", (e) => {
      if (!_layoutDragEl) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      const target = e.target.closest(".layout-el");
      if (!target || target === _layoutDragEl || target.classList.contains("off")) return;
      const rect = target.getBoundingClientRect();
      const before = e.clientY < rect.top + rect.height / 2;
      document.querySelectorAll(".layout-el").forEach((r) => r.classList.remove("drag-over-top", "drag-over-bottom"));
      target.classList.add(before ? "drag-over-top" : "drag-over-bottom");
      target.parentNode.insertBefore(_layoutDragEl, before ? target : target.nextSibling);
    });
    list.addEventListener("drop", (e) => e.preventDefault());
  })();

  async function saveLayout(ev) {
    ev.preventDefault();
    if (!layoutElements.length) { log("layout needs at least one field", "err"); toast("Pick at least one field to print", "warn"); return; }
    const unnamed = layoutElements.filter((el) => customFieldDefs[el] && !customFieldDefs[el].label);
    if (unnamed.length) { toast("Give your new custom field a name first", "warn"); return; }
    const body = {
      layout: {
        paper: {
          width_mm: parseFloat($("lay-w").value),
          height_mm: parseFloat($("lay-h").value),
        },
        elements: layoutElements,
        custom_fields: customFieldDefs,
        element_scales: elementScales,
      },
    };
    try {
      const r = await fetch("/config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const j = await r.json();
      if (!r.ok) { log("layout save failed: " + (j.detail || r.status), "err"); toast("Couldn't save the layout", "err"); return; }
      log("layout saved", "ok");
      toast("Layout saved");
      renderLayoutEditor(j.layout);
      updatePreview();
    } catch (e) {
      log("layout save failed: " + e, "err");
      toast("Couldn't save the layout", "err");
    }
  }

  // Debounced live preview — updates as the user types
  let _previewTimer = null;
  function schedulePreview() {
    if (_previewTimer) clearTimeout(_previewTimer);
    _previewTimer = setTimeout(updatePreview, 450);
  }

  function setPreviewChip(text, kind) {
    const chip = $("preview-status");
    chip.textContent = text;
    chip.className = "preview-status-chip" + (kind ? " " + kind : "");
  }

  async function updatePreview() {
    const payload = buildPayload(true);
    setPreviewChip("rendering…", "busy");
    try {
      const r = await fetch("/png-preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!r.ok) {
        setPreviewChip("error", "err");
        log("preview failed: " + r.status, "err");
        return;
      }
      const blob = await r.blob();
      if (lastPreviewBlobUrl) URL.revokeObjectURL(lastPreviewBlobUrl);
      lastPreviewBlobUrl = URL.createObjectURL(blob);
      const img = $("preview-img");
      img.src = lastPreviewBlobUrl;
      img.style.display = "";
      $("preview-empty").style.display = "none";
      setPreviewChip("up to date", "ok");
    } catch (e) {
      setPreviewChip("error", "err");
      log("preview failed: " + e, "err");
    }
  }

  async function testPrint() {
    log("sending test print…");
    try {
      const r = await fetch("/print-test", { method: "POST" });
      const j = await r.json();
      if (r.ok) { log("test printed: " + (j.print_job?.job_id || "ok"), "ok"); toast("Test page sent to the printer"); }
      else { log("test failed: " + (j.detail || r.status), "err"); toast("Test print didn't work", "err"); }
    } catch (e) { log("test failed: " + e, "err"); toast("Test print didn't work", "err"); }
  }

  async function printTicket(ev) {
    ev.preventDefault();
    const payload = buildPayload(false);
    log("printing " + payload.ticket_id + " (" + payload.name + ")…");
    try {
      const r = await fetch("/print-ticket", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const j = await r.json();
      if (r.ok) { log("printed " + payload.ticket_id, "ok"); toast("Badge printing — collect it from the printer"); }
      else { log("print failed: " + (j.detail || r.status), "err"); toast("Printing failed — check the printer", "err"); }
    } catch (e) { log("print failed: " + e, "err"); toast("Printing failed — check the printer", "err"); }
  }

  async function restartServer() {
    if (!confirm("Restart the server? Active jobs will be interrupted.")) return;
    log("restart requested…");
    try {
      const r = await fetch("/server/restart", { method: "POST" });
      if (r.ok) {
        log("server restarting…", "ok");
        let tries = 0;
        const iv = setInterval(async () => {
          tries++;
          try {
            const h = await fetch("/health");
            if (h.ok) { clearInterval(iv); log("server back online", "ok"); refresh(); }
          } catch (e) { /* still down */ }
          if (tries > 50) { clearInterval(iv); log("restart timeout — refresh manually", "err"); }
        }, 500);
      } else {
        log("restart failed: " + r.status, "err");
      }
    } catch (e) { log("restart failed: " + e, "err"); }
  }

  async function quitServer() {
    if (!confirm("Quit the server? The window will close.")) return;
    log("shutting down…");
    try { await fetch("/server/quit", { method: "POST" }); } catch (e) { /* expected */ }
    setTimeout(() => { try { window.close(); } catch (e) {} }, 600);
  }

  refresh().then(async () => {
    log("dashboard ready", "ok");
    await loadConfig();
    const sz = $("scan-section");
    const s = $("scan-input");
    if (sz && sz.open && s && !s.disabled) focusScan(); else ($("f-ticket").closest("label").hidden ? $("f-name") : $("f-ticket")).focus();
    updatePreview();
  });
  setInterval(refresh, 15000);

  ["f-ticket", "f-name", "f-company", "f-title", "f-country", "f-table", "f-type"].forEach((id) => {
    $(id).addEventListener("input", schedulePreview);
  });

  // ================= Badge types (dropdown options) =================
  let badgeTypes = [];
  const MAX_BADGE_TYPES = 30;

  function renderBadgeTypeOptions(selected) {
    const sel = $("f-type");
    sel.innerHTML = "";
    for (const t of badgeTypes) {
      const opt = document.createElement("option");
      opt.value = t;
      opt.textContent = t;
      sel.appendChild(opt);
    }
    if (selected && badgeTypes.some((t) => t.toLowerCase() === selected.toLowerCase())) {
      sel.value = selected;
    }
  }

  function renderBadgeTypesManager() {
    const wrap = $("badge-types-manager");
    if (!wrap) return;
    wrap.innerHTML = "";
    badgeTypes.forEach((t, idx) => {
      const row = document.createElement("div");
      row.className = "badge-type-row";
      const input = document.createElement("input");
      input.type = "text";
      input.className = "row-input";
      input.value = t;
      input.setAttribute("aria-label", "Badge type " + (idx + 1));
      input.addEventListener("input", () => {
        badgeTypes[idx] = input.value.trim();
      });
      const del = document.createElement("button");
      del.type = "button";
      del.className = "custom-del";
      del.textContent = "×";
      del.title = "Remove badge type";
      del.setAttribute("aria-label", "Remove badge type " + t);
      del.onclick = () => {
        badgeTypes.splice(idx, 1);
        renderBadgeTypesManager();
      };
      row.append(input, del);
      wrap.appendChild(row);
    });
    const add = document.createElement("button");
    add.type = "button";
    add.className = "ghost add-custom";
    add.textContent = "+ Add badge type";
    add.disabled = badgeTypes.length >= MAX_BADGE_TYPES;
    add.onclick = () => {
      badgeTypes.push("");
      renderBadgeTypesManager();
      const inputs = wrap.querySelectorAll("input");
      if (inputs.length) inputs[inputs.length - 1].focus();
    };
    wrap.appendChild(add);
  }

  async function saveBadgeTypes() {
    const cleaned = badgeTypes.map((t) => (t || "").trim()).filter(Boolean);
    if (!cleaned.length) { toast("Keep at least one badge type", "warn"); return; }
    try {
      const r = await fetch("/config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ badge_types: cleaned }),
      });
      const j = await r.json();
      if (!r.ok) { log("badge types save failed: " + (j.detail || r.status), "err"); toast("Couldn't save badge types", "err"); return; }
      const current = $("f-type").value;
      badgeTypes = j.badge_types || cleaned;
      renderBadgeTypeOptions(current);
      renderBadgeTypesManager();
      log("badge types saved", "ok");
      toast("Badge types saved");
    } catch (e) {
      log("badge types save failed: " + e, "err");
      toast("Couldn't save badge types", "err");
    }
  }

  // ================= Backend config =================
  async function loadConfig() {
    try {
      const r = await fetch("/config");
      const j = await r.json();
      $("cfg-url").value = j.backend_url || "";
      $("cfg-slug").value = j.event_slug || "";
      $("cfg-key").value = "";
      const stateEl = $("cfg-key-state");
      stateEl.textContent = j.api_key_set ? "set (" + j.api_key_masked + ")" : "not set";
      updateScanState(j);
      badgeTypes = j.badge_types || [];
      renderBadgeTypeOptions();
      renderBadgeTypesManager();
      renderLayoutEditor(j.layout);
    } catch (e) {
      log("config load failed: " + e, "err");
    }
  }

  function updateScanState(cfg) {
    const ready = cfg.backend_url && cfg.event_slug && cfg.api_key_set;
    const btn = $("scan-btn");
    const input = $("scan-input");
    $("banner").classList.toggle("show", !ready);
    _syncScanSection(ready);
    if (!ready) {
      btn.disabled = true;
      input.disabled = true;
      input.placeholder = "Connect your event first";
    } else if (!_scanInFlight) {
      btn.disabled = false;
      input.disabled = false;
      input.placeholder = "Ready to scan…";
    }
  }

  async function saveConfig(ev) {
    ev.preventDefault();
    const body = {
      backend_url: $("cfg-url").value.trim(),
      event_slug: $("cfg-slug").value.trim(),
    };
    const key = $("cfg-key").value.trim();
    if (key) body.api_key = key;
    try {
      const r = await fetch("/config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const j = await r.json();
      if (!r.ok) { log("config save failed: " + (j.detail || r.status), "err"); toast("Couldn't save the settings", "err"); return; }
      log("backend config saved", "ok");
      toast("Event connected — scanning is ready");
      $("cfg-key").value = "";
      const stateEl = $("cfg-key-state");
      stateEl.textContent = j.api_key_set ? "set (" + j.api_key_masked + ")" : "not set";
      updateScanState(j);
    } catch (e) {
      log("config save failed: " + e, "err");
      toast("Couldn't save the settings", "err");
    }
  }

  async function resetConfig() {
    if (!confirm("Disconnect this machine from your event? Scanning stops until you reconnect.")) return;
    try {
      const r = await fetch("/config", { method: "DELETE" });
      const j = await r.json();
      if (!r.ok) { log("config reset failed: " + (j.detail || r.status), "err"); toast("Couldn't reset the settings", "err"); return; }
      $("cfg-url").value = "";
      $("cfg-slug").value = "";
      $("cfg-key").value = "";
      $("cfg-key-state").textContent = "not set";
      updateScanState(j);
      clearHistory();
      log("backend credentials cleared", "ok");
      toast("Event disconnected", "warn");
    } catch (e) {
      log("config reset failed: " + e, "err");
      toast("Couldn't reset the settings", "err");
    }
  }

  // ================= Scan =================
  let _scanInFlight = false;
  let _scanQueue = [];
  const _recentScans = new Map();
  const DEDUP_MS = 3000;
  const FEED_MAX = 40;

  function focusScan() {
    const el = $("scan-input");
    if (el && !el.disabled) el.focus();
  }

  function clearHistory() {
    const el = $("scan-history");
    while (el.firstChild) el.removeChild(el.firstChild);
    el.appendChild(_feedEmpty());
    _recentScans.clear();
    _scanQueue = [];
    $("last-scan").classList.remove("show");
  }

  function _feedEmpty() {
    const d = document.createElement("div");
    d.className = "feed-empty";
    d.id = "feed-empty";
    d.textContent = "No scans yet — the first ticket will appear here";
    return d;
  }

  function _trimFeed() {
    const el = $("scan-history");
    const rows = el.querySelectorAll(".feed-row");
    for (let i = FEED_MAX; i < rows.length; i++) rows[i].remove();
  }

  function prependHistory(row) {
    const el = $("scan-history");
    const empty = $("feed-empty");
    if (empty) empty.remove();
    el.insertBefore(row, el.firstChild);
    _trimFeed();
  }

  // ---- Feed row renderer (replaces result-box cards) ----
  function _feedRow(kind) {
    const row = document.createElement("div");
    row.className = "feed-row " + kind;
    return row;
  }

  function _rowName(row, name) {
    const el = document.createElement("div");
    el.className = "r-name";
    el.textContent = name || "—";
    if (name) el.title = name;
    row.appendChild(el);
  }

  function _rowTs(row, date) {
    const el = document.createElement("div");
    el.className = "r-ts";
    el.textContent = (date || new Date()).toLocaleTimeString();
    row.appendChild(el);
  }

  function _rowMeta(row, stateWord, parts) {
    const el = document.createElement("div");
    el.className = "r-meta";
    const st = document.createElement("span");
    st.className = "r-state";
    st.textContent = stateWord;
    el.appendChild(st);
    const rest = parts.filter(Boolean).join(" · ");
    if (rest) {
      const m = document.createElement("span");
      m.textContent = rest;
      m.title = rest;
      el.appendChild(m);
    }
    row.appendChild(el);
    return el;
  }

  function renderScanSuccess(j) {
    const t = j.ticket || {};
    const row = _feedRow("ok");
    _rowName(row, t.name || t.ticket_id || "Printed");
    _rowTs(row);
    _rowMeta(row, "✓ Printed & checked in", [t.ticket_id, t.ticket_type, t.company]);
    prependHistory(row);
    _updateLastScan("ok", "Printed & checked in", t.name, [t.ticket_id, t.ticket_type], null);
  }

  function renderAlreadyScanned(j) {
    const t = j.ticket || {};
    const row = _feedRow("warn");
    _rowName(row, t.name || t.ticket_id || "Already checked in");
    _rowTs(row);
    const meta = _rowMeta(row, "↻ Already checked in", [t.ticket_id, t.ticket_type, t.company]);
    const reprintBtn = document.createElement("button");
    reprintBtn.type = "button";
    reprintBtn.textContent = "Reprint";
    reprintBtn.className = "r-reprint";
    const pid = t.ticket_id;
    reprintBtn.onclick = () => reprintTicket(pid, reprintBtn);
    meta.appendChild(reprintBtn);
    prependHistory(row);
    _updateLastScan("warn", "Already checked in", t.name, [t.ticket_id, t.ticket_type], null);
  }

  function renderScanError(publicId, msg) {
    const row = _feedRow("err");
    _rowName(row, publicId);
    _rowTs(row);
    _rowMeta(row, "× Couldn't scan", [msg]);
    prependHistory(row);
    _updateLastScan("err", "Couldn't scan", publicId, null, msg);
    _showScanNote(msg);
  }

  function renderScanning(publicId) {
    const row = _feedRow("scanning");
    _rowName(row, publicId);
    _rowTs(row);
    _rowMeta(row, "Scanning…", []);
    const bar = document.createElement("div");
    bar.className = "r-bar";
    row.appendChild(bar);
    prependHistory(row);
    return row;
  }

  // ---- LAST SCAN block ----
  function _updateLastScan(kind, stateWord, name, metaParts, reason) {
    const block = $("last-scan");
    block.classList.add("show");
    const state = $("last-state");
    state.className = "last-state " + kind;
    const word = (kind === "ok" ? "✓ " : kind === "warn" ? "↻ " : kind === "err" ? "× " : "") + stateWord;
    $("last-state-word").textContent = word;
    const nameEl = $("last-name");
    nameEl.textContent = name || "—";
    nameEl.title = name || "";
    const metaEl = $("last-meta");
    const meta = (metaParts || []).filter(Boolean).join(" · ") + (metaParts && metaParts.length ? " · " : "") + new Date().toLocaleTimeString();
    metaEl.textContent = meta;
    metaEl.title = meta;
    const reasonEl = $("last-reason");
    reasonEl.textContent = reason || "";
    reasonEl.style.display = reason ? "" : "none";
  }

  function _showScanNote(msg) {
    const note = $("scan-note");
    note.textContent = msg ? "× " + msg : "";
    note.classList.toggle("show", !!msg);
    if (msg) {
      clearTimeout(note._t);
      note._t = setTimeout(() => note.classList.remove("show"), 6000);
    }
  }

  async function _processScan(publicId) {
    const lastScan = _recentScans.get(publicId);
    if (lastScan && Date.now() - lastScan < DEDUP_MS) {
      log("duplicate ignored: " + publicId, "warn");
      return;
    }
    const placeholder = renderScanning(publicId);
    log("scanning " + publicId + "…");
    try {
      const r = await fetch("/scan/" + encodeURIComponent(publicId), { method: "POST" });
      const j = await r.json();
      if (placeholder.parentNode) placeholder.parentNode.removeChild(placeholder);
      if (!r.ok) {
        renderScanError(publicId, j.detail || ("Error " + r.status));
        log("scan failed: " + (j.detail || r.status), "err");
        toast("Scan didn't work — try again", "err");
      } else if (j.already_scanned) {
        renderAlreadyScanned(j);
        log("already scanned: " + publicId, "warn");
        toast("This guest already checked in", "warn");
        _recentScans.set(publicId, Date.now());
      } else {
        renderScanSuccess(j);
        log("printed + checked in: " + (j.ticket?.ticket_id || publicId), "ok");
        toast("Checked in — badge is printing");
        _recentScans.set(publicId, Date.now());
      }
    } catch (e) {
      if (placeholder.parentNode) placeholder.parentNode.removeChild(placeholder);
      renderScanError(publicId, String(e));
      log("scan error: " + e, "err");
      toast("Scan didn't work — try again", "err");
    }
  }

  async function _drainQueue() {
    while (_scanQueue.length > 0) {
      await _processScan(_scanQueue.shift());
    }
    _scanInFlight = false;
    $("scan-btn").disabled = false;
    $("scan-input").disabled = false;
    $("scan-input").placeholder = "Ready to scan…";
    focusScan();
  }

  async function scanTicket(ev) {
    ev.preventDefault();
    const publicId = $("scan-input").value.trim();
    if (!publicId) {
      const input = $("scan-input");
      input.placeholder = "Waiting for scan…";
      input.style.borderColor = "var(--warn)";
      setTimeout(() => {
        input.placeholder = "Ready to scan…";
        input.style.borderColor = "";
      }, 1500);
      return;
    }
    _showScanNote("");
    $("scan-input").value = "";
    $("scan-input").disabled = true;
    $("scan-input").placeholder = "Please wait…";
    setTimeout(() => {
      $("scan-input").disabled = _scanInFlight ? true : false;
      if (!$("scan-input").disabled) {
        $("scan-input").placeholder = "Ready to scan…";
        focusScan();
      }
    }, 80);
    if (_scanInFlight) {
      _scanQueue.push(publicId);
      log("queued: " + publicId);
      return;
    }
    _scanInFlight = true;
    $("scan-btn").disabled = true;
    $("scan-input").disabled = true;
    await _processScan(publicId);
    await _drainQueue();
  }

  async function reprintTicket(publicId, btn) {
    if (!publicId) return;
    btn.disabled = true;
    btn.textContent = "Reprinting…";
    log("reprinting " + publicId + "…");
    try {
      const r = await fetch("/scan/" + encodeURIComponent(publicId) + "/reprint", { method: "POST" });
      const j = await r.json();
      if (!r.ok) {
        const msg = j.detail || ("Error " + r.status);
        log("reprint failed: " + msg, "err");
        toast("Reprint failed — try again", "err");
        btn.disabled = false;
        btn.textContent = "Reprint";
      } else {
        log("reprinted: " + publicId, "ok");
        toast("Badge reprinted");
        btn.textContent = "Reprinted";
      }
    } catch (e) {
      log("reprint error: " + e, "err");
      toast("Reprint failed — try again", "err");
      btn.disabled = false;
      btn.textContent = "Reprint";
    }
  }
