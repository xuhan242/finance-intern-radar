# -*- coding: utf-8 -*-
"""信源适配器：北森（新版 API / 经典版 SSR） / hotjob / Moka / 平安自建站 / 鹏华自建站。

统一输出行结构（仅含红线允许的字段，不含 JD 全文与任何联系人信息）：
    {
        "company":  公司名,
        "entity":   招聘主体/部门（可空）,
        "title":    岗位名（保留职位号，去重用）,
        "cities":   城市串（可空）,
        "date":     ISO 日期串（时间基准字段，取日期部分）,
        "kind":     岗位性质（实习/全职，可空）,
        "url":      官网深链,
        "post_no":  稳定职位号（去重键；取不到时回退 url）,
    }

合规约束（见 合规依据.md）：
- 仅调用门户自身调用的公开接口，不携带任何绕过措施；
- 不落盘接口返回中的 Duty/Require/duty/qualification（JD 全文）与
  WorkWeChatQrCode（企业微信二维码）等字段，解析后即弃。
"""

import json
import os
import re
import threading
from urllib.parse import quote, urlencode, urlsplit

import requests
from requests.adapters import HTTPAdapter

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) finance-intern-radar"}
TIMEOUT = 20
JOB_NO_RE = re.compile(r"\(([Jj]\d+|[A-Za-z]?\d{3,})\)\s*$")

_TL = threading.local()


def _session(url):
    """按宿主复用连接（每线程独立，避免 Session 跨线程共享）。"""
    host = urlsplit(url).netloc
    pool = getattr(_TL, "pool", None)
    if pool is None:
        pool = _TL.pool = {}
    s = pool.get(host)
    if s is None:
        s = requests.Session()
        s.headers.update(UA)
        s.mount("https://", HTTPAdapter(pool_maxsize=8))
        s.mount("http://", HTTPAdapter(pool_maxsize=8))
        pool[host] = s
    return s


def _get(url, **kw):
    timeout = kw.pop("timeout", TIMEOUT)
    r = _session(url).get(url, headers={**UA, **kw.pop("headers", {})}, timeout=timeout, **kw)
    r.raise_for_status()
    return r


def _post(url, **kw):
    timeout = kw.pop("timeout", TIMEOUT)
    r = _session(url).post(url, headers={**UA, **kw.pop("headers", {})}, timeout=timeout, **kw)
    r.raise_for_status()
    return r


# ---------------- 北森 ----------------

def _beisen_post(base, body):
    r = _post(
        f"{base}/api/Jobad/GetJobAdPageList",
        json=body,
        headers={"Origin": base, "Referer": f"{base}/jobs"},
    )
    try:
        j = r.json()
    except ValueError:
        raise RuntimeError(f"接口返回非 JSON（HTTP {r.status_code}，门户疑已迁移或下线）") from None
    if not isinstance(j, dict):
        return []
    data = j.get("Data")
    return data if isinstance(data, list) else []


def fetch_beisen(src):
    base = src.get("base") or f"https://{src['slug']}.zhiye.com"
    display = ["Category", "Kind", "LocId", "PostDate", "Salary", "Org"]
    rows, page = [], 0
    while page < 12:  # 安全上限：12 页 × 100 条
        body = {
            "PageIndex": page, "PageSize": 100, "LocId": [],
            "Category": list(src["categories"]), "KeyWords": "",
            "SpecialType": 0, "PortalId": "", "DisplayFields": display,
        }
        items = _beisen_post(base, body)
        if not items:
            break
        for it in items:
            title = it.get("JobAdName") or ""
            kind = it.get("Kind") or ""
            if src.get("intern_filter") == "kind_or_title":
                if "实习" not in kind and "实习" not in title:
                    continue
            date = (it.get("PostDate") or "")[:10]
            if not date:
                continue
            m = JOB_NO_RE.search(title)
            rows.append({
                "company": src["company"],
                "entity": it.get("Org") or "",
                "title": title,
                "cities": "、".join(it.get("LocNames") or []),
                "date": date,
                "kind": kind,
                "url": src["deep_link"].format(Id=it.get("Id", "")) if "{Id}" in src["deep_link"] else src["deep_link"],
                "post_no": m.group(1) if m else title,
            })
        if len(items) < 100:
            break
        page += 1
    return rows


# ---------------- hotjob（大易）----------------

