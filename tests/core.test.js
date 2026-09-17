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
Pixel aspect ratio\t1:1
Color primaries\tBT.709
Matrix coefficients\tBT.709
Transfer characteristics\tBT.709
Scan type\tProgressive
Width\t1920
AUDIO
Bit depth\t24
Bit rate\t2304000
Channel s\t2
Format\tPCM
Language\teng
Loudness\t-24.0 LKFS
Sampling rate\t48000`;
const officialPass = `${svodPass}\nTrue peak\t-2.5 dBTP`;

const svodMp4Pass = officialPass.replace("File extension\tmov", "File extension\tmp4").replace("Codec ID\tapch", "Codec ID\tavc1").replace("Format\tProRes", "Format\tAVC");
const svodFail = officialPass.replace("Width\t1920", "Width\t1280").replace("True peak\t-2.5 dBTP", "True peak\t-1.5 dBTP");
const svodBadFrame = officialPass.replace(/Frame rate\t23\.976/g, "Frame rate\t23.964");
const svodSdPass = officialPass.replace("Width\t1920", "Width\t720").replace("Height\t1080", "Height\t480").replace("Display aspect ratio\t1.778", "Display aspect ratio\t1.333");
const svodLoudnessFail = officialPass.replace("Loudness\t-24.0 LKFS", "Loudness\t-20.5 LKFS");
const svodHdrFail = officialPass.replace("Color primaries\tBT.709", "Color primaries\tBT.2020");
const svodMissing = `GENERAL
File extension\tmov
VIDEO
Format\tProRes`;

const passResult = core.evaluateMetadata(officialPass, "pass.txt");
assert.strictEqual(passResult.verdict, "PASS");
assert.strictEqual(passResult.counts.fail, 0);
assert.strictEqual(passResult.title, "PUR0003995");

const failResult = core.evaluateMetadata(svodFail, "fail.txt");
assert.strictEqual(failResult.verdict, "FAIL");
assert.ok(failResult.checks.some((check) => check.id === "resolution" && check.status === "fail"));
assert.ok(failResult.checks.some((check) => check.id === "true_peak" && check.status === "fail"));

const badFrameResult = core.evaluateMetadata(svodBadFrame, "bad-frame.txt");
assert.strictEqual(badFrameResult.verdict, "PASS");
assert.ok(!badFrameResult.checks.some((check) => check.id === "frame_rate"));

const mp4Result = core.evaluateMetadata(svodMp4Pass, "mp4.txt");
assert.strictEqual(mp4Result.verdict, "PASS");
assert.ok(mp4Result.checks.some((check) => check.id === "file_type" && check.status === "pass"));

const sdResult = core.evaluateMetadata(svodSdPass, "720.txt");
assert.strictEqual(sdResult.verdict, "PASS");
assert.ok(sdResult.checks.some((check) => check.id === "resolution" && check.status === "pass"));

const loudnessResult = core.evaluateMetadata(svodLoudnessFail, "loudness-fail.txt");
assert.strictEqual(loudnessResult.verdict, "FAIL");
assert.ok(loudnessResult.checks.some((check) => check.id === "loudness" && check.status === "fail"));

const hdrResult = core.evaluateMetadata(svodHdrFail, "hdr-fail.txt");
assert.strictEqual(hdrResult.verdict, "FAIL");
assert.ok(hdrResult.checks.some((check) => check.id === "color_space" && check.status === "fail"));

const missingResult = core.evaluateMetadata(svodMissing, "missing.txt");
assert.strictEqual(missingResult.verdict, "MISSING INFO");
assert.ok(missingResult.counts.missing > 0);

const csv = core.toCsv([passResult]);
assert.ok(csv.startsWith("title,s3_prefix,verdict,reason,check,status,value,target,note"));
assert.ok(csv.includes("PUR0003995"));
assert.ok(csv.includes("File type"));
assert.strictEqual(core.VERSION, "V1.10");

console.log("core tests passed");
