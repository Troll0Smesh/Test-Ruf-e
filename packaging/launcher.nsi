Unicode True
Target amd64-unicode
ManifestSupportedOS Win10
Name "Джарвис"
Icon "../src/jarvis_pc/assets/jarvis.ico"
OutFile "${PAYLOAD}/Jarvis.exe"
RequestExecutionLevel user
SilentInstall silent
AutoCloseWindow true
ShowInstDetails nevershow
VIProductVersion "0.4.0.0"
VIAddVersionKey "ProductName" "Джарвис"
VIAddVersionKey "FileDescription" "Голосовой помощник Джарвис"
VIAddVersionKey "FileVersion" "0.4.0"
Section
  SetOutPath "$EXEDIR"
  Exec '"$EXEDIR\runtime\pythonw.exe" -I "$EXEDIR\app\launcher.py"'
  IfErrors 0 done
  MessageBox MB_ICONSTOP "Не удалось запустить приложение. Переустановите Джарвис."
  done:
SectionEnd
