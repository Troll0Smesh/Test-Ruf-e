Unicode True
Target amd64-unicode
ManifestSupportedOS Win10
!include "MUI2.nsh"
!include "x64.nsh"
!include "WinVer.nsh"
Name "Джарвис"
Icon "../src/jarvis_pc/assets/jarvis.ico"
OutFile "${OUTPUT}/Jarvis-Setup-0.4.1-x64.exe"
InstallDir "$LOCALAPPDATA\Programs\JarvisPC"
InstallDirRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\JarvisPC" "InstallLocation"
RequestExecutionLevel user
SetCompressor /SOLID zlib
VIProductVersion "0.4.1.0"
VIAddVersionKey "ProductName" "Джарвис"
VIAddVersionKey "FileDescription" "Установка голосового помощника Джарвис"
VIAddVersionKey "FileVersion" "0.4.1"
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN "$INSTDIR\Jarvis.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Запустить Джарвис"
!insertmacro MUI_PAGE_WELCOME
!define MUI_PAGE_CUSTOMFUNCTION_LEAVE CheckInstallDirectory
!insertmacro MUI_PAGE_DIRECTORY
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
FunctionEnd

Function CheckInstallDirectory
  IfFileExists "$INSTDIR\*.*" 0 checkWritable
  IfFileExists "$INSTDIR\.jarvis-install" checkWritable 0
  MessageBox MB_ICONSTOP "Папка $INSTDIR уже занята другими файлами. Установка остановлена."
  Abort
  checkWritable:
  ClearErrors
  CreateDirectory "$INSTDIR"
  IfErrors 0 tryWrite
  MessageBox MB_ICONSTOP "Нет доступа к папке $INSTDIR. Выберите папку, доступную вашему пользователю."
  Abort
  tryWrite:
  ClearErrors
  FileOpen $0 "$INSTDIR\.jarvis-write-test" w
  IfErrors 0 writable
  MessageBox MB_ICONSTOP "Нет права записи в папку $INSTDIR. Выберите другую папку."
  Abort
  writable:
  FileClose $0
  Delete "$INSTDIR\.jarvis-write-test"
FunctionEnd

Section "Джарвис"
  SetShellVarContext current
  SetOutPath "$INSTDIR"
  File /r "${PAYLOAD}/*"
  FileOpen $0 "$INSTDIR\.jarvis-install" w
  FileWrite $0 "JarvisPC 0.4.1"
  FileClose $0
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\Джарвис"
  CreateShortcut "$SMPROGRAMS\Джарвис\Джарвис.lnk" "$INSTDIR\Jarvis.exe"
  CreateShortcut "$DESKTOP\Джарвис.lnk" "$INSTDIR\Jarvis.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\JarvisPC" "DisplayName" "Джарвис"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\JarvisPC" "DisplayVersion" "0.4.1"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\JarvisPC" "InstallLocation" "$INSTDIR"
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
