(function () {
  "use strict";

  const state = {
    results: [],
    selectedId: null,
  };

  const DEFAULT_DIRECT_TARGET = "s3://gacm-deliver-vod/";

  const els = {
    directPanel: document.querySelector(".direct-panel"),
    directTarget: document.getElementById("direct-target"),
    directCommand: document.getElementById("direct-command"),
    copyCommand: document.getElementById("copy-command"),
    directModeNote: document.getElementById("direct-mode-note"),
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
    failCount: document.getElementById("fail-count"),
    titleCount: document.getElementById("title-count"),
    exportCsv: document.getElementById("export-csv"),
    exportJson: document.getElementById("export-json"),
  };

  els.directTarget.addEventListener("input", renderDirectCommand);
  els.copyCommand.addEventListener("click", copyDirectCommand);
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
        adoptDirectTarget(labelTarget, "That field is only a report label. I moved the S3/Iconik target to the Direct S3/Iconik Scan command builder above.");
        return;
      }
      setStatus("Paste an Iconik metadata block or drop metadata text files.");
      return;
    }
    if (isOnlyDirectTarget(text)) {
      adoptDirectTarget(detectDirectTarget(text), "That looks like an S3/Iconik target, not metadata text. Use the generated local-scanner command above.");
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

  function renderDirectCommand() {
    const target = els.directTarget.value.trim() || DEFAULT_DIRECT_TARGET;
    els.directCommand.textContent = buildScannerCommand(target);
    els.directModeNote.textContent = /^s3:\/\//i.test(target)
      ? "S3 scans create the base inventory first, then match each video object to Iconik metadata."
      : "Iconik links scan the collection or asset through the Iconik API, then write the XLSX report.";
  }

  async function copyDirectCommand() {
    const text = els.directCommand.textContent;
    try {
      await navigator.clipboard.writeText(text);
      els.directModeNote.textContent = "Command copied. Paste it into Terminal from the unzipped V1.4 folder.";
    } catch {
      els.directModeNote.textContent = "Clipboard access was blocked. Select the command text and copy it manually.";
    }
  }

  function handleLabelInput() {
    const target = detectDirectTarget(els.prefixInput.value);
    if (!target) return;
    els.prefixInput.value = "";
    adoptDirectTarget(target, "That field is only a label for metadata exports. I copied the S3/Iconik target into the direct-scan command builder above.");
  }

  function handlePasteInput() {
    const text = els.pasteInput.value.trim();
    if (!isOnlyDirectTarget(text)) return;
    els.pasteInput.value = "";
    adoptDirectTarget(detectDirectTarget(text), "That looks like an S3/Iconik target. The browser page cannot scan it directly, so I built the local-scanner command above.");
  }

  function adoptDirectTarget(target, message) {
    if (!target) return;
    els.directTarget.value = target;
    renderDirectCommand();
    setStatus(message);
    els.directPanel.classList.add("is-highlighted");
    window.setTimeout(() => els.directPanel.classList.remove("is-highlighted"), 1800);
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

  function buildScannerCommand(target) {
    const quotedTarget = quoteForShell(target || DEFAULT_DIRECT_TARGET);
    const lines = [
      "python3 -m pip install -r requirements.txt",
      'export ICONIK_APP_ID="your-app-id"',
      'export ICONIK_AUTH_TOKEN="your-auth-token"',
    ];
    if (/^s3:\/\//i.test(target)) {
      lines.push("# Make sure AWS credentials can read this bucket or prefix.");
    }
    lines.push(`python3 te_iconik_scanner.py ${quotedTarget} -o te_iconik_lite_report.xlsx`);
    return lines.join("\n");
  }

  function quoteForShell(value) {
    return `"${String(value).replace(/(["\\$`])/g, "\\$1")}"`;
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
      acc.fail += result.counts.fail || 0;
      return acc;
    }, { pass: 0, warn: 0, fail: 0 });
    els.titleCount.textContent = String(state.results.length);
    els.passCount.textContent = String(totals.pass);
    els.warnCount.textContent = String(totals.warn);
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
        <td><span class="pill ${result.verdict.toLowerCase()}">${result.verdict}</span></td>
        <td>${result.counts.fail || 0}</td>
        <td>${result.counts.warn || 0}</td>
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

  function exportCsv() {
    download("te_tool_iconik_lite_results_v1_4.csv", TeIconikLite.toCsv(state.results), "text/csv");
  }

  function exportJson() {
    download("te_tool_iconik_lite_results_v1_4.json", JSON.stringify(state.results, null, 2), "application/json");
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

  renderDirectCommand();
  render();
})();
