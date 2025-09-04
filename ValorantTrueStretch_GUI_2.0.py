# ValorantTrueStretch_GUI_2.0.py
# ValorantTrueStretch_GUI.py
# Tool to speed up "true stretch" config for VALORANT on Windows.
# Made by GlitchFL (credit required if you share)

import os
import re
import difflib
import shutil
import json
import threading
import ctypes
import datetime as _dt
from pathlib import Path

import tkinter as tk
from tkinter import messagebox, filedialog

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledText

APP_TITLE = "VALORANT Configuration Tool"
VERSION = "2.4 GlitchFL"

FULLSCREEN_KEY = "FullscreenMode"
HDR_KEY = "HDRDisplayOutputNits"

RESOLUTIONS = {
    "native": ["3840x2160", "2560x1440", "1920x1080", "2560x1080", "3440x1440"],
    "target": [
        "1920x1080", "1680x1050", "1440x1080", "1280x1024", "1100x1080",
        "1080x1080", "1280x960", "1024x768"
    ],
}

PRESETS_PATH = Path.home() / "Documents" / "ValorantTrueStretch_Presets.json"

# Core helpers 

def parse_whx(s: str):
    s = s.strip()
    m = re.fullmatch(r"(\d+)[xX](\d+)", s)
    if not m:
        raise ValueError("Invalid format. Use WIDTHxHEIGHT (e.g., 2560x1440)")
    return int(m.group(1)), int(m.group(2))

def read_lines(path: Path):
    return path.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)

def write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

def write_lines(path: Path, lines):
    write_text(path, "".join(lines))

def update_kv_lines(lines, updates: dict):
    changed = False
    found = set()
    out = []
    for ln in lines:
        m = re.match(r"^\s*([A-Za-z0-9_]+)\s*=\s*(.*)\s*$", ln)
        if m:
            k = m.group(1)
            if k in updates and updates[k] is not None:
                v = str(updates[k])
                new_ln = f"{k}={v}\n"
                if ln != new_ln:
                    changed = True
                    ln = new_ln
                found.add(k)
        out.append(ln)
    for k, v in updates.items():
        if v is None:
            continue
        if k not in found:
            out.append(f"{k}={v}\n")
            changed = True
    return out, changed

def ensure_hdr_and_fullscreen(lines, hdr_val="1000", fs_val="2"):
    out = []
    seen_hdr = False
    for ln in lines:
        if re.match(rf"^\s*{HDR_KEY}\s*=\s*\d+\s*$", ln):
            seen_hdr = True
            ln = f"{HDR_KEY}={hdr_val}\n"
            out.append(ln)
            out.append(f"{FULLSCREEN_KEY}={fs_val}\n")
        elif re.match(rf"^\s*{FULLSCREEN_KEY}\s*=\s*\d+\s*$", ln):
            continue
        else:
            out.append(ln)
    if not seen_hdr:
        if len(out) == 0 or not out[-1].endswith("\n"):
            out.append("\n")
        out.append(f"{HDR_KEY}={hdr_val}\n")
        out.append(f"{FULLSCREEN_KEY}={fs_val}\n")
    return out, True

def file_diff(old_lines, new_lines, label):
    return "".join(
        difflib.unified_diff(
            old_lines, new_lines, fromfile=f"{label} (current)", tofile=f"{label} (new)", n=3
        )
    )

def get_base_config_dir():
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError("Couldn't resolve %LOCALAPPDATA%. Are you on Windows?")
    return Path(local) / "VALORANT" / "Saved" / "Config"

def get_last_known_user(windows_client_dir: Path):
    rlmi = windows_client_dir / "RiotLocalMachine.ini"
    if not rlmi.is_file():
        return None
    txt = rlmi.read_text(encoding="utf-8", errors="ignore").splitlines()
    for ln in txt:
        m = re.match(r"^\s*LastKnownUser\s*=\s*([A-Za-z0-9\-]+)\s*$", ln)
        if m:
            return m.group(1)
    return None

def find_user_folder(base: Path, last_known: str):
    if not last_known:
        return None
    candidates = [
        p for p in base.iterdir() if p.is_dir() and p.name.lower().startswith(last_known.lower() + "-")
    ]
    def score(p):
        s = 0
        if (p / "Windows").is_dir(): s += 1
        if (p / "WindowsClient").is_dir(): s += 1
        return s
    if not candidates:
        return None
    candidates.sort(key=score, reverse=True)
    return candidates[0]

def native_check_ok(lines, native_x, native_y):
    want = {
        "ResolutionSizeX": str(native_x),
        "ResolutionSizeY": str(native_y),
        "LastUserConfirmedResolutionSizeX": str(native_x),
        "LastUserConfirmedResolutionSizeY": str(native_y),
        "bShouldLetterbox": "False",
        "bLastConfirmedShouldLetterbox": "False",
    }
    got = {}
    for ln in lines:
        m = re.match(r"^\s*([A-Za-z0-9_]+)\s*=\s*(.*)\s*$", ln)
        if m:
            got[m.group(1)] = m.group(2).strip()
    for k, v in want.items():
        if got.get(k) != v:
            return False, k, got.get(k)
    return True, None, None

