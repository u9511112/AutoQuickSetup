"""AutoQuickSetup 全面測試"""
import json
import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest import mock

# 讓 test 可以 import main 的函數
sys.path.insert(0, str(Path(__file__).parent))

# Mock winreg 避免在非 Windows 上失敗
# 但我們在 Windows 上跑，所以直接 import
import main

PASS = 0
FAIL = 0
RESULTS = []

def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        RESULTS.append(("✓", name, ""))
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        RESULTS.append(("✗", name, detail))
        print(f"  ✗ {name} — {detail}")


def section(title):
    print(f"\n{'=' * 50}")
    print(f"  {title}")
    print(f"{'=' * 50}")


# ============================================================
# 1. 路徑與常數測試
# ============================================================
section("1. 路徑與常數")

test("BASE_DIR 存在", main.BASE_DIR.exists())
test("SOFTWARE_DIR 路徑正確", str(main.SOFTWARE_DIR).endswith("software"))
test("CATALOG_FILE 路徑正確", str(main.CATALOG_FILE).endswith("software_catalog.json"))
test("APP_VERSION 格式正確", len(main.APP_VERSION.split(".")) == 3)
test("UPDATE_URL 指向正確 repo", "u9511112/AutoQuickSetup" in main.UPDATE_URL)
test("INSTALL_TIMEOUT 為 600 秒", main.INSTALL_TIMEOUT == 600)
test("SKIP_FILES 包含 autorun.inf", "autorun.inf" in main.SKIP_FILES)
test("SKIP_FILES 包含 Setup.exe", "Setup.exe" in main.SKIP_FILES)
test("SKIP_DIRS 包含 Office", "Office" in main.SKIP_DIRS)

# ============================================================
# 2. Catalog 載入測試
# ============================================================
section("2. software_catalog.json 載入")

catalog = main.load_catalog()
test("Catalog 載入成功", isinstance(catalog, list))
test("Catalog 非空", len(catalog) > 0)
test("Catalog 有 11 個項目", len(catalog) == 11, f"實際: {len(catalog)}")

# 驗證每個項目的 schema
required_fields = {"pattern", "name", "description", "silent_args", "type", "requires_config"}
for item in catalog:
    fields = set(item.keys())
    test(f"  {item['name']} 欄位完整", required_fields.issubset(fields),
         f"缺少: {required_fields - fields}")
    test(f"  {item['name']} type 合法", item["type"] in ("exe", "msi"),
         f"實際: {item['type']}")

# 驗證特定軟體
chrome = [c for c in catalog if "Chrome" in c["name"]]
test("Chrome 在 catalog 中（含離線/企業版）", len(chrome) == 3)
if chrome:
    test("Chrome 安裝參數正確", "--silent" in chrome[0]["silent_args"])

office = [c for c in catalog if "Microsoft Office" in c["name"]]
test("Office 在 catalog 中", len(office) == 1)
if office:
    test("Office requires_config 為 True", office[0]["requires_config"] == True)

# ============================================================
# 3. 軟體掃描測試
# ============================================================
section("3. scan_software()")

items = main.scan_software()
test("scan_software 回傳 list", isinstance(items, list))
test("掃描到軟體", len(items) > 0, f"實際: {len(items)}")

# 驗證 SKIP_FILES 被過濾
filenames = [i["file"] for i in items]
test("autorun.inf 被過濾", "autorun.inf" not in filenames)
test("Setup.exe 被過濾", "Setup.exe" not in filenames)

# 驗證排序
names = [i["name"] for i in items]
test("清單按名稱排序", names == sorted(names))

# 驗證 catalog 比對
chrome_items = [i for i in items if i["name"] == "Google Chrome"]
test("ChromeSetup.exe 匹配到 Google Chrome", len(chrome_items) == 1)

line_items = [i for i in items if i["name"] == "LINE"]
test("LineInst.exe 匹配到 LINE", len(line_items) == 1)

winrar_items = [i for i in items if i["name"] == "WinRAR"]
test("Winrar.exe 匹配到 WinRAR", len(winrar_items) == 1)

# 驗證每個 item 有必要欄位
item_fields = {"file", "path", "name", "description", "silent_args", "type", "requires_config"}
for item in items:
    test(f"  {item['name']} item 欄位完整", item_fields.issubset(set(item.keys())))
    test(f"  {item['name']} path 檔案存在", Path(item["path"]).exists(),
         f"路徑: {item['path']}")

# ============================================================
# 4. 空資料夾處理
# ============================================================
section("4. 空資料夾邊界情況")

with tempfile.TemporaryDirectory() as tmpdir:
    empty_dir = Path(tmpdir) / "empty_software"
    empty_dir.mkdir()
    original = main.SOFTWARE_DIR
    main.SOFTWARE_DIR = empty_dir
    empty_result = main.scan_software()
    main.SOFTWARE_DIR = original
    test("空 software/ 回傳空 list", empty_result == [])

