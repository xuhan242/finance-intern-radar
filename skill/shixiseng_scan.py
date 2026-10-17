# -*- coding: utf-8 -*-
"""实习僧渠道扫描器（与官网雷达并列的融合渠道）。

用法：
    python shixiseng_scan.py                  # 只扫实习僧，输出渠道矩阵 Excel
    python shixiseng_scan.py --merge          # 官网 + 实习僧，融合去重后输出
    python shixiseng_scan.py --merge --days 22
    python shixiseng_scan.py --keywords 风控,固收 --pages 1
    python shixiseng_scan.py --healthcheck    # 关键词体检（活跃/静默/零命中/渲染失败）

口径：
- 实习僧侧取"最新排序 + 近一月（publishTime=mon）"，行日期用首见日期存档法
  （state/shixiseng_seen.json，与中信证券 ID 存档法同构）。
- 融合去重：实习僧公司名经 shixiseng_config 别名表归一到官网标准名后，
  在同公司内做岗位名规范化匹配；命中即合并为一条（主链接官网），
  未命中且属官网 32 家之外的机构作为渠道独有条目输出。
- 浏览器为 headless Chromium 真实渲染，不登录、不触验证码、不逆向接口签名。
"""

import argparse
import asyncio
import datetime
import json
import os
import re
import sys
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import requests
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import radar_scan  # noqa: E402
import shixiseng_config as cfg  # noqa: E402
import sources as sources_mod  # noqa: E402
import workcalendar  # noqa: E402

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state", "shixiseng_seen.json")
SX_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state", "shixiseng_last.json")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

EXTRA_COLS = ["PE/VC", "信托", "其他"]
PAGE_SETTLE_MS = 500  # 卡片选择器已保证内容就绪，固定等待只作站点限速礼貌间隔
KEYWORD_WORKERS = 4  # 关键词并行页面数（每页独立上下文，站点侧仍是低频访问）


def parse_args():
    p = argparse.ArgumentParser(description="实习僧渠道扫描（可融合官网雷达）")
    p.add_argument("--merge", action="store_true", help="同时扫官网全部信源并融合去重")
    p.add_argument("--days", type=int, default=10, help="官网窗口（工作日，默认 10）")
    p.add_argument("--start", help="自然日区间起点 YYYYMMDD（覆盖 --days）")
    p.add_argument("--end", help="自然日区间终点 YYYYMMDD")
    p.add_argument("--keywords", help="逗号分隔关键词（默认机构清单 company_keywords.json）")
    p.add_argument("--directions", action="store_true", help="改用方向词维度（发现清单外机构）")
    p.add_argument("--pages", type=int, help="每关键词翻页数（机构默认 1、方向默认 2）")
    p.add_argument("--healthcheck", action="store_true",
                   help="关键词体检：逐词在招数/最新刷新/60 自然日判活（忽略缓存强制重扫）")
    p.add_argument("--reuse-cache", action="store_true",
                   help="复用上次实习僧采集缓存（仅重跑官网侧与融合）")
    p.add_argument("--out", help="输出 Excel 路径")
    return p.parse_args()


def build_url(keyword, page, latest=True):
    """搜索 URL。latest=True 用最新排序（方向词维度）；机构维度用默认排序（相关性优先，
    避免机构自身岗位被模糊匹配结果挤出首页）。"""
    sort = "&sortType=zj" if latest else ""
    return ("https://www.shixiseng.com/interns?type=intern"
            f"&keyword={urllib.parse.quote(keyword)}"
            f"&publishTime=mon{sort}&city={urllib.parse.quote(cfg.DEFAULT_CITY)}&page={page}")


def company_match(company, kw):
    """搜索结果公司名与搜索词匹配（实习僧为分词模糊匹配，须过滤）。"""
    c = clean_text(company).replace(" ", "")
    k = clean_text(kw).replace(" ", "")
    if not c or not k:
        return False
    if c == k or k in c or c in k:
        return True
    std_c, std_k = cfg.std_company(c), cfg.std_company(k)
    return bool(std_c and std_c == std_k)


