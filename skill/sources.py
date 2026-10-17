# -*- coding: utf-8 -*-
"""信源注册表。每条信源对应 sources/ 下一份人工实测记录，改动须两边同步。

字段说明：
- org_type    机构类型（矩阵列名，取值：公募/券商/保险集团/综合金融/保险资管/理财子/银行）
- adapter     适配器：beisen / hotjob / moka / pingan
- enabled     False 表示按 sources/ 记录暂不扫描（拒收或暂缓），仅保留配置备查
- intern_filter  beisen 校招混发租户的实习识别（kind_or_title = Kind字段或标题含实习）
"""

SOURCES = [
    # ===== 北森（Beisen）=====
    {
        "id": "cicc", "company": "中金公司", "org_type": "券商",
        "adapter": "beisen", "slug": "cicc",
        "categories": ["3"], "time_field": "PostDate",
        "deep_link": "https://cicc.zhiye.com/custom/projectxq?jc=3&hideMenu=1&jobAdId={Id}",
        "enabled": True,
        "also_covers": ["中金公司（资管业务）"],
        "note": "项目实习；深链已实测验证；含资产管理部主体（中金资管口径，316 seq 168 不另设源）",
    },
    {
        "id": "jobtaikang", "company": "泰康保险集团", "org_type": "保险集团",
        "adapter": "beisen", "slug": "jobtaikang",
        "categories": ["3"], "time_field": "PostDate",
        "deep_link": "https://jobtaikang.zhiye.com/custom/zcdetail?hideAll=1&jc=3&jobAdId={Id}",
        "enabled": True,
        "also_covers": ["泰康资产"],
        "note": "集团门户全量收录，主体见 Org 字段（含泰康资产/泰康基金，316 seq 182 不另设源）；同职位号可能重复出现，按职位号去重",
    },
    {
        "id": "gjzq", "company": "国金证券", "org_type": "券商",
        "adapter": "beisen", "slug": "gjzq",
        "categories": ["3"], "time_field": "PostDate",
        "deep_link": "https://gjzq.zhiye.com/jobs",
        "enabled": True,
        "note": "当晚实测新增频率最高的券商信源",
    },
    {
        "id": "picc", "company": "人保集团", "org_type": "保险集团",
        "adapter": "beisen", "slug": "picc",
        "categories": ["3"], "time_field": "PostDate",
        "deep_link": "https://picc.zhiye.com/jobs",
        "enabled": True,
        "note": "在招主体以财险分公司为主，全量列出按主体标注",
    },
    {
        "id": "guosen", "company": "国信证券", "org_type": "券商",
        "adapter": "beisen", "slug": "guosen",
        "categories": ["3"], "time_field": "PostDate",
        "deep_link": "https://guosen.zhiye.com/jobs",
        "enabled": True,
        "note": "保留观察：实习线更新近乎停滞",
    },
    {
        "id": "cmfchina", "company": "招商基金", "org_type": "公募",
        "adapter": "beisen", "slug": "cmfchina",
        "categories": ["3"], "time_field": "PostDate",
        "deep_link": "https://cmfchina.zhiye.com/jobs",
        "enabled": True,
        "note": "低频但零成本接入",
    },
    {
        "id": "dwzq", "company": "东吴证券", "org_type": "券商",
        "adapter": "beisen", "slug": "dwzq",
        "categories": ["2"], "intern_filter": "kind_or_title", "time_field": "PostDate",
        "deep_link": "https://dwzq.zhiye.com/jobs",
        "enabled": True,
        "note": "无独立实习分类，实习岗混在校园招聘内",
    },

    # ===== hotjob（大易）=====
    {
        "id": "gfsec", "company": "广发证券", "org_type": "券商",
        "adapter": "hotjob", "su": "SU625527c30dcad4021443cdda",
        "recruit_type": 12, "time_field": "publishFirstDate",
        "deep_link": "https://wecruit.hotjob.cn/SU625527c30dcad4021443cdda/pb/interns.html?postKey={postKey}",
        "enabled": True,
        "note": "官网 job.gf.com.cn 外链至此",
    },
    {
        "id": "htsc", "company": "华泰证券", "org_type": "券商",
        "adapter": "hotjob", "su": "SU6013d14e5d83dc11e4a8ae4d",
        "recruit_type": 12, "time_field": "publishFirstDate",
        "deep_link": "https://wecruit.hotjob.cn/SU6013d14e5d83dc11e4a8ae4d/pb/interns.html?postKey={postKey}",
        "enabled": True,
        "note": "保留观察：存量池，极低频；2026-10-12 起租户内公司字段含华泰证券（上海）资管 11 卡（下钻 S066 覆盖口径）",
    },

    {
        "id": "xyzq", "company": "兴业证券", "org_type": "券商",
        "adapter": "hotjob", "su": "SU68fb2499b7da1347a9dd852c",
        "recruit_type": 12, "time_field": "publishFirstDate",
        "deep_link": "https://wecruit.hotjob.cn/SU68fb2499b7da1347a9dd852c/pb/interns.html?postKey={postKey}",
        "enabled": True,
        "note": "保留观察：近60天1条，接口走 wecruit 主站（自定义域不承载接口）",
    },
    {
        "id": "nesc", "company": "东北证券", "org_type": "券商",
        "adapter": "beisen", "slug": "nesc",
        "categories": ["3"], "time_field": "PostDate",
        "deep_link": "https://nesc.zhiye.com/jobs",
        "enabled": True,
        "note": "保留观察：实习分类独立、26条在招、近60天1条",
    },

    {
        "id": "cmszh", "company": "招商证券", "org_type": "券商",
        "adapter": "hotjob", "su": "SU629dbc0c0dcad452299bc0f7",
        "recruit_type": 12, "time_field": "publishFirstDate",
        "deep_link": "https://wecruit.hotjob.cn/SU629dbc0c0dcad452299bc0f7/pb/interns.html?postKey={postKey}",
        "enabled": True,
        "note": "52条实习（实收47）、近30天7条；2026-10-09 纠错：此前误记为申万宏源，浏览器title核验为招商证券",
    },

    {
        "id": "citics", "company": "中信证券", "org_type": "券商",
        "adapter": "citics",
        "time_field": "首见日期（接口无发布时间，ID 存档法）",
        "deep_link": "https://careers.citics.com/headquarters/interns",
        "enabled": True,
        "note": "2026年日常实习招聘（总部），global-kong 网关；岗位详情页内展开",
    },

    {
        "id": "cntp", "company": "太平保险集团", "org_type": "保险集团",
        "adapter": "beisen", "slug": "cntp",
        "categories": ["3"], "time_field": "PostDate",
        "deep_link": "https://cntp.zhiye.com/jobs",
        "enabled": True,
        "note": "实习生招聘线滚动发布，主体以寿险分公司/中支为主，对口度低按主体标注",
    },
    {
        "id": "sinosig", "company": "阳光保险集团", "org_type": "保险集团",
        "adapter": "beisen", "base": "https://sunzhaopin.sinosig.com",
        "categories": ["3"], "time_field": "PostDate",
        "deep_link": "https://sunzhaopin.sinosig.com/jobs",
        "enabled": True,
        "note": "北森自建域；实习生招聘 cat3 在招 37 条；阳光资产岗位走校招线",
    },

    {
        "id": "cjpension", "company": "长江养老", "org_type": "养老金",
        "adapter": "beisen", "slug": "cjpension1",
        "categories": ["3"], "time_field": "PostDate",
        "deep_link": "https://cjpension1.zhiye.com/jobs",
        "enabled": True,
        "note": "对口度极高：风险管理部/投后管理部、研究所方向实习；注意租户是 cjpension1（cjpension 为空壳）",
    },

{
        "id": "ctsec", "company": "财通证券", "org_type": "券商",
        "adapter": "hotjob", "su": "SU60613f74bef57c36adc66d0b",
        "recruit_type": 12, "time_field": "publishFirstDate",
        "deep_link": "https://wecruit.hotjob.cn/SU60613f74bef57c36adc66d0b/pb/interns.html?postKey={postKey}",
        "enabled": True,
        "note": "8条实习、近60天2条（投行债券/股权日常实习生）；浏览器title核验归属",
    },

{
        "id": "kysec", "company": "开源证券", "org_type": "券商",
        "adapter": "hotjob_wt", "wt_base": "https://www.hotjob.cn/wt/kysec",
        "recruit_type": 12, "time_field": "publishDate",
        "deep_link": "https://wecruit.hotjob.cn/SU654f2e0b3538bc6c4d600eab/pb/interns.html?postKey={postKey}",
        "enabled": True,
        "note": "10条实习全在60天内，研究所方向密集；hotjob旧版wt形态",
    },

{
        "id": "glsc", "company": "国联民生", "org_type": "券商",
        "adapter": "beisen", "slug": "glsc",
        "categories": ["3"], "time_field": "PostDate",
        "deep_link": "https://glsc.zhiye.com/jobs",
        "enabled": True,
        "note": "cat3实习11条60d2；浏览器/门户title核验国联民生",
    },

    # ===== Moka =====
    {
        "id": "jsfund", "company": "嘉实基金", "org_type": "公募",
        "adapter": "moka", "org_id": "jsfund", "site_id": 44330,
        "time_field": "publishedAt", "title_prefix": "日常实习-",
        "deep_link": "https://app.mokahr.com/campus-recruitment/jsfund/44330#/job/{id}",
        "enabled": True,
        "note": "AES-128-CBC 前端编码，密钥随响应下发；commitment 字段脏数据，按标题前缀识别",
    },

    # ===== 自建站 =====
    {
        "id": "pingan", "company": "中国平安", "org_type": "综合金融",
        "adapter": "pingan",
        "time_field": "createdDate",
        "deep_link": "https://campus.pingan.com/positionDetail?positionId={idPosition}",
        "enabled": True,
        "also_covers": ["平安人寿"],
        "note": "集团校招门户实习生频道，成员公司见 businessUnitName（含平安人寿 PA002，316 seq 257 不另设源）；批量波式发布",
    },

    # ===== 2026-10-09 全量覆盖新增（11 家）=====
    {
        "id": "njzq", "company": "南京证券", "org_type": "券商",
        "adapter": "beisen", "slug": "njzq",
        "categories": ["3"], "time_field": "PostDate",
        "deep_link": "https://njzq.zhiye.com/jobs",
        "enabled": True,
        "note": "cat3=3条（债权融资总部/巨石创投实习生）；门户标题核验归属",
    },
    {
        "id": "bhzq", "company": "渤海证券", "org_type": "券商",
        "adapter": "beisen", "slug": "bhzq",
        "categories": ["3"], "time_field": "PostDate",
        "deep_link": "https://bhzq.zhiye.com/jobs",
        "enabled": True,
        "note": "cat3=2条（股权融资总部投行部实习生2026-09-08）；存量池",
    },
    {
        "id": "gszq", "company": "国盛证券", "org_type": "券商",
        "adapter": "hotjob", "su": "SU6879a7b3e57172288b60df9d", "recruit_type": 12,
        "time_field": "publishFirstDate",
        "deep_link": "https://gszq.hotjob.cn/SU6879a7b3e57172288b60df9d/pb/interns.html?postKey={postKey}",
        "enabled": True,
        "note": "custom域gszq.hotjob.cn解析SU；rt12=2条，含研究所销售助理实习生",
    },
    {
        "id": "xnzq", "company": "西南证券", "org_type": "券商",
        "adapter": "hotjob", "su": "SU61d3efeabef57c13bcba2eea", "recruit_type": 12,
        "time_field": "publishFirstDate",
        "deep_link": "https://wecruit.hotjob.cn/SU61d3efeabef57c13bcba2eea/pb/interns.html?postKey={postKey}",
        "enabled": True,
        "note": "保留观察：43条存量，最新2026-07-15超60天活性窗",
    },
    {
        "id": "nomuraoi", "company": "野村东方国际证券", "org_type": "券商",
        "adapter": "beisen", "slug": "nomuraoi-sec",
        "categories": ["3"], "time_field": "PostDate",
        "deep_link": "https://nomuraoi-sec.zhiye.com/intern",
        "enabled": True,
        "note": "cat3=8条（投资及产品服务/机构业务部研究销售实习生等）",
    },
    {
        "id": "huaxin", "company": "华鑫证券", "org_type": "券商",
        "adapter": "beisen", "slug": "cfsc",
        "categories": ["3"], "time_field": "PostDate",
        "deep_link": "https://cfsc.zhiye.com/jobs",
        "enabled": True,
        "note": "保留观察：cat3=17条存量，最新2025-04超60天",
    },
    {
        "id": "lczq", "company": "联储证券", "org_type": "券商",
        "adapter": "hotjob_wt", "wt_base": "https://www.hotjob.cn/wt/lczq",
        "recruit_type": 12, "time_field": "publishDate",
        "deep_link": "https://www.hotjob.cn/wt/lczq/web/index/interns",
        "enabled": True,
        "note": "保留观察：rt12=20条存量，最新2025-06超60天",
    },
    {
        "id": "easec", "company": "东亚前海证券", "org_type": "券商",
        "adapter": "hotjob_wt", "wt_base": "https://sc.hotjob.cn/wt/easec",
        "recruit_type": 12, "time_field": "publishDate",
        "deep_link": "https://sc.hotjob.cn/wt/easec/web/index/interns",
        "enabled": True,
        "note": "rt12=6条（资管综合运营/投行/分析师方向实习生），归属字段核验",
    },
    {
        "id": "wkzq", "company": "五矿证券", "org_type": "券商",
        "adapter": "hotjob", "su": "SU63045367bef57c3179e6fb63", "recruit_type": 12,
        "time_field": "publishFirstDate",
        "deep_link": "https://wecruit.hotjob.cn/SU63045367bef57c3179e6fb63/pb/interns.html?postKey={postKey}",
        "enabled": True,
        "note": "五矿资本租户覆盖：含五矿证券/五矿期货主体15条，最新2026-09-16",
    },
    {
        "id": "yxcap", "company": "越秀资本", "org_type": "综合金融",
        "adapter": "hotjob", "su": "SU5f2a6d7e9b0d7882cc51349e", "recruit_type": 12,
        "time_field": "publishFirstDate",
        "deep_link": "https://wecruit.hotjob.cn/SU5f2a6d7e9b0d7882cc51349e/pb/interns.html?postKey={postKey}",
        "enabled": True,
        "note": "保留观察：实习池11条含产业基金/越秀租赁主体，最新2026-06-15",
    },
    {
        "id": "xbzq", "company": "西部证券", "org_type": "券商",
        "adapter": "hotjob", "su": "SU614049aebef57c3b638d207c", "recruit_type": 12,
        "time_field": "publishFirstDate",
        "deep_link": "https://wecruit.hotjob.cn/SU614049aebef57c3b638d207c/pb/interns.html?postKey={postKey}",
        "enabled": True,
        "note": "保留观察：rt12=6条存量，最新2026-03-24超60天",
    },

    # ===== 2026-10-12 下钻战役新增 =====
    {
        "id": "gtqh", "company": "国投期货", "org_type": "期货",
        "adapter": "hotjob", "su": "SU625d4a0b2f9d24287db127c8", "recruit_type": 12,
        "time_field": "publishFirstDate",
        "deep_link": "https://wecruit.hotjob.cn/SU625d4a0b2f9d24287db127c8/pb/interns.html?postKey={postKey}",
        "enabled": True,
        "also_covers": ["国投证券"],
        "note": "官网 gtaxqh.com 诚聘英才直链本租户；rt12 实习 19 条（量化投资部/做市交易部，最新 2026-09-29）、社招 85/校招 90 同租户（同租户亦覆盖国投证券 essence.hotjob.cn 主体，316 seq 018 不另设源）；下钻 S062",
    },
    {
        "id": "scjddt", "company": "首创京都期货", "org_type": "期货",
        "adapter": "manual",
        "time_field": "页面无日期字段",
        "deep_link": "https://www.jingduqh.com/about/7.html",
        "enabled": False,
        "note": "记录档：官网招聘信息页为服务端渲染静态页、无日期字段，无法支持增量判定（人工复测口径，下钻 S037：在招'量化研究实习生—若干'）；若站点改版出结构化接口再接",
    },

    # ===== 2026-10-12 信源攻坚新增 =====
    {
        "id": "phfund", "company": "鹏华基金", "org_type": "公募",
        "adapter": "phfund", "profession_character": "3",
        "time_field": "releaseDate",
        "deep_link": "https://job.phfund.com.cn/",
        "enabled": True,
        "note": "自建站 JSON 接口 listDemandPage（3=实习/2=校招/1=社招）；实习在招 2 条（渠道经理 09-16/09-07）、校招 35/社招 27；深链落列表页（详情路由直访 404）；信源攻坚 2026-10-12",
    },
    {
        "id": "htffund", "company": "汇添富基金", "org_type": "公募",
        "adapter": "beisen_classic",
        "intern_url": "https://htffund.zhiye.com/Intern",
        "time_field": "页面发布时间",
        "deep_link": "https://htffund.zhiye.com/Intern",
        "enabled": True,
        "note": "北森经典版 SSR（div.zwlblit 行解析）；实习在招 11 条、最新 2026-06-02（低频，保留观察接入，零成本）；信源攻坚 2026-10-12",
    },

    # ===== 2026-10-12 存量接入（316 全量排查判「收录」清单对账补入，接口当时已实测）=====
    {
        "id": "dfzq", "company": "东方证券", "org_type": "券商",
        "adapter": "moka", "org_id": "dfzq", "site_id": 5546,
        "time_field": "publishedAt",
        "deep_link": "https://app.mokahr.com/campus_apply/dfzq/5546#/job/{id}",
        "enabled": True,
        "note": "campus_apply 站与社招站同 API；实习 20 条全 open，近 60 天 +3（08-14）；316 排查 seq 013",
    },
    {
        "id": "crsec", "company": "国新证券", "org_type": "券商",
        "adapter": "beisen_classic", "intern_url": "https://crsec.zhiye.com/Intern",
        "time_field": "页面发布时间",
        "deep_link": "https://crsec.zhiye.com/Intern",
        "enabled": True,
        "note": "北森经典版 2011 皮肤（jobsTable 模板，/zpdetail/ 岗位级深链由适配器拼接）；实习 4 条，近 60 天 +1（08-25）；316 seq 053",
    },
    {
        "id": "thfund", "company": "天弘基金", "org_type": "公募",
        "adapter": "moka", "org_id": "thfund", "site_id": 46218,
        "title_contains": "实习",
        "time_field": "publishedAt",
        "deep_link": "https://app.mokahr.com/social-recruitment/thfund/46218#/job/{id}",
        "enabled": True,
        "note": "无独立实习站——实习岗挂社招站 46218（标题含「实习」过滤，title_contains 机制）；在招 2 条（网络安全/量化研究实习），最近 09-23；316 seq 071 判收录，攻坚档案 2026-10-12 修正",
    },
    {
        "id": "wjasset", "company": "万家基金", "org_type": "公募",
        "adapter": "beisen", "slug": "wjasset",
        "categories": ["3"], "time_field": "PostDate",
        "deep_link": "https://wjasset.zhiye.com/intern/detail?jobAdId={Id}",
        "enabled": True,
        "note": "实习 1 条（08-31）；官网「我要应聘」按钮直指本门户；316 seq 087",
    },
    {
        "id": "greatwallfund", "company": "长城基金", "org_type": "公募",
        "adapter": "beisen", "slug": "greatwallfund",
        "categories": ["3"], "time_field": "PostDate",
        "deep_link": "https://greatwallfund.zhiye.com/home/detail?jobAdId={Id}",
        "enabled": True,
        "note": "实习 3 条，近 30 天 +1（09-28）；官网 ccfund.com.cn「加入我们」直链；316 seq 093",
    },
    {
        "id": "invescogreatwall", "company": "景顺长城基金", "org_type": "公募",
        "adapter": "beisen_classic", "intern_url": "https://invescogreatwall.zhiye.com/Intern",
        "time_field": "页面发布时间",
        "deep_link": "https://invescogreatwall.zhiye.com/Intern",
        "enabled": True,
        "note": "北森经典版 2011 皮肤（jobsTable 模板，岗位级 zpdetail 深链）；实习 10 条全「（日常实习）」但最新 2026-02-24（超 60 天，活性体检会提示）；316 seq 077",
    },
    {
        "id": "hffund", "company": "华富基金", "org_type": "公募",
        "adapter": "beisen", "slug": "hffund",
        "categories": ["3"], "time_field": "PostDate",
        "deep_link": "https://hffund.zhiye.com/intern/detail?jobAdId={Id}",
        "enabled": True,
        "note": "实习 6 条，近 30 天 +2（09-15）；/intern 路由即实习频道；316 seq 119",
    },
    {
        "id": "cjhxfund", "company": "创金合信基金", "org_type": "公募",
        "adapter": "moka", "org_id": "cjhxfund", "site_id": 41867,
        "title_contains": "实习",
        "time_field": "publishedAt",
        "deep_link": "https://cjhxhr.cjhxfund.com/social-recruitment/cjhxfund/41867#/job/{id}",
        "enabled": True,
        "note": "官方子域 Moka 社招站含「日常实习类」8 条（title_contains 过滤近似）；近 30 天 +2（09-30）；316 seq 107",
    },
    {
        "id": "grgbanking", "company": "广电运通", "org_type": "综合金融",
        "adapter": "moka", "org_id": "grgbanking", "site_id": 39448,
        "title_contains": "实习",
        "time_field": "publishedAt",
        "deep_link": "https://app.mokahr.com/campus-recruitment/grgbanking/39448#/job/{id}",
        "enabled": True,
        "note": "门户壳 hr.grgbanking.com，校园站「实习类」5 条（其中 1 条 pause），近 30 天 +1（机械实习生 09-21）；池外备查主体（ATM/金融科技）；316 seq 313",
    },
    {
        "id": "cmbc", "company": "民生银行", "org_type": "银行",
        "adapter": "cmbc",
        "time_field": "careerRecruitment_career_publishDate",
        "deep_link": "https://career.cmbc.com.cn/#/app/recruitmentview/{id}",
        "enabled": True,
        "also_covers": ["民生理财", "民生加银基金"],
        "note": "民生招聘门户实习生频道一源多主体（jobtaikang 先例）：本体 42 分行＋民生理财 5＋民生加银基金 5＋民生科技/金租，enterprise_name 落 entity；全频道 publishDate 09-14~09-16 批量波；316 seq 227/208/115",
    },
    {
        "id": "dgzq", "company": "东莞证券", "org_type": "券商",
        "adapter": "dgzq",
        "time_field": "beginDate",
        "deep_link": "https://www.dgzq.com.cn/dz-ow/pcfront/#/dz/about/recruitDetail?hiringId={hiringId}",
        "enabled": True,
        "note": "自建 dz-ow 系统 hiring/query 接口；实习 2 条（投行承做 08-21/量化 05-20，截止 10-31）；响应含 modifiedBy 员工姓名字段，白名单取数不落盘；316 seq 036",
    },
    {
        "id": "cmbchina", "company": "招商银行", "org_type": "银行",
        "adapter": "cmbchina", "recruitment_type_id": "DF94FD6D-26D3-4A19-9E69-577C4BA1DE82",
        "time_field": "首见日期（接口无发布时间，ID 存档法，state/cmbchina_seen.json）",
        "deep_link": "https://career.cmbchina.com/positionDetail/school?publishId={publishGID}",
        "enabled": True,
        "note": "梦工场·实习生招聘：研究院 5＋分行 14 共 19 条，接口仅返截止日期（expiredOn）→ ID 存档法（citics 同构）；316 seq 223",
    },

    # ===== 存量对账：记录档（官网为页面型/无时间字段，不接，留复测判据）=====
    {
        "id": "hazq", "company": "华安证券", "org_type": "券商",
        "adapter": "manual", "time_field": "岗位无发布时间字段",
        "deep_link": "https://hahr.hazq.com:8083/eip4ha-hyapp/recruitment/socialApply?type=03",
        "enabled": False,
        "note": "自建 EIP4HA 页面型、岗位无时间字段无法增量判定；实习 1 条（投行·深圳）；复测=页面出现新实习岗且系统出结构化接口再评估；316 seq 026 判收录",
    },
    {
        "id": "citicprufunds", "company": "中信保诚基金", "org_type": "公募",
        "adapter": "manual", "time_field": "列表页无时间字段（详情页有）",
        "deep_link": "https://www.citicprufunds.com.cn/pc/joinwe",
        "enabled": False,
        "note": "自建 SSR 页无列表接口；实习 4 条（09-07 批）；详情页 recruitDetails?position_id= 带发布时间，如需接入须逐条详情补采；316 seq 106 判收录",
    },
    {
        "id": "bdfund", "company": "博道基金", "org_type": "公募",
        "adapter": "manual", "time_field": "页面日期（无结构化接口）",
        "deep_link": "http://www.bdfund.cn/aboutus/job/index.html",
        "enabled": False,
        "note": "静态 CMS 单页（岗位+日期全在 HTML，5 条日常实习 09-04）；单页无独立 URL，写入需专属解析器，收益比低暂记录；316 seq 143 判收录",
    },
    {
        "id": "gtsfund", "company": "圆信永丰基金", "org_type": "公募",
        "adapter": "manual", "time_field": "官网无时间字段",
        "deep_link": "https://www.gtsfund.com.cn/introduction/jobs/index.html",
        "enabled": False,
        "note": "自建单页、无时间字段无法增量（实习 1 条：交易部实习生）；316 seq 156 判收录",
    },
    {
        "id": "zsfund", "company": "浙商基金", "org_type": "公募",
        "adapter": "manual", "time_field": "官网无时间字段",
        "deep_link": "https://www.zsfund.com/aboutus/job/job2/index.html",
        "enabled": False,
        "note": "静态栏目页 6 条实习（截止均 2026-12-31）、无发布时间；已排除北森/Moka/大易；316 seq 164 判收录",
    },
    {
        "id": "ksfund", "company": "开思基金", "org_type": "综合金融",
        "adapter": "manual", "time_field": "页面日期",
        "deep_link": "https://www.ks-fund.cn/menus/9eQxoegAlrCLl9dYAYm9UBo/child_menus/70Qwgbl96vI6l3B5w5R3hqD",
        "enabled": False,
        "note": "石云 CMS 单页 4 条实习（08-11，60 天边界）；PE/VC 主体，矩阵无该列暂记录；316 seq 303 判收录",
    },
    {
        "id": "cib", "company": "兴业银行", "org_type": "银行",
        "adapter": "manual", "time_field": "接口未直连（签名机制）",
        "deep_link": "https://job.cib.com.cn/portal/#/recruit/814456803227381761?recruitType=TR",
        "enabled": False,
        "note": "job.cib.com.cn 接口前置 /api/cfn/sysToken keySalt 签名握手——按红线 3 不做接口直连/签名伪造；TR 频道实习 21 条（本主体 3＋兴业基金 15＋金租 3，本主体最近 08-28）；复测=渲染路径人工/后续评估；316 seq 224 判收录",
    },

    # ===== 2026-10-12 高校就业网渠道（用户拍板纳入官方口径，排查档案见 排查/2026-10-12-高校就业网/）=====
    {
        "id": "sufe", "company": "上海财经大学", "org_type": "高校渠道",
        "adapter": "sufe",
        "time_field": "fbrq",
        "deep_link": "https://career.sufe.edu.cn/career/zpxx/sxzpxx",
        "enabled": True,
        "note": "春华秋韵就业网实习信息（total 6876，发布倒序，本地金融关键词过滤，全行业源）；响应含投递邮箱字段按红线不落盘；排查 2026-10-12 判收录",
    },
    {
        "id": "dufe", "company": "东北财经大学", "org_type": "高校渠道",
        "adapter": "dufe",
        "time_field": "startTime",
        "deep_link": "https://xyzc.dufe.edu.cn/f/recruitmentinfo/frontRecruitinfo?positionType=2",
        "enabled": True,
        "note": "就业指导网实习信息（count 73，接口分页+金融业筛选参数预留，本地金融关键词过滤）；最新 2026-10-08；排查 2026-10-12 判收录",
    },
    {
        "id": "ruc_sf", "company": "中国人民大学财金学院", "org_type": "高校渠道",
        "adapter": "ruc_sf", "list_url": "http://sf.ruc.edu.cn/zyfz/xxfb/sxxx/index.htm",
        "time_field": "页面发布日期",
        "deep_link": "http://sf.ruc.edu.cn/zyfz/xxfb/sxxx/index.htm",
        "enabled": True,
        "note": "财金职业发展实习信息 SSR 列表（条目多为微信文章链接，公开可读）；金融机构实习密度高校渠道最高；最新 2026-09-11；排查 2026-10-12 判收录",
    },
    {
        "id": "uibe_aeo", "company": "对外经济贸易大学", "org_type": "高校渠道",
        "adapter": "uibe", "list_url": "https://aeo.uibe.edu.cn/front/channel.jspa?channelId=622&parentId=625",
        "time_field": "列表日期（渲染 DOM）",
        "deep_link": "https://aeo.uibe.edu.cn/front/zpxx.jspa?tid=2034643209115664385",
        "enabled": True,
        "note": "就业频道 622=实习信息 tab：列表 ajax（zpxxQuery.do）为前端混淆加密无密钥下发（红线不走反解）→ 采集走 headless 渲染 DOM（20 条/页）；实测列表含中信信托 2027 校招 10-12、望华 2027 春季实习生等；316 两次实证（天弘暑期实习/富国岗位）",
    },
    {
        "id": "jnu_scdc", "company": "暨南大学", "org_type": "高校渠道",
        "adapter": "jnu", "base_url": "https://scdc.jnu.edu.cn",
        "time_field": "卡片发布日期",
        "deep_link": "https://scdc.jnu.edu.cn/job/search?d_category=102",
        "enabled": True,
        "note": "就业信息服务平台：与港中深同款（d_category=102 实习、/job/view/id/ 深链）但列表对非浏览器 TLS 指纹回空壳（被动客户端区分，无验证码/登录墙/签名）→ headless 渲染（贸大同模式）；time=60 近2月预过滤＋本地金融过滤，满页 14 卡；2026-10-17 定位列表接入",
    },
    {
        "id": "zuel_jyzx", "company": "中南财经政法大学", "org_type": "高校渠道",
        "adapter": "zuel", "base_url": "https://jyzx.zuel.edu.cn",
        "time_field": "createTime",
        "deep_link": "https://jyzx.zuel.edu.cn/home/career?type=1",
        "enabled": True,
        "note": "就业指导服务中心：/api/publicly/recruit/list 公开 JSON（title=实习 过滤 102 条、金融过滤 31 条：招行/平安证券/中德证券/私募等）；最新 2026-08-07（60 天边界外，保留观察级接入，汇添富先例零成本）；岗位详情为 SPA 路由无稳定 URL → 深链落列表页；2026-10-17 定位接入",
    },
    {
        "id": "zju_career", "company": "浙江大学", "org_type": "高校渠道",
        "adapter": "zju", "base_url": "https://www.career.zju.edu.cn",
        "time_field": "fbsj",
        "deep_link": "https://www.career.zju.edu.cn/jyxt/sczp/zpztgl/cxZpztList.zf?xxdm=10335",
        "enabled": True,
        "note": "就业服务平台（正方 v5 栈）：getZpztdwList.zf 公开 POST，zwlbdm=1016 金融类×zpdxdm=2 实习对象双服务端过滤（30 条量级，近60天 8 条：太和致远投研/国海良时期货量化/淡马锡/国投扬帆/天风长期实习等）；专题详情 SPA 壳→深链落列表页；2026-10-17 破解接入",
    },
    {
        "id": "swufe", "company": "西南财经大学", "org_type": "高校渠道",
        "adapter": "swufe",
        "time_field": "详情页刷新时间",
        "deep_link": "https://job3.swufe.edu.cn/interns/internship_list.htm",
        "enabled": True,
        "note": "智慧就业系统实习列表（SSR，全行业源本地金融关键词过滤）；卡片无日期→仅命中项取详情页刷新时间作行日期（同实习僧口径）；列表按刷新时间倒序取前 4 页；2026-10-17 破解接入",
    },
    {
        "id": "cuhk_sz", "company": "香港中文大学（深圳）", "org_type": "高校渠道",
        "adapter": "cuhk",
        "time_field": "卡片发布时间",
        "deep_link": "https://career.cuhk.edu.cn/job/search?d_category=102",
        "enabled": True,
        "note": "job/search?d_category=102=实习筛选（URL 参数化，requests 直抓无加密）；全行业源本地金融关键词过滤；分页 page=N；实测渣打银行2027实习生（09-29）、HKPC（10-08）；requests 需长超时（60s，站点响应慢）",
    },
    {
        "id": "cufe", "company": "中央财经大学", "org_type": "高校渠道",
        "adapter": "manual", "time_field": "待定位",
        "deep_link": "https://www.cufe.edu.cn/",
        "enabled": False,
        "note": "就业网域名未定位（career/job.cufe.edu.cn 均 DNS 不存在），主站就业频道入口待查；排查 2026-10-12 判暂缓",
    },

    {
        "id": "smth_ci", "company": "水木社区·求职投行版", "org_type": "高校渠道",
        "adapter": "manual", "time_field": "发帖日期",
        "deep_link": "https://m.newsmth.net/board/Career_Investment",
        "enabled": False,
        "note": "**用户裁定不入池（2026-10-12）**：民间论坛属第三方渠道（沿用排除口径），不接；技术备忘：m 版 SSR 可解析（30 帖/页、/article/{board}/{n} 深链、置顶过滤），版活跃（955 页、2026-10-09 直发帖），若未来口径变更可直接接入",
    },

    # ===== 已实测拒收 / 暂缓（记录见 sources/，不扫描）=====
    {
        "id": "nffund", "company": "南方基金", "org_type": "公募",
        "adapter": "hotjob", "su": "SU6138665dbef57c3b63841399", "recruit_type": 12,
        "time_field": "publishFirstDate",
        "deep_link": "https://wecruit.hotjob.cn/SU6138665dbef57c3b63841399/pb/interns.html?postKey={postKey}",
        "enabled": False,
        "note": "不接：实测双入口租户（SU6138665dbef57c3b63841399 与 SU63eedf31bef57c71d9fb6a64 同库）实习线全 0（rt12 及 3/4/10/11/13/14/15 穷举），社招 26/校招 25 无实习类目；复测判据=rt12 出现≥1 条",
    },
    {
        "id": "bosera", "company": "博时基金", "org_type": "公募",
        "adapter": "hotjob", "su": "SU65f940241c240e0a2275bda8", "recruit_type": 12,
        "time_field": "publishFirstDate",
        "deep_link": "https://bosera.hotjob.cn/SU65f940241c240e0a2275bda8/pb/interns.html?postKey={postKey}",
        "enabled": False, "note": "不接：实习池存量，近60天零新增",
    },
    {
        "id": "efund", "company": "易方达基金", "org_type": "公募",
        "adapter": "hotjob", "su": "SU67ac68866202cc7916aea66e", "recruit_type": 12,
        "time_field": "publishFirstDate",
        "deep_link": "https://wecruit.hotjob.cn/SU67ac68866202cc7916aea66e/pb/interns.html?postKey={postKey}",
        "enabled": False, "note": "不接：实习频道为多年期占位岗",
    },
    {
        "id": "zofund", "company": "中欧基金", "org_type": "公募",
        "adapter": "beisen_classic",
        "intern_url": "https://zofund.zhiye.com/intern?k=&c=&p=1^-1,3^-1&d=&PageIndex=1&class=3",
        "time_field": "页面发布时间",
        "deep_link": "https://zofund.zhiye.com/intern?k=&c=&p=1^-1,3^-1&d=&PageIndex=1&class=3",
        "enabled": False,
        "note": "不接：经典版第三皮肤（六列 /internxq?jobId= 深链行，岗位级 URL），在招 15 条、最新 2026-08-04（60 天外 9 天）；复测判据=/intern 列表页出现近 60 天内条目",
    },
]

