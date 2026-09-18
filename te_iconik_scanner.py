#!/usr/bin/env python3
"""Local Iconik/S3 SVOD scanner for TE Tool - Iconik Lite Version.

This script talks to Iconik from the user's machine, gathers file metadata for a
collection or S3 prefix, applies the same SVOD metadata checks as the browser
app, and writes a color-coded XLSX report.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import posixpath
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple
from xml.sax.saxutils import escape


VERSION = "V1.12"
VIDEO_EXTENSIONS = {".mov", ".mp4", ".m4v", ".mxf"}
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
ANY_UUID_RE = re.compile(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", re.I)
S3_RE = re.compile(r"^s3://([^/]+)(?:/(.*))?$", re.I)

PASS_FILL = "DDEFD9"
WARN_FILL = "F8E7B8"
FAIL_FILL = "E8DDF3"
MISSING_FILL = "DCEAF7"
INFO_FILL = "EAF0F6"
HEADER_FILL = "D9EAF1"


CHECK_DEFS = [
    ("file_type", "File type", ".mov or high-bitrate .mp4"),
    ("video_codec", "Video codec", "ProRes 422 HQ or native high-bitrate MP4 codec"),
    ("video_bitrate", "Video bit rate", "Reported / profile-specific"),
    ("resolution", "Resolution", "HD 1920x1080 or SD min 480p"),
    ("aspect_ratio", "Aspect ratio", "HD 16:9 or SD 4:3"),
    ("pixel_aspect_ratio", "Pixel aspect ratio", "1:1"),
    ("frame_rate", "Frame rate", "23.98 or 29.97 fps"),
    ("chroma", "Chroma sampling", "4:2:2"),
    ("scan_type", "Scan type", "Progressive"),
    ("color_space", "Color space", "SDR Rec.709"),
    ("audio_codec", "Audio codec", "PCM"),
    ("audio_bitrate", "Audio bit rate", "channels x 1,152 kb/s"),
    ("audio_sample_rate", "Audio sample rate", "48 kHz"),
    ("audio_bit_depth", "Audio bit depth", "24-bit"),
    ("stereo_only", "Audio mapping / stereo", "Track 1 stereo interleaved L+R"),
    ("audio_language", "Audio language", "One language per file"),
    ("loudness", "Loudness", "-24 LKFS +/- 2"),
    ("true_peak", "True peak", "<= -2 dBTP"),
    ("timecode_start", "Timecode start", "00:00:00:00 or 00;00;00;00"),
]

OFFICIAL_VOD_PROFILE_NAME = "VOD Technical Delivery Specification 2026_09_17"
STRICT_PROFILE_NAME = "Original TE CHECK - Strict"
LEGACY_LITE_PROFILE_NAME = "TE Tool Lite V1.9 SVOD"
LEGACY_CUSTOM_PROFILE_NAME = "Previous Saved Custom Profile"
CHECK_PROFILE_DEFAULTS_VERSION = "V1.12"
OFFICIAL_VOD_DISABLED_BY_DEFAULT_CHECKS = {"loudness", "true_peak", "timecode_start"}

OFFICIAL_VOD_CHECK_PROFILE = {
    "file_type": {
        "enabled": True,
        "pass": "mov, mp4",
        "warning": "",
        "fail": "anything else",
    },
    "video_codec": {
        "enabled": True,
        "pass": "apch, prores, h264, h.264, avc, avc1, hevc, h265, h.265",
        "warning": "",
        "fail": "anything else",
    },
    "video_bitrate": {
        "enabled": False,
        "pass": "",
        "warning": "",
        "fail": "",
    },
    "resolution": {
        "enabled": True,
        "pass": "1920x1080, SD >= 480p",
        "warning": "",
        "fail": "anything else",
    },
    "aspect_ratio": {
        "enabled": True,
        "pass": "HD 16:9 or SD 4:3",
        "warning": "",
        "fail": "anything else",
    },
    "pixel_aspect_ratio": {
        "enabled": True,
        "pass": "1:1, 1.0",
        "warning": "",
        "fail": "anything else",
    },
    "frame_rate": {
        "enabled": False,
        "pass": "",
        "warning": "",
        "fail": "",
    },
    "chroma": {
        "enabled": False,
        "pass": "",
        "warning": "",
        "fail": "",
    },
    "scan_type": {
        "enabled": True,
        "pass": "progressive",
        "warning": "",
        "fail": "anything else",
    },
    "color_space": {
        "enabled": True,
        "pass": "rec.709, bt.709, bt709, 709, sdr",
        "warning": "",
        "fail": "anything else",
    },
    "audio_codec": {
        "enabled": False,
        "pass": "",
        "warning": "",
        "fail": "",
    },
    "audio_bitrate": {
        "enabled": False,
        "pass": "",
        "warning": "",
        "fail": "",
    },
    "audio_sample_rate": {
        "enabled": False,
        "pass": "",
        "warning": "",
        "fail": "",
    },
    "audio_bit_depth": {
        "enabled": False,
        "pass": "",
        "warning": "",
        "fail": "",
    },
    "stereo_only": {
        "enabled": True,
        "pass": "1 stream, 2 channels",
        "warning": "",
        "fail": "anything else",
    },
    "audio_language": {
        "enabled": True,
        "pass": "1 language",
        "warning": "",
        "fail": "anything else",
    },
    "loudness": {
        "enabled": False,
        "pass": "-26 - -22 LKFS",
        "warning": "",
        "fail": "anything else",
    },
    "true_peak": {
        "enabled": False,
        "pass": "<= -2 dBTP",
        "warning": "",
        "fail": "anything else",
    },
    "timecode_start": {
        "enabled": False,
        "pass": "00:00:00:00, 00;00;00;00",
        "warning": "",
        "fail": "anything else",
    },
}

STRICT_TE_CHECK_PROFILE = {
    "file_type": {
        "enabled": True,
        "pass": "mov",
        "warning": "",
        "fail": "anything else",
    },
    "video_codec": {
        "enabled": True,
        "pass": "apch, prores",
        "warning": "",
        "fail": "anything else",
    },
    "video_bitrate": {
        "enabled": True,
        "pass": ">= 145 Mb/s",
        "warning": "",
        "fail": "below pass minimum",
    },
    "resolution": {
        "enabled": True,
        "pass": "1920x1080",
        "warning": "",
        "fail": "anything else",
    },
    "aspect_ratio": {
        "enabled": True,
        "pass": "16:9, 1.76-1.79",
        "warning": "",
        "fail": "anything else",
    },
    "pixel_aspect_ratio": {
        "enabled": True,
        "pass": "1:1, 1.0",
        "warning": "",
        "fail": "anything else",
    },
    "frame_rate": {
        "enabled": True,
        "pass": "23.98, 29.97",
        "warning": "",
        "fail": "anything else",
    },
    "chroma": {
        "enabled": True,
        "pass": "4:2:2, yuv422",
        "warning": "",
        "fail": "anything else",
    },
    "scan_type": {
        "enabled": True,
        "pass": "progressive",
        "warning": "",
        "fail": "anything else",
    },
    "color_space": {
        "enabled": True,
        "pass": "rec.709, bt.709, bt709, 709, sdr",
        "warning": "",
        "fail": "anything else",
    },
    "audio_codec": {
        "enabled": True,
        "pass": "pcm",
        "warning": "",
        "fail": "anything else",
    },
    "audio_bitrate": {
        "enabled": True,
        "pass": "channels x 1152 kb/s",
        "warning": "",
        "fail": "anything else",
    },
    "audio_sample_rate": {
        "enabled": True,
        "pass": "48000 Hz",
        "warning": "",
        "fail": "anything else",
    },
    "audio_bit_depth": {
        "enabled": True,
        "pass": "24",
        "warning": "",
        "fail": "anything else",
    },
    "stereo_only": {
        "enabled": True,
        "pass": "1 stream, 2 channels",
        "warning": "",
        "fail": "anything else",
    },
    "audio_language": {
        "enabled": False,
        "pass": "",
        "warning": "",
        "fail": "",
    },
    "loudness": {
        "enabled": False,
        "pass": "",
        "warning": "",
        "fail": "",
    },
    "true_peak": {
        "enabled": False,
        "pass": "",
        "warning": "",
        "fail": "",
    },
    "timecode_start": {
        "enabled": True,
        "pass": "00:00:00:00, 00;00;00;00",
        "warning": "",
        "fail": "anything else",
    },
}

LEGACY_LITE_CHECK_PROFILE = json.loads(json.dumps(STRICT_TE_CHECK_PROFILE))
LEGACY_LITE_CHECK_PROFILE["file_type"]["warning"] = "mp4"
LEGACY_LITE_CHECK_PROFILE["resolution"]["warning"] = "720x480"
LEGACY_LITE_CHECK_PROFILE["audio_bitrate"]["warning"] = "anything else"
LEGACY_LITE_CHECK_PROFILE["audio_bitrate"]["fail"] = ""
LEGACY_LITE_CHECK_PROFILE["audio_sample_rate"]["warning"] = "anything else"
LEGACY_LITE_CHECK_PROFILE["audio_sample_rate"]["fail"] = ""
LEGACY_LITE_CHECK_PROFILE["audio_bit_depth"]["warning"] = "anything else"
LEGACY_LITE_CHECK_PROFILE["audio_bit_depth"]["fail"] = ""

DEFAULT_CHECK_PROFILE = OFFICIAL_VOD_CHECK_PROFILE


def builtin_check_profiles() -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Return fresh copies of the shipped QC profiles."""
    return {
        OFFICIAL_VOD_PROFILE_NAME: json.loads(json.dumps(OFFICIAL_VOD_CHECK_PROFILE)),
        STRICT_PROFILE_NAME: json.loads(json.dumps(STRICT_TE_CHECK_PROFILE)),
        LEGACY_LITE_PROFILE_NAME: json.loads(json.dumps(LEGACY_LITE_CHECK_PROFILE)),
    }


