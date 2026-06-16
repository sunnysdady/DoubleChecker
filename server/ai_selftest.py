#!/usr/bin/env python3
# ai_selftest.py — AI 层自测（你本地/服务器跑，key 全程不经过他人）
#
# 用法：
#   export AI_PROVIDER=deepseek AI_API_KEY=sk-xxx     # Claude 则 AI_PROVIDER=claude
#   python3 ai_selftest.py
#
# 做两件事：
#   1) 连通性：发一个最小请求，确认 key/网络/模型可用；
#   2) 实跑：在内置的「故意埋错」多语种样例上跑跨语言对齐，打印 AI 候选。
import os
import sys

import ai_checks as A

# 内置样例：德文版功率与英文版不一致(30W vs 33W)，且德文缺了英文的安全警告。
SAMPLE = """\
EN  Power adapter: 9V 3A (30W). Warning: do not open the casing, risk of electric shock.
DE  Netzteil: 9V 3A (33W).
FR  Adaptateur: 9V 3A (30W). Avertissement: ne pas ouvrir le boitier, risque de choc electrique.
"""


def main():
    if not A.enabled():
        print("✗ 未检测到 AI_API_KEY。请先：export AI_PROVIDER=deepseek AI_API_KEY=sk-xxx")
        sys.exit(1)

    print(f"· provider = {A._provider()}")
    print(f"· model    = {A._model()}")

    # 1) 连通性
    print("\n[1/2] 连通性测试…")
    try:
        out = A._call_llm("只回一个 JSON 对象。", '返回 {"ok": true}', timeout=30)
        print("  ✓ 模型可达，原始返回：", out.strip()[:120])
    except Exception as e:
        print("  ✗ 调用失败：", type(e).__name__, str(e)[:200])
        print("    排查：key 是否正确 / 该机器能否访问端点 / AI_BASE_URL 是否需自定义")
        sys.exit(2)

    # 2) 跨语言对齐实跑
    print("\n[2/2] 跨语言对齐实跑（内置埋错样例）…")
    findings = A.check_cross_language(SAMPLE)
    if not findings:
        print("  · 未返回候选（可能模型较保守；可换更强模型或检查样例）。")
    for f in findings:
        print(f"  [{f['severity']}] {f['kind']} · {f['lang']} · L{f['line']}")
        print(f"      原文：{f['text']}")
        print(f"      {f['note']}")
    print("\n完成。若 [1/2] 通过即说明 key 可用；[2/2] 反映该模型的校对质量。")


if __name__ == "__main__":
    main()