def fetch_hotjob(src):
    su = src["su"]
    url = f"https://wecruit.hotjob.cn/wecruit/positionInfo/listPosition/{su}"
    params = {"iSaJAx": "isAjax", "request_locale": "zh_CN"}
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://wecruit.hotjob.cn",
        "Referer": f"https://wecruit.hotjob.cn/{su}/pb/interns.html",
    }
    host = "wecruit.hotjob.cn"
    if "hotjob.cn" in src["deep_link"] and not src["deep_link"].startswith("https://wecruit"):
        host = src["deep_link"].split("/")[2]
        url = f"https://{host}/wecruit/positionInfo/listPosition/{su}"
        headers["Origin"] = f"https://{host}"
        headers["Referer"] = f"https://{host}/{su}/pb/interns.html"
    rows, page, total_pos = [], 1, None
    while page < 30:  # 安全上限：30 页 × 15 条
        r = _post(url, data=f"isFrompb=true&recruitType={src['recruit_type']}&pageSize=15&currentPage={page}", headers=headers, params=params)
        j = r.json()
        data0 = j.get("data") or {}
        if total_pos is None:
            total_pos = data0.get("positonNum") or 0  # 租户全量总数，驱动翻页
        items = (data0.get("pageForm") or {}).get("pageData") or []
        if not items:
            break
        for it in items:
            date = (it.get("publishFirstDate") or it.get("publishDate") or "")[:10]
            if not date:
                continue
            rows.append({
                "company": src["company"],
                "entity": it.get("company") or "",
                "title": it.get("postName") or "",
                "cities": it.get("workPlaceStr") or "",
                "date": date,
                "kind": it.get("workTypeStr") or "",
                "url": (src["deep_link"].format(postId=it.get("postId", ""),
                                                postKey=quote(it.get("postName") or ""))
                        if "{" in src["deep_link"] else src["deep_link"]),
                "post_no": it.get("postCode") or it.get("postId") or it.get("postName") or "",
            })
        if (total_pos and len(rows) >= total_pos) or len(items) == 0:
            break
        page += 1
    return rows


# ---------------- Moka ----------------

_MOKA_IV = b"de7c21ed8d6f50fe"


def _moka_decrypt(payload):
    import base64

    from Crypto.Cipher import AES  # pycryptodome

    raw = base64.b64decode(payload["data"])
    key = payload["necromancer"].encode("utf-8")
    cipher = AES.new(key, AES.MODE_CBC, _MOKA_IV)
    data = cipher.decrypt(raw)
    pad = data[-1]
    return json_loads(data[:-pad])


def json_loads(b):
    import json

    if isinstance(b, bytes):
        b = b.decode("utf-8", errors="replace")
    return json.loads(b)


def fetch_moka(src):
    url = "https://app.mokahr.com/api/outer/ats-apply/website/jobs/v2"
    rows, offset = [], 0
    while offset < 500:  # 安全上限
        r = _post(url, json={
            "orgId": src["org_id"], "siteId": src["site_id"],
            "locale": "zh-CN", "limit": 50, "offset": offset,
        })
        payload = _moka_decrypt(r.json())
        jobs = ((payload.get("data") or {}).get("jobs")) or []
        if not jobs:
            break
        for it in jobs:
            title = it.get("title") or ""
            if src.get("title_prefix") and not title.startswith(src["title_prefix"]):
                continue
            if src.get("title_contains") and src["title_contains"] not in title:
                continue
            date = (it.get(src["time_field"]) or "")[:10]
            if not date:
                continue
            dept = ((it.get("department") or {}).get("name")) or ""
            m = re.search(r"base(北京|上海|深圳|广州|杭州|南京|成都|武汉)", title)
            rows.append({
                "company": src["company"],
                "entity": dept,
                "title": title,
                "cities": m.group(1) if m else "",
                "date": date,
                "kind": it.get("commitment") or "",
                "url": src["deep_link"].format(id=it.get("id", "")),
                "post_no": it.get("id") or title,
            })
        if len(jobs) < 50:
            break
        offset += 50
    return rows


# ---------------- 平安自建站 ----------------

_PINGAN_BODY = {
    "PageNum": 1, "businessUnitId": "", "pageSize": 200,
    "positionCategoryId": "", "wecruitId": "6c1db1bba8c33deab19a733ec785711a",
    "positionType": "2", "wecruitPlatform": True, "workCity": "", "interviewCity": "",
}


def fetch_pingan(src):
    url = ("https://campus.pingan.com/zztj-recruit-talent-webserver"
           "/rctt/candidate/position/campus/positionSearch/queryPositionPage")
    r = _post(url, json=_PINGAN_BODY, headers={
        "Origin": "https://campus.pingan.com",
        "Referer": "https://campus.pingan.com/internStudent",
    })
    j = r.json()
    if str(j.get("responseCode")) != "10001":
        raise RuntimeError(f"平安接口 responseCode={j.get('responseCode')}")
    rows = []
    for it in (j.get("data") or {}).get("list") or []:
        date = (it.get("createdDate") or "")[:10]
        if not date:
            continue
        rows.append({
            "company": src["company"],
            "entity": it.get("businessUnitName") or "",
            "title": it.get("positionName") or "",
            "cities": it.get("workCity") or "",
            "date": date,
            "kind": "实习",
            "url": src["deep_link"].format(idPosition=it.get("idPosition", "")),
            "post_no": it.get("positionCode") or str(it.get("idPosition") or ""),
        })
    return rows


# ---------------- 中信证券（自建站，global-kong 网关）----------------

# 中信接口无发布时间字段：按冻结设计启用"轻量 ID 存档"，
# 首见日期作为该岗位的窗口判定日期，存档文件随运行更新。
_CITICS_STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state", "citics_seen.json")


def _citics_seen():
    return _seen_store(_CITICS_STATE)


def _citics_save(seen):
    _seen_save(_CITICS_STATE, seen)


