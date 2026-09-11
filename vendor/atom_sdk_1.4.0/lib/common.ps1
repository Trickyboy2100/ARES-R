# Shared helpers for install.ps1 / uninstall.ps1. Meant to be dot-sourced, not run directly.

$DefaultPrefix = "C:\Program Files\AtomSdk"

function Find-CppPackageDir {
    param([string]$ScriptDir)
    $platformDir = Join-Path $ScriptDir "cpp\windows-x64"
    if (-not (Test-Path $platformDir)) { return $null }
    Get-ChildItem -Path $platformDir -Directory -Filter "atom_sdk-*" -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
}

function Find-PythonWheel {
    param([string]$ScriptDir)
    $pythonDir = Join-Path $ScriptDir "python"
    if (-not (Test-Path $pythonDir)) { return $null }
    Get-ChildItem -Path $pythonDir -File -Filter "*.whl" -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
}

function Find-CSharpSourceDir {
    param([string]$ScriptDir)
    $csharpDir = Join-Path $ScriptDir "csharp"
    $hasNupkg = Get-ChildItem -Path $csharpDir -File -Filter "*.nupkg" -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($hasNupkg) { return $csharpDir }
    return $null
}

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# 递归向上找到已存在的祖先目录，判断是否可写（用于判断能否在其下创建 Prefix 目录）。
function Test-DirWritable {
    param([string]$Dir)
    if (Test-Path $Dir) {
        $testFile = Join-Path $Dir ([System.IO.Path]::GetRandomFileName())
        try {
            [System.IO.File]::Create($testFile).Close()
            Remove-Item $testFile -Force
            return $true
        } catch {
            return $false
        }
    }
    $parent = Split-Path $Dir -Parent
    if ([string]::IsNullOrEmpty($parent)) { return $true }
    return Test-DirWritable -Dir $parent
}

function Assert-Writable {
    param([string]$Dir)
    if (Test-IsAdministrator) { return $true }
    if (Test-DirWritable -Dir $Dir) { return $true }
    Write-Warning "没有写入 $Dir 的权限，请以管理员身份重新运行，或者用 -Prefix 指定自己有权限的目录。"
    return $false
}