def make_updates_for_target(target_x, target_y):
    return {
        "ResolutionSizeX": str(target_x),
        "ResolutionSizeY": str(target_y),
        "LastUserConfirmedResolutionSizeX": str(target_x),
        "LastUserConfirmedResolutionSizeY": str(target_y),
        "bShouldLetterbox": "False",
        "bLastConfirmedShouldLetterbox": "False",
    }

def _timestamp():
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")

def safe_backup(src_path: Path, backup_root: Path, diff_text: str | None):
    rel = src_path.as_posix().replace(":", "")
    dst_dir = backup_root / _timestamp() / Path(rel).parent
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst_file = dst_dir / (src_path.name + ".bak")
    shutil.copy2(src_path, dst_file)
    if diff_text:
        write_text(dst_dir / (src_path.stem + ".patch"), diff_text)
    return dst_file

def process_gus(path: Path, target_x, target_y, apply_changes, label, log_func, backup_dir: Path | None):
    if not path.is_file():
        log_func(f"- Skipping (not found): {label} -> {path}", tag="warning")
        return
    old = read_lines(path)
    updates = make_updates_for_target(target_x, target_y)
    temp, changed_a = update_kv_lines(old, updates)
    temp2, _ = ensure_hdr_and_fullscreen(temp, "1000", "2")
    changed = changed_a or (temp2 != old)
    if not changed:
        log_func(f"- No changes needed: {label}", tag="muted")
        return
    diff = file_diff(old, temp2, str(path))
    log_func(f"\n>>> {label}\n{diff if diff.strip() else '(content replaced)'}", tag="info")
    if apply_changes:
        if backup_dir:
            try:
                saved = safe_backup(path, backup_dir, diff)
                log_func(f"-> Backup saved: {saved}", tag="success")
            except Exception as be:
                log_func(f"[!] Backup failed: {be}", tag="error")
        write_lines(path, temp2)
        log_func(f"-> Updated {label}.", tag="success")
    else:
        log_func("-> Dry run (no write).", tag="muted")

# Windows desktop resolution control 

# Minimal DEVMODE for width/height changes
class DEVMODE(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", ctypes.c_wchar * 32),
        ("dmSpecVersion", ctypes.c_uint16),
        ("dmDriverVersion", ctypes.c_uint16),
        ("dmSize", ctypes.c_uint16),
        ("dmDriverExtra", ctypes.c_uint16),
        ("dmFields", ctypes.c_uint32),
        ("dmOrientation", ctypes.c_int16),
        ("dmPaperSize", ctypes.c_int16),
        ("dmPaperLength", ctypes.c_int16),
        ("dmPaperWidth", ctypes.c_int16),
        ("dmScale", ctypes.c_int16),
        ("dmCopies", ctypes.c_int16),
        ("dmDefaultSource", ctypes.c_int16),
        ("dmPrintQuality", ctypes.c_int16),
        ("dmColor", ctypes.c_int16),
        ("dmDuplex", ctypes.c_int16),
        ("dmYResolution", ctypes.c_int16),
        ("dmTTOption", ctypes.c_int16),
        ("dmCollate", ctypes.c_int16),
        ("dmFormName", ctypes.c_wchar * 32),
        ("dmLogPixels", ctypes.c_uint16),
        ("dmBitsPerPel", ctypes.c_uint32),
        ("dmPelsWidth", ctypes.c_uint32),
        ("dmPelsHeight", ctypes.c_uint32),
        ("dmDisplayFlags", ctypes.c_uint32),
        ("dmDisplayFrequency", ctypes.c_uint32),
        ("dmICMMethod", ctypes.c_uint32),
        ("dmICMIntent", ctypes.c_uint32),
        ("dmMediaType", ctypes.c_uint32),
        ("dmDitherType", ctypes.c_uint32),
        ("dmReserved1", ctypes.c_uint32),
        ("dmReserved2", ctypes.c_uint32),
        ("dmPanningWidth", ctypes.c_uint32),
        ("dmPanningHeight", ctypes.c_uint32),
    ]

# Flags/consts
ENUM_CURRENT_SETTINGS = -1
DM_PELSWIDTH  = 0x00080000
DM_PELSHEIGHT = 0x00100000

CDS_UPDATEREGISTRY = 0x00000001
CDS_TEST           = 0x00000002
CDS_FULLSCREEN     = 0x00000004

DISP_CHANGE_SUCCESSFUL = 0
DISP_CHANGE_RESTART    = 1
DISP_CHANGE_FAILED     = -1
DISP_CHANGE_BADMODE    = -2
DISP_CHANGE_NOTUPDATED = -3
DISP_CHANGE_BADFLAGS   = -4
DISP_CHANGE_BADPARAM   = -5

