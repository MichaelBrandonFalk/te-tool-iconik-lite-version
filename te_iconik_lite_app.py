#!/usr/bin/env python3
"""Desktop app for TE Tool - Iconik Lite Version."""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import te_iconik_scanner as scanner


APP_NAME = "TE Tool - Iconik Lite Version"
VERSION = "V1.5"
CONFIG_DIR = Path.home() / "Library" / "Application Support" / "TE Tool Iconik Lite"
CONFIG_PATH = CONFIG_DIR / "settings.json"
KEYCHAIN_SERVICE = "TE Tool Iconik Lite"
KEY_ICONIK_APP_ID = "iconik_app_id"
KEY_ICONIK_AUTH_TOKEN = "iconik_auth_token"
KEY_AWS_ACCESS_KEY_ID = "aws_access_key_id"
KEY_AWS_SECRET_ACCESS_KEY = "aws_secret_access_key"
KEY_AWS_SESSION_TOKEN = "aws_session_token"
DEFAULT_HOST = "https://app.iconik.io"
DEFAULT_REGION = "us-west-2"


class ConfigStore:
    @staticmethod
    def load() -> Dict[str, Any]:
        try:
            with CONFIG_PATH.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def save(data: Dict[str, Any]) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        safe = {
            "host": str(data.get("host") or DEFAULT_HOST).strip().rstrip("/") or DEFAULT_HOST,
            "aws_region": str(data.get("aws_region") or DEFAULT_REGION).strip() or DEFAULT_REGION,
            "output_path": str(data.get("output_path") or default_output_path()),
            "save_xlsx_automatically": bool(data.get("save_xlsx_automatically", True)),
        }
        tmp = CONFIG_PATH.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(safe, handle, indent=2, sort_keys=True)
        os.replace(tmp, CONFIG_PATH)
        try:
            CONFIG_PATH.chmod(0o600)
        except Exception:
            pass


class KeychainStore:
    @staticmethod
    def available() -> bool:
        return sys.platform == "darwin" and shutil.which("security") is not None

    @staticmethod
    def _run(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["security", *args], capture_output=True, text=True, check=False)

    @classmethod
    def get(cls, account: str) -> str:
        if not cls.available():
            return ""
        proc = cls._run(["find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", account, "-w"])
        if proc.returncode != 0:
            return ""
        return (proc.stdout or "").strip()

    @classmethod
    def set(cls, account: str, value: str) -> None:
        if not cls.available():
            return
        clean = value.strip()
        if clean:
            proc = cls._run(["add-generic-password", "-U", "-s", KEYCHAIN_SERVICE, "-a", account, "-w", clean])
            if proc.returncode != 0:
                raise RuntimeError((proc.stderr or proc.stdout or "Could not save credential to Keychain.").strip())
        else:
            cls.delete(account)

    @classmethod
    def delete(cls, account: str) -> None:
        if cls.available():
            cls._run(["delete-generic-password", "-s", KEYCHAIN_SERVICE, "-a", account])


def default_output_path() -> str:
    return str(Path.home() / "Downloads" / "te_iconik_lite_report.xlsx")


def apply_aws_environment(settings: Dict[str, str]) -> None:
    mapping = {
        "AWS_ACCESS_KEY_ID": settings.get("aws_access_key_id", ""),
        "AWS_SECRET_ACCESS_KEY": settings.get("aws_secret_access_key", ""),
        "AWS_SESSION_TOKEN": settings.get("aws_session_token", ""),
        "AWS_DEFAULT_REGION": settings.get("aws_region", DEFAULT_REGION),
        "AWS_REGION": settings.get("aws_region", DEFAULT_REGION),
    }
    for key, value in mapping.items():
        if value:
            os.environ[key] = value
        elif key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
            os.environ.pop(key, None)


