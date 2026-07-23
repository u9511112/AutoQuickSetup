@echo off
chcp 65001 >nul 2>&1
title AutoQuickSetup - 同步到雲端硬碟

set "SRC=%~dp0"
if "%SRC:~-1%"=="\" set "SRC=%SRC:~0,-1%"
set "DST=%USERPROFILE%\Google Drive\AutoQuickSetup"

echo ===================================================
echo   同步 AutoQuickSetup 到 Google Drive
echo ===================================================
echo.

:: 同步主要檔案
echo [1/4] 同步程式檔案...
copy /Y "%SRC%\main.py" "%DST%\" >nul
copy /Y "%SRC%\software_catalog.json" "%DST%\" >nul
copy /Y "%SRC%\version.json" "%DST%\" >nul
copy /Y "%SRC%\README.md" "%DST%\" >nul
copy /Y "%SRC%\test_main.py" "%DST%\" >nul
copy /Y "%SRC%\.gitignore" "%DST%\" >nul
echo     -> 完成

:: 同步 EXE
echo [2/4] 同步 EXE...
if exist "%SRC%\AutoQuickSetup.exe" (
    copy /Y "%SRC%\AutoQuickSetup.exe" "%DST%\" >nul
    echo     -> 完成
) else (
    echo     -> [略過] 找不到 EXE
)

:: 同步 software 資料夾
echo [3/4] 同步 software 資料夾...
if not exist "%DST%\software" mkdir "%DST%\software"
xcopy /Y /E /I "%SRC%\software" "%DST%\software" >nul 2>&1
echo     -> 完成

:: 推送到 GitHub（提供雲端更新給其他電腦）
echo [4/4] 推送到 GitHub...
pushd "%SRC%"
git push
popd
echo     -> 完成

echo.
echo ===================================================
echo   同步完成！ %date% %time%
echo ===================================================
pause
