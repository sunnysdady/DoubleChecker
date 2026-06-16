#!/usr/bin/env bash
# proofread_watch.sh — 监听收件文件夹，PDF 一落地就自动预处理
# 「发 PDF 即可」：把 PDF 拖进 <收件文件夹>，自动产出到 <输出文件夹>（即 Cowork 工作文件夹）。
# 用法: proofread_watch.sh <收件文件夹> <输出文件夹>
set -euo pipefail

IN_DIR="${1:?用法: proofread_watch.sh <收件文件夹> <输出文件夹>}"
OUT_DIR="${2:?用法: proofread_watch.sh <收件文件夹> <输出文件夹>}"
DIR="$(cd "$(dirname "$0")" && pwd)"
export PATH="/opt/homebrew/bin:$PATH"
mkdir -p "$IN_DIR" "$OUT_DIR"

echo "👀 监听 $IN_DIR"
echo "   输出 → $OUT_DIR   (Ctrl-C 退出)"
fswatch -0 --event Created --event MovedTo --event Renamed "$IN_DIR" | while read -r -d "" f; do
  case "$f" in
    *.pdf|*.PDF)
      sleep 1  # 等文件写完整
      echo "── 新 PDF: $f"
      "$DIR/proofread_prep.sh" "$f" "$OUT_DIR" || echo "⚠ 处理失败: $f"
      ;;
  esac
done
