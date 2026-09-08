$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "== FIO Benchmark: build Windows =="

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install "PyInstaller==6.22.2"

$VendorDir = Join-Path $ProjectRoot "vendor\fio\windows"
$TempDir = Join-Path $ProjectRoot "build\_fio_windows"
$MsiPath = Join-Path $TempDir "fio-x64.msi"
$ExtractDir = Join-Path $TempDir "extracted"

Remove-Item $TempDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $VendorDir -Recurse -Force -ErrorAction SilentlyContinue
New-Item $TempDir -ItemType Directory -Force | Out-Null
New-Item $VendorDir -ItemType Directory -Force | Out-Null
New-Item $ExtractDir -ItemType Directory -Force | Out-Null

$Release = Invoke-RestMethod `
    -Uri "https://api.github.com/repos/axboe/fio/releases/tags/fio-3.42" `
    -Headers @{ "User-Agent" = "FioBenchmarkBuild" }

$Asset = $Release.assets |
    Where-Object { $_.name -match "fio-3\.42.*x64.*\.msi$" } |
    Select-Object -First 1

if (-not $Asset) {
    throw "Não foi encontrado o MSI x64 oficial do FIO 3.42."
}

Write-Host "Baixando FIO:" $Asset.browser_download_url
Invoke-WebRequest -Uri $Asset.browser_download_url -OutFile $MsiPath

$Process = Start-Process `
    -FilePath "msiexec.exe" `
    -ArgumentList @(
        "/a",
        "`"$MsiPath`"",
        "/qn",
        "TARGETDIR=`"$ExtractDir`""
    ) `
    -Wait `
    -PassThru

if ($Process.ExitCode -ne 0) {
    throw "Falha ao extrair o MSI do FIO. Código: $($Process.ExitCode)"
}

$FioExe = Get-ChildItem $ExtractDir -Recurse -Filter "fio.exe" |
    Select-Object -First 1

if (-not $FioExe) {
    throw "fio.exe não foi encontrado após extrair o MSI."
}

$FioSourceDir = $FioExe.Directory.FullName
Write-Host "Copiando FIO de:" $FioSourceDir
Copy-Item (Join-Path $FioSourceDir "*") $VendorDir -Recurse -Force

python -m PyInstaller build\fio_benchmark.spec --noconfirm --clean

$Iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"

if (-not (Test-Path $Iscc)) {
    if (Get-Command choco -ErrorAction SilentlyContinue) {
        choco install innosetup -y --no-progress
    }
}

if (-not (Test-Path $Iscc)) {
    throw "Inno Setup 6 não foi encontrado."
}

& $Iscc "build\windows_installer.iss"

Write-Host ""
Write-Host "Concluído."
Write-Host "Instalador em: release\FioBenchmark-Setup-Windows-x64.exe"
