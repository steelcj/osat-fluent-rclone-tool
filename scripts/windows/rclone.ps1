# rclone.ps1 — rendered by install-rclone.py; do not edit by hand
$_cfg = "$env:APPDATA\rclone-tool\env.ps1"
if (Test-Path $_cfg) { . $_cfg }
$_bin = "$env:LOCALAPPDATA\rclone-tool\__RCLONE_VERSION__\rclone.exe"
& $_bin @args
