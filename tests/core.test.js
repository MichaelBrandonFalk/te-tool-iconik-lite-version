const assert = require("assert");
const core = require("../te_iconik_lite_core.js");

const svodPass = `Created\t2026-03-19 13:21:38
Modified\t2026-03-19 13:21:38
Size\t6.75 GB
Format\tMPEG-4
Frame count\t8013
Frame rate\t23.976
Tim\t00:00:00:00
GENERAL
Count of audio streams\t1
File extension\tmov
File name\tPUR0003995
Overall bit rate\t174887093
Tim\t00:00:00:00
VIDEO
Bit rate\t172557886
Chroma subsampling\t4:2:2
Codec ID\tapch
Display aspect ratio\t1.778
Format\tProRes
Format profile\t422 HQ
Frame rate\t23.976
Height\t1080
Scan type\tProgressive
Width\t1920
AUDIO
Bit depth\t24
Bit rate\t2304000
Channel s\t2
Format\tPCM
Sampling rate\t48000`;

const svod2997Pass = svodPass.replace(/Frame rate\t23\.976/g, "Frame rate\t29.970");
const svodFail = svodPass.replace("Width\t1920", "Width\t1280").replace("Bit rate\t172557886", "Bit rate\t120000000");
const svodBadFrame = svodPass.replace(/Frame rate\t23\.976/g, "Frame rate\t23.964");
const svodMp4Warn = svodPass.replace("File extension\tmov", "File extension\tmp4");
const svod720Warn = svodPass.replace("Width\t1920", "Width\t720").replace("Height\t1080", "Height\t480");
const svodAudioWarn = svodPass
  .replace("Bit rate\t2304000", "Bit rate\t1536000")
  .replace("Sampling rate\t48000", "Sampling rate\t44100")
  .replace("Bit depth\t24", "Bit depth\t16");
const svodMissing = `GENERAL
File extension\tmov
VIDEO
Format\tProRes`;

const passResult = core.evaluateMetadata(svodPass, "pass.txt");
assert.strictEqual(passResult.verdict, "PASS");
assert.strictEqual(passResult.counts.fail, 0);
assert.strictEqual(passResult.title, "PUR0003995");

const pass2997Result = core.evaluateMetadata(svod2997Pass, "pass-2997.txt");
assert.strictEqual(pass2997Result.verdict, "PASS");
assert.ok(pass2997Result.checks.some((check) => check.id === "frame_rate" && check.status === "pass"));

const failResult = core.evaluateMetadata(svodFail, "fail.txt");
assert.strictEqual(failResult.verdict, "FAIL");
assert.ok(failResult.checks.some((check) => check.id === "resolution" && check.status === "fail"));
assert.ok(failResult.checks.some((check) => check.id === "video_bitrate" && check.status === "fail"));

const badFrameResult = core.evaluateMetadata(svodBadFrame, "bad-frame.txt");
assert.strictEqual(badFrameResult.verdict, "FAIL");
assert.ok(badFrameResult.checks.some((check) => check.id === "frame_rate" && check.status === "fail" && check.value === "23.96 fps"));

const mp4Result = core.evaluateMetadata(svodMp4Warn, "mp4.txt");
assert.strictEqual(mp4Result.verdict, "WARN");
assert.ok(mp4Result.checks.some((check) => check.id === "file_type" && check.status === "warn"));

const warn720Result = core.evaluateMetadata(svod720Warn, "720.txt");
assert.strictEqual(warn720Result.verdict, "WARN");
assert.ok(warn720Result.checks.some((check) => check.id === "resolution" && check.status === "warn"));
assert.ok(warn720Result.reason.includes("Resolution (WARNING: 720x480)"));

const audioWarnResult = core.evaluateMetadata(svodAudioWarn, "audio-warn.txt");
assert.strictEqual(audioWarnResult.verdict, "WARN");
assert.ok(audioWarnResult.checks.some((check) => check.id === "audio_bitrate" && check.status === "warn"));
assert.ok(audioWarnResult.checks.some((check) => check.id === "audio_sample_rate" && check.status === "warn"));
assert.ok(audioWarnResult.checks.some((check) => check.id === "audio_bit_depth" && check.status === "warn"));

const missingResult = core.evaluateMetadata(svodMissing, "missing.txt");
assert.strictEqual(missingResult.verdict, "MISSING INFO");
assert.ok(missingResult.counts.missing > 0);

const csv = core.toCsv([passResult]);
assert.ok(csv.startsWith("title,s3_prefix,verdict,reason,check,status,value,target,note"));
assert.ok(csv.includes("PUR0003995"));
assert.ok(csv.includes("File type"));
assert.strictEqual(core.VERSION, "V1.8");

console.log("core tests passed");
