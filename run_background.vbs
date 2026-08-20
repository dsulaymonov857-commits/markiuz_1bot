Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "c:\Users\User\Desktop\markirovka"
WshShell.Run """c:\Users\User\Desktop\markirovka\.venv\Scripts\python.exe"" ""c:\Users\User\Desktop\markirovka\scripts\runner.py""", 0, False
