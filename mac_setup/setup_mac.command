#!/usr/bin/env bash
# setup_mac.command — 一次性设置（可直接双击运行）
# 安装：多语言 OCR 数据 + 文件夹监听工具；并自检三件套是否就绪。
set -e
export PATH="/opt/homebrew/bin:/opt/homebrew/opt/openjdk/bin:$HOME/.local/bin:$PATH"
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "▶ 安装 Tesseract 全语言包 与 fswatch（已装会自动跳过）…"
brew install tesseract-lang fswatch

echo "▶ 赋予脚本可执行权限 …"
chmod +x "$DIR/proofread_prep.sh" "$DIR/proofread_watch.sh" "$DIR/setup_mac.command"

echo
echo "▶ 自检 …"
echo -n "ocrmypdf: ";            ocrmypdf --version
echo -n "opendataloader-pdf: "; (opendataloader-pdf --help >/dev/null 2>&1 && echo OK) || echo "缺失（pipx install opendataloader-pdf）"
echo -n "java: ";                java -version 2>&1 | head -1
echo "已安装 Tesseract 语言:"
tesseract --list-langs 2>/dev/null | tail -n +2 | tr '\n' ' '; echo

echo
echo "✅ 设置完成。两种用法："
echo "  1) 单个文件:  \"$DIR/proofread_prep.sh\"  你的文件.pdf  ~/校对工作文件夹"
echo "  2) 自动监听:  \"$DIR/proofread_watch.sh\"  ~/校对收件箱  ~/校对工作文件夹"
echo "     之后把 PDF 拖进 ~/校对收件箱 即自动处理（详见 README_Mac.md）。"
echo
echo "（按回车键关闭窗口）"; read -r _
