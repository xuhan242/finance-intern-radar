# -*- coding: utf-8 -*-
"""golden fixture 采集：对每类适配通道录一份真实响应样本 + 期望解析结果。

产物 tests/golden/{adapter}__{id}.json 供 run_golden_tests.py 离线回放。
录制响应一律脱敏（红线同样适用于测试资产）：
- JSON 响应：JD 全文 / 联系方式类字段值替换为 "[SAN]"（键名正则匹配，白名单字段不动）；
- Moka：解密 → 脱敏 → 用原密钥重加密后落盘（回放走真实解密路径）；
- HTML 响应：邮箱/手机号替换为 "[SAN]"（列表页本无 JD 正文）；
- citics / cmbchina：录「采集后」state 快照入档，回放时播种到临时目录（首见日期精确复现）。

用法：python tests/golden/_capture.py [adapter ...]   # 缺省全部重录
"""

import base64
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.join(os.path.dirname(os.path.dirname(HERE)), "skill")
GOLDEN = HERE
sys.path.insert(0, SKILL)

import requests  # noqa: E402

import adapters  # noqa: E402
import sources as sources_mod  # noqa: E402

# 每通道代表信源（id 见 sources.py）。beisen_classic 双模板各录一份。
REPS = {
    "beisen": ["cicc"],
    "beisen_classic": ["htffund", "crsec", "zofund"],
    "hotjob": ["gfsec"],
    "hotjob_wt": ["kysec"],
    "moka": ["jsfund"],
    "pingan": ["pingan"],
    "citics": ["citics"],
    "phfund": ["phfund"],
    "cmbc": ["cmbc"],
    "dgzq": ["dgzq"],
    "cmbchina": ["cmbchina"],
    "sufe": ["sufe"],
    "dufe": ["dufe"],
    "ruc_sf": ["ruc_sf"],
    "uibe": ["uibe_aeo"],
    "cuhk": ["cuhk_sz"],
    "jnu": ["jnu_scdc"],
    "zuel": ["zuel_jyzx"],
    "zju": ["zju_career"],
    "swufe": ["swufe"],
}

SAN_KEY = re.compile(
    r"(?i)(duty|requir|qualif|desc|responsib|jobrequire|content|detail"
    r"|wechat|weixin|wxqrcode|jltdyx|modifiedby|email|mail|phone|mobile"
    r"|contact|linkman|联系人|联系方式|简历)")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")


