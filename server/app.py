#!/usr/bin/env python3
# app.py — 转曲 PDF 校对预处理 Web 服务（FastAPI）
# 上传 PDF -> OCRmyPDF 加文字层 -> opendataloader 结构化 -> checks 自动校对 -> 下载 + 问题清单
import os, re, sys, uuid, glob, shutil, threading, subprocess, traceback
import concurrent.futures
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
import checks

# systemd / 任意启动环境下，确保能找到 venv 里的 ocrmypdf / opendataloader-pdf
os.environ["PATH"] = os.path.dirname(sys.executable) + os.pathsep + os.environ.get("PATH", "")

BASE = Path(__file__).resolve().parent
JOBS_DIR = Path(os.environ.get("JOBS_DIR", "/tmp/ocr_jobs"))
JOBS_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_LANGS = {"eng", "deu", "fra", "spa", "ita", "jpn", "chi_sim", "chi_tra", "kor", "por", "nld"}
DEFAULT_LANGS = "eng+deu+fra+spa+ita+jpn"

app = FastAPI(title="OCR 校对预处理")
JOBS = {}
LOCK = threading.Lock()


def _set(job_id, **kw):
    with LOCK:
        JOBS[job_id].update(kw)


def _run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def _ocr_pages(job_id: str, in_path: Path, out_pdf: Path, langs: str) -> int:
    """逐页并行 OCR：渲染 → tesseract 单页可搜索 PDF → 合并；带实时「第 X/N 页」进度。"""
    d = out_pdf.parent
    info = _run(["pdfinfo", str(in_path)]).stdout
    m = re.search(r"Pages:\s+(\d+)", info)
    pages = int(m.group(1)) if m else 1
    pdir = d / "pg"
    pdir.mkdir(exist_ok=True)
    _set(job_id, message=f"OCR：共 {pages} 页，多语种处理中…")
    done = [0]
    lk = threading.Lock()

    def one(i: int) -> None:
        pre = pdir / f"p{i:04d}"
        _run(["pdftoppm", "-r", "300", "-png", "-singlefile",
              "-f", str(i), "-l", str(i), str(in_path), str(pre)])
        try:
            _run(["timeout", "300", "tesseract", f"{pre}.png", str(pre), "-l", langs, "pdf"])
        except subprocess.CalledProcessError:
            _run(["pdftoppm", "-r", "150", "-pdf", "-f", str(i), "-l", str(i), str(in_path), str(pre)])
        try:
            Path(f"{pre}.png").unlink()
        except OSError:
            pass
        with lk:
            done[0] += 1
            _set(job_id, message=f"OCR 第 {done[0]}/{pages} 页…")

    workers = max(1, min(4, os.cpu_count() or 2))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        for _ in ex.map(one, range(1, pages + 1)):
            pass
    outs = sorted(glob.glob(str(pdir / "p*.pdf")))
    _run(["pdfunite", *outs, str(out_pdf)])
    return pages


def extract_docx_text(path: str) -> str:
    """按文档顺序抽出 Word 段落 + 表格文本（供校对检查）。"""
    from docx import Document as DocxDocument
    from docx.oxml.ns import qn
    from docx.text.paragraph import Paragraph
    from docx.table import Table
    doc = DocxDocument(path)
    out: list[str] = []
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            out.append(Paragraph(child, doc).text)
        elif child.tag == qn("w:tbl"):
            for row in Table(child, doc).rows:
                out.append("\t".join(c.text for c in row.cells))
    return "\n".join(t for t in out if t)


