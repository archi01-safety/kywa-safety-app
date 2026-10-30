$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$workspaceRoot = Split-Path $projectRoot -Parent
$taskPython = Join-Path $projectRoot '.venv/Scripts/python.exe'
$taskNodeRoot = Join-Path $workspaceRoot '.tools/node-runtime/node-v22.23.3-win-x64'
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'README의 Python 환경 설치를 먼저 진행하세요.' }
Push-Location $projectRoot
try {
    if (-not (Test-Path -LiteralPath 'frontend/out/index.html')) {
        $env:PATH = "$taskNodeRoot;$env:PATH"
        Push-Location frontend
        try { & (Join-Path $taskNodeRoot 'node.exe') (Join-Path $taskNodeRoot 'node_modules/npm/bin/npm-cli.js') run build }
        finally { Pop-Location }
        if ($LASTEXITCODE -ne 0) { throw '프런트엔드 빌드 실패' }
    }
    & $taskPython -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
} finally { Pop-Location }
