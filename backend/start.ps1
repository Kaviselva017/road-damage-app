$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

$port = if ($env:PORT) { $env:PORT } else { "8000" }

$pythonCandidates = @(
    (Join-Path $scriptDir "..\\.venv_clean\\Scripts\\python.exe"),
    (Join-Path $scriptDir "..\\.venv\\Scripts\\python.exe"),
    "python"
)

$pythonExe = $null
foreach ($candidate in $pythonCandidates) {
    if ($candidate -eq "python") {
        $pythonExe = $candidate
        break
    }
    if (Test-Path -LiteralPath $candidate) {
        $pythonExe = $candidate
        break
    }
}

if (-not $pythonExe) {
    throw "No Python interpreter found. Create a virtual environment first."
}

& $pythonExe -m alembic -c (Join-Path $scriptDir "alembic.ini") upgrade head
& $pythonExe -m uvicorn app.main:app --host 0.0.0.0 --port $port
