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
import time
from datetime import datetime
from pathlib import Path

APP_VERSION = "1.0.8"
APP_DATE = "2026-04-26"

CHANGELOG = [
    {
        "version": "1.0.8",
        "date": "2026-04-26",
        "features": [
            "系統優化新增「關閉工作列小工具」（關掉 Win11 工作列上的天氣／新聞彈窗）",
            "新增「💬 回報」按鈕：一鍵開啟預設信箱寄問題回報給作者",
        ],
        "fixes": [],
    },
    {
        "version": "1.0.7",
        "date": "2026-04-21",
        "features": [
            "「重新掃描」按鈕改名為「掃描新增的軟體」，語意更清楚",
        ],
        "fixes": [],
    },
    {
        "version": "1.0.6",
        "date": "2026-04-21",
        "features": [
            "自動更新：發現新版時一鍵下載並自動替換 exe、重啟程式，不需手動操作",
        ],
        "fixes": [
            "下載失敗會 fallback 開啟瀏覽器讓使用者手動下載",
        ],
    },
    {
        "version": "1.0.5",
        "date": "2026-04-20",
        "features": [
            "系統優化：電池使用中也永不睡眠／關螢幕（筆電適用）",
            "同步腳本 sync.bat／sync_to_drive.bat 自動 git push 到 GitHub",
        ],
        "fixes": [
            "更新對話框「前往下載」連結帳號修正（Wilson-Hsieh → u9511112）",
        ],
    },
    {
        "version": "1.0.4",
        "date": "2026-04-18",
        "features": [
            "新增「📄 日誌」按鈕：一鍵開啟本次安裝日誌",
            "新增「ℹ 版本」按鈕：查看版本號、日期與更新紀錄",
        ],
        "fixes": [
            "離線時不再自動跳過需聯網軟體（仍嘗試安裝，由安裝程式回報）",
            "網路偵測改用多重節點（Google、Cloudflare、HTTP），避免單一節點被封鎖誤判",
            "LINE 強制排最後安裝",
            "軟體安裝預設不勾選，由使用者自行選擇",
        ],
    },
    {
        "version": "1.0.3",
        "date": "2026-04-16",
        "features": [
            "Chrome 離線版／企業版 MSI 自動偵測支援",
            "新增重新掃描 software 資料夾按鈕",
            "解除安裝分頁（限 software 資料夾中的軟體）",
            "暫停／停止按鈕、步驟進度顯示",
        ],
        "fixes": [
            "控制台桌面圖示 GUID 修正",
            "LINE 改為手動安裝並排最後（含語音提示）",
            "所有 Windows 錯誤訊息中文化",
            "JSON 解析、權限、競態保護、非法檔名檢查",
            "解除安裝確認視窗：按鈕固定底部、視窗加大可調整",
            "DPI 感知修正，多螢幕座標正確",
        ],
    },
    {
        "version": "1.0.2",
        "date": "2026-04-10",
        "features": [
            "安裝彈窗自動點擊（pywinauto）",
            "自動更新檢查",
        ],
        "fixes": [
            "USB-C／唯讀磁碟相容性",
            "跨品牌相容性修復（電源 GUID、Office 路徑）",
            "移除 shell=True 避免卡住",
        ],
    },
    {
        "version": "1.0.0",
        "date": "2026-04-01",
        "features": [
            "初始版本：軟體自動安裝、系統優化、日誌儲存、語音通知",
        ],
        "fixes": [],
    },
]

# DPI 感知：確保座標系統統一（物理像素）
import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# Windows 錯誤碼中文對照
_WIN_ERROR_MAP = {
    2: "找不到檔案",
    3: "找不到路徑",
    5: "存取被拒（權限不足）",
    32: "檔案被其他程式佔用",
    87: "參數錯誤",
    740: "需要管理員權限",
    1223: "操作已取消",
    1260: "被安全性原則封鎖",
}

def _cn_error(e):
    """將 Windows 錯誤轉為中文訊息"""
    if hasattr(e, 'winerror') and e.winerror in _WIN_ERROR_MAP:
        return _WIN_ERROR_MAP[e.winerror]
    return str(e)

UPDATE_URL = "https://raw.githubusercontent.com/u9511112/AutoQuickSetup/master/version.json"
UPDATE_EXE_URL = "https://github.com/u9511112/AutoQuickSetup/releases/latest/download/AutoQuickSetup.exe"

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
        "description": "關閉自動休眠與螢幕關閉（插電/電池皆永不）",
        "commands": [
            "powercfg /change standby-timeout-ac 0",
            "powercfg /change monitor-timeout-ac 0",
            "powercfg /change standby-timeout-dc 0",
            "powercfg /change monitor-timeout-dc 0",
        ],
    },
    {
        "name": "桌面圖示：本機",
        "description": "顯示「本機」圖示",
        "commands": [
            'reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\HideDesktopIcons\\NewStartPanel" /v "{20D04FE0-3AEA-1069-A2D8-08002B30309D}" /t REG_DWORD /d 0 /f',
            'reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\HideDesktopIcons\\ClassicStartMenu" /v "{20D04FE0-3AEA-1069-A2D8-08002B30309D}" /t REG_DWORD /d 0 /f',
        ],
    },
    {
        "name": "桌面圖示：使用者資料夾",
        "description": "顯示個人資料夾圖示",
        "commands": [
            'reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\HideDesktopIcons\\NewStartPanel" /v "{59031a47-3f72-44a7-89c5-5595fe6b30ee}" /t REG_DWORD /d 0 /f',
            'reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\HideDesktopIcons\\ClassicStartMenu" /v "{59031a47-3f72-44a7-89c5-5595fe6b30ee}" /t REG_DWORD /d 0 /f',
        ],
    },
    {
        "name": "桌面圖示：控制台",
        "description": "顯示控制台圖示",
        "commands": [
            'reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\HideDesktopIcons\\NewStartPanel" /v "{5399E694-6CE5-4D6C-8FCE-1D8870FDCBA0}" /t REG_DWORD /d 0 /f',
            'reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\HideDesktopIcons\\ClassicStartMenu" /v "{5399E694-6CE5-4D6C-8FCE-1D8870FDCBA0}" /t REG_DWORD /d 0 /f',
        ],
    },
    {
        "name": "桌面圖示：網路",
        "description": "顯示網路圖示",
        "commands": [
            'reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\HideDesktopIcons\\NewStartPanel" /v "{F02C1A0D-BE21-4350-88B0-7367FC96EF3C}" /t REG_DWORD /d 0 /f',
            'reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\HideDesktopIcons\\ClassicStartMenu" /v "{F02C1A0D-BE21-4350-88B0-7367FC96EF3C}" /t REG_DWORD /d 0 /f',
        ],
    },
    {
        "name": "桌面圖示：資源回收桶",
        "description": "顯示資源回收桶圖示",
        "commands": [
            'reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\HideDesktopIcons\\NewStartPanel" /v "{645FF040-5081-101B-9F08-00AA002F954E}" /t REG_DWORD /d 0 /f',
            'reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\HideDesktopIcons\\ClassicStartMenu" /v "{645FF040-5081-101B-9F08-00AA002F954E}" /t REG_DWORD /d 0 /f',
        ],
    },
    {
        "name": "關閉工作列小工具",
        "description": "關閉 Windows 11 工作列上的小工具（天氣／新聞彈窗）",
        "commands": [
            'reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced" /v "TaskbarDa" /t REG_DWORD /d 0 /f',
        ],
    },
]


