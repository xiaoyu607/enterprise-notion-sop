"""Eight database schemas transcribed from the supplied deployment workbook."""


def spec(filename, title, identity, columns):
    fields = [tuple(item.split(":")) for item in columns.split("|")]
    return {"file": filename, "title": title, "identity": identity, "fields": fields}


DATABASES = {
    "roles": spec("01-岗位目录", "岗位名称", "岗位名称", "岗位名称:title|部门:select|岗位使命:text|直属上级:text|关键职责:text|岗位负责人:person|版本:text|状态:select|备注:text"),
    "sops": spec("02-岗位SOP", "SOP标题", "SOP编号", "SOP标题:title|SOP编号:text|部门:select|关联岗位:relation|流程类别:select|适用范围:text|触发条件:text|完成标准:text|负责人:person|审核人:person|状态:select|版本:text|生效日期:date|复审日期:date|标签:multi_select|正文文件:text"),
    "processes": spec("03-跨部门流程", "流程名称", "流程编号", "流程名称:title|流程编号:text|牵头部门:select|参与部门:multi_select|开始条件:text|阶段:select|交接内容:text|完成标准:text|流程负责人:person|状态:select|版本:text|风险点:text"),
    "tasks": spec("04-项目与任务", "任务名称", "任务名称", "任务名称:title|项目:text|关联流程编号:relation|部门:select|负责人:person|优先级:select|状态:select|计划开始:date|截止日期:date|验收标准:text|阻塞原因:text|备注:text"),
    "training": spec("05-培训与考核", "课程/SOP名称", "课程/SOP名称", "课程/SOP名称:title|培训对象岗位:relation|部门:select|培训负责人:person|培训方式:select|计划日期:date|完成日期:date|参加人数:number|合格标准:text|是否合格:select|复训日期:date|备注:text"),
    "knowledge": spec("06-企业知识库", "知识条目名称", "知识条目名称", "知识条目名称:title|分类:select|部门:select|关键词:multi_select|内容摘要:text|内容负责人:person|保密等级:select|审核状态:select|版本:text|下次复审:date|关联SOP编号:relation"),
    "changes": spec("07-变更与问题", "问题/变更标题", "问题/变更标题", "问题/变更标题:title|关联SOP编号:relation|问题类型:select|发现人:person|发现日期:date|严重程度:select|负责人:person|处理状态:select|建议改动:text|审核结果:select|关闭日期:date|版本变更:text"),
    "implementation": spec("08-实施追踪", "任务", "任务", "任务:title|阶段:select|建议日期:date|负责角色:text|优先级:select|状态:select|交付物:text|验收方式:text|备注:text"),
}

RELATIONS = {
    ("sops", "关联岗位"): "roles",
    ("tasks", "关联流程编号"): "processes",
    ("training", "培训对象岗位"): "roles",
    ("knowledge", "关联SOP编号"): "sops",
    ("changes", "关联SOP编号"): "sops",
}

VIEWS = {
    "roles": ["在用岗位：状态=在用，按部门分组", "待确认岗位：状态≠在用"],
    "sops": ["待审核：状态=待审核", "已发布：状态=已发布", "待复审：状态=已发布且复审日期不晚于今天"],
    "processes": ["进行中：状态=进行中，按牵头部门分组"],
    "tasks": ["任务看板：按状态分组", "逾期：截止日期早于今天且状态≠已完成且状态≠已取消"],
    "training": ["培训日历：计划日期", "待复训：复训日期不晚于今天"],
    "knowledge": ["待审核：审核状态=待审核", "待复审：下次复审不晚于今天"],
    "changes": ["未关闭：处理状态≠已关闭，按严重程度排序"],
    "implementation": ["实施看板：按阶段分组", "未完成：状态≠已完成"],
}

IMPLEMENTATION_TASKS = [
    ("D1", "确认范围与试点岗位", "需求确认单", "管理层确认边界"),
    ("D1", "收集与访谈", "资料目录与访谈纪要", "主管和执行者交叉核对"),
    ("D2", "设计8库与首页", "字段与导航", "8类数据库可定位"),
    ("D2", "确定版本与审核原则", "审核规则", "未经审核不得发布"),
    ("D3", "导入并配置字段视图", "导入记录", "核对字段、日期和记录数"),
    ("D4", "编写真实SOP", "3–5份试点初稿", "步骤、标准、异常完整"),
    ("D4", "主管审核", "批准记录", "责任人、审核人与版本明确"),
    ("D5", "权限与提醒", "测试日志", "普通员工和管理员分别测试"),
    ("D6", "岗位实操与访问测试", "验收记录", "真实网络和真实角色测试"),
    ("D7", "培训与管理员交接", "培训签收与备份", "企业拥有管理员权限"),
    ("D7", "验收与维护约定", "书面验收单", "复审周期与责任人明确"),
]
