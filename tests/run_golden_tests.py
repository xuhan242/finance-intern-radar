# -*- coding: utf-8 -*-
"""golden 回放：离线重放各通道录制的真实响应，断言解析结果与录制时逐条一致。

覆盖三类回归：
① 请求形态漂移 —— URL/查询参数/请求体与录制不符，或多发了请求 → 报错；
② 字段映射漂移 —— 解析行与录制期望不一致（条数/字段值/顺序）→ 报错；
③ 行结构漂移 —— 输出行缺 schema 字段，或行值中出现邮箱/手机号（红线）→ 报错。

citics / cmbchina 的 ID 存档种到临时目录，不动真实 state。
用法：python tests/run_golden_tests.py [adapter ...]   # 缺省全部
"""

import base64
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.join(os.path.dirname(HERE), "skill")
sys.path.insert(0, SKILL)

import requests  # noqa: E402

import adapters  # noqa: E402

GOLDEN = os.path.join(HERE, "golden")
_ROW_KEYS = {"company", "entity", "title", "cities", "date", "kind", "url", "post_no"}
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class FakeResp:
    """模拟 requests.Response：原始字节 + 可改写的 encoding 驱动 .text 解码。"""

    def __init__(self, b64, enc, status):
        self._content = base64.b64decode(b64)
        self.encoding = enc
        self.status_code = status

    @property
    def text(self):
        return self._content.decode(self.encoding or "utf-8", errors="replace")

    def json(self):
        return json.loads(self.text)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeRequests:
    """替换 adapters.requests：按录制顺序回放，请求形态对不上立即报错。"""

    def __init__(self, calls):
        self.q = list(calls)
        self.i = 0

    def _next(self, method, url, params, body_json, body_str):
        if self.i >= len(self.q):
            raise AssertionError(
                f"请求形态漂移：适配器第 {self.i + 1} 个请求超出录制序列（多翻了页？）")
        c = self.q[self.i]
        self.i += 1
        problems = []
        if c["method"] != method:
            problems.append(f"method {c['method']}→{method}")
        if c["url"] != url:
            problems.append(f"url {c['url']}→{url}")
        if (c.get("params") or None) != (params or None):
            problems.append(f"params {c.get('params')}→{params}")
        if c.get("body_json") != body_json:
            problems.append(f"body_json {c.get('body_json')}→{body_json}")
        if (c.get("body_str") or None) != (body_str or None):
            problems.append(f"body_str {c.get('body_str')}→{body_str}")
        if problems:
            raise AssertionError("请求形态漂移：" + "；".join(problems))
        return FakeResp(c["resp_b64"], c.get("resp_enc", "utf-8"), c.get("status", 200))

    def get(self, url, headers=None, timeout=None, params=None, **kw):
        return self._next("GET", url, params, None, None)

    def post(self, url, headers=None, timeout=None, json=None, data=None, params=None, **kw):
        return self._next("POST", url, params, json,
                          data if isinstance(data, str) else None)


_RENDER_ADAPTERS = {"uibe": "_uibe_render", "jnu": "_jnu_render"}


def run_fixture(path):
    with open(path, encoding="utf-8") as f:
        fx = json.load(f)
    src, adapter = fx["source"], fx["adapter"]
    tmp = tempfile.mkdtemp(prefix="radar_golden_")
    fake = FakeRequests(fx["calls"])
    saved = {"_session": adapters._session}
    try:
        adapters._session = lambda url: fake
        for st in fx.get("state") or []:
            p = os.path.join(tmp, os.path.basename(st["attr"]) + ".json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(st["data"], f, ensure_ascii=False)
            saved[st["attr"]] = getattr(adapters, st["attr"])
            setattr(adapters, st["attr"], p)
        render_attr = _RENDER_ADAPTERS.get(adapter)
        if render_attr:  # 渲染类：按录制序列重放（URL 漂移即报错）
            it = iter(c for c in fx["calls"] if c["method"] == "RENDER")

            def fake_render(url, _it=it):
                c = next(_it)
                if c["url"] != url:
                    raise AssertionError(f"渲染 URL 漂移：录制 {c['url']} → 实得 {url}")
                return c["resp_text"]
            saved[render_attr] = getattr(adapters, render_attr)
            setattr(adapters, render_attr, fake_render)
        rows = adapters.ADAPTERS[adapter](src)
    finally:
        for k, v in saved.items():
            setattr(adapters, k, v)

    name = os.path.basename(path)
    if rows != fx["expected"]:
        got_n, want_n = len(rows), len(fx["expected"])
        detail = ""
        for i, (g, w) in enumerate(zip(rows, fx["expected"])):
            if g != w:
                detail = f"；首个差异行 #{i}：期望 {w}，实得 {g}"
                break
        if not detail and got_n != want_n:
            detail = f"；首行：期望 {fx['expected'][0] if want_n else '∅'}，实得 {rows[0] if got_n else '∅'}"
        raise AssertionError(f"{name} 字段映射漂移：条数 {got_n}≠{want_n}{detail}")
    for i, r in enumerate(rows):
        if not _ROW_KEYS <= set(r):
            raise AssertionError(f"{name} 行 #{i} 缺 schema 字段：{sorted(_ROW_KEYS - set(r))}")
        if not _DATE_RE.match(r["date"]):
            raise AssertionError(f"{name} 行 #{i} 日期格式异常：{r['date']!r}")
        for v in r.values():
            if isinstance(v, str) and (_EMAIL_RE.search(v) or _PHONE_RE.search(v)):
                raise AssertionError(f"{name} 行 #{i} 出现联系方式（红线）：{v[:50]}")
    return len(rows)


def main():
    only = set(sys.argv[1:])
    files = sorted(f for f in os.listdir(GOLDEN) if f.endswith(".json"))
    if only:
        files = [f for f in files if f.split("__")[0] in only]
    if not files:
        raise SystemExit("tests/golden/ 下没有 fixture，先跑 _capture.py")
    total = 0
    for fn in files:
        total += run_fixture(os.path.join(GOLDEN, fn))
        print(f"[PASS] {fn}")
    print(f"\n结论：{len(files)} 个通道 fixture 全部通过，共 {total} 行")


if __name__ == "__main__":
    main()
