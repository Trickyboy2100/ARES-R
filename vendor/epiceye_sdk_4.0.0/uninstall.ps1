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
    Write-Host "请选择要卸载的 SDK（可多选，空格分隔序号）："
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
        }
    }
}

function Uninstall-CppSdk {
    if (-not (Assert-Writable -Dir $Prefix)) { return $false }
    try {
        Remove-Item -LiteralPath (Join-Path $Prefix "include\epiceye_sdk") -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath (Join-Path $Prefix "lib\cmake\epiceye_sdk") -Recurse -Force -ErrorAction SilentlyContinue
        Get-ChildItem -Path (Join-Path $Prefix "lib") -Filter "*epiceye_sdk*" -ErrorAction SilentlyContinue | Remove-Item -Force
        Get-ChildItem -Path (Join-Path $Prefix "bin") -Filter "*epiceye_sdk*" -ErrorAction SilentlyContinue | Remove-Item -Force
        return $true
    } catch {
        Write-Warning "[C++] 卸载失败: $_"
        return $false
    }
}

$failed = $false
if ($Python) { & python -m pip uninstall -y epiceye; if ($LASTEXITCODE -ne 0) { $failed = $true } }
if ($Cpp -and -not (Uninstall-CppSdk)) { $failed = $true }
if ($CSharp) { & dotnet nuget remove source EpicEyeSdkLocal; if ($LASTEXITCODE -ne 0) { $failed = $true } }
if ($failed) { exit 1 }
