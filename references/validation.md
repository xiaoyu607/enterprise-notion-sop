# 验证范围 / Validation scope

Version: 0.1.0 Beta. Design date: 2026-10-27.

字段来自用户提供的部署工作簿「04-数据库结构」：8库字段数为9、16、12、12、12、11、12、9。保留所有字段，调整CSV标题列顺序。原工作簿未修改，源文件不作为发布依赖。

本地验证包括：8库模式、两种独立ZIP、CSV编码/列数、演示标题、正式数据隔离、SOP正文与链接、配置定制、日期、无效配置、关联完整性、已发布字段、中文空格路径、重复构建保留旧输出及内容一致性。

运行 `python3 tests/test_template.py` 可复现。测试均使用纯虚构资料，无真实企业记录。测试结果与实际产物另存本机交付记录；不把未进行的Notion导入、权限测试或业务验收写为已完成。

The offline suite verifies schemas, data-mode isolation, CSV/ZIP integrity, configurable clients, SOP bodies, invalid inputs, and non-destructive rebuilds. All fixtures are synthetic. Live Notion import and business/permission acceptance require a separately authorised workspace and are not established by these tests.

## 独立演练与纠错 / Independent dry run and corrections

独立代理仅修改临时虚构客户配置，完成8类业务记录与SOP正文的生成，检查两种模式各8个CSV、ZIP CRC、正文链接与数据隔离。发现并修复两处缺陷：状态尾随空白绕过发布字段检查；SOP编号大小写不同导致Mac正文文件冲突。现已在写入前拒绝这两类配置，并加入回归测试。还验证了全新源码下载后自动创建本机配置、不覆盖客户修改。

An independent synthetic-client run exercised all eight database types and found two defects: trailing whitespace bypassing publication checks and case-colliding SOP filenames. Both are now rejected before output, with regression coverage. The suite also tests fresh-download configuration bootstrapping and preservation of client edits.

官方参考（2026-10-27核验）：[导入说明](https://www.notion.com/help/import-data-into-notion)、[关系与汇总](https://www.notion.com/help/relations-and-rollups)。
