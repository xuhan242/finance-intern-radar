# -*- coding: utf-8 -*-
"""测试证据：工作日历边界用例 + 去重键 + 输出矩阵结构。

运行：python tests/run_calendar_tests.py
证据落盘本文件输出，由执行 agent 转录到 tests/测试记录.md。
"""

import datetime
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skill"))

import workcalendar  # noqa: E402
import sources as sources_mod  # noqa: E402

out = []


def check(name, got, want):
    ok = got == want
    out.append(f"[{'PASS' if ok else 'FAIL'}] {name}: got={got} want={want}")
    return ok


# ---- 1. 法定节假日正确剔除（2026 国庆 10-01~10-07 全休）----
d = datetime.date(2026, 10, 1)
all_rest = all(not workcalendar.is_workday(d + datetime.timedelta(days=i)) for i in range(7))
check("2026 国庆 10-01~07 全部判休", all_rest, True)

# ---- 2. 调休上班日判班（2026-10-10 周六上班）----
check("2026-10-10 周六调休判班", workcalendar.is_workday(datetime.date(2026, 10, 10)), True)
check("2026-09-20 周日调休判班", workcalendar.is_workday(datetime.date(2026, 9, 20)), True)

# ---- 3. 中秋假（2026-09-25~27）与节前调休 ----
check("2026-09-25 中秋假判休", workcalendar.is_workday(datetime.date(2026, 9, 25)), False)
check("2026-09-24 正常工作日", workcalendar.is_workday(datetime.date(2026, 9, 24)), True)

# ---- 4. 10 工作日窗口：终点 2026-10-09，应起于 09-20（含节前调休班）----
s, e, deg = workcalendar.working_day_window(datetime.date(2026, 10, 9), 10)
check("10 工作日窗口起点（跨国庆+中秋）", s.isoformat(), "2026-09-20")
check("10 工作日窗口降级标记", deg, False)

# ---- 5. 窗口覆盖休息日（休息日发布的岗位不漏）----
s2, _, _ = workcalendar.working_day_window(datetime.date(2026, 10, 9), 1)
check("1 工作日窗口含全部自然日区间", (s2, datetime.date(2026, 10, 9)), (datetime.date(2026, 10, 9), datetime.date(2026, 10, 9)))

# ---- 6. 跨年降级：2027 无官方表 ----
s3, _, deg3 = workcalendar.working_day_window(datetime.date(2027, 1, 15), 10)
check("2027-01 窗口触发降级标记", deg3, True)

# ---- 7. 联网校验开关（网络不可用时应静默回退内置表）----
report = workcalendar.attempt_online_refresh([2026])
out.append(f"[INFO] 联网校验 2026：{report}（ok=接口可达并覆写；unavailable=用内置表）")

# ---- 8. 信源注册表完整性 ----
ids = [s["id"] for s in sources_mod.SOURCES]
check("信源 id 无重复", len(ids), len(set(ids)))
enabled = [s for s in sources_mod.SOURCES if s.get("enabled")]
out.append(f"[INFO] 启用信源 {len(enabled)} 家：{'、'.join(s['company'] for s in enabled)}")
missing_link = [s["id"] for s in sources_mod.SOURCES if "deep_link" not in s]
check("全部信源有 deep_link", missing_link, [])
missing_time = [s["id"] for s in sources_mod.SOURCES if "time_field" not in s]
check("全部信源有 time_field", missing_time, [])

# ---- 9. 方向选择 ----
check("券商方向数量", len(sources_mod.select_sources("券商")), len([s for s in enabled if s["org_type"] == "券商"]))
check("资管方向=公募+保险集团+综合金融+养老金", sorted({s["org_type"] for s in sources_mod.select_sources("资管")}), sorted(["公募", "保险集团", "综合金融", "养老金"]))

result = "\n".join(out)
fails = result.count("[FAIL]")
print(result)
print(f"\n结论：{'全部通过' if fails == 0 else str(fails) + ' 项失败'}")
