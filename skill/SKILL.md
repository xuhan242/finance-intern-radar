---
name: finance-intern-radar
description: 扫描金融机构官网日常实习岗位并输出日期×机构类型矩阵 Excel。当用户要求"扫实习岗位""跑一下实习雷达""看看最近有什么日常实习更新""实习信源体检"时使用。仅聚合机构官网公开 JD（公司名+岗位名+城市+官网深链），不含 JD 全文与任何联系方式。
---

# finance-intern-radar

金融机构日常实习岗位聚合扫描器。官网/机构侧已接入 47 家信源（11 类适配通道：北森新版 API、北森经典版 SSR 三模板、hotjob、hotjob 经典 wt、Moka（含 title_contains 过滤）、平安自建站、中信证券自建站（ID 存档法）、鹏华自建站、民生银行门户、东莞证券自建、招商银行自建（ID 存档法）），另接**高校就业网渠道** 9 家（上财/东北财/人大财金/贸大/港中深/暨大/中南财/浙大/西财，官方口径；矩阵「高校渠道」列，entity=招聘金融机构；暨大走渲染路径、中南财公开 JSON、浙大正方栈双服务端过滤、西财实习列表 SSR＋详情刷新时间）——合计 **56 家 enabled**（机构类型十类），清单以 `skill/sources.py` 的 enabled 为准，各家接口规格见 `sources/*.md`。另接**实习僧渠道**（并列渠道，机构清单维度、全方向 JD、可融合去重），规格见 `sources/实习僧.md`。

## 使用

```bash
cd finance-intern-radar/skill

# 官网雷达：全部信源，默认 10 个工作日窗口（含节假日，窗口内休息日发布的岗位不漏）
python radar_scan.py

# 指定方向（公募 / 券商 / 保险 / 综合金融 / 资管；资管 = 公募+保险集团+综合金融）
python radar_scan.py --direction 券商

# 自定义窗口：工作日数，或自然日区间
python radar_scan.py --days 20
python radar_scan.py --start 20260901 --end 20260930

# 信源体检：错误三分（真零新增 / HTTP·网络错误 / 接口异常 / 解析 0 条=疑似平台改版）
python radar_scan.py --healthcheck

# 复测模式：注册表记录档＋recheck_spec.json 批量探针，产出升格候选清单（升格仍需人工签核）
python radar_scan.py --recheck

# 同日重复运行：复用 30 分钟内的官网解析结果（默认关闭，说明页会注明）
python radar_scan.py --reuse-cache

# 实习僧渠道（并列渠道，headless Chromium 真实渲染）：机构清单维度，近一月全方向 JD
python shixiseng_scan.py
python shixiseng_scan.py --merge            # 叠加官网/高校 56 家，岗位级融合去重
python shixiseng_scan.py --merge --days 22  # 官网窗口同步放宽到近一月
python shixiseng_scan.py --directions       # 方向词维度（发现机构清单外机会＋自动产出候选报告）
python shixiseng_scan.py --healthcheck      # 关键词体检（活跃/静默/零命中复探/渲染失败）
python shixiseng_scan.py --keywords 天弘基金,安联资管 --pages 2
```

输出规则：

- **有新增**：打印一行结论（窗口、总条数、分类型计数）+ Excel 路径（`output/radar_时间戳.xlsx`）。
- **零新增**：只回一句"窗口内零新增"，不落盘。
- Excel 三页，默认展示 `岗位清单`（一行一岗：日期 / 机构类型 / 岗位 / Base地 / 来源 / 可点链接）；`岗位矩阵`（一天一块、日期列纵向合并；块内按层横向铺开，一格一岗位一超链接，条目带 Base 地后缀）；`扫描说明`（窗口、日历口径、逐信源计数、失败信源、未启用信源）。
- 各家 `sources/*.md` 为实测留档；深链模板与启用状态以 `skill/sources.py` 为准。
- 向用户汇报时引用控制台结论与文件路径即可，Excel 内的说明页已含全部口径信息。

## 依赖

Python 3.12 + `requests` + `openpyxl` + `pycryptodome`（Moka 解密用，缺失时嘉实一家失败、其余信源不受影响）。

## 关键设计（冻结决策，改动需用户确认）

