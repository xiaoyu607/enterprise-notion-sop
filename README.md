# 企业 Notion 管理工作 Skill / Enterprise Notion SOP

**XY-SKILL-003 · v0.1.0 Beta · 姚明宇制作 / Created by Yaomingyu**

把企业岗位、SOP、跨部门流程、任务、培训、知识库、变更和实施追踪整理为可复用的 Notion 配置项目。客户定制只改一个本机配置文件，生成分开的演示/正式 ZIP，由管理员手动导入并完成权限与业务验收。

A reusable local framework for eight enterprise SOP databases: roles, SOPs, cross-team processes, tasks, training, knowledge, changes, and implementation tracking. Customise one local JSON configuration, build separate demo and production ZIPs, then import and configure them in Notion.

## 快速开始 / Quick start

Python 3.10+，只用标准库，无 API Key、无第三方依赖。 / Python 3.10+, standard library only, no API key or external packages.

```bash
python3 build_template.py
python3 tests/test_template.py
```

首次从仓库下载后，构建命令自动从通用 `company_config.example.json` 建立本机的 `company_config.json`，不覆盖已有文件。以后只改该本机文件即可。输出在 `dist/<企业短名>-<时间>-<随机后缀>/`，每次生成新目录，保留旧产物。

On a fresh clone, the first build creates a local `company_config.json` from the generic example without overwriting existing files. Edit that local file for each client. Every build writes a new directory under `dist/` and preserves earlier outputs.

每次输出 / Each build contains:

- `Notion_<短名>_demo.zip`：8个CSV、28条虚构演示记录、10份说明页、3份演示SOP正文。
- `Notion_<短名>_production.zip`：同样8库和10份说明，记录仅来自配置的 `data`；默认无正式记录、无虚构SOP正文。
- 解压后的 `demo/`、`production/` 和 `build_report.json`，包含数量、大小、SHA-256与未进行线上验收的标记。

The demo ZIP has 8 CSVs, 28 explicitly labelled synthetic rows, 10 guide pages, and 3 sample SOP bodies. The production ZIP uses only `data` from your configuration; its default is empty. Unpacked folders and a build report provide counts and SHA-256 hashes. Build success is not live Notion acceptance.

## 客户定制 / Client configuration

为每位客户复制一个独立本机目录，仅编辑 `company_config.json`。修改企业名称、英文短名、部门、参考日期、复审天数与 `data` 中8类记录。配置字段说明及正式SOP示例见 [配置约定](references/configuration.md)。

Use an isolated local copy for each client and edit only `company_config.json`: company name/slug, departments, reference date, review interval, and the eight `data` arrays. See the [configuration contract](references/configuration.md), including a synthetic production-record example.

```bash
python3 build_template.py --config /path/to/client/company_config.json --output /path/to/private-output
```

公开仓库不包含客户配置或构建产物；这些路径已在 `.gitignore` 中排除。示例配置始终保留为通用空正式数据。不要把真实客户资料放进示例、测试、公开 Issue 或 GitHub 提交。

Client configuration and generated output are excluded from Git by default. Keep the public example generic and production data empty. Do not put real client information into examples, tests, public issues, or commits.

## 手动导入 Notion / Manual import

在 Notion 的 Settings → Import 选择 ZIP（Convert Zip to pages），上传一个模式的ZIP。检查8库和正文；若CSV未转换成数据库，解压后逐个使用 CSV 导入。**只有表头的正式CSV若被拒绝，按字段字典手动创建8个空库**，不要填演示行充数。完整步骤见 [05-配置步骤](notion_import/05-配置步骤.md)。

Use Notion Settings → Import → ZIP, then check the eight databases and SOP pages. If CSVs are not converted, import them individually. If a header-only production CSV is rejected, create the empty database from the field dictionary. See the [setup guide](notion_import/05-配置步骤.md).

导入后还要配置字段类型、人员映射、Relation、视图、权限、审批记录、提醒和首页导航。CSV中的正文路径不会自动绑定SOP页面。导入/合并CSV会新增记录，重试前先检查部分成功内容，避免重复。[官方导入说明](https://www.notion.com/help/import-data-into-notion)

After import, configure property types, people, relations, views, permissions, approval records, reminders, and navigation. SOP paths are not automatic page bindings. CSV import adds records, so inspect partial results before retrying. [Official import documentation](https://www.notion.com/help/import-data-into-notion).

## 作为 Skill 使用 / Use as a Skill

把仓库放入你的本地 Skills 目录，或让 Codex 读取 `SKILL.md` 按其执行。 / Install the repository as a local skill folder, or ask Codex to read and follow `SKILL.md`.

```text
使用 $enterprise-notion-sop，根据这家企业已授权的资料完善 company_config.json，
保留8类数据库，区分演示和正式数据，构建、测试并告诉我哪些Notion配置尚未验收。
```

```text
Use $enterprise-notion-sop to configure the eight databases from the client's
authorised materials, separate demo and production data, build and test the ZIPs,
and report the Notion setup steps that still require acceptance.
```

当前只提供本机生成和手动导入流程；未连接或写入真实 Notion，未实现API部署器。7天仅为3–5岗位试点的估算，主管业务审批、真实网络、权限和员工实操仍需现场验证。

This version generates local bundles for manual import. No live Notion write or API provisioner is implemented. Seven days is a planning estimate for a small pilot, subject to real materials, business approval, access tests, and staff exercises.

## 项目结构 / Structure

```text
notion_sop_workspace/
  SKILL.md                    Skill instructions
  company_config.example.json Public generic configuration
  company_config.json         Local client configuration (ignored)
  schema.py                   Eight database schemas
  build_template.py           Local builder
  notion_import/              Ten import-guide templates
  references/                 Configuration and validation notes
  tests/test_template.py      Offline functional tests
  dist/                       Generated client output (ignored)
```

验证范围与纠错记录见 [validation.md](references/validation.md)。原始工作簿仅作为本机设计依据，未作为运行依赖或客户数据上传。 / See the [validation record](references/validation.md). The supplied workbook informed the schema locally and is not a runtime dependency or uploaded client dataset.

[MIT License](LICENSE).
