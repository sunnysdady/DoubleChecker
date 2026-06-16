#!/usr/bin/env bash
# setup_domain.sh — 配置落地域名（systemd 常驻 + Nginx 反代 +（可选）HTTPS）
# 用法: bash setup_domain.sh [域名]   默认 dc.xiaomaozhiwei.com
# 前提: 该域名的 A 记录已指向本服务器公网 IP（DNS 已生效）。
set -e
DOMAIN="${1:-dc.xiaomaozhiwei.com}"
DIR="$(cd "$(dirname "$0")" && pwd)"
USER_NAME="$(whoami)"
echo "▶ 目标域名: $DOMAIN  | 应用目录: $DIR"

echo "▶ [1/4] 安装 systemd 服务（后台常驻，绑 127.0.0.1:8000）…"
cat >/etc/systemd/system/ocr-proofread.service <<EOF
[Unit]
Description=OCR Proofread Web Service
After=network.target
[Service]
Type=simple
User=${USER_NAME}
WorkingDirectory=${DIR}
ExecStart=/bin/bash ${DIR}/run.sh
Environment=PORT=8000
Environment=HOST=127.0.0.1
Restart=on-failure
RestartSec=3
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now ocr-proofread
sleep 2
systemctl --no-pager --full status ocr-proofread | head -5 || true

echo "▶ [2/4] 安装 Nginx…"
apt-get update -qq
apt-get install -y nginx >/dev/null

echo "▶ [3/4] 写站点配置（含大文件上传 300M + 长超时）…"
cat >/etc/nginx/sites-available/${DOMAIN} <<EOF
server {
    listen 80;
    server_name ${DOMAIN};
    client_max_body_size 300M;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 1800s;
        proxy_send_timeout 1800s;
    }
}
EOF
ln -sf /etc/nginx/sites-available/${DOMAIN} /etc/nginx/sites-enabled/${DOMAIN}
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# 放行 Web 端口
command -v ufw >/dev/null 2>&1 && ufw allow 'Nginx Full' >/dev/null 2>&1 || true

echo "▶ [4/4] 完成 HTTP。访问： http://${DOMAIN}"
echo
echo "如需 HTTPS（确认 DNS 已生效后再跑）："
echo "  apt-get install -y certbot python3-certbot-nginx"
echo "  certbot --nginx -d ${DOMAIN} --redirect -m you@example.com --agree-tos -n"
echo "  # 之后 https://${DOMAIN} 自动跳转，证书自动续期。"
