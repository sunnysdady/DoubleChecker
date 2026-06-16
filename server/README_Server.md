# 转曲 PDF 校对预处理 · Ubuntu 服务器版

无文字层 PDF →（OCRmyPDF 多语种加文字层 → opendataloader 结构化 → 自动校对检查）→ 网页下载 + 问题清单。
你同事开网址、传 PDF 即可，全在服务器算，零本地安装。

## 部署（三步）

```bash
# 1) 把整个 server/ 目录传到服务器，例如 ~/server
cd ~/server

# 2) 一次性安装（需 sudo；装 Tesseract 多语种 + Ghostscript + Java + Python 依赖）
bash setup_server.sh

# 3) 启动
bash run.sh            # http://<服务器IP>:8000
```

浏览器打开 `http://<服务器IP>:8000`，拖入 PDF、选语言、开始。

### 常驻运行（推荐 systemd）

```bash
# 改 ocr-proofread.service 里的 User / WorkingDirectory 为你的实际值
sudo cp ocr-proofread.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ocr-proofread
sudo systemctl status ocr-proofread        # 查看状态
```

### 绑定落地域名（dc.xiaomaozhiwei.com）

1. **DNS**：在 xiaomaozhiwei.com 的域名解析里加一条 A 记录：主机 `dc` → 服务器公网 IP，保存，等生效（几分钟）。
2. **一键配置**（systemd 常驻 + Nginx 反代 + 大文件上传）：
   ```bash
   sudo bash setup_domain.sh dc.xiaomaozhiwei.com
   ```
   跑完即可 `http://dc.xiaomaozhiwei.com` 访问。
3. **HTTPS**（DNS 生效后）：
   ```bash
   sudo apt-get install -y certbot python3-certbot-nginx
   sudo certbot --nginx -d dc.xiaomaozhiwei.com --redirect -m 你的邮箱 --agree-tos -n
   ```
   之后 `https://dc.xiaomaozhiwei.com` 自动跳转、证书自动续期。

> `setup_domain.sh` 已把上传上限设为 300M、代理超时 1800s（适配大 PDF）；并把应用装成 systemd 服务（开机自启、崩溃自愈），绑在内网 127.0.0.1:8000，由 Nginx 对外。

## 输出

每次处理产出，网页可下载：
- **校对报告（Word）**：套用原校对报告排版（标题深红、蓝底表头、5 列问题表、分档小节）。
- **可搜索 PDF**：原页面 + OCR 文字层，可全文检索/复制。
- **结构化 Markdown**：opendataloader 按阅读顺序抽出的文本（供交叉核对）。
- **校对报告（Markdown）**：自动检查清单，分三档——
  - **高优先**：功率算术不自洽（如 9V×3A≠30W）、NVRAM 等事实待核实；
  - **疑似串版**：跨语言混入候选（高召回，需人工逐条确认；ES/IT 易混对标低置信）；
  - **低优先**：单位空格、风格禁用词。

## 边界（重要）

本服务是校对的「**线索层**」，不是定稿：
- OCR 会错字（型号、对勾矩阵、特殊符号易错）→ 数值/枚举类只作定位，**最终以矢量原稿视觉终审为准**。
- 串版检测高召回低精度，**人工确认**；语义型交叉引用（标题↔机型，如 S-01）和纯视觉乱码（tofu 方框）本层抓不到。
- 遵循四条铁律：只校产品内容 / 禁止编造 / OCR 不纠错 / 截断不补全。

## 配置项（环境变量）

- `PORT`（默认 8000）、`HOST`（默认 0.0.0.0）、`JOBS_DIR`（默认 /tmp/ocr_jobs）。

## 故障排查

- `opendataloader` 报错：确认 `default-jre` 已装（`java -version`）。本服务已用 `--image-output off` 规避大页渲染崩溃。
- 缺语言：`tesseract --list-langs` 看是否有 deu/fra/spa/ita/jpn；缺则 `sudo apt-get install tesseract-ocr-<lang>`。
- OCR 很慢：多语种 + 高页数本就慢（服务器 CPU 决定），网页有分阶段进度，属正常。
