DEFAULT_PREFIX="/usr/local"

detect_cpp_platform_dir() {
  local arch
  arch="$(uname -m)"
  case "${arch}" in
    x86_64 | amd64) echo "linux-x86_64" ;;
    aarch64 | arm64) echo "linux-arm64" ;;
    *) echo "不支持的架构: ${arch}" >&2; return 1 ;;
  esac
}

find_cpp_package_dir() {
  local script_dir="$1" platform_dir="$2"
  find "${script_dir}/cpp/${platform_dir}" -maxdepth 1 -name 'epiceye_sdk-*' -type d 2>/dev/null | head -n 1
}

find_python_wheel() {
  find "$1/python" -maxdepth 1 -name 'epiceye-*.whl' -type f 2>/dev/null | head -n 1
}

find_csharp_source_dir() {
  local dir="$1/csharp"
  if find "${dir}" -maxdepth 1 -name 'EpicEye.SDK.*.nupkg' -type f 2>/dev/null | grep -q .; then
    echo "${dir}"
  fi
}

dir_needs_sudo() {
  local dir="$1"
  if [ -e "${dir}" ]; then
    [ ! -w "${dir}" ]
    return $?
  fi
  [ ! -w "$(dirname "${dir}")" ]
}

resolve_sudo() {
  local dir="$1"
  SUDO=""
  if [ "$(id -u)" -eq 0 ]; then
    return 0
  fi
  if dir_needs_sudo "${dir}"; then
    if command -v sudo >/dev/null 2>&1; then
      SUDO="sudo"
    else
      echo "没有写入 ${dir} 的权限，请使用 --prefix 指定可写目录。" >&2
      return 1
    fi
  fi
}