def default_check_profile(profile_name: str = OFFICIAL_VOD_PROFILE_NAME) -> Dict[str, Dict[str, Any]]:
    """Return a fresh copy of a shipped check profile."""
    return json.loads(json.dumps(builtin_check_profiles().get(profile_name, OFFICIAL_VOD_CHECK_PROFILE)))


def normalize_check_profile(
    profile: Optional[Dict[str, Any]] = None,
    base_profile: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Dict[str, Any]]:
    normalized = json.loads(json.dumps(base_profile or DEFAULT_CHECK_PROFILE))
    if not isinstance(profile, dict):
        return normalized
    valid_ids = {check_id for check_id, _, _ in CHECK_DEFS}
    for check_id, values in profile.items():
        if check_id not in valid_ids or not isinstance(values, dict):
            continue
        rule = normalized[check_id]
        if "enabled" in values:
            rule["enabled"] = bool(values.get("enabled"))
        for key in ("pass", "warning", "fail"):
            if key in values:
                rule[key] = str(values.get(key) or "").strip()
    return normalized


def normalize_check_profile_library(
    profiles: Optional[Dict[str, Any]] = None,
    legacy_profile: Optional[Dict[str, Any]] = None,
    defaults_version: Optional[str] = None,
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    normalized = builtin_check_profiles()
    migrate_saved_official_profile = str(defaults_version or "").strip() != CHECK_PROFILE_DEFAULTS_VERSION
    if isinstance(profiles, dict):
        for name, profile in profiles.items():
            clean_name = str(name or "").strip()
            if not clean_name or not isinstance(profile, dict):
                continue
            base = normalized.get(clean_name, DEFAULT_CHECK_PROFILE)
            normalized[clean_name] = normalize_check_profile(profile, base)
            if clean_name == OFFICIAL_VOD_PROFILE_NAME and migrate_saved_official_profile:
                for check_id in OFFICIAL_VOD_DISABLED_BY_DEFAULT_CHECKS:
                    normalized[clean_name][check_id]["enabled"] = False
    if isinstance(legacy_profile, dict):
        normalized.setdefault(LEGACY_CUSTOM_PROFILE_NAME, normalize_check_profile(legacy_profile))
    return normalized


def active_check_profile_name(name: Any, profiles: Dict[str, Any]) -> str:
    clean = str(name or "").strip()
    if clean in profiles:
        return clean
    return OFFICIAL_VOD_PROFILE_NAME if OFFICIAL_VOD_PROFILE_NAME in profiles else next(iter(profiles))


def rule_target(rule: Dict[str, Any]) -> str:
    pass_value = str(rule.get("pass") or "").strip() or "-"
    warning_value = str(rule.get("warning") or "").strip() or "-"
    fail_value = str(rule.get("fail") or "").strip() or "-"
    return f"Pass: {pass_value}; Warning: {warning_value}; Fail: {fail_value}"

ProgressCallback = Optional[Callable[[str], None]]
ControlCallback = Optional[Callable[[], bool]]


class ScanStopped(RuntimeError):
    """Raised when a desktop user stops an active scan."""


@dataclass
class CheckResult:
    check_id: str
    label: str
    status: str
    value: str
    target: str
    note: str = ""


@dataclass
class ScanRow:
    verdict: str
    asset_title: str
    asset_id: str
    iconik_url: str
    file_name: str
    s3_uri: str
    upload_date: str
    file_size: str
    checks: List[CheckResult]


@dataclass
class S3InventoryObject:
    bucket: str
    key: str
    size_bytes: int
    last_modified: str

    @property
    def uri(self) -> str:
        return f"s3://{self.bucket}/{self.key}"

    @property
    def file_name(self) -> str:
        return posixpath.basename(self.key)


class IconikClient:
    def __init__(self, app_id: str, auth_token: str, host: str = "https://app.iconik.io", timeout: int = 45) -> None:
        self.host = host.rstrip("/")
        self.app_id = app_id.strip()
        self.auth_token = auth_token.strip()
        self.timeout = timeout
        self._formats_cache: Dict[str, List[Dict[str, Any]]] = {}

    def request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        url = path if path.startswith("http") else f"{self.host}{path}"
        data = None
        headers = {
            "App-ID": self.app_id,
            "Auth-Token": self.auth_token,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read()
                if not raw:
                    return {}
                return json.loads(raw.decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 500, 502, 503, 504) and attempt < 3:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                body = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"Iconik API error {exc.code} for {url}: {body[:400]}") from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt < 3:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise RuntimeError(f"Could not reach Iconik API at {url}: {exc}") from exc
        return {}

    def get(self, path: str) -> Any:
        return self.request("GET", path)

    def post(self, path: str, payload: Dict[str, Any]) -> Any:
        return self.request("POST", path, payload)

    def paged_get(self, path: str) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        next_path: Optional[str] = path
        while next_path:
            data = self.get(next_path)
            items.extend(objects_from(data))
            next_url = data.get("next_url") if isinstance(data, dict) else None
            next_path = normalize_next_url(next_url, path)
        return items

    def get_asset(self, asset_id: str) -> Dict[str, Any]:
        data = self.get(f"/API/assets/v1/assets/{quote(asset_id)}/")
        return data if isinstance(data, dict) else {}

    def list_files(self, asset_id: str) -> List[Dict[str, Any]]:
        return self.paged_get(f"/API/files/v1/assets/{quote(asset_id)}/files/?page=1&per_page=100")

    def list_formats(self, asset_id: str) -> List[Dict[str, Any]]:
        if asset_id not in self._formats_cache:
            self._formats_cache[asset_id] = self.paged_get(f"/API/files/v1/assets/{quote(asset_id)}/formats/?page=1&per_page=100")
        return self._formats_cache[asset_id]

    def collection_contents(self, collection_id: str) -> List[Dict[str, Any]]:
        return self.paged_get(f"/API/assets/v1/collections/{quote(collection_id)}/contents/?page=1&per_page=100")

    def search(self, query: str, page: int = 1, per_page: int = 100) -> Dict[str, Any]:
        payload = {
            "query": query,
            "doc_types": ["assets"],
            "page": page,
            "per_page": per_page,
        }
        data = self.post("/API/search/v1/search/", payload)
        return data if isinstance(data, dict) else {}


def quote(value: str) -> str:
    return urllib.parse.quote(value, safe="")


def objects_from(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if not isinstance(data, dict):
        return []
    for key in ("objects", "results", "items", "data"):
        value = data.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
    return []


def normalize_next_url(next_url: Any, fallback_path: str) -> Optional[str]:
    if not isinstance(next_url, str) or not next_url.strip():
        return None
    value = next_url.strip()
    if value.startswith("http"):
        parsed = urllib.parse.urlparse(value)
        return urllib.parse.urlunparse(("", "", parsed.path, "", parsed.query, ""))
    if value.startswith("/"):
        return value
    return posixpath.dirname(fallback_path.split("?")[0]).rstrip("/") + "/" + value


def parse_target(value: str) -> Tuple[str, str]:
    raw = value.strip()
    if S3_RE.match(raw):
        match = S3_RE.match(raw)
        bucket = match.group(1) if match else ""
        key = (match.group(2) or "").strip("/") if match else ""
        return "s3", f"s3://{bucket}/{key}" if key else f"s3://{bucket}/"
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme in ("http", "https"):
        if "/collection/" in parsed.path or "/collections/" in parsed.path:
            match = ANY_UUID_RE.search(parsed.path)
            if match:
                return "collection", match.group(1)
        if "/asset/" in parsed.path or "/assets/" in parsed.path:
            match = ANY_UUID_RE.search(parsed.path)
            if match:
                return "asset", match.group(1)
        raise ValueError("Expected an Iconik collection/asset link or an s3:// URI.")
    if UUID_RE.match(raw):
        return "asset", raw
    raise ValueError("Expected an Iconik collection/asset link or an s3:// URI.")


def scan_target(
    client: IconikClient,
    target: str,
    limit: int = 0,
    progress: ProgressCallback = None,
    control: ControlCallback = None,
    check_profile: Optional[Dict[str, Any]] = None,
) -> List[ScanRow]:
    profile = normalize_check_profile(check_profile)
    target_type, target_id = parse_target(target)
    if target_type == "collection":
        report_progress(progress, "Listing Iconik collection contents...")
        asset_ids = collection_asset_ids(client, target_id)
    elif target_type == "asset":
        asset_ids = [target_id]
    else:
        report_progress(progress, "Building S3 inventory...")
        inventory = list_s3_inventory_if_available(target_id)
        if inventory:
            report_progress(progress, f"Found {len(inventory)} S3 object(s). Matching videos to Iconik metadata...")
            return scan_s3_inventory(client, inventory, limit=limit, progress=progress, control=control, check_profile=profile)
        asset_ids = s3_asset_ids(client, target_id)

    rows: List[ScanRow] = []
    seen_files = set()
    total_assets = len(asset_ids)
    for asset_index, asset_id in enumerate(asset_ids, start=1):
        check_control(control)
        asset = client.get_asset(asset_id)
        title = str(asset.get("title") or asset.get("name") or asset_id)
        report_progress(progress, f"Scanning asset {asset_index}/{total_assets}: {title}")
        for fobj in client.list_files(asset_id):
            file_name = str(fobj.get("filename") or fobj.get("name") or fobj.get("original_name") or "")
            if not is_video_file(file_name):
                continue
            fobj = enrich_file_with_format_metadata(client, asset_id, fobj)
            s3_uri = best_s3_uri(fobj)
            file_key = (asset_id, str(fobj.get("id") or fobj.get("file_id") or file_name), s3_uri)
            if file_key in seen_files:
                continue
            seen_files.add(file_key)
            checks = evaluate_record(asset, fobj, profile)
            verdict = verdict_from_checks(checks)
            rows.append(
                ScanRow(
                    verdict=verdict,
                    asset_title=title,
                    asset_id=asset_id,
                    iconik_url=f"{client.host}/asset/{asset_id}",
                    file_name=file_name,
                    s3_uri=s3_uri,
                    upload_date=first_present(fobj, asset, ["date_created", "created_at", "created", "upload_date", "date_imported"]),
                    file_size=human_size(first_present(fobj, asset, ["size", "file_size"])),
                    checks=checks,
                )
            )
            if limit and len(rows) >= limit:
                return rows
    return rows


def scan_s3_inventory(
    client: IconikClient,
    inventory: Sequence[S3InventoryObject],
    limit: int = 0,
    progress: ProgressCallback = None,
    control: ControlCallback = None,
    check_profile: Optional[Dict[str, Any]] = None,
) -> List[ScanRow]:
    profile = normalize_check_profile(check_profile)
    rows: List[ScanRow] = []
    video_items = [item for item in inventory if is_video_file(item.file_name)]
    total = len(video_items)
    for index, item in enumerate(video_items, start=1):
        check_control(control)
        report_progress(progress, f"Checking video {index}/{total}: {item.file_name}")
        match = find_iconik_asset_for_s3_object(client, item)
        if not match:
            rows.append(unmatched_s3_row(item, profile))
        else:
            asset_id, asset, fobj = match
            title = str(asset.get("title") or asset.get("name") or asset_id)
            fobj = enrich_file_with_format_metadata(client, asset_id, fobj)
            checks = evaluate_record(asset, fobj, profile)
            rows.append(
                ScanRow(
                    verdict=verdict_from_checks(checks),
                    asset_title=title,
                    asset_id=asset_id,
                    iconik_url=f"{client.host}/asset/{asset_id}",
                    file_name=str(fobj.get("filename") or fobj.get("name") or item.file_name),
                    s3_uri=item.uri,
                    upload_date=item.last_modified or first_present(fobj, asset, ["date_created", "created_at", "created", "upload_date", "date_imported"]),
                    file_size=human_size(item.size_bytes or first_present(fobj, asset, ["size", "file_size"])),
                    checks=checks,
                )
            )
        if limit and len(rows) >= limit:
            break
    return rows


def report_progress(progress: ProgressCallback, message: str) -> None:
    if progress:
        progress(message)


def check_control(control: ControlCallback) -> None:
    if control and not control():
        raise ScanStopped("Scan stopped by user.")


def list_s3_inventory_if_available(s3_uri: str) -> List[S3InventoryObject]:
    try:
        return list_s3_inventory(s3_uri)
    except Exception as error:  # pylint: disable=broad-except
        print(f"S3 inventory unavailable, falling back to Iconik search: {error}", file=sys.stderr)
        return []


def list_s3_inventory(s3_uri: str) -> List[S3InventoryObject]:
    match = S3_RE.match(s3_uri)
    if not match:
        raise ValueError("Invalid S3 URI.")
    try:
        import boto3  # type: ignore
        from botocore.config import Config as BotoConfig  # type: ignore
        from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError  # type: ignore
    except ImportError as error:
        raise RuntimeError("boto3 is required for direct S3 inventory. Install boto3 or use Iconik collection/link mode.") from error

    bucket = match.group(1)
    raw_key = match.group(2) or ""
    key_has_trailing_slash = raw_key.endswith("/")
    prefix = raw_key.strip("/")
    looks_like_file = bool(os.path.splitext(prefix)[1])
    if prefix and (key_has_trailing_slash or not looks_like_file):
        prefix = prefix.rstrip("/") + "/"

    s3_client = boto3.session.Session().client(
        "s3",
        config=BotoConfig(max_pool_connections=32, retries={"mode": "standard", "max_attempts": 6}),
    )
    objects: List[S3InventoryObject] = []
    continuation_token: Optional[str] = None
    while True:
        request: Dict[str, Any] = {"Bucket": bucket, "Prefix": prefix, "MaxKeys": 1000}
        if continuation_token:
            request["ContinuationToken"] = continuation_token
        try:
            response = s3_client.list_objects_v2(**request)
        except (BotoCoreError, ClientError, NoCredentialsError) as error:
            raise RuntimeError(f"Unable to list {s3_uri}. Confirm AWS credentials and ListBucket permission.") from error
        for entry in response.get("Contents", []):
            key = str(entry.get("Key") or "").strip()
            if not key or key.endswith("/"):
                continue
            last_modified_value = entry.get("LastModified")
            last_modified = last_modified_value.isoformat() if hasattr(last_modified_value, "isoformat") else str(last_modified_value or "")
            objects.append(
                S3InventoryObject(
                    bucket=bucket,
                    key=key,
                    size_bytes=int(entry.get("Size", 0) or 0),
                    last_modified=last_modified,
                )
            )
        if not response.get("IsTruncated"):
            break
        continuation_token = response.get("NextContinuationToken")
    return objects


def find_iconik_asset_for_s3_object(client: IconikClient, item: S3InventoryObject) -> Optional[Tuple[str, Dict[str, Any], Dict[str, Any]]]:
    query_candidates = [
        f'files.path:"{item.key}"',
        f'"{item.uri}"',
        f'files.name:"{item.file_name}"',
    ]
    for query in query_candidates:
        data = client.search(query, page=1, per_page=25)
        for obj in objects_from(data):
            asset_id = str(obj.get("id") or obj.get("asset_id") or obj.get("object_id") or "")
            if not UUID_RE.match(asset_id):
                continue
            asset = client.get_asset(asset_id)
            files = client.list_files(asset_id)
            fobj = choose_matching_file(files, item) or (files[0] if files else {})
            if fobj:
                return asset_id, asset, fobj
    return None


def choose_matching_file(files: Sequence[Dict[str, Any]], item: S3InventoryObject) -> Optional[Dict[str, Any]]:
    for fobj in files:
        uri = best_s3_uri(fobj)
        file_name = str(fobj.get("filename") or fobj.get("name") or fobj.get("original_name") or "")
        if uri == item.uri or uri.endswith("/" + item.key) or file_name == item.file_name:
            return dict(fobj)
    return None


def enrich_file_with_format_metadata(client: IconikClient, asset_id: str, fobj: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(fobj)
    try:
        formats = client.list_formats(asset_id)
    except Exception:
        return enriched
    if not formats:
        return enriched

    format_id = str(enriched.get("format_id") or "").strip()
    chosen: Optional[Dict[str, Any]] = None
    if format_id:
        for fmt in formats:
            if str(fmt.get("id") or "") == format_id:
                chosen = fmt
                break
    if chosen is None:
        for fmt in formats:
            if str(fmt.get("name") or "").upper() == "ORIGINAL":
                chosen = fmt
                break
    if chosen is None:
        chosen = formats[0]

    enriched.setdefault("format", chosen)
    if chosen.get("metadata") not in (None, ""):
        enriched.setdefault("format_metadata", chosen.get("metadata"))
    if chosen.get("components") not in (None, ""):
        enriched.setdefault("format_components", chosen.get("components"))
    return enriched


def unmatched_s3_row(item: S3InventoryObject, check_profile: Optional[Dict[str, Any]] = None) -> ScanRow:
    profile = normalize_check_profile(check_profile)
    checks = []
    for check_id, label, _target in CHECK_DEFS:
        rule = profile[check_id]
        target = rule_target(rule)
        if not rule.get("enabled", True):
            checks.append(ignored_result(check_id, label, target))
        else:
            checks.append(
                CheckResult(
                    check_id,
                    label,
                    "missing",
                    "Iconik metadata not found",
                    target,
                    "No matching Iconik asset/file metadata was found for this S3 object.",
                )
            )
    return ScanRow(
        verdict=verdict_from_checks(checks),
        asset_title="",
        asset_id="",
        iconik_url="",
        file_name=item.file_name,
        s3_uri=item.uri,
        upload_date=item.last_modified,
        file_size=human_size(item.size_bytes),
        checks=checks,
    )


def collection_asset_ids(client: IconikClient, collection_id: str) -> List[str]:
    ids: List[str] = []
    queue = [collection_id]
    seen_collections = set()
    while queue:
        cid = queue.pop(0)
        if cid in seen_collections:
            continue
        seen_collections.add(cid)
        for obj in client.collection_contents(cid):
            obj_type = str(obj.get("object_type") or obj.get("type") or obj.get("doc_type") or "").lower()
            obj_id = str(obj.get("id") or obj.get("object_id") or obj.get("asset_id") or "")
            if not UUID_RE.match(obj_id):
                continue
            if "collection" in obj_type:
                queue.append(obj_id)
            elif obj_id not in ids:
                ids.append(obj_id)
    return ids


def s3_asset_ids(client: IconikClient, s3_prefix: str) -> List[str]:
    match = S3_RE.match(s3_prefix)
    if not match:
        raise ValueError("Invalid S3 URI.")
    bucket = match.group(1)
    key_prefix = (match.group(2) or "").strip("/")
    candidates = [
        f'files.path:"{key_prefix}"' if key_prefix else f'"{bucket}"',
        f'"{s3_prefix.rstrip("/")}"',
        f'"{bucket}/{key_prefix}"' if key_prefix else f'"{bucket}"',
    ]
    ids: List[str] = []
    for query in candidates:
        page = 1
        while True:
            data = client.search(query, page=page, per_page=100)
            objects = objects_from(data)
            for obj in objects:
                aid = str(obj.get("id") or obj.get("asset_id") or obj.get("object_id") or "")
                if UUID_RE.match(aid) and aid not in ids:
                    ids.append(aid)
            total = int_or_zero(data.get("total") if isinstance(data, dict) else 0)
            if not objects or len(ids) >= total or page >= 100:
                break
            page += 1
        if ids:
            break
    return ids


def is_video_file(file_name: str) -> bool:
    return os.path.splitext(file_name.split("?")[0])[1].lower() in VIDEO_EXTENSIONS


def best_s3_uri(fobj: Dict[str, Any]) -> str:
    for key in ("s3_uri", "file_path", "filepath", "path", "absolute_path", "url"):
        value = fobj.get(key)
        if isinstance(value, str) and value.strip():
            text = value.strip()
            if text.startswith("s3://"):
                return text
            if text.startswith("http"):
                converted = presigned_to_s3(text)
                if converted.startswith("s3://"):
                    return converted
            return text
    directory = str(fobj.get("directory_path") or fobj.get("directory") or "").strip("/")
    name = str(fobj.get("filename") or fobj.get("name") or "").strip("/")
    storage = str(fobj.get("storage_name") or fobj.get("storage_method") or "").strip("/")
    return "/".join(part for part in (storage, directory, name) if part)


def presigned_to_s3(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc
    path = parsed.path.lstrip("/")
    match = re.match(r"^([^.]+)\.s3[.-][^.]+\.amazonaws\.com$", host)
    if match:
        return f"s3://{match.group(1)}/{path}"
    if re.match(r"^s3[.-][^.]+\.amazonaws\.com$", host) and "/" in path:
        bucket, key = path.split("/", 1)
        return f"s3://{bucket}/{key}"
    return url


def evaluate_record(asset: Dict[str, Any], fobj: Dict[str, Any], check_profile: Optional[Dict[str, Any]] = None) -> List[CheckResult]:
    meta = flatten_metadata(asset, fobj)
    profile = normalize_check_profile(check_profile)
    return [evaluate_check(check_id, label, rule_target(profile[check_id]), meta, profile[check_id]) for check_id, label, _target in CHECK_DEFS]


def flatten_metadata(asset: Dict[str, Any], fobj: Dict[str, Any]) -> Dict[str, Any]:
    flat: Dict[str, Any] = {}

    def set_value(key: str, value: Any) -> None:
        if value in (None, ""):
            return
        normalized = normalize_key(key)
        flat[normalized] = value
        short = normalized.split(".")[-1]
        flat.setdefault(short, value)

    def visit(prefix: str, value: Any) -> None:
        if isinstance(value, dict):
            for k, v in value.items():
                key = normalize_key(k)
                visit(f"{prefix}.{key}" if prefix else key, v)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(f"{prefix}.{index}", item)
        elif value not in (None, ""):
            set_value(prefix, value)

    def visit_components(value: Any) -> None:
        if not isinstance(value, list):
            return
        for component in value:
            if not isinstance(component, dict):
                continue
            ctype = lower(component.get("type") or component.get("name") or "")
            if "video" in ctype:
                section = "video"
            elif "audio" in ctype:
                section = "audio"
            elif "general" in ctype:
                section = "general"
            elif "text" in ctype:
                section = "text"
            else:
                section = ctype or "component"
            metadata = component.get("metadata")
            if isinstance(metadata, dict):
                visit(section, metadata)

    visit("asset", asset)
    visit("file", fobj)
    technical = fobj.get("technical_metadata") or fobj.get("metadata") or asset.get("technical_metadata") or asset.get("metadata") or {}
    visit("", technical)
    visit("format", fobj.get("format") or {})
    visit("format metadata", fobj.get("format_metadata") or {})
    visit_components(fobj.get("format_components"))
    if isinstance(fobj.get("format"), dict):
        visit_components(fobj["format"].get("components"))
    file_name = str(fobj.get("filename") or fobj.get("name") or fobj.get("original_name") or "")
    if file_name:
        flat.setdefault("file name", file_name)
        flat.setdefault("file extension", os.path.splitext(file_name.split("?")[0])[1].lstrip("."))
    add_flattened_aliases(flat)
    return flat


def add_flattened_aliases(flat: Dict[str, Any]) -> None:
    alias_groups = {
        "container format": ["general.format", "format"],
        "video framerate": ["video.frame rate", "frame rate"],
        "video.framerate": ["video.frame rate", "frame rate", "video framerate"],
        "framerate": ["video.frame rate", "frame rate", "video framerate"],
        "video scan type": ["video.scan type", "scan type"],
        "video.scan": ["video.scan type", "scan type"],
        "video chroma subsampling": ["video.chroma subsampling", "chroma subsampling"],
        "video.chroma": ["video.chroma subsampling", "chroma subsampling"],
        "video codec": ["video.codec", "video.format", "codec"],
        "video bitrate": ["video.bit rate", "bit rate"],
        "video.bitrate": ["video.bit rate", "bit rate", "video bitrate"],
        "pixel aspect ratio": ["video.pixel aspect ratio", "sample aspect ratio"],
        "video pixel aspect ratio": ["video.pixel aspect ratio", "sample aspect ratio"],
        "sample aspect ratio": ["video.pixel aspect ratio", "pixel aspect ratio"],
        "color primaries": ["video.color primaries", "color primaries"],
        "video color primaries": ["video.color primaries", "color primaries"],
        "colour primaries": ["video.color primaries", "color primaries"],
        "matrix coefficients": ["video.matrix coefficients", "matrix coefficients"],
        "video matrix coefficients": ["video.matrix coefficients", "matrix coefficients"],
        "transfer characteristics": ["video.transfer characteristics", "transfer characteristics"],
        "video transfer characteristics": ["video.transfer characteristics", "transfer characteristics"],
        "color space": ["video.color space", "color space"],
        "colour space": ["video.color space", "color space"],
        "audio codec": ["audio.format", "audio codec"],
        "audio channels": ["audio.channel s", "audio.channels", "channels"],
        "audio bit depth": ["audio.bit depth", "bit depth"],
        "audio bit rate": ["audio.bit rate", "audio bitrate"],
        "audio.bitrate": ["audio.bit rate", "audio bitrate"],
        "audio sample rate": ["audio.sampling rate", "sampling rate"],
        "audio.sample rate": ["audio.sampling rate", "sampling rate", "audio sample rate"],
        "audio language": ["audio.language", "language"],
        "language": ["audio.language"],
        "loudness": ["audio.loudness", "integrated loudness"],
        "integrated loudness": ["audio.loudness", "loudness"],
        "audio integrated loudness": ["audio.loudness", "integrated loudness"],
        "true peak": ["audio.true peak", "true peak"],
        "audio true peak": ["audio.true peak", "true peak"],
    }
    for source_key, destinations in alias_groups.items():
        value = flat.get(source_key)
        if value in (None, ""):
            continue
        for dest in destinations:
            flat.setdefault(normalize_key(dest), value)

    resolution = flat.get("video resolution") or flat.get("resolution")
    if resolution not in (None, ""):
        parsed = parse_resolution(str(resolution))
        if parsed:
            width, height = parsed
            flat.setdefault("video.width", str(width))
            flat.setdefault("video.height", str(height))
            flat.setdefault("width", str(width))
            flat.setdefault("height", str(height))


def criteria_parts(criteria: Any) -> List[str]:
    return [part.strip() for part in re.split(r"[,|]+", str(criteria or "")) if part.strip()]


def criteria_is_anything_else(criteria: Any) -> bool:
    text = lower(str(criteria or ""))
    return text in {"anything else", "outside pass", "outside pass values", "out of spec", "otherwise", "any other value"}


def matches_exact_text(value: str, criteria: Any) -> bool:
    clean = lower(value).lstrip(".")
    return any(clean == lower(part).lstrip(".") for part in criteria_parts(criteria))


def matches_contains_text(value: str, criteria: Any) -> bool:
    text = lower(value)
    return any(lower(part) in text for part in criteria_parts(criteria))


def contains_hdr_color_signal(value: str) -> bool:
    text = lower(value)
    return any(signal in text for signal in ("bt.2020", "bt2020", "2020", "pq", "smpte st 2084", "hlg", "hdr"))


def matches_resolution(width: Optional[int], height: Optional[int], criteria: Any) -> bool:
    if width is None or height is None:
        return False
    for part in criteria_parts(criteria):
        text = lower(part)
        if "sd" in text and "480p" in text:
            if min(width, height) >= 480 and max(width, height) <= 1024:
                return True
        if text in {">= 480p", "min 480p"} and min(width, height) >= 480:
            return True
        parsed = parse_resolution(part)
        if parsed and parsed == (width, height):
            return True
    return False


def matches_frame_rate(rounded: Optional[str], criteria: Any) -> bool:
    if rounded is None:
        return False
    for part in criteria_parts(criteria):
        value = parse_frame_rate(part)
        if value is not None and round_frame_rate(value) == rounded:
            return True
    return False


def matches_numeric(value: Optional[int], criteria: Any) -> bool:
    if value is None:
        return False
    for part in criteria_parts(criteria):
        text = part.strip()
        threshold = parse_number(text)
        if threshold is None:
            continue
        if text.startswith(">=") and value >= threshold:
            return True
        if text.startswith(">") and value > threshold:
            return True
        if text.startswith("<=") and value <= threshold:
            return True
        if text.startswith("<") and value < threshold:
            return True
        range_match = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*(?:-|to)\s*(-?\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
        if range_match:
            low = parse_number(range_match.group(1))
            high = parse_number(range_match.group(2))
            if low is not None and high is not None and low <= value <= high:
                return True
        elif value == threshold:
            return True
    return False


def format_measurement(value: float, unit: str) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{text} {unit}"


def matches_ratio(value: Optional[float], raw: str, criteria: Any) -> bool:
    if value is None and not raw:
        return False
    for part in criteria_parts(criteria):
        text = part.strip()
        ratio = parse_ratio(text)
        if ":" in text and raw.strip() == text:
            return True
        range_match = re.match(r"^\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*$", text)
        if range_match and value is not None:
            low = float(range_match.group(1))
            high = float(range_match.group(2))
            if low <= value <= high:
                return True
        elif ratio is not None and value is not None and abs(value - ratio) <= 0.005:
            return True
    return False


def matches_audio_bitrate(bitrate: Optional[int], channels: Optional[int], criteria: Any) -> bool:
    if bitrate is None:
        return False
    for part in criteria_parts(criteria):
        expected = parse_number(part)
        if expected is None:
            continue
        if "channel" in lower(part):
            if channels is not None and bitrate == channels * expected:
                return True
        elif matches_numeric(bitrate, part):
            return True
    return False


def matches_stereo(streams: Optional[int], channels: Optional[int], criteria: Any) -> bool:
    if channels is None:
        return False
    text = lower(str(criteria or ""))
    numbers = [int(value) for value in re.findall(r"\d+", text)]
    expected_streams = numbers[0] if "stream" in text and numbers else None
    expected_channels = numbers[-1] if numbers else 2
    stream_ok = expected_streams is None or streams in (None, expected_streams)
    return stream_ok and channels == expected_channels


def is_sd_resolution(width: Optional[int], height: Optional[int]) -> bool:
    return bool(width and height and min(width, height) >= 480 and max(width, height) <= 1024)


def is_hd_resolution(width: Optional[int], height: Optional[int]) -> bool:
    return bool(width == 1920 and height == 1080)


def matches_vod_aspect(
    ratio: Optional[float],
    raw: str,
    width: Optional[int],
    height: Optional[int],
    criteria: Any,
) -> bool:
    text = lower(criteria)
    if "hd" not in text or "sd" not in text:
        return False
    if is_hd_resolution(width, height):
        return matches_ratio(ratio, raw, "16:9, 1.76-1.79")
    if is_sd_resolution(width, height):
        return matches_ratio(ratio, raw, "4:3, 1.32-1.34")
    return matches_ratio(ratio, raw, "16:9, 1.76-1.79, 4:3, 1.32-1.34")


def language_values(value: str) -> List[str]:
    ignored = {"", "und", "undefined", "unknown", "n/a", "none", "not reported"}
    values = []
    for part in re.split(r"[,|;/]+", str(value or "")):
        clean = part.strip().lower()
        if clean and clean not in ignored:
            values.append(clean)
    return sorted(set(values))


def matches_language_count(value: str, criteria: Any) -> bool:
    languages = language_values(value)
    expected_numbers = [int(v) for v in re.findall(r"\d+", str(criteria or ""))]
    expected = expected_numbers[0] if expected_numbers else 1
    return len(languages) == expected


def warning_or_fail(
    check_id: str,
    label: str,
    target: str,
    value: str,
    rule: Dict[str, Any],
    warning_match: bool,
    note: str,
) -> CheckResult:
    if warning_match or criteria_is_anything_else(rule.get("warning")):
        return result(check_id, label, target, "warning", value, note)
    return result(check_id, label, target, "fail", value, note)


def evaluate_check(check_id: str, label: str, target: str, m: Dict[str, Any], rule: Optional[Dict[str, Any]] = None) -> CheckResult:
    rule = rule or normalize_check_profile().get(check_id, {})
    if not rule.get("enabled", True):
        return ignored_result(check_id, label, target)
    if check_id == "file_type":
        ext = clean_ext(first(m, ["general.file extension", "file.file extension", "file extension", "extension"]))
        if not ext:
            return missing_result(check_id, label, target, "File extension was not available.")
        if matches_exact_text(ext, rule.get("pass")):
            return result(check_id, label, target, "pass", ext)
        if matches_exact_text(ext, rule.get("warning")) or criteria_is_anything_else(rule.get("warning")):
            return result(check_id, label, target, "warning", ext, "MP4 is accepted as a warning for SVOD review.")
        return result(check_id, label, target, "fail", ext, "Expected .mov file extension. MP4 is a warning.")
    if check_id == "video_codec":
        codec = lower(first(m, ["video.codec id", "codec id", "codec_tag_string", "video.codec_tag_string", "video codec"]))
        fmt = first(m, ["video.codec", "video codec", "video.format", "codec_name", "video.codec_name", "video.commercial name", "codec", "format"])
        profile = first(m, ["video.format profile", "profile", "format profile"])
        if not codec and not fmt:
            return missing_result(check_id, label, target, "Video codec was not available.")
        display = " ".join(x for x in [fmt or codec or "missing", profile, f"({codec})" if codec else ""] if x)
        match_text = " ".join(x for x in [codec, fmt, profile] if x)
        if matches_contains_text(match_text, rule.get("pass")):
            return result(check_id, label, target, "pass", display)
        return warning_or_fail(
            check_id,
            label,
            target,
            display,
            rule,
            matches_contains_text(match_text, rule.get("warning")),
            "Expected ProRes 422 HQ codec tag apch.",
        )
    if check_id == "video_bitrate":
        value = parse_number(first(m, ["video.bit rate", "video.bit_rate", "bit_rate", "overall bit rate"]))
        if value is None:
            return missing_result(check_id, label, target, "Video bit rate was not available.")
        if matches_numeric(value, rule.get("pass")):
            return result(check_id, label, target, "pass", format_mbps(value))
        return warning_or_fail(
            check_id,
            label,
            target,
            format_mbps(value),
            rule,
            matches_numeric(value, rule.get("warning")),
            "Expected at least 145 Mb/s.",
        )
    if check_id == "resolution":
        width = parse_number(first(m, ["video.width", "width"]))
        height = parse_number(first(m, ["video.height", "height"]))
        if width is None or height is None:
            parsed_resolution = parse_resolution(first(m, ["video.resolution", "resolution", "video resolution"]))
            if parsed_resolution:
                width, height = parsed_resolution
        if width is None or height is None:
            return missing_result(check_id, label, target, "Resolution was not available.")
        value = f"{width or '?'}x{height or '?'}"
        if matches_resolution(width, height, rule.get("pass")):
            return result(check_id, label, target, "pass", value)
        if matches_resolution(width, height, rule.get("warning")) or criteria_is_anything_else(rule.get("warning")):
            return result(check_id, label, target, "warning", value, "Resolution is accepted as a warning for this profile.")
        return result(check_id, label, target, "fail", value, "Expected HD 1920x1080 or SD at least 480p.")
    if check_id == "aspect_ratio":
        raw = first(m, ["video.display aspect ratio string", "video.display aspect ratio", "display_aspect_ratio", "display aspect ratio"])
        ratio = parse_ratio(raw)
        width = parse_number(first(m, ["video.width", "width"]))
        height = parse_number(first(m, ["video.height", "height"]))
        if width is None or height is None:
            parsed_resolution = parse_resolution(first(m, ["video.resolution", "resolution", "video resolution"]))
            if parsed_resolution:
                width, height = parsed_resolution
        calculated = (width / height) if width and height else None
        if not raw and calculated is None:
            return missing_result(check_id, label, target, "Aspect ratio or resolution was not available.")
        display = raw or (f"{calculated:.3f}" if calculated else "missing")
        pass_match = (
            matches_vod_aspect(ratio, raw, width, height, rule.get("pass"))
            or matches_vod_aspect(calculated, raw, width, height, rule.get("pass"))
            or matches_ratio(ratio, raw, rule.get("pass"))
            or matches_ratio(calculated, raw, rule.get("pass"))
        )
        warning_match = (
            matches_vod_aspect(ratio, raw, width, height, rule.get("warning"))
            or matches_vod_aspect(calculated, raw, width, height, rule.get("warning"))
            or matches_ratio(ratio, raw, rule.get("warning"))
            or matches_ratio(calculated, raw, rule.get("warning"))
        )
        if pass_match:
            return result(check_id, label, target, "pass", display)
        return warning_or_fail(
            check_id,
            label,
            target,
            display,
            rule,
            warning_match,
            "Expected HD 16:9 or SD 4:3.",
        )
    if check_id == "pixel_aspect_ratio":
        value = first(m, ["video.pixel aspect ratio", "pixel aspect ratio", "sample aspect ratio", "sar"])
        ratio = parse_ratio(value)
        if not value and ratio is None:
            return missing_result(check_id, label, target, "Pixel aspect ratio was not available.")
        display = value or (f"{ratio:.3f}" if ratio else "missing")
        if matches_ratio(ratio, value, rule.get("pass")):
            return result(check_id, label, target, "pass", display)
        return warning_or_fail(
            check_id,
            label,
            target,
            display,
            rule,
            matches_ratio(ratio, value, rule.get("warning")),
            "Expected square pixels / 1:1 pixel aspect ratio.",
        )
    if check_id == "frame_rate":
        fps = parse_frame_rate(first(m, ["video.r frame rate", "r_frame_rate", "video.frame rate", "frame_rate", "frame rate", "video framerate"]))
        rounded = round_frame_rate(fps) if fps is not None else None
        if matches_frame_rate(rounded, rule.get("pass")):
            return result(check_id, label, target, "pass", f"{rounded} fps")
        if rounded is None:
            return missing_result(check_id, label, target, "Frame rate was not available.")
        return warning_or_fail(
            check_id,
            label,
            target,
            f"{rounded} fps",
            rule,
            matches_frame_rate(rounded, rule.get("warning")),
            "Expected 23.98 or 29.97 fps for SVOD.",
        )
    if check_id == "chroma":
        value = first(m, ["video.chroma subsampling", "chroma subsampling", "video chroma subsampling", "pix_fmt", "pixel format"])
        if not value:
            return missing_result(check_id, label, target, "Chroma sampling was not available.")
        if matches_contains_text(value, rule.get("pass")):
            return result(check_id, label, target, "pass", value or "missing")
        return warning_or_fail(
            check_id,
            label,
            target,
            value or "missing",
            rule,
            matches_contains_text(value, rule.get("warning")),
            "Expected 4:2:2 chroma.",
        )
    if check_id == "scan_type":
        value = first(m, ["video.scan type", "scan type", "video scan type", "field_order", "field order"])
        if not value:
            return missing_result(check_id, label, target, "Scan type was not available.")
        if matches_contains_text(value, rule.get("pass")):
            return result(check_id, label, target, "pass", value or "missing")
        return warning_or_fail(
            check_id,
            label,
            target,
            value or "missing",
            rule,
            matches_contains_text(value, rule.get("warning")),
            "Expected progressive scan.",
        )
    if check_id == "color_space":
        values = [
            first(m, ["video.color space", "color space", "colour space"]),
            first(m, ["video.color primaries", "color primaries", "colour primaries"]),
            first(m, ["video.matrix coefficients", "matrix coefficients"]),
            first(m, ["video.transfer characteristics", "transfer characteristics"]),
        ]
        present = [value for value in values if value]
        display = " / ".join(dict.fromkeys(present))
        if not display:
            return missing_result(check_id, label, target, "Color space / Rec.709 metadata was not available.")
        if matches_contains_text(display, rule.get("pass")) and not contains_hdr_color_signal(display):
            return result(check_id, label, target, "pass", display)
        return warning_or_fail(
            check_id,
            label,
            target,
            display,
            rule,
            matches_contains_text(display, rule.get("warning")),
            "Expected SDR Rec.709 color metadata.",
        )
    if check_id == "audio_codec":
        value = first(m, ["audio.codec", "audio.format", "audio codec", "audio codecs", "audio codec name", "audio.codec_name"])
        if not value:
            return missing_result(check_id, label, target, "Audio codec was not available.")
        if matches_contains_text(value, rule.get("pass")):
            return result(check_id, label, target, "pass", value or "missing")
        return warning_or_fail(
            check_id,
            label,
            target,
            value or "missing",
            rule,
            matches_contains_text(value, rule.get("warning")),
            "Expected PCM audio.",
        )
    if check_id == "audio_bitrate":
        channels = parse_number(first(m, ["audio.channel s", "audio.channels", "channels", "audio channels total"]))
        bitrate = parse_number(first(m, ["audio.bit rate", "audio.bit_rate", "audio_bitrate"]))
        if channels is None or bitrate is None:
            return missing_result(check_id, label, target, "Audio channels or bit rate was not available.")
        expected = channels * 1152000 if channels is not None else None
        if matches_audio_bitrate(bitrate, channels, rule.get("pass")):
            return result(check_id, label, target, "pass", format_kbps(bitrate))
        return warning_or_fail(
            check_id,
            label,
            target,
            format_kbps(bitrate),
            rule,
            matches_audio_bitrate(bitrate, channels, rule.get("warning")),
            f"Expected {format_kbps(expected)} for {channels or '?'} channel(s).",
        )
    if check_id == "audio_sample_rate":
        value = parse_number(first(m, ["audio.sampling rate", "sample_rate", "sampling rate"]))
        if value is None:
            return missing_result(check_id, label, target, "Audio sample rate was not available.")
        display = "48 kHz" if value == 48000 else (f"{value} Hz" if value else "missing")
        if matches_numeric(value, rule.get("pass")):
            return result(check_id, label, target, "pass", display)
        return warning_or_fail(
            check_id,
            label,
            target,
            display,
            rule,
            matches_numeric(value, rule.get("warning")),
            "Expected 48000 Hz.",
        )
    if check_id == "audio_bit_depth":
        value = parse_number(first(m, ["audio.bit depth", "bits_per_sample", "bit depth"]))
        if value is None:
            return missing_result(check_id, label, target, "Audio bit depth was not available.")
        display = f"{value} bits" if value else "missing"
        if matches_numeric(value, rule.get("pass")):
            return result(check_id, label, target, "pass", display)
        return warning_or_fail(
            check_id,
            label,
            target,
            display,
            rule,
            matches_numeric(value, rule.get("warning")),
            "Expected 24-bit PCM.",
        )
    if check_id == "stereo_only":
        streams = parse_number(first(m, ["general.count of audio streams", "count of audio streams", "audio_stream_count"]))
        channels = parse_number(first(m, ["audio.channel s", "audio.channels", "channels", "audio channels total"]))
        if channels is None:
            return missing_result(check_id, label, target, "Audio channel count was not available.")
        display = f"{streams or '?'} stream, {channels or '?'} channels"
        if matches_stereo(streams, channels, rule.get("pass")):
            return result(check_id, label, target, "pass", display)
        return warning_or_fail(
            check_id,
            label,
            target,
            display,
            rule,
            matches_stereo(streams, channels, rule.get("warning")),
            "Expected one stereo audio stream.",
        )
    if check_id == "audio_language":
        value = first(m, ["audio.language", "language", "audio language", "audio.language string"])
        if not value:
            return missing_result(check_id, label, target, "Audio language metadata was not available.")
        languages = language_values(value)
        display = ", ".join(languages) if languages else value
        if matches_language_count(value, rule.get("pass")):
            return result(check_id, label, target, "pass", display)
        return warning_or_fail(
            check_id,
            label,
            target,
            display,
            rule,
            matches_language_count(value, rule.get("warning")),
            "Expected one language per video file.",
        )
    if check_id == "loudness":
        value = parse_float_number(first(m, ["audio.loudness", "loudness", "integrated loudness", "audio.integrated loudness"]))
        if value is None:
            return missing_result(check_id, label, target, "Integrated loudness metadata was not available.")
        display = format_measurement(value, "LKFS")
        if matches_numeric(value, rule.get("pass")):
            return result(check_id, label, target, "pass", display)
        return warning_or_fail(
            check_id,
            label,
            target,
            display,
            rule,
            matches_numeric(value, rule.get("warning")),
            "Expected -24 LKFS with +/- 2 tolerance.",
        )
    if check_id == "true_peak":
        value = parse_float_number(first(m, ["audio.true peak", "true peak", "true_peak", "audio.true_peak"]))
        if value is None:
            return missing_result(check_id, label, target, "True peak metadata was not available.")
        display = format_measurement(value, "dBTP")
        if matches_numeric(value, rule.get("pass")):
            return result(check_id, label, target, "pass", display)
        return warning_or_fail(
            check_id,
            label,
            target,
            display,
            rule,
            matches_numeric(value, rule.get("warning")),
            "Expected true peak at or below -2 dBTP.",
        )
    if check_id == "timecode_start":
        value = first(m, ["general.tim", "tim", "timecode", "start_timecode"])
        if not value:
            return missing_result(check_id, label, target, "Start timecode was not available.")
        if matches_exact_text(value, rule.get("pass")):
            return result(check_id, label, target, "pass", value or "missing")
        return warning_or_fail(
            check_id,
            label,
            target,
            value or "missing",
            rule,
            matches_exact_text(value, rule.get("warning")),
            "Expected SVOD start timecode at zero.",
        )
    return result(check_id, label, target, "info", "not checked")


def result(check_id: str, label: str, target: str, status: str, value: str, note: str = "") -> CheckResult:
    return CheckResult(check_id, label, status, value or "", target, "" if status == "pass" else note)


def missing_result(check_id: str, label: str, target: str, note: str) -> CheckResult:
    return result(check_id, label, target, "missing", "missing", note)


def ignored_result(check_id: str, label: str, target: str) -> CheckResult:
    return CheckResult(check_id, label, "ignored", "ignored", target, "Ignored by user settings.")


def verdict_from_checks(checks: Sequence[CheckResult]) -> str:
    if any(c.status == "fail" for c in checks):
        return "FAIL"
    if any(c.status == "missing" for c in checks):
        return "MISSING INFO"
    if any(c.status == "warning" for c in checks):
        return "WARNING"
    return "PASS"


def first(m: Dict[str, Any], keys: Sequence[str]) -> str:
    normalized = {normalize_key(k): v for k, v in m.items()}
    for key in keys:
        value = normalized.get(normalize_key(key))
        if value not in (None, ""):
            return str(value).strip()
    return ""


def first_present(primary: Dict[str, Any], secondary: Dict[str, Any], keys: Sequence[str]) -> str:
    for source in (primary, secondary):
        for key in keys:
            value = source.get(key)
            if value not in (None, ""):
                return str(value)
    return ""


def normalize_key(value: str) -> str:
    return str(value).strip().lower().replace("_", " ")


def lower(value: str) -> str:
    return str(value or "").strip().lower()


def clean_ext(value: str) -> str:
    text = str(value or "").split("?")[0].strip()
    if "." in text:
        return text.rsplit(".", 1)[-1]
    return text


def parse_number(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    text = str(value).replace(",", "").strip()
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    number = float(match.group(0))
    ltext = text.lower()
    if "mb/s" in ltext:
        number *= 1_000_000
    elif "kb/s" in ltext:
        number *= 1_000
    elif "khz" in ltext:
        number *= 1_000
    return int(round(number))


def parse_float_number(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    text = str(value).replace(",", "").strip()
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    number = float(match.group(0))
    ltext = text.lower()
    if "mb/s" in ltext:
        number *= 1_000_000
    elif "kb/s" in ltext:
        number *= 1_000
    elif "khz" in ltext:
        number *= 1_000
    return number


def parse_frame_rate(value: str) -> Optional[float]:
    text = str(value or "").strip()
    fraction = re.search(r"(\d+)\s*/\s*(\d+)", text)
    if fraction and int(fraction.group(2)):
        return int(fraction.group(1)) / int(fraction.group(2))
    match = re.search(r"\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None


def round_frame_rate(value: float) -> str:
    return f"{round(value + 1e-10, 2):.2f}"


def parse_ratio(value: str) -> Optional[float]:
    text = str(value or "").strip()
    colon = re.search(r"(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)", text)
    if colon and float(colon.group(2)):
        return float(colon.group(1)) / float(colon.group(2))
    match = re.search(r"\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None


def parse_resolution(value: str) -> Optional[Tuple[int, int]]:
    text = str(value or "").replace(" ", "").lower()
    match = re.search(r"(\d{3,5})[x×](\d{3,5})", text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def within(value: Optional[float], low: float, high: float) -> bool:
    return value is not None and low < value < high


def format_mbps(value: Optional[int]) -> str:
    return "missing" if value is None else f"{value / 1_000_000:.1f} Mb/s"


def format_kbps(value: Optional[int]) -> str:
    return "missing" if value is None else f"{round(value / 1_000):,} kb/s"


def human_size(value: Any) -> str:
    number = parse_number(value)
    if number is None:
        return ""
    units = ["B", "KB", "MB", "GB", "TB"]
    amount = float(number)
    unit = units[0]
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            break
        amount /= 1024
    return f"{amount:.2f} {unit}"


def int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def write_xlsx(rows: Sequence[ScanRow], output_path: str, target: str, profile_name: str = "") -> None:
    headers = [
        "Result",
        "Reason",
        "Asset Title",
        "Upload Date",
        "File Name",
        "S3 URI / Storage Path",
        "Iconik URL",
        "Asset ID",
    ] + [label for _, label, _ in CHECK_DEFS]

    data_rows: List[List[str]] = []
    cell_styles: List[List[str]] = []
    for row in rows:
        check_values = [f"{check.status.upper()}: {check.value}" for check in row.checks]
        reason = reason_for_row(row)
        data_rows.append([
            row.verdict,
            reason,
            row.asset_title,
            row.upload_date,
            row.file_name,
            row.s3_uri,
            row.iconik_url,
            row.asset_id,
            *check_values,
        ])
        row_style = status_style_key(row.verdict)
        check_styles = [status_style_key(check.status) if check.status in {"fail", "warning", "missing"} else "" for check in row.checks]
        cell_styles.append([row_style, row_style if reason else "", "", "", "", "", "", "", *check_styles])

    summary = [
        ["TE Tool - Iconik Lite Version", VERSION],
        ["Target", target],
        ["Check Profile", profile_name or OFFICIAL_VOD_PROFILE_NAME],
        ["Generated", dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        ["Total Videos", str(len(rows))],
        ["Pass", str(sum(1 for r in rows if r.verdict == "PASS"))],
        ["Warning", str(sum(1 for r in rows if r.verdict == "WARNING"))],
        ["Missing Info", str(sum(1 for r in rows if r.verdict == "MISSING INFO"))],
        ["Fail", str(sum(1 for r in rows if r.verdict == "FAIL"))],
    ]

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml())
        zf.writestr("_rels/.rels", root_rels_xml())
        zf.writestr("xl/workbook.xml", workbook_xml())
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml())
        zf.writestr("xl/styles.xml", styles_xml())
        zf.writestr("xl/worksheets/sheet1.xml", worksheet_xml("Summary", summary, []))
        zf.writestr("xl/worksheets/sheet2.xml", worksheet_xml("SVOD Report", [headers, *data_rows], ["header", *["" for _ in data_rows]], [[], *cell_styles]))


def reason_for_row(row: ScanRow) -> str:
    problem_checks = [check for check in row.checks if check.status in {"fail", "warning", "missing"}]
    if not problem_checks:
        return ""
    return "; ".join(f"{check.label} ({reason_status(check.status)}: {check.value})" for check in problem_checks)


def reason_status(status: str) -> str:
    normalized = status_style_key(status)
    if normalized == "missing":
        return "MISSING INFO"
    if normalized == "warning":
        return "WARNING"
    if normalized == "fail":
        return "FAIL"
    return normalized.upper()


def worksheet_xml(
    name: str,
    rows: Sequence[Sequence[str]],
    row_styles: Sequence[str],
    cell_styles: Optional[Sequence[Sequence[str]]] = None,
) -> str:
    col_widths = {1: 14, 2: 58, 3: 34, 4: 22, 5: 32, 6: 46, 7: 48, 8: 38}
    cols = "".join(f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>' for i, w in col_widths.items())
    sheet_rows = []
    for r_idx, row in enumerate(rows, start=1):
        style_name = row_styles[r_idx - 1] if r_idx - 1 < len(row_styles) else ""
        row_cell_styles = cell_styles[r_idx - 1] if cell_styles and r_idx - 1 < len(cell_styles) else []
        cells = []
        for c_idx, value in enumerate(row, start=1):
            cell_style_name = row_cell_styles[c_idx - 1] if c_idx - 1 < len(row_cell_styles) else ""
            style = style_index(cell_style_name or style_name, c_idx, bool(cell_style_name))
            cells.append(f'<c r="{cell_ref(r_idx, c_idx)}" t="inlineStr" s="{style}"><is><t>{escape(str(value or ""))}</t></is></c>')
        sheet_rows.append(f'<row r="{r_idx}">{"".join(cells)}</row>')
    auto_filter = f'<autoFilter ref="A1:{cell_ref(1, len(rows[0]))}"/>' if name == "SVOD Report" and rows else ""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<cols>{cols}</cols>"
        f'<sheetData>{"".join(sheet_rows)}</sheetData>'
        f"{auto_filter}"
        "</worksheet>"
    )


def style_index(style_name: str, c_idx: int, force: bool = False) -> int:
    if style_name == "header":
        return 1
    if force or c_idx == 1:
        return {"pass": 2, "warning": 3, "fail": 4, "missing": 5}.get(style_name, 0)
    return 0


def status_style_key(status: str) -> str:
    normalized = lower(status).replace(" ", "_")
    return "missing" if normalized in ("missing", "missing_info") else normalized


def cell_ref(row: int, col: int) -> str:
    letters = ""
    while col:
        col, rem = divmod(col - 1, 26)
        letters = chr(65 + rem) + letters
    return f"{letters}{row}"


def content_types_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""


def root_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""


def workbook_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Summary" sheetId="1" r:id="rId1"/>
    <sheet name="SVOD Report" sheetId="2" r:id="rId2"/>
  </sheets>
</workbook>"""


def workbook_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""


def styles_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2">
    <font><sz val="11"/><name val="Aptos"/></font>
    <font><b/><sz val="11"/><name val="Aptos"/></font>
  </fonts>
  <fills count="7">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF{HEADER_FILL}"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF{PASS_FILL}"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF{WARN_FILL}"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF{FAIL_FILL}"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF{MISSING_FILL}"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="6">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFill="1" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>
    <xf numFmtId="0" fontId="1" fillId="3" borderId="0" xfId="0" applyFill="1" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>
    <xf numFmtId="0" fontId="1" fillId="4" borderId="0" xfId="0" applyFill="1" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>
    <xf numFmtId="0" fontId="1" fillId="5" borderId="0" xfId="0" applyFill="1" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>
    <xf numFmtId="0" fontId="1" fillId="6" borderId="0" xfId="0" applyFill="1" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""


def run(args: argparse.Namespace) -> int:
    app_id = args.app_id or os.environ.get("ICONIK_APP_ID", "")
    auth_token = args.auth_token or os.environ.get("ICONIK_AUTH_TOKEN", "")
    if not app_id or not auth_token:
        raise SystemExit("Iconik credentials required. Use --app-id/--auth-token or ICONIK_APP_ID/ICONIK_AUTH_TOKEN.")
    client = IconikClient(app_id=app_id, auth_token=auth_token, host=args.host)
    rows = scan_target(client, args.target, limit=args.limit)
    write_xlsx(rows, args.output, args.target)
    print(f"Wrote {len(rows)} video row(s) to {args.output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan an Iconik collection or S3 prefix and export a TE Tool Iconik Lite XLSX report.")
    parser.add_argument("target", help="Iconik collection/asset URL, asset UUID, or s3://bucket/prefix/")
    parser.add_argument("-o", "--output", default="te_iconik_lite_report.xlsx", help="Output XLSX path.")
    parser.add_argument("--host", default="https://app.iconik.io", help="Iconik host.")
    parser.add_argument("--app-id", help="Iconik App-ID. Can also use ICONIK_APP_ID.")
    parser.add_argument("--auth-token", help="Iconik Auth-Token. Can also use ICONIK_AUTH_TOKEN.")
    parser.add_argument("--limit", type=int, default=0, help="Optional max video rows for testing.")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
