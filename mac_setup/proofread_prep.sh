#!/usr/bin/env bash
# proofread_prep.sh — 转曲/无文字层 PDF 校对预处理（Mac 全语言版）
# 用 brew 装好的 ocrmypdf + 全语言 Tesseract + opendataloader-pdf，把 PDF 转成：
#   <out>/<名>.ocr.pdf  (可搜索/可复制文字)  +  <out>/<名>.md  (结构化文本，供交叉核对)
# 用法: proofread_prep.sh <input.pdf> [output_dir]
set -euo pipefail

IN="${1:?用法: proofread_prep.sh <input.pdf> [output_dir]}"
[ -f "$IN" ] || { echo "找不到文件: $IN" >&2; exit 1; }
BASE="$(basename "${IN%.*}")"
OUT="${2:-$(dirname "$IN")/proofread_out}"
mkdir -p "$OUT"

# 双击/Folder Action 运行时 PATH 可能不全，显式补上 brew 与 openjdk
export PATH="/opt/homebrew/bin:/opt/homebrew/opt/openjdk/bin:$HOME/.local/bin:$PATH"

# 期望语言（按你的 6 语种说明书：EN/DE/FR/ES/IT/JP，外加中文备用）
# 自动剔除未安装的语种，避免 ocrmypdf 因缺语言数据报错
WANT="eng deu fra spa ita jpn chi_sim chi_tra kor"
HAVE="$(tesseract --list-langs 2>/dev/null | tail -n +2)"
LANGS=""
for l in $WANT; do
  printf '%s\n' "$HAVE" | grep -qx "$l" && LANGS="${LANGS:+$LANGS+}$l"
done
[ -n "$LANGS" ] || LANGS="eng"
echo "▶ OCR 语言: $LANGS"

echo "▶ [1/2] OCRmyPDF 加文字层 …"
ocrmypdf --force-ocr -l "$LANGS" --output-type pdf --optimize 0 \
  "$IN" "$OUT/$BASE.ocr.pdf"

echo "▶ [2/2] opendataloader-pdf 抽结构化 Markdown …"
# --image-output off：避免在 OCR 栅格化大页上触发 WCAG 渲染崩溃，且更快更小（文字交叉核对不需要图片裁切）
opendataloader-pdf -o "$OUT" -f markdown --image-output off -q "$OUT/$BASE.ocr.pdf" >/dev/null
[ -f "$OUT/$BASE.ocr.md" ] && mv -f "$OUT/$BASE.ocr.md" "$OUT/$BASE.md"

echo "✅ 完成："
echo "   $OUT/$BASE.ocr.pdf   (可搜索/可复制文字，供 Cowork 逐页渲染做视觉终审)"
echo "   $OUT/$BASE.md        (结构化文本，供目录↔正文/表格↔接口数/跨语言枚举交叉核对)"