def sanitize_json(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(v, (str, list)) and SAN_KEY.search(str(k)):
                out[k] = "[SAN]"
            else:
                out[k] = sanitize_json(v)
        return out
    if isinstance(obj, list):
        return [sanitize_json(x) for x in obj]
    return obj


def sanitize_text(text):
    text = _EMAIL_RE.sub("[SAN]", text)
    return _PHONE_RE.sub("[SAN]", text)


_DIV_TOK_RE = re.compile(r"<div\b[^>]*>|</div>", re.I)


def scrub_jd_html(html):
    """剔除 JD 正文区块（红线：测试资产同样不落 JD 全文）。
    按 div 深度配对裁剪 <div class="describe"> 整块，替换为 [SAN]。"""
    tag = '<div class="describe">'
    while True:
        i = html.find(tag)
        if i < 0:
            return html
        depth, end = 0, len(html)
        for m in _DIV_TOK_RE.finditer(html, i):
            depth += 1 if m.group(0).lower().startswith("<div") else -1
            if depth == 0:
                end = m.end()
                break
        html = html[:i] + "[SAN]" + html[end:]


def sanitize_resp(text, adapter):
    t = text.lstrip()
    if t.startswith("{") or t.startswith("["):
        try:
            return sanitize_text(json.dumps(sanitize_json(json.loads(text)),
                                            ensure_ascii=False, separators=(",", ":")))
        except ValueError:
            pass
    if adapter == "moka":  # 密文信封：解密脱敏后按原密钥重加密
        env = json.loads(text)
        payload = adapters._moka_decrypt(env)
        import base64

        from Crypto.Cipher import AES

        raw = json.dumps(sanitize_json(payload), ensure_ascii=False).encode("utf-8")
        pad = 16 - len(raw) % 16
        raw += bytes([pad]) * pad
        cipher = AES.new(env["necromancer"].encode("utf-8"), AES.MODE_CBC, adapters._MOKA_IV)
        env["data"] = base64.b64encode(cipher.encrypt(raw)).decode()
        return json.dumps(env, ensure_ascii=False, separators=(",", ":"))
    return sanitize_text(scrub_jd_html(text))


def smart_decode(b, initial_enc):
    """优先严格 UTF-8：中文页面能严格解出即真 UTF-8；否则用录制时的编码
    （requests 对无 charset 头的页会猜错，如 ruc_sf 实为 UTF-8 却记成 latin-1 系）。"""
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode(initial_enc or "utf-8", errors="replace")


class Recorder:
    """替换 adapters.requests：真发请求并按序落档（method/url/params/body/原始字节+编码）。
    存原始字节而非 .text —— ruc_sf 这类「先设 encoding 再读」的适配器才能被回放复现。"""

    def __init__(self):
        self.calls = []

    def get(self, url, headers=None, timeout=None, params=None, **kw):
        r = requests.get(url, headers=headers, timeout=timeout, params=params, **kw)
        r.raise_for_status()
        self.calls.append(self._log("GET", url, params, None, None, r))
        return r

    def post(self, url, headers=None, timeout=None, json=None, data=None, params=None, **kw):
        r = requests.post(url, headers=headers, timeout=timeout, json=json, data=data,
                          params=params, **kw)
        r.raise_for_status()
        self.calls.append(self._log(
            "POST", url, params, json, data if isinstance(data, str) else None, r))
        return r

    @staticmethod
    def _log(method, url, params, body_json, body_str, r):
        return {"method": method, "url": url, "params": params or None,
                "body_json": body_json, "body_str": body_str,
                "status": r.status_code,
                "resp_b64": base64.b64encode(r.content).decode("ascii"),
                "resp_enc": r.encoding or r.apparent_encoding or "utf-8"}


def find_source(sid):
    for s in sources_mod.SOURCES:
        if s.get("id") == sid:  # 记录档（enabled=False）同样可录 fixture
            return s
    raise SystemExit(f"未找到信源 id={sid}")


_RENDER_ADAPTERS = {"uibe": "_uibe_render", "jnu": "_jnu_render"}


def capture_one(adapter, src):
    rec = Recorder()
    real_session = adapters._session
    adapters._session = lambda url: rec
    render_attr = _RENDER_ADAPTERS.get(adapter)
    real_render = getattr(adapters, render_attr) if render_attr else None
    if real_render:
        def wrapped(url, _real=real_render):
            html = _real(url)
            rec.calls.append({"method": "RENDER", "url": url, "params": None,
                              "body_json": None, "body_str": None, "status": 200,
                              "resp_text": html})
            return html
        setattr(adapters, render_attr, wrapped)
    try:
        rows = adapters.ADAPTERS[adapter](src)
    finally:
        adapters._session = real_session
        if real_render:
            setattr(adapters, render_attr, real_render)

    # ID 存档法两源：录「采集后」state 快照 —— 回放播种后首见日期可精确复现
    state = None
    if adapter in ("citics", "cmbchina"):
        attr = "_CITICS_STATE" if adapter == "citics" else "_CMBCHINA_STATE"
        with open(getattr(adapters, attr), encoding="utf-8") as f:
            state = [{"attr": attr, "data": json.load(f)}]

    for c in rec.calls:
        if "resp_b64" in c:  # HTTP 调用：智能解码→脱敏→统一转 UTF-8 存回
            text = smart_decode(base64.b64decode(c["resp_b64"]), c["resp_enc"])
            text = sanitize_resp(text, adapter)
            c["resp_b64"] = base64.b64encode(text.encode("utf-8")).decode("ascii")
            c["resp_enc"] = "utf-8"
        else:  # RENDER（uibe 渲染 DOM，本就是解码后的字符串）
            c["resp_text"] = sanitize_resp(c["resp_text"], adapter)
    fx = {
        "adapter": adapter,
        "source": {k: v for k, v in src.items() if k != "enabled"},
        "state": state,
        "calls": rec.calls,
        "expected": rows,
    }
    path = os.path.join(GOLDEN, f"{adapter}__{src['id']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fx, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  {adapter}__{src['id']}: {len(rec.calls)} calls, {len(rows)} rows, "
          f"{os.path.getsize(path) // 1024} KB")


def main():
    only = set(sys.argv[1:])
    for adapter, ids in REPS.items():
        if only and adapter not in only:
            continue
        for sid in ids:
            capture_one(adapter, find_source(sid))
    print("录制完成。")


if __name__ == "__main__":
    main()
