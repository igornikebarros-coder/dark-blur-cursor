#Requires AutoHotkey v2.0
#SingleInstance Force
Persistent()

; ============================================================================
;  Dark Blur Cursor - Click Animations (AutoHotkey v2)
;
;  Plays a monochrome glass effect at the mouse pointer on every left click.
;  The effects are pre-rendered frames (<effect>-<dark|light>.bgra, effects: ripple,
;  glow, particle, orbit): 40 frames of 160x160 px, 32bpp, top-down, B,G,R,A bytes
;  with PREMULTIPLIED alpha. Frames are blitted to a click-through layered window with
;  UpdateLayeredWindow. Keep this script and the .bgra files in the same folder.
;
;  Tray menu: enable/disable, choose effect, choose theme (auto / dark / light),
;  start with Windows, exit.
;  Hotkeys:   Ctrl+Alt+F9  = toggle on/off     Ctrl+Alt+F10 = next effect
;             Ctrl+Alt+F11 = next theme (auto -> dark -> light)
;  Test only: AutoHotkey64.exe click-animations.ahk --check   (loads files, no overlay)
; ============================================================================

AppName    := "Dark Blur Cursor"
FrameCount := 40
FrameSize  := 160
FrameBytes := FrameSize * FrameSize * 4
FrameMs    := 16
EffectFiles  := ["ripple", "glow", "particle", "orbit"]
ThemeKeys    := ["auto", "dark", "light"]
SettingsFile := A_ScriptDir "\settings.ini"
StartupLink  := A_Startup "\Dark Blur Click Animations.lnk"

; ---------------------------------------------------------------- language
LangId := DllCall("GetUserDefaultUILanguage", "UShort") & 0x3FF
if (LangId = 0x16) {      ; Portuguese
    Labels := Map(
        "Enabled", "Animações de clique ativadas",
        "ripple", "Ondulação",
        "glow", "Brilho",
        "particle", "Partículas",
        "orbit", "Órbita",
        "auto", "Tema: automático (Windows)",
        "dark", "Tema: escuro",
        "light", "Tema: claro",
        "Startup", "Iniciar com o Windows",
        "Exit", "Sair",
        "Missing", "Arquivo de efeito não encontrado:",
        "Bad", "Arquivo de efeito incompleto:",
        "Check", "OK: 8 efeitos carregados (4 x escuro/claro); nenhuma sobreposição aberta."
    )
} else {
    Labels := Map(
        "Enabled", "Click animations enabled",
        "ripple", "Ripple",
        "glow", "Glow pulse",
        "particle", "Particles",
        "orbit", "Orbit",
        "auto", "Theme: automatic (Windows)",
        "dark", "Theme: dark",
        "light", "Theme: light",
        "Startup", "Start with Windows",
        "Exit", "Exit",
        "Missing", "Effect file not found:",
        "Bad", "Effect file is incomplete:",
        "Check", "PASS: 8 effects loaded (4 x dark/light); no overlay opened."
    )
}
EnabledLabel := Labels["Enabled"]
StartupLabel := Labels["Startup"]
StyleNames := []
for name in EffectFiles
    StyleNames.Push(Labels[name])
ThemeNames := []
for name in ThemeKeys
    ThemeNames.Push(Labels[name])

; ------------------------------------------------------------ load frames
Frames := Map("dark", [], "light", [])
for theme in ["dark", "light"] {
    for name in EffectFiles {
        path := A_ScriptDir "\" name "-" theme ".bgra"
        if !FileExist(path) {
            MsgBox(Labels["Missing"] "`n" path, AppName, "Iconx")
            ExitApp()
        }
        data := FileRead(path, "RAW")
        if (data.Size != FrameCount * FrameBytes) {
            MsgBox(Labels["Bad"] "`n" path, AppName, "Iconx")
            ExitApp()
        }
        Frames[theme].Push(data)
    }
}
if (A_Args.Length && A_Args[1] = "--check") {
    FileAppend(Labels["Check"] "`n", "*")
    ExitApp(0)
}

; --------------------------------------------------------------- settings
SelectedStyle := 1
Enabled := true
try {
    SelectedStyle := Integer(IniRead(SettingsFile, "General", "Effect", "1"))
    Enabled := (IniRead(SettingsFile, "General", "Enabled", "1") = "1")
}
if (SelectedStyle < 1 || SelectedStyle > EffectFiles.Length)
    SelectedStyle := 1