ORG_TYPE_ORDER = ["公募", "券商", "期货", "保险集团", "综合金融", "保险资管", "养老金", "理财子", "银行", "高校渠道"]

DIRECTION_MAP = {
    "all": None, "全部": None, "全部信源": None,
    "fund": "公募", "公募": "公募", "基金": "公募",
    "sec": "券商", "券商": "券商", "证券": "券商",
    "qh": "期货", "期货": "期货",
    "insurance": "保险集团", "保险": "保险集团", "保险集团": "保险集团",
    "综合金融": "综合金融",
    "资管": "资管",  # 资管 = 公募+保险集团+综合金融（资管视角的组合方向）
}


def select_sources(direction):
    """按方向选信源。资管 = 公募+保险集团+综合金融 的组合口径。"""
    enabled = [s for s in SOURCES if s.get("enabled")]
    if direction in (None, "all", "全部", "全部信源"):
        return enabled
    if direction == "资管":
        want = {"公募", "保险集团", "综合金融", "养老金"}
        return [s for s in enabled if s["org_type"] in want]
    want = DIRECTION_MAP.get(direction)
    if want is None:
        raise SystemExit(f"未知方向：{direction}（可选：all/公募/券商/保险/综合金融/资管）")
    return [s for s in enabled if s["org_type"] == want]
