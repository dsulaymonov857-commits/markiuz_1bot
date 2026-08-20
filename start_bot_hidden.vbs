Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "c:\Users\User\Desktop\markirovka"
WshShell.Run ".\.venv\Scripts\python.exe scripts\runner.py", 0, False
