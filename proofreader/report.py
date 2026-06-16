#!/usr/bin/env python3
# report.py — 由合并后的 findings 生成交付报告：① 自包含 HTML ② Word(.docx)
# 用法： python3 report.py merged.json out_dir   （merged.json = {meta, issues, stats, audit_summary}）
# HTML 永远生成；Word 需 python-docx，缺失则跳过并提示。
import sys, json, html
from datetime import date

SEV = {"high": ("高优先", "#c0392b"), "warn": ("疑似 / 待确认", "#e67e22"), "low": ("低优先", "#7f8c8d")}


def _rows(issues, sev):
    items = [i for i in issues if i.get("severity") == sev]
    if not items:
        return "<p style='color:#888'>（无）</p>"
    r = ["<table><tr><th>代号</th><th>位置</th><th>原文（逐字）</th><th>类型</th><th>建议 / 说明</th></tr>"]
    for it in items:
        loc = html.escape(str(it.get("lang") or "—"))
        if it.get("line"):
            loc += f" · L{it['line']}"
        r.append("<tr><td>{}</td><td>{}</td><td><code>{}</code></td><td>{}</td><td>{}</td></tr>".format(
            html.escape(it.get("code", "")), loc, html.escape(it.get("text", "")),
            html.escape(it.get("kind", "")), html.escape(it.get("note", ""))))
    r.append("</table>")
    return "".join(r)


def build_html(meta, result, out_path):
    st = result.get("stats", {})
    audit = result.get("audit_summary", "")
    secs = ""
    for sev, (label, color) in SEV.items():
        secs += f"<h2 style='border-left:5px solid {color};padding-left:10px'>{label}</h2>" + _rows(result["issues"], sev)
    audit_box = (f"<div class='audit'><b>AI 审计结论（独立审计员把关）</b><br>{html.escape(audit)}</div>"
                 if audit else "")
    doc = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>校对报告 · {html.escape(meta.get('product',''))}</title>