def load_catalog():
    if CATALOG_FILE.exists():
        try:
            with open(CATALOG_FILE, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return []
    return []


def scan_software():
    """掃描 software/ 資料夾，比對 catalog 產生安裝清單"""
    catalog = load_catalog()
    items = []
    if not SOFTWARE_DIR.exists():
        return items

    try:
        entries = list(SOFTWARE_DIR.iterdir())
    except PermissionError:
        return items

    for entry in entries:
        try:
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
                pattern = cat.get("pattern", "")
                if pattern and fnmatch.fnmatch(entry.name, pattern):
                    matched = cat
                    break

            if matched:
                items.append({
                    "file": entry.name,
                    "path": str(entry),
                    "name": matched.get("name", entry.stem),
                    "description": matched.get("description", ""),
                    "silent_args": matched.get("silent_args", "/S"),
                    "type": matched.get("type", "exe"),
                    "requires_config": matched.get("requires_config", False),
                    "manual_install": matched.get("manual_install", False),
                    "requires_network": matched.get("requires_network", False),
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
                    "requires_network": False,
                })
        except (PermissionError, OSError):
            continue

    items.sort(key=lambda x: x["name"])
    return items


def check_network():
    """檢查是否有網路連線（多重節點，避免單一節點被封鎖誤判）"""
    import socket
    # Google DNS, Cloudflare DNS, Quad9 DNS
    hosts = [("8.8.8.8", 53), ("1.1.1.1", 53), ("9.9.9.9", 53)]
    for host in hosts:
        try:
            socket.create_connection(host, timeout=2)
            return True
        except OSError:
            continue
    # 最後嘗試 HTTP（某些環境封鎖 DNS 埠但允許 HTTP）
    try:
        req = urllib.request.Request(
            "http://www.msftconnecttest.com/connecttest.txt",
            headers={"User-Agent": "AutoQuickSetup"},
        )
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        return False


def check_installed(name):
    """透過 Registry 檢查軟體是否已安裝，回傳 True/False"""
    info = get_uninstall_info(name)
    return info is not None


def get_uninstall_info(name):
    """透過 Registry 取得軟體的解除安裝資訊，回傳 dict 或 None"""
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
                                uninstall_str = ""
                                quiet_uninstall_str = ""
                                try:
                                    quiet_uninstall_str = winreg.QueryValueEx(subkey, "QuietUninstallString")[0]
                                except (FileNotFoundError, OSError):
                                    pass
                                try:
                                    uninstall_str = winreg.QueryValueEx(subkey, "UninstallString")[0]
                                except (FileNotFoundError, OSError):
                                    pass
                                return {
                                    "display_name": display_name,
                                    "uninstall_string": uninstall_str,
                                    "quiet_uninstall_string": quiet_uninstall_str,
                                }
                        except (FileNotFoundError, OSError):
                            pass
                        finally:
                            winreg.CloseKey(subkey)
                    except (FileNotFoundError, OSError):
                        pass
                winreg.CloseKey(key)
            except (FileNotFoundError, OSError):
                pass
    return None


def get_all_installed():
    """掃描 Registry 取得所有已安裝軟體清單"""
    uninstall_keys = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    ]
    installed = []
    seen = set()
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
                            if display_name in seen:
                                continue
                            seen.add(display_name)
                            uninstall_str = ""
                            quiet_uninstall_str = ""
                            try:
                                quiet_uninstall_str = winreg.QueryValueEx(subkey, "QuietUninstallString")[0]
                            except (FileNotFoundError, OSError):
                                pass
                            try:
                                uninstall_str = winreg.QueryValueEx(subkey, "UninstallString")[0]
                            except (FileNotFoundError, OSError):
                                pass
                            if uninstall_str or quiet_uninstall_str:
                                installed.append({
                                    "display_name": display_name,
                                    "uninstall_string": uninstall_str,
                                    "quiet_uninstall_string": quiet_uninstall_str,
                                })
                        except (FileNotFoundError, OSError):
                            pass
                        finally:
                            winreg.CloseKey(subkey)
                    except (FileNotFoundError, OSError):
                        pass
                winreg.CloseKey(key)
            except (FileNotFoundError, OSError):
                pass
    installed.sort(key=lambda x: x["display_name"].lower())
    return installed


def run_uninstall(info):
    """執行單一軟體解除安裝，回傳 (success, message)"""
    cmd = info.get("quiet_uninstall_string") or info.get("uninstall_string", "")
    if not cmd:
        return False, "找不到解除安裝指令"

    # 如果沒有靜默參數，嘗試加上常見的靜默旗標
    cmd_lower = cmd.lower()
    if info.get("quiet_uninstall_string"):
        pass  # 已經是靜默指令
    elif "msiexec" in cmd_lower:
        if "/x" in cmd_lower and "/quiet" not in cmd_lower:
            cmd += " /quiet /norestart"
    else:
        if "/s" not in cmd_lower and "/silent" not in cmd_lower and "/quiet" not in cmd_lower:
            cmd += " /S"

    try:
        # 解析指令為 list，避免 shell=True 導致等錯行程
        import shlex
        try:
            cmd_list = shlex.split(cmd, posix=False)
        except ValueError:
            cmd_list = cmd.split()

        proc = subprocess.Popen(
            cmd_list,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=0x08000000  # CREATE_NO_WINDOW
        )

        stop_event = threading.Event()
        clicker = threading.Thread(
            target=_auto_click_worker, args=(proc, stop_event), daemon=True
        )
        clicker.start()

        try:
            proc.wait(timeout=INSTALL_TIMEOUT)
        except subprocess.TimeoutExpired:
            proc.kill()
            stop_event.set()
            return False, "解除安裝逾時（超過 10 分鐘）"

        stop_event.set()
        clicker.join(timeout=5)

        if proc.returncode == 0:
            return True, "解除安裝成功"
        elif proc.returncode == 3010:
            return True, "解除安裝成功（需重新開機）"
        else:
            return False, f"解除安裝失敗（錯誤碼: {proc.returncode}）"
    except Exception as e:
        return False, f"解除安裝錯誤: {_cn_error(e)}"



