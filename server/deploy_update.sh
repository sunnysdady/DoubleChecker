#!/usr/bin/env bash
# deploy_update.sh — 一条命令把新代码更新到正在运行的服务器并接好 AI 层 key
#
# 在服务器上、git 仓库里运行（先 git pull 到最新分支再跑本脚本）：
#   sudo bash server/deploy_update.sh                 # 默认装到 /root/server
#   sudo bash server/deploy_update.sh /opt/server     # 或指定你的安装目录
#
# 它会：① 拷贝最新 .py 与前端到安装目录；② 确保 ai.env 存在（填 key 用）；
#        ③ 用 systemd drop-in 安全注入 ai.env（不改原服务文件）；④ 重启 + 自检。
set -e

SRC="$(cd "$(dirname "$0")" && pwd)"          # 本脚本所在 server/ 目录（git 仓库里）
DEST="${1:-/root/server}"                       # 安装目录（服务实际运行处）
SERVICE="ocr-proofread"

echo "▶ 源代码: $SRC"
echo "▶ 安装到: $DEST"
[ -d "$DEST" ] || { echo "✗ 安装目录不存在: $DEST （用第一个参数指定正确目录）"; exit 1; }

echo "▶ [1/4] 拷贝最新代码 + 校验系统依赖…"
cp "$SRC"/*.py "$DEST"/
mkdir -p "$DEST/static"
cp "$SRC/static/"* "$DEST/static/" 2>/dev/null || true
# OCR 依赖 poppler-utils(pdfinfo/pdftoppm/pdftotext/pdfunite)，缺则补装
if ! command -v pdfinfo >/dev/null 2>&1; then
  echo "  · 缺 poppler-utils，正在安装…"
  apt-get install -y poppler-utils >/dev/null 2>&1 && echo "  ✓ poppler-utils 已装" || echo "  ✗ 安装失败，请手动: apt-get install -y poppler-utils"
fi

echo "▶ [2/4] 准备 AI 配置文件 ai.env…"
if [ ! -f "$DEST/ai.env" ]; then
  cp "$SRC/ai.env.example" "$DEST/ai.env"
  chmod 600 "$DEST/ai.env"
  echo "  · 已生成 $DEST/ai.env —— 现在请填入你的 DeepSeek key："
  echo "      nano $DEST/ai.env      （改完保存：Ctrl+O 回车，退出：Ctrl+X）"
  NEED_KEY=1
else
  echo "  · 已存在 $DEST/ai.env，保留不动。"
fi

echo "▶ [3/4] 用 systemd drop-in 注入 ai.env（不改原服务文件）…"
DROP="/etc/systemd/system/${SERVICE}.service.d"
mkdir -p "$DROP"
cat > "$DROP/ai.conf" <<EOF
[Service]
EnvironmentFile=-$DEST/ai.env
EOF
systemctl daemon-reload

echo "▶ [4/4] 重启服务并自检…"
systemctl restart "$SERVICE"
sleep 2
if curl -fs http://127.0.0.1:8000/healthz >/dev/null; then
  echo "  ✓ 服务已重启并健康"
else
  echo "  ✗ 健康检查未通过，看日志： journalctl -u $SERVICE -n 40 --no-pager"
fi

echo
if [ "${NEED_KEY:-0}" = "1" ]; then
  echo "⚠ 还差最后一步：编辑 $DEST/ai.env 填上 key，然后再次重启："
  echo "    nano $DEST/ai.env  &&  systemctl restart $SERVICE"
else
  echo "✅ 完成。AI 跨语言对齐已随服务启用（前提：ai.env 里已填有效 key）。"
fi
echo "自测（可选）： cd $DEST && set -a && . ai.env && set +a && python3 ai_selftest.py"