def detect_primary_resolution():
    """Get current primary screen resolution in physical pixels."""
    try:
        user32 = ctypes.windll.user32
        # Ensure pixel-accurate metrics on high-DPI systems
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass
        w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
        h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
        if w and h:
            return w, h
    except Exception:
        pass
    return None

def change_desktop_resolution(width: int, height: int):
    """Change primary display resolution to width x height using ChangeDisplaySettings."""
    try:
        devmode = DEVMODE()
        devmode.dmSize = ctypes.sizeof(DEVMODE)
        ctypes.windll.user32.EnumDisplaySettingsW(None, ENUM_CURRENT_SETTINGS, ctypes.byref(devmode))
        devmode.dmFields = DM_PELSWIDTH | DM_PELSHEIGHT
        devmode.dmPelsWidth = int(width)
        devmode.dmPelsHeight = int(height)

        # Test first
        test = ctypes.windll.user32.ChangeDisplaySettingsW(ctypes.byref(devmode), CDS_TEST)
        if test != DISP_CHANGE_SUCCESSFUL:
            return False, f"Mode not supported by Windows (code {test})."

        # Apply
        rc = ctypes.windll.user32.ChangeDisplaySettingsW(ctypes.byref(devmode), 0)
        if rc == DISP_CHANGE_SUCCESSFUL:
            return True, "Desktop resolution changed."
        elif rc == DISP_CHANGE_RESTART:
            return True, "Desktop resolution changed (restart required)."
        else:
            return False, f"Failed to change resolution (code {rc})."
    except Exception as e:
        return False, f"Error changing resolution: {e}"

# -------------------- ttkbootstrap UI --------------------

