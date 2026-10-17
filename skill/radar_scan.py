# -*- coding: utf-8 -*-
"""finance-intern-radar 主扫描器。

用法（工作目录任意，脚本定位自动）：
    python radar_scan.py                        # 全部信源，默认 10 个工作日窗口
    python radar_scan.py --direction 券商        # 单方向（公募/券商/保险/综合金融/资管）
    python radar_scan.py --days 20              # 自定义工作日窗口
    python radar_scan.py --start 20260901 --end 20260930   # 自定义自然日区间
    python radar_scan.py --healthcheck          # 信源体检（60 自然日活性）

输出：日期 × 机构类型 矩阵 Excel（行=发布日期倒序，格内一条岗位一个超链接），
窗口内零新增时不落盘，只回一句结论。
"""

import argparse
import datetime
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import adapters  # noqa: E402
import sources as sources_mod  # noqa: E402
import workcalendar  # noqa: E402

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEALTH_DAYS = 60  # 信源时效容忍度（自然日）
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state", "cache")
CACHE_TTL = 1800  # 秒；同日重复运行复用解析结果
_cache_hits = [0]


def parse_args():
    p = argparse.ArgumentParser(description="金融机构官网日常实习岗位扫描")
    p.add_argument("--direction", default="all",
                   help="all/公募/券商/保险/综合金融/资管（默认 all）")
    p.add_argument("--days", type=int, default=10,
                   help="输出窗口（工作日，默认 10）")
    p.add_argument("--start", help="自然日区间起点 YYYYMMDD（与 --end 配合，覆盖 --days）")
    p.add_argument("--end", help="自然日区间终点 YYYYMMDD")
    p.add_argument("--out", help="输出 Excel 路径（默认 output/radar_时间戳.xlsx）")
    p.add_argument("--healthcheck", action="store_true", help="信源体检模式")
    p.add_argument("--recheck", action="store_true",
                   help="复测模式：注册表记录档＋recheck_spec.json 批量探针，产出升格候选清单")
    p.add_argument("--reuse-cache", action="store_true",
                   help="复用 30 分钟内的解析结果（按信源缓存，默认关闭）")
    return p.parse_args()


def norm_date(s):
    return datetime.datetime.strptime(s, "%Y%m%d").date()


def _fetch_cached(src, reuse_cache):
    if not reuse_cache:
        return adapters.fetch_source(src)
    p = os.path.join(CACHE_DIR, f"{src['id']}.json")
    try:
        with open(p, encoding="utf-8") as f:
            c = json.load(f)
        if time.time() - c["ts"] < CACHE_TTL:
            _cache_hits[0] += 1
            return c["rows"]
    except Exception:
        pass
    rows = adapters.fetch_source(src)
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "rows": rows}, f, ensure_ascii=False)
    except Exception:
        pass
    return rows


def collect(sources, start, end, reuse_cache=False):
    """逐信源取数、去重、窗口过滤。返回 (行列表, 各信源统计, 失败列表)。

    并发策略：同招聘宿主（北森 zhiye / hotjob / Moka）的信源串行 —— 单宿主
    请求节奏与逐家串行完全一致；跨宿主 8 线程并行。结果按原信源顺序组装，
    输出与串行版逐条一致。"""
    _cache_hits[0] = 0
    groups = {}
    for i, src in enumerate(sources):
        groups.setdefault(_host_group(src), []).append((i, src))
    results = {}

    def run_group(items):
        out = []
        for i, src in items:
            try:
                rows = _fetch_cached(src, reuse_cache)
            except Exception as e:  # 单信源失败不阻断整体
                out.append((i, src, None, f"{type(e).__name__}: {e}"[:120]))
                continue
            out.append((i, src, rows, None))
        return out

    with ThreadPoolExecutor(max_workers=8) as ex:
        for group_out in ex.map(run_group, list(groups.values())):
            for i, src, rows, err in group_out:
                results[i] = (src, rows, err)

    all_rows, stats, failures = [], [], []
    for i in range(len(sources)):  # 按原始顺序组装（与串行版一致）
        src, rows, err = results[i]
        if err is not None:
            failures.append({"company": src["company"], "error": err})
            stats.append({"company": src["company"], "total": 0, "in_window": 0, "status": "失败"})
            continue
        seen = {}
        for r in rows:
            r["org_type"] = src["org_type"]
            key = f"{r['company']}|{r['post_no']}"
            if key in seen and seen[key]["date"] >= r["date"]:
                continue
            seen[key] = r
        uniq = list(seen.values())
        in_win = [r for r in uniq if start.isoformat() <= r["date"] <= end.isoformat()]
        all_rows.extend(in_win)
        stats.append({"company": src["company"], "total": len(uniq),
                      "in_window": len(in_win), "status": "正常"})
    return all_rows, stats, failures


