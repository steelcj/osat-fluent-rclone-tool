@echo off
rem rclone.cmd — rendered by install-rclone.py; do not edit by hand
set "_cfg=%APPDATA%\rclone-tool\env.cmd"
if exist "%_cfg%" call "%_cfg%"
set "_bin=%LOCALAPPDATA%\rclone-tool\__RCLONE_VERSION__\rclone.exe"
"%_bin%" %*
