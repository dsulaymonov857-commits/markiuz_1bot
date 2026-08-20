import os
import subprocess
from pathlib import Path

startup_dir = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
target_bat = Path(r"c:\Users\User\Desktop\markirovka\start_bot.bat").resolve()
target_dir = Path(r"c:\Users\User\Desktop\markirovka").resolve()
shortcut_path = startup_dir / "Markirovka Bot.lnk"

vbs_code = f"""
Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{str(shortcut_path)}"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "{str(target_bat)}"
oLink.WorkingDirectory = "{str(target_dir)}"
oLink.Description = "Markirovka Telegram Bot Runner"
oLink.Save
"""

temp_vbs = target_dir / "temp_create_shortcut.vbs"
temp_vbs.write_text(vbs_code, encoding="utf-8")
try:
    subprocess.run(["cscript", "//nologo", str(temp_vbs)], check=True)
    print(f"Muvaffaqiyatli yaratildi: {shortcut_path}")
finally:
    if temp_vbs.exists():
        temp_vbs.unlink()
