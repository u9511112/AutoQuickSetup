import customtkinter as ctk
import json
import os
import sys
import subprocess
import threading
import winreg
import fnmatch
import pyttsx3
import urllib.request
from datetime import datetime
from pathlib import Path

APP_VERSION = "1.0.0"
UPDATE_URL = "https://raw.githubusercontent.com/u9511112/AutoQuickSetup/master/version.json"

# === 路徑設定 ===
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

SOFTWARE_DIR = BASE_DIR / "software"
CATALOG_FILE = BASE_DIR / "software_catalog.json"
CONFIG_DIR = BASE_DIR / "configs"
LOG_DIR = BASE_DIR / "logs"

SKIP_FILES = {"autorun.inf", "Setup.exe"}
SKIP_DIRS = {"Office"}

INSTALL_TIMEOUT = 600  # 10 分鐘

# === 系統優化指令 ===
SYSTEM_TWEAKS = [
    {
        "name": "關閉休眠",
        "description": "釋放硬碟空間，加速開關機",
        "commands": ["powercfg -h off"],
    },
    {
        "name": "高效能電源計畫",
        "description": "關閉自動休眠與螢幕關閉",
        "commands": [
            "powercfg /change standby-timeout-ac 0",
            "powercfg /change monitor-timeout-ac 0",
            "powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",
        ],
    },
    {
        "name": "顯示桌面圖示",
        "description": "顯示我的電腦、使用者資料夾等圖示",
        "commands": [
            'reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\HideDesktopIcons\\NewStartPanel" /v "{20D04FE0-3AEA-1069-A2D8-08002B30309D}" /t REG_DWORD /d 0 /f',
            'reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\HideDesktopIcons\\NewStartPanel" /v "{59031a47-3f72-44a7-89c5-5595fe6b30ee}" /t REG_DWORD /d 0 /f',
            'reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\HideDesktopIcons\\NewStartPanel" /v "{5399E694-6C79-4741-86F1-E240E4E25E33}" /t REG_DWORD /d 0 /f',
            'reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\HideDesktopIcons\\NewStartPanel" /v "{F02C1A0D-BE21-4350-88B0-7367FC96EF3C}" /t REG_DWORD /d 0 /f',
        ],
    },
]


def load_catalog():
    if CATALOG_FILE.exists():
        with open(CATALOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def scan_software():
    """掃描 software/ 資料夾，比對 catalog 產生安裝清單"""
    catalog = load_catalog()
    items = []
    if not SOFTWARE_DIR.exists():
        return items

    for entry in SOFTWARE_DIR.iterdir():
        if entry.name in SKIP_FILES:
            continue
        if entry.is_dir() and entry.name in SKIP_DIRS:
            continue
        if entry.is_dir():
            continue
        if entry.suffix.lower() not in (".exe", ".msi"):
            continue

        matched = None
        for cat in catalog:
            if fnmatch.fnmatch(entry.name, cat["pattern"]):
                matched = cat
                break

        if matched:
            items.append({
                "file": entry.name,
                "path": str(entry),
                "name": matched["name"],
                "description": matched["description"],
                "silent_args": matched["silent_args"],
                "type": matched["type"],
                "requires_config": matched.get("requires_config", False),
            })
        else:
            items.append({
                "file": entry.name,
                "path": str(entry),
                "name": entry.stem,
                "description": "未知軟體",
                "silent_args": "/S" if entry.suffix.lower() == ".exe" else "/quiet /norestart",
                "type": "exe" if entry.suffix.lower() == ".exe" else "msi",
                "requires_config": False,
            })

    items.sort(key=lambda x: x["name"])
    return items


def check_installed(name):
    """透過 Registry 檢查軟體是否已安裝"""
    uninstall_keys = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    ]
    search = name.lower()
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for key_path in uninstall_keys:
            try:
                key = winreg.OpenKey(root, key_path)
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        subkey = winreg.OpenKey(key, subkey_name)
                        try:
                            display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                            if search in display_name.lower():
                                return True
                        except (FileNotFoundError, OSError):
                            pass
                        finally:
                            winreg.CloseKey(subkey)
                    except (FileNotFoundError, OSError):
                        pass
                winreg.CloseKey(key)
            except (FileNotFoundError, OSError):
                pass
    return False