def _auto_click_worker(proc, stop_event):
    """背景監控安裝程式彈窗，自動點擊同意/下一步/安裝按鈕 (不依賴滑鼠座標與 DPI)"""
    try:
        import uiautomation as auto
        auto.SetGlobalSearchTimeout(1.0) # 設定搜尋超時，避免卡頓
        
        click_texts = [
            "同意", "我同意", "接受", "我接受",
            "Agree", "I Agree", "I agree", "Accept",
            "同意して", "同意する",
            "下一步", "Next", "繼續", "Continue",
            "安裝", "Install", "インストール",
            "完成", "Finish", "OK", "ok", "Ok",
            "是", "Yes", "Close", "關閉",
        ]
        check_texts = [
            "同意", "我同意", "I agree", "I Agree", "Agree",
            "接受", "Accept", "我已閱讀",
        ]
        my_pid = os.getpid()

        while not stop_event.is_set() and proc.poll() is None:
            try:
                # 取得桌面第一層視窗
                root = auto.GetRootControl()
                for win in root.GetChildren():
                    try:
                        # 排除本程式視窗、無名背景視窗與常見的大型瀏覽器視窗（優化效能）
                        if win.ProcessId == my_pid:
                            continue
                        if not win.Name:
                            continue
                        if win.ClassName in ("Chrome_WidgetWin_1", "MozillaWindowClass"):
                            continue
                        
                        # 遍歷主視窗內的控制項，深度限制為 4 層（足夠應對安裝程式 UI）
                        for control, depth in auto.WalkControl(win, maxDepth=4):
                            try:
                                # 1. 處理勾選框 (CheckBox)
                                if control.ControlType == auto.ControlType.CheckBoxControl:
                                    ctrl_text = control.Name
                                    if ctrl_text:
                                        for ct in check_texts:
                                            if ct in ctrl_text:
                                                toggle_pattern = control.GetTogglePattern()
                                                if toggle_pattern and toggle_pattern.ToggleState == 0:
                                                    toggle_pattern.Toggle()
                                                    time.sleep(0.2)
                                                break
                                
                                # 2. 處理按鈕 (Button)
                                elif control.ControlType == auto.ControlType.ButtonControl:
                                    ctrl_text = control.Name
                                    if ctrl_text:
                                        for bt in click_texts:
                                            if bt == ctrl_text or bt in ctrl_text:
                                                invoke_pattern = control.GetInvokePattern()
                                                if invoke_pattern:
                                                    # 使用 InvokePattern 直接觸發按鈕點擊，完全不移動滑鼠
                                                    invoke_pattern.Invoke()
                                                else:
                                                    # 若不支援 InvokePattern，則進行不移動滑鼠的 Click 模擬
                                                    control.Click(simulateMove=False)
                                                time.sleep(1)
                                                break
                            except Exception:
                                pass
                    except Exception:
                        pass
            except Exception:
                pass
            time.sleep(2)
    except ImportError:
        pass


def run_install(item):
    """執行單一軟體安裝，回傳 (success, message)"""
    path = item["path"]
    args = item["silent_args"]
    install_type = item["type"]

    if item.get("requires_config"):
        config_xml = SOFTWARE_DIR / "configuration.xml"
        if not config_xml.exists():
            return False, "需要 configuration.xml 設定檔，已跳過"
        # 將 args 中的相對路徑替換為絕對路徑
        args = args.replace("configuration.xml", str(config_xml))

    try:
        import shlex
        args_list = shlex.split(args, posix=False) if args else []
        if install_type == "msi":
            cmd_list = ["msiexec", "/i", path] + args_list
        else:
            cmd_list = [path] + args_list

        # UNC 路徑不能作為 cwd，改傳 None 讓子程序繼承當前目錄
        cwd = None if str(SOFTWARE_DIR).startswith("\\\\") else str(SOFTWARE_DIR)

        proc = subprocess.Popen(
            cmd_list,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=cwd,
            creationflags=0x08000000  # CREATE_NO_WINDOW
        )

        # 啟動自動點擊監控
        stop_event = threading.Event()
        clicker = threading.Thread(
            target=_auto_click_worker, args=(proc, stop_event), daemon=True
        )
        clicker.start()

        try:
            proc.wait(timeout=INSTALL_TIMEOUT)
        except subprocess.TimeoutExpired:
            proc.kill()
            stop_event.set()
            return False, "安裝逾時（超過 10 分鐘）"

        stop_event.set()
        clicker.join(timeout=5)

        if proc.returncode == 0:
            return True, "安裝成功"
        elif proc.returncode == 3010:
            return True, "安裝成功（需重新開機）"
        else:
            return False, f"安裝失敗（錯誤碼: {proc.returncode}）"
    except Exception as e:
        return False, f"安裝錯誤: {_cn_error(e)}"


