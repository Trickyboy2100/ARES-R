#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

PREFIX="${DEFAULT_PREFIX}"
UNINSTALL_PYTHON=0
UNINSTALL_CPP=0
UNINSTALL_CSHARP=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --python) UNINSTALL_PYTHON=1 ;;
    --cpp) UNINSTALL_CPP=1 ;;
    --csharp) UNINSTALL_CSHARP=1 ;;
    --all) UNINSTALL_PYTHON=1; UNINSTALL_CPP=1; UNINSTALL_CSHARP=1 ;;
    --prefix) PREFIX="$2"; shift ;;
    -h | --help) echo "用法: $(basename "$0") [--python] [--cpp] [--csharp] [--all] [--prefix <目录>]"; exit 0 ;;
    *) echo "未知参数: $1" >&2; exit 1 ;;
  esac
  shift
done

if [ "${UNINSTALL_PYTHON}" -eq 0 ] && [ "${UNINSTALL_CPP}" -eq 0 ] && [ "${UNINSTALL_CSHARP}" -eq 0 ]; then
  echo "请选择要卸载的 SDK（可多选，空格分隔序号）："
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
      4) UNINSTALL_PYTHON=1; UNINSTALL_CPP=1; UNINSTALL_CSHARP=1 ;;
    esac
  done
fi

uninstall_cpp() {
  resolve_sudo "${PREFIX}" || return 1
  ${SUDO} rm -rf "${PREFIX}/include/epiceye_sdk" "${PREFIX}/lib/cmake/epiceye_sdk"
  ${SUDO} rm -f "${PREFIX}/lib/libepiceye_sdk.so" "${PREFIX}/lib/libepiceye_sdk.so."* "${PREFIX}/lib/libepiceye_sdk.a" "${PREFIX}/bin/epiceye_sdk"*
  if [ "${PREFIX}" = "${DEFAULT_PREFIX}" ] && command -v ldconfig >/dev/null 2>&1; then
    ${SUDO} ldconfig
  fi
}

FAILED=0
if [ "${UNINSTALL_PYTHON}" -eq 1 ]; then python3 -m pip uninstall -y epiceye || FAILED=1; fi
if [ "${UNINSTALL_CPP}" -eq 1 ]; then uninstall_cpp || FAILED=1; fi
if [ "${UNINSTALL_CSHARP}" -eq 1 ]; then dotnet nuget remove source EpicEyeSdkLocal || FAILED=1; fi
exit "${FAILED}"
