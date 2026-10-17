# -*- coding: utf-8 -*-
"""中国法定节假日工作日历。

内置表来源：国务院办公厅 2025-11 发布的 2026 年部分节假日安排通知
（经 timor.tech 节假日接口 2026-10-08 交叉核对，逐日一致）。
2027 年官方安排尚未公布（2026-10-08 查证），该年降级为"仅剔除周末"并在输出中注明。

联网校验：attempt_online_refresh() 调用 timor.tech 接口核对内置表，
成功则用接口数据覆写当年表；失败则静默使用内置表。
"""

import datetime
import json

# 休 = 法定休假日（含调休连休）；班 = 周末调休上班日
BUILTIN = {
    2026: {
        "rest": {
            1: {1, 2, 3},
            2: {15, 16, 17, 18, 19, 20, 21, 22, 23},
            4: {4, 5, 6},
            5: {1, 2, 3, 4, 5},
            6: {19, 20, 21},
            9: {25, 26, 27},
            10: {1, 2, 3, 4, 5, 6, 7},
        },
        "work": {
            1: {4},
            2: {14, 28},
            5: {9},
            9: {20},
            10: {10},
        },
    },
    # 2025 年表用于跨年窗口回溯
    2025: {
        "rest": {
            1: {1, 28, 29, 30, 31},
            2: {1, 2, 3, 4},
            4: {4, 5, 6},
            5: {1, 2, 3, 4, 5, 31},
            6: {1, 2},
            10: {1, 2, 3, 4, 5, 6, 7, 8},
        },
        "work": {
            1: {26},
            2: {8},
            4: {27},
            9: {28},
            10: {11},
        },
    },
}

ONLINE_URL = "https://timor.tech/api/holiday/year/{year}/"
ONLINE_TIMEOUT = 8


def is_workday(d):
    """d: date。判断是否工作日（含调休）。该年无内置表时仅剔除周末。"""
    tbl = BUILTIN.get(d.year)
    if d.weekday() >= 5:
        return bool(tbl and d.day in tbl.get("work", {}).get(d.month, set()))
    if tbl and d.day in tbl.get("rest", {}).get(d.month, set()):
        return False
    return True


def working_day_window(end_date, n_days):
    """返回 (start_date, end_date, degraded)。

    窗口定义为"往前第 N 个工作日"到 end_date 的整个自然日区间，
    区间内的休息日发布的岗位不会漏。degraded 表示区间跨入了无内置表的年份。
    """
    degraded = False
    d = end_date
    count = 0
    start = end_date
    while count < n_days:
        if is_workday(d):
            count += 1
            if d.year not in BUILTIN:
                degraded = True
            start = d
        if count >= n_days:
            break
        d -= datetime.timedelta(days=1)
    # 若自然区间内存在无表年份，同样标记降级
    for y in range(start.year, end_date.year + 1):
        if y not in BUILTIN:
            degraded = True
    return start, end_date, degraded


def attempt_online_refresh(years):
    """联网核对内置表。返回 dict: year -> "ok"|"mismatch:fixed"|"unavailable"|"no-data"。

    仅在成功取得接口数据时覆写内存中的 BUILTIN，不写回源文件。
    """
    import urllib.request

    report = {}
    for y in years:
        try:
            req = urllib.request.Request(
                ONLINE_URL.format(year=y),
                headers={"User-Agent": "Mozilla/5.0 (finance-intern-radar)"},
            )
            with urllib.request.urlopen(req, timeout=ONLINE_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            holiday = data.get("holiday") or {}
            if not holiday:
                report[y] = "no-data"
                continue
            rest, work = {}, {}
            for k, v in holiday.items():
                try:
                    mm, dd = k.split("-")
                    m, d = int(mm), int(dd)
                except (ValueError, AttributeError):
                    continue
                if v.get("holiday") is True:
                    rest.setdefault(m, set()).add(d)
                elif v.get("holiday") is False:
                    work.setdefault(m, set()).add(d)
            BUILTIN[y] = {"rest": rest, "work": work}
            report[y] = "ok"
        except Exception:
            report[y] = "unavailable"
    return report
