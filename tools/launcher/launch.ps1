[CmdletBinding()]
param(
	[Parameter(Mandatory = $true)]
	[string] $RepositoryRoot
)

$ErrorActionPreference = "Stop"
$resolvedRepositoryRoot = (Resolve-Path -LiteralPath $RepositoryRoot).Path
$localRoot = Join-Path $env:LOCALAPPDATA "AphelionContentTools"
$runtimeRoot = Join-Path $localRoot "runtime"
$settingsPath = Join-Path $localRoot "settings.json"
$requirementsPath = Join-Path $resolvedRepositoryRoot "tools\lore_editor\requirements.txt"
$runtimeManifestPath = Join-Path $resolvedRepositoryRoot "tools\launcher\runtime_manifest.json"
$runtimeManifest = Get-Content -LiteralPath $runtimeManifestPath -Raw | ConvertFrom-Json

if (-not ("AphelionContentToolsJob" -as [type])) {
	Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;

public static class AphelionContentToolsJob
{
	private const int JobObjectExtendedLimitInformation = 9;
	private const uint JobObjectLimitKillOnJobClose = 0x2000;

	[StructLayout(LayoutKind.Sequential)]
	private struct IoCounters
	{
		public ulong ReadOperationCount;
		public ulong WriteOperationCount;
		public ulong OtherOperationCount;
		public ulong ReadTransferCount;
		public ulong WriteTransferCount;
		public ulong OtherTransferCount;
	}

	[StructLayout(LayoutKind.Sequential)]
	private struct BasicLimitInformation
	{
		public long PerProcessUserTimeLimit;
		public long PerJobUserTimeLimit;
		public uint LimitFlags;
		public UIntPtr MinimumWorkingSetSize;
		public UIntPtr MaximumWorkingSetSize;
		public uint ActiveProcessLimit;
		public UIntPtr Affinity;
		public uint PriorityClass;
		public uint SchedulingClass;
	}

	[StructLayout(LayoutKind.Sequential)]
	private struct ExtendedLimitInformation
	{
		public BasicLimitInformation BasicLimitInformation;
		public IoCounters IoInfo;
		public UIntPtr ProcessMemoryLimit;
		public UIntPtr JobMemoryLimit;
		public UIntPtr PeakProcessMemoryUsed;
		public UIntPtr PeakJobMemoryUsed;
	}

	[DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
	private static extern IntPtr CreateJobObject(IntPtr attributes, string name);

	[DllImport("kernel32.dll", SetLastError = true)]
	[return: MarshalAs(UnmanagedType.Bool)]
	private static extern bool SetInformationJobObject(IntPtr job, int infoClass, IntPtr info, uint length);

	[DllImport("kernel32.dll", SetLastError = true)]
	[return: MarshalAs(UnmanagedType.Bool)]
	private static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);

	[DllImport("kernel32.dll", SetLastError = true)]
	[return: MarshalAs(UnmanagedType.Bool)]
	private static extern bool CloseHandle(IntPtr handle);

	public static IntPtr CreateKillOnCloseJob()
	{
		IntPtr job = CreateJobObject(IntPtr.Zero, null);
		if (job == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error());
		var limits = new ExtendedLimitInformation();
		limits.BasicLimitInformation.LimitFlags = JobObjectLimitKillOnJobClose;
		IntPtr buffer = Marshal.AllocHGlobal(Marshal.SizeOf(typeof(ExtendedLimitInformation)));
		try
		{
			Marshal.StructureToPtr(limits, buffer, false);
			if (!SetInformationJobObject(job, JobObjectExtendedLimitInformation, buffer, (uint)Marshal.SizeOf(typeof(ExtendedLimitInformation))))
			{
				throw new Win32Exception(Marshal.GetLastWin32Error());
			}
			return job;
		}
		catch
		{
			CloseHandle(job);
			throw;
		}
		finally
		{
			Marshal.FreeHGlobal(buffer);
		}
	}

	public static void Assign(IntPtr job, IntPtr process)
	{
		if (!AssignProcessToJobObject(job, process)) throw new Win32Exception(Marshal.GetLastWin32Error());
	}

	public static void Close(IntPtr job)
	{
		if (job != IntPtr.Zero) CloseHandle(job);
	}
}
'@
}

function Test-PythonRuntime {
	param([string] $PythonPath)
	if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
		return $false
	}
	try {
		$versionCheck = & $PythonPath -c "import sys; print('ok' if sys.version_info >= (3, 11) else 'old')" 2>$null
		if (($versionCheck | Select-Object -Last 1) -ne "ok") {
			return $false
		}
		& $PythonPath -c "import PIL, lancedb, fastembed, numpy, fastapi, uvicorn, pydantic" 2>$null
		return $LASTEXITCODE -eq 0
	}
	catch {
		return $false
	}
}