def fetch_citics(src):
    import datetime as _dt

    url = "https://global-kong.citics.com/api/v1/recruit/getPositionList"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "Origin": "https://careers.citics.com",
        "Referer": "https://careers.citics.com/headquarters/interns",
    }
    seen = _citics_seen()
    today = _dt.date.today().isoformat()
    rows, page = [], 1
    while page < 10:
        data = {"sysNo": "CSE001", "recruitType": "08", "deptype": "Headquarter",
                "practice": "1", "batchId": "58", "pageNo": str(page), "pageSize": "50"}
        r = _post(url, data=urlencode(data), headers=headers)
        j = r.json()
        if j.get("errorCode") != 0:
            raise RuntimeError(f"中信接口 errorCode={j.get('errorCode')} {j.get('errorMsg', '')}")
        items = j.get("positionList") or []
        if not items:
            break
        for it in items:
            no = str(it.get("positionNo") or "")
            first = seen.get(no, today)
            seen[no] = first
            rows.append({
                "company": src["company"],
                "entity": it.get("deptName") or "",
                "title": it.get("positionName") or "",
                "cities": it.get("workplace") or "",
                "date": first,  # 首见日期（接口无发布时间）
                "kind": "实习",
                "url": src["deep_link"],
                "post_no": no,
            })
        if len(items) < 50:
            break
        page += 1
    _citics_save(seen)
    return rows


# ---------------- hotjob 旧版 wt 应用（sc/www.hotjob.cn/wt/{alias}）----------------

def fetch_hotjob_wt(src):
    base_url = src["wt_base"]
    rows, page = [], 1
    while page < 20:
        url = f"{base_url}/web/json/position/list?pageNo={page}&pageSize=20&recruitType={src['recruit_type']}"
        r = _get(url, headers={"Referer": f"{base_url}/web/index/interns"})
        j = r.json()
        items = j.get("postList") or []
        if not items:
            break
        for it in items:
            date = (it.get("publishDate") or "")[:10]
            if not date:
                continue
            rows.append({
                "company": src["company"],
                "entity": it.get("orgName") or "",
                "title": it.get("postName") or "",
                "cities": it.get("workPlace") or "",
                "date": date,
                "kind": "",
                "url": (src["deep_link"].format(postKey=quote(it.get("postName") or ""))
                        if "{" in src["deep_link"] else src["deep_link"]),
                "post_no": str(it.get("postId") or "") or it.get("postName") or "",
            })
        if len(items) < 20:
            break
        page += 1
    return rows


# ---------------- 北森经典版（SSR 静态页，2019 前部署的老租户）----------------

