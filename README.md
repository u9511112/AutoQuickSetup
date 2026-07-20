# AutoQuickSetup - 萬能裝機自動化工具

一鍵安裝/解除安裝常用軟體 + 系統優化，專為 IT 裝機人員設計的可攜式工具。

---

## 使用方式

### 1. 準備隨身碟

將整個 `AutoQuickSetup` 資料夾複製到 USB 隨身碟（支援 USB-A / USB-C 雙頭隨身碟）：

```
USB 隨身碟/
└── AutoQuickSetup/
    ├── AutoQuickSetup.exe    ← 主程式（雙擊執行）
    ├── software_catalog.json ← 軟體對照表
    └── software/             ← 安裝檔存放處
```

### 2. 放入安裝檔

將需要安裝的軟體安裝檔放入 `software/` 資料夾。

目前支援的軟體：

| 檔案名稱 | 軟體 | 說明 |
|----------|------|------|
| ChromeSetup.exe | Google Chrome | 網頁瀏覽器，全球市佔率最高 |
| LibreOffice_24.8.5_Win_x86-64.msi | LibreOffice | 免費開源辦公套件（文書、試算表、簡報） |
| LineInst.exe | LINE | 即時通訊軟體（文字、語音、視訊通話） |
| OfficeSetup.exe | Microsoft Office | 微軟辦公套件（Word、Excel、PowerPoint） |
| PC-cillin.exe | 趨勢科技 PC-cillin | 防毒軟體，即時防護、網頁威脅過濾 |
| Player.exe | PotPlayer | 多媒體影音播放器，支援多種格式 |
| Setup-WPS.exe | WPS Office 中文版 | 辦公套件中文版（相容 MS Office 格式） |
| Setup-WPS 英文.exe | WPS Office 英文版 | 辦公套件英文版（相容 MS Office 格式） |
| Winrar.exe | WinRAR | 壓縮/解壓縮工具（支援 RAR、ZIP 等格式） |

> 放入其他 `.exe` 或 `.msi` 檔案也會自動識別並顯示在清單中。

### 3. 執行程式

1. 雙擊 `AutoQuickSetup.exe`
2. 系統會要求管理員權限（UAC），請點選「是」
3. 程式啟動後自動掃描 `software/` 資料夾，列出所有可安裝的軟體

### 4. 安裝軟體（📦 安裝分頁）

- **軟體安裝區**：勾選要安裝的軟體，每個軟體旁有功能說明
- **系統優化區**：勾選要執行的系統設定
  - 關閉休眠 — 釋放硬碟空間，加速開關機
  - 高效能電源計畫 — 關閉自動休眠與螢幕關閉
  - 桌面圖示：本機 — 顯示「本機」圖示
  - 桌面圖示：使用者資料夾 — 顯示個人資料夾圖示
  - 桌面圖示：控制台 — 顯示控制台圖示
  - 桌面圖示：網路 — 顯示網路圖示

> 已安裝的軟體會顯示綠色「✓ 已安裝」標記，預設不勾選（可手動勾選強制重裝）。

### 5. 解除安裝軟體（🗑 解除安裝分頁）

- 自動掃描電腦上所有已安裝的軟體
- 搜尋框即時篩選軟體名稱
- 勾選要移除的軟體，點擊「🗑 解除安裝」
- 解除安裝前會彈出確認對話框，防止誤刪
- 支援靜默解除安裝 + 彈窗自動點擊

### 6. 開始安裝/解除安裝

點擊對應按鈕後：

- 進度條即時顯示進度與百分比
- 每個軟體最多等待 10 分鐘，超時自動跳過
- 安裝程式彈出的同意/下一步對話框會自動處理（含 LINE 等 Electron 安裝程式）
- 完成後語音通知：
  - 全部成功 →「全部安裝完成」/「全部解除安裝完成」
  - 有失敗 →「安裝完成，其中 N 個失敗」
- 結果自動儲存到 `logs/` 資料夾

---

## 功能說明

### 智慧偵測

程式啟動時在背景自動檢查電腦上已安裝的軟體，已安裝的項目會標記為綠色，避免重複安裝。（背景執行，不影響啟動速度）

### 設定檔

- **儲存設定**：將目前的勾選組合儲存為設定檔（例如「基本裝機」「全套安裝」）
- **載入設定**：下次裝機時直接載入設定檔，一鍵套用

