[CmdletBinding()]
param(
	[Parameter()]
	[string] $OutputRoot = (Join-Path $PSScriptRoot "out")
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$resolvedOutput = [System.IO.Path]::GetFullPath($OutputRoot)
$workRoot = Join-Path $resolvedOutput "work"
$distRoot = Join-Path $resolvedOutput "dist"

New-Item -ItemType Directory -Force -Path $resolvedOutput | Out-Null
python -m PyInstaller `
	--noconfirm `
	--clean `
	--workpath $workRoot `
	--distpath $distRoot `
	(Join-Path $PSScriptRoot "aphelion_sidecar.spec")
if ($LASTEXITCODE -ne 0) {
	throw "PyInstaller exited with code $LASTEXITCODE."
}

$artifact = Join-Path $distRoot "aphelion-sidecar\aphelion-sidecar.exe"
if (-not (Test-Path -LiteralPath $artifact -PathType Leaf)) {
	throw "PyInstaller did not produce $artifact."
}

Write-Output $artifact
