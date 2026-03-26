# Required: pip install mss opencv-python numpy keyboard psutil requests rich pywin32 PyQt5
# Run as Administrator!
import win32gui
import win32process
import os
import psutil
import time
import threading
import shutil
import tempfile
import zipfile
import re
import sys
import subprocess
import webbrowser
from ctypes import *
from pathlib import Path
import requests
import keyboard
import numpy as np
import cv2
import mss
import winsound
from rich.console import Console
from rich.theme import Theme
from rich.live import Live
from rich.text import Text
from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QMessageBox
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QFont

# ────────────────────────────────────────────────
# Rich Console Setup
# ────────────────────────────────────────────────
theme = Theme({
    "time": "dim white", "info": "cyan", "success": "green bold",
    "warn": "yellow bold", "error": "red bold", "path": "magenta",
    "inject": "bright_magenta", "state": "bright_blue", "key": "yellow bold",
})
console = Console(theme=theme, highlight=False, soft_wrap=True)

# Rainbow helpers
RAINBOW = [
    "#ff0000", "#ff4000", "#ff7f00", "#ffbf00", "#ffff00",
    "#c0ff00", "#80ff00", "#40ff00", "#00ff00", "#00ff40",
    "#00ff80", "#00ffbf", "#00ffff", "#00bfff", "#0080ff",
    "#0040ff", "#0000ff", "#4000ff", "#8000ff", "#bf00ff",
    "#ff00ff", "#ff00bf", "#ff0080", "#ff0040",
]

def _rainbow_rich(text: str, offset: int = 0) -> Text:
    rt = Text()
    for i, ch in enumerate(text):
        rt.append(ch, style=RAINBOW[(i + offset) % len(RAINBOW)])
    return rt

def log(msg: str, rainbow: bool = False, style: str = "info") -> None:
    ts = time.strftime("%H:%M:%S")
    prefix = f"[{ts}] "
    if not rainbow:
        console.print(f"[{style}]{prefix}{msg}[/{style}]")
        return
    full = prefix + msg
    with Live(console=console, refresh_per_second=15, transient=True) as live:
        for frame in range(10):
            live.update(_rainbow_rich(full, offset=frame * 2))
            time.sleep(0.07)
    console.print(f"[{style}]{prefix}{msg}[/{style}]")

# ────────────────────────────────────────────────
# Version & Update Settings
# ────────────────────────────────────────────────
CURRENT_VERSION = "Beta-0.7"
GITHUB_API_URL = "https://api.github.com/repos/jellowrld/tfdnjector/releases/latest"
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0"}

# ────────────────────────────────────────────────
# Auto Update Checker (Fixed - must run after QApplication)
# ────────────────────────────────────────────────
def check_for_updates():
    log("Checking for updates on GitHub...", style="info")
    try:
        r = requests.get(GITHUB_API_URL, headers=HTTP_HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()

        latest_tag = data.get("tag_name", "").lstrip("v")
        release_url = data.get("html_url", "https://github.com/jellowrld/tfdnjector/releases")

        if not latest_tag:
            return

        if latest_tag != CURRENT_VERSION:
            log(f"New version available: {latest_tag} (you have {CURRENT_VERSION})", style="warn")
            
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("Update Available")
            msg.setText(f"A new version is available!\n\nCurrent: {CURRENT_VERSION}\nLatest: {latest_tag}")
            msg.setInformativeText("Click OK to open the download page.\n\nThe injector will close after opening the browser.")
            msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)

            if msg.exec_() == QMessageBox.Ok:
                log("Opening download page in browser...", style="success")
                webbrowser.open(release_url)
                time.sleep(1.0)          # Small delay so user sees the log
                log("Closing injector so you can run the new version...", style="info")
                sys.exit(0)              # ← This exits cleanly after opening browser
            else:
                log("Update skipped by user", style="warn")
        else:
            log(f"You are running the latest version ({CURRENT_VERSION})", style="success")
            
    except Exception as e:
        log(f"Update check failed: {e}", style="dim")

# ────────────────────────────────────────────────
# Constants
# ────────────────────────────────────────────────
STEAM_APP_ID = 2074920
PROCESS_NAME = "m1-win64-shipping.exe"
EAC_ZIP_URL = "https://github.com/jellowrld/oldeac/archive/refs/heads/main.zip"
PAGE_READWRITE = 0x04
PROCESS_ALL_ACCESS = 0x1F0FFF
VIRTUAL_MEM = 0x1000 | 0x2000

