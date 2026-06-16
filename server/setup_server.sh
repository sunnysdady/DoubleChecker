#!/usr/bin/env bash
# setup_server.sh — Ubuntu 服务器一次性安装（需 sudo）
# 装：系统依赖(Tesseract+全语种数据/Ghostscript/Java) + Python 依赖
set -e
echo "▶ 安装系统依赖（Tesseract 多语种 / Ghostscript / Java / pip）…"
sudo apt-get update
sudo apt-get install -y \
  tesseract-ocr tesseract-ocr-eng tesseract-ocr-deu tesseract-ocr-fra \
  tesseract-ocr-spa tesseract-ocr-ita tesseract-ocr-jpn \
  tesseract-ocr-chi-sim tesseract-ocr-kor \
  ghostscript default-jre python3-pip python3-venv

DIR="$(cd "$(dirname "$0")" && pwd)"
echo "▶ 建虚拟环境并装 Python 依赖…"
python3 -m venv "$DIR/.venv"
"$DIR/.venv/bin/pip" install --upgrade pip
"$DIR/.venv/bin/pip" install -r "$DIR/requirements.txt"

echo "▶ 自检…"
"$DIR/.venv/bin/ocrmypdf" --version
"$DIR/.venv/bin/opendataloader-pdf" --help >/dev/null 2>&1 && echo "opendataloader-pdf OK"
tesseract --list-langs | tail -n +2 | tr '\n' ' '; echo
echo "✅ 安装完成。启动： bash run.sh   （默认 http://0.0.0.0:8000）"