_HOST_GROUPS = {  # 共享宿主的通道归组，组内串行防限流
    "beisen": "zhiye.com", "beisen_classic": "zhiye.com",
    "hotjob": "hotjob.cn", "hotjob_wt": "hotjob.cn", "moka": "mokahr.com",
}


def _host_group(src):
    return _HOST_GROUPS.get(src["adapter"], src["id"])


def display_label(r):
    title = re.sub(r"\([Jj]\d+\)\s*$", "", r["title"]).strip()
    if r["entity"] and r["entity"] not in title:
        return f"{r['company']}·{r['entity']} - {title}"
    return f"{r['company']} - {title}"


def clean_city(s):
    """城市串清洗：多城市合并（顿号分隔）、"省·市"/"市-区"取市级、去行政区划后缀。
    例：'广西壮族自治区·南宁市'→'南宁'；'广州市-天河区'→'广州'；'北京市、上海市'→'北京/上海'。"""
    if not s:
        return ""
    out = []
    for part in re.split(r"[、,，/]", str(s)):
        segs = [x.strip() for x in re.split(r"[·\-—]", part) if x.strip()]
        if not segs:
            continue
        city = ""
        for seg in segs:
            if seg.endswith("特别行政区"):
                city = seg[:-5]
                break
            if seg.endswith("市"):
                city = seg[:-1]
                break
        if not city:
            city = re.sub(r"(自治区|省|市|区)$", "", segs[0])
        if city and city not in out:
            out.append(city)
    return "/".join(out)


def label_with_city(r):
    city = clean_city(r.get("cities", ""))
    return display_label(r) + (f"（{city}）" if city else "")


