param(
    # A loop's frames from make_loop.py (30 fps JPEGs named 00001.jpg, 00002.jpg, ...).
    [Parameter(Mandatory)] [string] $Frames,
    [Parameter(Mandatory)] [ValidateSet('dark', 'light')] [string] $Theme,
    [string] $Out = (Join-Path $PSScriptRoot '..\..\site\assets\video')
)
# Encodes a hero loop into the four files the page plays: hero-<theme>-1980/1320 .webm (AV1) and .mp4 (H.264),
# BT.709 limited range. main.js advertises av01.0.12M.08 (1980), av01.0.08M.08 (1320) and avc1.640032; if you
# change the settings, check the levels with ffprobe. Needs an ffmpeg build with libsvtav1 and libx264.
$ErrorActionPreference = 'Stop'
$src = Join-Path $Frames '%05d.jpg'
$tags = '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-color_range', 'tv'
foreach ($w in 1980, 1320) {
    $vf = "scale=${w}:-2:flags=lanczos:in_color_matrix=bt601:out_color_matrix=bt709:in_range=pc:out_range=tv,format=yuv420p"
    ffmpeg -v error -y -framerate 30 -i $src -vf $vf @tags -c:v libsvtav1 -preset 5 -crf 38 -g 300 -svtav1-params log-level=0 -an (Join-Path $Out "hero-$Theme-$w.webm")
    ffmpeg -v error -y -framerate 30 -i $src -vf $vf @tags -c:v libx264 -preset slower -crf 27 -profile:v high -movflags +faststart -an (Join-Path $Out "hero-$Theme-$w.mp4")
}
Get-ChildItem $Out -Filter "hero-$Theme-*" | ForEach-Object {
    $s = (ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,level,width,height -show_entries format=duration -of json $_.FullName | ConvertFrom-Json)
    "{0}: {1} level {2}, {3}x{4}, {5:N1} s, {6:N0} KB" -f $_.Name, $s.streams[0].codec_name, $s.streams[0].level, $s.streams[0].width, $s.streams[0].height, [double]$s.format.duration, ($_.Length / 1KB)
}