async def _crawl(keywords, pages, filter_company, latest):
    """多页面并行采集：每个 worker 一个独立上下文（cookie/限速互不干扰），
    关键词按队列分发；结果按关键词原顺序组装，与逐词串行版逐条一致。"""
    from playwright.async_api import async_playwright

    q = asyncio.Queue()
    for kw in keywords:
        q.put_nowait(kw)
    results = {kw: [] for kw in keywords}
    failures = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        async def worker():
            ctx = await browser.new_context(user_agent=UA, locale="zh-CN")
            await ctx.route("**/*", lambda route: route.abort()
                            if route.request.resource_type in ("image", "media", "font")
                            else route.continue_())
            page = await ctx.new_page()
            try:
                while True:
                    try:
                        kw = q.get_nowait()
                    except asyncio.QueueEmpty:
                        return
                    ok = False
                    for pg in range(1, pages + 1):
                        got = False
                        for _ in range(2):  # 单页失败重试一次
                            try:
                                await page.goto(build_url(kw, pg, latest=latest), timeout=45000)
                                try:
                                    await page.wait_for_selector("div.intern-detail", timeout=25000)
                                except Exception:
                                    pass  # 零卡片：页面已加载，仅无匹配结果
                                got = True
                                break
                            except Exception:
                                await page.wait_for_timeout(1500)
                        if not got:
                            break
                        for c in await page.query_selector_all("div.intern-detail"):
                            job = await c.query_selector(".intern-detail__job a.title")
                            comp = await c.query_selector(".intern-detail__company a.title")
                            city = await c.query_selector(".intern-detail__job .city")
                            sal = await c.query_selector(".intern-detail__job .day")
                            ind = await c.query_selector(".intern-detail__company p.tip span:not(.font)")
                            link = await c.query_selector("a[href*='/intern/inn_']")
                            if not job or not comp or not link:
                                continue
                            company = (await comp.text_content()).strip()
                            if filter_company and not company_match(company, kw):
                                continue
                            results[kw].append({
                                "company": company,
                                "title": (await job.text_content()).strip(),
                                "city": (await city.text_content()).strip() if city else "",
                                "salary": (await sal.text_content()).strip() if sal else "",
                                "industry": (await ind.text_content()).strip() if ind else "",
                                "url": await link.get_attribute("href"),
                                "keyword": kw,
                            })
                        ok = True
                        await page.wait_for_timeout(PAGE_SETTLE_MS)
                    if not ok and kw not in failures:
                        failures.append(kw)
            finally:
                await ctx.close()

        try:
            n = max(1, min(KEYWORD_WORKERS, len(keywords)))
            await asyncio.gather(*[worker() for _ in range(n)])
        finally:
            await browser.close()

    rows = [r for kw in keywords for r in results[kw]]  # 按关键词原顺序组装
    uniq = {r["url"]: r for r in rows}  # 按 URL 去重
    return list(uniq.values()), failures


def fetch_shixiseng(keywords, pages, filter_company=False, latest=True):
    """headless Chromium 逐关键词逐页采集（KEYWORD_WORKERS 个页面并行）。
    返回 (rows, 渲染失败关键词)。

    「页面加载成功但近一月筛下零卡片」不算失败 —— 那是真实零在招
    （体检模式归为零命中）；只有页面本身加载不了才算渲染失败。"""
    if not keywords:
        return [], []
    return asyncio.run(_crawl(keywords, pages, filter_company, latest))


def load_state():
    """读状态：url → {seen: 首见日期, refresh: 详情页刷新时间}（兼容旧的纯日期格式）。"""
    if not os.path.exists(STATE_PATH):
        return {}
    with open(STATE_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    return {k: (v if isinstance(v, dict) else {"seen": v, "refresh": None})
            for k, v in raw.items()}


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)


def parse_refresh_time(html):
    """从详情页 HTML 提取刷新时间（平台上对外显示的时间）。"""
    text = re.sub(r"<[^>]+>", "", html)
    m = re.search(r"(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}:\d{2}\s*刷新", text)
    return m.group(1) if m else None


_TL = threading.local()


def _detail_session():
    s = getattr(_TL, "session", None)
    if s is None:
        s = requests.Session()
        s.headers.update({"User-Agent": UA})
        _TL.session = s
    return s


def fetch_refresh_time(url):
    try:
        r = _detail_session().get(url, timeout=20)
        r.raise_for_status()
        return parse_refresh_time(r.content.decode("utf-8", "ignore"))
    except Exception:
        return None