設定檔存放在 `configs/` 資料夾中，可跨機器使用。

> 若隨身碟為唯讀狀態，儲存設定會顯示警告而非崩潰。

### 主題切換

右上角按鈕可切換深色/淺色主題。

### 安裝日誌

每次安裝/解除安裝完成後，結果會自動記錄到 `logs/` 資料夾，格式：

```
install_log_20260415_081500.txt
```

內容包含：時間、每個項目的結果（成功/失敗）、錯誤訊息、署名。

> 若隨身碟為唯讀狀態，日誌無法寫入但不影響安裝流程。

### 自動更新檢查

每次啟動時，程式會自動連線檢查是否有新版本。若有新版會彈出通知，可選擇前往下載或稍後再說。離線環境下會自動跳過，不影響使用。

### 彈窗自動處理

安裝過程中，若安裝程式彈出同意條款、下一步、安裝等對話框，程式會自動勾選同意並點擊。支援：

- 標準 Windows 安裝程式（UIA 控制項偵測）
- Electron/網頁式安裝程式如 LINE（鍵盤模擬 Tab + Space + Enter）
- 安全防護：不會點擊「刪除」「格式化」等危險按鈕，也不會誤觸自身視窗

---

## 新增軟體

### 方法一：直接放入

將安裝檔（`.exe` 或 `.msi`）放入 `software/` 資料夾，程式會自動識別。

### 方法二：自訂名稱和說明

編輯 `software_catalog.json`，新增一筆：

```json
{
  "pattern": "你的檔名*.exe",
  "name": "顯示名稱",
  "description": "軟體說明文字",
  "silent_args": "/S",
  "type": "exe",
  "requires_config": false
}
```

| 欄位 | 說明 |
|------|------|
| pattern | 檔名匹配模式（支援 `*` 萬用字元） |
| name | 介面上顯示的軟體名稱 |
| description | 軟體功能說明 |
| silent_args | 靜默安裝參數 |
| type | `exe` 或 `msi` |
| requires_config | 是否需要額外設定檔（如 Office） |

---

## Microsoft Office 注意事項

Microsoft Office 使用 Click-to-Run 安裝方式，需要額外的 `configuration.xml` 設定檔。

將 `configuration.xml` 放入 `software/` 資料夾。若缺少此檔案，程式會跳過 Office 並顯示警告。

---

## 資料夾結構

```
AutoQuickSetup/
├── AutoQuickSetup.exe        ← 主程式
├── main.py                   ← Python 原始碼
├── software_catalog.json     ← 軟體對照表
├── version.json              ← 版本資訊（自動更新用）
├── software/                 ← 安裝檔存放處
│   ├── ChromeSetup.exe
│   ├── LineInst.exe
│   └── ...
├── configs/                  ← 設定檔（自動建立）
│   └── 基本裝機.json
└── logs/                     ← 安裝日誌（自動建立）
    └── install_log_20260415_081500.txt
```

---

## 系統需求

- Windows 10 / 11（所有品牌筆電適用：Lenovo、Dell、HP、ASUS、Acer、MSI 等）
- 需要管理員權限（安裝軟體和修改系統設定）
- USB 建議格式化為 exFAT（FAT32 不支援超過 4GB 的安裝檔）
- 支援 USB-A / USB-C 雙頭隨身碟

### 不支援
- Windows S Mode（需先切換出 S Mode）
- ARM 架構 Windows（如 Surface Pro X）的自動點擊功能可能受限

---

## 注意事項

- 本自動裝機系統只能安裝正版授權軟體
- 程式只會安裝 `software/` 資料夾內的檔案，不會從網路下載任何東西
- 安裝過程中請勿關閉程式
- 系統優化若部分指令因權限或環境限制失敗，會在結果中標示，不影響其他項目

---

## 開發者：執行測試

測試檔為 `test_main.py`（自製輕量框架，直接以 Python 執行，無需 pytest）：

```bash
# Windows 必須帶 PYTHONUTF8=1，否則 cp950 編碼印不出 ✓ 會直接崩潰
set PYTHONUTF8=1 && .venv\Scripts\python.exe test_main.py
```

PowerShell：

```powershell
$env:PYTHONUTF8=1; .venv\Scripts\python.exe test_main.py
```

目前共 152 項測試，全數通過視為可發布。

---

By: 謝智翔
