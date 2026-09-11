# Shared helpers for install.sh / uninstall.sh. Meant to be sourced, not run directly.

DEFAULT_PREFIX="/usr/local"

# Linux 下 C++ 编译产物所在的平台子目录名（linux-x86_64 / linux-arm64），当前架构不支持时返回非 0。
detect_cpp_platform_dir() {
  local arch
  arch="$(uname -m)"
  case "${arch}" in
    x86_64 | amd64) echo "linux-x86_64" ;;
    aarch64 | arm64) echo "linux-arm64" ;;
    *)
      echo "不支持的架构: ${arch}" >&2
      return 1
      ;;
  esac
}

find_cpp_package_dir() {
  local script_dir="$1" platform_dir="$2"
  find "${script_dir}/cpp/${platform_dir}" -maxdepth 1 -name 'atom_sdk-*' -type d 2>/dev/null | head -n1
}

find_python_wheel() {
  local script_dir="$1"
  find "${script_dir}/python" -maxdepth 1 -name '*.whl' -type f 2>/dev/null | head -n1
}

find_csharp_source_dir() {
  local script_dir="$1"
  local dir="${script_dir}/csharp"
  if find "${dir}" -maxdepth 1 -name '*.nupkg' -type f 2>/dev/null | grep -q .; then
    echo "${dir}"
  fi
}

# 判断目录是否需要 sudo 才能写入：目录存在时看自身，不存在时看父目录。
dir_needs_sudo() {
  local dir="$1"
  if [ -e "${dir}" ]; then
    [ ! -w "${dir}" ]
    return $?
  fi
  [ ! -w "$(dirname "${dir}")" ]
}

# 根据目标目录设置全局变量 SUDO（"sudo" 或空字符串），没有权限又没有 sudo 时返回非 0。
resolve_sudo() {
  local dir="$1"
  SUDO=""
  if [ "$(id -u)" -eq 0 ]; then
    return 0
  fi
  if dir_needs_sudo "${dir}"; then
    if command -v sudo >/dev/null 2>&1; then
      echo "没有写入 ${dir} 的权限，将使用 sudo；也可以用 --prefix 指定自己有权限的目录。" >&2
      SUDO="sudo"
    else
      echo "没有写入 ${dir} 的权限，且系统没有 sudo，请用 --prefix 指定自己有权限的目录（如 --prefix \$HOME/atom_sdk）。" >&2
      return 1
    fi
  fi
}
