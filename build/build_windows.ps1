$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "== FIO Benchmark: build Windows =="

python -m pip install --upgrade pip
python -m pip install -r build\requirements-build.txt

$VendorDir = Join-Path $ProjectRoot "vendor\fio\windows"
$TempDir = Join-Path $ProjectRoot "build\_fio_windows"
$MsiPath = Join-Path $TempDir "fio-x64.msi"
$ExtractDir = Join-Path $TempDir "extracted"

Remove-Item $TempDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $VendorDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "dist\FioBenchmark" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "release" -Recurse -Force -ErrorAction SilentlyContinue

New-Item $TempDir -ItemType Directory -Force | Out-Null
New-Item $VendorDir -ItemType Directory -Force | Out-Null
New-Item $ExtractDir -ItemType Directory -Force | Out-Null
New-Item "release" -ItemType Directory -Force | Out-Null

Write-Host "== Baixando FIO oficial para Windows =="

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

$VendoredFio = Get-ChildItem $VendorDir -Recurse -Filter "fio.exe" |
    Select-Object -First 1 |
    ForEach-Object { $_.FullName }

if (-not $VendoredFio) {
    throw "fio.exe não está presente no diretório vendor após a cópia."
}

& $VendoredFio --version
if ($LASTEXITCODE -ne 0) {
    throw "O FIO copiado não executou corretamente."
}

Write-Host "== Gerando aplicação PyInstaller =="
python -m PyInstaller build\fio_benchmark.spec --noconfirm --clean

$BundleExe = Join-Path $ProjectRoot "dist\FioBenchmark\FioBenchmark.exe"
if (-not (Test-Path $BundleExe)) {
    throw "O executável PyInstaller não foi criado."
}

Write-Host "== Testando bundle Windows =="
$BundleReport = Join-Path $ProjectRoot "build\windows-selftest.txt"
& $BundleExe --self-test $BundleReport
if ($LASTEXITCODE -ne 0) {
    if (Test-Path $BundleReport) {
        Get-Content $BundleReport
    }
    throw "O bundle Windows falhou no self-test."
}
Get-Content $BundleReport

$Iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"

if (-not (Test-Path $Iscc)) {
    if (Get-Command choco -ErrorAction SilentlyContinue) {
        choco install innosetup -y --no-progress
    }
}

if (-not (Test-Path $Iscc)) {
    throw "Inno Setup 6 não foi encontrado."
}

Write-Host "== Criando instalador Windows =="
& $Iscc "build\windows_installer.iss"

$Installer = Join-Path $ProjectRoot "release\FioBenchmark-Setup-Windows-x64.exe"
if (-not (Test-Path $Installer)) {
    throw "O instalador Windows não foi criado."
}

Write-Host "== Instalando silenciosamente para testar o instalador final =="
$TestInstallDir = Join-Path $ProjectRoot "build\_installed_test"
Remove-Item $TestInstallDir -Recurse -Force -ErrorAction SilentlyContinue

$InstallProcess = Start-Process `
    -FilePath $Installer `
    -ArgumentList @(
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/DIR=`"$TestInstallDir`""
    ) `
    -Wait `
    -PassThru

if ($InstallProcess.ExitCode -ne 0) {
    throw "O instalador de teste falhou. Código: $($InstallProcess.ExitCode)"
}

$InstalledExe = Join-Path $TestInstallDir "FioBenchmark.exe"
if (-not (Test-Path $InstalledExe)) {
    throw "FioBenchmark.exe não foi encontrado após a instalação de teste."
}

$InstalledReport = Join-Path $ProjectRoot "build\windows-installed-selftest.txt"
& $InstalledExe --self-test $InstalledReport

if ($LASTEXITCODE -ne 0) {
    if (Test-Path $InstalledReport) {
        Get-Content $InstalledReport
    }
    throw "A aplicação instalada falhou no self-test."
}

Get-Content $InstalledReport

Write-Host ""
Write-Host "Concluído."
Write-Host "Instalador em: release\FioBenchmark-Setup-Windows-x64.exe"
