#!/bin/bash
# 一键卸载脚本（Linux x86_64 / arm64 通用），和 install.sh 参数风格一致。
# --cpp 的 --prefix 要和当初 install.sh 用的一致，否则找不到要删的文件。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

PREFIX="${DEFAULT_PREFIX}"
UNINSTALL_PYTHON=0
UNINSTALL_CPP=0
UNINSTALL_CSHARP=0

usage() {
  cat <<EOF
用法: $(basename "$0") [--python] [--cpp] [--csharp] [--all] [--prefix <目录>]

  --python          卸载 Python SDK
  --cpp             卸载 C++ SDK
  --csharp          卸载 C# SDK（移除本地 NuGet 源）
  --all             以上三个都卸载
  --prefix <目录>   C++ SDK 的安装路径，需要和 install.sh 时用的一致，默认 ${DEFAULT_PREFIX}

不带 --python/--cpp/--csharp/--all 中任何一个时会进入交互菜单
（--prefix 可以单独传，不影响是否弹菜单）。
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --python) UNINSTALL_PYTHON=1 ;;
    --cpp) UNINSTALL_CPP=1 ;;
    --csharp) UNINSTALL_CSHARP=1 ;;
    --all)
      UNINSTALL_PYTHON=1
      UNINSTALL_CPP=1
      UNINSTALL_CSHARP=1
      ;;
    --prefix)
      PREFIX="$2"
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "未知参数: $1" >&2
      usage
      exit 1
      ;;
  esac
  shift
done

if [ "${UNINSTALL_PYTHON}" -eq 0 ] && [ "${UNINSTALL_CPP}" -eq 0 ] && [ "${UNINSTALL_CSHARP}" -eq 0 ]; then
  echo "请选择要卸载的 SDK（可多选，空格分隔序号，如: 1 3）："
  echo "  1) Python"
  echo "  2) C++"
  echo "  3) C#"
  echo "  4) 全部"
  read -rp "> " choices
  for choice in ${choices}; do
    case "${choice}" in
      1) UNINSTALL_PYTHON=1 ;;
      2) UNINSTALL_CPP=1 ;;
      3) UNINSTALL_CSHARP=1 ;;
      4)
        UNINSTALL_PYTHON=1
        UNINSTALL_CPP=1
        UNINSTALL_CSHARP=1
        ;;
      *) echo "忽略未知选项: ${choice}" >&2 ;;
    esac
  done
fi

if [ "${UNINSTALL_PYTHON}" -eq 0 ] && [ "${UNINSTALL_CPP}" -eq 0 ] && [ "${UNINSTALL_CSHARP}" -eq 0 ]; then
  echo "没有选择任何 SDK，退出。"
  exit 0
fi

uninstall_python() {
  if ! pip3 show atom-sdk >/dev/null 2>&1; then
    echo "[Python] 未检测到已安装的 atom-sdk，跳过。"
    return 0
  fi
  echo "[Python] 卸载 atom-sdk ..."
  pip3 uninstall -y atom-sdk
  echo "[Python] 完成。"
}

# 只删 install.sh 自己拷贝过去的东西：include/atom_sdk 这个命名空间子目录，
# 以及 lib 下文件名匹配 atom_sdk_cpp 的文件，不碰目标目录里其他无关内容。
uninstall_cpp() {
  local target_include="${PREFIX}/include/atom_sdk"
  local removed=0

  resolve_sudo "${PREFIX}" || return 1

  if [ -d "${target_include}" ]; then
    echo "[C++] 删除 ${target_include} ..."
    ${SUDO} rm -rf "${target_include}"
    removed=1
  fi

  local lib_matches=()
  if [ -d "${PREFIX}/lib" ]; then
    while IFS= read -r -d '' f; do
      lib_matches+=("${f}")
    done < <(find "${PREFIX}/lib" -maxdepth 1 -name '*atom_sdk_cpp*' -print0 2>/dev/null)
  fi
  if [ "${#lib_matches[@]}" -gt 0 ]; then
    echo "[C++] 删除 ${PREFIX}/lib 下的 atom_sdk_cpp 库文件 ..."
    ${SUDO} rm -f "${lib_matches[@]}"
    removed=1
  fi

  if [ "${removed}" -eq 0 ]; then
    echo "[C++] 在 ${PREFIX} 下未找到已安装的 atom_sdk，跳过。"
  else
    echo "[C++] 完成。"
  fi
}

uninstall_csharp() {
  if ! dotnet nuget list source 2>/dev/null | grep -q "AtomSdkLocal"; then
    echo "[C#] 未找到名为 AtomSdkLocal 的 NuGet 源，跳过。"
    return 0
  fi
  echo "[C#] 移除本地 NuGet 源 AtomSdkLocal ..."
  dotnet nuget remove source AtomSdkLocal
  echo "[C#] 完成。"
}

FAILED=0
if [ "${UNINSTALL_PYTHON}" -eq 1 ]; then
  uninstall_python || FAILED=1
fi
if [ "${UNINSTALL_CPP}" -eq 1 ]; then
  uninstall_cpp || FAILED=1
fi
if [ "${UNINSTALL_CSHARP}" -eq 1 ]; then
  uninstall_csharp || FAILED=1
fi
exit "${FAILED}"