def run_system_tweak(tweak):
    """執行系統優化指令，回傳 (success, message)"""
    failed = []
    for cmd in tweak["commands"]:
        if not cmd.strip():
            continue
        cmd_name = cmd.split()[0] if cmd.split() else cmd[:20]
        try:
            result = subprocess.run(cmd, shell=True, timeout=30, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode != 0:
                failed.append(cmd_name)
        except subprocess.TimeoutExpired:
            failed.append(f"{cmd_name}(逾時)")
        except Exception as e:
            failed.append(_cn_error(e))
    if failed:
        return False, f"部分指令失敗: {', '.join(failed)}"
    return True, "設定完成"


def speak(text):
    """語音通知（非阻塞，獨立線程 + timeout）"""
    def _speak():
        # 優先用 PowerShell（更穩定，不會卡住）
        try:
            ps_cmd = (
                f'powershell -Command "Add-Type -AssemblyName System.Speech; '
                f'(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak(\'{text}\')"'
            )
            subprocess.run(ps_cmd, shell=True, timeout=15)
            return
        except Exception:
            pass
        # 備案：pyttsx3
        try:
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception:
            pass
    threading.Thread(target=_speak, daemon=True).start()


def save_log(results):
    """儲存安裝日誌"""
    try:
        LOG_DIR.mkdir(exist_ok=True)
    except OSError:
        return Path("install_log_unavailable.txt")
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

    try:
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except OSError:
        return Path("日誌儲存失敗")

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
        self.uninstall_vars = {}
        self.uninstall_items = []
        self.installing = False
        self.last_log_file = None
        self._paused = threading.Event()
        self._paused.set()  # 未暫停狀態
        self._stopped = threading.Event()

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

        self.about_btn = ctk.CTkButton(
            title_frame, text="ℹ 版本", width=70, height=28,
            fg_color="gray40", hover_color="gray30",
            command=self._show_about
        )
        self.about_btn.pack(side="right", padx=(0, 6))

        self.log_btn = ctk.CTkButton(
            title_frame, text="📄 日誌", width=70, height=28,
            fg_color="gray40", hover_color="gray30",
            command=self._open_log
        )
        self.log_btn.pack(side="right", padx=(0, 6))

        self.feedback_btn = ctk.CTkButton(
            title_frame, text="💬 回報", width=70, height=28,
            fg_color="gray40", hover_color="gray30",
            command=self._send_feedback
        )
        self.feedback_btn.pack(side="right", padx=(0, 6))

        ctk.CTkLabel(
            self, text="萬能裝機自動化工具",
            font=ctk.CTkFont(size=13), text_color="gray"
        ).pack(anchor="w", padx=20)

        # 分頁
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=15, pady=(10, 5))

        self.tab_install = self.tabview.add("📦 安裝")
        self.tab_uninstall = self.tabview.add("🗑 解除安裝")

        self._build_install_tab()
        self._build_uninstall_tab()

        # 進度區
        progress_frame = ctk.CTkFrame(self)
        progress_frame.pack(fill="x", padx=15, pady=(5, 5))

        # 步驟顯示
        self.step_label = ctk.CTkLabel(
            progress_frame, text="",
            font=ctk.CTkFont(size=11), text_color="gray"
        )
        self.step_label.pack(anchor="w", padx=10, pady=(8, 0))

        self.progress_label = ctk.CTkLabel(
            progress_frame, text="就緒",
            font=ctk.CTkFont(size=13)
        )
        self.progress_label.pack(anchor="w", padx=10, pady=(2, 2))

        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.pack(fill="x", padx=10, pady=(0, 4))
        self.progress_bar.set(0)

        # 進度百分比 + 暫停/停止按鈕
        ctrl_frame = ctk.CTkFrame(progress_frame, fg_color="transparent")
        ctrl_frame.pack(fill="x", padx=10, pady=(0, 8))

        self.progress_pct = ctk.CTkLabel(
            ctrl_frame, text="0%",
            font=ctk.CTkFont(size=12), text_color="gray"
        )
        self.progress_pct.pack(side="left")

        self.stop_btn = ctk.CTkButton(
            ctrl_frame, text="⏹ 停止", width=70, height=26,
            fg_color="#dc3545", hover_color="#c82333",
            font=ctk.CTkFont(size=11),
            command=self._stop_install, state="disabled"
        )
        self.stop_btn.pack(side="right", padx=(5, 0))

        self.pause_btn = ctk.CTkButton(
            ctrl_frame, text="⏸ 暫停", width=70, height=26,
            fg_color="#ffc107", hover_color="#e0a800",
            text_color="black",
            font=ctk.CTkFont(size=11),
            command=self._toggle_pause, state="disabled"
        )
        self.pause_btn.pack(side="right")

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

    def _build_install_tab(self):
        tab = self.tab_install

        self.install_scroll = ctk.CTkScrollableFrame(tab)
        self.install_scroll.pack(fill="both", expand=True, pady=(0, 5))

        # 軟體安裝區
        ctk.CTkLabel(
            self.install_scroll, text="📦 軟體安裝",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=5, pady=(5, 8))

        if not self.software_items:
            ctk.CTkLabel(
                self.install_scroll,
                text="⚠ 請將安裝檔放入 software 資料夾",
                text_color="orange"
            ).pack(anchor="w", padx=20)
        else:
            # 軟體預設不勾選，由使用者自行選擇
            self._install_rows = {}
            for item in self.software_items:
                var = ctk.BooleanVar(value=False)
                self.software_vars[item["file"]] = var

                row = ctk.CTkFrame(self.install_scroll, fg_color="transparent")
                row.pack(fill="x", padx=5, pady=2)

                cb = ctk.CTkCheckBox(
                    row, text="", variable=var, width=24,
                    checkbox_width=20, checkbox_height=20
                )
                cb.pack(side="left")

                display_name = item["name"]
                if item.get("manual_install"):
                    display_name += "  🖐 手動"
                if item.get("requires_network"):
                    display_name += "  🌐 需聯網"

                name_label = ctk.CTkLabel(
                    row, text=display_name,
                    font=ctk.CTkFont(size=14, weight="bold")
                )
                name_label.pack(side="left", padx=(4, 0))

                ctk.CTkLabel(
                    row, text=f"— {item['description']}",
                    font=ctk.CTkFont(size=12), text_color="gray"
                ).pack(side="left", padx=(8, 0))

                self._install_rows[item["file"]] = {
                    "var": var, "label": name_label, "name": item["name"]
                }

            # 背景查詢已安裝狀態
            threading.Thread(target=self._check_installed_bg, daemon=True).start()

        # 分隔線
        ctk.CTkFrame(self.install_scroll, height=2, fg_color="gray30").pack(
            fill="x", padx=5, pady=12
        )

        # 系統優化區
        install_scroll = self.install_scroll
        ctk.CTkLabel(
            install_scroll, text="⚙ 系統優化",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=5, pady=(0, 8))

        for tweak in SYSTEM_TWEAKS:
            var = ctk.BooleanVar(value=True)
            self.tweak_vars[tweak["name"]] = var

            row = ctk.CTkFrame(install_scroll, fg_color="transparent")
            row.pack(fill="x", padx=5, pady=2)

            ctk.CTkCheckBox(
                row, text="", variable=var, width=24,
                checkbox_width=20, checkbox_height=20
            ).pack(side="left")

            ctk.CTkLabel(
                row, text=tweak["name"],
                font=ctk.CTkFont(size=14, weight="bold")
            ).pack(side="left", padx=(4, 0))

            ctk.CTkLabel(
                row, text=f"— {tweak['description']}",
                font=ctk.CTkFont(size=12), text_color="gray"
            ).pack(side="left", padx=(8, 0))

        # 按鈕列
        btn_frame = ctk.CTkFrame(tab, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(5, 0))

        ctk.CTkButton(
            btn_frame, text="🔄 掃描新增的軟體", width=140,
            fg_color="gray40", command=self._refresh_install_list
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_frame, text="全選", width=80, command=self._select_all
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_frame, text="全不選", width=80,
            fg_color="gray40", command=self._deselect_all
        ).pack(side="left", padx=(0, 8))

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

    def _refresh_install_list(self):
        """重新掃描 software/ 資料夾，更新安裝清單"""
        if self.installing:
            self.progress_label.configure(text="⚠ 安裝/解除安裝進行中，無法重新掃描")
            return
        self.software_items = scan_software()
        self.software_vars.clear()
        # 清除並重建安裝分頁內容
        for widget in self.install_scroll.winfo_children():
            widget.destroy()
        self._install_rows = {}

        ctk.CTkLabel(
            self.install_scroll, text="📦 軟體安裝",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=5, pady=(5, 8))

        if not self.software_items:
            ctk.CTkLabel(
                self.install_scroll,
                text="⚠ 請將安裝檔放入 software 資料夾",
                text_color="orange"
            ).pack(anchor="w", padx=20)
        else:
            for item in self.software_items:
                var = ctk.BooleanVar(value=False)
                self.software_vars[item["file"]] = var

                row = ctk.CTkFrame(self.install_scroll, fg_color="transparent")
                row.pack(fill="x", padx=5, pady=2)

                ctk.CTkCheckBox(
                    row, text="", variable=var, width=24,
                    checkbox_width=20, checkbox_height=20
                ).pack(side="left")

                display_name = item["name"]
                if item.get("manual_install"):
                    display_name += "  🖐 手動"
                if item.get("requires_network"):
                    display_name += "  🌐 需聯網"

                name_label = ctk.CTkLabel(
                    row, text=display_name,
                    font=ctk.CTkFont(size=14, weight="bold")
                )
                name_label.pack(side="left", padx=(4, 0))

                ctk.CTkLabel(
                    row, text=f"— {item['description']}",
                    font=ctk.CTkFont(size=12), text_color="gray"
                ).pack(side="left", padx=(8, 0))

                self._install_rows[item["file"]] = {
                    "var": var, "label": name_label, "name": item["name"]
                }

            threading.Thread(target=self._check_installed_bg, daemon=True).start()

        # 重建系統優化區
        ctk.CTkFrame(self.install_scroll, height=2, fg_color="gray30").pack(
            fill="x", padx=5, pady=12
        )
        ctk.CTkLabel(
            self.install_scroll, text="⚙ 系統優化",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=5, pady=(0, 8))

        for tweak in SYSTEM_TWEAKS:
            if tweak["name"] not in self.tweak_vars:
                self.tweak_vars[tweak["name"]] = ctk.BooleanVar(value=True)
            var = self.tweak_vars[tweak["name"]]

            row = ctk.CTkFrame(self.install_scroll, fg_color="transparent")
            row.pack(fill="x", padx=5, pady=2)

            ctk.CTkCheckBox(
                row, text="", variable=var, width=24,
                checkbox_width=20, checkbox_height=20
            ).pack(side="left")

            ctk.CTkLabel(
                row, text=tweak["name"],
                font=ctk.CTkFont(size=14, weight="bold")
            ).pack(side="left", padx=(4, 0))

            ctk.CTkLabel(
                row, text=f"— {tweak['description']}",
                font=ctk.CTkFont(size=12), text_color="gray"
            ).pack(side="left", padx=(8, 0))

        self.progress_label.configure(
            text=f"已重新掃描，找到 {len(self.software_items)} 個安裝檔"
        )

    def _check_installed_bg(self):
        """背景查詢已安裝軟體狀態，完成後更新 UI"""
        results = {}
        for file_key, row_data in self._install_rows.items():
            results[file_key] = check_installed(row_data["name"])
        self.after(0, lambda: self._update_installed_status(results))

    def _update_installed_status(self, results):
        for file_key, installed in results.items():
            if file_key not in self._install_rows:
                continue
            row_data = self._install_rows[file_key]
            if installed:
                row_data["var"].set(False)
                row_data["label"].configure(
                    text=f"{row_data['name']}  ✓ 已安裝",
                    text_color="#90EE90"
                )

    def _build_uninstall_tab(self):
        tab = self.tab_uninstall

        # 搜尋框
        search_frame = ctk.CTkFrame(tab, fg_color="transparent")
        search_frame.pack(fill="x", pady=(5, 5))

        ctk.CTkLabel(
            search_frame, text="🔍", font=ctk.CTkFont(size=14)
        ).pack(side="left", padx=(0, 5))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._filter_uninstall_list())
        ctk.CTkEntry(
            search_frame, textvariable=self.search_var,
            placeholder_text="搜尋 software 資料夾中已安裝的軟體...", height=32
        ).pack(side="left", fill="x", expand=True)

        # 軟體清單
        self.uninstall_scroll = ctk.CTkScrollableFrame(tab)
        self.uninstall_scroll.pack(fill="both", expand=True, pady=(0, 5))

        self._load_uninstall_list()

        # 按鈕列
        btn_frame = ctk.CTkFrame(tab, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(5, 0))

        ctk.CTkButton(
            btn_frame, text="🔄 重新整理", width=100,
            fg_color="gray40", command=self._refresh_uninstall_list
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_frame, text="全選", width=80,
            fg_color="gray40", command=self._select_all_uninstall
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_frame, text="全不選", width=80,
            fg_color="gray40", command=self._deselect_all_uninstall
        ).pack(side="left", padx=(0, 8))

        self.uninstall_btn = ctk.CTkButton(
            btn_frame, text="🗑 解除安裝", width=120,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#dc3545", hover_color="#c82333",
            command=self._start_uninstall
        )
        self.uninstall_btn.pack(side="right")

    def _load_uninstall_list(self, filter_text="", refresh=False):
        if refresh or not self.uninstall_items:
            # 背景掃描 Registry，避免卡主執行緒
            self._show_uninstall_loading()
            threading.Thread(
                target=self._scan_installed_bg, daemon=True
            ).start()
            return

        self._render_uninstall_list(filter_text)

    def _show_uninstall_loading(self):
        for widget in self.uninstall_scroll.winfo_children():
            widget.destroy()
        ctk.CTkLabel(
            self.uninstall_scroll, text="掃描中...", text_color="gray"
        ).pack(pady=20)

    def _scan_installed_bg(self):
        all_items = get_all_installed()
        # 只保留 software/ 資料夾中有對應安裝檔的軟體
        catalog = load_catalog()
        catalog_names = [c.get("name", "").lower() for c in catalog]
        # 也加入 scan_software 掃到的軟體名稱
        sw_names = [item["name"].lower() for item in scan_software()]
        allowed_names = set(catalog_names + sw_names)

        filtered = []
        for item in all_items:
            display = item["display_name"].lower()
            for name in allowed_names:
                if name and name in display:
                    filtered.append(item)
                    break

        self.after(0, lambda: self._on_scan_done(filtered))

    def _on_scan_done(self, items):
        self.uninstall_items = items
        self._render_uninstall_list("")

    def _render_uninstall_list(self, filter_text=""):
        for widget in self.uninstall_scroll.winfo_children():
            widget.destroy()
        self.uninstall_vars.clear()

        ft = filter_text.lower()
        shown = 0
        for item in self.uninstall_items:
            name = item["display_name"]
            if ft and ft not in name.lower():
                continue

            var = ctk.BooleanVar(value=False)
            self.uninstall_vars[name] = {"var": var, "info": item}

            row = ctk.CTkFrame(self.uninstall_scroll, fg_color="transparent")
            row.pack(fill="x", padx=5, pady=1)

            ctk.CTkCheckBox(
                row, text="", variable=var, width=24,
                checkbox_width=20, checkbox_height=20
            ).pack(side="left")

            ctk.CTkLabel(
                row, text=name,
                font=ctk.CTkFont(size=13),
                anchor="w"
            ).pack(side="left", padx=(4, 0), fill="x", expand=True)

            shown += 1

        if shown == 0:
            ctk.CTkLabel(
                self.uninstall_scroll,
                text="找不到符合的軟體" if ft else "software 資料夾中的軟體均未安裝",
                text_color="gray"
            ).pack(pady=20)

    def _filter_uninstall_list(self):
        # 只對已快取的清單過濾，不重掃 Registry
        self._render_uninstall_list(self.search_var.get())

    def _refresh_uninstall_list(self):
        self.search_var.set("")
        self._load_uninstall_list(refresh=True)
        self.progress_label.configure(text="重新整理中...")

    def _select_all_uninstall(self):
        for entry in self.uninstall_vars.values():
            entry["var"].set(True)

    def _deselect_all_uninstall(self):
        for entry in self.uninstall_vars.values():
            entry["var"].set(False)

    def _start_uninstall(self):
        if self.installing:
            return

        selected = [
            entry["info"] for entry in self.uninstall_vars.values()
            if entry["var"].get()
        ]
        if not selected:
            self.progress_label.configure(text="未選擇任何要解除安裝的軟體")
            return

        # 確認對話框
        confirm = ctk.CTkToplevel(self)
        confirm.title("確認解除安裝")
        confirm.geometry("500x400")
        confirm.resizable(True, True)
        confirm.minsize(400, 350)
        confirm.transient(self)
        confirm.grab_set()
        # 置中顯示
        confirm.after(100, lambda: confirm.focus_force())

        ctk.CTkLabel(
            confirm, text="⚠ 確認要解除安裝以下軟體？",
            font=ctk.CTkFont(size=16, weight="bold"), text_color="orange"
        ).pack(pady=(20, 10))

        # 按鈕先 pack 到底部（固定位置，不會被擠掉）
        btn_frame = ctk.CTkFrame(confirm, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x", padx=20, pady=(10, 20))

        def do_uninstall():
            confirm.destroy()
            self.installing = True
            self._stopped.clear()
            self._paused.set()
            self.uninstall_btn.configure(state="disabled", text="解除安裝中...")
            self._enable_controls(True)
            threading.Thread(
                target=self._uninstall_worker, args=(selected,), daemon=True
            ).start()

        ctk.CTkButton(
            btn_frame, text="✓ 確認解除安裝", width=150, height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#dc3545", hover_color="#c82333",
            command=do_uninstall
        ).pack(side="left", padx=(0, 15))

        ctk.CTkButton(
            btn_frame, text="取消", width=100, height=40,
            font=ctk.CTkFont(size=14),
            fg_color="gray40", command=confirm.destroy
        ).pack(side="left")

        # 軟體清單在按鈕上方，填滿剩餘空間
        names_frame = ctk.CTkScrollableFrame(confirm)
        names_frame.pack(fill="both", expand=True, padx=20, pady=(0, 5))

        for item in selected:
            ctk.CTkLabel(
                names_frame, text=f"  • {item['display_name']}",
                font=ctk.CTkFont(size=13), anchor="w"
            ).pack(anchor="w")

    def _uninstall_worker(self, selected):
        results = []
        total = len(selected)

        for i, item in enumerate(selected, 1):
            if self._stopped.is_set():
                results.append({"name": "[中止]", "success": False, "message": "使用者停止"})
                break
            self._paused.wait()

            pct = i / total
            name = item["display_name"]
            self.after(0, lambda n=name, p=pct, c=i, tt=total:
                self._update_progress(f"[{c}/{tt}] 解除安裝 {n}...", p))

            success, message = run_uninstall(item)
            results.append({"name": name, "success": success, "message": message})

        # 儲存日誌
        log_file = save_log(results)
        self.last_log_file = log_file

        success_count = sum(1 for r in results if r["success"])
        fail_count = total - success_count
        summary = f"完成！成功: {success_count} | 失敗: {fail_count} | 日誌: {log_file.name}"

        self.after(0, lambda: self._update_progress(summary, 1.0))
        self.after(0, self._uninstall_done)

        if fail_count > 0:
            speak(f"解除安裝完成，其中 {fail_count} 個失敗")
        else:
            speak("全部解除安裝完成")

    def _uninstall_done(self):
        self.installing = False
        self._stopped.clear()
        self._paused.set()
        self.uninstall_btn.configure(state="normal", text="🗑 解除安裝")
        self._enable_controls(False)
        self._refresh_uninstall_list()

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
        dialog.geometry("420x220")
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

        status_label = ctk.CTkLabel(dialog, text="", font=ctk.CTkFont(size=12))
        status_label.pack(pady=5)

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=10)

        update_btn = ctk.CTkButton(
            btn_frame, text="立即更新", width=120,
            fg_color="#28a745", hover_color="#218838",
        )
        update_btn.pack(side="left", padx=10)

        later_btn = ctk.CTkButton(
            btn_frame, text="稍後再說", width=120,
            fg_color="gray40", command=dialog.destroy
        )
        later_btn.pack(side="left", padx=10)

        def start_update():
            update_btn.configure(state="disabled")
            later_btn.configure(state="disabled")
            status_label.configure(text="下載新版中...")
            threading.Thread(
                target=self._perform_update,
                args=(dialog, status_label, update_btn, later_btn, download_url),
                daemon=True,
            ).start()

        update_btn.configure(command=start_update)

    def _perform_update(self, dialog, status_label, update_btn, later_btn, download_url):
        try:
            if not getattr(sys, "frozen", False):
                self.after(0, lambda: status_label.configure(text="⚠ 開發環境不支援自動更新"))
                self.after(0, lambda: update_btn.configure(state="normal", text="關閉", command=dialog.destroy))
                self.after(0, lambda: later_btn.configure(state="normal"))
                return

            current_exe = Path(sys.executable)
            temp_dir = Path(os.environ.get("TEMP", str(current_exe.parent)))
            new_exe = temp_dir / "AutoQuickSetup_new.exe"
            updater_bat = temp_dir / "AutoQuickSetup_update.bat"

            req = urllib.request.Request(UPDATE_EXE_URL, headers={"User-Agent": "AutoQuickSetup"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                with open(new_exe, "wb") as f:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            pct = int(downloaded * 100 / total)
                            self.after(0, lambda p=pct: status_label.configure(text=f"下載中... {p}%"))

            self.after(0, lambda: status_label.configure(text="準備安裝，程式即將重啟..."))

            bat_content = (
                "@echo off\r\n"
                "ping 127.0.0.1 -n 3 >nul\r\n"
                "setlocal\r\n"
                "set /a TRIES=0\r\n"
                ":RETRY\r\n"
                "set /a TRIES+=1\r\n"
                "if %TRIES% gtr 15 goto FAIL\r\n"
                f'move /y "{new_exe}" "{current_exe}" >nul 2>&1\r\n'
                "if errorlevel 1 (\r\n"
                "    ping 127.0.0.1 -n 2 >nul\r\n"
                "    goto RETRY\r\n"
                ")\r\n"
                f'start "" "{current_exe}"\r\n'
                "goto CLEANUP\r\n"
                ":FAIL\r\n"
                f'start "" "{current_exe}"\r\n'
                ":CLEANUP\r\n"
                'del "%~f0"\r\n'
            )
            updater_bat.write_text(bat_content, encoding="utf-8")

            subprocess.Popen(
                ["cmd.exe", "/c", str(updater_bat)],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
                close_fds=True,
            )
            time.sleep(1)
            self.after(0, self.destroy)
            time.sleep(1)
            os._exit(0)
        except Exception as e:
            err = str(e)[:80]
            def show_err():
                status_label.configure(text=f"⚠ 下載失敗：{err}")
                if download_url:
                    try:
                        os.startfile(download_url)
                    except OSError:
                        pass
                update_btn.configure(state="normal", text="關閉", command=dialog.destroy)
                later_btn.configure(state="normal")
            self.after(0, show_err)

    def _toggle_pause(self):
        if self._paused.is_set():
            self._paused.clear()
            self.pause_btn.configure(text="▶ 繼續", fg_color="#28a745", hover_color="#218838", text_color="white")
            self.progress_label.configure(text="已暫停")
        else:
            self._paused.set()
            self.pause_btn.configure(text="⏸ 暫停", fg_color="#ffc107", hover_color="#e0a800", text_color="black")

    def _stop_install(self):
        self._stopped.set()
        self._paused.set()  # 解除暫停，讓 worker 能檢查 stopped 旗標
        self.progress_label.configure(text="正在停止...")

    def _enable_controls(self, enable):
        """啟用/停用暫停和停止按鈕"""
        state = "normal" if enable else "disabled"
        self.pause_btn.configure(state=state)
        self.stop_btn.configure(state=state)
        if not enable:
            self.pause_btn.configure(text="⏸ 暫停", fg_color="#ffc107", hover_color="#e0a800", text_color="black")

    def _toggle_theme(self):
        current = ctk.get_appearance_mode()
        if current == "Dark":
            ctk.set_appearance_mode("light")
            self.theme_btn.configure(text="🌙 深色")
        else:
            ctk.set_appearance_mode("dark")
            self.theme_btn.configure(text="☀ 淺色")

    def _open_log(self):
        """開啟本次安裝日誌，若無則開啟 logs/ 中最新的一份"""
        target = None
        if self.last_log_file and Path(self.last_log_file).exists():
            target = Path(self.last_log_file)
        elif LOG_DIR.exists():
            try:
                logs = sorted(
                    LOG_DIR.glob("install_log_*.txt"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if logs:
                    target = logs[0]
            except OSError:
                pass

        if target is None:
            self.progress_label.configure(text="⚠ 尚無安裝日誌")
            return
        try:
            os.startfile(str(target))
            self.progress_label.configure(text=f"已開啟日誌: {target.name}")
        except OSError as e:
            self.progress_label.configure(text=f"⚠ 無法開啟日誌: {_cn_error(e)}")

    def _send_feedback(self):
        """開啟預設信箱寄回報信給作者"""
        import urllib.parse
        subject = f"AutoQuickSetup v{APP_VERSION} 回報"
        body = (
            f"版本：{APP_VERSION}\n"
            f"日期：{APP_DATE}\n"
            f"\n"
            f"請在下方描述問題或建議：\n"
            f"\n"
        )
        url = (
            f"mailto:u9511112@gmail.com"
            f"?subject={urllib.parse.quote(subject)}"
            f"&body={urllib.parse.quote(body)}"
        )
        try:
            os.startfile(url)
            self.progress_label.configure(text="已開啟信箱，感謝您的回報！")
        except OSError as e:
            self.progress_label.configure(text=f"⚠ 無法開啟信箱：{_cn_error(e)}（請寄到 u9511112@gmail.com）")

    def _show_about(self):
        """顯示版本資訊與更新紀錄"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("版本資訊")
        dialog.geometry("560x560")
        dialog.minsize(480, 400)
        dialog.transient(self)
        dialog.grab_set()

        header = ctk.CTkFrame(dialog, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 5))

        ctk.CTkLabel(
            header, text=f"AutoQuickSetup v{APP_VERSION}",
            font=ctk.CTkFont(size=22, weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            header, text=f"發行日期：{APP_DATE}   |   作者：謝智翔",
            font=ctk.CTkFont(size=12), text_color="gray"
        ).pack(anchor="w", pady=(2, 0))

        ctk.CTkLabel(
            dialog, text="更新紀錄",
            font=ctk.CTkFont(size=15, weight="bold")
        ).pack(anchor="w", padx=20, pady=(15, 5))

        content = ctk.CTkScrollableFrame(dialog)
        content.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        for entry in CHANGELOG:
            ver_row = ctk.CTkFrame(content, fg_color="transparent")
            ver_row.pack(fill="x", pady=(8, 2))
            ctk.CTkLabel(
                ver_row, text=f"v{entry['version']}",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color="#4da6ff"
            ).pack(side="left")
            ctk.CTkLabel(
                ver_row, text=f"　{entry['date']}",
                font=ctk.CTkFont(size=11), text_color="gray"
            ).pack(side="left")

            if entry.get("features"):
                ctk.CTkLabel(
                    content, text="✨ 新增功能",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color="#90EE90"
                ).pack(anchor="w", padx=6, pady=(4, 0))
                for f in entry["features"]:
                    ctk.CTkLabel(
                        content, text=f"    • {f}",
                        font=ctk.CTkFont(size=12),
                        wraplength=480, justify="left", anchor="w"
                    ).pack(anchor="w", padx=6)

            if entry.get("fixes"):
                ctk.CTkLabel(
                    content, text="🔧 修復 Bug",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color="#ffb366"
                ).pack(anchor="w", padx=6, pady=(4, 0))
                for fx in entry["fixes"]:
                    ctk.CTkLabel(
                        content, text=f"    • {fx}",
                        font=ctk.CTkFont(size=12),
                        wraplength=480, justify="left", anchor="w"
                    ).pack(anchor="w", padx=6)

        ctk.CTkButton(
            dialog, text="關閉", width=100,
            command=dialog.destroy
        ).pack(pady=(0, 15))

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
        try:
            CONFIG_DIR.mkdir(exist_ok=True)
        except OSError:
            self.progress_label.configure(text="⚠ 無法儲存設定（磁碟唯讀）")
            return
        dialog = ctk.CTkInputDialog(
            text="輸入設定檔名稱：", title="儲存設定"
        )
        name = dialog.get_input()
        if not name:
            return

        import re
        if re.search(r'[\\/:*?"<>|]', name) or name.strip().upper() in (
            "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4",
            "LPT1", "LPT2", "LPT3",
        ):
            self.progress_label.configure(text="⚠ 檔名含非法字元，請重新輸入")
            return

        config = {
            "software": {k: v.get() for k, v in self.software_vars.items()},
            "tweaks": {k: v.get() for k, v in self.tweak_vars.items()},
        }
        config_file = CONFIG_DIR / f"{name}.json"
        try:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            self.progress_label.configure(text=f"設定已儲存: {name}.json")
        except OSError:
            self.progress_label.configure(text="⚠ 儲存失敗（磁碟空間不足或權限不足）")

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
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            window.destroy()
            self.progress_label.configure(text="⚠ 設定檔格式損壞，無法載入")
            return

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
        self._stopped.clear()
        self._paused.set()
        self.start_btn.configure(state="disabled", text="安裝中...")
        self.after(0, lambda: self._enable_controls(True))
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

        # 檢查網路狀態（僅提示，不再自動跳過）
        has_network = check_network()
        if not has_network:
            self.after(0, lambda: self.step_label.configure(
                text="⚠ 偵測到離線環境，需聯網軟體仍會嘗試安裝（可能失敗）"
            ))

        # 排序：tweak → 離線軟體 → 需聯網軟體 → 手動安裝（排最後）
        auto_software = [item for item in selected_software
                         if not item.get("manual_install")]
        manual_software = [item for item in selected_software
                           if item.get("manual_install")]

        all_steps = []
        for tweak in selected_tweaks:
            all_steps.append(("tweak", tweak))
        # 將需聯網的排到離線後面（離線優先安裝，聯網放後面）
        offline_first = sorted(auto_software, key=lambda x: bool(x.get("requires_network")))
        for item in offline_first:
            all_steps.append(("software", item))
        for item in manual_software:
            all_steps.append(("manual", item))

        # 強制：LINE 永遠排在最後（即使有其他 manual_install 軟體）
        def _is_line(step):
            return step[1].get("name", "").strip().upper() == "LINE"
        all_steps.sort(key=_is_line)

        total = len(all_steps)
        if total == 0:
            self.after(0, lambda: self.progress_label.configure(text="未選擇任何項目"))
            self.after(0, self._install_done)
            return

        # 顯示步驟清單
        step_names = [s[1]["name"] for s in all_steps]
        display = ' → '.join(step_names[:8]) + (' → ...' if len(step_names) > 8 else '')
        self.after(0, lambda d=display: self.step_label.configure(text=f"步驟: {d}"))

        for current, (step_type, step_data) in enumerate(all_steps, 1):
            if self._stopped.is_set():
                results.append({"name": "[中止]", "success": False, "message": "使用者停止"})
                break

            self._paused.wait()

            pct = (current - 1) / total

            if step_type == "tweak":
                self.after(0, lambda t=step_data, p=pct, c=current, tt=total:
                    self._update_progress(f"[{c}/{tt}] 系統優化: {t['name']}...", p))
                success, message = run_system_tweak(step_data)
                status = "✓" if success else "✗"
                self.after(0, lambda n=step_data["name"], s=status, m=message:
                    self.step_label.configure(text=f"  {s} [系統] {n}: {m}"))
                results.append({
                    "name": f"[系統] {step_data['name']}",
                    "success": success,
                    "message": message,
                })
            elif step_type == "manual":
                # 手動安裝：語音提示，啟動安裝程式但不等待
                name = step_data["name"]
                self.after(0, lambda n=name, p=pct, c=current, tt=total:
                    self._update_progress(f"[{c}/{tt}] 手動安裝 {n}（請手動操作）...", p))
                speak(f"請手動勾選同意並安裝 {name}")
                try:
                    proc = subprocess.Popen(
                        [step_data["path"]],
                        creationflags=0x08000000
                    )
                    self.after(0, lambda n=name:
                        self.step_label.configure(text=f"  ⏳ {n}: 等待手動安裝完成..."))
                    proc.wait(timeout=INSTALL_TIMEOUT)
                    success = proc.returncode == 0 or proc.returncode == 3010
                    message = "安裝成功" if success else f"安裝失敗（錯誤碼: {proc.returncode}）"
                except subprocess.TimeoutExpired:
                    proc.kill()
                    success, message = False, "安裝逾時"
                except Exception as e:
                    success, message = False, f"安裝錯誤: {_cn_error(e)}"
                status = "✓" if success else "✗"
                results.append({"name": name, "success": success, "message": message})
                self.after(0, lambda n=name, s=status, m=message:
                    self.step_label.configure(text=f"  {s} {n}: {m}"))
            else:
                self.after(0, lambda it=step_data, p=pct, c=current, tt=total:
                    self._update_progress(f"[{c}/{tt}] 安裝 {it['name']}...", p))
                success, message = run_install(step_data)
                status = "✓" if success else "✗"
                results.append({
                    "name": step_data["name"],
                    "success": success,
                    "message": message,
                })
                self.after(0, lambda n=step_data["name"], s=status, m=message:
                    self.step_label.configure(text=f"  {s} {n}: {m}"))

        # 刷新桌面圖示
        if selected_tweaks and not self._stopped.is_set():
            try:
                subprocess.run(
                    ["RUNDLL32.exe", "user32.dll,UpdatePerUserSystemParameters", ",1", ",True"],
                    timeout=10, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
            except Exception:
                pass
            try:
                subprocess.run(
                    ["ie4uinit.exe", "-show"],
                    timeout=10, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
            except Exception:
                pass

        # 儲存日誌
        log_file = save_log(results)
        self.last_log_file = log_file

        # 更新 UI
        success_count = sum(1 for r in results if r["success"])
        fail_count = len(results) - success_count
        stopped = self._stopped.is_set()
        if stopped:
            summary = f"已停止！成功: {success_count} | 未完成: {fail_count} | 日誌: {log_file.name}"
        else:
            summary = f"完成！成功: {success_count} | 失敗: {fail_count} | 日誌: {log_file.name}"

        self.after(0, lambda: self._update_progress(summary, 1.0))
        self.after(0, self._install_done)

        # 語音通知
        if stopped:
            speak("安裝已停止")
        elif fail_count > 0:
            speak(f"安裝完成，其中 {fail_count} 個失敗")
        else:
            speak("全部安裝完成")

    def _update_progress(self, text, pct):
        self.progress_label.configure(text=text)
        self.progress_bar.set(pct)
        self.progress_pct.configure(text=f"{int(pct * 100)}%")

    def _install_done(self):
        self.installing = False
        self._stopped.clear()
        self._paused.set()
        self.start_btn.configure(state="normal", text="▶ 開始安裝")
        self._enable_controls(False)
        self.step_label.configure(text="")


if __name__ == "__main__":
    app = App()
    app.mainloop()