def apply_dates(rows, fetch_missing=True):
    """岗位日期 = 详情页刷新时间（缺失时匿名直连补采，低频）；兜底用首见日期。
    行日期即平台上点开看到的时间，与用户核对一致。"""
    state = load_state()
    baseline = not state
    today = datetime.date.today().isoformat()
    missing = [r for r in rows if not state.get(r["url"], {}).get("refresh")]
    if fetch_missing and missing:
        print(f"补采详情页时间：{len(missing)} 条 ...")
        with ThreadPoolExecutor(max_workers=4) as ex:
            times = list(ex.map(fetch_refresh_time, [r["url"] for r in missing]))
        ok = 0
        for r, t in zip(missing, times):
            if t:
                state.setdefault(r["url"], {"seen": today, "refresh": None})["refresh"] = t
                ok += 1
        print(f"  成功 {ok}/{len(missing)} 条")
    for r in rows:
        e = state.setdefault(r["url"], {"seen": today, "refresh": None})
        r["date"] = e.get("refresh") or e.get("seen") or today
    save_state(state)
    return rows, baseline


PUA_RE = re.compile(r"[\ue000-\uf8ff\ufffd]")


def clean_text(t):
    """剥离实习僧自定义字体渲染出的私有区字符（不解析字体映射，仅忽略）。"""
    return PUA_RE.sub("", t).strip()


def norm_job(t):
    t = clean_text(t)
    t = re.sub(r"[（(][^）)]*[)）]", "", t)
    t = re.sub(r"^(日常实习|项目实习|暑期实习|寒假实习)[-－—\s]*", "", t)
    t = re.sub(r"(实习生|实习)$", "", t)
    t = re.sub(r"[\s/／·、\-－—]+", "", t)
    return t