def write_matrix(rows, stats, failures, start, end, calendar_note, out_path):
    wb = Workbook()

    # ---- Sheet1: 矩阵（一行 = 一个日期；每格 = 该日期该类型全部岗位）----
    ws = wb.active
    ws.title = "岗位矩阵"
    org_types = [t for t in sources_mod.ORG_TYPE_ORDER
                 if any(r["org_type"] == t for r in rows)]
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="4472C4")
    ws.cell(row=1, column=1, value="日期").font = header_font
    ws.cell(row=1, column=1).fill = header_fill
    for i, t in enumerate(org_types, start=2):
        c = ws.cell(row=1, column=i, value=t)
        c.font = header_font
        c.fill = header_fill
        ws.column_dimensions[get_column_letter(i)].width = 58
    ws.column_dimensions["A"].width = 12

    by_date_org = {}
    for r in rows:
        by_date_org.setdefault(r["date"], {}).setdefault(r["org_type"], []).append(r)

    # 一天一块：块内按"层"横向铺开（一层一行、各类型各占一格，一格一岗位一链接），
    # 日期列纵向合并。
    link_font = Font(color="0563C1", underline="single")
    row_i = 2
    for date in sorted(by_date_org, reverse=True):
        block_start = row_i
        per_type = {t: sorted(by_date_org[date].get(t, []), key=lambda x: (x["company"], x["title"]))
                    for t in org_types}
        max_n = max((len(v) for v in per_type.values()), default=0)
        for k in range(max_n):
            filled = False
            for t in org_types:
                items = per_type[t]
                if k < len(items):
                    c = ws.cell(row=row_i, column=org_types.index(t) + 2, value=label_with_city(items[k]))
                    c.hyperlink = items[k]["url"]
                    c.font = link_font
                    c.alignment = Alignment(wrap_text=True, vertical="center")
                    filled = True
            if filled:
                ws.row_dimensions[row_i].height = 30
                row_i += 1
        dcell = ws.cell(row=block_start, column=1, value=datetime.date.fromisoformat(date))
        dcell.number_format = "yyyy-mm-dd"
        dcell.alignment = Alignment(vertical="top")
        if row_i - block_start > 1:
            ws.merge_cells(start_row=block_start, start_column=1, end_row=row_i - 1, end_column=1)

    # ---- Sheet: 岗位清单（一行一岗，链接可点） ----
    ws3 = wb.create_sheet("岗位清单")
    ws3.append(["日期", "机构类型", "岗位", "Base地", "链接"])
    for c in ws3[1]:
        c.font = header_font
        c.fill = header_fill
    for k, v in {"A": 12, "B": 10, "C": 60, "D": 12, "E": 110}.items():
        ws3.column_dimensions[k].width = v
    link_font = Font(color="0563C1", underline="single")
    for r in sorted(rows, key=lambda x: (x["date"], x["org_type"]), reverse=True):
        ws3.append([datetime.date.fromisoformat(r["date"]), r["org_type"],
                    display_label(r), clean_city(r.get("cities", "")), r["url"]])
        cell = ws3.cell(row=ws3.max_row, column=5)
        cell.hyperlink = r["url"]
        cell.font = link_font
        ws3.cell(row=ws3.max_row, column=3).alignment = Alignment(wrap_text=True, vertical="center")

    # ---- Sheet: 说明 ----
    ws2 = wb.create_sheet("扫描说明")
    ws2.column_dimensions["A"].width = 22
    ws2.column_dimensions["B"].width = 90
    info = [
        ("扫描时间", datetime.datetime.now().strftime("%Y-%m-%d %H:%M")),
        ("输出窗口", f"{start.isoformat()} 至 {end.isoformat()}"
         + (f"（{args_days_label}）" if args_days_label else "")),
        ("工作日历", calendar_note),
        ("岗位总数", str(len(rows))),
    ]
    for k, v in info:
        ws2.append([k, v])
    ws2.append([])
    ws2.append(["信源", "去重后在招 / 窗口内新增", "状态"])
    for s in stats:
        ws2.append([s["company"], f"{s['total']} / {s['in_window']}", s["status"]])
    if failures:
        ws2.append([])
        ws2.append(["失败信源", "原因"])
        for f in failures:
            ws2.append([f["company"], f["error"]])
    disabled = [s["company"] for s in sources_mod.SOURCES if not s.get("enabled")]
    if disabled:
        ws2.append([])
        ws2.append(["未启用信源", "、".join(disabled)])
    wb.move_sheet(ws3, offset=-1)  # 页签顺序：岗位清单优先展示
    wb.save(out_path)


args_days_label = ""


RECHECK_SPEC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recheck_spec.json")