def fetch_beisen_cms(src):
    """北森 CMS 皮肤门户：职位列表服务端渲染在 /campus 页表格内（无独立列表接口）。
    表格缺位或结构不符时抛错，不猜测、不产出可疑行。"""
    base = src.get("base") or f"https://{src['slug']}.zhiye.com"
    html = _get(f"{base}/campus").text
    m = re.search(r'<table class="jobsTable".*?</table>', html, re.S)
    if not m:
        raise RuntimeError("未找到职位表格（CMS 皮肤结构可能已变化）")
    table = m.group(0)
    if "无任何在招职位" in table:
        return []

    def txt(x):
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", x)).strip()

    rows = []
    for tr in re.findall(r"<tr>(.*?)</tr>", table, re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(tds) < 4:
            continue
        date = txt(tds[3])[:10]
        if not re.match(r"\d{4}-\d{2}-\d{2}$", date):
            continue
        href = re.search(r'href="([^"]+)"', tds[0])
        title = txt(tds[0])
        rows.append({
            "company": src["company"],
            "entity": txt(tds[1]),
            "title": title,
            "cities": txt(tds[2]),
            "date": date,
            "kind": "",
            "url": base + href.group(1) if href else f"{base}/campus",
            "post_no": title,
        })
    return rows


def fetch_beisen_classic(src):
    """经典版门户 /Intern 页服务端渲染，三模板：
    ① div.zwlblit 行（2014-2019 皮肤，htffund）；② table.jobsTable 行（2011 皮肤，
    crsec/invescogreatwall，含 /zpdetail/ 岗位级深链）；③ /internxq?jobId= 链接行
    （zofund 皮肤，全列挂岗位级深链）。三类页面均含 JD 区块，
    解析仅取岗位名/单位/地点/日期，JD 不落盘。"""
    r = _get(src["intern_url"], headers={"Referer": src["intern_url"]})
    html = r.text
    rows = []
    for row in re.findall(r'<h1 class="zwlblit">(.*?)</h1>', html, re.S):
        title = re.search(r'zwlbtxt275">\s*(.*?)\s*</span>', row)
        if not title:
            continue
        cities = re.search(r'zwlbtxt250"[^>]*>\s*(.*?)\s*</span>', row)
        date = re.search(r'zwlbtxt210">\s*(\d{4}-\d{2}-\d{2})\s*</span>', row)
        if not date:
            continue
        job_ad = re.search(r'jobadid="(\d+)"', row)
        m = JOB_NO_RE.search(title.group(1))
        rows.append({
            "company": src["company"],
            "entity": "",
            "title": title.group(1),
            "cities": (cities.group(1) if cities else "").replace("&nbsp", ""),
            "date": date.group(1),
            "kind": "实习",
            "url": src["deep_link"],
            "post_no": job_ad.group(1) if job_ad else (m.group(1) if m else title.group(1)),
        })
    if not rows:  # 模板二：jobsTable
        base = src["intern_url"].rsplit("/", 1)[0]
        for tr in re.findall(r"<tr[^>]*>((?:(?!</tr>).)*)</tr>", html, re.S):
            if "zpdetail" not in tr:
                continue
            link = re.search(r'<a title="([^"]+)" href="(/zpdetail/\d+)"', tr)
            tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if not link or len(tds) < 4:
                continue
            date = re.search(r"(\d{4}-\d{2}-\d{2})", tds[3])
            if not date:
                continue
            clean = lambda s: re.sub(r"<[^>]+>", "", s).replace("&nbsp", "").strip()
            m = JOB_NO_RE.search(link.group(1))
            rows.append({
                "company": src["company"],
                "entity": clean(tds[1]),
                "title": link.group(1),
                "cities": clean(tds[2]),
                "date": date.group(1),
                "kind": "实习",
                "url": base + link.group(2),
                "post_no": m.group(1) if m else link.group(2),
            })
    if not rows:  # 模板三：internxq 链接行（六列全挂 /internxq?jobId= 深链）
        base = src["intern_url"].rsplit("/", 1)[0]
        for tr in re.findall(r"<tr[^>]*>((?:(?!</tr>).)*)</tr>", html, re.S):
            m = re.search(r'<a href="(/internxq\?jobId=\d+)"', tr)
            if not m:
                continue
            tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(tds) < 5:
                continue
            date = re.search(r"(\d{4}-\d{2}-\d{2})", tds[4])
            if not date:
                continue
            clean = lambda s: re.sub(r"<[^>]+>", "", s).replace("&nbsp", "").strip()
            title = clean(tds[0])
            if not title:
                continue
            rows.append({
                "company": src["company"],
                "entity": clean(tds[1]),
                "title": title,
                "cities": clean(tds[3]),
                "date": date.group(1),
                "kind": "实习",
                "url": base + m.group(1),
                "post_no": m.group(1).split("=")[-1],
            })
    return rows


# ---------------- 鹏华自建站（Spring 后端 JSON 接口）----------------

def fetch_phfund(src):
    """listDemandPage：professionCharacter 3=实习 2=校招 1=社招；返回含 JD 全文
    （responsibility/jobRequirements），本适配器只挑选白名单字段，JD 解析后即弃。"""
    url = "https://job.phfund.com.cn/general/demand/listDemandPage"
    headers = {
        "Content-Type": "application/json",
        "Origin": "https://job.phfund.com.cn",
        "Referer": "https://job.phfund.com.cn/",
    }
    rows, page = [], 1
    while page < 20:  # 安全上限
        r = _post(url, json={
            "professionCharacter": src.get("profession_character", "3"),
            "page": page, "size": 100,
        }, headers=headers)
        j = r.json()
        if j.get("code") != 200:
            raise RuntimeError(f"鹏华接口 code={j.get('code')} {str(j.get('message'))[:40]}")
        items = (j.get("data") or {}).get("list") or []
        if not items:
            break
        for it in items:
            date = (it.get("releaseDate") or "")[:10]
            if not date:
                continue
            rows.append({
                "company": src["company"],
                "entity": it.get("entryDep") or "",
                "title": it.get("jobName") or "",
                "cities": (it.get("workAddress") or "").replace(",", "、"),
                "date": date,
                "kind": it.get("professionCharacter") or "实习",
                "url": src["deep_link"],
                "post_no": str(it.get("id") or "") or it.get("jobName") or "",
            })
        if len(items) < 100:
            break
        page += 1
    return rows


# ---------------- 民生银行招聘门户（cmbc，一源多主体）----------------

def fetch_cmbc(src):
    """career.cmbc.com.cn 实习生频道：一个门户覆盖民生银行各分行、民生理财、
    民生加银基金等主体（enterprise_name 落 entity 按主体标注，jobtaikang 先例）。"""
    url = "https://career.cmbc.com.cn/portal/rest/careerrecruitment/search.view"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://career.cmbc.com.cn/#/app/recruitmentlist/trainee",
    }
    rows, page = [], 1
    while page < 10:  # 安全上限
        r = _post(url, data=f"view=careerRecruitmentList&pageNo={page}&pageSize=100&searchRecruitmentIds=trainee",
                  headers=headers)
        j = r.json()
        items = (j.get("data") or {}).get("items") or []
        if not items:
            break
        for it in items:
            date = (it.get("careerRecruitment_career_publishDate") or "")[:10]
            if not date:
                continue
            rows.append({
                "company": src["company"],
                "entity": it.get("careerRecruitment_career_enterprise_name") or "",
                "title": it.get("careerRecruitment_career_name") or "",
                "cities": it.get("careerRecruitment_regions_name") or "",
                "date": date,
                "kind": "实习",
                "url": src["deep_link"].format(id=it.get("id", "")) if "{id}" in src["deep_link"] else src["deep_link"],
                "post_no": str(it.get("id") or ""),
            })
        if len(items) < 100:
            break
        page += 1
    return rows