<style>
body{{font-family:system-ui,"PingFang SC","Microsoft YaHei",sans-serif;max-width:980px;margin:0 auto;padding:30px;color:#1a1a1a;line-height:1.6}}
h1{{color:#c00000;font-size:26px;margin-bottom:2px}} h2{{font-size:19px;margin:26px 0 8px}}
.sub{{color:#666;margin-bottom:14px}}
.kv{{border-collapse:collapse;margin:10px 0}} .kv td{{border:1px solid #ddd;padding:6px 12px}} .kv td:first-child{{background:#efefef;font-weight:600}}
.stat{{display:flex;gap:10px;margin:14px 0}} .stat div{{border:1px solid #ddd;border-radius:8px;padding:8px 16px}} .stat b{{font-size:24px;display:block}}
table{{width:100%;border-collapse:collapse;margin:8px 0;font-size:13.5px}} th,td{{border:1px solid #ddd;padding:7px 9px;text-align:left;vertical-align:top}} th{{background:#d5e8f0}}
code{{background:#f4f4f4;padding:1px 5px;border-radius:4px}}
.audit{{background:#f4f0ff;border-left:5px solid #5b3a8c;padding:12px 16px;border-radius:0 8px 8px 0;margin:14px 0}}
.boundary{{background:#fffaf0;border-left:4px solid #e67e22;padding:10px 14px;font-size:13px;color:#555;margin-top:24px}}
.stamp{{display:inline-block;border:2px solid #5b3a8c;color:#5b3a8c;border-radius:6px;padding:2px 10px;font-size:12px;transform:rotate(-3deg)}}
</style></head><body>
<h1>校对报告 {('<span class="stamp">已审计</span>' if audit else '')}</h1>
<div class="sub">{html.escape(meta.get('product', meta.get('filename','')))}</div>
<table class="kv">
<tr><td>文件 / 产品</td><td>{html.escape(meta.get('filename',''))}</td></tr>
<tr><td>语言覆盖</td><td>{html.escape(meta.get('langs',''))}</td></tr>
<tr><td>风格标准</td><td>Apple 技术文档风格（专业·精准·简洁·无营销腔）</td></tr>
<tr><td>制表日期</td><td>{meta.get('date', date.today().isoformat())}</td></tr>
</table>
<div class="stat"><div><b>{st.get('total',0)}</b>总数</div><div style="color:#c0392b"><b>{st.get('high',0)}</b>高优先</div>
<div style="color:#e67e22"><b>{st.get('warn',0)}</b>疑似/待确认</div><div style="color:#7f8c8d"><b>{st.get('low',0)}</b>低优先</div></div>
{audit_box}
{secs}
<div class="boundary">本报告为「线索层」，不替代视觉终审。四条铁律：只校产品内容 / 禁止编造 / OCR 不纠错 / 截断不补全。
事实真伪、纯视觉乱码、语义型交叉引用需人工 + 联网最终确认。</div>
</body></html>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(doc)
    return out_path


def build_docx(meta, result, out_path):
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor, Inches
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
    except ImportError:
        return None
    FONT = "Arial"

    def shade(cell, fill):
        tcPr = cell._tc.get_or_add_tcPr(); shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear'); shd.set(qn('w:fill'), fill); tcPr.append(shd)

    def setc(cell, t, bold=False, size=10):
        cell.text = ""; r = cell.paragraphs[0].add_run(t or "")
        r.font.name = FONT; r.font.size = Pt(size); r.font.bold = bold

    doc = Document()
    doc.styles["Normal"].font.name = FONT; doc.styles["Normal"].font.size = Pt(10)
    p = doc.add_paragraph(); r = p.add_run("校对报告")
    r.font.name = FONT; r.font.size = Pt(20); r.font.bold = True; r.font.color.rgb = RGBColor(0xC0, 0, 0)
    doc.add_paragraph(meta.get("product", meta.get("filename", "")))
    st = result.get("stats", {})
    if result.get("audit_summary"):
        h = doc.add_heading(level=2); h.add_run("AI 审计结论（独立审计员把关）").font.name = FONT
        ap = doc.add_paragraph(); ar = ap.add_run(result["audit_summary"]); ar.font.italic = True; ar.font.name = FONT
    for sev, (label, _c) in SEV.items():
        items = [i for i in result["issues"] if i.get("severity") == sev]
        h = doc.add_heading(level=2); h.add_run(f"{label}（{len(items)}）").font.name = FONT
        if not items:
            doc.add_paragraph("（无）"); continue
        t = doc.add_table(rows=1, cols=5); t.style = "Table Grid"
        for i, c in enumerate(["代号", "位置", "原文", "类型", "建议/说明"]):
            setc(t.rows[0].cells[i], c, bold=True); shade(t.rows[0].cells[i], "D5E8F0")
        for it in items:
            loc = (it.get("lang") or "—") + (f" · L{it['line']}" if it.get("line") else "")
            cells = t.add_row().cells
            for i, v in enumerate([it.get("code", ""), loc, it.get("text", ""), it.get("kind", ""), it.get("note", "")]):
                setc(cells[i], str(v))
    doc.add_heading(level=2).add_run("说明与边界").font.name = FONT
    for line in ["本报告为线索层，不替代视觉终审。",
                 "四条铁律：只校产品内容 / 禁止编造 / OCR 不纠错 / 截断不补全。"]:
        doc.add_paragraph(line, style="List Bullet")
    doc.save(out_path)
    return out_path


if __name__ == "__main__":
    data = json.load(open(sys.argv[1], encoding="utf-8"))
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "."
    meta = data.get("meta", {})
    result = {"issues": data.get("issues", []), "stats": data.get("stats", {}),
              "audit_summary": data.get("audit_summary", "")}
    h = build_html(meta, result, f"{out_dir}/report.html")
    print(f"✓ HTML: {h}")
    d = build_docx(meta, result, f"{out_dir}/report.docx")
    print(f"✓ Word: {d}" if d else "· Word 跳过（pip install python-docx 后可生成）")