def run_recheck():
    """复测模式：注册表可探针记录档 ＋ recheck_spec.json 目标批量探测。

    判定统一按 60 自然日新增；升格候选只出清单，enabled 仍需人工签核
    （清单=签核资产的口径不破）。spec 的 manual 节与实习僧观察名单一并列入报告。"""
    today = datetime.date.today()
    cut = (today - datetime.timedelta(days=HEALTH_DAYS)).isoformat()
    targets = []
    for s in sources_mod.SOURCES:
        if not s.get("enabled") and s.get("adapter") and s["adapter"] != "manual":
            targets.append({"company": s["company"], "adapter": s["adapter"],
                            "src": dict(s), "from": "注册表（记录档）", "verdict": "记录档",
                            "judge_note": (s.get("note") or "")[:120]})
    spec = {"targets": [], "manual": [], "shixiseng_watchlist": []}
    if os.path.exists(RECHECK_SPEC):
        with open(RECHECK_SPEC, encoding="utf-8") as f:
            spec = json.load(f)
    for e in spec.get("targets", []):
        src = {k: v for k, v in e.items()
               if k not in ("company", "verdict", "from", "judge_note", "adapter")}
        targets.append({"company": e["company"], "adapter": e["adapter"], "src": src,
                        "from": e.get("from", "spec"), "verdict": e.get("verdict", ""),
                        "judge_note": e.get("judge_note", "")})

    groups = {}
    for i, t in enumerate(targets):
        groups.setdefault(_host_group({"adapter": t["adapter"], "id": t["company"]}), []).append((i, t))
    results = {}

    def run_group(items):
        out = []
        for i, t in items:
            src = dict(t["src"], company=t["company"], org_type="复测")
            try:
                rows = adapters.ADAPTERS[t["adapter"]](src)
            except Exception as e:
                out.append((i, t, None, f"{type(e).__name__}: {e}"[:120]))
                continue
            out.append((i, t, rows, None))
        return out

    with ThreadPoolExecutor(max_workers=8) as ex:
        for group_out in ex.map(run_group, list(groups.values())):
            for i, t, rows, err in group_out:
                results[i] = (t, rows, err)

    up, keep, zero, fail = [], [], [], []
    for i in range(len(targets)):
        t, rows, err = results[i]
        if err is not None:
            fail.append((t, err))
        elif not rows:
            zero.append(t)
        else:
            n60 = sum(1 for r in rows if r["date"] >= cut)
            latest = max(r["date"] for r in rows)
            (up if n60 else keep).append((t, len(rows), n60, latest))

    print(f"复测模式（{len(targets)} 个探针，判据窗口 近{HEALTH_DAYS}自然日 ≥ {cut}）")
    print(f"  ★ 升格候选 {len(up)}｜维持 {len(keep)}｜零岗位 {len(zero)}｜探针失败 {len(fail)}")
    for t, n, n60, latest in up:
        print(f"  ★ {t['company']}：在招 {n}，近{HEALTH_DAYS}天 {n60}，最新 {latest}"
              f"（{t['from']}｜原判定 {t['verdict']}）")

    out_dir = os.path.join(PROJECT_ROOT, "output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"recheck_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# 复测报告（升格候选清单）\n\n"
                f"- 扫描时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"- 探针数：{len(targets)}（注册表记录档可探针 ＋ spec 自动目标）\n"
                f"- 判据窗口：近 {HEALTH_DAYS} 自然日新增 ≥ 1（{cut} 起）\n"
                f"- 口径：升格候选仅出清单，enabled 需人工签核后修改 sources.py\n\n")
        f.write("## ★ 升格候选\n\n")
        if up:
            for t, n, n60, latest in up:
                f.write(f"- **{t['company']}**（{t['from']}｜原判定 {t['verdict']}）："
                        f"在招 {n}，近{HEALTH_DAYS}天新增 {n60}，最新 {latest}\n"
                        f"  - 探针：{t['adapter']}｜判据原文：{t['judge_note'] or '—'}\n")
        else:
            f.write("- 无\n")
        f.write("\n## 维持（在招但 60 天无新增）\n\n")
        for t, n, n60, latest in keep:
            f.write(f"- {t['company']}（{t['from']}｜原判定 {t['verdict']}）："
                    f"在招 {n}，最新 {latest}｜判据原文：{t['judge_note'] or '—'}\n")
        f.write("\n## 零岗位（接口通但无在招）\n\n")
        f.write("、".join(t["company"] for t in zero) + "\n")
        f.write("\n## 探针失败\n\n")
        for t, err in fail:
            f.write(f"- {t['company']}：{err}\n")
        manual = spec.get("manual") or []
        if manual:
            f.write("\n## 不可自动复测（页面型/无结构化接口，人工判）\n\n")
            for m in manual:
                f.write(f"- {m['company']}（{m.get('verdict', '')}）：{m.get('reason', '')}\n")
        watch = spec.get("shixiseng_watchlist") or []
        if watch:
            f.write("\n## 实习僧侧观察名单（保留观察带实习僧渠道）\n\n"
                    "一键复测（在招数/最新刷新/60 天判活）：\n\n"
                    "```bash\n"
                    "python shixiseng_scan.py --healthcheck --keywords "
                    + ",".join(watch) + "\n"
                    "```\n")
    print(f"报告：{out_path}")