# ---------------- 东莞证券（自建 dz-ow）----------------

def fetch_dgzq(src):
    """dgzq.com.cn/dz-ow 招聘系统：form POST hiring/query，返回含员工姓名字段
    （modifiedBy）——白名单取字段，姓名不落盘（红线 1）。"""
    url = "https://www.dgzq.com.cn/dz-ow/system/hiring/query"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://www.dgzq.com.cn/dz-ow/pcfront/",
    }
    rows, page = [], 1
    while page < 5:  # 安全上限
        r = _post(url, data=f"hiringDept=&hiringJob=&deptJobInfo=&length=50&start={page}", headers=headers)
        j = r.json()
        if str(j.get("returnCode")) != "0":
            raise RuntimeError(f"东莞证券接口 returnCode={j.get('returnCode')}")
        blocks = j.get("dataSet") or []
        items = []
        for b in blocks:
            items.extend(b.get("data") or [])
        if not items:
            break
        for it in items:
            title = it.get("hiringJob") or ""
            if "实习" not in title:
                continue
            date = (it.get("beginDate") or "")[:10]
            if not date:
                continue
            rows.append({
                "company": src["company"],
                "entity": it.get("hiringDept") or "",
                "title": title,
                "cities": it.get("workPlace") or "",
                "date": date,
                "kind": "实习",
                "url": src["deep_link"].format(hiringId=it.get("hiringId", "")) if "{hiringId}" in src["deep_link"] else src["deep_link"],
                "post_no": str(it.get("hiringId") or ""),
            })
        if len(items) < 50:
            break
        page += 1
    return rows


# ---------------- 招商银行（自建，无发布时间字段 → ID 存档法）----------------

_CMBCHINA_STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state", "cmbchina_seen.json")


def _seen_store(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _seen_save(path, seen):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=0)


def fetch_cmbchina(src):
    """career.cmbchina.com 梦工场·实习生招聘：接口仅返回截止日期（expiredOn）
    无发布时间 → 按冻结设计启用 ID 存档法（首见日期作窗口判定日期）。"""
    import datetime as _dt

    url = "https://career.cmbchina.com/api/campusRecruitmentWebsite/job/getList"
    headers = {
        "Content-Type": "application/json",
        "Referer": f"https://career.cmbchina.com/positionlist/{src['recruitment_type_id']}",
    }
    state_path = _CMBCHINA_STATE
    seen = _seen_store(state_path)
    today = _dt.date.today().isoformat()
    rows, page = [], 1
    while page < 10:  # 安全上限
        r = _post(url, json={
            "orgIdList": [], "keywords": "", "locationIdList": [],
            "pageIndex": page, "pageSize": 50,
            "recruitmentTypeId": src["recruitment_type_id"], "jobTypeIdList": [],
        }, headers=headers)
        j = r.json()
        if j.get("returnCode") != "SUC0000":
            raise RuntimeError(f"招商银行接口 returnCode={j.get('returnCode')}")
        items = (j.get("body") or {}).get("data") or []
        if not items:
            break
        for it in items:
            no = str(it.get("publishGID") or "")
            first = seen.get(no, today)
            seen[no] = first
            rows.append({
                "company": src["company"],
                "entity": it.get("branchCodeName") or "",
                "title": it.get("jobDisplay") or "",
                "cities": it.get("locationName") or "",
                "date": first,  # 首见日期（接口无发布时间）
                "kind": "实习",
                "url": src["deep_link"].format(publishGID=no) if "{publishGID}" in src["deep_link"] else src["deep_link"],
                "post_no": no,
            })
        if len(items) < 50:
            break
        page += 1
    _seen_save(state_path, seen)
    return rows


# ---------------- 高校就业网渠道（2026-10-12 纳入官方口径）----------------

_FIN_TITLE_RE = re.compile(r"证券|基金|银行|期货|资管|资产管理|信托|保险|公募|私募|投行|固收|研究所")


def fetch_sufe(src):
    """上财春华秋韵就业网实习信息：POST search/sxzpxx 默认按发布倒序；
    覆盖全行业，本地按金融关键词过滤（岗位标题或单位名）；响应含简历投递
    邮箱字段（jltdyx）——白名单取数不落盘（红线 1）。"""
    url = "https://career.sufe.edu.cn/career//zpxx/search/sxzpxx"
    headers = {"Referer": "https://career.sufe.edu.cn/career/zpxx/sxzpxx"}
    r = _post(url, headers=headers)
    j = r.json()
    if j.get("code") != 200:
        raise RuntimeError(f"上财接口 code={j.get('code')}")
    rows = []
    for it in (j.get("data") or {}).get("list") or []:
        title = it.get("zpzt") or ""
        org = it.get("dwmc") or ""
        if not (_FIN_TITLE_RE.search(title) or _FIN_TITLE_RE.search(org)):
            continue
        date = (it.get("fbrq") or "")[:10]
        if not date:
            continue
        rows.append({
            "company": src["company"],
            "entity": org,
            "title": title,
            "cities": it.get("szxmc") or "",
            "date": date,
            "kind": "实习",
            "url": src["deep_link"],
            "post_no": str(it.get("zpxxid") or ""),
        })
    return rows