- **两把时间尺子**：信源活性 = 60 自然日（`--healthcheck`）；输出窗口 = 10 个工作日（`--days` 可调），取"往前第 N 个工作日"到今天的整个自然日区间。
- **工作日历**：内置 2026 年国务院节假日表（含调休），每次扫描先联网核对（timor.tech），失败静默用内置表；窗口跨入官方安排未公布的年份（如 2027）自动降级为"仅剔除周末"并在扫描说明页注明。
- **并发扫描**：同招聘宿主（zhiye / hotjob / mokahr）的信源组内串行——单宿主请求节奏与逐家串行完全一致；跨宿主 8 线程并行，结果按原信源顺序组装（输出与串行版逐条一致）。HTTP 连接按宿主、按线程复用（`adapters._session`），不跨线程共享 Session。
- **运行效率**：`--merge` 时官网采集与实习僧浏览器采集并行（两渠道无共享状态）；实习僧按**关键词并行**（`KEYWORD_WORKERS=4`，每 worker 独立上下文，结果按关键词原顺序组装并去重，与逐词串行版逐条一致：20 词 A/B 36.4s→10.9s）；列表页拦截图片/媒体/字体资源、页间固定等待 0.5s（卡片选择器已保证内容就绪，`PAGE_SETTLE_MS` 可调）；详情页刷新时间补采 4 线程；`--reuse-cache` 按信源复用 30 分钟内的解析结果（默认关闭）。
- **体检错误三分**：真零新增（在招但 60 天无新增）／HTTP·网络错误／接口异常（返回错误码或结构变化，疑似改版或下线）／解析 0 条（接口通但零岗位，疑似平台改版，需对照 sources/ 档案核实是真空还是改版——国盛证券 2026-10-17 首例，核实为实习频道真空）。实习僧关键词体检另分：活跃／静默／零命中（先复探一轮再定论，区分瞬时抽风与真实零在招）／渲染失败。
- **复测模式（--recheck）**：`skill/recheck_spec.json`（自动目标=探针参数同 sources.py 结构；manual=页面型不可自动复测；shixiseng_watchlist=实习僧侧观察名单）；北森门户改版为 CMS 皮肤（页面型 SSR 表格）的机构用 `beisen_cms` 探针；接口返回非 JSON（门户迁移/下线）时抛「接口非 JSON」而非 JSONDecodeError＋注册表记录档可探针项，统一按 60 自然日新增判定；升格候选只出清单（output/recheck_*.md），enabled 需人工签核——清单=签核资产口径不破。
- **方向词反哺**：`--directions` 采集后自动 diff 机构词表，产出「清单外高频机构候选」报告（output/directions_scout_*.md，卡片数/最新刷新/类型推断），只进待审、不自动加词。
- **去重键** = 公司 + 职位号（泰康同职位号重复发布的坑已处理）；窗口判定用各信源的时间基准字段（北森 `PostDate`、hotjob `publishFirstDate`、Moka `publishedAt`、平安 `createdDate`），不用会被刷新的 `publishDate`。**中信证券接口无发布时间字段**，启用 ID 存档法（`skill/state/citics_seen.json`，首见日期作窗口判定日期）。
- **方向切分按机构类型**，不做岗位关键词过滤（会两头出错）；集团门户全量收录、按主体标注（泰康/人保/平安先例）。
- **不扫暑期/校招线**（浙大 zpdxdm=2 分类层过滤＋名称层剔暑期兜底）；信源按 60 自然日活性体检，零新增剔除并留复测判据。
- **深链策略**：有岗位级 URL 的**直达岗位**（中金/泰康 `?jobAdId=`、嘉实 Moka `#/job/{id}`、平安 `?positionId=`、暨大 `/job/view/id/`、实习僧 `/intern/inn_{id}`）；hotjob 系（13 家）用**列表页 + `?postKey={岗位名}` 过滤定位**（详情页需登录，平台设计；过滤参数已实测有效）；**北森标准皮肤（10 家）、中信证券、中南财、浙大**的岗位详情为页内展开或 SPA 壳、无岗位级 URL，深链落列表页（平台限制，非工具缺陷）。
- **实习僧渠道**（并列渠道，非机构官网，经用户确认接入）：机构清单维度为主（`company_keywords.json`，默认排序保证机构岗位不被模糊匹配挤出）、方向词维度为辅（最新排序）；行日期 = 详情页刷新时间（匿名直连补采、缓存于 state，日常只补新岗位）；搜索结果按公司名过滤（站点为分词模糊匹配）；标题中的自定义字体私有区字符仅剥离、不解析字体映射；「页面加载成功但近一月筛下零卡片」归为零命中而非渲染失败（真实零在招，体检模式复探确认）；`--merge` 与官网做岗位级融合去重（公司别名归一 + 岗位名规范化匹配）。
- **回归测试**：`tests/run_golden_tests.py` 离线回放 21 份通道 fixture（真实响应录制、脱敏后存 `tests/golden/`；JD 全文/联系方式字段替换为 `[SAN]`，Moka 解密→脱敏→原密钥重加密），覆盖三类漂移——请求形态（URL/参数/请求体）、字段映射（逐行比对录制期望）、行结构（schema＋红线扫描）；渲染类通道（贸大/暨大）按录制序列重放。fixture 过期重录：`python tests/golden/_capture.py [adapter ...]`。

## 数据红线（不可越）

1. 绝不输出任何 HR 姓名、电话、邮箱、微信。
2. 不全文复制 JD，只出公司名、主体、岗位名、城市与官网深链。
3. 不绕过任何反爬措施（验证码、登录墙、签名）。Moka 的 AES 响应密钥随响应明文下发，属前端编码，已由用户确认可解。

## 新增信源的流程

1. 按 `sources/` 下既有记录的格式实测新机构（接口、分类编码、时间基准字段、深链、近 7/30/60 天新增），落盘 `sources/{公司}.md`。
2. `skill/sources.py` 注册（选对 adapter；机构类型决定矩阵列）。
3. `tests/golden/_capture.py {adapter}` 补该通道 fixture，`tests/run_golden_tests.py` 验证。
4. 更新 `行业地图/` 对应名单的「信息源存在」列（本地运营资产，发布包不含）。
5. `python radar_scan.py --healthcheck` 验证，再跑一次全量扫描确认不破坏现有输出。
6. 保留观察/暂缓的可探针项录入 `skill/recheck_spec.json`（targets 加探针参数；页面型进 manual），供 `--recheck` 批量复测。
