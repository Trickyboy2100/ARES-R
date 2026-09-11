#!/bin/bash
# 一键安装脚本（Linux x86_64 / arm64 通用）：从本压缩包本地安装 Python / C++ / C# SDK，
# 不需要联网访问 pypi.qianyi.ai / conan.qianyi.ai / nuget.qianyi.ai。
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

  --python          安装 Python SDK（pip install 本地 wheel）
  --cpp             安装 C++ SDK（拷贝 include/lib 到系统目录）
  --csharp          安装 C# SDK（注册为本地 NuGet 源）
  --all             以上三个都装
  --prefix <目录>   C++ SDK 的安装路径，默认 ${DEFAULT_PREFIX}
                    （没有 sudo 权限时可指定自己有权限的目录，如 --prefix \$HOME/atom_sdk）

不带 --python/--cpp/--csharp/--all 中任何一个时会进入交互菜单
（--prefix 可以单独传，不影响是否弹菜单）。
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --python) INSTALL_PYTHON=1 ;;
    --cpp) INSTALL_CPP=1 ;;
    --csharp) INSTALL_CSHARP=1 ;;
    --all)
      INSTALL_PYTHON=1
      INSTALL_CPP=1
      INSTALL_CSHARP=1
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

if [ "${INSTALL_PYTHON}" -eq 0 ] && [ "${INSTALL_CPP}" -eq 0 ] && [ "${INSTALL_CSHARP}" -eq 0 ]; then
  echo "请选择要安装的 SDK（可多选，空格分隔序号，如: 1 3）："
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
      4)
        INSTALL_PYTHON=1
        INSTALL_CPP=1
        INSTALL_CSHARP=1
        ;;
      *) echo "忽略未知选项: ${choice}" >&2 ;;
    esac
  done
fi

if [ "${INSTALL_PYTHON}" -eq 0 ] && [ "${INSTALL_CPP}" -eq 0 ] && [ "${INSTALL_CSHARP}" -eq 0 ]; then
  echo "没有选择任何 SDK，退出。"
  exit 0
fi

install_python() {
  local wheel
  wheel="$(find_python_wheel "${SCRIPT_DIR}")"
  if [ -z "${wheel}" ]; then
    echo "[Python] 未找到 wheel 文件，跳过。" >&2
    return 1
  fi
  echo "[Python] 安装 $(basename "${wheel}") ..."
  pip3 install --force-reinstall "${wheel}"
  echo "[Python] 安装完成。"
}

install_cpp() {
  local platform_dir pkg_dir
  platform_dir="$(detect_cpp_platform_dir)" || return 1
  pkg_dir="$(find_cpp_package_dir "${SCRIPT_DIR}" "${platform_dir}")"
  if [ -z "${pkg_dir}" ]; then
    echo "[C++] 未找到 ${platform_dir} 平台的编译产物，跳过。" >&2
    return 1
  fi

  resolve_sudo "${PREFIX}" || return 1

  echo "[C++] 安装到 ${PREFIX} ..."
  ${SUDO} mkdir -p "${PREFIX}/include" "${PREFIX}/lib"
  ${SUDO} cp -r "${pkg_dir}/include/atom_sdk" "${PREFIX}/include/"
  ${SUDO} cp "${pkg_dir}"/lib/*atom_sdk_cpp* "${PREFIX}/lib/"
  if [ "${PREFIX}" = "${DEFAULT_PREFIX}" ] && command -v ldconfig >/dev/null 2>&1; then
    ${SUDO} ldconfig
  fi
  echo "[C++] 安装完成，头文件在 ${PREFIX}/include/atom_sdk，库文件在 ${PREFIX}/lib。"
  if [ "${PREFIX}" != "${DEFAULT_PREFIX}" ]; then
    echo "[C++] 提示：自定义路径需要在自己项目的 CMake 里加 -DCMAKE_PREFIX_PATH=${PREFIX}，运行时可能还要设置 LD_LIBRARY_PATH=${PREFIX}/lib。"
  fi
}

install_csharp() {
  local source_dir
  source_dir="$(find_csharp_source_dir "${SCRIPT_DIR}")"
  if [ -z "${source_dir}" ]; then
    echo "[C#] 未找到 nupkg 文件，跳过。" >&2
    return 1
  fi
  echo "[C#] 注册本地 NuGet 源 AtomSdkLocal -> ${source_dir} ..."
  dotnet nuget remove source AtomSdkLocal >/dev/null 2>&1 || true
  dotnet nuget add source "${source_dir}" -n AtomSdkLocal
  echo "[C#] 完成，之后在项目里执行 dotnet add package AtomSdk 即可离线安装。"
}

FAILED=0
if [ "${INSTALL_PYTHON}" -eq 1 ]; then
  install_python || FAILED=1
fi
if [ "${INSTALL_CPP}" -eq 1 ]; then
  install_cpp || FAILED=1
fi
if [ "${INSTALL_CSHARP}" -eq 1 ]; then
  install_csharp || FAILED=1
fi
exit "${FAILED}"