ThemeIndex := 1
try ThemeIndex := Integer(IniRead(SettingsFile, "General", "Theme", "1"))
if (ThemeIndex < 1 || ThemeIndex > ThemeKeys.Length)
    ThemeIndex := 1
ActiveFrames := Frames["dark"][SelectedStyle]

SaveSettings() {
    global SettingsFile, SelectedStyle, Enabled, ThemeIndex
    try {
        IniWrite(SelectedStyle, SettingsFile, "General", "Effect")
        IniWrite(ThemeIndex, SettingsFile, "General", "Theme")
        IniWrite(Enabled ? 1 : 0, SettingsFile, "General", "Enabled")
    }
}

; ----------------------------------------------- layered overlay (GDI)
try DllCall("SetThreadDpiAwarenessContext", "Ptr", -4, "Ptr")   ; per-monitor v2: physical pixels
Overlay := Gui("+AlwaysOnTop -Caption +ToolWindow +E0x80020 +E0x08000000 -DPIScale")
; E0x80000 WS_EX_LAYERED | E0x20 WS_EX_TRANSPARENT (click-through) | E0x08000000 WS_EX_NOACTIVATE

DC := DllCall("gdi32\CreateCompatibleDC", "Ptr", 0, "Ptr")
Header := Buffer(40, 0)       ; BITMAPINFOHEADER, negative height = top-down
NumPut("UInt", 40, "Int", FrameSize, "Int", -FrameSize, "UShort", 1, "UShort", 32, Header)
Bits := 0
Bitmap := DllCall("gdi32\CreateDIBSection", "Ptr", DC, "Ptr", Header, "UInt", 0, "Ptr*", &Bits, "Ptr", 0, "UInt", 0, "Ptr")
if (!DC || !Bitmap || !Bits) {
    MsgBox("Could not create the drawing surface.", AppName, "Iconx")
    ExitApp()
}
OldBitmap  := DllCall("gdi32\SelectObject", "Ptr", DC, "Ptr", Bitmap, "Ptr")
Position   := Buffer(8, 0)    ; POINT  - top-left of the overlay on screen
Dimensions := Buffer(8, 0)    ; SIZE   - overlay size
NumPut("Int", FrameSize, "Int", FrameSize, Dimensions)
Origin     := Buffer(8, 0)    ; POINT  - source origin (0,0)
Blend      := Buffer(4, 0)    ; BLENDFUNCTION: SRC_OVER, 0, 255, AC_SRC_ALPHA
NumPut("UChar", 0, "UChar", 0, "UChar", 255, "UChar", 1, Blend)
Started := 0

; -------------------------------------------------------------- tray menu
try TraySetIcon(A_ScriptDir "\dark-blur.ico")
A_IconTip := AppName
A_TrayMenu.Delete()
A_TrayMenu.Add(EnabledLabel, ToggleEffect)
A_TrayMenu.Add()
for index, name in StyleNames
    A_TrayMenu.Add(name, SelectStyle.Bind(index))
A_TrayMenu.Add()
for index, name in ThemeNames
    A_TrayMenu.Add(name, SelectTheme.Bind(index))
A_TrayMenu.Add()
A_TrayMenu.Add(StartupLabel, ToggleStartup)
A_TrayMenu.Add()
A_TrayMenu.Add(Labels["Exit"], QuitApp)
if Enabled
    A_TrayMenu.Check(EnabledLabel)
A_TrayMenu.Check(StyleNames[SelectedStyle])
A_TrayMenu.Check(ThemeNames[ThemeIndex])
if FileExist(StartupLink)
    A_TrayMenu.Check(StartupLabel)
OnExit(Cleanup)

; ----------------------------------------------------------------- hotkeys
~*LButton::StartEffect()
^!F9::ToggleEffect()
^!F10::NextStyle()
^!F11::NextTheme()

