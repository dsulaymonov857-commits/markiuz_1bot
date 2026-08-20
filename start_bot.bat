@echo off
title Markirovka Telegram Bot (Continuous Mode)
echo ==============================================
echo  Markirovka Telegram Bot ishga tushirilmoqda...
echo  (Uzluksiz va avtomatik qayta tiklanish rejimi)
echo ==============================================
cd /d "%~dp0"
.\.venv\Scripts\python.exe scripts\runner.py
pause
