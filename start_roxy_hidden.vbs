' Starts start_roxy.bat without a console window (used by the Windows Startup shortcut)
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
CreateObject("WScript.Shell").Run """" & folder & "\start_roxy.bat""", 0, False
