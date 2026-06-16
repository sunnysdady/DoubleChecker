# checks.py — 校对自动检查（在 OCR 结构化文本上跑，仅作"线索层"，不替代视觉终审）
# 复刻管线：串版检测 / 功率算术 / 事实触发(NVRAM) / 单位空格 / 禁用词
import re
from collections import Counter
from langdetect import detect, DetectorFactory
DetectorFactory.seed = 0

LCODE = {'en': 'EN', 'es': 'ES', 'de': 'DE', 'fr': 'FR', 'it': 'IT', 'ja': 'JP'}
LATIN = {'EN', 'ES', 'DE', 'FR', 'IT'}
CLOSE = {frozenset({'ES', 'IT'}), frozenset({'ES', 'PT'})}  # 易混语对 -> 低置信


def _clean_len(s):
    return len(re.sub(r'[^A-Za-zÀ-ÿ぀-ヿ一-鿿]', '', s))


def _is_garble(s):
    toks = re.findall(r'\S+', s)
    if not toks:
        return True
    short = sum(1 for t in toks if len(re.sub(r'[^A-Za-zÀ-ÿ]', '', t)) <= 2)
    if short / len(toks) > 0.4:
        return True
    if len(re.findall(r'@\d+\s*Hz', s)) >= 2:          # 显示矩阵行
        return True
    if len(re.findall(r'\b[JYVNI]\b|√|✓|\bNI\b|\baf\b|\bal\b', s)) >= 3:
        return True
    return False


def _realwords(s):
    return [t for t in re.findall(r"[A-Za-zÀ-ÿ']+", s) if len(t) >= 4]


def _line_lang(s):
    if _clean_len(s) < 10:
        return None
    try:
        return LCODE.get(detect(s))
    except Exception:
        return None


def _segment(lines, langs):
    """按行语言平滑出每行所属"段落语言"（mode 滤波，填补空行）。"""
    n = len(lines)
    block = [None] * n
    w = 8
    for i in range(n):
        c = Counter(langs[j] for j in range(max(0, i - w), min(n, i + w + 1))
                    if langs[j] and not _is_garble(lines[j]))
        if c:
            block[i] = c.most_common(1)[0][0]
    # 前后填补
    last = None
    for i in range(n):
        if block[i]:
            last = block[i]
        elif last:
            block[i] = last
    return block


def _interior(block, i, k=3):
    """该行是否处于同语言段落内部（前后 k 行同段语言），排除段落边界。"""
    lo, hi = max(0, i - k), min(len(block), i + k + 1)
    return all(block[j] == block[i] for j in range(lo, hi))


def check_langmix(lines):
    langs = [_line_lang(s) for s in lines]
    block = _segment(lines, langs)
    # 高召回设计：串版多发生在短标题（S-01/02/03 均为标题），故只用 garble+≥2实词过滤，
    # 不做 interior 硬过滤；全部标「疑似·需人工确认」，非易混语对优先、ES/IT 易混对降置信。
    out, seen = [], set()
    for i, (s, ll) in enumerate(zip(lines, langs)):
        st = s.strip()
        if not ll or len(st) < 12 or _is_garble(s) or len(_realwords(s)) < 2:
            continue
        sec = block[i]
        if not sec or ll == sec:
            continue
        is_latin_pair = {ll, sec} <= LATIN and 'EN' not in (ll, sec)
        is_jp_latin = sec == 'JP' and ll in ('IT', 'FR', 'ES', 'DE')
        if not (is_latin_pair or is_jp_latin):
            continue
        key = (sec, ll, st[:45])
        if key in seen:
            continue
        seen.add(key)
        low = frozenset({ll, sec}) in CLOSE
        out.append({
            'code': 'S-MIX', 'severity': 'warn',
            'kind': '疑似串版' + ('（低置信·ES/IT 易混）' if low else ''),
            'lang': f'{sec}←{ll}', 'line': i + 1, 'text': st[:160],
            '_low': low,
            'note': f'段落[{sec}] 中检出疑似[{ll}]文本，需人工确认是否语言串版'})
    # 非易混语对排前（更可能是真串版）
    out.sort(key=lambda o: (o['_low'], o['line']))
    for o in out:
        o.pop('_low', None)
    return out


def check_power(text):
    out = []
    for m in re.finditer(r'(\d+)\s*V\s*[^\dA-Za-z]{0,4}(\d+)\s*A\s*[(（]\s*(\d+)\s*W', text):
        v, a, w = map(int, m.groups())
        if v * a != w:
            out.append({
                'code': 'F-PWR', 'severity': 'high', 'kind': '功率算术不自洽',
                'lang': '全语言', 'line': None,
                'text': f'{v}V × {a}A 标注 {w}W',
                'note': f'实算 {v}×{a}={v*a}W ≠ 标称 {w}W；二者择一修正（改电压/电流 或 改标称）'})
    # 去重
    uniq, seen = [], set()
    for o in out:
        if o['text'] in seen:
            continue
        seen.add(o['text']); uniq.append(o)
    return uniq


FACT_PATTERNS = [
    (r'\bNVRAM\b', 'F-NVRAM', 'NVRAM 重置：Apple Silicon(M 系)不支持手动重置 NVRAM，需联网核实是否删除/限定 Intel'),
]


def check_facts(lines):
    out = []
    for i, s in enumerate(lines):
        for pat, code, note in FACT_PATTERNS:
            if re.search(pat, s, re.I):
                out.append({'code': code, 'severity': 'high', 'kind': '事实待核实',
                            'lang': '—', 'line': i + 1, 'text': s.strip()[:160], 'note': note})
    return out


FORBIDDEN = re.compile(r"\b(please|bitte|veuillez|por favor|s'il vous pla[iî]t)\b", re.I)


def check_forbidden(lines):
    out = []
    for i, s in enumerate(lines):
        m = FORBIDDEN.search(s)
        if m:
            out.append({'code': 'STY-FW', 'severity': 'low', 'kind': '风格·禁用词',
                        'lang': '—', 'line': i + 1, 'text': s.strip()[:160],
                        'note': f'说明书走技术文档风格，建议去掉客套词「{m.group(0)}」改祈使句'})
    return out


UNIT = re.compile(r'(?<![\w.])(\d+(?:[.,]\d+)?)(W|Gbps|Mbps|MB/s|GB/s|mm)\b')


def check_unit_spacing(lines):
    out, seen = [], set()
    for i, s in enumerate(lines):
        for m in UNIT.finditer(s):
            tok = m.group(0)
            if tok in seen:
                continue
            seen.add(tok)
            out.append({'code': 'UNIT', 'severity': 'low', 'kind': '单位空格',
                        'lang': '—', 'line': i + 1, 'text': tok,
                        'note': f'数字与单位间建议加空格：{m.group(1)} {m.group(2)}（OCR 空格不稳，以原稿为准）'})
    return out


def run_all(text):
    lines = text.splitlines()
    issues = []
    issues += check_power(text)
    issues += check_facts(lines)
    issues += check_langmix(lines)
    issues += check_forbidden(lines)
    issues += check_unit_spacing(lines)
    order = {'high': 0, 'warn': 1, 'low': 2}
    issues.sort(key=lambda o: (order.get(o['severity'], 9), o['code']))
    stats = {
        'total': len(issues),
        'high': sum(1 for i in issues if i['severity'] == 'high'),
        'warn': sum(1 for i in issues if i['severity'] == 'warn'),
        'low': sum(1 for i in issues if i['severity'] == 'low'),
    }
    return {'issues': issues, 'stats': stats}