def rows_for_s3_without_iconik(target: str, progress: Callable[[str], None]) -> List[scanner.ScanRow]:
    progress("Listing S3 objects...")
    inventory = scanner.list_s3_inventory(target)
    rows: List[scanner.ScanRow] = []
    for item in inventory:
        if not scanner.is_video_file(item.file_name):
            continue
        row = scanner.unmatched_s3_row(item)
        row.checks = [
            scanner.CheckResult(
                check.check_id,
                check.label,
                "fail",
                "Iconik credentials missing",
                check.target,
                "Save Iconik credentials in Settings so the app can retrieve technical metadata for this S3 object.",
            )
            for check in row.checks
        ]
        rows.append(row)
    return rows


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent: "IconikLiteApp") -> None:
        super().__init__(parent)
        self.parent_app = parent
        self.title("Settings")
        self.geometry("760x430")
        self.minsize(680, 390)
        self.transient(parent)
        self.grab_set()

        cfg = ConfigStore.load()
        self.iconik_host_var = tk.StringVar(value=str(cfg.get("host") or DEFAULT_HOST))
        self.iconik_app_id_var = tk.StringVar(value=KeychainStore.get(KEY_ICONIK_APP_ID))
        self.iconik_token_var = tk.StringVar(value=KeychainStore.get(KEY_ICONIK_AUTH_TOKEN))
        self.aws_key_var = tk.StringVar(value=KeychainStore.get(KEY_AWS_ACCESS_KEY_ID))
        self.aws_secret_var = tk.StringVar(value=KeychainStore.get(KEY_AWS_SECRET_ACCESS_KEY))
        self.aws_token_var = tk.StringVar(value=KeychainStore.get(KEY_AWS_SESSION_TOKEN))
        self.aws_region_var = tk.StringVar(value=str(cfg.get("aws_region") or DEFAULT_REGION))
        self.output_path_var = tk.StringVar(value=str(cfg.get("output_path") or default_output_path()))
        self.auto_save_var = tk.BooleanVar(value=bool(cfg.get("save_xlsx_automatically", True)))

        self.secret_entries: List[ttk.Entry] = []
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.columnconfigure(0, weight=1)

        intro = (
            "Save credentials once, then paste S3 or Iconik targets in the main window. "
            "Secrets are stored in macOS Keychain when available and hidden by default."
        )
        ttk.Label(outer, text=intro, wraplength=700).grid(row=0, column=0, sticky="ew")

        iconik = ttk.LabelFrame(outer, text="Iconik API Credentials", padding=12)
        iconik.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        iconik.columnconfigure(1, weight=1)
        iconik.columnconfigure(3, weight=1)

        ttk.Label(iconik, text="Host").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(iconik, textvariable=self.iconik_host_var).grid(row=0, column=1, columnspan=3, sticky="ew")
        ttk.Label(iconik, text="App-ID").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(10, 0))
        ttk.Entry(iconik, textvariable=self.iconik_app_id_var).grid(row=1, column=1, sticky="ew", pady=(10, 0))
        ttk.Label(iconik, text="Auth-Token").grid(row=1, column=2, sticky="w", padx=(16, 8), pady=(10, 0))
        self._secret_entry(iconik, self.iconik_token_var).grid(row=1, column=3, sticky="ew", pady=(10, 0))
        ttk.Label(
            iconik,
            text="Required for Iconik links and for turning S3 inventory into real TE metadata checks.",
            foreground="#4b5563",
        ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(8, 0))

        aws = ttk.LabelFrame(outer, text="AWS S3 Credentials", padding=12)
        aws.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        aws.columnconfigure(1, weight=1)
        aws.columnconfigure(3, weight=1)

        ttk.Label(aws, text="Access Key ID").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(aws, textvariable=self.aws_key_var).grid(row=0, column=1, sticky="ew")
        ttk.Label(aws, text="Region").grid(row=0, column=2, sticky="w", padx=(16, 8))
        ttk.Entry(aws, textvariable=self.aws_region_var, width=16).grid(row=0, column=3, sticky="w")
        ttk.Label(aws, text="Secret Access Key").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(10, 0))
        self._secret_entry(aws, self.aws_secret_var).grid(row=1, column=1, sticky="ew", pady=(10, 0))
        ttk.Label(aws, text="Session Token").grid(row=1, column=2, sticky="w", padx=(16, 8), pady=(10, 0))
        self._secret_entry(aws, self.aws_token_var).grid(row=1, column=3, sticky="ew", pady=(10, 0))
        ttk.Label(
            aws,
            text="Required for direct s3:// bucket, folder, and file-path scans. Leave blank to use an existing AWS profile/provider chain on this Mac.",
            foreground="#4b5563",
        ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(8, 0))

        output = ttk.LabelFrame(outer, text="Report Output", padding=12)
        output.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        output.columnconfigure(1, weight=1)
        ttk.Label(output, text="XLSX path").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(output, textvariable=self.output_path_var).grid(row=0, column=1, sticky="ew")
        ttk.Button(output, text="Choose...", command=self._choose_output).grid(row=0, column=2, padx=(8, 0))
        ttk.Checkbutton(output, text="Save XLSX automatically after each scan", variable=self.auto_save_var).grid(
            row=1, column=1, columnspan=2, sticky="w", pady=(8, 0)
        )

        actions = ttk.Frame(outer)
        actions.grid(row=4, column=0, sticky="ew", pady=(16, 0))
        actions.columnconfigure(0, weight=1)
        ttk.Button(actions, text="Reveal / Hide Secrets", command=self._toggle_secrets).grid(row=0, column=0, sticky="w")
        ttk.Button(actions, text="Remove Saved Credentials", command=self._remove_credentials).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(actions, text="Cancel", command=self.destroy).grid(row=0, column=2, padx=(16, 0))
        ttk.Button(actions, text="Save Settings", command=self._save).grid(row=0, column=3, padx=(8, 0))

    def _secret_entry(self, parent: tk.Widget, variable: tk.StringVar) -> ttk.Entry:
        entry = ttk.Entry(parent, textvariable=variable, show="*")
        self.secret_entries.append(entry)
        return entry

    def _toggle_secrets(self) -> None:
        show = "" if self.secret_entries and self.secret_entries[0].cget("show") == "*" else "*"
        for entry in self.secret_entries:
            entry.configure(show=show)

    def _choose_output(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".xlsx",
            filetypes=[("Excel workbook", "*.xlsx")],
            initialfile=Path(self.output_path_var.get() or default_output_path()).name,
        )
        if path:
            self.output_path_var.set(path)

    def _save(self) -> None:
        try:
            ConfigStore.save(
                {
                    "host": self.iconik_host_var.get(),
                    "aws_region": self.aws_region_var.get(),
                    "output_path": self.output_path_var.get(),
                    "save_xlsx_automatically": self.auto_save_var.get(),
                }
            )
            KeychainStore.set(KEY_ICONIK_APP_ID, self.iconik_app_id_var.get())
            KeychainStore.set(KEY_ICONIK_AUTH_TOKEN, self.iconik_token_var.get())
            KeychainStore.set(KEY_AWS_ACCESS_KEY_ID, self.aws_key_var.get())
            KeychainStore.set(KEY_AWS_SECRET_ACCESS_KEY, self.aws_secret_var.get())
            KeychainStore.set(KEY_AWS_SESSION_TOKEN, self.aws_token_var.get())
        except Exception as exc:  # pylint: disable=broad-except
            messagebox.showerror("Could Not Save Settings", str(exc), parent=self)
            return
        self.parent_app.load_settings()
        self.parent_app.set_status("Settings saved.")
        self.destroy()

    def _remove_credentials(self) -> None:
        if not messagebox.askyesno("Remove Credentials", "Remove saved Iconik and AWS credentials from Keychain?", parent=self):
            return
        for account in (
            KEY_ICONIK_APP_ID,
            KEY_ICONIK_AUTH_TOKEN,
            KEY_AWS_ACCESS_KEY_ID,
            KEY_AWS_SECRET_ACCESS_KEY,
            KEY_AWS_SESSION_TOKEN,
        ):
            KeychainStore.delete(account)
        self.iconik_app_id_var.set("")
        self.iconik_token_var.set("")
        self.aws_key_var.set("")
        self.aws_secret_var.set("")
        self.aws_token_var.set("")
        self.parent_app.load_settings()
        self.parent_app.set_status("Saved credentials removed.")


class IconikLiteApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} {VERSION}")
        self.geometry("1180x760")
        self.minsize(960, 640)
        self.result_queue: "queue.Queue[tuple[str, Any]]" = queue.Queue()
        self.rows: List[scanner.ScanRow] = []
        self.current_output_path = default_output_path()

        self.target_var = tk.StringVar(value="")
        self.output_path_var = tk.StringVar(value=default_output_path())
        self.status_var = tk.StringVar(value="Ready. Open Settings once, then paste an S3 or Iconik target and scan.")
        self.summary_var = tk.StringVar(value="No scan yet.")
        self.credential_status_var = tk.StringVar(value="")

        self.settings: Dict[str, str] = {}
        self.load_settings()
        self._build()
        self.after(100, self._drain_queue)

    def load_settings(self) -> None:
        cfg = ConfigStore.load()
        self.settings = {
            "host": str(cfg.get("host") or DEFAULT_HOST).strip().rstrip("/") or DEFAULT_HOST,
            "aws_region": str(cfg.get("aws_region") or DEFAULT_REGION).strip() or DEFAULT_REGION,
            "output_path": str(cfg.get("output_path") or default_output_path()),
            "save_xlsx_automatically": bool(cfg.get("save_xlsx_automatically", True)),
            "iconik_app_id": KeychainStore.get(KEY_ICONIK_APP_ID),
            "iconik_auth_token": KeychainStore.get(KEY_ICONIK_AUTH_TOKEN),
            "aws_access_key_id": KeychainStore.get(KEY_AWS_ACCESS_KEY_ID),
            "aws_secret_access_key": KeychainStore.get(KEY_AWS_SECRET_ACCESS_KEY),
            "aws_session_token": KeychainStore.get(KEY_AWS_SESSION_TOKEN),
        }
        self.current_output_path = self.settings["output_path"]
        self.output_path_var.set(self.current_output_path)
        parts = []
        parts.append("Iconik saved" if self.has_iconik_credentials() else "Iconik not saved")
        parts.append("AWS saved" if self.has_aws_credentials() else "AWS profile/Settings needed")
        self.credential_status_var.set(" | ".join(parts))

    def has_iconik_credentials(self) -> bool:
        return bool(self.settings.get("iconik_app_id") and self.settings.get("iconik_auth_token"))

    def has_aws_credentials(self) -> bool:
        return bool(self.settings.get("aws_access_key_id") and self.settings.get("aws_secret_access_key"))

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(5, weight=1)

        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text=APP_NAME, font=("Arial", 22, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text=VERSION, font=("Arial", 12, "bold"), foreground="#176b87").grid(row=0, column=1, sticky="e")
        ttk.Label(
            header,
            text="Paste an S3 bucket, folder, file path, or Iconik asset/collection link. The app builds the video list, retrieves Iconik metadata when available, and writes the QC report.",
            wraplength=900,
            foreground="#374151",
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        target_frame = ttk.LabelFrame(outer, text="Scan Target", padding=12)
        target_frame.grid(row=1, column=0, sticky="ew", pady=(16, 0))
        target_frame.columnconfigure(0, weight=1)
        ttk.Entry(target_frame, textvariable=self.target_var, font=("Arial", 13)).grid(row=0, column=0, sticky="ew")
        ttk.Button(target_frame, text="Scan", command=self.scan).grid(row=0, column=1, padx=(10, 0), ipadx=12)
        ttk.Button(target_frame, text="Settings", command=self.open_settings).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(target_frame, text="Clear", command=self.clear).grid(row=0, column=3, padx=(8, 0))
        examples = "Examples: s3://gacm-deliver-vod/  |  s3://gacm-axinom-staging/series/the_real_mccoys_1974776387798/  |  https://app.iconik.io/collection/..."
        ttk.Label(target_frame, text=examples, foreground="#5f6b7a", wraplength=900).grid(row=1, column=0, columnspan=4, sticky="w", pady=(8, 0))

        output_frame = ttk.Frame(outer)
        output_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        output_frame.columnconfigure(1, weight=1)
        ttk.Label(output_frame, text="Report").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(output_frame, textvariable=self.output_path_var).grid(row=0, column=1, sticky="ew")
        ttk.Button(output_frame, text="Choose...", command=self.choose_output).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(output_frame, text="Save XLSX", command=self.save_xlsx).grid(row=0, column=3, padx=(8, 0))

        status_frame = ttk.Frame(outer)
        status_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        status_frame.columnconfigure(0, weight=1)
        ttk.Label(status_frame, textvariable=self.status_var, foreground="#244456").grid(row=0, column=0, sticky="w")
        ttk.Label(status_frame, textvariable=self.credential_status_var, foreground="#5f6b7a").grid(row=0, column=1, sticky="e")
        ttk.Label(status_frame, textvariable=self.summary_var, foreground="#374151").grid(row=1, column=0, columnspan=2, sticky="w", pady=(3, 0))

        panes = ttk.PanedWindow(outer, orient=tk.VERTICAL)
        panes.grid(row=5, column=0, sticky="nsew", pady=(12, 0))

        results_frame = ttk.LabelFrame(panes, text="Video Results", padding=8)
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        columns = ("result", "title", "upload", "file", "s3", "fails", "warnings")
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show="headings", height=10)
        headings = {
            "result": "Result",
            "title": "Title",
            "upload": "Upload Date",
            "file": "File",
            "s3": "S3 / Storage Path",
            "fails": "Fails",
            "warnings": "Warnings",
        }
        widths = {"result": 84, "title": 220, "upload": 160, "file": 210, "s3": 360, "fails": 60, "warnings": 80}
        for col in columns:
            self.results_tree.heading(col, text=headings[col])
            self.results_tree.column(col, width=widths[col], minwidth=50, stretch=col in {"title", "s3"})
        self.results_tree.grid(row=0, column=0, sticky="nsew")
        result_scroll = ttk.Scrollbar(results_frame, orient="vertical", command=self.results_tree.yview)
        result_scroll.grid(row=0, column=1, sticky="ns")
        self.results_tree.configure(yscrollcommand=result_scroll.set)
        self.results_tree.tag_configure("pass", background="#ddeed9")
        self.results_tree.tag_configure("warning", background="#f8e7b8")
        self.results_tree.tag_configure("fail", background="#eee3f6")
        self.results_tree.bind("<<TreeviewSelect>>", self._on_result_selected)

        details_frame = ttk.LabelFrame(panes, text="Selected Video Checks", padding=8)
        details_frame.columnconfigure(0, weight=1)
        details_frame.rowconfigure(0, weight=1)
        detail_cols = ("check", "status", "value", "target", "note")
        self.detail_tree = ttk.Treeview(details_frame, columns=detail_cols, show="headings", height=9)
        detail_headings = {"check": "Check", "status": "Status", "value": "Value", "target": "Target", "note": "Note"}
        detail_widths = {"check": 180, "status": 90, "value": 170, "target": 170, "note": 440}
        for col in detail_cols:
            self.detail_tree.heading(col, text=detail_headings[col])
            self.detail_tree.column(col, width=detail_widths[col], minwidth=60, stretch=col == "note")
        self.detail_tree.grid(row=0, column=0, sticky="nsew")
        detail_scroll = ttk.Scrollbar(details_frame, orient="vertical", command=self.detail_tree.yview)
        detail_scroll.grid(row=0, column=1, sticky="ns")
        self.detail_tree.configure(yscrollcommand=detail_scroll.set)
        self.detail_tree.tag_configure("pass", background="#ddeed9")
        self.detail_tree.tag_configure("warning", background="#f8e7b8")
        self.detail_tree.tag_configure("fail", background="#eee3f6")

        panes.add(results_frame, weight=2)
        panes.add(details_frame, weight=1)

        log_frame = ttk.LabelFrame(outer, text="Scan Log", padding=8)
        log_frame.grid(row=6, column=0, sticky="ew", pady=(12, 0))
        log_frame.columnconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=5, wrap="word", font=("Menlo", 11))
        self.log_text.grid(row=0, column=0, sticky="ew")
        self.log_text.configure(state="disabled")

    def open_settings(self) -> None:
        SettingsDialog(self)

    def choose_output(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".xlsx",
            filetypes=[("Excel workbook", "*.xlsx")],
            initialfile=Path(self.output_path_var.get() or default_output_path()).name,
        )
        if path:
            self.output_path_var.set(path)
            self.current_output_path = path
            cfg = ConfigStore.load()
            cfg["output_path"] = path
            ConfigStore.save(cfg)

    def scan(self) -> None:
        target = self.target_var.get().strip()
        if not target:
            messagebox.showerror("Missing Target", "Paste an S3 path or Iconik link first.", parent=self)
            return
        try:
            target_type, _ = scanner.parse_target(target)
        except Exception as exc:
            messagebox.showerror("Unsupported Target", str(exc), parent=self)
            return
        if target_type in {"asset", "collection"} and not self.has_iconik_credentials():
            messagebox.showerror("Iconik Credentials Needed", "Open Settings and save Iconik App-ID and Auth-Token first.", parent=self)
            return
        if target_type == "s3" and not self.has_aws_credentials():
            if not messagebox.askyesno(
                "AWS Credentials",
                "No AWS keys are saved in Settings. Continue using any AWS profile/provider chain already configured on this Mac?",
                parent=self,
            ):
                return

        self.rows = []
        self._clear_tree(self.results_tree)
        self._clear_tree(self.detail_tree)
        self.summary_var.set("Scanning...")
        self.set_status("Scanning. You can keep working while this runs.")
        self._append_log(f"Target: {target}")

        thread = threading.Thread(target=self._scan_worker, args=(target, target_type), daemon=True)
        thread.start()

    def _scan_worker(self, target: str, target_type: str) -> None:
        try:
            self.result_queue.put(("log", "Loading saved credentials..."))
            apply_aws_environment(self.settings)
            rows: List[scanner.ScanRow]
            if self.has_iconik_credentials():
                client = scanner.IconikClient(
                    app_id=str(self.settings.get("iconik_app_id") or ""),
                    auth_token=str(self.settings.get("iconik_auth_token") or ""),
                    host=str(self.settings.get("host") or DEFAULT_HOST),
                )
                self.result_queue.put(("log", "Contacting Iconik and scanning metadata..."))
                rows = scanner.scan_target(client, target)
            elif target_type == "s3":
                self.result_queue.put(("log", "Iconik credentials are not saved, so this will be an S3 inventory with metadata-missing failures."))
                rows = rows_for_s3_without_iconik(target, lambda msg: self.result_queue.put(("log", msg)))
            else:
                raise RuntimeError("Iconik credentials are required for Iconik links.")

            output_path = self.output_path_var.get().strip() or default_output_path()
            if self.settings.get("save_xlsx_automatically", True):
                self.result_queue.put(("log", f"Writing XLSX report: {output_path}"))
                scanner.write_xlsx(rows, output_path, target)
            self.result_queue.put(("done", {"rows": rows, "output": output_path}))
        except Exception as exc:  # pylint: disable=broad-except
            self.result_queue.put(("error", str(exc)))

    def _drain_queue(self) -> None:
        try:
            while True:
                kind, payload = self.result_queue.get_nowait()
                if kind == "log":
                    self._append_log(str(payload))
                elif kind == "done":
                    self.rows = list(payload["rows"])
                    self.current_output_path = str(payload["output"])
                    self.output_path_var.set(self.current_output_path)
                    self.render_results()
                    self.set_status(f"Scan complete. {len(self.rows)} video row(s).")
                    self._append_log("Scan complete.")
                elif kind == "error":
                    self.set_status("Scan failed.")
                    self._append_log(f"ERROR: {payload}")
                    messagebox.showerror("Scan Failed", str(payload), parent=self)
        except queue.Empty:
            pass
        self.after(100, self._drain_queue)

    def render_results(self) -> None:
        self._clear_tree(self.results_tree)
        counts = {"PASS": 0, "WARNING": 0, "FAIL": 0}
        for idx, row in enumerate(self.rows):
            counts[row.verdict] = counts.get(row.verdict, 0) + 1
            fail_count = sum(1 for check in row.checks if check.status == "fail")
            warning_count = sum(1 for check in row.checks if check.status == "warning")
            self.results_tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(row.verdict, row.asset_title, row.upload_date, row.file_name, row.s3_uri, fail_count, warning_count),
                tags=(row.verdict.lower(),),
            )
        self.summary_var.set(
            f"Videos: {len(self.rows)} | PASS: {counts.get('PASS', 0)} | WARNING: {counts.get('WARNING', 0)} | FAIL: {counts.get('FAIL', 0)}"
        )
        if self.rows:
            self.results_tree.selection_set("0")
            self._render_details(self.rows[0])

    def _on_result_selected(self, _event: tk.Event) -> None:
        selection = self.results_tree.selection()
        if not selection:
            return
        index = int(selection[0])
        if 0 <= index < len(self.rows):
            self._render_details(self.rows[index])

    def _render_details(self, row: scanner.ScanRow) -> None:
        self._clear_tree(self.detail_tree)
        for check in row.checks:
            self.detail_tree.insert(
                "",
                "end",
                values=(check.label, check.status.upper(), check.value, check.target, check.note),
                tags=(check.status,),
            )

    def save_xlsx(self) -> None:
        if not self.rows:
            messagebox.showerror("No Results", "Run a scan before saving an XLSX report.", parent=self)
            return
        path = self.output_path_var.get().strip() or default_output_path()
        try:
            scanner.write_xlsx(self.rows, path, self.target_var.get().strip())
        except Exception as exc:  # pylint: disable=broad-except
            messagebox.showerror("Could Not Save Report", str(exc), parent=self)
            return
        self.current_output_path = path
        self.set_status(f"Saved report: {path}")

    def clear(self) -> None:
        self.target_var.set("")
        self.rows = []
        self._clear_tree(self.results_tree)
        self._clear_tree(self.detail_tree)
        self.summary_var.set("No scan yet.")
        self.set_status("Ready.")
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state="disabled")

    def set_status(self, message: str) -> None:
        self.status_var.set(message)

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    @staticmethod
    def _clear_tree(tree: ttk.Treeview) -> None:
        for item in tree.get_children():
            tree.delete(item)


def verify_imports() -> int:
    import boto3  # type: ignore  # pylint: disable=unused-import,import-outside-toplevel

    print("imports ok")
    return 0


def verify_tk() -> int:
    root = tk.Tk()
    root.update()
    root.destroy()
    print("tk ok")
    return 0


def main() -> int:
    if os.environ.get("TE_ICONIK_LITE_VERIFY_IMPORTS") == "1":
        return verify_imports()
    if os.environ.get("TE_ICONIK_LITE_VERIFY_TK") == "1":
        return verify_tk()
    app = IconikLiteApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
