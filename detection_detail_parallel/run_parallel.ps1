param(
  [Parameter(Mandatory = $true)]
  [string]$Pdf,
  [string]$Out = ".\outputs_parallel",
  [int]$MaxPages = 0,
  [int]$Dpi = 180,
  [double]$Padding = 3.0,
  [ValidateSet("cuda", "auto", "cpu")]
  [string]$Device = "cuda",
  [int]$NumThreads = 4,
  [int]$PatchWorkers = 0,
  [int]$GapWorkers = 0,
  [int]$OcrThreadsPerWorker = 0,
  [switch]$NoDrawBboxes
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$argsList = @(
  "$scriptDir\scan_pdf_parallel.py",
  "--pdf", $Pdf,
  "--out", $Out,
  "--dpi", "$Dpi",
  "--padding", "$Padding",
  "--device", $Device,
  "--num-threads", "$NumThreads",
  "--patch-workers", "$PatchWorkers",
  "--gap-workers", "$GapWorkers"
)

if ($MaxPages -gt 0) {
  $argsList += @("--max-pages", "$MaxPages")
}
if ($OcrThreadsPerWorker -gt 0) {
  $argsList += @("--ocr-threads-per-worker", "$OcrThreadsPerWorker")
}
if ($NoDrawBboxes) {
  $argsList += "--no-draw-bboxes"
}

python @argsList

