#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

PREFIX="${DEFAULT_PREFIX}"
INSTALL_PYTHON=0
INSTALL_CPP=0
INSTALL_CSHARP=0

usage() {
  cat <<EOF
用法: $(basename "$0") [--python] [--cpp] [--csharp] [--all] [--prefix <目录>]

  --python          安装 Python SDK
  --cpp             安装当前 Linux 平台的 C++ SDK
  --csharp          注册 C# SDK 本地 NuGet 源
  --all             安装三种语言 SDK
  --prefix <目录>   C++ SDK 安装目录，默认 ${DEFAULT_PREFIX}

不传语言参数时进入交互菜单。
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --python) INSTALL_PYTHON=1 ;;
    --cpp) INSTALL_CPP=1 ;;
    --csharp) INSTALL_CSHARP=1 ;;
    --all) INSTALL_PYTHON=1; INSTALL_CPP=1; INSTALL_CSHARP=1 ;;
    --prefix) PREFIX="$2"; shift ;;
    -h | --help) usage; exit 0 ;;
    *) echo "未知参数: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

if [ "${INSTALL_PYTHON}" -eq 0 ] && [ "${INSTALL_CPP}" -eq 0 ] && [ "${INSTALL_CSHARP}" -eq 0 ]; then
  echo "请选择要安装的 SDK（可多选，空格分隔序号）："
  echo "  1) Python"
  echo "  2) C++"
  echo "  3) C#"
  echo "  4) 全部"
  read -rp "> " choices
  for choice in ${choices}; do
    case "${choice}" in
      1) INSTALL_PYTHON=1 ;;
      2) INSTALL_CPP=1 ;;
      3) INSTALL_CSHARP=1 ;;
      4) INSTALL_PYTHON=1; INSTALL_CPP=1; INSTALL_CSHARP=1 ;;
      *) echo "忽略未知选项: ${choice}" >&2 ;;
    esac
  done
fi

install_python() {
  local wheel
  wheel="$(find_python_wheel "${SCRIPT_DIR}")"
  [ -n "${wheel}" ] || { echo "[Python] 未找到 Wheel。" >&2; return 1; }
  python3 -m pip install --force-reinstall "${wheel}"
}

install_cpp() {
  local platform_dir package_dir
  platform_dir="$(detect_cpp_platform_dir)" || return 1
  package_dir="$(find_cpp_package_dir "${SCRIPT_DIR}" "${platform_dir}")"
  [ -n "${package_dir}" ] || { echo "[C++] 未找到 ${platform_dir} 平台包。" >&2; return 1; }
  resolve_sudo "${PREFIX}" || return 1

  echo "[C++] 安装到 ${PREFIX} ..."
  ${SUDO} mkdir -p "${PREFIX}/include" "${PREFIX}/lib" "${PREFIX}/bin"
  ${SUDO} cp -r "${package_dir}/include/epiceye_sdk" "${PREFIX}/include/"
  ${SUDO} cp -r "${package_dir}/lib/." "${PREFIX}/lib/"
  if [ -d "${package_dir}/bin" ]; then
    ${SUDO} cp -r "${package_dir}/bin/." "${PREFIX}/bin/"
  fi
  if [ "${PREFIX}" = "${DEFAULT_PREFIX}" ] && command -v ldconfig >/dev/null 2>&1; then
    ${SUDO} ldconfig
  fi
  echo "[C++] 安装完成。"
}

install_csharp() {
  local source_dir
  source_dir="$(find_csharp_source_dir "${SCRIPT_DIR}")"
  [ -n "${source_dir}" ] || { echo "[C#] 未找到 NuGet 包。" >&2; return 1; }
  dotnet nuget remove source EpicEyeSdkLocal >/dev/null 2>&1 || true
  dotnet nuget add source "${source_dir}" -n EpicEyeSdkLocal
  echo "[C#] 已注册本地 NuGet 源 EpicEyeSdkLocal。"
}

FAILED=0
[ "${INSTALL_PYTHON}" -eq 0 ] || install_python || FAILED=1
[ "${INSTALL_CPP}" -eq 0 ] || install_cpp || FAILED=1
[ "${INSTALL_CSHARP}" -eq 0 ] || install_csharp || FAILED=1
exit "${FAILED}"
