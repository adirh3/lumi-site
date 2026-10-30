param([Parameter(Mandatory)] [string] $In, [Parameter(Mandatory)] [string] $Out)
# Reads the text in every PNG in -In with the Windows OCR engine and writes one .txt per image to -Out.
# Used by scan_public.py --ocr. Needs Windows PowerShell 5.1 (powershell.exe), which can load WinRT types.
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime]
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, [Type] $type) { $t = $asTask.MakeGenericMethod($type).Invoke($null, @($op)); $t.Wait(-1) | Out-Null; $t.Result }
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
New-Item -ItemType Directory -Force $Out | Out-Null
$n = 0
foreach ($f in Get-ChildItem $In -Filter *.png) {
    $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($f.FullName)) ([Windows.Storage.StorageFile])
    $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    ($result.Lines | ForEach-Object { $_.Text }) -join "`n" | Set-Content -Path (Join-Path $Out ($f.BaseName + '.txt')) -Encoding UTF8
    $stream.Dispose(); $n++
}
"OCR: $n image(s), engine $($engine.RecognizerLanguage.DisplayName)"
