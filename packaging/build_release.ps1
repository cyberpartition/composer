# Build Composer: portable folder, single exe, and installer.
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

$python = Join-Path $Root ".venv\Scripts\python.exe"
$pyinstaller = Join-Path $Root ".venv\Scripts\pyinstaller.exe"
if (-not (Test-Path $python)) {
    throw "Missing .venv. From this folder run: python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
}

& $python -m pip install pyinstaller pillow
& $python (Join-Path $Root "packaging\make_icon.py")

$release = Join-Path $Root "release"
$work = Join-Path $Root "build"
if (Test-Path $release) { Remove-Item -LiteralPath $release -Recurse -Force }
New-Item -ItemType Directory -Path $release | Out-Null

& $pyinstaller --noconfirm --distpath (Join-Path $release "pyinstaller") --workpath $work (Join-Path $Root "packaging\Composer.spec")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$portable = Join-Path $release "portable\Composer"
New-Item -ItemType Directory -Path (Split-Path $portable) -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $release "pyinstaller\Composer") -Destination $portable -Recurse
$versionLine = Select-String -Path (Join-Path $Root "composer\__init__.py") -Pattern '__version__ = "([^"]+)"'
$version = $versionLine.Matches[0].Groups[1].Value
Compress-Archive -Path $portable -DestinationPath (Join-Path $release "Composer-$version-portable.zip") -CompressionLevel Optimal

& $pyinstaller --noconfirm --distpath (Join-Path $release "onefile") --workpath (Join-Path $work "onefile") (Join-Path $Root "packaging\Composer-onefile.spec")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Copy-Item (Join-Path $release "onefile\Composer.exe") (Join-Path $release "Composer-$version.exe") -Force

$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup compiler (ISCC.exe) was not found." }
& $iscc (Join-Path $Root "packaging\composer.iss")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Output "Portable: $(Join-Path $release "Composer-$version-portable.zip")"
Write-Output "Exe: $(Join-Path $release "Composer-$version.exe")"
Write-Output "Installer: $(Join-Path $release "Composer-$version-setup.exe")"
