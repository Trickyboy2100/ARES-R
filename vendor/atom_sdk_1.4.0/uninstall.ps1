# 一键卸载脚本（Windows x64），和 install.ps1 参数风格一致。
# -Cpp 的 -Prefix 要和当初 install.ps1 用的一致，否则找不到要删的文件。
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
    Write-Host "请选择要卸载的 SDK（可多选，空格分隔序号，如: 1 3）："
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

function Uninstall-Python {
    $shown = & pip show atom-sdk 2>$null
    if (-not $shown) {
        Write-Host "[Python] 未检测到已安装的 atom-sdk，跳过。"
        return $true
    }
    Write-Host "[Python] 卸载 atom-sdk ..."
    pip uninstall -y atom-sdk
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "[Python] pip uninstall 失败（退出码 $LASTEXITCODE）。"
        return $false
    }
    Write-Host "[Python] 完成。"
    return $true
}

# 只删 install.ps1 自己拷贝过去的东西：include\atom_sdk 这个命名空间子目录，
# 以及 lib、bin 下文件名匹配 atom_sdk_cpp 的文件，不碰目标目录里其他无关内容。
function Uninstall-Cpp {
    if (-not (Assert-Writable -Dir $Prefix)) { return $false }

    $removed = $false
    try {
        $targetInclude = Join-Path $Prefix "include\atom_sdk"
        if (Test-Path $targetInclude) {
            Write-Host "[C++] 删除 $targetInclude ..."
            Remove-Item -Path $targetInclude -Recurse -Force
            $removed = $true
        }

        foreach ($subdir in @("lib", "bin")) {
            $dir = Join-Path $Prefix $subdir
            if (Test-Path $dir) {
                $matched = Get-ChildItem -Path $dir -Filter "*atom_sdk_cpp*" -ErrorAction SilentlyContinue
                if ($matched) {
                    Write-Host "[C++] 删除 $dir 下的 atom_sdk_cpp 文件 ..."
                    $matched | Remove-Item -Force
                    $removed = $true
                }
            }
        }
    } catch {
        Write-Warning "[C++] 卸载失败: $_"
        return $false
    }

    if (-not $removed) {
        Write-Host "[C++] 在 $Prefix 下未找到已安装的 atom_sdk，跳过。"
    } else {
        Write-Host "[C++] 完成。"
    }
    return $true
}

function Uninstall-CSharp {
    $sources = dotnet nuget list source 2>$null
    if (-not ($sources -match "AtomSdkLocal")) {
        Write-Host "[C#] 未找到名为 AtomSdkLocal 的 NuGet 源，跳过。"
        return $true
    }
    Write-Host "[C#] 移除本地 NuGet 源 AtomSdkLocal ..."
    dotnet nuget remove source AtomSdkLocal
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "[C#] dotnet nuget remove source 失败（退出码 $LASTEXITCODE）。"
        return $false
    }
    Write-Host "[C#] 完成。"
    return $true
}

$failed = $false
if ($Python) { if (-not (Uninstall-Python)) { $failed = $true } }
if ($Cpp) { if (-not (Uninstall-Cpp)) { $failed = $true } }
if ($CSharp) { if (-not (Uninstall-CSharp)) { $failed = $true } }

if ($failed) { exit 1 } else { exit 0 }
