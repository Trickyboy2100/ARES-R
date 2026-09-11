[CmdletBinding()]
param(
    [switch]$Python,
    [switch]$Cpp,
    [switch]$CSharp,
    [switch]$All,
    [string]$Prefix
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "lib\common.ps1")

if ([string]::IsNullOrEmpty($Prefix)) { $Prefix = $DefaultPrefix }
if ($All) { $Python = $true; $Cpp = $true; $CSharp = $true }

if (-not ($Python -or $Cpp -or $CSharp)) {
    Write-Host "请选择要安装的 SDK（可多选，空格分隔序号）："
    Write-Host "  1) Python"
    Write-Host "  2) C++"
    Write-Host "  3) C#"
    Write-Host "  4) 全部"
    $choices = Read-Host ">"
    foreach ($choice in ($choices -split '\s+')) {
        switch ($choice) {
            "1" { $Python = $true }
            "2" { $Cpp = $true }
            "3" { $CSharp = $true }
            "4" { $Python = $true; $Cpp = $true; $CSharp = $true }
            default { if ($choice) { Write-Warning "忽略未知选项: $choice" } }
        }
    }
}

function Install-PythonSdk {
    $wheel = Find-PythonWheel -ScriptDir $PSScriptRoot
    if (-not $wheel) { Write-Warning "[Python] 未找到 Wheel。"; return $false }
    & python -m pip install --force-reinstall $wheel
    return $LASTEXITCODE -eq 0
}

function Install-CppSdk {
    $packageDir = Find-CppPackageDir -ScriptDir $PSScriptRoot
    if (-not $packageDir) { Write-Warning "[C++] 未找到 Windows x64 平台包。"; return $false }
    if (-not (Assert-Writable -Dir $Prefix)) { return $false }

    try {
        New-Item -ItemType Directory -Force -Path (Join-Path $Prefix "include"), (Join-Path $Prefix "lib"), (Join-Path $Prefix "bin") | Out-Null
        Copy-Item -Path (Join-Path $packageDir "include\epiceye_sdk") -Destination (Join-Path $Prefix "include") -Recurse -Force
        Copy-Item -Path (Join-Path $packageDir "lib\*") -Destination (Join-Path $Prefix "lib") -Recurse -Force
        if (Test-Path (Join-Path $packageDir "bin")) {
            Copy-Item -Path (Join-Path $packageDir "bin\*") -Destination (Join-Path $Prefix "bin") -Recurse -Force
        }
    } catch {
        Write-Warning "[C++] 安装失败: $_"
        return $false
    }
    Write-Host "[C++] 安装完成。"
    return $true
}

function Install-CSharpSdk {
    $sourceDir = Find-CSharpSourceDir -ScriptDir $PSScriptRoot
    if (-not $sourceDir) { Write-Warning "[C#] 未找到 NuGet 包。"; return $false }
    & dotnet nuget remove source EpicEyeSdkLocal 2>$null | Out-Null
    & dotnet nuget add source $sourceDir -n EpicEyeSdkLocal
    return $LASTEXITCODE -eq 0
}

$failed = $false
if ($Python -and -not (Install-PythonSdk)) { $failed = $true }
if ($Cpp -and -not (Install-CppSdk)) { $failed = $true }
if ($CSharp -and -not (Install-CSharpSdk)) { $failed = $true }
if ($failed) { exit 1 }
