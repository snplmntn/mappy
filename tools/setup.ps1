# One-time setup for the demo laptop. Run on home internet: the demo network has none.
#   powershell -ExecutionPolicy Bypass -File tools\setup.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

function Step($msg) { Write-Host "`n== $msg" -ForegroundColor Yellow }

$E5 = @{
    "model.onnx"     = @{ url = "https://huggingface.co/intfloat/multilingual-e5-small/resolve/main/onnx/model.onnx";
                          sha = "ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665" }
    "tokenizer.json" = @{ url = "https://huggingface.co/intfloat/multilingual-e5-small/resolve/main/onnx/tokenizer.json";
                          sha = "0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39" }
}

Step "Python 3.12"
$py = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
if (-not (Test-Path $py)) {
    winget install --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
}
if (-not (Test-Path ".venv")) { & $py -m venv .venv }
$vpy = Join-Path $root ".venv\Scripts\python.exe"
& $vpy -m pip install -q --upgrade pip
& $vpy -m pip install -q -e ".[dev]"

Step "Checking native libraries load (Windows Smart App Control can block some)"
& $vpy -c "import pydantic_core, numpy, onnxruntime, tokenizers, rapidfuzz, ml_dtypes, cryptography.hazmat.primitives.asymmetric.ec; print('all native libraries load')"
if ($LASTEXITCODE -ne 0) { throw "A library is blocked. Note which one and try an older version, e.g. pip install 'pydantic==2.10.6'." }

Step "Ollama + Qwen3-1.7B"
$ollama = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
if (-not (Test-Path $ollama)) {
    winget install --id Ollama.Ollama --scope user --silent --accept-package-agreements --accept-source-agreements
}
& $ollama pull qwen3:1.7b

Step "Embedding model (multilingual-e5-small)"
$e5dir = Join-Path $root "models\e5"
New-Item -ItemType Directory -Force $e5dir | Out-Null
foreach ($name in $E5.Keys) {
    $dest = Join-Path $e5dir $name
    if (-not (Test-Path $dest)) { Invoke-WebRequest -UseBasicParsing -Uri $E5[$name].url -OutFile $dest }
    $hash = (Get-FileHash $dest -Algorithm SHA256).Hash.ToLower()
    if ($hash -ne $E5[$name].sha) { throw "$name checksum mismatch: $hash" }
    Write-Host "  $name ok"
}
if (-not (Test-Path (Join-Path $e5dir "model_int8.onnx"))) {
    & $vpy -c "from onnxruntime.quantization import quantize_dynamic, QuantType; quantize_dynamic(r'$e5dir\model.onnx', r'$e5dir\model_int8.onnx', weight_type=QuantType.QInt8)"
}

Step "Settings"
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Write-Host "  created .env (set MAPPY_WIFI_PASS to the hotspot password)" }

Step "Tests"
& $vpy -m pytest -q

Step "Done"
Write-Host "Allow phones to reach this laptop (run once in an ADMIN PowerShell):"
Write-Host '  New-NetFirewallRule -DisplayName "Mappy" -Direction Inbound -Protocol TCP -LocalPort 8000,8443 -Action Allow -Profile Any'
Write-Host "Then start Mappy with:  powershell -ExecutionPolicy Bypass -File tools\run.ps1"