def main():
    global args_days_label
    a = parse_args()

    # 日历：联网校验失败时静默用内置表；跨无表年份则降级注明
    end = norm_date(a.end) if a.end else datetime.date.today()
    if a.start:
        start, degraded = norm_date(a.start), False
        window_label = "自定义区间"
    else:
        workcalendar.attempt_online_refresh([end.year])
        start, _, degraded = workcalendar.working_day_window(end, a.days)
        window_label = f"{a.days} 个工作日"
    note = "内置 2026 年国务院法定节假日表（含调休）"
    if degraded:
        note += "；窗口含官方安排未公布的年份，该段按「仅剔除周末」估算"
    args_days_label = window_label

    srcs = sources_mod.select_sources(a.direction)
    if a.recheck:
        run_recheck()
        return
    if a.healthcheck:
        run_healthcheck(srcs)
        return
    rows, stats, failures = collect(srcs, start, end, a.reuse_cache)
    if a.reuse_cache:
        print(f"缓存复用：{_cache_hits[0]}/{len(srcs)} 家（{CACHE_TTL // 60} 分钟内）")
        if _cache_hits[0]:
            note += f"；{_cache_hits[0]} 家信源复用 {CACHE_TTL // 60} 分钟内缓存"

    if not rows:
        print(f"窗口 {start.isoformat()} ~ {end.isoformat()}（{window_label}）内零新增。")
        return

    out_dir = os.path.join(PROJECT_ROOT, "output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = a.out or os.path.join(
        out_dir, f"radar_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx")
    write_matrix(rows, stats, failures, start, end, note, out_path)

    by_type = {}
    for r in rows:
        by_type[r["org_type"]] = by_type.get(r["org_type"], 0) + 1
    summary = "、".join(f"{t} {n}" for t, n in
                        sorted(by_type.items(), key=lambda kv: sources_mod.ORG_TYPE_ORDER.index(kv[0])))
    print(f"窗口 {start.isoformat()} ~ {end.isoformat()}（{window_label}）新增 {len(rows)} 条：{summary}")
    print(f"Excel：{out_path}")


def run_healthcheck(srcs):
    """信源体检（错误三分）：区分 真零新增 / 解析 0 条（疑似平台改版）/
    HTTP·网络错误 / 接口异常（返回错误码或结构变化，疑似改版或下线）。"""
    import requests as _rq

    today = datetime.date.today()
    cut = (today - datetime.timedelta(days=HEALTH_DAYS)).isoformat()
    print(f"信源体检（活性阈值 {HEALTH_DAYS} 自然日，基准 {today.isoformat()}）")
    n = {"ok": 0, "zero": 0, "parse0": 0, "http": 0, "api": 0}
    for src in srcs:
        try:
            rows = adapters.fetch_source(src)
        except _rq.exceptions.RequestException as e:
            n["http"] += 1
            print(f"  ✗ HTTP·网络错误  {src['company']}：{type(e).__name__}: {e}"[:140])
            continue
        except Exception as e:
            n["api"] += 1
            print(f"  ✗ 接口异常（疑似改版/下线）  {src['company']}：{type(e).__name__}: {e}"[:140])
            continue
        if not rows:
            n["parse0"] += 1
            print(f"  ! 解析 0 条（疑似平台改版）  {src['company']}：接口通但零岗位，"
                  f"对照 sources/ 记录核字段映射")
            continue
        n60 = sum(1 for r in rows if r["date"] >= cut)
        latest = max((r["date"] for r in rows), default="-")
        if n60:
            n["ok"] += 1
            print(f"  ✓ 达标  {src['company']}：在招 {len(rows)}，近{HEALTH_DAYS}天新增 {n60}，最新 {latest}")
        else:
            n["zero"] += 1
            print(f"  ✗ 零新增（真）  {src['company']}：在招 {len(rows)}，最新 {latest}"
                  f"，复测判据见 sources/ 记录")
    print(f"\n合计：达标 {n['ok']}｜零新增（真） {n['zero']}｜解析 0 条（疑似改版） {n['parse0']}"
          f"｜HTTP·网络错误 {n['http']}｜接口异常（疑似改版/下线） {n['api']}")


if __name__ == "__main__":
    main()
