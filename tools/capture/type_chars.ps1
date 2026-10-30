param(
    [Parameter(Mandatory)] [long] $Hwnd,
    [Parameter(Mandatory)] [string] $Text,
    [int] $MinDelayMs = 28,
    [int] $MaxDelayMs = 70,
    [switch] $Clear
)
# Types into the focused control of a specific window by posting WM_CHAR messages to it, so the text
# goes through the app's normal text input (caret and all) without activating the window or touching
# the user's foreground input.
$ErrorActionPreference = 'Stop'
Add-Type @'
using System; using System.Runtime.InteropServices;
public static class CharPost {
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
}
'@
if ($Clear) {
    Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
    $root = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]$Hwnd)
    $condition = New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::AutomationIdProperty, 'PART_Input')
    $input = $root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $condition)
    $input.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).SetValue('')
    Start-Sleep -Milliseconds 150
}
$random = New-Object System.Random 11
$watch = [System.Diagnostics.Stopwatch]::StartNew()
foreach ($ch in $Text.ToCharArray()) {
    [void][CharPost]::PostMessage([IntPtr]$Hwnd, 0x0102, [IntPtr][int]$ch, [IntPtr]1)
    $delay = $random.Next($MinDelayMs, $MaxDelayMs)
    if ($ch -in @(' ', ',', '.')) { $delay += 35 }
    Start-Sleep -Milliseconds $delay
}
"posted $($Text.Length) chars in $([math]::Round($watch.Elapsed.TotalSeconds, 1))s"
