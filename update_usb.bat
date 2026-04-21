@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title AutoQuickSetup 隨身碟更新工具

set "SRC=%~dp0AutoQuickSetup.exe"
set "SELF_DRIVE=%~d0"

if not exist "%SRC%" (
    echo [錯誤] 找不到來源 exe：%SRC%
    echo 請確認 update_usb.bat 與 AutoQuickSetup.exe 放在同一個資料夾
    pause
    exit /b 1
)

echo 掃描隨身碟中（含子資料夾）...

set "FOUND_COUNT=0"
for %%D in (D E F G H I J K L M N O P Q R S T U V W X Y Z) do (
    if /i not "%%D:"=="%SELF_DRIVE%" (
        if exist "%%D:\" (
            if exist "%%D:\software\" if exist "%%D:\software_catalog.json" if exist "%%D:\AutoQuickSetup.exe" (
                set /a FOUND_COUNT+=1
                set "FOUND_!FOUND_COUNT!=%%D:\"
            )
            for /d %%S in ("%%D:\*") do (
                if exist "%%S\software\" if exist "%%S\software_catalog.json" if exist "%%S\AutoQuickSetup.exe" (
                    set /a FOUND_COUNT+=1
                    set "FOUND_!FOUND_COUNT!=%%S\"
                )
            )
        )
    )
)

if %FOUND_COUNT%==0 (
    echo.
    echo 沒偵測到 AutoQuickSetup 隨身碟。
    echo （條件：同時有 software\、software_catalog.json、AutoQuickSetup.exe^)
    echo.
    set /p "TARGET=請手動輸入路徑（例 D:\AutoQuickSetup\）或直接關閉："
    if "!TARGET!"=="" exit /b
    if "!TARGET:~-1!" neq "\" set "TARGET=!TARGET!\"
    if not exist "!TARGET!software\" (
        echo [錯誤] 路徑無效
        pause
        exit /b 1
    )
    goto CONFIRM
)

if %FOUND_COUNT%==1 (
    set "TARGET=!FOUND_1!"
    echo.
    echo 找到：!TARGET!
    goto CONFIRM
)

echo.
echo 找到 %FOUND_COUNT% 個候選位置：
for /l %%i in (1,1,%FOUND_COUNT%) do echo   [%%i] !FOUND_%%i!
echo.
echo 提示：Google Drive 同步資料夾也可能被列出（通常在 G:\），
echo 請選擇真正的隨身碟。
echo.
set /p "PICK=請選擇（輸入數字）："
if not defined FOUND_%PICK% (
    echo [錯誤] 編號無效
    pause
    exit /b 1
)
call set "TARGET=%%FOUND_%PICK%%%"

:CONFIRM
echo.
echo ============================================
echo  目標：%TARGET%
echo.
echo  會保留：software\、software_catalog.json
echo  會覆蓋：AutoQuickSetup.exe（貼上最新版）
echo  會刪除：.claude\、__pycache__\、logs\、
echo          .gitignore、main.py、README.md、
echo          sync.bat、sync_to_drive.bat、
echo          test_main.py、version.json、
echo          update_usb.bat、build\、dist\、*.spec
echo ============================================
echo.
set /p "CONFIRM=確定執行？(Y/N)："
if /i not "%CONFIRM%"=="Y" (
    echo 已取消
    pause
    exit /b
)

echo.
echo [1/2] 清理不需要的檔案...
for %%D in (.claude __pycache__ logs build dist) do (
    if exist "%TARGET%%%D\" (
        rmdir /s /q "%TARGET%%%D"
        echo   已刪除 %%D\
    )
)
for %%F in (.gitignore main.py README.md sync.bat sync_to_drive.bat test_main.py version.json update_usb.bat) do (
    if exist "%TARGET%%%F" (
        del /f /q "%TARGET%%%F"
        echo   已刪除 %%F
    )
)
for %%F in ("%TARGET%*.spec") do (
    if exist "%%F" (
        del /f /q "%%F"
        echo   已刪除 %%~nxF
    )
)

echo.
echo [2/2] 貼上新版 AutoQuickSetup.exe...
copy /y "%SRC%" "%TARGET%AutoQuickSetup.exe" >nul
if errorlevel 1 (
    echo [錯誤] 複製失敗！可能隨身碟滿了或被佔用
    pause
    exit /b 1
)
echo   已完成

echo.
echo ============================================
echo  完成！目標位置已更新為最新版
echo ============================================
pause
