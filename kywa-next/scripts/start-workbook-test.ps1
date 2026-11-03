param([int]$Port = 8001)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$taskPython = Join-Path $projectRoot '.venv/Scripts/python.exe'
$testData = Join-Path $projectRoot 'local-data/workbook-test/data.json'
if (-not (Test-Path -LiteralPath $testData)) { throw '먼저 backend.local_workspace로 엑셀 사본을 준비하세요.' }
$env:APP_ENV = 'demo'
$env:LOCAL_WORKSPACE = 'true'
$env:APP_BASE_URL = "http://localhost:$Port"
$env:DEMO_DATA_PATH = $testData
Push-Location $projectRoot
try { & $taskPython scripts/start_workbook_test.py --port $Port }
finally { Pop-Location }