def run_install(item):
    """執行單一軟體安裝，回傳 (success, message)"""
    path = item["path"]
    args = item["silent_args"]
    install_type = item["type"]

    if item.get("requires_config"):
        config_xml = SOFTWARE_DIR / "configuration.xml"
        if not config_xml.exists():
            return False, "需要 configuration.xml 設定檔，已跳過"

    try:
        if install_type == "msi":
            cmd = f'msiexec /i "{path}" {args}'
        else:
            cmd = f'"{path}" {args}'

        result = subprocess.run(
            cmd, shell=True, timeout=INSTALL_TIMEOUT,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if result.returncode == 0:
            return True, "安裝成功"
        elif result.returncode == 3010:
            return True, "安裝成功（需重新開機）"
        else:
            return False, f"安裝失敗（錯誤碼: {result.returncode}）"
    except subprocess.TimeoutExpired:
        return False, "安裝逾時（超過 10 分鐘）"
    except Exception as e:
        return False, f"安裝錯誤: {str(e)}"


def run_system_tweak(tweak):
    """執行系統優化指令"""
    for cmd in tweak["commands"]:
        subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def speak(text):
    """語音通知"""
    try:
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception:
        try:
            ps_cmd = (
                f'powershell -Command "Add-Type -AssemblyName System.Speech; '
                f'(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak(\'{text}\')"'
            )
            subprocess.run(ps_cmd, shell=True, timeout=30)
        except Exception:
            pass


def save_log(results):
    """儲存安裝日誌"""
    LOG_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"install_log_{timestamp}.txt"

    lines = []
    lines.append(f"AutoQuickSetup 安裝日誌")
    lines.append(f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"{'=' * 50}")
    lines.append("")

    success_count = sum(1 for r in results if r["success"])
    fail_count = len(results) - success_count
    lines.append(f"總計: {len(results)} 個項目 | 成功: {success_count} | 失敗: {fail_count}")
    lines.append("")

    for r in results:
        status = "✓" if r["success"] else "✗"
        lines.append(f"  [{status}] {r['name']} — {r['message']}")

    lines.append("")
    lines.append(f"{'=' * 50}")
    lines.append("By: 謝智翔")

    with open(log_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return log_file


# === GUI ===

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AutoQuickSetup - 萬能裝機自動化工具")
        self.geometry("700x820")
        self.resizable(True, True)
        self.minsize(700, 600)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.software_items = scan_software()
        self.software_vars = {}
        self.tweak_vars = {}
        self.installing = False

        self._build_ui()
        threading.Thread(target=self._check_update, daemon=True).start()

    def _build_ui(self):
        # 標題
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(fill="x", padx=20, pady=(15, 5))

        ctk.CTkLabel(
            title_frame, text=f"AutoQuickSetup v{APP_VERSION}",
            font=ctk.CTkFont(size=24, weight="bold")
        ).pack(side="left")

        self.theme_btn = ctk.CTkButton(
            title_frame, text="☀ 淺色", width=80, height=28,
            command=self._toggle_theme
        )
        self.theme_btn.pack(side="right")

        ctk.CTkLabel(
            self, text="萬能裝機自動化工具",
            font=ctk.CTkFont(size=13), text_color="gray"
        ).pack(anchor="w", padx=20)

        # 主要捲動區域
        main_scroll = ctk.CTkScrollableFrame(self, height=480)
        main_scroll.pack(fill="both", expand=True, padx=15, pady=(10, 5))

        # 軟體安裝區
        sw_label = ctk.CTkLabel(
            main_scroll, text="📦 軟體安裝",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        sw_label.pack(anchor="w", padx=5, pady=(5, 8))

        if not self.software_items:
            ctk.CTkLabel(
                main_scroll,
                text="⚠ 請將安裝檔放入 software 資料夾",
                text_color="orange"
            ).pack(anchor="w", padx=20)
        else:
            for item in self.software_items:
                installed = check_installed(item["name"])
                var = ctk.BooleanVar(value=not installed)
                self.software_vars[item["file"]] = var

                row = ctk.CTkFrame(main_scroll, fg_color="transparent")
                row.pack(fill="x", padx=5, pady=2)

                cb = ctk.CTkCheckBox(
                    row, text="", variable=var, width=24,
                    checkbox_width=20, checkbox_height=20
                )
                cb.pack(side="left")

                name_text = item["name"]
                if installed:
                    name_text += "  ✓ 已安裝"

                name_label = ctk.CTkLabel(
                    row, text=name_text,
                    font=ctk.CTkFont(size=14, weight="bold"),
                    text_color="#90EE90" if installed else None
                )
                name_label.pack(side="left", padx=(4, 0))

                desc_label = ctk.CTkLabel(
                    row, text=f"— {item['description']}",
                    font=ctk.CTkFont(size=12),
                    text_color="gray"
                )
                desc_label.pack(side="left", padx=(8, 0))

        # 分隔線
        ctk.CTkFrame(main_scroll, height=2, fg_color="gray30").pack(
            fill="x", padx=5, pady=12
        )

        # 系統優化區
        ctk.CTkLabel(
            main_scroll, text="⚙ 系統優化",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=5, pady=(0, 8))

        for tweak in SYSTEM_TWEAKS:
            var = ctk.BooleanVar(value=True)
            self.tweak_vars[tweak["name"]] = var

            row = ctk.CTkFrame(main_scroll, fg_color="transparent")
            row.pack(fill="x", padx=5, pady=2)

            cb = ctk.CTkCheckBox(
                row, text="", variable=var, width=24,
                checkbox_width=20, checkbox_height=20
            )
            cb.pack(side="left")

            ctk.CTkLabel(
                row, text=tweak["name"],
                font=ctk.CTkFont(size=14, weight="bold")
            ).pack(side="left", padx=(4, 0))

            ctk.CTkLabel(
                row, text=f"— {tweak['description']}",
                font=ctk.CTkFont(size=12), text_color="gray"
            ).pack(side="left", padx=(8, 0))

        # 進度區
        progress_frame = ctk.CTkFrame(self)
        progress_frame.pack(fill="x", padx=15, pady=(5, 5))

        self.progress_label = ctk.CTkLabel(
            progress_frame, text="就緒",
            font=ctk.CTkFont(size=13)
        )
        self.progress_label.pack(anchor="w", padx=10, pady=(8, 2))

        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.pack(fill="x", padx=10, pady=(0, 4))
        self.progress_bar.set(0)

        self.progress_pct = ctk.CTkLabel(
            progress_frame, text="0%",
            font=ctk.CTkFont(size=12), text_color="gray"
        )
        self.progress_pct.pack(anchor="e", padx=10, pady=(0, 8))

        # 按鈕列
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(5, 5))

        ctk.CTkButton(
            btn_frame, text="全選", width=80, command=self._select_all
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_frame, text="全不選", width=80,
            fg_color="gray40", command=self._deselect_all
        ).pack(side="left", padx=(0, 8))

        # 設定檔按鈕
        ctk.CTkButton(
            btn_frame, text="💾 儲存設定", width=100,
            fg_color="gray40", command=self._save_config
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_frame, text="📂 載入設定", width=100,
            fg_color="gray40", command=self._load_config
        ).pack(side="left", padx=(0, 8))

        self.start_btn = ctk.CTkButton(
            btn_frame, text="▶ 開始安裝", width=120,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#28a745", hover_color="#218838",
            command=self._start_install
        )
        self.start_btn.pack(side="right")

        # 底部備註
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=15, pady=(5, 10))

        ctk.CTkLabel(
            footer,
            text="⚠ 本自動裝機系統只能安裝正版授權軟體",
            font=ctk.CTkFont(size=12), text_color="orange"
        ).pack(side="left")

        ctk.CTkLabel(
            footer,
            text="By: 謝智翔",
            font=ctk.CTkFont(size=12), text_color="gray"
        ).pack(side="right")

    def _check_update(self):
        try:
            req = urllib.request.Request(UPDATE_URL, headers={"User-Agent": "AutoQuickSetup"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            latest = data.get("version", APP_VERSION)
            download_url = data.get("download_url", "")
            if latest != APP_VERSION:
                self.after(0, lambda: self._show_update_dialog(latest, download_url))
        except Exception:
            pass  # 離線或連線失敗，靜默跳過

    def _show_update_dialog(self, latest, download_url):
        dialog = ctk.CTkToplevel(self)
        dialog.title("發現新版本")
        dialog.geometry("400x180")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text="🔔 有新版本可用！",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=(20, 5))

        ctk.CTkLabel(
            dialog, text=f"目前版本: v{APP_VERSION}    最新版本: v{latest}",
            font=ctk.CTkFont(size=13)
        ).pack(pady=5)

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=15)

        def open_download():
            if download_url:
                os.startfile(download_url)
            dialog.destroy()

        ctk.CTkButton(
            btn_frame, text="前往下載", width=120,
            fg_color="#28a745", hover_color="#218838",
            command=open_download
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            btn_frame, text="稍後再說", width=120,
            fg_color="gray40", command=dialog.destroy
        ).pack(side="left", padx=10)

    def _toggle_theme(self):
        current = ctk.get_appearance_mode()
        if current == "Dark":
            ctk.set_appearance_mode("light")
            self.theme_btn.configure(text="🌙 深色")
        else:
            ctk.set_appearance_mode("dark")
            self.theme_btn.configure(text="☀ 淺色")

    def _select_all(self):
        for var in self.software_vars.values():
            var.set(True)
        for var in self.tweak_vars.values():
            var.set(True)

    def _deselect_all(self):
        for var in self.software_vars.values():
            var.set(False)
        for var in self.tweak_vars.values():
            var.set(False)

    def _save_config(self):
        CONFIG_DIR.mkdir(exist_ok=True)
        dialog = ctk.CTkInputDialog(
            text="輸入設定檔名稱：", title="儲存設定"
        )
        name = dialog.get_input()
        if not name:
            return

        config = {
            "software": {k: v.get() for k, v in self.software_vars.items()},
            "tweaks": {k: v.get() for k, v in self.tweak_vars.items()},
        }
        config_file = CONFIG_DIR / f"{name}.json"
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        self.progress_label.configure(text=f"設定已儲存: {name}.json")

    def _load_config(self):
        if not CONFIG_DIR.exists() or not list(CONFIG_DIR.glob("*.json")):
            self.progress_label.configure(text="尚無設定檔")
            return

        configs = [f.stem for f in CONFIG_DIR.glob("*.json")]

        load_win = ctk.CTkToplevel(self)
        load_win.title("載入設定")
        load_win.geometry("300x400")
        load_win.transient(self)
        load_win.grab_set()

        ctk.CTkLabel(
            load_win, text="選擇設定檔：",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=(15, 10))

        listbox_frame = ctk.CTkScrollableFrame(load_win, height=250)
        listbox_frame.pack(fill="both", expand=True, padx=15)

        for cfg_name in configs:
            btn = ctk.CTkButton(
                listbox_frame, text=cfg_name,
                fg_color="gray30", hover_color="gray40",
                command=lambda n=cfg_name, w=load_win: self._apply_config(n, w)
            )
            btn.pack(fill="x", pady=2)

    def _apply_config(self, name, window):
        config_file = CONFIG_DIR / f"{name}.json"
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)

        for k, v in config.get("software", {}).items():
            if k in self.software_vars:
                self.software_vars[k].set(v)

        for k, v in config.get("tweaks", {}).items():
            if k in self.tweak_vars:
                self.tweak_vars[k].set(v)

        window.destroy()
        self.progress_label.configure(text=f"已載入設定: {name}")

    def _start_install(self):
        if self.installing:
            return
        self.installing = True
        self.start_btn.configure(state="disabled", text="安裝中...")
        threading.Thread(target=self._install_worker, daemon=True).start()

    def _install_worker(self):
        results = []

        selected_software = [
            item for item in self.software_items
            if self.software_vars.get(item["file"], ctk.BooleanVar(value=False)).get()
        ]
        selected_tweaks = [
            tweak for tweak in SYSTEM_TWEAKS
            if self.tweak_vars.get(tweak["name"], ctk.BooleanVar(value=False)).get()
        ]

        total = len(selected_software) + len(selected_tweaks)
        if total == 0:
            self.after(0, lambda: self.progress_label.configure(text="未選擇任何項目"))
            self.after(0, self._install_done)
            return

        current = 0

        # 系統優化
        for tweak in selected_tweaks:
            current += 1
            pct = current / total
            self.after(0, lambda t=tweak, p=pct, c=current, tt=total:
                self._update_progress(f"[{c}/{tt}] 系統優化: {t['name']}...", p))

            run_system_tweak(tweak)
            results.append({
                "name": f"[系統] {tweak['name']}",
                "success": True,
                "message": "設定完成",
            })

        # 軟體安裝
        for item in selected_software:
            current += 1
            pct = current / total
            self.after(0, lambda it=item, p=pct, c=current, tt=total:
                self._update_progress(f"[{c}/{tt}] 安裝 {it['name']}...", p))

            success, message = run_install(item)
            results.append({
                "name": item["name"],
                "success": success,
                "message": message,
            })

        # 重整桌面
        if selected_tweaks:
            subprocess.run(
                "taskkill /f /im explorer.exe", shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            subprocess.Popen("explorer.exe", shell=True)

        # 儲存日誌
        log_file = save_log(results)

        # 更新 UI
        success_count = sum(1 for r in results if r["success"])
        fail_count = len(results) - success_count
        summary = f"完成！成功: {success_count} | 失敗: {fail_count} | 日誌: {log_file.name}"

        self.after(0, lambda: self._update_progress(summary, 1.0))
        self.after(0, self._install_done)

        # 語音通知
        speak("安裝已完成")

    def _update_progress(self, text, pct):
        self.progress_label.configure(text=text)
        self.progress_bar.set(pct)
        self.progress_pct.configure(text=f"{int(pct * 100)}%")

    def _install_done(self):
        self.installing = False
        self.start_btn.configure(state="normal", text="▶ 開始安裝")


if __name__ == "__main__":
    app = App()
    app.mainloop()
