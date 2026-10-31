@echo off
setlocal
title AI Facial Asymmetry Analysis Platform — Launcher

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
