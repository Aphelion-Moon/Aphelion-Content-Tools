[CmdletBinding()]
param(
	[Parameter(Mandatory = $false)]
	[string]$ManifestPath = (Join-Path $PSScriptRoot "python-suites.json"),

	[Parameter(Mandatory = $false)]
	[string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")),

	[Parameter(Mandatory = $false)]
	[string]$OutputRoot = (Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..\..")) "tools\logs\test-suites"),

	[Parameter(Mandatory = $false)]
	[string[]]$Suite
)

$ErrorActionPreference = "Stop"
$repositoryPath = [IO.Path]::GetFullPath($RepositoryRoot)
$manifestFile = [IO.Path]::GetFullPath($ManifestPath)
$outputPath = [IO.Path]::GetFullPath($OutputRoot)
$toolRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$pythonCommand = (Get-Command python -ErrorAction Stop).Source
New-Item -ItemType Directory -Force -Path $outputPath | Out-Null

$previousPythonPath = $env:PYTHONPATH
if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
	$env:PYTHONPATH = $toolRoot
}
else {
	$env:PYTHONPATH = "$toolRoot$([IO.Path]::PathSeparator)$previousPythonPath"
}

try {
	$manifestJson = & $pythonCommand -m tools.testing.suites --manifest $manifestFile --repository-root $repositoryPath
	if ($LASTEXITCODE -ne 0) {
		throw "Python suite manifest validation failed with exit code $LASTEXITCODE."
	}
	$manifest = $manifestJson | ConvertFrom-Json
	$availableIds = @($manifest.suites | ForEach-Object { [string]$_.id })
	if ($Suite) {
		$unknown = @($Suite | Where-Object { $_ -notin $availableIds })
		if ($unknown.Count -gt 0) {
			throw "Unknown Python suite(s): $($unknown -join ', '). Available: $($availableIds -join ', ')."
		}
		$selected = @($manifest.suites | Where-Object { $_.id -in $Suite })
	}
	else {
		$selected = @($manifest.suites)
	}

	$startedAt = [DateTimeOffset]::UtcNow
	$runId = [Guid]::NewGuid().ToString("N")
	$results = @()
	foreach ($entry in $selected) {
		$logPath = Join-Path $outputPath "$($entry.id).log"
		$modules = @($entry.modules | ForEach-Object { [string]$_ })
		$testArguments = @('-W', 'always::ResourceWarning', '-m', 'unittest') + $modules + @('-v')
		if ($entry.runner -eq 'pytest') {
			$testFiles = @($modules | ForEach-Object { $_.Replace('.', '/') + '.py' })
			$testArguments = @('-W', 'always::ResourceWarning', '-m', 'pytest', '-q', '-p', 'no:cacheprovider') + $testFiles
			$pytestBaseTemp = Join-Path $outputPath ".pytest-$($entry.id)-$runId"
			$testArguments += @('--basetemp', $pytestBaseTemp)
		}
		Write-Host "[$($entry.id)] $($entry.description)"
		$resultJson = & $pythonCommand -m tools.testing.suite_process `
			--name ([string]$entry.id) `
			--working-directory $repositoryPath `
			--log-path $logPath `
			--timeout-seconds ([string]$entry.timeout_seconds) `
			--max-log-bytes ([string]$entry.max_log_bytes) `
			-- $pythonCommand @testArguments
		if ($LASTEXITCODE -ne 0) {
			throw "Suite process wrapper failed for $($entry.id) with exit code $LASTEXITCODE."
		}
		$result = $resultJson | ConvertFrom-Json
		$results += $result
		Write-Host "[$($entry.id)] $($result.status) in $([Math]::Round([double]$result.duration_seconds, 2))s; log: $logPath"
	}

	$summary = [ordered]@{
		schema_version = 1
		started_at = $startedAt.ToString("o")
		completed_at = [DateTimeOffset]::UtcNow.ToString("o")
		manifest = $manifestFile
		repository = $repositoryPath
		results = $results
	}
	$summaryPath = Join-Path $outputPath "summary.json"
	$summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryPath -Encoding utf8
	Write-Host "Summary: $summaryPath"
	if (@($results | Where-Object { $_.status -ne "passed" }).Count -gt 0) {
		exit 1
	}
	exit 0
}
finally {
	$env:PYTHONPATH = $previousPythonPath
}