def same_job(a, b):
    na, nb = norm_job(a), norm_job(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if len(na) >= 4 and len(nb) >= 4 and (na in nb or nb in na):
        return True
    from difflib import SequenceMatcher
    return SequenceMatcher(None, na, nb).ratio() >= 0.85


def merge(radar_rows, sx_rows):
    """岗位级融合去重。返回 (输出行, 双源清单, 实习僧独有条数)。"""
    out = list(radar_rows)
    by_company = {}
    for r in radar_rows:
        by_company.setdefault(r["company"], []).append(r)
    dual, sx_only = [], 0
    for s in sx_rows:
        std = cfg.std_company(clean_text(s["company"]))
        hit = None
        if std:
            for r in by_company.get(std, []):
                if same_job(s["title"], r["title"]):
                    hit = r
                    break
        if hit:
            hit["sx_url"] = s["url"]  # 双源标记，主链接仍为官网
            hit["sx_city"] = s["city"]  # 官网城市为空时（如 Moka）用实习僧城市补充
            for d in dual:
                if d["radar_url"] == hit["url"]:
                    d["sx_urls"].append(s["url"])
                    break
            else:
                dual.append({"company": hit["company"], "title": hit["title"],
                             "radar_url": hit["url"], "sx_urls": [s["url"]],
                             "city": s["city"], "salary": s["salary"]})
        else:
            org_type = (by_company[std][0]["org_type"] if std and by_company.get(std)
                        else cfg.infer_org_type(s["company"]))
            out.append({
                "company": clean_text(s["company"]), "entity": "", "title": clean_text(s["title"]),
                "post_no": s["url"], "date": s["date"],
                "url": s["url"], "org_type": org_type,
                "city": s["city"], "keyword": s["keyword"], "sx_only": True,
            })
            sx_only += 1
    return out, dual, sx_only


def plain_label(r):
    """纯名称（清单页「条目」列用）。"""
    if r.get("sx_only"):
        return f"{r['company']} - {r['title']}"
    return radar_scan.display_label(r)


def city_of(r):
    return radar_scan.clean_city(r.get("cities") or r.get("sx_city") or r.get("city") or "")


def label_of(r):
    """矩阵格内条目（含 Base 地后缀）。"""
    city = city_of(r)
    if r.get("sx_only"):
        tag = "·".join(x for x in [city, "实习僧"] if x)
        return f"{r['company']} - {r['title']}（{tag}）" if tag else f"{r['company']} - {r['title']}"
    return radar_scan.display_label(r) + (f"（{city}）" if city else "")


def write_output(rows, dual, sx_only, failures, start, end, window_label,
                 calendar_note, baseline, out_path, merge_mode, sx_total):
    wb = Workbook()
    ws = wb.active
    ws.title = "岗位矩阵"
    org_types = [t for t in sources_mod.ORG_TYPE_ORDER + EXTRA_COLS
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
    # 日期列纵向合并；同一类型岗位多于其他类型时，多出的层单列占行。
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
                    c = ws.cell(row=row_i, column=org_types.index(t) + 2, value=label_of(items[k]))
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
    ws3.append(["日期", "机构类型", "岗位", "Base地", "来源", "链接"])
    for c in ws3[1]:
        c.font = header_font
        c.fill = header_fill
    widths = {"A": 12, "B": 10, "C": 60, "D": 12, "E": 14, "F": 110}
    for k, v in widths.items():
        ws3.column_dimensions[k].width = v
    link_font = Font(color="0563C1", underline="single")
    for r in sorted(rows, key=lambda x: (x["date"], x["org_type"]), reverse=True):
        src = "官网" if not r.get("sx_only") else "实习僧"
        if r.get("sx_url"):
            src = "官网+实习僧"
        ws3.append([datetime.date.fromisoformat(r["date"]), r["org_type"],
                    plain_label(r), city_of(r), src, r["url"]])
        cell = ws3.cell(row=ws3.max_row, column=6)
        cell.hyperlink = r["url"]
        cell.font = link_font
        ws3.cell(row=ws3.max_row, column=3).alignment = Alignment(wrap_text=True, vertical="center")

    ws2 = wb.create_sheet("扫描说明")
    ws2.column_dimensions["A"].width = 24
    ws2.column_dimensions["B"].width = 100
    info = [
        ("扫描时间", datetime.datetime.now().strftime("%Y-%m-%d %H:%M")),
        ("渠道", "官网雷达 + 实习僧融合去重" if merge_mode else "实习僧渠道"),
        ("官网窗口" if merge_mode else "实习僧窗口",
         f"{start.isoformat()} 至 {end.isoformat()}（{window_label}）"),
        ("实习僧口径", "行日期 = 详情页刷新时间（平台显示时间，与点开详情一致）；"
         "采集窗口 = 近一月刷新（publishTime=mon）"),
        ("工作日历", calendar_note),
        ("岗位总数", str(len(rows))),
        ("其中：实习僧独有", str(sx_only)),
        ("其中：官网/实习僧双源", str(len(dual))),
        ("实习僧采集条数", str(sx_total)),
    ]
    for k, v in info:
        ws2.append([k, v])
    if dual:
        ws2.append([])
        ws2.append(["双源岗位（官网链接 | 实习僧链接）", ""])
        for d in dual:
            extra = f"（{d['city']}{'·' + d['salary'] if d.get('salary') else ''}）"
            ws2.append([f"{d['company']} - {d['title']}{extra}",
                        d["radar_url"] + " | " + " | ".join(d["sx_urls"])])
    if failures:
        ws2.append([])
        ws2.append(["实习僧渲染失败关键词", "、".join(failures)])
    wb.move_sheet(ws3, offset=-1)  # 页签顺序：岗位清单优先展示
    wb.save(out_path)


def run_kw_healthcheck(rows, sx_fail, keywords):
    """关键词体检：活跃 / 静默（超 60 天无刷新）/ 零命中（真实零在招或词失效）/
    渲染失败（页面加载不了）四分，静默与零命中逐词列明。

    零命中先复探一轮再定论——97 词连搜存在瞬时抽风（同词复跑可恢复），
    单轮零命中不可直接判死。"""
    today = datetime.date.today()
    cut = (today - datetime.timedelta(days=radar_scan.HEALTH_DAYS)).isoformat()
    by_kw = {}
    for r in rows:
        by_kw.setdefault(r["keyword"], []).append(r)
    zero = [kw for kw in keywords if not by_kw.get(kw)]
    recovered = []
    if zero:
        print(f"  … 零命中 {len(zero)} 词，复探一轮 …")
        re_rows, _ = fetch_shixiseng(zero, 1, filter_company=True, latest=False)
        re_by = {}
        for r in re_rows:
            re_by.setdefault(r["keyword"], []).append(r)
        recovered = [kw for kw in zero if re_by.get(kw)]
        zero = [kw for kw in zero if not re_by.get(kw)]
    active, silent = [], []
    for kw in keywords:
        rs = by_kw.get(kw)
        if not rs:
            continue
        latest = max(r["date"] for r in rs)
        (active if latest >= cut else silent).append((kw, len(rs), latest))
    n_active = len(active) + len(recovered)
    print(f"实习僧关键词体检（{len(keywords)} 词，活性阈值 {radar_scan.HEALTH_DAYS} 自然日，"
          f"基准 {today.isoformat()}）")
    print(f"  ✓ 活跃 {n_active} 词（近{radar_scan.HEALTH_DAYS}天有刷新）")
    if recovered:
        print(f"  ✓ 其中复探恢复 {len(recovered)} 词（首轮零命中、复跑有卡，瞬时抽风类）：")
        print("      " + "、".join(recovered))
    if silent:
        print(f"  ✗ 静默（超{radar_scan.HEALTH_DAYS}天无刷新）{len(silent)} 词：")
        for kw, n, latest in sorted(silent, key=lambda x: x[2]):
            print(f"      {kw}：在招 {n}，最新刷新 {latest}")
    if zero:
        print(f"  ! 零命中 {len(zero)} 词（近一月筛下无在招贴，真实零在招或词失效；"
              f"搜索页模糊卡片经公司名过滤后归零）：")
        print("      " + "、".join(zero))
    if sx_fail:
        print(f"  ✗ 渲染失败 {len(sx_fail)} 词（页面加载不了，网络或站点侧问题）：")
        print("      " + "、".join(sx_fail))
    if len(zero) > len(keywords) * 0.3:
        print("  ⚠ 大面积零命中：疑似页面改版或验证码墙，复探确认后再定论")


_SCOUT_SKIP = {"实习僧内推助手"}  # 代发账号，公司名未落主体，不作候选


def write_scout_report(rows):
    """方向词反哺：清单外高频机构候选报告（只进待审，不自动加词）。

    与 company_keywords.json 逐词匹配（含包含关系，如「国泰君安期货」⊂「国泰君安」）
    判定清单内；其余按卡片数排序输出，类型推断供人工筛。"""
    kws = cfg.load_company_keywords()
    names = {}
    for r in rows:
        c = clean_text(r["company"])
        if c:
            names.setdefault(c, {"n": 0, "latest": ""})
            names[c]["n"] += 1
            names[c]["latest"] = max(names[c]["latest"], r.get("date", ""))
    known = {c for c in names if any(company_match(c, kw) for kw in kws)}
    cand = {c: d for c, d in names.items()
            if c not in known and c not in _SCOUT_SKIP}
    ranked = sorted(cand.items(), key=lambda kv: (-kv[1]["n"], kv[1]["latest"]))
    today = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    out_path = os.path.join(PROJECT_ROOT, "output", f"directions_scout_{today}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# 方向词反哺：清单外高频机构候选（待审，不自动加词）\n\n"
                f"- 扫描时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"- 方向词清单：{'、'.join(cfg.DEFAULT_DIRECTIONS)}\n"
                f"- 采集卡片：{sum(d['n'] for d in names.values())}；清单内机构 {len(known)}；"
                f"清单外候选 {len(ranked)}\n\n"
                "| 机构 | 卡片数 | 最近刷新 | 类型推断 |\n|---|---|---|---|\n")
        for c, d in ranked:
            f.write(f"| {c} | {d['n']} | {d['latest'] or '—'} | {cfg.infer_org_type(c)} |\n")
        f.write("\n加词须经人工签核后改 skill/company_keywords.json（清单=签核资产口径）。\n")
    print("清单外高频机构候选（top10，按卡片数）：")
    for c, d in ranked[:10]:
        print(f"  {c}：{d['n']} 卡，最新 {d['latest'] or '—'}，{cfg.infer_org_type(c)}")
    print(f"候选报告：{out_path}")


def main():
    a = parse_args()
    end = radar_scan.norm_date(a.end) if a.end else datetime.date.today()
    if a.start:
        start, degraded = radar_scan.norm_date(a.start), False
        window_label = "自定义区间"
    else:
        workcalendar.attempt_online_refresh([end.year])
        start, _, degraded = workcalendar.working_day_window(end, a.days)
        window_label = f"{a.days} 个工作日"
    note = "内置 2026 年国务院法定节假日表（含调休）"
    if degraded:
        note += "；窗口含官方安排未公布的年份，该段按「仅剔除周末」估算"

    if a.keywords:
        keywords, pages, filter_company, latest, mode = a.keywords.split(","), a.pages or cfg.COMPANY_PAGES, True, False, "自定义"
    elif a.directions:
        keywords, pages, filter_company, latest, mode = cfg.DEFAULT_DIRECTIONS, a.pages or cfg.DIRECTION_PAGES, False, True, "方向词"
    else:
        keywords, pages, filter_company, latest, mode = cfg.load_company_keywords(), a.pages or cfg.COMPANY_PAGES, True, False, "机构清单"
    if not keywords and not (a.reuse_cache and os.path.exists(SX_CACHE)):
        print("机构清单为空（skill/company_keywords.json 不存在），请用 --keywords 或 --directions。")
        return
    radar_pool = radar_fut = None
    if a.merge and not a.healthcheck:
        radar_pool = ThreadPoolExecutor(max_workers=1)
        radar_fut = radar_pool.submit(radar_scan.collect, sources_mod.select_sources("all"),
                                      start, end)
    if a.reuse_cache and not a.healthcheck and os.path.exists(SX_CACHE):
        with open(SX_CACHE, encoding="utf-8") as f:
            sx_rows, sx_fail = json.load(f), []
        print(f"实习僧缓存复用：{len(sx_rows)} 条")
    else:
        print(f"实习僧采集[{mode}]：{len(keywords)} 个关键词 × {pages} 页 ...")
        sx_rows, sx_fail = fetch_shixiseng(keywords, pages, filter_company=filter_company, latest=latest)
        with open(SX_CACHE, "w", encoding="utf-8") as f:
            json.dump(sx_rows, f, ensure_ascii=False)
    sx_rows, baseline = apply_dates(sx_rows)
    if a.healthcheck:
        run_kw_healthcheck(sx_rows, sx_fail, keywords)
        return
    if mode == "方向词":
        write_scout_report(sx_rows)
    if not baseline:
        sx_rows = [r for r in sx_rows if r["date"] >= start.isoformat()]
    print(f"实习僧近一月采集 {len(sx_rows)} 条"
          + (f"（渲染失败关键词：{'、'.join(sx_fail)}）" if sx_fail else ""))

    if a.merge:
        radar_rows, stats, failures = radar_fut.result()
        radar_pool.shutdown()
        rows, dual, sx_only = merge(radar_rows, sx_rows)
    else:
        rows = [{
            "company": clean_text(s["company"]), "entity": "", "title": clean_text(s["title"]),
            "post_no": s["url"], "date": s["date"], "url": s["url"],
            "org_type": cfg.infer_org_type(s["company"]),
            "city": s["city"], "keyword": s["keyword"], "sx_only": True,
        } for s in sx_rows]
        dual, sx_only = [], len(rows)

    if not rows:
        print(f"窗口 {start.isoformat()} ~ {end.isoformat()}（{window_label}）内零新增。")
        return

    out_dir = os.path.join(PROJECT_ROOT, "output")
    os.makedirs(out_dir, exist_ok=True)
    tag = "merged" if a.merge else "shixiseng"
    out_path = a.out or os.path.join(
        out_dir, f"{tag}_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx")
    write_output(rows, dual, sx_only, sx_fail, start, end, window_label, note,
                 baseline, out_path, a.merge, len(sx_rows))

    by_type = {}
    for r in rows:
        by_type[r["org_type"]] = by_type.get(r["org_type"], 0) + 1
    order = sources_mod.ORG_TYPE_ORDER + EXTRA_COLS
    summary = "、".join(f"{t} {n}" for t, n in sorted(by_type.items(), key=lambda kv: order.index(kv[0])))
    print(f"条目 {len(rows)} 条（实习僧独有 {sx_only}、双源 {len(dual)}）：{summary}")
    print(f"Excel：{out_path}")


if __name__ == "__main__":
    main()
