Unicode True
Target amd64-unicode
ManifestSupportedOS Win10
!include "MUI2.nsh"
!include "x64.nsh"
!include "WinVer.nsh"
Name "Джарвис"
Icon "../src/jarvis_pc/assets/jarvis.ico"
OutFile "${OUTPUT}/Jarvis-Setup-0.2.0-x64.exe"
InstallDir "$LOCALAPPDATA\Programs\JarvisPC"
RequestExecutionLevel user
SetCompressor /SOLID zlib
VIProductVersion "0.2.0.0"
VIAddVersionKey "ProductName" "Джарвис"
VIAddVersionKey "FileDescription" "Установка голосового помощника Джарвис"
VIAddVersionKey "FileVersion" "0.2.0"
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN "$INSTDIR\Jarvis.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Запустить Джарвис"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Russian"

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "Нужна 64-разрядная Windows 10 или 11."
    Abort
  ${EndIf}
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_ICONSTOP "Нужна Windows 10 или 11."
    Abort
  ${EndIf}
  System::Call 'kernel32::OpenMutexW(i 0x100000, i 0, w "Local\JarvisPC.Desktop") p .r0'
  IntCmp $0 0 available
  System::Call 'kernel32::CloseHandle(p r0)'
  MessageBox MB_ICONINFORMATION "Закройте окно Джарвиса перед установкой обновления."
  Abort
  available:
  IfFileExists "$INSTDIR\*.*" 0 ready
  IfFileExists "$INSTDIR\.jarvis-install" ready 0
  MessageBox MB_ICONSTOP "Папка $INSTDIR уже занята другими файлами. Установка остановлена."
  Abort
  ready:
FunctionEnd

Section "Джарвис"
  SetShellVarContext current
  SetOutPath "$INSTDIR"
  File /r "${PAYLOAD}/*"
  FileOpen $0 "$INSTDIR\.jarvis-install" w
  FileWrite $0 "JarvisPC 0.2.0"
  FileClose $0
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\Джарвис"
  CreateShortcut "$SMPROGRAMS\Джарвис\Джарвис.lnk" "$INSTDIR\Jarvis.exe"
  CreateShortcut "$DESKTOP\Джарвис.lnk" "$INSTDIR\Jarvis.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\JarvisPC" "DisplayName" "Джарвис"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\JarvisPC" "DisplayVersion" "0.2.0"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\JarvisPC" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\JarvisPC" "DisplayIcon" "$INSTDIR\Jarvis.exe"
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\JarvisPC" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\JarvisPC" "NoRepair" 1
SectionEnd

Function un.onInit
  System::Call 'kernel32::OpenMutexW(i 0x100000, i 0, w "Local\JarvisPC.Desktop") p .r0'
  IntCmp $0 0 ready
  System::Call 'kernel32::CloseHandle(p r0)'
  MessageBox MB_ICONINFORMATION "Сначала закройте окно Джарвиса."
  Abort
  ready:
FunctionEnd

Section "Uninstall"
  SetShellVarContext current
  Delete "$DESKTOP\Джарвис.lnk"
  Delete "$SMPROGRAMS\Джарвис\Джарвис.lnk"
  RMDir "$SMPROGRAMS\Джарвис"
  RMDir /r "$INSTDIR\runtime"
  RMDir /r "$INSTDIR\app"
  RMDir /r "$INSTDIR\models"
  Delete "$INSTDIR\Jarvis.exe"
  Delete "$INSTDIR\.jarvis-install"
  Delete "$INSTDIR\LICENSE"
  Delete "$INSTDIR\BUILD-MANIFEST.json"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\JarvisPC"
SectionEnd
