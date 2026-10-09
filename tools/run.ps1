# Start Mappy: make sure Ollama is serving, preload the model, then run the web server.
param([int]$Threads = 4)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$ollama = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"

function Test-Ollama {
    try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:11434/api/version -TimeoutSec 2 | Out-Null; return $true }
    catch { return $false }
}

if (-not (Test-Ollama)) {
    $env:OLLAMA_NUM_PARALLEL = "1"
    $env:OLLAMA_MAX_LOADED_MODELS = "1"
    Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden
    for ($i = 0; $i -lt 20 -and -not (Test-Ollama); $i++) { Start-Sleep -Milliseconds 500 }
}

Write-Host "Loading qwen3:1.7b into memory..."
$body = @{ model = "qwen3:1.7b"; keep_alive = -1; options = @{ num_thread = $Threads } } | ConvertTo-Json
Invoke-WebRequest -UseBasicParsing -Method Post -Uri http://127.0.0.1:11434/api/generate -Body $body -ContentType "application/json" | Out-Null

$env:MAPPY_LLM_THREADS = "$Threads"
& (Join-Path $root ".venv\Scripts\python.exe") -m mappy
