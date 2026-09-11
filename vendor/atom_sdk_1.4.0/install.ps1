# 一键安装脚本（Windows x64）：从本压缩包本地安装 Python / C++ / C# SDK，
# 不需要联网访问 pypi.qianyi.ai / conan.qianyi.ai / nuget.qianyi.ai。
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

# 只有一个语言选项都没传（-Prefix 之类的其他参数不算）时才弹交互菜单。
if (-not ($Python -or $Cpp -or $CSharp)) {
    Write-Host "请选择要安装的 SDK（可多选，空格分隔序号，如: 1 3）："
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

if (-not ($Python -or $Cpp -or $CSharp)) {
    Write-Host "没有选择任何 SDK，退出。"
    exit 0
}

function Install-Python {
    $wheel = Find-PythonWheel -ScriptDir $PSScriptRoot
    if (-not $wheel) {
        Write-Warning "[Python] 未找到 wheel 文件，跳过。"
        return $false
    }
    Write-Host "[Python] 安装 $(Split-Path $wheel -Leaf) ..."
    pip install --force-reinstall $wheel
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "[Python] pip install 失败（退出码 $LASTEXITCODE）。"
        return $false
    }
    Write-Host "[Python] 安装完成。"
    return $true
}

function Install-Cpp {
    $pkgDir = Find-CppPackageDir -ScriptDir $PSScriptRoot
    if (-not $pkgDir) {
        Write-Warning "[C++] 未找到 windows-x64 平台的编译产物，跳过。"
        return $false
    }
    if (-not (Assert-Writable -Dir $Prefix)) { return $false }

    try {
        Write-Host "[C++] 安装到 $Prefix ..."
        New-Item -ItemType Directory -Force -Path (Join-Path $Prefix "include") | Out-Null
        New-Item -ItemType Directory -Force -Path (Join-Path $Prefix "lib") | Out-Null
        New-Item -ItemType Directory -Force -Path (Join-Path $Prefix "bin") | Out-Null
        Copy-Item -Path (Join-Path $pkgDir "include\atom_sdk") -Destination (Join-Path $Prefix "include") -Recurse -Force
        Get-ChildItem -Path (Join-Path $pkgDir "lib") -Filter "*atom_sdk_cpp*" -ErrorAction SilentlyContinue |
            Copy-Item -Destination (Join-Path $Prefix "lib") -Force
        Get-ChildItem -Path (Join-Path $pkgDir "bin") -Filter "*atom_sdk_cpp*" -ErrorAction SilentlyContinue |
            Copy-Item -Destination (Join-Path $Prefix "bin") -Force
    } catch {
        Write-Warning "[C++] 安装失败: $_"
        return $false
    }
    Write-Host "[C++] 安装完成，头文件在 $Prefix\include\atom_sdk，库文件在 $Prefix\lib，动态库在 $Prefix\bin。"
    if ($Prefix -ne $DefaultPrefix) {
        Write-Host "[C++] 提示：自定义路径需要在自己项目的 CMake 里加 -DCMAKE_PREFIX_PATH=$Prefix。"
    }
    return $true
}

function Install-CSharp {
    $sourceDir = Find-CSharpSourceDir -ScriptDir $PSScriptRoot
    if (-not $sourceDir) {
        Write-Warning "[C#] 未找到 nupkg 文件，跳过。"
        return $false
    }
    Write-Host "[C#] 注册本地 NuGet 源 AtomSdkLocal -> $sourceDir ..."
    dotnet nuget remove source AtomSdkLocal 2>$null | Out-Null
    dotnet nuget add source $sourceDir -n AtomSdkLocal
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "[C#] dotnet nuget add source 失败（退出码 $LASTEXITCODE）。"
        return $false
    }
    Write-Host "[C#] 完成，之后在项目里执行 dotnet add package AtomSdk 即可离线安装。"
    return $true
}

$failed = $false
if ($Python) { if (-not (Install-Python)) { $failed = $true } }
if ($Cpp) { if (-not (Install-Cpp)) { $failed = $true } }
if ($CSharp) { if (-not (Install-CSharp)) { $failed = $true } }

if ($failed) { exit 1 } else { exit 0 }
