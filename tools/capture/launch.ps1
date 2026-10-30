param(
    # Lumi.exe from a Debug build of adirh3/Lumi (a worktree, never the main checkout's Release build).
    [Parameter(Mandatory)] [string] $Exe,
    # The isolated profile folder written by seed_profile.py.
    [Parameter(Mandatory)] [string] $Profile,
    [int] $Width = 1980,
    [int] $Height = 1290
)
# Launches Lumi with an isolated profile (LUMI_APPDATA_DIR, so no real data is touched), restores it without
# activating it and sizes its client area to Width x Height at the bottom of the window stack on the rightmost
# monitor (it must be a 100% / 96 DPI monitor). Prints the PID and HWND that the other tools take.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type @'
using System; using System.Runtime.InteropServices;
public static class LumiStage {
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr a, int x, int y, int cx, int cy, uint f);
  [DllImport("user32.dll")] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr c);
}
'@
[void][LumiStage]::SetThreadDpiAwarenessContext([IntPtr](-4))
$screen = [System.Windows.Forms.Screen]::AllScreens | Sort-Object { $_.Bounds.Right } -Descending | Select-Object -First 1
$x = $screen.Bounds.Left + 60; $y = $screen.Bounds.Top

$env:LUMI_APPDATA_DIR = (Resolve-Path $Profile).Path
$p = Start-Process -FilePath $Exe -ArgumentList '--skip-onboarding' -PassThru
$deadline = (Get-Date).AddSeconds(40)
do { Start-Sleep -Milliseconds 400; $p.Refresh() } while ($p.MainWindowHandle -eq 0 -and (Get-Date) -lt $deadline)
$h = $p.MainWindowHandle
if ($h -eq 0) { throw "Lumi (PID $($p.Id)) didn't open a window." }
Start-Sleep 3
[void][LumiStage]::ShowWindow($h, 4)   # restore without activating
# The outer size adds the window frame, so the client area is exactly Width x Height.
foreach ($i in 1..2) { [void][LumiStage]::SetWindowPos($h, [IntPtr]1, $x, $y, $Width + 16, $Height + 8, 0x0010); Start-Sleep 1 }
"PID=$($p.Id) HWND=$h"
