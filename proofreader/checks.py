#!/usr/bin/env python3
# checks.py — 确定性校对检查（L1，纯 Python·零依赖·100% 可复现）
# 这层只做"可判定"的事：算术自洽、单位空格、风格禁用词。结论是 ground truth，AI 不得覆盖。
# 用法：  python3 checks.py extracted.txt        # 或  cat extracted.txt | python3 checks.py -
# 输出：  JSON {"issues":[...], "stats":{...}}   （字段与 AI 层一致，便于合并）
import sys, re, json

ORDER = {"high": 0, "warn": 1, "low": 2}


def _line_of(text, span_start):
    return text.count("\n", 0, span_start) + 1


# ---- 功率算术自洽：V × A(可为 mA) =? W ----
# 容错匹配： 9V 3A (30W) / 9 V, 3000 mA = 30 W / 9V·3A 30W 等
PWR = re.compile(
    r'(\d+(?:[.,]\d+)?)\s*V\b[^\dA-Za-z]{0,6}'
    r'(\d+(?:[.,]\d+)?)\s*(mA|A)\b[^\dA-Za-z]{0,6}'
    r'(?:[\(（]\s*)?(\d+(?:[.,]\d+)?)\s*W\b', re.I)


def _num(s):
    return float(s.replace(",", "."))


def check_power(text):
    out = []
    for m in PWR.finditer(text):
        v = _num(m.group(1))
        a = _num(m.group(2))
        if m.group(3).lower() == "ma":
            a = a / 1000.0
        w = _num(m.group(4))
        calc = v * a
        # 允许 2% 取整误差
        if abs(calc - w) > max(0.5, w * 0.02):
            out.append({
                "code": "F-PWR", "severity": "high", "kind": "功率算术不自洽",
                "lang": "全语言", "line": _line_of(text, m.start()),
                "text": m.group(0).strip()[:160],
                "note": f"实算 {v:g}×{a:g}={calc:g}W ≠ 标称 {w:g}W；改电压/电流 或 改标称（二择一）",
            })
    # 去重
    seen, uniq = set(), []
    for o in out:
        if o["text"] in seen:
            continue
        seen.add(o["text"]); uniq.append(o)
    return uniq


# ---- 单位空格：数字与单位间建议留空格 ----
UNIT = re.compile(r'(?<![\w.])(\d+(?:[.,]\d+)?)(W|Gbps|Mbps|MB/s|GB/s|mm|kHz|MHz|GHz)\b')


def check_unit_spacing(text):
    out, seen = [], set()
    for m in UNIT.finditer(text):
        tok = m.group(0)
        if tok in seen:
            continue
        seen.add(tok)
        out.append({
            "code": "UNIT", "severity": "low", "kind": "单位空格",
            "lang": "—", "line": _line_of(text, m.start()), "text": tok,
            "note": f"数字与单位间建议加空格：{m.group(1)} {m.group(2)}（以原稿为准）",
        })
    return out


# ---- 风格·禁用客套词（说明书走技术文档风格）----
FORBIDDEN = re.compile(r"\b(please|bitte|veuillez|por favor|s'il vous pla[iî]t|per favore)\b", re.I)


def check_forbidden(text):
    out, seen = [], set()
    for m in FORBIDDEN.finditer(text):
        key = (m.group(0).lower(), _line_of(text, m.start()))
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "code": "STY-FW", "severity": "low", "kind": "风格·禁用词",
            "lang": "—", "line": _line_of(text, m.start()),
            "text": m.group(0),
            "note": f"技术文档风格建议去掉客套词「{m.group(0)}」，改祈使句",
        })
    return out


def run_all(text):
    issues = check_power(text) + check_unit_spacing(text) + check_forbidden(text)
    issues.sort(key=lambda o: (ORDER.get(o["severity"], 9), o["code"]))
    stats = {"total": len(issues),
             "high": sum(1 for i in issues if i["severity"] == "high"),
             "warn": sum(1 for i in issues if i["severity"] == "warn"),
             "low": sum(1 for i in issues if i["severity"] == "low")}
    return {"issues": issues, "stats": stats}


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "-"
    txt = sys.stdin.read() if src == "-" else open(src, encoding="utf-8", errors="ignore").read()
    print(json.dumps(run_all(txt), ensure_ascii=False, indent=2))