; --------------------------------------------------------------- functions
StartEffect(*) {
    global Enabled, Started, Position, Overlay, FrameMs, FrameSize, ActiveFrames, Frames, SelectedStyle
    if !Enabled
        return
    ActiveFrames := Frames[CurrentTheme()][SelectedStyle]
    point := Buffer(8, 0)
    if !DllCall("GetCursorPos", "Ptr", point)
        return
    half := FrameSize // 2
    NumPut("Int", NumGet(point, 0, "Int") - half, "Int", NumGet(point, 4, "Int") - half, Position)
    Started := A_TickCount
    PaintFrame()
    ; HWND_TOPMOST, no move/size/activate, show window (0x1 | 0x2 | 0x10 | 0x40)
    DllCall("SetWindowPos", "Ptr", Overlay.Hwnd, "Ptr", -1, "Int", 0, "Int", 0, "Int", 0, "Int", 0, "UInt", 0x0053)
    SetTimer(PaintFrame, FrameMs)
}

PaintFrame(*) {
    global Started, FrameCount, FrameBytes, ActiveFrames, Bits, Overlay, DC, Position, Dimensions, Origin, Blend, FrameMs
    frame := (A_TickCount - Started) // FrameMs
    if (frame >= FrameCount) {
        SetTimer(PaintFrame, 0)
        Overlay.Hide()
        return
    }
    DllCall("RtlMoveMemory", "Ptr", Bits, "Ptr", ActiveFrames.Ptr + frame * FrameBytes, "UPtr", FrameBytes)
    ok := DllCall("UpdateLayeredWindow", "Ptr", Overlay.Hwnd, "Ptr", 0, "Ptr", Position, "Ptr", Dimensions
        , "Ptr", DC, "Ptr", Origin, "UInt", 0, "Ptr", Blend, "UInt", 2)   ; ULW_ALPHA
    if !ok {
        SetTimer(PaintFrame, 0)
        Overlay.Hide()
    }
}

SelectStyle(index, *) {
    global SelectedStyle, StyleNames, Overlay
    SetTimer(PaintFrame, 0)
    Overlay.Hide()
    A_TrayMenu.Uncheck(StyleNames[SelectedStyle])
    SelectedStyle := index
    A_TrayMenu.Check(StyleNames[index])
    SaveSettings()
}

; "dark" / "light" for the effect to play (auto follows the Windows "apps" theme)
CurrentTheme() {
    global ThemeIndex, ThemeKeys
    key := ThemeKeys[ThemeIndex]
    if (key != "auto")
        return key
    try
        return RegRead("HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "AppsUseLightTheme") ? "light" : "dark"
    return "dark"
}

SelectTheme(index, *) {
    global ThemeIndex, ThemeNames, Overlay
    SetTimer(PaintFrame, 0)
    Overlay.Hide()
    A_TrayMenu.Uncheck(ThemeNames[ThemeIndex])
    ThemeIndex := index
    A_TrayMenu.Check(ThemeNames[index])
    SaveSettings()
}

NextTheme(*) {
    global ThemeIndex, ThemeNames
    SelectTheme(Mod(ThemeIndex, ThemeNames.Length) + 1)
}

NextStyle(*) {
    global SelectedStyle, StyleNames
    SelectStyle(Mod(SelectedStyle, StyleNames.Length) + 1)
}

ToggleEffect(*) {
    global Enabled, Overlay, EnabledLabel
    Enabled := !Enabled
    if Enabled
        A_TrayMenu.Check(EnabledLabel)
    else {
        A_TrayMenu.Uncheck(EnabledLabel)
        SetTimer(PaintFrame, 0)
        Overlay.Hide()
    }
    SaveSettings()
}

ToggleStartup(*) {
    global StartupLink, StartupLabel, AppName
    if FileExist(StartupLink) {
        try FileDelete(StartupLink)
        A_TrayMenu.Uncheck(StartupLabel)
    } else {
        try FileCreateShortcut(A_AhkPath, StartupLink, A_ScriptDir, '"' A_ScriptFullPath '"', AppName)
        if FileExist(StartupLink)
            A_TrayMenu.Check(StartupLabel)
    }
}

QuitApp(*) {
    ExitApp()
}

Cleanup(*) {
    global DC, OldBitmap, Bitmap, Overlay
    SetTimer(PaintFrame, 0)
    Overlay.Destroy()
    DllCall("gdi32\SelectObject", "Ptr", DC, "Ptr", OldBitmap)
    DllCall("gdi32\DeleteObject", "Ptr", Bitmap)
    DllCall("gdi32\DeleteDC", "Ptr", DC)
}
