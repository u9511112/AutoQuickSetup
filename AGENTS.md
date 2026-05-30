# AutoQuickSetup — Repo-Level Instructions for Codex

## 專案性質
萬能裝機自動化工具。一鍵安裝 / 解除安裝常用軟體 + 系統優化、專為 **IT 裝機人員 / 3C 門市員工**設計的可攜式工具（隨身碟版）。
Stack：Python 3.12 + CustomTkinter（GUI）+ PyInstaller --onefile（打包成 .exe）。

## 同系列專案
- **EasyPcBuild**：買電腦（推薦選購）
- **AutoQuickSetup**（本專案）：裝電腦（軟體 + 系統優化）
- **USBDoctor**：救電腦（診斷 + 修復）

## 使用方式
USB 隨身碟結構：
```
USB/
└── AutoQuickSetup/
    ├── AutoQuickSetup.exe    ← 主程式
    ├── software_catalog.json ← 軟體對照表
    └── software/             ← 安裝檔（.exe / .msi）
```
雙擊 exe → UAC 提權 → 自動掃描 `software/` → 列出可安裝軟體。

## 檔案結構
```
main.py                 ← 主程式（GUI、安裝邏輯、系統優化）
software_catalog.json   ← 軟體對照表（檔名 → 顯示名稱 + 說明 + glob pattern）
test_main.py            ← pytest
sync.bat / sync_to_drive.bat / update_usb.bat  ← 發布腳本
version.json            ← 版本資訊（GitHub Releases 自動更新用）
README.md
AutoQuickSetup.exe      ← PyInstaller 產出（commit 進 repo、方便直接 copy 到 USB）
```

## 已建立的慣例（被同系列借用）
| 慣例 | 位置 |
|------|------|
| `BASE_DIR` PyInstaller-aware 解析 | `main.py` L143-152 |
| `_WIN_ERROR_MAP` Windows 錯誤碼中文化 | `main.py` L122-138 |
| `update_usb.bat` 自動發布 | repo 根 |
| `version.json` + GitHub Releases 自動更新 | repo 根 |

## 約定
- **語言**：UI 字串用繁體中文 (zh-TW)
- **GUI framework**：CustomTkinter（dark mode 預設）
- **打包**：PyInstaller `--onefile`，**commit .exe 進 repo**（門市員工直接 copy 不用 build）
- **自動更新**：發現新版 → 一鍵下載並替換 exe → 重啟程式（fallback：開啟瀏覽器手動下載）
- **發布流程**：`sync.bat` → 改 `version.json` + `CHANGELOG` in main.py → commit + tag → GitHub Releases 上傳 exe

## Coding Style
- snake_case 函式變數、PascalCase 類別、私有 helper 前綴 `_`
- 不寫多餘 docstring；註解只寫 why、不寫 what
- subprocess call Windows command 一定要 redirect stderr 防卡死
- 寫到登錄機碼用 `winreg` 並 try/except、不要 raise 出 UI

## 系統優化項目（在 main.py 內定義）
- 關閉工作列小工具（Win11 天氣 / 新聞彈窗）
- 電源計畫：永不睡眠 / 關螢幕（含電池模式、筆電適用）
- 其他見 CHANGELOG

## 常見陷阱
- 修改 `main.py` 但忘記改 `APP_VERSION` / `CHANGELOG` → 自動更新不會觸發
- 用 PyInstaller --onefile 後路徑變 `sys._MEIPASS` 暫存 → 一定要用 `BASE_DIR` (L143-152) 解析
- subprocess 沒帶 `creationflags=CREATE_NO_WINDOW` → 跑系統命令會彈黑視窗
- 寫到 HKLM 沒先檢查管理員權限 → 寫入失敗但 UI 沒報錯
- 改 CHANGELOG 不更新 `APP_DATE` → 自動更新 UI 顯示舊日期