function Find-CompatiblePython {
	$candidates = @()
	$pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
	if ($pythonCommand) { $candidates += $pythonCommand.Source }
	$pyCommand = Get-Command py.exe -ErrorAction SilentlyContinue
	if ($pyCommand) {
		try {
			$pyPath = & $pyCommand.Source -3 -c "import sys; print(sys.executable)" 2>$null
			if ($pyPath) { $candidates += ($pyPath | Select-Object -Last 1).Trim() }
		}
		catch { }
	}
	$candidates += (Join-Path $runtimeRoot "python\python.exe")
	foreach ($candidate in ($candidates | Select-Object -Unique)) {
		if (Test-PythonRuntime $candidate) { return $candidate }
	}
	return $null
}

function Show-RequirementsGuidance {
	Write-Host ""
	Write-Host "Aphelion Content Tools needs 64-bit Python 3.11 or newer with its pinned dependencies installed." -ForegroundColor Yellow
	Write-Host "Install Python from https://www.python.org/downloads/windows/ and then run:" -ForegroundColor Yellow
	Write-Host "  python -m pip install -r tools\lore_editor\requirements.txt" -ForegroundColor Yellow
	Write-Host "Then double-click Launch Aphelion Content Tools.cmd again." -ForegroundColor Yellow
}

function Install-PrivatePython {
	New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
	$installerFileName = "python-$($runtimeManifest.version)-$($runtimeManifest.architecture).exe"
	$installerPath = Join-Path $runtimeRoot $installerFileName
	$temporaryInstallerPath = "$installerPath.download"
	$installerUrl = [string]$runtimeManifest.installer_url
	Write-Host "Downloading the official Python $($runtimeManifest.version) installer..."
	Remove-Item -LiteralPath $temporaryInstallerPath -Force -ErrorAction SilentlyContinue
	Invoke-WebRequest -Uri $installerUrl -OutFile $temporaryInstallerPath
	$signature = Get-AuthenticodeSignature -LiteralPath $temporaryInstallerPath
	if ($signature.Status -ne "Valid" -or $signature.SignerCertificate.Subject -notlike "*$($runtimeManifest.signature_subject_contains)*") {
		Remove-Item -LiteralPath $temporaryInstallerPath -Force -ErrorAction SilentlyContinue
		throw "The downloaded Python installer did not have the expected valid Python Software Foundation signature."
	}
	Move-Item -LiteralPath $temporaryInstallerPath -Destination $installerPath -Force
	$installPath = Join-Path $runtimeRoot "python"
	$arguments = @(
		"/quiet",
		"InstallAllUsers=0",
		"PrependPath=0",
		"Include_launcher=0",
		"Include_test=0",
		("TargetDir=" + $installPath)
	)
	$installer = Start-Process -FilePath $installerPath -ArgumentList $arguments -Wait -PassThru
	if ($installer.ExitCode -ne 0) { throw "Python installation failed with exit code $($installer.ExitCode)." }
	$pythonPath = Join-Path $installPath "python.exe"
	if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) { throw "Python installation completed without creating python.exe." }
	& $pythonPath -m pip install --disable-pip-version-check --no-input -r $requirementsPath
	if ($LASTEXITCODE -ne 0) { throw "Installing the Aphelion Content Tools Python dependency failed." }
	return $pythonPath
}

function Read-GameRepository {
	if (Test-Path -LiteralPath $settingsPath -PathType Leaf) {
		try {
			$settings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
			if ($settings.gameRepository -and (Test-Path -LiteralPath $settings.gameRepository -PathType Container)) {
				return (Resolve-Path -LiteralPath $settings.gameRepository).Path
			}
		}
		catch { }
	}
	$defaultGameRoot = Join-Path (Split-Path -Parent $resolvedRepositoryRoot) "Meridian-Rift"
	if (Test-Path -LiteralPath $defaultGameRoot -PathType Container) {
		$answer = Read-Host "Use the nearby Meridian-Rift checkout at '$defaultGameRoot'? (Y/n)"
		if ([string]::IsNullOrWhiteSpace($answer) -or $answer -match '^(y|yes)$') { return (Resolve-Path -LiteralPath $defaultGameRoot).Path }
	}
	$gameRoot = Read-Host "Enter the full path to your local Meridian-Rift checkout (blank to continue without it)"
	if ([string]::IsNullOrWhiteSpace($gameRoot)) { return $null }
	if (-not (Test-Path -LiteralPath $gameRoot -PathType Container)) { throw "The selected game checkout does not exist: $gameRoot" }
	$resolvedGameRoot = (Resolve-Path -LiteralPath $gameRoot).Path
	return $resolvedGameRoot
}