def fetch_dufe(src):
    """东北财就业指导网实习信息：ajax_frontRecruitinfo JSON 分页，
    positionType=2 实习；startTime=发布 endTime=截止；url 字段为岗位详情深链。"""
    url = "https://xyzc.dufe.edu.cn/f/recruitmentinfo/ajax_frontRecruitinfo"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://xyzc.dufe.edu.cn/f/recruitmentinfo/frontRecruitinfo?positionType=2",
    }
    rows, page = [], 1
    while page < 10:  # 安全上限
        r = _post(url, data=f"pageNo={page}&pageSize=50&positionType=2&city=&title=&corporationNature=&corporationinfo.industry=",
                  headers=headers)
        obj = (r.json().get("object") or {})
        items = obj.get("list") or []
        if not items:
            break
        for it in items:
            title = it.get("title") or ""
            org = (it.get("corporationinfo") or {}).get("name") or ""
            if not (_FIN_TITLE_RE.search(title) or _FIN_TITLE_RE.search(org)):
                continue
            date = (it.get("startTime") or "")[:10]
            if not date:
                continue
            rows.append({
                "company": src["company"],
                "entity": org,
                "title": title,
                "cities": "",
                "date": date,
                "kind": "实习",
                "url": it.get("url") or src["deep_link"],
                "post_no": str(it.get("id") or ""),
            })
        if len(items) < 50 or page >= (obj.get("totalPage") or 1):
            break
        page += 1
    return rows


