param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$PdfDir,

    [Parameter(Mandatory = $false, Position = 1)]
    [string]$OutputDir = "",

    [Parameter(Mandatory = $false, Position = 2)]
    [int]$MaxPages = 0
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $ScriptDir "out"
}

$VenvPython = Join-Path $ProjectRoot "venv\Scripts\python.exe"
if (Test-Path -LiteralPath $VenvPython) {
    $PythonBin = $VenvPython
}
else {
    $PythonBin = "python"
}

if (-not $env:CUDA_VISIBLE_DEVICES) {
    $env:CUDA_VISIBLE_DEVICES = "0"
}

$ArgsList = @(
    (Join-Path $ScriptDir "batch_scan.py"),
    "--input-dir", $PdfDir,
    "--out", $OutputDir,
    "--device", "cuda",
    "--dpi", "180",
    "--recursive",
    "--draw-bboxes"
)

if ($MaxPages -gt 0) {
    $ArgsList += @("--max-pages", "$MaxPages")
}

& $PythonBin @ArgsList
exit $LASTEXITCODE
