# finance-intern-radar（金融机构实习岗位雷达）

聚合**金融机构官网**日常实习岗位并输出「日期 × 机构类型」矩阵 Excel 的扫描工具。附带**实习僧**并列渠道，两份结果自动融合去重。

- 官网侧：47 家信源在线（11 类适配通道：北森新版 API、北森经典版 SSR 三模板、hotjob、hotjob 经典 wt、Moka（含 title_contains 过滤）、平安自建站、中信证券自建站（ID 存档法）、鹏华自建站、民生银行门户、东莞证券自建、招商银行自建（ID 存档法））。
- 高校就业网渠道 9 家（上财 / 东北财 / 人大财金 / 贸大 / 港中深 / 暨大 / 中南财 / 浙大 / 西财，官方口径），entity 归到招聘金融机构。
- 合计 **56 家 enabled**，机构类型十类（公募 / 券商 / 期货 / 保险集团 / 综合金融 / 保险资管 / 养老金 / 理财子 / 银行 / 高校渠道）；清单以 `skill/sources.py` 的 enabled 为准，各家接口规格见 `sources/*.md`。
- 实习僧侧：97 个机构关键词 + 方向词维度，近一月全方向 JD，行日期 = 详情页刷新时间（与平台显示一致）。
- 扫描并发：同招聘宿主（zhiye / hotjob / mokahr）组内串行（单宿主请求节奏与串行版一致），跨宿主 8 线程并行，输出与串行版逐条一致；HTTP 连接按宿主、按线程复用。`--merge` 时官网与实习僧两渠道并行采集，实习僧列表页拦截图片/媒体/字体、页间等待 0.5s，关键词 4 路并行采集，详情页刷新时间补采 4 线程。
- 输出：Excel 三页——`岗位清单`（一行一岗，日期/机构类型/岗位/Base地/来源/可点链接）、`岗位矩阵`（一天一块、按层横排、超链接）、`扫描说明`（窗口、日历、逐信源计数）。
- 数据口径：只聚合**公司名 + 主体 + 岗位名 + 城市 + 官网深链**，不含 JD 全文、不含任何 HR 联系方式（合规红线，见下）。

## 环境要求

- Python 3.10+（开发环境 3.12）
- 首次使用需安装依赖与 Chromium（实习僧采集用真实浏览器渲染）：

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## 快速开始

```bash
cd skill

# 日常一条命令：官网 56 家 + 实习僧 97 词，岗位级融合去重，默认 10 个工作日窗口
python shixiseng_scan.py --merge

# 只看官网雷达
python radar_scan.py

# 指定方向（公募/券商/保险/综合金融/资管；资管 = 公募+保险集团+综合金融）
python radar_scan.py --direction 券商

# 自定义窗口
python radar_scan.py --days 20                    # 最近 20 个工作日
python radar_scan.py --start 20260901 --end 20260930   # 自然日区间
python shixiseng_scan.py --merge --start 20260901 --end 20260930  # 双渠道同窗口融合

# 信源体检（错误三分：真零新增 / HTTP·网络错误 / 接口异常 / 解析 0 条=疑似平台改版）
python radar_scan.py --healthcheck

# 实习僧关键词体检（活跃 / 静默 / 零命中复探 / 渲染失败）
python shixiseng_scan.py --healthcheck

# 复测模式：保留观察/暂缓批量探针，产出升格候选清单（升格需人工签核）
python radar_scan.py --recheck

# 同日重复运行：复用 30 分钟内的官网解析结果（默认关闭）
python radar_scan.py --reuse-cache

# 实习僧方向词维度（发现机构清单外机会，自动产出候选报告 output/directions_scout_*.md）
python shixiseng_scan.py --directions
```

输出 Excel 在 `output/` 目录（`merged_时间戳.xlsx`，含三页）。窗口内零新增时只打印一句"窗口内零新增"，不落盘。

## 目录结构

```
├── skill/
│   ├── SKILL.md              使用说明与冻结设计（入口）
│   ├── radar_scan.py         官网扫描器（11 类通道适配，并发分组）
│   ├── shixiseng_scan.py     实习僧采集器（headless Chromium，可融合官网结果）
│   ├── shixiseng_config.py   实习僧机构别名 / 类型映射
│   ├── sources.py            信源注册表（enabled 决定在线状态）
│   ├── adapters.py           各招聘系统适配器
│   ├── workcalendar.py       国务院节假日日历（含调休）
│   ├── reconcile.py          排查台账 × 注册表对账（判收录漏接检测）
│   ├── recheck_spec.json     复测目标清单（自动探针参数 / manual / 实习僧观察名单）
│   ├── company_keywords.json 实习僧机构关键词清单
│   └── state/                运行状态缓存（首见日期/刷新时间存档，自动生成，可清空）
├── sources/                  各机构接口实测档案（接口规格/时间基准字段/深链模板/复测判据）
├── tests/
│   ├── run_calendar_tests.py 工作日历 12 项 + 信源结构校验
│   ├── run_golden_tests.py   通道回归：离线回放 fixture（脱敏录制）
│   └── golden/               各通道真实响应 fixture + _capture.py 重录工具
└── README.md                 本说明
```

## 新增信源流程

1. 实测新机构的招聘系统（接口、分类编码、时间基准字段、深链），按 `sources/` 既有档案格式落盘。
2. 在 `skill/sources.py` 注册（选对 adapter；`enabled=True` 即上线）。
3. `python radar_scan.py --healthcheck` 验证。
4. 跑一次全量扫描确认不破坏现有输出。

## 合规说明（三条数据红线，不可越）

1. 不输出任何 HR 姓名、电话、邮箱、微信。
2. 不复制 JD 全文，只出公司名、主体、岗位名、城市与官网深链。
3. 不绕过任何反爬措施（验证码、登录墙、签名）。个别招聘系统响应带前端 AES 编码、密钥随响应明文下发（Moka 系），属前端编码而非访问控制，工具按公开接口直读处理；若对方升级为真正登录墙/验证码，按协议直接放弃该信源，不做绕过。

## 使用声明

- 本项目仅供个人学习与研究使用，不得用于商业用途。
- 请控制访问频率（默认即低频），遵守目标站点的服务条款与 robots 约定；站点方提出异议时，相应信源应立即停用。
- 不存储、不再分发 JD 全文；测试样本（tests/golden/）为脱敏后的历史响应快照，仅用于回归测试。
- Moka 系适配器为实验性通道：其 AES 密钥由对方接口响应明文下发，代码未做任何逆向破解；如介意可删除 `skill/adapters.py` 中 `fetch_moka` 并移除对应信源，其余功能不受影响。

## 测试

```bash
python tests/run_calendar_tests.py   # 工作日历 12 项 + 信源结构校验
python tests/run_golden_tests.py     # 通道回归：22 份脱敏 fixture 离线回放
python skill/reconcile.py            # 排查台账 × 注册表对账（需台账文件，发布包内无则跳过）
```

## 与隔离环境的差异说明（仅原项目内保留）

本发布包不含：目标机构名单（行业地图/）、排查过程档案（排查/）、历史输出 Excel（output/）——这些是运营资产而非工具本体；机构名单需自行维护或联系作者索取。