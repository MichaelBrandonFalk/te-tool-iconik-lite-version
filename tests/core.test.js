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

const svodWarn = svodPass.replace(/Frame rate\t23\.976/g, "Frame rate\t29.970");
const svodFail = svodPass.replace("Width\t1920", "Width\t1280").replace("Bit rate\t172557886", "Bit rate\t120000000");

const passResult = core.evaluateMetadata(svodPass, "pass.txt");
assert.strictEqual(passResult.verdict, "PASS");
assert.strictEqual(passResult.counts.fail, 0);
assert.strictEqual(passResult.title, "PUR0003995");

const warnResult = core.evaluateMetadata(svodWarn, "warn.txt");
assert.strictEqual(warnResult.verdict, "WARN");
assert.ok(warnResult.checks.some((check) => check.id === "frame_rate" && check.status === "warn"));

const failResult = core.evaluateMetadata(svodFail, "fail.txt");
assert.strictEqual(failResult.verdict, "FAIL");
assert.ok(failResult.checks.some((check) => check.id === "resolution" && check.status === "fail"));
assert.ok(failResult.checks.some((check) => check.id === "video_bitrate" && check.status === "fail"));

const csv = core.toCsv([passResult]);
assert.ok(csv.includes("PUR0003995"));
assert.ok(csv.includes("File type"));
assert.strictEqual(core.VERSION, "V1.1");

console.log("core tests passed");
