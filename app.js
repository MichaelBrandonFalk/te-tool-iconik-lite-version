(function () {
  "use strict";

  const state = {
    results: [],
    selectedId: null,
  };

  const els = {
    appPanel: document.querySelector(".app-panel"),
    fileInput: document.getElementById("file-input"),
    folderInput: document.getElementById("folder-input"),
    pickButton: document.getElementById("pick-button"),
    folderButton: document.getElementById("folder-button"),
    scanButton: document.getElementById("scan-button"),
    clearButton: document.getElementById("clear-button"),
    pasteInput: document.getElementById("paste-input"),
    prefixInput: document.getElementById("s3-prefix"),
    statusLine: document.getElementById("status-line"),
    dropzone: document.getElementById("dropzone"),
    resultsBody: document.getElementById("results-body"),
    detailBody: document.getElementById("detail-body"),
    infoBody: document.getElementById("info-body"),
    selectedTitle: document.getElementById("selected-title"),
    emptyState: document.getElementById("empty-state"),
    passCount: document.getElementById("pass-count"),
    warnCount: document.getElementById("warn-count"),
    missingCount: document.getElementById("missing-count"),
    failCount: document.getElementById("fail-count"),
    titleCount: document.getElementById("title-count"),
    exportCsv: document.getElementById("export-csv"),
    exportJson: document.getElementById("export-json"),
  };

  els.pickButton.addEventListener("click", () => els.fileInput.click());
  els.folderButton.addEventListener("click", () => els.folderInput.click());
  els.fileInput.addEventListener("change", () => runFiles([...els.fileInput.files], true));
  els.folderInput.addEventListener("change", () => runFiles([...els.folderInput.files], true));
  els.scanButton.addEventListener("click", runPasted);
  els.clearButton.addEventListener("click", clearAll);
  els.exportCsv.addEventListener("click", exportCsv);
  els.exportJson.addEventListener("click", exportJson);
  els.prefixInput.addEventListener("input", handleLabelInput);
  els.pasteInput.addEventListener("input", handlePasteInput);

  ["dragenter", "dragover"].forEach((eventName) => {
    els.dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      els.dropzone.classList.add("is-dragging");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    els.dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      els.dropzone.classList.remove("is-dragging");
    });
  });

  els.dropzone.addEventListener("drop", (event) => {
    const files = [...event.dataTransfer.files].filter((file) => file.type.startsWith("text/") || /\.(txt|tsv|csv)$/i.test(file.name));
    runFiles(files, true);
  });

  async function runFiles(files, replace) {
    if (!files.length) {
      setStatus("No metadata text files selected.");
      return;
    }
    const next = [];
    for (const file of files) {
      const text = await file.text();
      next.push(TeIconikLite.evaluateMetadata(text, file.name, els.prefixInput.value.trim()));
    }
    state.results = replace ? next : [...state.results, ...next];
    state.selectedId = state.results[0]?.sourceName || null;
    render();
    setStatus(`Scanned ${next.length} metadata file${next.length === 1 ? "" : "s"}.`);
  }

  function runPasted() {
    const text = els.pasteInput.value.trim();
    const labelTarget = detectDirectTarget(els.prefixInput.value);
    if (!text) {
      if (labelTarget) {
        flagDesktopTarget("That field is only a report label. Download the Mac app above and paste the S3/Iconik target there.");
        return;
      }
      setStatus("Paste an Iconik metadata block or drop metadata text files.");
      return;
    }
    if (isOnlyDirectTarget(text)) {
      flagDesktopTarget("That looks like an S3/Iconik target, not metadata text. Download the Mac app above and paste the target there.");
      return;
    }
    const result = TeIconikLite.evaluateMetadata(text, "Pasted metadata", els.prefixInput.value.trim());
    state.results = [result];
    state.selectedId = result.sourceName;
    render();
    setStatus("Scanned pasted metadata.");
  }

  function clearAll() {
    state.results = [];
    state.selectedId = null;
    els.fileInput.value = "";
    els.folderInput.value = "";
    els.pasteInput.value = "";
    render();
    setStatus("Ready for Iconik metadata.");
  }

  function handleLabelInput() {
    const target = detectDirectTarget(els.prefixInput.value);
    if (!target) return;
    els.prefixInput.value = "";
    flagDesktopTarget("That field is only a label for metadata exports. Download the Mac app above and paste the S3/Iconik target there.");
  }

  function handlePasteInput() {
    const text = els.pasteInput.value.trim();
    if (!isOnlyDirectTarget(text)) return;
    els.pasteInput.value = "";
    flagDesktopTarget("That looks like an S3/Iconik target. The browser metadata checker cannot scan it, but the Mac app above can.");
  }

  function flagDesktopTarget(message) {
    setStatus(message);
    els.appPanel.classList.add("is-highlighted");
    window.setTimeout(() => els.appPanel.classList.remove("is-highlighted"), 1800);
  }

  function isOnlyDirectTarget(text) {
    const trimmed = String(text || "").trim();
    const target = detectDirectTarget(trimmed);
    if (!target) return false;
    const hasMetadataSignals = /\b(GENERAL|VIDEO|AUDIO|Frame rate|File extension|Codec ID)\b/i.test(trimmed);
    return !hasMetadataSignals && trimmed.length <= target.length + 4;
  }

  function detectDirectTarget(value) {
    const text = String(value || "").trim();
    const match = text.match(/s3:\/\/[^\s"'<>]+/i)
      || text.match(/https:\/\/app\.iconik\.io\/(?:collection|asset)\/[a-z0-9-]+/i);
    return match ? match[0].replace(/[),.;]+$/, "") : "";
  }

  function render() {
    renderSummary();
    renderResults();
    renderDetails();
    const hasResults = state.results.length > 0;
    els.exportCsv.disabled = !hasResults;
    els.exportJson.disabled = !hasResults;
  }

  function renderSummary() {
    const totals = state.results.reduce((acc, result) => {
      acc.pass += result.counts.pass || 0;
      acc.warn += result.counts.warn || 0;
      acc.missing += result.counts.missing || 0;
      acc.fail += result.counts.fail || 0;
      return acc;
    }, { pass: 0, warn: 0, missing: 0, fail: 0 });
    els.titleCount.textContent = String(state.results.length);
    els.passCount.textContent = String(totals.pass);
    els.warnCount.textContent = String(totals.warn);
    els.missingCount.textContent = String(totals.missing);
    els.failCount.textContent = String(totals.fail);
  }

  function renderResults() {
    els.resultsBody.innerHTML = "";
    els.emptyState.hidden = state.results.length > 0;
    for (const result of state.results) {
      const tr = document.createElement("tr");
      tr.className = result.sourceName === state.selectedId ? "is-selected" : "";
      tr.innerHTML = `
        <td><button class="row-button" type="button" data-id="${escapeAttr(result.sourceName)}">${escapeHtml(result.title)}</button></td>
        <td><span class="pill ${statusClass(result.verdict)}">${result.verdict}</span></td>
        <td>${result.counts.fail || 0}</td>
        <td>${result.counts.warn || 0}</td>
        <td>${result.counts.missing || 0}</td>
      `;
      els.resultsBody.appendChild(tr);
    }
    els.resultsBody.querySelectorAll("button[data-id]").forEach((button) => {
      button.addEventListener("click", () => {
        state.selectedId = button.dataset.id;
        render();
      });
    });
  }

  function renderDetails() {
    const result = state.results.find((item) => item.sourceName === state.selectedId) || state.results[0];
    els.detailBody.innerHTML = "";
    els.infoBody.innerHTML = "";
    if (!result) {
      els.selectedTitle.textContent = "No title selected";
      return;
    }
    els.selectedTitle.textContent = result.title;
    for (const check of result.checks) {
      els.detailBody.appendChild(checkRow(check));
    }
    for (const check of result.infoChecks) {
      els.infoBody.appendChild(checkRow(check));
    }
  }

  function checkRow(check) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(check.label)}</td>
      <td><span class="pill ${check.status}">${check.status.toUpperCase()}</span></td>
      <td>${escapeHtml(check.value || "")}</td>
      <td>${escapeHtml(check.target || "")}</td>
      <td>${escapeHtml(check.note || "")}</td>
    `;
    return tr;
  }

  function statusClass(status) {
    const normalized = String(status || "").toLowerCase().replace(/\s+/g, "-");
    return normalized === "missing-info" ? "missing" : normalized;
  }

  function exportCsv() {
    download("te_tool_iconik_lite_results_v1_5.csv", TeIconikLite.toCsv(state.results), "text/csv");
  }

  function exportJson() {
    download("te_tool_iconik_lite_results_v1_5.json", JSON.stringify(state.results, null, 2), "application/json");
  }

  function download(name, content, type) {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function setStatus(message) {
    els.statusLine.textContent = message;
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[char]));
  }

  function escapeAttr(value) {
    return escapeHtml(value).replace(/`/g, "&#96;");
  }

  render();
})();
