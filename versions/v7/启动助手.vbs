Option Explicit
Dim shell, fso, folder, pythonExe, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
pythonExe = folder & "\.venv\Scripts\pythonw.exe"
If Not fso.FileExists(pythonExe) Then
    pythonExe = "pyw.exe"
End If
command = """" & pythonExe & """ """ & folder & "\duty_assistant.py"""
shell.CurrentDirectory = folder
shell.Run command, 0, False