def process(job_id: str, in_path: Path, langs: str, ext: str) -> None:
    d = JOBS_DIR / job_id
    base = "doc"
    ocr_pdf = d / f"{base}.ocr.pdf"
    is_pdf = ext == ".pdf"
    langs_label = langs if is_pdf else "Word(.docx) · 无需 OCR"
    try:
        if is_pdf:
            _set(job_id, stage="ocr", message="OCR 准备中…")
            _ocr_pages(job_id, in_path, ocr_pdf, langs)

            _set(job_id, stage="text", message="提取文本…")
            txt = _run(["pdftotext", "-layout", str(ocr_pdf), "-"]).stdout

            _set(job_id, stage="structure", message="opendataloader 抽结构化 Markdown…")
            try:
                _run(["opendataloader-pdf", "-o", str(d), "-f", "markdown",
                      "--image-output", "off", "-q", str(ocr_pdf)])
                mds = glob.glob(str(d / "*.md"))
                if mds and Path(mds[0]).name != f"{base}.md":
                    shutil.move(mds[0], d / f"{base}.md")
                md_path = str(d / f"{base}.md")
                md_text = Path(md_path).read_text(encoding="utf-8", errors="ignore")
            except Exception:
                md_path, md_text = None, txt      # 结构化失败则退回纯文本
            ocr_pdf_out = str(ocr_pdf)
        else:
            _set(job_id, stage="text", message="提取 Word 文本…")
            md_text = extract_docx_text(str(in_path))
            md_path = str(d / f"{base}.md")
            Path(md_path).write_text(md_text, encoding="utf-8")
            ocr_pdf_out = None

        _set(job_id, stage="checks", message="运行自动校对检查…")
        result = checks.run_all(md_text)

        # AI 层（L2 跨语言对齐 → L3 联网事实核查 → L5 审计员把关）。
        # 需配置 AI_API_KEY，否则整层跳过；逐层失败降级，不影响既有结果。
        try:
            import ai_checks
            if ai_checks.enabled():
                result = ai_checks.run_pipeline(
                    md_text, result,
                    progress=lambda m: _set(job_id, stage="checks", message=m))
        except Exception:
            pass

        # 生成报告 md
        rep = [f"# 校对自动检查报告\n", f"**文件**：{JOBS[job_id]['filename']}",
               f"**OCR 语言**：{langs_label}", "",
               f"统计：高优先 {result['stats']['high']} · 疑似串版 {result['stats']['warn']} · 低优先 {result['stats']['low']}",
               "", "> 本报告为「线索层」：自动机械检查，不替代视觉终审。",
               "> 串版为高召回候选，需人工确认；OCR 疑似错字/截断不纠错、不补全。", ""]
        if result.get("audit_summary"):
            rep += ["## AI 审计结论", "> " + result["audit_summary"], ""]
        cur = None
        for it in result["issues"]:
            sev = {"high": "## 高优先", "warn": "## 疑似串版（需人工确认）", "low": "## 低优先"}[it["severity"]]
            if sev != cur:
                rep.append("\n" + sev + "\n"); cur = sev
            loc = f"L{it['line']}" if it["line"] else "—"
            rep.append(f"- **[{it['code']}] {it['kind']}** · {it['lang']} · {loc}\n  - 原文：`{it['text']}`\n  - {it['note']}")
        rep_path = d / f"{base}.report.md"
        rep_path.write_text("\n".join(rep), encoding="utf-8")

        # Word 报告（套用原校对报告排版）
        docx_path = None
        try:
            import report_docx
            dp = d / f"{base}.report.docx"
            report_docx.build({"filename": JOBS[job_id]["filename"], "langs": langs_label,
                               "product": JOBS[job_id]["filename"]}, result, str(dp))
            docx_path = str(dp)
        except Exception:
            docx_path = None

        _set(job_id, status="done", stage="done", message="完成",
             ocr_pdf=ocr_pdf_out, md=md_path, report=str(rep_path), docx=docx_path,
             issues=result["issues"], stats=result["stats"])
    except subprocess.CalledProcessError as e:
        _set(job_id, status="error", stage="error",
             message=f"命令失败：{' '.join(e.cmd[:2])} … {(e.stderr or '')[-300:]}")
    except Exception:
        _set(job_id, status="error", stage="error", message=traceback.format_exc()[-400:])


@app.get("/", response_class=HTMLResponse)
def index():
    return (BASE / "static" / "index.html").read_text(encoding="utf-8")


@app.post("/api/jobs")
async def create_job(file: UploadFile = File(...), langs: str = Form(DEFAULT_LANGS)):
    fn = (file.filename or "").lower()
    if fn.endswith(".pdf"):
        ext = ".pdf"
    elif fn.endswith(".docx"):
        ext = ".docx"
    else:
        raise HTTPException(400, "只接受 PDF 或 Word(.docx) 文件")
    parts = [p for p in re.split(r"[+\s,]+", langs) if p]
    parts = [p for p in parts if p in ALLOWED_LANGS] or ["eng"]
    langs = "+".join(dict.fromkeys(parts))
    job_id = uuid.uuid4().hex[:12]
    d = JOBS_DIR / job_id
    d.mkdir(parents=True, exist_ok=True)
    in_path = d / ("input" + ext)
    with open(in_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    with LOCK:
        JOBS[job_id] = {"status": "running", "stage": "queued",
                        "message": "排队中…", "filename": file.filename, "langs": langs}
    threading.Thread(target=process, args=(job_id, in_path, langs, ext), daemon=True).start()
    return {"job_id": job_id, "langs": langs}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    with LOCK:
        j = JOBS.get(job_id)
    if not j:
        raise HTTPException(404, "job not found")
    out = {k: j.get(k) for k in ("status", "stage", "message", "filename", "langs", "stats", "issues")}
    out["downloads"] = {k: bool(j.get(k)) for k in ("ocr_pdf", "md", "report", "docx")}
    return JSONResponse(out)


@app.get("/api/jobs/{job_id}/download/{kind}")
def download(job_id: str, kind: str):
    with LOCK:
        j = JOBS.get(job_id)
    if not j or kind not in ("ocr_pdf", "md", "report", "docx") or not j.get(kind):
        raise HTTPException(404, "not ready")
    path = j[kind]
    names = {"ocr_pdf": "可搜索.pdf", "md": "结构化.md",
             "report": "校对报告.md", "docx": "校对报告.docx"}
    return FileResponse(path, filename=names[kind])


@app.get("/healthz")
def healthz():
    return {"ok": True}
