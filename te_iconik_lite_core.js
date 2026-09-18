(function (root) {
  "use strict";

  const VERSION = "V1.12";

  const CHECKS = [
    {
      id: "file_type",
      label: "File type",
      target: ".mov or high-bitrate .mp4",
      evaluate: (m) => {
        const ext = cleanExtension(first(m, ["general.file extension", "summary.format extension", "file extension"]));
        if (!ext) return missing("missing", "File extension was not available.");
        if (ext === "mov" || ext === "mp4") return pass(ext);
        return fail(ext, "Expected .mov or accepted high-bitrate .mp4.");
      },
    },
    {
      id: "video_codec",
      label: "Video codec",
      target: "ProRes 422 HQ or native high-bitrate MP4 codec",
      evaluate: (m) => {
        const codecId = lower(first(m, ["video.codec id", "video.codec_tag_string", "codec id", "codec_tag_string", "video codec"]));
        const display = displayCodec(m);
        if (!codecId && display === "missing") return missing("missing", "Video codec was not available.");
        const text = lower(`${codecId} ${display}`);
        const ok = ["apch", "prores", "h264", "h.264", "avc", "avc1", "hevc", "h265", "h.265"].some((part) => text.includes(part));
        return ok ? pass(display) : fail(display, "Expected ProRes 422 HQ or common native MP4 codec metadata.");
      },
    },
    {
      id: "resolution",
      label: "Resolution",
      target: "HD 1920x1080 or SD min 480p",
      evaluate: (m) => {
        const width = parseNumber(first(m, ["video.width", "width"]));
        const height = parseNumber(first(m, ["video.height", "height"]));
        const parsed = !width || !height ? parseResolution(first(m, ["video.resolution", "video resolution", "resolution"])) : null;
        const finalWidth = width || (parsed ? parsed[0] : NaN);
        const finalHeight = height || (parsed ? parsed[1] : NaN);
        if (!Number.isFinite(finalWidth) || !Number.isFinite(finalHeight)) return missing("missing", "Resolution was not available.");
        const value = `${finalWidth}x${finalHeight}`;
        if (finalWidth === 1920 && finalHeight === 1080) return pass(value);
        if (Math.min(finalWidth, finalHeight) >= 480 && Math.max(finalWidth, finalHeight) <= 1024) return pass(value);
        return fail(value, "Expected HD 1920x1080 or SD at least 480p.");
      },
    },
    {
      id: "aspect_ratio",
      label: "Aspect ratio",
      target: "HD 16:9 or SD 4:3",
      evaluate: (m) => {
        const raw = first(m, ["video.display aspect ratio string", "video.display aspect ratio", "display aspect ratio"]);
        const width = parseNumber(first(m, ["video.width", "width"]));
        const height = parseNumber(first(m, ["video.height", "height"]));
        const parsed = !width || !height ? parseResolution(first(m, ["video.resolution", "video resolution", "resolution"])) : null;
        const finalWidth = width || (parsed ? parsed[0] : NaN);
        const finalHeight = height || (parsed ? parsed[1] : NaN);
        const ratio = parseRatio(raw);
        const calculated = finalWidth && finalHeight ? finalWidth / finalHeight : NaN;
        if (!raw && !Number.isFinite(calculated)) return missing("missing", "Aspect ratio or resolution was not available.");
        const isHd = finalWidth === 1920 && finalHeight === 1080;
        const isSd = finalWidth && finalHeight && Math.min(finalWidth, finalHeight) >= 480 && Math.max(finalWidth, finalHeight) <= 1024;
        const hdOk = raw === "16:9" || within(ratio, 1.76, 1.79) || within(calculated, 1.76, 1.79);
        const sdOk = raw === "4:3" || within(ratio, 1.32, 1.34) || within(calculated, 1.32, 1.34);
        const ok = isHd ? hdOk : isSd ? sdOk : hdOk || sdOk;
        return ok ? pass(raw || calculated.toFixed(3)) : fail(raw || "missing", "Expected HD 16:9 or SD 4:3.");
      },
    },
    {
      id: "pixel_aspect_ratio",
      label: "Pixel aspect ratio",
      target: "1:1",
      evaluate: (m) => {
        const value = first(m, ["video.pixel aspect ratio", "pixel aspect ratio", "sample aspect ratio", "video.sample aspect ratio"]);
        const ratio = parseRatio(value);
        if (!value && !Number.isFinite(ratio)) return missing("missing", "Pixel aspect ratio was not available.");
        const ok = value === "1:1" || within(ratio, 0.995, 1.005);
        return ok ? pass(value || ratio.toFixed(3)) : fail(value || "missing", "Expected square pixels / 1:1.");
      },
    },
    {
      id: "scan_type",
      label: "Scan type",
      target: "Progressive",
      evaluate: (m) => {
        const value = first(m, ["video.scan type", "video scan type", "video.scan type string", "video.field_order"]);
        if (!value) return missing("missing", "Scan type was not available.");
        return lower(value) === "progressive"
          ? pass(value)
          : fail(value || "missing", "Expected progressive scan.");
      },
    },
    {
      id: "color_space",
      label: "Color space",
      target: "SDR Rec.709",
      evaluate: (m) => {
        const values = [
          first(m, ["video.color space", "color space", "colour space"]),
          first(m, ["video.color primaries", "color primaries", "colour primaries"]),
          first(m, ["video.matrix coefficients", "matrix coefficients"]),
          first(m, ["video.transfer characteristics", "transfer characteristics"]),
        ].filter(Boolean);
        const value = [...new Set(values)].join(" / ");
        if (!value) return missing("missing", "Color space / Rec.709 metadata was not available.");
        const ok = ["rec.709", "bt.709", "bt709", "709", "sdr"].some((part) => lower(value).includes(part));
        return ok && !containsHdrColorSignal(value)
          ? pass(value)
          : fail(value || "missing", "Expected SDR Rec.709 color metadata.");
      },
    },
    {
      id: "stereo_only",
      label: "Audio mapping / stereo",
      target: "Track 1 stereo interleaved L+R",
      evaluate: (m) => {
        const streams = parseNumber(first(m, ["general.count of audio streams", "count of audio streams"]));
        const channels = parseNumber(first(m, ["audio.channel s", "audio.channels", "audio channels", "audio channels total"]));
        if (!Number.isFinite(channels)) return missing("missing", "Audio channel count was not available.");
        const streamOk = streams === 1 || !Number.isFinite(streams);
        const channelOk = channels === 2;
        if (streamOk && channelOk) return pass(`${streams || 1} stream, ${channels} channels`);
        return fail(`${streams || "?"} stream, ${channels || "?"} channels`, "Expected one stereo audio stream.");
      },
    },
    {
      id: "audio_language",
      label: "Audio language",
      target: "One language per file",
      evaluate: (m) => {
        const value = first(m, ["audio.language", "language", "audio language"]);
        if (!value) return missing("missing", "Audio language metadata was not available.");
        const languages = languageValues(value);
        if (languages.length === 1) return pass(languages[0]);
        return fail(languages.join(", ") || value, "Expected one language per video file.");
      },
    },
  ];

  const INFO_CHECKS = [
    {
      id: "loudness",
      label: "Loudness",
      target: "Optional / not checked by default",
      evaluate: (m) => {
        const value = parseFloatNumber(first(m, ["audio.loudness", "loudness", "integrated loudness", "audio.integrated loudness"]));
        return Number.isFinite(value)
          ? info(formatMeasurement(value, "LKFS"))
          : info("not checked", "Loudness is not checked by the default VOD profile.");
      },
    },
    {
      id: "true_peak",
      label: "True peak",
      target: "Optional / not checked by default",
      evaluate: (m) => {
        const value = parseFloatNumber(first(m, ["audio.true peak", "true peak", "audio.true_peak", "true_peak"]));
        return Number.isFinite(value)
          ? info(formatMeasurement(value, "dBTP"))
          : info("not checked", "True peak is not checked by the default VOD profile.");
      },
    },
    {
      id: "timecode_start",
      label: "Timecode start",
      target: "Optional in desktop Settings",
      evaluate: (m) => {
        const value = first(m, ["general.tim", "tim", "timecode", "general.timecode"]);
        return value ? info(value) : info("not checked", "Timecode Start can be enabled in the desktop app profile settings.");
      },
    },
    {
      id: "caption_track",
      label: "Caption/text track",
      target: "Reported if present",
      evaluate: (m) => {
        const value = first(m, ["general.text codecs", "text.format", "text format list", "count of text streams"]);
        return value ? info(value) : info("not reported", "Iconik metadata did not expose a text/caption stream.");
      },
    },
  ];

  function parseMetadataText(text, sourceName = "Pasted metadata", s3Prefix = "") {
    const sections = { summary: {}, general: {}, video: {}, audio: {}, text: {} };
    let section = "summary";
    const lines = String(text || "").split(/\r?\n/);

    for (const rawLine of lines) {
      const line = rawLine.trim();
      if (!line) continue;
      const upper = line.toUpperCase();
      if (["GENERAL", "VIDEO", "AUDIO", "TEXT"].includes(upper)) {
        section = upper.toLowerCase();
        continue;
      }
      const parsed = splitKeyValue(line);
      if (!parsed) continue;
      const key = normalizeKey(parsed.key);
      const value = parsed.value.trim();
      if (!key || !value) continue;
      sections[section][key] = value;
    }

    const flat = {};
    for (const [sectionName, values] of Object.entries(sections)) {
      for (const [key, value] of Object.entries(values)) {
        flat[`${sectionName}.${key}`] = value;
        if (!(key in flat)) flat[key] = value;
      }
    }

    const title = titleFromMetadata(flat, sourceName);
    return { sourceName, s3Prefix, title, sections, flat };
  }

  function evaluateMetadata(text, sourceName = "Pasted metadata", s3Prefix = "") {
    const parsed = parseMetadataText(text, sourceName, s3Prefix);
    const checks = CHECKS.map((check) => ({ id: check.id, label: check.label, target: check.target, ...check.evaluate(parsed.flat) }));
    const infoChecks = INFO_CHECKS.map((check) => ({ id: check.id, label: check.label, target: check.target, ...check.evaluate(parsed.flat) }));
    const counts = tally(checks);
    const verdict = counts.fail > 0 ? "FAIL" : counts.missing > 0 ? "MISSING INFO" : counts.warn > 0 ? "WARN" : "PASS";
    const reason = reasonForChecks(checks);
    return { ...parsed, checks, infoChecks, counts, verdict, reason, version: VERSION };
  }

  function tally(checks) {
    return checks.reduce((acc, check) => {
      acc[check.status] = (acc[check.status] || 0) + 1;
      return acc;
    }, { pass: 0, fail: 0, warn: 0, missing: 0, info: 0 });
  }

  function splitKeyValue(line) {
    const tab = line.indexOf("\t");
    if (tab > -1) return { key: line.slice(0, tab), value: line.slice(tab + 1) };
    const match = line.match(/^([^:]+):\s*(.+)$/);
    return match ? { key: match[1], value: match[2] } : null;
  }

  function titleFromMetadata(m, sourceName) {
    const fromMeta = first(m, ["general.file name", "file name", "general.file name extension", "file name extension"]);
    if (fromMeta) return stripQuery(fromMeta);
    return sourceName.replace(/\.(txt|tsv|csv)$/i, "");
  }

  function first(m, keys) {
    for (const key of keys) {
      const value = m[normalizeKey(key)];
      if (value !== undefined && value !== null && String(value).trim() !== "") return String(value).trim();
    }
    return "";
  }

  function normalizeKey(key) {
    return String(key || "")
      .trim()
      .toLowerCase()
      .replace(/_/g, " ")
      .replace(/\s+/g, " ");
  }

  function parseNumber(value) {
    if (value === undefined || value === null) return NaN;
    const cleaned = String(value).replace(/,/g, "").replace(/\s+/g, " ").trim();
    const match = cleaned.match(/-?\d+(?:\.\d+)?/);
    if (!match) return NaN;
    let number = Number(match[0]);
    const lowerValue = cleaned.toLowerCase();
    if (lowerValue.includes("mb/s")) number *= 1000000;
    if (lowerValue.includes("kb/s")) number *= 1000;
    if (lowerValue.includes("khz")) number *= 1000;
    return Math.round(number);
  }

  function parseFloatNumber(value) {
    if (value === undefined || value === null) return NaN;
    const cleaned = String(value).replace(/,/g, "").replace(/\s+/g, " ").trim();
    const match = cleaned.match(/-?\d+(?:\.\d+)?/);
    if (!match) return NaN;
    let number = Number(match[0]);
    const lowerValue = cleaned.toLowerCase();
    if (lowerValue.includes("mb/s")) number *= 1000000;
    if (lowerValue.includes("kb/s")) number *= 1000;
    if (lowerValue.includes("khz")) number *= 1000;
    return number;
  }

  function parseFrameRate(value) {
    const raw = String(value || "").trim();
    const fraction = raw.match(/(\d+)\s*\/\s*(\d+)/);
    if (fraction) return Number(fraction[1]) / Number(fraction[2]);
    const number = raw.match(/\d+(?:\.\d+)?/);
    return number ? Number(number[0]) : NaN;
  }

  function roundFrameRate(value) {
    return (Math.round(value * 100) / 100).toFixed(2);
  }

  function parseRatio(value) {
    const raw = String(value || "").trim();
    const colon = raw.match(/(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)/);
    if (colon) return Number(colon[1]) / Number(colon[2]);
    const number = raw.match(/\d+(?:\.\d+)?/);
    return number ? Number(number[0]) : NaN;
  }

  function parseResolution(value) {
    const match = String(value || "").replace(/\s+/g, "").toLowerCase().match(/(\d{3,5})[x×](\d{3,5})/);
    return match ? [Number(match[1]), Number(match[2])] : null;
  }

  function within(value, min, max) {
    return Number.isFinite(value) && value > min && value < max;
  }

  function cleanExtension(value) {
    const raw = stripQuery(value).trim();
    if (!raw) return "";
    if (raw.includes(".")) return raw.split(".").pop();
    return raw;
  }

  function stripQuery(value) {
    return String(value || "").split("?")[0];
  }

  function displayCodec(m) {
    const format = first(m, ["video.codec", "video codec", "video.format", "video.commercial name", "video format list", "codec"]) || "missing";
    const profile = first(m, ["video.format profile"]);
    const codecId = first(m, ["video.codec id"]);
    return [format, profile, codecId ? `(${codecId})` : ""].filter(Boolean).join(" ");
  }

  function lower(value) {
    return String(value || "").trim().toLowerCase();
  }

  function containsHdrColorSignal(value) {
    const text = lower(value);
    return ["bt.2020", "bt2020", "2020", "pq", "smpte st 2084", "hlg", "hdr"].some((part) => text.includes(part));
  }

  function formatMbps(value) {
    return `${(value / 1000000).toFixed(1)} Mb/s`;
  }

  function formatKbps(value) {
    return `${Math.round(value / 1000).toLocaleString("en-US")} kb/s`;
  }

  function formatMeasurement(value, unit) {
    const text = Number(value).toFixed(2).replace(/\.?0+$/, "");
    return `${text} ${unit}`;
  }

  function languageValues(value) {
    const ignored = new Set(["", "und", "undefined", "unknown", "n/a", "none", "not reported"]);
    return [...new Set(String(value || "")
      .split(/[,|;/]+/)
      .map((part) => part.trim().toLowerCase())
      .filter((part) => !ignored.has(part)))].sort();
  }

  function pass(value, note = "") {
    return { status: "pass", value, note };
  }

  function fail(value, note = "") {
    return { status: "fail", value, note };
  }

  function warn(value, note = "") {
    return { status: "warn", value, note };
  }

  function missing(value, note = "") {
    return { status: "missing", value, note };
  }

  function info(value, note = "") {
    return { status: "info", value, note };
  }

  function toCsv(results) {
    const rows = [["title", "s3_prefix", "verdict", "reason", "check", "status", "value", "target", "note"]];
    for (const result of results) {
      for (const check of [...result.checks, ...result.infoChecks]) {
        rows.push([result.title, result.s3Prefix, result.verdict, result.reason || "", check.label, check.status.toUpperCase(), check.value, check.target, check.note || ""]);
      }
    }
    return rows.map((row) => row.map(csvCell).join(",")).join("\n");
  }

  function reasonForChecks(checks) {
    const problemChecks = checks.filter((check) => ["fail", "warn", "missing"].includes(check.status));
    return problemChecks.map((check) => `${check.label} (${reasonStatus(check.status)}: ${check.value})`).join("; ");
  }

  function reasonStatus(status) {
    if (status === "warn") return "WARNING";
    if (status === "missing") return "MISSING INFO";
    return String(status || "").toUpperCase();
  }

  function csvCell(value) {
    const text = String(value ?? "");
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  }

  const api = { VERSION, CHECKS, INFO_CHECKS, evaluateMetadata, parseMetadataText, toCsv, parseFrameRate, roundFrameRate };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.TeIconikLite = api;
})(typeof globalThis !== "undefined" ? globalThis : window);
