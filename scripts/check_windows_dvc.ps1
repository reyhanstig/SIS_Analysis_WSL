# Check for DVC installation on Windows

Write-Host "--- DVC Diagnostic Tool ---" -ForegroundColor Cyan

# 1. Check if DVC is in PATH
Write-Host "1. Checking PATH for 'dvc'..."
if (Get-Command "dvc" -ErrorAction SilentlyContinue) {
    Write-Host "Success: DVC found in PATH." -ForegroundColor Green
    dvc --version
    exit
} else {
    Write-Host "Failure: 'dvc' command not found." -ForegroundColor Red
}

# 2. Check Pip Installation
Write-Host "`n2. Checking Python/Pip installation..."
try {
    $pipOutput = pip show dvc 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Success: DVC package is installed via pip." -ForegroundColor Green
        $locationLine = $pipOutput | Select-String "Location:"
        Write-Host "Package Location: $locationLine"
        
        # 3. Check if we can run it as a module
        Write-Host "`n3. Attempting to run as python module..."
        python -m dvc --version
        if ($LASTEXITCODE -eq 0) {
             Write-Host "`n[DIAGNOSIS]: DVC is installed but not in your PATH." -ForegroundColor Yellow
             Write-Host "To fix this, add the Python Scripts directory to your system PATH."
             Write-Host "Or just use: python -m dvc <command>" -ForegroundColor Cyan
        }
    } else {
        Write-Host "Failure: DVC is NOT installed via pip." -ForegroundColor Red
        Write-Host "Please install it using: pip install dvc"
    }
} catch {
    Write-Host "Error checking pip: $_"
}

Write-Host "`n--- End of Report ---"