def fetch_ruc_sf(src):
    """人大财金学院「财金职业发展」实习信息：SSR 静态列表（ul-txt1-qm），
    条目链接多为微信文章（公开可读）；页面为 UTF-8，requests 需显式指定编码。"""
    r = _get(src["list_url"], headers={"Referer": src["list_url"]})
    r.encoding = "utf-8"
    html = r.text
    rows = []
    for li in re.findall(r'<li id="line_u\d+_\d+">(.*?)</li>', html, re.S):
        date = re.search(r"<span>\s*(\d{4}-\d{2}-\d{2})\s*</span>", li)
        link = re.search(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', li, re.S)
        if not date or not link:
            continue
        title = re.sub(r"<[^>]+>", "", link.group(2)).strip()
        if not title:
            continue
        href = link.group(1)
        if href.startswith("../"):
            from urllib.parse import urljoin
            href = urljoin(src["list_url"], href)
        rows.append({
            "company": src["company"],
            "entity": "人大财金职业发展",
            "title": title,
            "cities": "北京",
            "date": date.group(1),
            "kind": "实习",
            "url": href,
            "post_no": href,
        })
    return rows


# ---------------- 贸大招生就业处（列表接口前端混淆加密 → 渲染路径）----------------

def fetch_uibe(src):
    """贸大就业频道实习信息：列表 ajax（zpxxQuery.do）响应为前端混淆加密文本
    （无密钥下发，按红线不走反解）→ 采集走 headless 渲染真实 DOM（与实习僧通道同模式）。
    解析 <ul id="zpxx-list-content"> 列表行：标题/城市/日期/详情 tid。"""
    return _parse_uibe_html(_uibe_render(src["list_url"]), src["company"])


def _uibe_render(list_url):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0")
        page = ctx.new_page()
        page.goto(list_url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(4500)
        html = page.content()
        b.close()
    return html


def _parse_uibe_html(html, company):
    rows = []
    for li in re.findall(r"<li>(.*?)</li>", html, re.S):
        link = re.search(r'<a href="(/front/zpxx\.jspa\?tid=\d+)"[^>]*>([^<]{2,60})</a>', li)
        date = re.search(r"class=\"[^\"]*time[^\"]*\">.*?(\d{4}-\d{2}-\d{2})", li, re.S)
        city = re.search(r'class="region">\s*[\[（]?\s*([^\]）<]{2,32})', li)
        if not link or not date:
            continue
        title = link.group(2).strip()
        title = re.sub(r"\s+", " ", title)
        if not _FIN_TITLE_RE.search(title):
            continue
        rows.append({
            "company": company,
            "entity": "",
            "title": title,
            "cities": city.group(1).strip("[]（）() ") if city else "",
            "date": date.group(1),
            "kind": "实习",
            "url": "https://aeo.uibe.edu.cn" + link.group(1),
            "post_no": link.group(1),
        })
    return rows


# ---------------- 西南财经大学（智慧就业系统，实习列表 SSR＋详情刷新时间）----------------

_SWUFE_BASE = "https://job3.swufe.edu.cn"
_SWUFE_PAGES = 4  # 列表卡片无日期字段：按刷新时间倒序，前 4 页约覆盖近一个月


def fetch_swufe(src):
    """实习列表（服务端渲染，全行业）：卡片标题属性形如「北京市 | 审计助理」。
    卡片无日期，仅对命中金融关键词的岗位取详情页「刷新时间」作行日期
    （与平台展示一致，同实习僧口径）。"""
    rows = []
    for pg in range(1, _SWUFE_PAGES + 1):
        url = (f"{_SWUFE_BASE}/interns/internship_list.htm" if pg == 1
               else f"{_SWUFE_BASE}/interns/internship_list/page/{pg}.htm")
        html = _get(url).text
        for blk in html.split('class="J_jobsList yli"')[1:]:
            a = re.search(r'<a href="(/interns/interns_show/id/(\d+)\.htm)"[^>]*title="([^"]*)"', blk)
            if not a:
                continue
            comp = re.search(r'class="line_substring"[^>]*>([^<]{2,60})</a>', blk)
            city, _, title = a.group(3).replace("&nbsp;", " ").partition("|")
            company = (comp.group(1) if comp else "").replace("&nbsp;", " ").strip()
            title = title.strip()
            if not (_FIN_TITLE_RE.search(title) or _FIN_TITLE_RE.search(company)):
                continue
            if re.search(r"暑期|暑假|夏令营|[Ss]ummer", title):  # 不扫暑期线，名称层兜底
                continue
            try:
                detail = _get(_SWUFE_BASE + a.group(1)).text
            except Exception:
                continue
            m = re.search(r'class="job_date[^"]*"><span[^>]*>(\d{4}-\d{2}-\d{2})', detail)
            if not m:
                continue
            rows.append({
                "company": company or src["company"],
                "entity": "",
                "title": title,
                "cities": city.strip(),
                "date": m.group(1),
                "kind": "实习",
                "url": _SWUFE_BASE + a.group(1),
                "post_no": a.group(2),
            })
    return rows


# ---------------- 港中深（职业规划与发展处，URL 参数化筛选，requests 直抓）----------------

def fetch_cuhk(src):
    """career.cuhk.edu.cn/job/search：d_category=102 实习筛选为 URL 参数；
    站为全行业 → 本地金融关键词过滤；发布时间在卡片 sousuo_list_time 区。"""
    rows, page = [], 1
    while page < 5:  # 安全上限
        r = _get(f"https://career.cuhk.edu.cn/job/search?d_category=102&page={page}",
                 headers={"Referer": "https://career.cuhk.edu.cn/job/search"},
                 timeout=60)
        html = r.text
        cards = re.findall(
            r'<div class="sousuo_list_com"><a[^>]*>(.*?)</a></div>.*?'
            r'<a target="_blank" href="(/job/view/id/\d+)"[^>]*>(.*?)</a>.*?'
            r'发布时间：(\d{4}-\d{2}-\d{2})',
            html, re.S)
        if not cards:
            break
        for org, href, title, date in cards:
            title = title.strip()
            org = org.strip()
            if not (_FIN_TITLE_RE.search(title) or _FIN_TITLE_RE.search(org)):
                continue
            rows.append({
                "company": src["company"],
                "entity": org,
                "title": title,
                "cities": "",
                "date": date,
                "kind": "实习",
                "url": "https://career.cuhk.edu.cn" + href,
                "post_no": href.split("/")[-1],
            })
        if len(cards) < 20:
            break
        page += 1
    return rows


# ---------------- 暨大就业信息服务平台（scdc，渲染路径）----------------

def fetch_jnu(src):
    """scdc.jnu.edu.cn 岗位信息：与港中深同款平台（d_category=102 实习、/job/view/id/
    深链），但列表对非浏览器 TLS 指纹返回空壳（requests 直拿零卡片，无验证码/
    登录墙/签名，属被动客户端区分）→ 采集走 headless 渲染（与贸大同模式）。
    time=60（近2月）预过滤 + 本地金融关键词过滤，分页 ?page=N。"""
    rows, page = [], 1
    while page < 8:  # 安全上限：近2月筛选下的页数上限
        url = f"{src['base_url']}/job/search?d_category=102&time=60&page={page}"
        html = _jnu_render(url)
        n_cards = len(re.findall(r"发布</span>", html))
        rows.extend(_parse_jnu_html(html, src["company"], src["base_url"]))
        if n_cards < 14:  # 满页 14 卡，短页即列表末（整页无金融岗不算末页）
            break
        page += 1
    return rows


def _jnu_render(url):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0")
        page = ctx.new_page()
        page.goto(url, timeout=45000, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        html = page.content()
        b.close()
    return html


def _parse_jnu_html(html, company, base_url):
    rows = []
    for org, href, title, date, city in re.findall(
            r'<div class="job">.*?<a target="_blank" href="/company/view/id/\d+">(.*?)</a>'
            r'.*?href="(/job/view/id/\d+)"[^>]*>(.*?)</a>\s*<span>(\d{4}-\d{2}-\d{2})发布</span>'
            r'.*?<li>([^<]*?)</li>\s*<li>实习</li>',
            html, re.S):
        title = title.strip()
        org = org.strip()
        if not (_FIN_TITLE_RE.search(title) or _FIN_TITLE_RE.search(org)):
            continue
        rows.append({
            "company": company,
            "entity": org,
            "title": title,
            "cities": city.strip(),
            "date": date,
            "kind": "实习",
            "url": base_url + href,
            "post_no": href.split("/")[-1],
        })
    return rows


# ---------------- 中南财就业指导服务中心（公开 JSON API）----------------

def fetch_zuel(src):
    """jyzx.zuel.edu.cn：/api/publicly/* 公开 JSON（无加密无登录，首页有浏览器
    检测但 API 不设防）；title=实习 参数化过滤（百条量级）＋本地金融关键词过滤；
    createTime 为发布时间（斜杠格式）。岗位详情为 SPA 路由、无稳定公开 URL →
    深链落列表页（北森标准皮肤先例）。"""
    rows, page = [], 1
    while page < 5:  # 安全上限
        r = _get(f"{src['base_url']}/api/publicly/recruit/list?page={page}&limit=100&title=实习",
                 headers={"Referer": f"{src['base_url']}/home/career?type=1"})
        j = r.json()
        items = j.get("data") or []
        if not items:
            break
        for it in items:
            date = (it.get("createTime") or "").replace("/", "-")[:10]
            if not date:
                continue
            org = it.get("companyName") or ""
            title = it.get("title") or ""
            pos = it.get("positionNames") or ""
            if not (_FIN_TITLE_RE.search(title) or _FIN_TITLE_RE.search(org)
                    or _FIN_TITLE_RE.search(pos)):
                continue
            rows.append({
                "company": src["company"],
                "entity": org,
                "title": title,
                "cities": "",
                "date": date,
                "kind": "实习",
                "url": src["deep_link"],
                "post_no": str(it.get("id") or ""),
            })
        if len(items) < 100:
            break
        page += 1
    return rows


# ---------------- 浙大就业服务平台（正方 v5 栈，公开 POST）----------------

_ZJU_BODY = ("send_by_bootstrap_table=true"
             "&searchModel.inputType=%7B%22zpzt%22%3A%5B%22%22%5D%2C%22zwmc%22%3A%5B%22%22%5D%2C%22dwmc%22%3A%5B%22%22%5D%7D"
             "&searchModel.selectType=%7B%22zwlbdm%22%3A%5B%221016%22%5D%2C%22zpdxdm%22%3A%5B%222%22%5D%7D"
             "&searchModel.dateType=%7B%7D&searchModel.numberType=%7B%7D"
             "&searchModel.inputSqlType=0&queryModel.showCount=15")


def fetch_zju(src):
    """浙大就业服务平台：/jyxt/sczp/zpztgl/getZpztdwList.zf 公开 POST（正方
    bootstrap-table 协议，无加密无登录）。zwlbdm=1016（金融/银行/保险/证券/投资
    类）× zpdxdm=2（实习对象）双服务端过滤——分类层天然避开校招主口径，名称层
    剔暑期兜底；fbsj=发布时间、ztid=稳定专题 ID。专题详情为 SPA 路由
    （ckZpgwList.zf?ztid= 渲染为壳）→ 深链落列表页。"""
    rows, page = [], 1
    while page < 6:  # 安全上限
        r = _post(src["base_url"] + "/jyxt/sczp/zpztgl/getZpztdwList.zf",
                  data=_ZJU_BODY + f"&queryModel.currentPage={page}",
                  headers={
                      "Content-Type": "application/x-www-form-urlencoded",
                      "X-Requested-With": "XMLHttpRequest",
                      "Referer": src["base_url"] + "/jyxt/sczp/zpztgl/cxZpztList.zf?xxdm=10335",
                  })
        j = r.json()
        items = j.get("items") or []
        if not items:
            break
        for it in items:
            date = (it.get("fbsj") or "")[:10]
            if not date:
                continue
            title = it.get("zpzt") or ""
            if re.search(r"暑期|暑假|夏令营|[Ss]ummer", title):
                continue
            org = it.get("dwmc") or ""
            if not (_FIN_TITLE_RE.search(title) or _FIN_TITLE_RE.search(org)):
                continue  # zwlbdm 已限金融类，代发主体名兜底
            rows.append({
                "company": src["company"],
                "entity": org,
                "title": title,
                "cities": "",
                "date": date,
                "kind": "实习",
                "url": src["deep_link"],
                "post_no": it.get("ztid") or title,
            })
        if page >= (j.get("totalPage") or 1) or len(items) < 15:
            break
        page += 1
    return rows


ADAPTERS = {
    "beisen": fetch_beisen,
    "beisen_classic": fetch_beisen_classic,
    "beisen_cms": fetch_beisen_cms,
    "hotjob": fetch_hotjob,
    "moka": fetch_moka,
    "pingan": fetch_pingan,
    "citics": fetch_citics,
    "hotjob_wt": fetch_hotjob_wt,
    "phfund": fetch_phfund,
    "cmbc": fetch_cmbc,
    "dgzq": fetch_dgzq,
    "cmbchina": fetch_cmbchina,
    "sufe": fetch_sufe,
    "dufe": fetch_dufe,
    "ruc_sf": fetch_ruc_sf,
    "uibe": fetch_uibe,
    "cuhk": fetch_cuhk,
    "jnu": fetch_jnu,
    "zuel": fetch_zuel,
    "zju": fetch_zju,
    "swufe": fetch_swufe,
}


def fetch_source(src):
    """按信源配置取数，带一次重试。抛出的异常由调用方记录。"""
    fn = ADAPTERS[src["adapter"]]
    try:
        return fn(src)
    except Exception:
        return fn(src)