HUD_AREA = {"top": 0, "left": 0, "width": 1920, "height": 1080}
PRESS_COOLDOWN = 0.5

# ────────────────────────────────────────────────
# Load configurable Confidence Threshold
# ────────────────────────────────────────────────
def load_confidence_threshold() -> float:
    cfg_path = Path("confidence.cfg")
    default_value = 0.92
   
    if not cfg_path.exists():
        try:
            with open(cfg_path, "w", encoding="utf-8") as f:
                f.write("# ===============================================\n")
                f.write("# V & Q Auto-Press Confidence Threshold\n")
                f.write("# ===============================================\n")
                f.write("# Edit the value below (recommended range: 0.80 - 1.00)\n")
                f.write("# Higher = stricter / fewer false positives\n")
                f.write("# Lower  = more sensitive\n\n")
                f.write(f"confidence = {default_value}\n")
            log(f"✓ Created default confidence.cfg with value {default_value}", style="success")
        except Exception as e:
            log(f"Failed to create confidence.cfg: {e}", style="error")
            return default_value
   
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.search(r"confidence\s*=\s*([0-9]*\.?[0-9]+)", content)
        if match:
            value = float(match.group(1))
            value = max(0.80, min(1.00, value))
            log(f"Loaded confidence threshold: {value:.3f} from confidence.cfg", style="info")
            return value
        else:
            log("Invalid confidence.cfg, using default 0.92", style="warn")
            return default_value
    except Exception as e:
        log(f"Failed to read confidence.cfg: {e} → using default 0.92", style="warn")
        return default_value

MATCH_THRESHOLD = load_confidence_threshold()