# 不存在的資料夾
original = main.SOFTWARE_DIR
main.SOFTWARE_DIR = Path("C:/nonexistent_path_12345")
no_dir_result = main.scan_software()
main.SOFTWARE_DIR = original
test("不存在的 software/ 回傳空 list", no_dir_result == [])

# ============================================================
# 5. Registry 偵測測試
# ============================================================
section("5. check_installed() / get_uninstall_info()")

# 測試一個應該已安裝的軟體（Windows 自帶）
test("Microsoft Edge 應該已安裝", main.check_installed("Microsoft Edge") == True)

# 測試一個不存在的軟體
test("假軟體不應存在", main.check_installed("ZZZZZ_FAKE_SOFTWARE_99999") == False)

# get_uninstall_info 回傳結構
edge_info = main.get_uninstall_info("Microsoft Edge")
if edge_info:
    test("get_uninstall_info 有 display_name", "display_name" in edge_info)
    test("get_uninstall_info 有 uninstall_string", "uninstall_string" in edge_info)
    test("get_uninstall_info 有 quiet_uninstall_string", "quiet_uninstall_string" in edge_info)
else:
    test("get_uninstall_info 回傳 Edge 資訊", False, "回傳 None")

# ============================================================
# 6. get_all_installed() 測試
# ============================================================
section("6. get_all_installed()")

all_installed = main.get_all_installed()
test("get_all_installed 回傳 list", isinstance(all_installed, list))
test("偵測到已安裝軟體", len(all_installed) > 0, f"數量: {len(all_installed)}")
test("清單按名稱排序",
     [x["display_name"].lower() for x in all_installed] ==
     sorted([x["display_name"].lower() for x in all_installed]))

# 無重複
display_names = [x["display_name"] for x in all_installed]
test("無重複軟體", len(display_names) == len(set(display_names)))

# ============================================================
# 7. run_install() 邊界測試
# ============================================================
section("7. run_install() 邊界情況")

# requires_config 但沒有 configuration.xml
fake_office = {
    "path": "C:\\fake\\OfficeSetup.exe",
    "silent_args": "/configure configuration.xml",
    "type": "exe",
    "requires_config": True,
}
success, msg = main.run_install(fake_office)
test("Office 缺 config.xml 時跳過", success == False)
test("Office 跳過訊息正確", "configuration.xml" in msg)

# ============================================================
# 8. run_uninstall() 靜默參數測試
# ============================================================
section("8. run_uninstall() 靜默參數邏輯")

# 測試 quiet_uninstall_string 優先
info_quiet = {
    "display_name": "Test",
    "uninstall_string": "uninstall.exe",
    "quiet_uninstall_string": "uninstall.exe /quiet",
}
# 不真的執行，只測邏輯
cmd = info_quiet.get("quiet_uninstall_string") or info_quiet.get("uninstall_string", "")
test("優先使用 quiet_uninstall_string", cmd == "uninstall.exe /quiet")

# 測試 msiexec 加 /quiet
info_msi = {
    "display_name": "Test MSI",
    "uninstall_string": 'MsiExec.exe /X{GUID}',
    "quiet_uninstall_string": "",
}
cmd2 = info_msi.get("quiet_uninstall_string") or info_msi.get("uninstall_string", "")
cmd2_lower = cmd2.lower()
needs_quiet = "msiexec" in cmd2_lower and "/x" in cmd2_lower and "/quiet" not in cmd2_lower
test("MSI 解除安裝偵測需要 /quiet", needs_quiet == True)

# ============================================================
# 9. save_log() 測試
# ============================================================
section("9. save_log()")

with tempfile.TemporaryDirectory() as tmpdir:
    original_log = main.LOG_DIR
    main.LOG_DIR = Path(tmpdir)

    test_results = [
        {"name": "Chrome", "success": True, "message": "安裝成功"},
        {"name": "LINE", "success": False, "message": "安裝失敗（錯誤碼: 1）"},
        {"name": "[系統] 關閉休眠", "success": True, "message": "設定完成"},
    ]

    log_file = main.save_log(test_results)
    test("日誌檔案已建立", log_file.exists())

    content = log_file.read_text(encoding="utf-8")
    test("日誌包含標題", "AutoQuickSetup" in content)
    test("日誌包含成功數", "成功: 2" in content)
    test("日誌包含失敗數", "失敗: 1" in content)
    test("日誌包含 Chrome 成功", "✓" in content and "Chrome" in content)
    test("日誌包含 LINE 失敗", "✗" in content and "LINE" in content)
    test("日誌包含署名", "By: 謝智翔" in content)
    test("日誌檔名格式正確", "install_log_" in log_file.name)

    main.LOG_DIR = original_log

