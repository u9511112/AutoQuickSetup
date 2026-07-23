@echo off
chcp 65001 >nul 2>&1
set "SRC=%~dp0"
if "%SRC:~-1%"=="\" set "SRC=%SRC:~0,-1%"
set "DST=%USERPROFILE%\Google Drive\AutoQuickSetup"
if not exist "%DST%" mkdir "%DST%"
if not exist "%DST%\software" mkdir "%DST%\software"
copy /Y "%SRC%\main.py" "%DST%\" >nul 2>&1
copy /Y "%SRC%\software_catalog.json" "%DST%\" >nul 2>&1
copy /Y "%SRC%\version.json" "%DST%\" >nul 2>&1
copy /Y "%SRC%\README.md" "%DST%\" >nul 2>&1
copy /Y "%SRC%\test_main.py" "%DST%\" >nul 2>&1
copy /Y "%SRC%\AutoQuickSetup.exe" "%DST%\" >nul 2>&1
echo 已同步到 Google Drive
pushd "%SRC%"
git push
popd
echo 已推送到 GitHub
