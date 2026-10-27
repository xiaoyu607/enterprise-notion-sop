#!/usr/bin/env python3
"""Build separate Notion demo and production import bundles. Standard library only."""
from __future__ import annotations

import argparse
import copy
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote
import uuid
import zipfile

from schema import DATABASES, RELATIONS, VIEWS, IMPLEMENTATION_TASKS

ROOT = Path(__file__).resolve().parent
MARKER = "【演示】"
BODY_FIELDS = {"目的", "触发条件", "步骤", "完成标准", "异常升级"}


class ConfigError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ConfigError(message)


def load_config(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "配置存在重复字段")
            result[key] = value
        return result
    try:
        config = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigError("无法读取有效 UTF-8 JSON 配置；未输出配置内容") from exc
    validate_config(config)
    return config


def valid_date(value):
    require(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value), "日期必须为 YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ConfigError("日期不存在") from exc


def validate_config(c):
    require(isinstance(c, dict), "配置必须是对象")
    require(set(c) == {"schema_version", "company_name", "company_slug", "reference_date", "departments", "review_cycle_days", "data"}, "配置字段不匹配；请对照 company_config.json")
    require(type(c["schema_version"]) is int and c["schema_version"] == 1, "不支持的配置版本")
    require(isinstance(c["company_name"], str) and c["company_name"].strip() and len(c["company_name"]) <= 120, "企业名称应为1–120字符")
    require(isinstance(c["company_slug"], str) and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", c["company_slug"]) and len(c["company_slug"]) <= 60, "company_slug 必须是最多60字符的英文小写短名")
    valid_date(c["reference_date"])
    require(type(c["review_cycle_days"]) is int and 1 <= c["review_cycle_days"] <= 3660, "复审天数须在1–3660之间")
    require(isinstance(c["departments"], list) and c["departments"] and all(isinstance(x, str) and x.strip() for x in c["departments"]), "部门清单不能为空")
    require(len(set(c["departments"])) == len(c["departments"]), "部门不能重复")
    require(isinstance(c["data"], dict) and set(c["data"]) == set(DATABASES), "data 必须保留8类数据库")
    for key, spec in DATABASES.items():
        rows = c["data"][key]
        require(isinstance(rows, list), f"{key} 必须为记录数组")
        require(len(rows) <= 5000, f"{key} 超过单库5000条的本地模板上限")
        fields = dict(spec["fields"])
        ids = set()
        for index, row in enumerate(rows, 1):
            label = f"{key} 第{index}条"
            require(isinstance(row, dict), label + "必须是对象")
            require(set(row) <= set(fields) | ({"正文"} if key == "sops" else set()), label + "存在未知字段")
            for mandatory in {spec["title"], spec["identity"]}:
                require(isinstance(row.get(mandatory), str) and row[mandatory].strip(), label + "缺少标题或唯一标识")
            identity = row[spec["identity"]]
            require(identity == identity.strip(), label + "唯一标识不能有首尾空白")
            require(identity.casefold() not in ids, label + "唯一标识重复或大小写冲突")
            ids.add(identity.casefold())
            for field, value in row.items():
                if field == "正文":
                    continue
                require(isinstance(value, str) or type(value) is int, label + "字段仅支持文本或整数")
                require(MARKER not in str(value) and "DEMO-" not in str(value), label + "正式数据含演示标记")
                require("\x00" not in str(value), label + "含不支持的空字符")
                if fields.get(field) == "select":
                    require(isinstance(value, str) and value == value.strip() and "\n" not in value and "\r" not in value, label + "选项值不能有首尾空白或换行")
                require(not re.match(r"^[\s]*[=+@]", str(value)), label + "含疑似表格公式，请改为普通说明文字")
                if fields.get(field) == "date" and value != "":
                    valid_date(value)
                if fields.get(field) == "number" and value != "":
                    require(type(value) is int and value >= 0, label + "人数须为非负整数")
                if field in {"部门", "牵头部门"} and value:
                    require(value in c["departments"], label + "部门不在配置清单内")
                if field == "参与部门" and value:
                    require(all(x.strip() in c["departments"] for x in str(value).split(";")), label + "参与部门须用分号分隔且在清单内")
            for start, end in [("计划开始", "截止日期"), ("生效日期", "复审日期"), ("计划日期", "完成日期"), ("发现日期", "关闭日期")]:
                if row.get(start) and row.get(end):
                    require(valid_date(row[start]) <= valid_date(row[end]), label + "日期先后矛盾")
            if key == "sops":
                require(row.get("状态", "草稿") in {"草稿", "待审核", "已发布", "待修订", "归档"}, label + "SOP状态必须使用既定选项")
                require(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", identity), label + "SOP编号仅允许字母数字下划线和短横线")
                require(not row.get("正文文件"), label + "正文文件由程序生成，请改填正文对象")
                body = row.get("正文")
                if body is not None:
                    validate_body(body, label)
                if row.get("状态") == "已发布":
                    require(body and all(str(row.get(f, "")).strip() for f in ["负责人", "审核人", "版本", "生效日期", "复审日期"]), label + "已发布SOP缺少正文、责任人、审核人、版本或日期")
                    require(row["负责人"] != "待确认" and row["审核人"] != "待确认", label + "已发布SOP仍有待确认人员")
    for (key, field), target in RELATIONS.items():
        known = {r[DATABASES[target]["identity"]] for r in c["data"][target]}
        for row in c["data"][key]:
            refs = str(row.get(field, ""))
            if refs:
                require(all(x.strip() in known for x in refs.split(";")), f"{key}.{field} 有未定义关联；请先录入目标记录")


def validate_body(body, label):
    require(isinstance(body, dict) and set(body) == BODY_FIELDS, label + "正文须含目的、触发条件、步骤、完成标准、异常升级")
    require(all(isinstance(body[k], str) and body[k].strip() for k in BODY_FIELDS - {"步骤"}), label + "正文说明不能为空")
    require(isinstance(body["步骤"], list) and body["步骤"], label + "正文步骤不能为空")
    for step in body["步骤"]:
        require(isinstance(step, dict) and set(step) == {"操作", "完成标准", "异常处理"} and all(isinstance(v, str) and v.strip() for v in step.values()), label + "每步须含操作、完成标准和异常处理")
    require(MARKER not in json.dumps(body, ensure_ascii=False) and "DEMO-" not in json.dumps(body), label + "正式正文含演示标记")


def demo_data(c):
    data = {key: [] for key in DATABASES}
    departments = (c["departments"] * 3)[:3]
    today = valid_date(c["reference_date"])
    review = (today + timedelta(days=c["review_cycle_days"])).isoformat()
    for i, title in enumerate(["销售专员", "设计师", "行政管理员", "业务主管"]):
        data["roles"].append({"岗位名称": MARKER + title, "部门": departments[min(i, 2)], "岗位使命": "样例：明确职责与交接", "关键职责": "样例：执行、记录、反馈", "岗位负责人": "待确认", "版本": "0.1", "状态": "草稿", "备注": "纯虚构样例，不能作为客户真实岗位"})
    for i, title in enumerate(["销售线索交接", "设计文件交付", "离职账号回收"]):
        data["sops"].append({"SOP标题": MARKER + title, "SOP编号": f"DEMO-SOP-{i+1:03}", "部门": departments[i], "关联岗位": data["roles"][i]["岗位名称"], "流程类别": "样例流程", "适用范围": "演示环境", "触发条件": "样例：收到明确请求", "完成标准": "样例：记录齐全并取得接收确认", "负责人": "待确认", "审核人": "待确认", "状态": "草稿", "版本": "0.1", "复审日期": review, "标签": "样例", "正文": {"目的": f"说明{title}的样例结构", "触发条件": "接到已授权请求", "步骤": [{"操作": "核对请求范围与所需资料", "完成标准": "输入清单齐全", "异常处理": "缺项退回补充"}, {"操作": "执行交接并记录交付内容", "完成标准": "有交付记录与接收人", "异常处理": "失败时保留记录并升级主管"}, {"操作": "接收人核验并关闭任务", "完成标准": "明确验收结果", "异常处理": "未确认不标记完成"}], "完成标准": "样例：交接和验收均有记录", "异常升级": "向岗位主管说明影响，按企业规则决定后续动作"}})
    for i, title in enumerate(["销售到设计交接", "账号权限回收"]):
        data["processes"].append({"流程名称": MARKER + title, "流程编号": f"DEMO-PROC-{i+1:03}", "牵头部门": departments[i], "参与部门": ";".join(dict.fromkeys(departments)), "开始条件": "样例请求已确认", "阶段": "待开始", "交接内容": "样例资料清单", "完成标准": "交接双方确认", "流程负责人": "待确认", "状态": "草稿", "版本": "0.1", "风险点": "样例：输入缺失或交付版本错误"})
    for i in range(3):
        data["tasks"].append({"任务名称": MARKER + f"试点任务{i+1}", "项目": "样例试点", "关联流程编号": "DEMO-PROC-001", "部门": departments[i], "负责人": "待确认", "优先级": "高", "状态": "待开始", "计划开始": today.isoformat(), "截止日期": (today + timedelta(days=7)).isoformat(), "验收标准": "样例：产出可核验", "备注": "纯虚构样例"})
    for i in range(2):
        data["training"].append({"课程/SOP名称": MARKER + f"试点培训{i+1}", "培训对象岗位": data["roles"][i]["岗位名称"], "部门": departments[i], "培训负责人": "待确认", "培训方式": "实操", "计划日期": today.isoformat(), "参加人数": 0, "合格标准": "样例：独立完成模拟任务", "是否合格": "待考核", "备注": "样例人数0不代表实际参加人数"})
        data["knowledge"].append({"知识条目名称": MARKER + f"交接知识{i+1}", "分类": "样例", "部门": departments[i], "关键词": "样例;交接", "内容摘要": "样例：检查输入、记录动作、确认结果", "内容负责人": "待确认", "保密等级": "内部", "审核状态": "草稿", "版本": "0.1", "下次复审": review, "关联SOP编号": f"DEMO-SOP-{i+1:03}"})
    data["changes"].append({"问题/变更标题": MARKER + "交接清单缺项", "关联SOP编号": "DEMO-SOP-001", "问题类型": "内容改进", "发现人": "待确认", "发现日期": today.isoformat(), "严重程度": "中", "负责人": "待确认", "处理状态": "待处理", "建议改动": "样例：增加版本确认", "审核结果": "待审核"})
    for phase, task, output, check in IMPLEMENTATION_TASKS:
        data["implementation"].append({"任务": MARKER + task, "阶段": phase, "建议日期": (today + timedelta(days=int(phase[1:])-1)).isoformat(), "负责角色": "待确认", "优先级": "高", "状态": "待开始", "交付物": output, "验收方式": check, "备注": "样例建议排期，非客户承诺"})
    return data


def body_markdown(row, mode):
    body = row["正文"]
    text = f"# {row['SOP标题']}\n\n"
    text += "纯虚构样例，未经企业业务审核，不可当作正式制度。\n\n" if mode == "demo" else "正文由配置提供；业务批准情况以企业真实审核记录为准。\n\n"
    text += f"编号：{row['SOP编号']}；版本：{row.get('版本', '')}；状态：{row.get('状态', '草稿')}\n\n"
    for key in ["目的", "触发条件"]:
        text += f"## {key}\n\n{body[key]}\n\n"
    text += "## 操作步骤\n\n"
    for i, step in enumerate(body["步骤"], 1):
        text += f"### {i}. {step['操作']}\n\n完成标准：{step['完成标准']}\n\n异常处理：{step['异常处理']}\n\n"
    for key in ["完成标准", "异常升级"]:
        text += f"## {key}\n\n{body[key]}\n\n"
    return text


def render_package(c, mode):
    require(mode in {"demo", "production"}, "未知数据模式")
    rows = demo_data(c) if mode == "demo" else copy.deepcopy(c["data"])
    files = {}
    for key, spec in DATABASES.items():
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=[name for name, _ in spec["fields"]], lineterminator="\n")
        writer.writeheader()
        for row in rows[key]:
            if key == "sops" and row.get("正文"):
                filename = f"SOP正文/{row['SOP编号']}.md"
                files[filename] = body_markdown(row, mode).encode("utf-8")
                row["正文文件"] = filename
            values = {}
            for name, kind in spec["fields"]:
                value = row.get(name, "")
                if kind == "date" and value:
                    value = valid_date(value).strftime("%m/%d/%Y")
                values[name] = value
            writer.writerow(values)
        files[f"数据库/{spec['file']}.csv"] = output.getvalue().encode("utf-8-sig")
    tokens = {
        "company_name": c["company_name"], "mode_label": "演示样例" if mode == "demo" else "正式数据模板",
        "reference_date": c["reference_date"], "review_cycle_days": str(c["review_cycle_days"]),
        "database_links": "\n".join(f"- [{s['file']}](数据库/{quote(s['file'])}.csv)（{len(rows[k])} 条）" for k, s in DATABASES.items()),
        "schema_table": schema_table(), "view_table": view_table(),
    }
    for path in sorted((ROOT / "notion_import").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"\{\{([a-z_]+)\}\}", lambda m: tokens[m[1]], text)
        files[path.name] = text.encode("utf-8")
    require(sum(name.endswith(".csv") for name in files) == 8, "内部错误：CSV数量不为8")
    require(sum("/" not in name and name.endswith(".md") for name in files) == 10, "内部错误：应有10份配置说明")
    return files, {k: len(v) for k, v in rows.items()}


def schema_table():
    lines = ["| 数据库 | 属性 | 建议类型 |", "|---|---|---|"]
    for spec in DATABASES.values():
        for field, kind in spec["fields"]:
            lines.append(f"| {spec['file']} | {field} | {kind} |")
    return "\n".join(lines)


def view_table():
    return "\n".join(f"- {DATABASES[key]['file']}：" + "；".join(views) for key, views in VIEWS.items())


def zip_bytes(c, mode, files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as archive:
        for path, content in sorted(files.items()):
            info = zipfile.ZipInfo(f"{c['company_slug']}-{mode}/{path}", (2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    return buf.getvalue()


def build(config_path, output_root):
    c = load_config(config_path)
    bundles = {}
    report = {"schema_version": 1, "project_id": "XY-SKILL-003", "offline_only": True, "live_notion_tested": False, "packages": {}}
    for mode in ["demo", "production"]:
        files, counts = render_package(c, mode)
        archive = zip_bytes(c, mode, files)
        bundles[mode] = (files, archive)
        report["packages"][mode] = {"csv_count": 8, "guides_count": 10, "sop_body_count": sum(x.startswith("SOP正文/") for x in files), "records": counts, "sha256": hashlib.sha256(archive).hexdigest(), "size_bytes": len(archive)}
    run = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    target = Path(output_root).expanduser().resolve() / f"{c['company_slug']}-{run}"
    # All config validation/rendering occurs before any output is created.
    target.mkdir(parents=True, exist_ok=False)
    for mode, (files, archive) in bundles.items():
        folder = target / mode
        folder.mkdir()
        for name, content in files.items():
            p = folder / name
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("xb") as handle:
                handle.write(content)
        with (target / f"Notion_{c['company_slug']}_{mode}.zip").open("xb") as handle:
            handle.write(archive)
    with (target / "build_report.json").open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    return target, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "company_config.json")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    try:
        if args.config == ROOT / "company_config.json" and not args.config.exists():
            # A clone ships only a generic example; the editable customer file stays ignored.
            with args.config.open("x", encoding="utf-8") as handle:
                handle.write((ROOT / "company_config.example.json").read_text(encoding="utf-8"))
        path, report = build(args.config, args.output)
    except (ConfigError, OSError) as exc:
        print(f"构建失败：{exc}", file=sys.stderr)
        return 1
    print(json.dumps({"output": str(path), "report": report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
