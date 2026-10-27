# 配置约定 / Configuration contract

仅修改 company_config.json 即可定制客户。首次运行自动从公开 example 建立本机配置；框架、字段名和测试不需改动。正式客户文件不会进入Git提交。 / Customise only the local company_config.json. The first run creates it from the generic example; it is excluded from Git.

必填根字段：schema_version=1；company_name；英文小写 company_slug；reference_date（YYYY-MM-DD）；departments（非空且不重复）；review_cycle_days（1–3660整数）；data（完整8类数组）。没有资料的数据库保留空数组。 / Keep all eight data arrays, using empty arrays for unavailable records.

8类键：roles、sops、processes、tasks、training、knowledge、changes、implementation。属性名见字段字典与 schema.py。每条记录至少有标题与身份字段；SOP编号和流程编号另需填写。关联字段用目标身份值，多个值用英文分号分隔，必须能在同一配置找到目标记录。

生产记录禁止【演示】和 DEMO- 标记。日期输入用 ISO；CSV 为 MM/DD/YYYY。人员名字暂为文本，不自动建立用户。人数为非负整数。不要把密码、令牌或支付资料放入配置。

## 纯虚构的正式模式测试数据 / Synthetic production-mode example

下例仅解释格式，不是客户资料。可将内容合并到临时测试配置，正式客户必须替换成已授权的真实事实。 / This illustrates the production format using fictional test data, not real client facts.

```json
{
  "roles": [
    {"岗位名称": "支持专员", "部门": "客户支持组", "状态": "在用"}
  ],
  "sops": [
    {
      "SOP编号": "SUP-001",
      "SOP标题": "处理咨询",
      "部门": "客户支持组",
      "关联岗位": "支持专员",
      "状态": "草稿",
      "版本": "0.1",
      "正文": {
        "目的": "准确记录咨询",
        "触发条件": "收到已授权请求",
        "步骤": [
          {"操作": "核对请求", "完成标准": "输入齐全", "异常处理": "缺项退回"}
        ],
        "完成标准": "答复与交接有记录",
        "异常升级": "提交岗位主管"
      }
    }
  ]
}
```

配置 departments 中须存在客户支持组，其他6类 data 键仍须保留。不要手填正文文件路径，程序根据正文对象生成 SOP正文/SUP-001.md。没有正文的草稿可以保留，但不能通过正文审核；已发布记录必须有正文、负责人、审核人、版本、生效日期和复审日期。这些字段齐全也不能证明企业真的批准了该制度。

CSV将 title 属性排首列，故SOP编号不再是首列，实施追踪以任务为首列；原字段全部保留。 / Title properties are first in CSVs, while preserving every source field.

身份字段不能有首尾空白，大小写归一后也须唯一，避免Mac文件名冲突。SOP状态仅允许：草稿、待审核、已发布、待修订、归档。选择值不能带首尾空白或换行。 / Identifiers must be unique after case folding; trim-free status values prevent ambiguous review checks and case-insensitive filename collisions.

Notion无法直接从本配置推导成员权限或法律/业务批准。独立客户的配置、ZIP和测试页面必须分离。 / Configuration is not authority for member access or business approval; isolate client copies and outputs.
