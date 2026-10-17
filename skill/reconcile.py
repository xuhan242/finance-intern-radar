# -*- coding: utf-8 -*-
"""排查结论 × 信源注册表 对账脚本。

背景：316 排查判「收录」的 42 家中曾有 24 家沉睡未接入（2026-10-12 发现），
根因是排查收口后没有强制对账。本脚本把该对账固化为一条命令：
    python reconcile.py                       # 默认对 2026-10-10 批次
    python reconcile.py --tsv <其他批次汇总>   # 对其他排查批次

输出三张清单：
  [未接入] 排查判「收录」但 sources.py 无 enabled 条目（需评估接入）
  [记录档] 排查判「收录」且已有 enabled=False 记录档（确认覆盖即可）
  [口径差] sources.py 已 enabled 但排查结论非「收录」（多为后续收复，正常）
退出码：存在[未接入]时为 1，可挂 CI/收口检查。
"""

import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sources as sources_mod  # noqa: E402

DEFAULT_TSV = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "排查", "2026-10-10", "_汇总.tsv")


def norm(name):
    """机构名归一：去公司后缀与资管括注，供两侧模糊对齐。"""
    for suf in ("股份有限公司", "有限责任公司", "基金管理", "有限公司"):
        name = name.replace(suf, "")
    return name.replace("（", "(").split("(")[0].strip()


def main():
    ap = argparse.ArgumentParser(description="排查结论 × 信源注册表对账")
    ap.add_argument("--tsv", default=DEFAULT_TSV, help="排查批次 _汇总.tsv 路径")
    a = ap.parse_args()

    registry = {}
    for s in sources_mod.SOURCES:
        names = [s["company"]] + list(s.get("also_covers", []))
        for n in names:
            registry.setdefault(norm(n), []).append(s)

    with open(a.tsv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))

    pending, filed, mismatch = [], [], []
    for r in rows:
        name, verdict = r["机构"], r["官网结论"]
        entries = registry.get(norm(name), [])
        if verdict == "收录":
            if not entries:
                pending.append(name)
            elif not any(e.get("enabled") for e in entries):
                filed.append(name)
        elif entries and any(e.get("enabled") for e in entries):
            mismatch.append(f"{name}（排查={verdict}）")

    print(f"对账批次：{os.path.basename(a.tsv)}（{len(rows)} 行）｜注册表 {len(sources_mod.SOURCES)} 条"
          f"（enabled {sum(1 for s in sources_mod.SOURCES if s.get('enabled'))}）")
    print(f"\n[未接入] 判收录且无任何注册条目：{len(pending)}")
    for n in pending:
        print("  -", n)
    print(f"\n[记录档] 判收录仅 enabled=False 记录档：{len(filed)}")
    for n in filed:
        print("  -", n)
    print(f"\n[口径差] 已启用但排查结论非收录（多为收复，核对即可）：{len(mismatch)}")
    for n in mismatch:
        print("  -", n)

    if pending:
        print(f"\n结论：{len(pending)} 家判收录未接入，需评估（对照排查档案取接口参数）。")
        sys.exit(1)
    print("\n结论：判收录机构全部有注册条目，对账通过。")


if __name__ == "__main__":
    main()