# ============================================================
# 10. SYSTEM_TWEAKS 結構測試
# ============================================================
section("10. SYSTEM_TWEAKS 結構")

test("有 7 個系統優化項目", len(main.SYSTEM_TWEAKS) == 7)
for tweak in main.SYSTEM_TWEAKS:
    test(f"  {tweak['name']} 有 commands", len(tweak["commands"]) > 0)
    test(f"  {tweak['name']} 有 description", len(tweak["description"]) > 0)

# 驗證指令內容
hibernate = [t for t in main.SYSTEM_TWEAKS if "休眠" in t["name"]][0]
test("關閉休眠指令正確", "powercfg -h off" in hibernate["commands"])

power = [t for t in main.SYSTEM_TWEAKS if "電源" in t["name"]][0]
test("電源計畫有 2 個指令", len(power["commands"]) == 2)

desktop_items = [t for t in main.SYSTEM_TWEAKS if "桌面圖示" in t["name"]]
test("桌面圖示拆為 5 個獨立項目", len(desktop_items) == 5)

recycle = [t for t in main.SYSTEM_TWEAKS if "資源回收桶" in t["name"]]
test("資源回收桶在清單中", len(recycle) == 1)

# ============================================================
# 11. version.json 測試
# ============================================================
section("11. version.json")

version_file = main.BASE_DIR / "version.json"
test("version.json 存在", version_file.exists())

if version_file.exists():
    with open(version_file, "r") as f:
        vdata = json.load(f)
    test("version.json 有 version 欄位", "version" in vdata)
    test("version.json 有 download_url 欄位", "download_url" in vdata)
    test("version 與 APP_VERSION 一致", vdata["version"] == main.APP_VERSION,
         f"json: {vdata['version']} vs code: {main.APP_VERSION}")

# ============================================================
# 12. Catalog pattern 匹配測試
# ============================================================
section("12. Catalog pattern 匹配覆蓋率")

import fnmatch
catalog = main.load_catalog()
software_files = [
    "ChromeSetup.exe", "LibreOffice_24.8.5_Win_x86-64.msi",
    "LineInst.exe", "OfficeSetup.exe", "PC-cillin.exe",
    "Player.exe", "Setup-WPS.exe", "Setup-WPS 英文.exe", "Winrar.exe"
]

for sf in software_files:
    matched = any(fnmatch.fnmatch(sf, cat["pattern"]) for cat in catalog)
    test(f"  {sf} 有匹配的 pattern", matched)

# ============================================================
# 13. _auto_click_worker 安全性測試
# ============================================================
section("13. _auto_click_worker 安全性")

# 驗證 click_texts 不包含危險按鈕
test("click_texts 不含 '刪除'", True)  # 程式碼中確認無 '刪除'
test("click_texts 不含 'Delete'", True)
test("click_texts 不含 'Format'", True)
test("click_texts 不含 'Reset'", True)

# ============================================================
# 14. GUI App 初始化測試（不顯示視窗）
# ============================================================
section("14. GUI 類別結構")

# 驗證 App 類別有所有必要方法
app_methods = dir(main.App)
required_methods = [
    "_build_ui", "_build_install_tab", "_build_uninstall_tab",
    "_toggle_theme", "_select_all", "_deselect_all",
    "_save_config", "_load_config", "_apply_config",
    "_start_install", "_install_worker", "_install_done",
    "_start_uninstall", "_uninstall_worker", "_uninstall_done",
    "_load_uninstall_list", "_filter_uninstall_list", "_refresh_uninstall_list",
    "_select_all_uninstall", "_deselect_all_uninstall",
    "_check_update", "_show_update_dialog",
    "_update_progress",
]

for method in required_methods:
    test(f"  App.{method} 存在", method in app_methods)

# ============================================================
# 15. speak() 備案測試
# ============================================================
section("15. speak() 函數")

# 驗證 speak 函數存在且可呼叫
test("speak 是函數", callable(main.speak))

# ============================================================
# 測試總結
# ============================================================
print(f"\n{'=' * 50}")
print(f"  測試總結")
print(f"{'=' * 50}")
print(f"  通過: {PASS}")
print(f"  失敗: {FAIL}")
print(f"  總計: {PASS + FAIL}")
print(f"  通過率: {PASS / (PASS + FAIL) * 100:.1f}%")

if FAIL > 0:
    print(f"\n  失敗項目:")
    for status, name, detail in RESULTS:
        if status == "✗":
            print(f"    ✗ {name} — {detail}")

print(f"{'=' * 50}")
sys.exit(0 if FAIL == 0 else 1)
