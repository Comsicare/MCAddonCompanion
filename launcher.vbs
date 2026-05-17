Set WshShell = CreateObject("WScript.Shell")
Dim batPath
batPath = Replace(WScript.ScriptFullName, "launcher.vbs", "launcher.bat")
WshShell.Run Chr(34) & batPath & Chr(34), 0, False
Set WshShell = Nothing
