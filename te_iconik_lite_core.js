(function (root) {
  "use strict";

  const VERSION = "V1.5";
  const MIN_VIDEO_BITRATE = 145000000;

  const CHECKS = [
    {
      id: "file_type",
      label: "File type",
      target: ".mov",
      evaluate: (m) => {
        const ext = cleanExtension(first(m, ["general.file extension", "summary.format extension", "file extension"]));
        return ext === "mov"
          ? pass(ext || ".mov")
          : fail(ext || "missing", "Expected .mov file extension.");
      },
    },
    {
      id: "video_codec",
      label: "Video codec",
      target: "ProRes 422 HQ / apch",
      evaluate: (m) => {
        const codecId = lower(first(m, ["video.codec id", "video.codec_tag_string", "codec id", "codec_tag_string"]));
        const ok = codecId === "apch";
        return ok ? pass(displayCodec(m)) : fail(displayCodec(m), "Expected ProRes 422 HQ.");
      },
    },
    {
      id: "video_bitrate",
      label: "Video bit rate",
      target: ">= 145 Mb/s",
      evaluate: (m) => {
        const raw = first(m, ["video.bit rate", "overall bit rate"]);
        const value = parseNumber(raw);
        if (!Number.isFinite(value)) return fail("missing", "Video bit rate was not available.");
        return value >= MIN_VIDEO_BITRATE
          ? pass(formatMbps(value))
          : fail(formatMbps(value), "Expected at least 145 Mb/s.");
      },
    },
    {
      id: "resolution",
      label: "Resolution",
      target: "1920x1080",
      evaluate: (m) => {
        const width = parseNumber(first(m, ["video.width", "width"]));
        const height = parseNumber(first(m, ["video.height", "height"]));
        const value = width && height ? `${width}x${height}` : "missing";
        return width === 1920 && height === 1080
          ? pass(value)
          : fail(value, "Expected exactly 1920x1080.");
      },
    },
    {
      id: "aspect_ratio",
      label: "Aspect ratio",
      target: "16:9",
      evaluate: (m) => {
        const raw = first(m, ["video.display aspect ratio string", "video.display aspect ratio", "display aspect ratio"]);
        const width = parseNumber(first(m, ["video.width", "width"]));
        const height = parseNumber(first(m, ["video.height", "height"]));
        const ratio = parseRatio(raw);
        const calculated = width && height ? width / height : NaN;
        const ok = raw === "16:9" || within(ratio, 1.76, 1.79) || within(calculated, 1.76, 1.79);
        return ok ? pass(raw || calculated.toFixed(3)) : fail(raw || "missing", "Expected 16:9.");
      },
    },
    {
      id: "frame_rate",
      label: "Frame rate",
      target: "23.98 or 29.97 fps",
      evaluate: (m) => {
        const value = parseFrameRate(first(m, ["video.r_frame_rate", "r_frame_rate", "video.frame rate", "frame rate", "video.frame rate string"]));
        if (!Number.isFinite(value)) return fail("missing", "Frame rate was not available.");
        const rounded = roundFrameRate(value);
        if (rounded === "23.98" || rounded === "29.97") return pass(`${rounded} fps`);
        return fail(`${rounded} fps`, "Expected 23.98 or 29.97 fps for SVOD.");
      },
    },
    {
      id: "chroma",
      label: "Chroma sampling",
      target: "4:2:2",
      evaluate: (m) => {
        const value = first(m, ["video.chroma subsampling", "video.chroma subsampling string", "video.pixel format", "video.pix_fmt"]);
        const ok = lower(value).includes("4:2:2") || lower(value).startsWith("yuv422");
        return ok ? pass(value) : fail(value || "missing", "Expected 4:2:2 chroma.");
      },
    },
    {
      id: "scan_type",
      label: "Scan type",
      target: "Progressive",
      evaluate: (m) => {
        const value = first(m, ["video.scan type", "video.scan type string", "video.field_order"]);
        return lower(value) === "progressive"
          ? pass(value)
          : fail(value || "missing", "Expected progressive scan.");
      },
    },
    {
      id: "audio_codec",
      label: "Audio codec",
      target: "PCM",
      evaluate: (m) => {
        const value = first(m, ["audio.format", "audio.commercial name", "audio codecs", "audio format list"]);
        return lower(value).startsWith("pcm") || lower(value).includes("pcm")
          ? pass(value)
          : fail(value || "missing", "Expected PCM audio.");
      },
    },
    {
      id: "audio_bitrate",
      label: "Audio bit rate",
      target: "channels x 1,152 kb/s",
      evaluate: (m) => {
        const channels = parseNumber(first(m, ["audio.channel s", "audio.channels", "audio channels total"]));
        const bitrate = parseNumber(first(m, ["audio.bit rate"]));
        if (!Number.isFinite(channels) || !Number.isFinite(bitrate)) return fail("missing", "Audio channels or bit rate was not available.");
        const expected = channels * 1152000;
        return bitrate === expected
          ? pass(formatKbps(bitrate))
          : fail(formatKbps(bitrate), `Expected ${formatKbps(expected)} for ${channels} channel(s).`);
      },
    },
    {
      id: "audio_sample_rate",
      label: "Audio sample rate",
      target: "48 kHz",
      evaluate: (m) => {
        const value = parseNumber(first(m, ["audio.sampling rate", "audio.sample rate"]));
        return value === 48000
          ? pass("48 kHz")
          : fail(value ? `${value} Hz` : "missing", "Expected 48000 Hz.");
      },
    },
    {
      id: "audio_bit_depth",
      label: "Audio bit depth",
      target: "24-bit",
      evaluate: (m) => {
        const value = parseNumber(first(m, ["audio.bit depth"]));
        return value === 24
          ? pass("24 bits")
          : fail(value ? `${value} bits` : "missing", "Expected 24-bit PCM.");
      },
    },
    {
      id: "stereo_only",
      label: "Stereo only",
      target: "1 stream, 2 channels",
      evaluate: (m) => {
        const streams = parseNumber(first(m, ["general.count of audio streams", "count of audio streams"]));
        const channels = parseNumber(first(m, ["audio.channel s", "audio.channels", "audio channels total"]));
        const streamOk = streams === 1 || !Number.isFinite(streams);
        const channelOk = channels === 2;
        if (streamOk && channelOk) return pass(`${streams || 1} stream, ${channels} channels`);
        return fail(`${streams || "?"} stream, ${channels || "?"} channels`, "Expected one stereo audio stream.");
      },
    },
    {
      id: "timecode_start",
      label: "Timecode start",
      target: "00:00:00:00 or 00;00;00;00",
      evaluate: (m) => {
        const value = first(m, ["general.tim", "tim", "timecode", "general.timecode"]);
        const normalized = String(value || "").trim();
        const ok = normalized === "00:00:00:00" || normalized === "00;00;00;00";
        return ok ? pass(normalized) : fail(normalized || "missing", "Expected SVOD start timecode at zero.");
      },
    },
  ];

  const INFO_CHECKS = [
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
    const verdict = counts.fail > 0 ? "FAIL" : counts.warn > 0 ? "WARN" : "PASS";
    return { ...parsed, checks, infoChecks, counts, verdict, version: VERSION };
  }

  function tally(checks) {
    return checks.reduce((acc, check) => {
      acc[check.status] = (acc[check.status] || 0) + 1;
      return acc;
    }, { pass: 0, fail: 0, warn: 0, info: 0 });
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
    const format = first(m, ["video.format", "video.commercial name", "video format list"]) || "missing";
    const profile = first(m, ["video.format profile"]);
    const codecId = first(m, ["video.codec id"]);
    return [format, profile, codecId ? `(${codecId})` : ""].filter(Boolean).join(" ");
  }

  function lower(value) {
    return String(value || "").trim().toLowerCase();
  }

  function formatMbps(value) {
    return `${(value / 1000000).toFixed(1)} Mb/s`;
  }

  function formatKbps(value) {
    return `${Math.round(value / 1000).toLocaleString("en-US")} kb/s`;
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

  function info(value, note = "") {
    return { status: "info", value, note };
  }

  function toCsv(results) {
    const rows = [["title", "s3_prefix", "verdict", "check", "status", "value", "target", "note"]];
    for (const result of results) {
      for (const check of [...result.checks, ...result.infoChecks]) {
        rows.push([result.title, result.s3Prefix, result.verdict, check.label, check.status.toUpperCase(), check.value, check.target, check.note || ""]);
      }
    }
    return rows.map((row) => row.map(csvCell).join(",")).join("\n");
  }

  function csvCell(value) {
    const text = String(value ?? "");
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  }

  const api = { VERSION, CHECKS, INFO_CHECKS, evaluateMetadata, parseMetadataText, toCsv, parseFrameRate, roundFrameRate };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.TeIconikLite = api;
})(typeof globalThis !== "undefined" ? globalThis : window);
