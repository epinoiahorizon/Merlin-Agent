; Custom NSIS hooks for the certificate-free Windows install lane
; (electron-builder.config.cjs -> nsis). MSIX is the release target; this lane
; exists so a downloaded setup.exe installs like a conventional desktop app.
;
; electron-builder's template already writes DisplayName, DisplayVersion,
; Publisher and UninstallString. It leaves the two fields Windows uses to find
; and label an existing install blank, so an upgrade has to guess the folder
; and Apps & Features shows a generic icon. Fill both from $INSTDIR, which is
; whatever the user actually chose on the directory page.

!macro customInstall
  WriteRegStr SHELL_CONTEXT "${UNINSTALL_REGISTRY_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr SHELL_CONTEXT "${UNINSTALL_REGISTRY_KEY}" "DisplayIcon" "$INSTDIR\${APP_EXECUTABLE_FILENAME},0"
!macroend