function ConvertTo-EscapedArgument {
	param([string] $Argument)
	if ($Argument.Length -gt 0 -and $Argument -notmatch '[\s"]') {
		return $Argument
	}
	$escaped = New-Object System.Text.StringBuilder
	[void]$escaped.Append('"')
	$backslashCount = 0
	foreach ($character in $Argument.ToCharArray()) {
		if ($character -eq '\') {
			$backslashCount++
			continue
		}
		if ($character -eq '"') {
			[void]$escaped.Append('\' * (($backslashCount * 2) + 1))
			[void]$escaped.Append('"')
			$backslashCount = 0
			continue
		}
		if ($backslashCount -gt 0) {
			[void]$escaped.Append('\' * $backslashCount)
			$backslashCount = 0
		}
		[void]$escaped.Append($character)
	}
	if ($backslashCount -gt 0) {
		[void]$escaped.Append('\' * ($backslashCount * 2))
	}
	[void]$escaped.Append('"')
	return $escaped.ToString()
}

$python = Find-CompatiblePython
if (-not $python) {
	Write-Host "No compatible Python runtime was found." -ForegroundColor Yellow
	$downloadAnswer = Read-Host "Download and install a private Python runtime for this tool? (y/N)"
	if ($downloadAnswer -notmatch '^(y|yes)$') {
		Show-RequirementsGuidance
		exit 1
	}
	try { $python = Install-PrivatePython }
	catch {
		Write-Host $_.Exception.Message -ForegroundColor Red
		Show-RequirementsGuidance
		exit 1
	}
}

$gameRoot = Read-GameRepository
if ($gameRoot) {
	New-Item -ItemType Directory -Force -Path $localRoot | Out-Null
	@{ gameRepository = $gameRoot } | ConvertTo-Json | Set-Content -LiteralPath $settingsPath -Encoding UTF8
}
$catalogArguments = @(
	(Join-Path $resolvedRepositoryRoot "tools\lore_editor\cli.py"),
	"catalog-bootstrap", "--repo-root", $resolvedRepositoryRoot
)
if ($gameRoot) { $catalogArguments += @("--game-repo", $gameRoot) }
& $python @catalogArguments
if ($LASTEXITCODE -ne 0) {
	Write-Host "Catalog bootstrap did not complete. Existing authored records remain available." -ForegroundColor Yellow
}
$frontendIndexPath = Join-Path $resolvedRepositoryRoot "webapp\frontend\dist\index.html"
if (-not (Test-Path -LiteralPath $frontendIndexPath -PathType Leaf)) {
	throw "The built browser app is missing. Restore the release files or run 'npm --prefix webapp/frontend run build'."
}
$arguments = @(
	(Join-Path $resolvedRepositoryRoot "webapp\serve_api.py"),
	"--repo-root", $resolvedRepositoryRoot,
	"--port", "0"
)
if ($gameRoot) { $arguments += @("--game-repo", $gameRoot) }

$startInfo = New-Object System.Diagnostics.ProcessStartInfo
$startInfo.FileName = $python
$startInfo.Arguments = ($arguments | ForEach-Object { ConvertTo-EscapedArgument $_ }) -join ' '
$startInfo.WorkingDirectory = $resolvedRepositoryRoot
$startInfo.UseShellExecute = $false
$startInfo.RedirectStandardOutput = $true
$startInfo.RedirectStandardError = $false
$server = New-Object System.Diagnostics.Process
$server.StartInfo = $startInfo
$jobHandle = [IntPtr]::Zero
$jobAssigned = $false
try {
	$jobHandle = [AphelionContentToolsJob]::CreateKillOnCloseJob()
	$null = $server.Start()
	[AphelionContentToolsJob]::Assign($jobHandle, $server.Handle)
	$jobAssigned = $true
	$url = $null
	while (-not $server.HasExited -and -not $url) {
		if (-not $server.StandardOutput.EndOfStream) {
			$line = $server.StandardOutput.ReadLine()
			if ($line -like "LORE_EDITOR_URL=*") { $url = $line.Substring("LORE_EDITOR_URL=".Length) }
			else { Write-Host $line }
		}
		else { Start-Sleep -Milliseconds 100 }
	}
	if (-not $url) {
		throw "Aphelion Content Tools could not start its local server. See the server diagnostics above."
	}
	Start-Process $url
	Write-Host "Aphelion Content Tools is running at $url. Close this window to stop it."
	while (-not $server.HasExited) {
		if (-not $server.StandardOutput.EndOfStream) { Write-Host $server.StandardOutput.ReadLine() }
		else { Start-Sleep -Milliseconds 250 }
	}
}
finally {
	if ($server) {
		try {
			if (-not $server.HasExited) {
				try { $null = $server.CloseMainWindow() } catch { }
				if (-not $server.WaitForExit(5000)) {
					$server.Kill()
					$server.WaitForExit()
				}
			}
			else {
				$server.WaitForExit()
			}
		}
		catch {
			# The launcher is already unwinding; avoid masking the startup or runtime error.
		}
		if ($jobHandle -ne [IntPtr]::Zero) { [AphelionContentToolsJob]::Close($jobHandle) }
		elseif ($jobAssigned -and -not $server.HasExited) { $server.Kill() }
		$server.Dispose()
	}
}
