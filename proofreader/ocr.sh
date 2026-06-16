#!/usr/bin/env bash
# ocr.sh — 给「无视觉模型」(DeepSeek 等) 用：把转曲/扫描 PDF 转成可读文本，再交给 AI 校对
#
# 一次性装依赖（Ubuntu / Claude Code 环境，需要哪些语言就装哪些 tesseract-ocr-xxx）：
#   sudo apt-get update && sudo apt-get install -y \
#     tesseract-ocr tesseract-ocr-eng tesseract-ocr-deu tesseract-ocr-fra \
#     tesseract-ocr-spa tesseract-ocr-ita tesseract-ocr-jpn \
#     poppler-utils ghostscript default-jre
#   pip install ocrmypdf opendataloader-pdf
#
# 用法：  bash proofreader/ocr.sh 你的文件.pdf [eng+deu+fra+spa+ita+jpn]
# 产出：  work/<名>.ocr.pdf（可搜索）
#         work/extracted.md （opendataloader 结构化 Markdown，优先喂 AI；无 Java 时退回下一项）
#         work/extracted.txt（pdftotext 纯文本，给 checks.py / 兜底）
set -euo pipefail

IN="${1:?用法: bash ocr.sh <input.pdf> [语言, 默认 eng+deu+fra+spa+ita+jpn]}"
WANT="${2:-eng+deu+fra+spa+ita+jpn}"
[ -f "$IN" ] || { echo "✗ 找不到文件: $IN" >&2; exit 1; }

# 检查工具
command -v ocrmypdf >/dev/null || { echo "✗ 缺 ocrmypdf：pip install ocrmypdf" >&2; exit 1; }
command -v pdftotext >/dev/null || { echo "✗ 缺 poppler-utils：sudo apt-get install -y poppler-utils" >&2; exit 1; }

# 只保留已安装的语言包，缺的给出明确警告（乱码头号原因）
HAVE="$(tesseract --list-langs 2>/dev/null | tail -n +2)"
USE=""; MISS=""
for l in ${WANT//+/ }; do
  if printf '%s\n' "$HAVE" | grep -qx "$l"; then USE="${USE:+$USE+}$l"; else MISS="$MISS $l"; fi
done
[ -n "$USE" ] || { echo "✗ 没有任何可用语言包，先装 tesseract-ocr-<语言>" >&2; exit 1; }
[ -n "$MISS" ] && echo "⚠ 缺语言包$MISS —— 这些语种会乱码！装：sudo apt-get install -y$(for m in $MISS; do echo -n " tesseract-ocr-$m"; done)"

mkdir -p work
BASE="$(basename "${IN%.*}")"
OCR="work/${BASE}.ocr.pdf"

echo "▶ OCR（--force-ocr，语言: $USE）… 转曲 PDF 必须 force-ocr，否则跳过识别=乱码"
ocrmypdf --force-ocr -l "$USE" --output-type pdf "$IN" "$OCR"

echo "▶ 抽取纯文本 → work/extracted.txt"
pdftotext -layout "$OCR" work/extracted.txt

# opendataloader-pdf：按阅读顺序抽结构化 Markdown（更适合喂 AI）；需 Java，缺则跳过
if command -v opendataloader-pdf >/dev/null 2>&1; then
  echo "▶ 结构化抽取（opendataloader-pdf）→ work/extracted.md"
  if opendataloader-pdf -o work -f markdown --image-output off -q "$OCR" >/dev/null 2>&1; then
    MD="$(ls -t work/*.md 2>/dev/null | head -1 || true)"
    [ -n "$MD" ] && [ "$MD" != "work/extracted.md" ] && mv -f "$MD" work/extracted.md
  else
    echo "  · opendataloader 失败（多为缺 Java：sudo apt-get install -y default-jre），已退回纯文本"
  fi
else
  echo "· 跳过结构化（未装 opendataloader-pdf：pip install opendataloader-pdf）"
fi

LINES=$(wc -l < work/extracted.txt)
PRIMARY="work/extracted.txt"; [ -f work/extracted.md ] && PRIMARY="work/extracted.md（结构化，优先）"
echo "✅ 完成：$OCR"
echo "   文本：work/extracted.txt（$LINES 行）$( [ -f work/extracted.md ] && echo '＋ work/extracted.md（结构化）')"
echo "   下一步：python3 proofreader/checks.py work/extracted.txt"
echo "           再把 $PRIMARY 交给 AI 按 WORKFLOW.md 校对"
