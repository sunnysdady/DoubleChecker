# 运维手册（DoubleChecker）

服务器 `45.32.216.198`，应用以 systemd 服务 `ocr-proofread` 常驻，
代码在 `/root/server`，依赖在 `/root/server/.venv`，Nginx 反代到 127.0.0.1:8000。

## 访问

- 直连：`http://45.32.216.198:8000`（若 Nginx 已绑域名且应用绑 127.0.0.1，则走域名）
- 域名：`http://dc.xiaomaozhiwei.com`（DNS 生效后；配 HTTPS 后用 https）

## 服务管理

```bash
systemctl status ocr-proofread        # 看状态
systemctl restart ocr-proofread       # 重启（改完代码后执行）
systemctl stop ocr-proofread          # 停
journalctl -u ocr-proofread -n 50 --no-pager   # 看最近日志
journalctl -u ocr-proofread -f        # 实时日志
```

## 更新代码（两种）

A. **从 Mac 推**（改完本地代码打包后）：
```bash
# Mac:
scp ~/Desktop/DoubleChecker.zip root@45.32.216.198:~
# 服务器:
ssh root@45.32.216.198 'cd ~ && unzip -o DoubleChecker.zip && \
  cp ~/DoubleChecker/server/app.py ~/DoubleChecker/server/checks.py ~/DoubleChecker/server/report_docx.py /root/server/ && \
  cp ~/DoubleChecker/server/static/index.html /root/server/static/ && \
  systemctl restart ocr-proofread && sleep 2 && curl -s http://127.0.0.1:8000/healthz'
```

B. **从 GitHub 拉**（已推到仓库后）：
```bash
cd ~/DoubleChecker && git pull
cp server/app.py server/checks.py server/report_docx.py /root/server/
cp server/static/index.html /root/server/static/
systemctl restart ocr-proofread
```

> 想彻底省事，可让服务直接跑在 `~/DoubleChecker/server`（把 `.venv` 复制过去，再 `bash setup_domain.sh dc.xiaomaozhiwei.com` 重指 systemd），之后更新只需 `git pull && systemctl restart ocr-proofread`。

## DNS + HTTPS

- DNS：在 xiaomaozhiwei.com 解析后台加 A 记录 `dc` → `45.32.216.198`。验证：`dig +short dc.xiaomaozhiwei.com`。
- HTTPS（DNS 生效后）：
  ```bash
  apt-get install -y certbot python3-certbot-nginx
  certbot --nginx -d dc.xiaomaozhiwei.com --redirect -m 你的邮箱 --agree-tos -n
  ```

## 常见问题

| 现象 | 原因 / 处理 |
|------|------|
| 网页报 `No such file or directory: 'ocrmypdf'` | venv 不在 PATH。已在 app.py 修复；确认跑的是新版并 `systemctl restart`。 |
| `opendataloader` 在大页崩 | 已用 `--image-output off` 规避；结构化失败会自动退回纯文本，不影响检查。 |
| `apt install` 时 SSH 被断开 | needrestart 重启了 sshd。重连后先 `export NEEDRESTART_MODE=a` 再装。 |
| 上传大文件报 413 | Nginx 上限。`setup_domain.sh` 已设 300M；如需更大改 `client_max_body_size`。 |
| OCR 很慢 | 多语种 × 高页数本就慢（CPU 决定）；网页有分阶段进度，属正常。 |
| 缺语言 | `tesseract --list-langs` 检查；缺则 `apt-get install tesseract-ocr-<lang>`。 |

## 数据 / 清理

- 任务产物在 `/tmp/ocr_jobs/<id>/`（重启服务器会清）。需要长期留存就改 `JOBS_DIR` 环境变量到持久目录，并定期清理。

## 输入与输出

- 输入：转曲/扫描 **PDF** 或 **Word(.docx)**。
- 输出：可搜索 PDF（仅 PDF 输入）、结构化 Markdown、校对报告（Word + Markdown）。
- 定位：自动机械检查「线索层」，不替代视觉终审；遵循四条铁律。
