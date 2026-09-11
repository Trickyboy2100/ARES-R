#!/usr/bin/env bash
# 一键：在 .32 上触发 EpicEye 拍照采集点云，并把结果拉回本地
# 用法：bash capture_and_fetch.sh [相机IP]     （相机IP 默认 192.168.99.199:5000）
set -euo pipefail

SERVER="172.28.172.210"                 # .32 的 ZeroTier IP（也可改成 192.168.99.32）
REMOTE_BASE="/home/yikun/ARES-R/vendor"
PY="${REMOTE_BASE}/venv311/bin/python3.11"
CAPTURE="${REMOTE_BASE}/epiceye_sdk_4.0.0/python/examples/capture.py"
CAM_IP="${1:-192.168.99.199:5000}"
LOCAL_DIR="$(cd "$(dirname "$0")" && pwd)"   # 本脚本所在目录（captures/）

TS="$(date +%Y%m%d_%H%M%S)"
REMOTE_OUT="${REMOTE_BASE}/capture_output/${TS}"

echo "==> [1/3] 在 .32 上触发拍照并采集点云 ..."
ssh -o ConnectTimeout=15 "${SERVER}" \
    "mkdir -p '${REMOTE_OUT}' && cd '${REMOTE_OUT}' && '${PY}' '${CAPTURE}' '${CAM_IP}'"

echo "==> [2/3] 拉回本地 ..."
mkdir -p "${LOCAL_DIR}/${TS}"
scp -o ConnectTimeout=15 -r "${SERVER}:${REMOTE_OUT}/." "${LOCAL_DIR}/${TS}/"

echo "==> [3/3] 完成，本地文件："
ls -lh "${LOCAL_DIR}/${TS}"
echo "目录: ${LOCAL_DIR}/${TS}"
