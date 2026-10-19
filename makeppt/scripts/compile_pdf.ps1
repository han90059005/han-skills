<#
.SYNOPSIS
  Compile an NWPU-Beamer presentation PDF (two XeLaTeX passes) and deliver main.pdf.

.DESCRIPTION
  -BuildDir must be an assembled build directory containing at least:
    main.tex, nwpubeamer.sty, source\ (background/logo assets), figures\ (images)
  The script: sets TeX Live PATH -> two xelatex passes -> copies main.pdf to -Out.

.PARAMETER BuildDir
  Build directory containing main.tex.

.PARAMETER Out
  Full path of the output PDF.

.PARAMETER TeXLiveBin
  TeX Live bin\windows directory. Default D:\AI-tools\latex\texlive\2026\bin\windows.

.EXAMPLE
  powershell -File compile_pdf.ps1 -BuildDir "C:\Temp\makeppt-xxx" -Out "D:\report\slides.pdf"
#>
param(
    [Parameter(Mandatory = $true)][string]$BuildDir,
    [Parameter(Mandatory = $true)][string]$Out,
    [string]$TeXLiveBin = "D:\AI-tools\latex\texlive\2026\bin\windows"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path (Join-Path $TeXLiveBin "xelatex.exe"))) {
    throw "xelatex.exe not found under: $TeXLiveBin"
}
if (-not (Test-Path (Join-Path $BuildDir "main.tex"))) {
    throw "main.tex not found in build dir: $BuildDir"
}

$env:PATH = "$TeXLiveBin;$env:PATH"

Push-Location $BuildDir
try {
    Write-Host "[makeppt] XeLaTeX pass 1 ..."
    xelatex -interaction=nonstopmode -halt-on-error main.tex | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "XeLaTeX pass 1 failed. See main.log under: $BuildDir"
    }

    Write-Host "[makeppt] XeLaTeX pass 2 ..."
    xelatex -interaction=nonstopmode -halt-on-error main.tex | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "XeLaTeX pass 2 failed. See main.log under: $BuildDir"
    }

    if (-not (Test-Path (Join-Path $BuildDir "main.pdf"))) {
        throw "main.pdf was not produced."
    }

    $outDir = Split-Path -Parent $Out
    if ($outDir -and -not (Test-Path $outDir)) {
        New-Item -ItemType Directory -Path $outDir -Force | Out-Null
    }
    Copy-Item (Join-Path $BuildDir "main.pdf") -Destination $Out -Force
    Write-Host "[makeppt] PDF written: $Out"
}
finally {
    Pop-Location
}