# ────────────────────────────────────────────────
# Smart Template Loader
# ────────────────────────────────────────────────
def load_templates(prefix: str) -> list[np.ndarray]:
    template_dir = Path("templates")
    template_dir.mkdir(exist_ok=True)
   
    github_api_url = "https://api.github.com/repos/jellowrld/tfdnjector/contents/templates"
   
    log(f"Checking for {prefix} templates...", style="info")
   
    templates = []
    try:
        r = requests.get(github_api_url, headers=HTTP_HEADERS, timeout=15)
        r.raise_for_status()
        files = r.json()
       
        template_files = [f for f in files
                         if f.get("type") == "file"
                         and f["name"].startswith(prefix)
                         and f["name"].endswith(".png")]
       
        if not template_files:
            log(f"No {prefix}*.png files found on GitHub", style="error")
            return []
       
        for file_info in template_files:
            name = file_info["name"]
            download_url = file_info["download_url"]
            remote_size = file_info.get("size", 0)
            local_path = template_dir / name
           
            needs_download = True
            if local_path.exists():
                if local_path.stat().st_size == remote_size:
                    needs_download = False
                    log(f"✓ Up to date: {name}", style="dim")
                else:
                    log(f"→ {name} changed, re-downloading...", style="warn")
           
            if needs_download:
                try:
                    log(f"Downloading: {name}...", style="info")
                    resp = requests.get(download_url, headers=HTTP_HEADERS, timeout=20)
                    resp.raise_for_status()
                    local_path.write_bytes(resp.content)
                    log(f"✓ Downloaded/Updated: {name}", style="success")
                except Exception as e:
                    log(f"✗ Failed to download {name}: {e}", style="error")
                    continue
           
            img = cv2.imread(str(local_path))
            if img is not None:
                templates.append(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
                log(f"Loaded: {name} ({img.shape[1]}×{img.shape[0]})", style="dim")
            else:
                log(f"✗ Failed to load {name}", style="error")
               
    except Exception as e:
        log(f"GitHub check failed: {e}", style="warn")
        log(f"Falling back to local {prefix} templates...", style="warn")
        for local_path in sorted(template_dir.glob(f"{prefix}*.png")):
            img = cv2.imread(str(local_path))
            if img is not None:
                templates.append(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
   
    log(f"Ready with {len(templates)} {prefix} template(s)", style="success")
    return templates

# ────────────────────────────────────────────────
# Core helpers
# ────────────────────────────────────────────────
def find_dll() -> str:
    dlls = list(Path.cwd().glob("*.dll"))
    if not dlls:
        log("No .dll found in current folder.", rainbow=True, style="error")
        sys.exit(1)
    if len(dlls) > 1:
        log(f"Multiple DLLs found → using first: {dlls[0].name}", style="warn")
    path = str(dlls[0].absolute())
    log(f"Using DLL → [path]{path}[/path]")
    return path

def is_game_foreground(target_pid: int) -> bool:
    try:
        hwnd = win32gui.GetForegroundWindow()
        if hwnd == 0: return False
        _, fg_pid = win32process.GetWindowThreadProcessId(hwnd)
        if fg_pid != target_pid: return False
        if win32gui.IsIconic(hwnd): return False
        return True
    except:
        return False

def find_game_folder() -> Path | None:
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
        winreg.CloseKey(key)
        steam_path = Path(steam_path)
        def _check_manifest(base: Path) -> Path | None:
            man = base / "steamapps" / f"appmanifest_{STEAM_APP_ID}.acf"
            if not man.exists(): return None
            with open(man, "r", encoding="utf-8") as f:
                m = re.search(r'"installdir"\s+"(.+?)"', f.read())
            if m:
                return base / "steamapps" / "common" / m.group(1)
            return None
        path = _check_manifest(steam_path)
        if path:
            log(f"Game found (primary): [path]{path}[/path]")
            return path
        lib_vdf = steam_path / "steamapps" / "libraryfolders.vdf"
        if lib_vdf.exists():
            with open(lib_vdf, "r", encoding="utf-8") as f:
                for p_str in re.findall(r'"path"\s+"(.+?)"', f.read()):
                    path = _check_manifest(Path(p_str))
                    if path:
                        log(f"Game found (library): [path]{path}[/path]")
                        return path
    except Exception as e:
        log(f"Cannot locate game folder: {e}", style="error")
    return None

def update_eac_files(game_folder: Path) -> None:
    log(f"Downloading EAC bypass files: {EAC_ZIP_URL}", rainbow=True)
    try:
        r = requests.get(EAC_ZIP_URL, stream=True, timeout=20, headers=HTTP_HEADERS)
        if r.status_code != 200:
            log(f"Download failed (HTTP {r.status_code})", style="error")
            return
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            zipf = tmp / "oldeac.zip"
            with open(zipf, "wb") as f:
                for chunk in r.iter_content(16384):
                    f.write(chunk)
            with zipfile.ZipFile(zipf) as z:
                z.extractall(tmp)
            src = next(tmp.glob("oldeac-*"), None)
            if not src:
                log("Extraction folder not found", style="error")
                return
            log("Copying files to game folder...", rainbow=True)
            for item in src.iterdir():
                dst = game_folder / item.name
                try:
                    if dst.exists():
                        shutil.rmtree(dst, ignore_errors=True) if dst.is_dir() else dst.unlink()
                    if item.is_dir():
                        shutil.copytree(item, dst, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, dst)
                    log(f" copied: {item.name}", style="success")
                except Exception as ex:
                    log(f" skip {item.name} → {ex}", style="warn")
        log("EAC files updated", style="success")
    except Exception as e:
        log(f"EAC update failed: {e}", style="error")

def clean_game_folders(game_folder: Path) -> None:
    log("Starting cleanup of logs / crashes / webcache / pipeline / BlackCipher...", rainbow=True)
    user = Path(os.environ.get("USERPROFILE", ""))
    base = user / "AppData" / "Local" / "M1" / "Saved"
    if not base.exists():
        log("Saved directory not found.", style="warn")
        return
    static_folders = [
        base / "Config" / "CrashReportClient",
        base / "Logs",
        base / "Crashes",
    ]
    for folder in static_folders:
        if folder.exists():
            try:
                shutil.rmtree(folder, ignore_errors=True)
                log(f" removed folder: {folder.name}", style="success")
            except Exception as e:
                log(f" failed removing {folder.name} → {e}", style="warn")
    for item in base.iterdir():
        if item.is_dir() and item.name.lower().startswith("webcache_"):
            try:
                shutil.rmtree(item, ignore_errors=True)
                log(f" removed cache: {item.name}", style="success")
            except Exception as e:
                log(f" failed removing {item.name} → {e}", style="warn")
    pipe_file = base / "M1_PCD3D_SM6.upipelinecache"
    if pipe_file.exists():
        try:
            pipe_file.unlink()
            log(" removed pipeline cache", style="success")
        except Exception as e:
            log(f" failed removing pipeline cache → {e}", style="warn")
    bc = game_folder / "M1" / "Binaries" / "Win64" / "BlackCipher"
    if bc.exists():
        for pat in ("*.log", "*.dump"):
            for f in bc.glob(pat):
                try:
                    f.unlink()
                    log(f" deleted: {f.name}", style="success")
                except Exception:
                    pass
    log("Cleanup finished ✔", style="success")

def launch_game() -> None:
    log("Launching game via Steam...", rainbow=True)
    subprocess.Popen(
        ["cmd", "/c", "start", f"steam://run/{STEAM_APP_ID}"],
        shell=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

# ────────────────────────────────────────────────
# DLL Injection
# ────────────────────────────────────────────────
kernel32 = windll.kernel32
kernel32.OpenProcess.argtypes = [c_ulong, c_bool, c_ulong]
kernel32.OpenProcess.restype = c_void_p
kernel32.VirtualAllocEx.argtypes = [c_void_p, c_void_p, c_size_t, c_ulong, c_ulong]
kernel32.VirtualAllocEx.restype = c_void_p
kernel32.WriteProcessMemory.argtypes = [c_void_p, c_void_p, c_void_p, c_size_t, POINTER(c_size_t)]
kernel32.WriteProcessMemory.restype = c_bool
kernel32.GetModuleHandleW.argtypes = [c_wchar_p]
kernel32.GetModuleHandleW.restype = c_void_p
kernel32.GetProcAddress.argtypes = [c_void_p, c_char_p]
kernel32.GetProcAddress.restype = c_void_p
kernel32.CreateRemoteThread.argtypes = [c_void_p, c_void_p, c_size_t, c_void_p, c_void_p, c_ulong, POINTER(c_ulong)]
kernel32.CreateRemoteThread.restype = c_void_p
kernel32.CloseHandle.argtypes = [c_void_p]
kernel32.CloseHandle.restype = c_bool

def inject_dll(dll_path: str, pid: int) -> bool:
    log(f"Injecting into PID {pid}...", rainbow=True, style="inject")
    path_bytes = (dll_path + "\0").encode("utf-16-le")
    size = len(path_bytes)
    h_proc = None
    try:
        h_proc = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        if not h_proc:
            log("OpenProcess failed", style="error")
            return False
        addr = kernel32.VirtualAllocEx(h_proc, None, size, VIRTUAL_MEM, PAGE_READWRITE)
        if not addr:
            log("VirtualAllocEx failed", style="error")
            return False
        written = c_size_t()
        if not kernel32.WriteProcessMemory(h_proc, addr, path_bytes, size, byref(written)):
            log("WriteProcessMemory failed", style="error")
            return False
        h_k32 = kernel32.GetModuleHandleW("kernel32.dll")
        loadlib = kernel32.GetProcAddress(h_k32, b"LoadLibraryW")
        if not loadlib:
            log("LoadLibraryW not found", style="error")
            return False
        tid = c_ulong()
        h_th = kernel32.CreateRemoteThread(h_proc, None, 0, loadlib, addr, 0, byref(tid))
        if not h_th:
            log("CreateRemoteThread failed", style="error")
            return False
        log(f"Injected successfully (TID {tid.value})", style="success")
        kernel32.CloseHandle(h_th)
        return True
    except Exception as e:
        log(f"Injection exception: {e}", style="error")
        return False
    finally:
        if h_proc:
            kernel32.CloseHandle(h_proc)

# ────────────────────────────────────────────────
# PyQt5 Overlay - Game UI Style
# ────────────────────────────────────────────────
class OverlaySignals(QObject):
    update_signal = pyqtSignal(str)

class OverlayWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.signals = OverlaySignals()
        self.signals.update_signal.connect(self._update_text)
       
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setGeometry(1580, 40, 380, 115)
       
        self.label = QLabel(self)
        self.label.setFont(QFont("Consolas", 20, QFont.Bold))
        self.label.setAlignment(Qt.AlignLeft)
        self.label.setStyleSheet("""
            color: #ffffff;
            background: rgba(0, 0, 0, 160);
            padding: 10px 16px;
            border: 1px solid rgba(255, 255, 255, 40);
            border-radius: 6px;
        """)
        self.label.move(14, 12)
       
        self.help_label = QLabel("F1 = Toggle Q | F2 = Toggle V (draggable)", self)
        self.help_label.setFont(QFont("Arial", 9))
        self.help_label.setStyleSheet("color: #aaaaaa; background: transparent;")
        self.help_label.move(18, 82)
       
        self.old_pos = None
        self._update_text("Q AUTO: ENABLED\nV AUTO: ENABLED")

    def _update_text(self, text: str):
        q_line, v_line = text.split('\n')
        q_status = q_line.split(": ")[1]
        v_status = v_line.split(": ")[1]
       
        q_color = "#00ff88" if q_status == "ENABLED" else "#ff6666"
        v_color = "#00ff88" if v_status == "ENABLED" else "#ff6666"
       
        styled = f'<font color="#ffffff">Q AUTO: </font><font color="{q_color}">{q_status}</font><br>' \
                 f'<font color="#ffffff">V AUTO: </font><font color="{v_color}">{v_status}</font>'
       
        self.label.setText(styled)
        self.label.adjustSize()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if self.old_pos is not None:
            delta = event.globalPos() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()

# ────────────────────────────────────────────────
# Main Injector Class
# ────────────────────────────────────────────────
class Injector:
    def __init__(self, dll_path: str, game_folder: Path):
        self.dll_path = dll_path
        self.game_folder = game_folder
        self._injected = False
        self._lock = threading.Lock()
        self._scanner_thread = None
        self.v_enabled = True
        self.q_enabled = True
        self.app = QApplication.instance()
        self.overlay = OverlayWindow()
        self.overlay.show()
        self._add_hotkeys()

    def _add_hotkeys(self):
        keyboard.add_hotkey('f1', self._toggle_q)
        keyboard.add_hotkey('f2', self._toggle_v)
        log("F1 = Toggle Q Auto | F2 = Toggle V Auto", style="key")

    def _toggle_v(self):
        self.v_enabled = not self.v_enabled
        self._update_overlay()
        status = "ENABLED" if self.v_enabled else "DISABLED"
        log(f"V Auto {status}", rainbow=True, style="success" if self.v_enabled else "warn")
        winsound.Beep(900 if self.v_enabled else 400, 180)

    def _toggle_q(self):
        self.q_enabled = not self.q_enabled
        self._update_overlay()
        status = "ENABLED" if self.q_enabled else "DISABLED"
        log(f"Q Auto {status}", rainbow=True, style="success" if self.q_enabled else "warn")
        winsound.Beep(1100 if self.q_enabled else 500, 180)

    def _update_overlay(self):
        q_status = "ENABLED" if self.q_enabled else "DISABLED"
        v_status = "ENABLED" if self.v_enabled else "DISABLED"
        full_text = f"Q AUTO: {q_status}\nV AUTO: {v_status}"
        self.overlay.signals.update_signal.emit(full_text)

    @staticmethod
    def _get_game_pid() -> int | None:
        for p in psutil.process_iter(["pid", "name"]):
            if p.info.get("name", "").lower() == PROCESS_NAME.lower():
                return p.info["pid"]
        return None

    def _start_scanner(self):
        if self._scanner_thread is not None and self._scanner_thread.is_alive():
            return

        def scanner_loop():
            v_templates = load_templates("hex_v_template")
            q_templates = load_templates("hex_q_template")

            # Auto-disable if no templates found
            if not v_templates:
                self.v_enabled = False
                log("No V templates loaded → V Auto has been DISABLED", style="warn")
            if not q_templates:
                self.q_enabled = False
                log("No Q templates loaded → Q Auto has been DISABLED", style="warn")

            self._update_overlay()

            if not v_templates and not q_templates:
                console.print("[red bold]No templates available at all → scanner exiting[/red bold]")
                return

            last_v = 0.0
            last_q = 0.0

            while True:
                with self._lock:
                    if not self._injected:
                        console.print("[yellow]Game no longer running → scanner stopping[/yellow]")
                        break

                if not (self.v_enabled or self.q_enabled):
                    time.sleep(0.3)
                    continue

                pid = self._get_game_pid()
                if not pid or not is_game_foreground(pid):
                    time.sleep(0.3)
                    continue

                with mss.mss() as sct:
                    screenshot = sct.grab(HUD_AREA)
                screen_rgb = cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGRA2RGB)

                now = time.time()

                if self.v_enabled and v_templates and now - last_v >= PRESS_COOLDOWN:
                    for template in v_templates:
                        if template.shape[0] > screen_rgb.shape[0] or template.shape[1] > screen_rgb.shape[1]:
                            continue
                        result = cv2.matchTemplate(screen_rgb, template, cv2.TM_CCOEFF_NORMED)
                        _, max_val, _, _ = cv2.minMaxLoc(result)
                        if max_val >= MATCH_THRESHOLD:
                            keyboard.press_and_release('v')
                            last_v = now
                            console.print(f"[green]V pressed (match ≥ {max_val:.3f})[/green]")
                            break

                if self.q_enabled and q_templates and now - last_q >= PRESS_COOLDOWN:
                    for template in q_templates:
                        if template.shape[0] > screen_rgb.shape[0] or template.shape[1] > screen_rgb.shape[1]:
                            continue
                        result = cv2.matchTemplate(screen_rgb, template, cv2.TM_CCOEFF_NORMED)
                        _, max_val, _, _ = cv2.minMaxLoc(result)
                        if max_val >= MATCH_THRESHOLD:
                            keyboard.press_and_release('q')
                            last_q = now
                            console.print(f"[cyan]Q pressed (match ≥ {max_val:.3f})[/cyan]")
                            break

                time.sleep(0.12)

            console.print("[dim]Scanner thread ended[/dim]")

        self._scanner_thread = threading.Thread(target=scanner_loop, daemon=True)
        self._scanner_thread.start()
        console.print("[cyan]V + Q scanner thread started[/cyan]")

    def _full_sequence(self):
        update_eac_files(self.game_folder)
        clean_game_folders(self.game_folder)
        launch_game()

    def monitor_loop(self):
        while True:
            pid = self._get_game_pid()
            with self._lock:
                if pid and not self._injected:
                    log(f"Game detected (PID {pid}) → injecting...", rainbow=True)
                    if inject_dll(self.dll_path, pid):
                        self._injected = True
                        self._start_scanner()
                elif not pid and self._injected:
                    log("Game closed → state reset", style="state")
                    self._injected = False
            time.sleep(1.3)

    def keyboard_loop(self):
        log("Press [yellow bold]I[/] when game is CLOSED to re-do EAC + clean + launch", style="key")
        def on_i():
            if self._get_game_pid() is not None:
                log("Game still running → ignoring I press", style="warn")
            else:
                log("I pressed → full preparation sequence...", rainbow=True)
                self._full_sequence()
        keyboard.add_hotkey("i", on_i)
        keyboard.wait()

    def start(self):
        self._full_sequence()
        threading.Thread(target=self.monitor_loop, daemon=True).start()
        threading.Thread(target=self.keyboard_loop, daemon=True).start()
        log("Injector running. Press Ctrl+C to exit.", style="state")
        log(f"Current confidence threshold: {MATCH_THRESHOLD:.3f} (edit confidence.cfg to change)", style="info")
        sys.exit(self.app.exec_())

# ────────────────────────────────────────────────
# Entry point - FIXED
# ────────────────────────────────────────────────
if __name__ == "__main__":
    console.rule("Jell's Auto-Injector + V & Q Auto-Press", style="bright_blue on black")
    log("Starting...", rainbow=True)

    # Create QApplication FIRST - this fixes the QWidget error
    app = QApplication(sys.argv) if QApplication.instance() is None else QApplication.instance()

    # Now safe to show message boxes
    check_for_updates()

    dll_path = find_dll()
    game_folder = find_game_folder()
    if not game_folder:
        log("Game folder not found. Exiting.", rainbow=True, style="error")
        sys.exit(1)

    log(f"Game directory → [path]{game_folder}[/path]")
    
    Injector(dll_path, game_folder).start()