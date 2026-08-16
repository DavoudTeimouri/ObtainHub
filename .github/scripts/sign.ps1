# sign.ps1 - Code-sign ObtainHub release binaries.
# Supports two backends (configure ONE in repo secrets):
#   A) Azure Trusted Signing  -> AzureSignTool (dotnet global tool)
#   B) PFX certificate        -> signtool.exe
# If no signing secrets are present, prints a warning and exits 0 (unsigned build).
# Any unexpected error is caught and turned into a warning so the CI build does
# not fail on the signing step.

$ErrorActionPreference = "Stop"

try {
    Write-Host "=== Code Signing ==="

    $signableFiles = @("dist\ohub.exe", "dist\ObtainHub-Setup.exe", "dist\ObtainHub.msi")
    $present = @($signableFiles | Where-Object { Test-Path $_ })
    if (-not $present) {
        Write-Host "No binaries found to sign - skipping."
        exit 0
    }
    foreach ($f in $present) { Write-Host "  Will sign: $f" }

    $signed = $false

    # --- Option A: Azure Trusted Signing ---
    $hasAzure = $env:AZURE_TENANT_ID -and $env:AZURE_CLIENT_ID -and $env:AZURE_CLIENT_SECRET -and $env:AZURE_ACCOUNT_ENDPOINT -and $env:AZURE_CODE_SIGNING_PROFILE
    if ($hasAzure) {
        Write-Host "Using Azure Trusted Signing..."
        $azt = Get-Command AzureSignTool -ErrorAction SilentlyContinue
        if (-not $azt) {
            Write-Host "AzureSignTool not on PATH - installing via dotnet tool..."
            dotnet tool install --global AzureSignTool 2>&1
            $azt = Get-Command AzureSignTool -ErrorAction SilentlyContinue
        }
        if (-not $azt) {
            Write-Host "AzureSignTool unavailable - cannot sign with Azure Trusted Signing (will try PFX)."
        } else {
            $aztPath = $azt.Source
            foreach ($f in $present) {
                Write-Host "Signing $f with Azure Trusted Signing..."
                & $aztPath sign --file $f --endpoint "$env:AZURE_ACCOUNT_ENDPOINT" --code-signing-profile-name "$env:AZURE_CODE_SIGNING_PROFILE" --azure-tenant-id "$env:AZURE_TENANT_ID" --azure-client-id "$env:AZURE_CLIENT_ID" --azure-client-secret "$env:AZURE_CLIENT_SECRET" --timestamp http://timestamp.digicert.com --timestamp-rfc3161 http://timestamp.digicert.com 2>&1
                if ($LASTEXITCODE -ne 0) { Write-Host "AzureSignTool failed (exit $LASTEXITCODE) on $f"; exit $LASTEXITCODE }
            }
            $signed = $true
        }
    }

    # --- Option B: PFX certificate from secrets ---
    if (-not $signed -and $env:SIGNING_PFX_B64 -and $env:SIGNING_PFX_PASSWORD) {
        Write-Host "Using PFX certificate from secrets..."
        $pfxPath = "$env:TEMP\ohub_codesign.pfx"
        [IO.File]::WriteAllBytes($pfxPath, [Convert]::FromBase64String($env:SIGNING_PFX_B64))
        $signTool = (Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin" -Recurse -Filter "signtool.exe" -ErrorAction SilentlyContinue | Sort-Object FullName | Select-Object -Last 1).FullName
        if (-not $signTool) { $signTool = (Get-Command signtool.exe -ErrorAction SilentlyContinue).Source }
        if (-not $signTool) { Write-Host "signtool.exe not found - cannot sign."; exit 1 }
        Write-Host "signtool: $signTool"
        foreach ($f in $present) {
            Write-Host "Signing $f with PFX..."
            & $signTool sign /f $pfxPath /p "$env:SIGNING_PFX_PASSWORD" /tr http://timestamp.digicert.com /td sha256 /fd sha256 "$f" 2>&1
            if ($LASTEXITCODE -ne 0) { Write-Host "signtool failed (exit $LASTEXITCODE) on $f"; exit $LASTEXITCODE }
        }
        Remove-Item $pfxPath -Force -ErrorAction SilentlyContinue
        $signed = $true
    }

    if (-not $signed) {
        Write-Host "::warning::No signing secrets configured (SIGNING_PFX_B64/PASSWORD or Azure Trusted Signing). Binaries are NOT code-signed - Windows SmartScreen will flag them as unrecognized."
    } else {
        Write-Host "=== Signature verification ==="
        $stv = Get-Command signtool.exe -ErrorAction SilentlyContinue
        if ($stv) { foreach ($f in $present) { & $stv.Source verify /pa "$f" 2>&1; Write-Host "  $f verify exit: $LASTEXITCODE" } }
    }

    exit 0
}
catch {
    Write-Host "::warning::Code signing step encountered an error and was skipped: $_"
    exit 0
}
