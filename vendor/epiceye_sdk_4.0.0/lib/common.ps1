$DefaultPrefix = "C:\Program Files\EpicEyeSdk"

function Find-CppPackageDir {
    param([string]$ScriptDir)
    $platformDir = Join-Path $ScriptDir "cpp\windows-x64"
    if (-not (Test-Path $platformDir)) { return $null }
    Get-ChildItem -Path $platformDir -Directory -Filter "epiceye_sdk-*" -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
}

function Find-PythonWheel {
    param([string]$ScriptDir)
    Get-ChildItem -Path (Join-Path $ScriptDir "python") -File -Filter "epiceye-*.whl" -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
}

function Find-CSharpSourceDir {
    param([string]$ScriptDir)
    $directory = Join-Path $ScriptDir "csharp"
    $package = Get-ChildItem -Path $directory -File -Filter "EpicEye.SDK.*.nupkg" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($package) { return $directory }
    return $null
}

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

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
    if ((Test-IsAdministrator) -or (Test-DirWritable -Dir $Dir)) { return $true }
    Write-Warning "没有写入 $Dir 的权限，请以管理员身份运行，或用 -Prefix 指定可写目录。"
    return $false
}