class App(tb.Window):
    def __init__(self):
        # Locked to dark theme (no theme switcher)
        super().__init__(title=APP_TITLE, themename="darkly")
        self.geometry("1040x760")
        self.minsize(960, 660)

        # State
        self.native_var = tk.StringVar()
        self.target_var = tk.StringVar()
        self.force_var = tk.BooleanVar(value=False)
        self.backup_var = tk.BooleanVar(value=True)
        self.change_desktop_var = tk.BooleanVar(value=False)  # NEW: change Windows desktop on Apply
        self.backup_dir_var = tk.StringVar(value=str(Path.home() / "Documents" / "ValorantTrueStretch_Backups"))
        self.cfg_base_var = tk.StringVar(value="")
        self.presets = self._load_presets()

        # UI
        self._build_header()
        self._build_body()
        self._build_statusbar()

        # Defaults
        self.native_var.set("2560x1440")
        self.target_var.set("1280x1024")
        self._log("Ready. Make sure VALORANT is completely closed (Riot Client can remain open).", tag="muted")
        self._detect_base_config_dir()

        # Shortcuts
        self.bind("<F1>", lambda e: self.preflight())
        self.bind("<F2>", lambda e: self.dry_run())
        self.bind("<Control-Return>", lambda e: self.apply())
        self.bind("<Control-l>", lambda e: self._clear_log())

    # ----- Layout
    def _build_header(self):
        bar = tb.Frame(self, padding=(16, 14))
        bar.pack(fill=X)
        tb.Label(bar, text="VALORANT TRUE STRETCH CONFIG", font=("Segoe UI Semibold", 15)).pack(side=LEFT)
        tb.Label(bar, text=f"v{VERSION}", bootstyle=SECONDARY).pack(side=RIGHT)

    def _build_body(self):
        body = tb.Frame(self, padding=(16, 8, 16, 16))
        body.pack(fill=BOTH, expand=YES)
        body.columnconfigure(0, weight=1, uniform="col")
        body.columnconfigure(1, weight=1, uniform="col")

        self._build_quick_guide(body, 0)
        self._build_config_card(body, 0)
        self._build_paths_card(body, 0)

        self._build_actions(body, 1)
        self._build_output_card(body, 1)

    def _build_quick_guide(self, parent, col):
        lf = tb.Labelframe(parent, text="Quick Guide", padding=12)
        lf.grid(row=0, column=col, sticky=EW, pady=(0, 10), padx=(0, 8) if col == 0 else (8, 0))
        msg = (
            "SETUP → VALORANT: Fullscreen + Fill at native → Apply → Close\n"
            "USAGE → Choose native & target → VERIFY → PREVIEW → APPLY\n"
            "AFTER → Change Windows desktop to target → Launch VALORANT"
        )
        tb.Label(lf, text=msg, justify=LEFT, bootstyle=SECONDARY).pack(anchor=W)

    def _build_config_card(self, parent, col):
        card = tb.Labelframe(parent, text="Configuration", padding=12)
        card.grid(row=1, column=col, sticky=EW, pady=(0, 10), padx=(0, 8) if col == 0 else (8, 0))

        grid = tb.Frame(card)
        grid.pack(fill=X)
        for i in (0, 2):
            grid.columnconfigure(i, weight=1)

        # Labels
        tb.Label(grid, text="Native Resolution").grid(row=0, column=0, sticky=W)
        tb.Label(grid, text="Target Resolution").grid(row=0, column=2, sticky=W)

        # Combos
        native_combo = tb.Combobox(
            grid, textvariable=self.native_var, values=RESOLUTIONS["native"], width=20,
            bootstyle=INFO, state="readonly"
        )
        native_combo.grid(row=1, column=0, sticky=EW, padx=(0, 10), pady=(4, 8))

        target_combo = tb.Combobox(
            grid, textvariable=self.target_var, values=RESOLUTIONS["target"], width=20,
            bootstyle=INFO, state="readonly"
        )
        target_combo.grid(row=1, column=2, sticky=EW, padx=(0, 10), pady=(4, 8))

        # NEW: Detect native button (small)
        tb.Button(grid, text="Detect", bootstyle=SECONDARY, command=self._detect_native)\
            .grid(row=1, column=1, sticky=W, padx=(0, 10))

        # Manual entry override
        tb.Label(grid, text="Or type manually (WIDTHxHEIGHT)", bootstyle=SECONDARY).grid(
            row=2, column=0, sticky=W, pady=(4, 0)
        )
        tb.Label(grid, text="Or type manually (WIDTHxHEIGHT)", bootstyle=SECONDARY).grid(
            row=2, column=2, sticky=W, pady=(4, 0)
        )

        self.native_entry = tb.Entry(grid)
        self.native_entry.grid(row=3, column=0, sticky=EW, pady=(2, 4))
        self.target_entry = tb.Entry(grid)
        self.target_entry.grid(row=3, column=2, sticky=EW, pady=(2, 4))

        # Quick Buttons (user-defined)
        self.quick_row = tb.Frame(card)
        self.quick_row.pack(fill=X, pady=(8, 2))
        tb.Label(self.quick_row, text="Quick buttons:", bootstyle=SECONDARY).pack(side=LEFT)

        self.quick_btns_wrap = tb.Frame(card)
        self.quick_btns_wrap.pack(fill=X, pady=(4, 0))
        self._render_quick_buttons()

        # Controls to manage quick buttons
        manage = tb.Frame(card)
        manage.pack(fill=X, pady=(6, 0))
        tb.Button(manage, text="Add Quick Button", bootstyle=SUCCESS, command=self._open_add_preset).pack(side=LEFT)
        tb.Button(manage, text="Manage…", bootstyle=SECONDARY, command=self._open_manage_presets).pack(side=LEFT, padx=6)

        # Toggles
        toggles = tb.Frame(card); toggles.pack(fill=X, pady=(10, 0))
        tb.Checkbutton(
            toggles, text="Force apply (skip native check)", variable=self.force_var,
            bootstyle="secondary-round-toggle",
        ).pack(side=LEFT)
        tb.Checkbutton(
            toggles, text="Also change Windows desktop to target on Apply",  # NEW
            variable=self.change_desktop_var, bootstyle="success-round-toggle",
        ).pack(side=LEFT, padx=12)

    def _build_paths_card(self, parent, col):
        card = tb.Labelframe(parent, text="Paths & Backups", padding=12)
        card.grid(row=2, column=col, sticky=EW, pady=(0, 10), padx=(0, 8) if col == 0 else (8, 0))

        row1 = tb.Frame(card); row1.pack(fill=X, pady=(0, 6))
        tb.Label(row1, text="Config base:", width=12).pack(side=LEFT)
        self.cfg_entry = tb.Entry(row1, textvariable=self.cfg_base_var)
        self.cfg_entry.pack(side=LEFT, fill=X, expand=YES, padx=6)
        tb.Button(row1, text="Detect", bootstyle=SECONDARY, command=self._detect_base_config_dir).pack(side=LEFT, padx=4)
        tb.Button(row1, text="Browse", bootstyle=SECONDARY, command=self._browse_cfg_dir).pack(side=LEFT, padx=4)
        tb.Button(row1, text="Open", bootstyle=LINK, command=self._open_cfg_dir).pack(side=LEFT, padx=4)

        row2 = tb.Frame(card); row2.pack(fill=X, pady=(0, 2))
        tb.Checkbutton(row2, text="Save backups & diffs to:", variable=self.backup_var,
                       bootstyle="success-round-toggle").pack(side=LEFT)
        self.backup_entry = tb.Entry(row2, textvariable=self.backup_dir_var)
        self.backup_entry.pack(side=LEFT, fill=X, expand=YES, padx=6)
        tb.Button(row2, text="Browse", bootstyle=SECONDARY, command=self._browse_backup_dir).pack(side=LEFT, padx=4)
        tb.Button(row2, text="Open", bootstyle=LINK, command=self._open_backup_dir).pack(side=LEFT, padx=4)

    def _build_actions(self, parent, col):
        card = tb.Labelframe(parent, text="Actions", padding=12)
        card.grid(row=0, column=col, sticky=EW, pady=(0, 10), padx=(8, 0) if col == 1 else (0, 8))

        row = tb.Frame(card); row.pack(pady=2)
        tb.Button(row, text="VERIFY (F1)", command=self.preflight, bootstyle=SECONDARY).pack(side=LEFT, padx=4)
        tb.Button(row, text="PREVIEW (F2)", command=self.dry_run, bootstyle=INFO).pack(side=LEFT, padx=4)
        tb.Button(row, text="APPLY (Ctrl+Enter)", command=self.apply, bootstyle=SUCCESS).pack(side=LEFT, padx=4)

        tb.Label(card, text="Tip: Manual entries override comboboxes.", bootstyle=SECONDARY)\
            .pack(anchor=W, pady=(8, 0))

    def _build_output_card(self, parent, col):
        box = tb.Labelframe(parent, text="Output", padding=8)
        box.grid(row=1, column=col, rowspan=2, sticky=NSEW, pady=(0, 10), padx=(8, 0) if col == 1 else (0, 8))
        parent.rowconfigure(1, weight=1)
        parent.rowconfigure(2, weight=0)

        toolbar = tb.Frame(box); toolbar.pack(fill=X)
        tb.Button(toolbar, text="Clear", command=self._clear_log, bootstyle=LINK).pack(side=RIGHT)
        tb.Button(toolbar, text="Save Log", command=self._save_log, bootstyle=LINK).pack(side=RIGHT, padx=8)
        tb.Button(toolbar, text="Copy Log", command=self._copy_log, bootstyle=LINK).pack(side=RIGHT)

        self.output = ScrolledText(box, autohide=True, height=18, padding=4)
        self.output.pack(fill=BOTH, expand=YES)
        
        # Configure color tags for different log levels
        self.output.tag_configure("success", foreground="#00bc8c")  # Green
        self.output.tag_configure("error", foreground="#e74c3c")    # Red
        self.output.tag_configure("warning", foreground="#f39c12")  # Orange/Yellow
        self.output.tag_configure("info", foreground="#3498db")     # Blue
        self.output.tag_configure("muted", foreground="#6c757d")    # Gray
        self.output.tag_configure("highlight", foreground="#e83e8c", font=("Consolas", 10, "bold"))  # Pink/bold

    def _build_statusbar(self):
        bar = tb.Frame(self, padding=(12, 6, 12, 12))
        bar.pack(side=BOTTOM, fill=X)
        self.status = tb.Label(bar, text="Ready", anchor=W, bootstyle=SECONDARY)
        self.status.pack(side=LEFT)
        self.prog = tb.Progressbar(bar, mode="indeterminate", length=160, bootstyle=INFO)
        self.prog.pack(side=RIGHT)

    # Quick Buttons (presets)
    def _load_presets(self):
        if PRESETS_PATH.is_file():
            try:
                data = json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return [p for p in data if {"name","native","target"} <= set(p.keys())]
            except Exception:
                pass
        return [
            {"name": "1080→1080x1080", "native": "1920x1080", "target": "1080x1080"},
            {"name": "1440p→1280x1024", "native": "2560x1440", "target": "1280x1024"},
            {"name": "1440p→1440x1080", "native": "2560x1440", "target": "1440x1080"},
        ]

    def _save_presets(self):
        try:
            write_text(PRESETS_PATH, json.dumps(self.presets, indent=2, ensure_ascii=False))
        except Exception as e:
            messagebox.showerror("Save presets", f"Failed to save presets:\n{e}")

    def _render_quick_buttons(self):
        for w in self.quick_btns_wrap.winfo_children():
            w.destroy()
        if not self.presets:
            tb.Label(self.quick_btns_wrap, text="No quick buttons yet. Click 'Add Quick Button'.",
                     bootstyle=SECONDARY).pack(anchor=W)
            return
        row = tb.Frame(self.quick_btns_wrap); row.pack(fill=X, pady=(2, 2))
        cur_width = 0
        max_width = 760
        for p in self.presets:
            btn = tb.Button(row, text=p["name"], bootstyle=INFO,
                            command=lambda n=p["native"], t=p["target"]: self._apply_preset(n, t))
            btn.update_idletasks()
            w = btn.winfo_reqwidth() + 8
            if cur_width + w > max_width:
                row = tb.Frame(self.quick_btns_wrap); row.pack(fill=X, pady=(2, 2))
                cur_width = 0
            btn.pack(side=LEFT, padx=4, pady=2)
            cur_width += w

    def _apply_preset(self, native_wh: str, target_wh: str):
        self.native_entry.delete(0, tk.END)
        self.native_entry.insert(0, native_wh)
        self.target_entry.delete(0, tk.END)
        self.target_entry.insert(0, target_wh)

    def _open_add_preset(self):
        top = tb.Toplevel(self)
        top.title("Add Quick Button")
        top.resizable(False, False)
        frm = tb.Frame(top, padding=12); frm.pack(fill=BOTH, expand=YES)

        name_var = tk.StringVar()
        native_var = tk.StringVar(value=(self.native_entry.get().strip() or self.native_var.get()))
        target_var = tk.StringVar(value=(self.target_entry.get().strip() or self.target_var.get()))

        tb.Label(frm, text="Button name").grid(row=0, column=0, sticky=W, pady=(0,4))
        tb.Entry(frm, textvariable=name_var, width=28).grid(row=0, column=1, sticky=EW, padx=(8,0), pady=(0,4))

        tb.Label(frm, text="Native (WIDTHxHEIGHT)").grid(row=1, column=0, sticky=W)
        tb.Entry(frm, textvariable=native_var, width=20).grid(row=1, column=1, sticky=EW, padx=(8,0), pady=(2,4))

        tb.Label(frm, text="Target (WIDTHxHEIGHT)").grid(row=2, column=0, sticky=W)
        tb.Entry(frm, textvariable=target_var, width=20).grid(row=2, column=1, sticky=EW, padx=(8,0), pady=(2,8))

        def use_current():
            native_cur = (self.native_entry.get().strip() or self.native_var.get().strip())
            target_cur = (self.target_entry.get().strip() or self.target_var.get().strip())
            native_var.set(native_cur); target_var.set(target_cur)

        tb.Button(frm, text="Use current inputs", bootstyle=SECONDARY, command=use_current)\
            .grid(row=3, column=0, columnspan=2, sticky=W, pady=(0,8))

        btns = tb.Frame(frm); btns.grid(row=4, column=0, columnspan=2, sticky=E)
        def add_and_close():
            name = name_var.get().strip()
            native = native_var.get().strip()
            target = target_var.get().strip()
            if not name:
                messagebox.showerror("Add Quick Button", "Please enter a button name."); return
            try:
                parse_whx(native); parse_whx(target)
            except ValueError as e:
                messagebox.showerror("Add Quick Button", str(e)); return
            self.presets.append({"name": name, "native": native, "target": target})
            self._save_presets(); self._render_quick_buttons(); top.destroy()

        tb.Button(btns, text="Cancel", bootstyle=SECONDARY, command=top.destroy).pack(side=RIGHT, padx=6)
        tb.Button(btns, text="Add", bootstyle=SUCCESS, command=add_and_close).pack(side=RIGHT)

        top.grab_set(); top.transient(self)

    def _open_manage_presets(self):
        top = tb.Toplevel(self)
        top.title("Manage Quick Buttons")
        top.geometry("420x320")
        frm = tb.Frame(top, padding=12); frm.pack(fill=BOTH, expand=YES)
        frm.rowconfigure(1, weight=1); frm.columnconfigure(0, weight=1)

        tb.Label(frm, text="Your quick buttons").grid(row=0, column=0, sticky=W)

        lb = tk.Listbox(frm, selectmode=tk.SINGLE); lb.grid(row=1, column=0, sticky=NSEW, pady=(6,6))
        for p in self.presets:
            lb.insert(tk.END, f"{p['name']}   [{p['native']} → {p['target']}]")

        btns = tb.Frame(frm); btns.grid(row=2, column=0, sticky=E)

        def remove_sel():
            i = lb.curselection()
            if not i: return
            idx = i[0]
            del self.presets[idx]
            self._save_presets(); self._render_quick_buttons()
            lb.delete(idx)

        def move(up=True):
            i = lb.curselection()
            if not i: return
            idx = i[0]; new = idx-1 if up else idx+1
            if new < 0 or new >= len(self.presets): return
            self.presets[idx], self.presets[new] = self.presets[new], self.presets[idx]
            self._save_presets(); self._render_quick_buttons()
            lb.delete(0, tk.END)
            for p in self.presets:
                lb.insert(tk.END, f"{p['name']}   [{p['native']} → {p['target']}]")
            lb.selection_set(new)

        tb.Button(btns, text="Up", bootstyle=SECONDARY, command=lambda: move(True)).pack(side=LEFT, padx=4)
        tb.Button(btns, text="Down", bootstyle=SECONDARY, command=lambda: move(False)).pack(side=LEFT, padx=4)
        tb.Button(btns, text="Remove", bootstyle=DANGER, command=remove_sel).pack(side=LEFT, padx=8)
        tb.Button(btns, text="Close", bootstyle=SUCCESS, command=top.destroy).pack(side=LEFT)

        top.grab_set(); top.transient(self)

    # Generic utilities
    def _log(self, msg: str, tag: str | None = None):
        """Log a message with optional color tagging.
        
        Tags: success (green), error (red), warning (yellow), info (blue), muted (gray), highlight (pink/bold)
        Auto-detects tag if not specified based on message content.
        """
        if not msg.endswith("\n"):
            msg += "\n"
        
        # Auto-detect tag based on message content if not specified
        if tag is None:
            msg_lower = msg.lower()
            if any(x in msg for x in ["[!]", "Error:", "Failed", "✖"]):
                tag = "error"
            elif any(x in msg_lower for x in ["✔", "success", "complete", "done", "updated", "saved"]):
                tag = "success"
            elif any(x in msg_lower for x in ["warning", "skip", "not found", "missing"]):
                tag = "warning"
            elif any(x in msg for x in ["->", "Detected", "Base config:", "User folder:", "Planned"]):
                tag = "info"
        
        if tag:
            self.output.insert(tk.END, msg, tag)
        else:
            self.output.insert(tk.END, msg)
        
        self.output.see(tk.END)
        self.update_idletasks()

    def _clear_log(self):
        self.output.delete("1.0", tk.END)

    def _copy_log(self):
        txt = self.output.get("1.0", tk.END)
        self.clipboard_clear(); self.clipboard_append(txt)

    def _save_log(self):
        p = filedialog.asksaveasfilename(
            title="Save log", defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("All files", "*.*")],
            initialfile=f"valorant_true_stretch_log_{_timestamp()}.txt",
        )
        if p:
            write_text(Path(p), self.output.get("1.0", tk.END))

    def _set_status(self, text: str, style=SECONDARY, busy=False):
        self.status.configure(text=text, bootstyle=style)
        try:
            self.prog.start(12) if busy else self.prog.stop()
        except Exception:
            pass
        self.update_idletasks()

    def _parse_inputs(self):
        native = (self.native_entry.get().strip() or self.native_var.get().strip())
        target = (self.target_entry.get().strip() or self.target_var.get().strip())
        try:
            nx, ny = parse_whx(native)
            tx, ty = parse_whx(target)
            return nx, ny, tx, ty
        except ValueError as e:
            messagebox.showerror("Input Error", str(e))
            return None

    def _get_targets_and_check(self, nx, ny, force=False):
        base = Path(self.cfg_base_var.get().strip() or get_base_config_dir())
        winclient = base / "WindowsClient"
        gus_root = winclient / "GameUserSettings.ini"
        if not gus_root.is_file():
            raise RuntimeError(
                "Missing GameUserSettings.ini in WindowsClient.\nLaunch VALORANT once (native Fullscreen+Fill), then close."
            )
        root_lines = read_lines(gus_root)
        ok, bad_key, bad_val = native_check_ok(root_lines, nx, ny)
        if not ok and not force:
            self._log(f"[!] Native check failed on {gus_root}", tag="error")
            self._log(f"    Expected {bad_key} to match native {nx}x{ny} / flags False. Got '{bad_val}'.", tag="error")
            self._log("    -> Open VALORANT on Fullscreen+Fill at native, then close and rerun.", tag="warning")
            self._set_status("Native check failed", DANGER)
            return None
        elif not ok and force:
            self._log(f"[!] Native check failed but continuing (--force). Key {bad_key} got '{bad_val}'", tag="warning")

        last_user = get_last_known_user(winclient)
        user_dir = find_user_folder(base, last_user) if last_user else None

        self._log(f"Base config: {base}", tag="info")
        self._log(f"LastKnownUser: {last_user or '??'}", tag="info")
        self._log(f"User folder: {user_dir if user_dir else 'NOT FOUND (will still update root)'}", 
                tag="info" if user_dir else "warning")

        targets = [(gus_root, "Root WindowsClient/GameUserSettings.ini")]
        if user_dir:
            targets += [
                (user_dir / "WindowsClient" / "GameUserSettings.ini", f"{user_dir.name}/WindowsClient/GameUserSettings.ini"),
                (user_dir / "Windows" / "GameUserSettings.ini", f"{user_dir.name}/Windows/GameUserSettings.ini"),
            ]
        return targets

    def _run_async(self, fn):
        t = threading.Thread(target=fn, daemon=True); t.start()

    #native detect + desktop change
    def _detect_native(self):
        res = detect_primary_resolution()
        if not res:
            messagebox.showerror("Detect native", "Could not detect screen resolution.")
            return
        w, h = res
        wh = f"{w}x{h}"
        self.native_entry.delete(0, tk.END)
        self.native_entry.insert(0, wh)
        self._log(f"Detected native resolution: {wh}", tag="success")

    # Actions
    def preflight(self, *_):
        def _run():
            self._clear_log()
            self._set_status("Verifying configuration...", INFO, busy=True)
            parsed = self._parse_inputs()
            if not parsed:
                self._set_status("Invalid input", DANGER, busy=False); return
            nx, ny, tx, ty = parsed
            try:
                targets = self._get_targets_and_check(nx, ny, force=self.force_var.get())
                if targets is None:
                    self._set_status("Native check failed", DANGER, busy=False); return
                self._log("\nPlanned updates:", tag="info")
                for p, lbl in targets: 
                    self._log(f" - {lbl} -> {p}", tag="muted")
                self._log("\nVerification complete.", tag="success")
                self._set_status("Verification complete", SUCCESS, busy=False)
            except Exception as e:
                self._log(f"Error: {e}", tag="error")
                self._set_status("Error occurred", DANGER, busy=False)
        self._run_async(_run)


    def dry_run(self, *_):
        def _run():
            self._clear_log()
            self._set_status("Running preview...", INFO, busy=True)
            parsed = self._parse_inputs()
            if not parsed:
                self._set_status("Invalid input", DANGER, busy=False); return
            nx, ny, tx, ty = parsed
            try:
                targets = self._get_targets_and_check(nx, ny, force=self.force_var.get())
                if targets is None:
                    self._set_status("Native check failed", DANGER, busy=False); return
                self._log("\nPlanned updates:", tag="info")
                for p, lbl in targets: 
                    self._log(f" - {lbl} -> {p}", tag="muted")
                for p, lbl in targets:
                    if p.exists():
                        process_gus(p, tx, ty, apply_changes=False, label=lbl, log_func=self._log,
                                    backup_dir=self._backup_root_if_enabled())
                    else:
                        self._log(f"- Not found: {lbl} -> {p} (skipped)", tag="warning")
                self._log("\nDry run complete.", tag="success")
                self._set_status("Preview complete", SUCCESS, busy=False)
            except Exception as e:
                self._log(f"Error: {e}", tag="error")
                self._set_status("Error occurred", DANGER, busy=False)
        self._run_async(_run)

    def apply(self, *_):
        result = messagebox.askquestion(
            "Confirm",
            "This will modify VALORANT configuration files.\n\n"
            "Make sure VALORANT is completely closed.\n(Riot Client can remain open)\n\nProceed?",
            icon="warning",
        )
        if result != "yes": return
        def _run():
            self._clear_log()
            self._set_status("Applying configuration...", INFO, busy=True)
            parsed = self._parse_inputs()
            if not parsed:
                self._set_status("Invalid input", DANGER, busy=False); return
            nx, ny, tx, ty = parsed
            try:
                targets = self._get_targets_and_check(nx, ny, force=self.force_var.get())
                if targets is None:
                    self._set_status("Native check failed", DANGER, busy=False); return
                self._log("\nPlanned updates:", tag="info")
                for p, lbl in targets: 
                    self._log(f" - {lbl} -> {p}", tag="muted")
                for p, lbl in targets:
                    if p.exists():
                        process_gus(p, tx, ty, apply_changes=True, label=lbl, log_func=self._log,
                                    backup_dir=self._backup_root_if_enabled())
                    else:
                        self._log(f"- Not found: {lbl} -> {p} (skipped)", tag="warning")

                # NEW: optionally change Windows desktop resolution
                if self.change_desktop_var.get():
                    self._log(f"\nChanging Windows desktop to {tx}x{ty} ...", tag="info")
                    ok, msg = change_desktop_resolution(tx, ty)
                    self._log(("✔ " if ok else "✖ ") + msg, tag="success" if ok else "error")

                self._log("\nDone.", tag="highlight")
                self._log("Next steps:", tag="info")
                self._log(f"  1) Ensure your Windows desktop resolution is {tx}x{ty} (toggled above can do this).")
                self._log("  2) Launch VALORANT.")
                self._set_status("Configuration applied successfully", SUCCESS, busy=False)
            except Exception as e:
                self._log(f"Error: {e}", tag="error")
                self._set_status("Error occurred", DANGER, busy=False)
        self._run_async(_run)

    def _backup_root_if_enabled(self) -> Path | None:
        if not self.backup_var.get(): return None
        root = Path(self.backup_dir_var.get().strip())
        root.mkdir(parents=True, exist_ok=True)
        return root

    # ----- Paths helpers -----
    def _detect_base_config_dir(self):
        try:
            base = get_base_config_dir()
            self.cfg_base_var.set(str(base))
            self._log(f"Config base detected: {base}", tag="info")
        except Exception as e:
            self._log(f"[!] Could not detect config base: {e}", tag="error")
    def _browse_cfg_dir(self):
        p = filedialog.askdirectory(title="Select VALORANT Config Base Folder")
        if p: self.cfg_base_var.set(p)

    def _open_cfg_dir(self):
        p = self.cfg_base_var.get().strip()
        if p and Path(p).exists(): os.startfile(p)

    def _browse_backup_dir(self):
        p = filedialog.askdirectory(title="Select Backups Folder", initialdir=self.backup_dir_var.get())
        if p: self.backup_dir_var.set(p)

    def _open_backup_dir(self):
        p = self.backup_dir_var.get().strip()
        Path(p).mkdir(parents=True, exist_ok=True)
        os.startfile(p)

if __name__ == "__main__":
    app = App()
    app.mainloop()
