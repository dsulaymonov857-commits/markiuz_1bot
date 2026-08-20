@echo off
title Markirovka Bot - Windows Avto-yuklanishiga qoshish
echo ========================================================
echo  Markirovka Botini Windows Startup (Avtozagruzka) ga qoshish...
echo ========================================================
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([Environment]::GetFolderPath('Startup') + '\Markirovka Bot.lnk'); $s.TargetPath = 'c:\Users\User\Desktop\markirovka\start_bot.bat'; $s.WorkingDirectory = 'c:\Users\User\Desktop\markirovka'; $s.Save(); Write-Host 'Muvaffaqiyatli qoshildi!' -ForegroundColor Green"
echo.
pause
