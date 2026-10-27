"""Offline functional tests; all organizations, people and records are synthetic."""
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest
from urllib.parse import unquote
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build_template as builder
from schema import DATABASES


class TemplateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.config = json.loads((ROOT / "company_config.example.json").read_text(encoding="utf-8"))

    def write_config(self, c=None):
        p = self.folder / "company_config.json"
        p.write_text(json.dumps(c or self.config, ensure_ascii=False), encoding="utf-8")
        return p

    def formal_config(self):
        c = copy.deepcopy(self.config)
        c["company_name"] = "虚构测试企业甲"
        c["company_slug"] = "synthetic-alpha"
        c["departments"] = ["客户支持组"]
        c["data"]["roles"] = [{"岗位名称": "支持专员", "部门": "客户支持组", "状态": "在用"}]
        c["data"]["sops"] = [{"SOP编号": "SUP-001", "SOP标题": "处理咨询", "关联岗位": "支持专员", "部门": "客户支持组", "负责人": "虚构负责人甲", "审核人": "虚构审核人乙", "版本": "1.0", "状态": "已发布", "生效日期": "2026-10-27", "复审日期": "2027-01-27", "正文": {"目的": "回答已授权问题", "触发条件": "收到咨询", "步骤": [{"操作": "核对咨询内容", "完成标准": "问题分类准确", "异常处理": "无法判断时升级"}], "完成标准": "用户收到可核验答复", "异常升级": "提交指定主管"}}]
        return c

    def test_schema_matches_workbook_fields(self):
        self.assertEqual([len(s["fields"]) for s in DATABASES.values()], [9, 16, 12, 12, 12, 11, 12, 9])
        self.assertEqual(len(DATABASES), 8)
        self.assertTrue(all(s["fields"][0] == (s["title"], "title") for s in DATABASES.values()))

    def test_build_two_zips_and_exact_csv_schema(self):
        target, report = builder.build(self.write_config(), self.folder / "out")
        self.assertEqual(len(list(target.glob("*.zip"))), 2)
        for mode in ["demo", "production"]:
            p = target / f"Notion_company-template_{mode}.zip"
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), report["packages"][mode]["sha256"])
            with zipfile.ZipFile(p) as z:
                self.assertIsNone(z.testzip())
                csv_names = [x for x in z.namelist() if x.endswith(".csv")]
                self.assertEqual(len(csv_names), 8)
                self.assertEqual(len([x for x in z.namelist() if x.endswith(".md") and "/SOP正文/" not in x]), 10)
                for key, spec in DATABASES.items():
                    content = z.read(f"company-template-{mode}/数据库/{spec['file']}.csv")
                    self.assertTrue(content.startswith(b"\xef\xbb\xbf"))
                    rows = list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))
                    self.assertEqual(rows[0], [n for n, _ in spec["fields"]])
                    self.assertTrue(all(len(r) == len(rows[0]) for r in rows))
                    if mode == "production":
                        self.assertEqual(len(rows), 1)
                    else:
                        self.assertTrue(all(r[0].startswith("【演示】") for r in rows[1:]))
        self.assertEqual(list(report["packages"]["demo"]["records"].values()), [4, 3, 2, 3, 2, 2, 1, 11])
        self.assertEqual(report["packages"]["demo"]["sop_body_count"], 3)
        self.assertFalse(report["live_notion_tested"])

    def test_client_changes_only_config_and_modes_do_not_leak(self):
        c = self.formal_config()
        builder.validate_config(c)
        target, _ = builder.build(self.write_config(c), self.folder / "out")
        with zipfile.ZipFile(target / "Notion_synthetic-alpha_production.zip") as z:
            body = z.read("synthetic-alpha-production/SOP正文/SUP-001.md").decode()
            self.assertIn("处理咨询", body)
            self.assertNotIn("【演示】", body)
            csv_text = z.read("synthetic-alpha-production/数据库/02-岗位SOP.csv").decode("utf-8-sig")
            row = list(csv.DictReader(io.StringIO(csv_text)))[0]
            self.assertEqual(row["生效日期"], "10/27/2026")
            self.assertEqual(row["正文文件"], "SOP正文/SUP-001.md")
            self.assertIn("虚构测试企业甲", z.read("synthetic-alpha-production/00-企业首页.md").decode())
        with zipfile.ZipFile(target / "Notion_synthetic-alpha_demo.zip") as z:
            selected = b"\n".join(z.read(x) for x in z.namelist() if x.endswith(".csv") or "/SOP正文/" in x).decode("utf-8-sig")
            self.assertNotIn("虚构负责人甲", selected)
            self.assertNotIn("SUP-001", selected)

    def test_sop_body_links_resolve(self):
        files, _ = builder.render_package(self.config, "demo")
        text = files["数据库/02-岗位SOP.csv"].decode("utf-8-sig")
        for r in csv.DictReader(io.StringIO(text)):
            self.assertIn(r["正文文件"], files)
        for spec in DATABASES.values():
            self.assertIn(f"数据库/{spec['file']}.csv", unquote(files["00-企业首页.md"].decode()))

    def test_rebuild_preserves_old_outputs_and_is_deterministic(self):
        p = self.write_config()
        before = p.read_bytes()
        first, _ = builder.build(p, self.folder / "out")
        saved = {x.name: x.read_bytes() for x in first.glob("*.zip")}
        second, _ = builder.build(p, self.folder / "out")
        self.assertNotEqual(first, second)
        self.assertEqual(before, p.read_bytes())
        for name, content in saved.items():
            self.assertEqual((first / name).read_bytes(), content)
            self.assertEqual((second / name).read_bytes(), content)

    def test_invalid_configs_write_nothing(self):
        mutations = [
            lambda c: c.update(company_slug="../../private"),
            lambda c: c.update(reference_date="2026-02-30"),
            lambda c: c.update(review_cycle_days=True),
            lambda c: c["data"].pop("changes"),
            lambda c: c["data"].update(roles=[{"岗位名称": "【演示】角色"}]),
            lambda c: c["data"].update(roles=[{"岗位名称": "角色", "部门": "不存在"}]),
            lambda c: c["data"].update(roles=[{"岗位名称": "角色", "未知字段": "x"}]),
            lambda c: c["data"].update(roles=[{"岗位名称": "角色"}, {"岗位名称": "角色"}]),
            lambda c: c["data"].update(roles=[{"岗位名称": "=1+1"}]),
            lambda c: c["data"].update(sops=[{"SOP编号": "../../evil", "SOP标题": "标题"}]),
            lambda c: c["data"].update(sops=[{"SOP编号": "S1", "SOP标题": "标题", "关联岗位": "不存在"}]),
            lambda c: c["data"].update(sops=[{"SOP编号": "S1", "SOP标题": "标题", "状态": "已发布"}]),
            lambda c: c["data"].update(tasks=[{"任务名称": "任务", "计划开始": "2026-10-28", "截止日期": "2026-10-27"}]),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                c = copy.deepcopy(self.config)
                mutate(c)
                with self.assertRaises(builder.ConfigError):
                    builder.build(self.write_config(c), self.folder / "never-created")
                self.assertFalse((self.folder / "never-created").exists())

    def test_empty_or_demo_body_is_rejected_for_production(self):
        for field, value in [("步骤", []), ("目的", "【演示】不是真实"), ("异常升级", "")]:
            c = self.formal_config()
            c["data"]["sops"][0]["正文"][field] = value
            with self.assertRaises(builder.ConfigError):
                builder.validate_config(c)

    def test_missing_approval_information_fails(self):
        for field in ["负责人", "审核人", "版本", "生效日期", "复审日期", "正文"]:
            c = self.formal_config()
            del c["data"]["sops"][0][field]
            with self.assertRaises(builder.ConfigError):
                builder.validate_config(c)
        for field in ["负责人", "审核人", "版本"]:
            c = self.formal_config()
            c["data"]["sops"][0][field] = " "
            with self.assertRaises(builder.ConfigError):
                builder.validate_config(c)

    def test_duplicate_json_key_rejected(self):
        p = self.folder / "bad.json"
        p.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
        with self.assertRaises(builder.ConfigError):
            builder.load_config(p)

    def test_csv_roundtrip_quotes_comma_newline_and_chinese(self):
        c = self.formal_config()
        c["data"]["roles"][0]["备注"] = '中文,"带逗号"\n第二行'
        files, _ = builder.render_package(c, "production")
        r = list(csv.DictReader(io.StringIO(files["数据库/01-岗位目录.csv"].decode("utf-8-sig"))))[0]
        self.assertEqual(r["备注"], c["data"]["roles"][0]["备注"])

    def test_cli_from_different_directory(self):
        p = self.write_config()
        result = subprocess.run([sys.executable, str(ROOT / "build_template.py"), "--config", str(p), "--output", str(self.folder / "中文 空格")], cwd=self.folder, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(Path(json.loads(result.stdout)["output"]).exists())

    def test_fresh_download_bootstraps_local_config_and_preserves_it(self):
        clone = self.folder / "fresh"
        clone.mkdir()
        for name in ["build_template.py", "schema.py", "company_config.example.json"]:
            shutil.copyfile(ROOT / name, clone / name)
        shutil.copytree(ROOT / "notion_import", clone / "notion_import")
        cmd = [sys.executable, str(clone / "build_template.py")]
        result = subprocess.run(cmd, cwd=self.folder, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        local = clone / "company_config.json"
        c = json.loads(local.read_text(encoding="utf-8"))
        c["company_name"] = "虚构客户乙"
        local.write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")
        saved = local.read_bytes()
        result = subprocess.run(cmd, cwd=self.folder, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(saved, local.read_bytes())

    def test_published_status_whitespace_cannot_bypass_review(self):
        for status in ["已发布 ", " 已发布", "已发布\n", "已发布\u3000", "已發佈"]:
            c = copy.deepcopy(self.config)
            c["data"]["sops"] = [{"SOP编号": "S-001", "SOP标题": "虚构测试SOP", "状态": status}]
            with self.subTest(status=status), self.assertRaises(builder.ConfigError):
                builder.build(self.write_config(c), self.folder / "rejected-status")
            self.assertFalse((self.folder / "rejected-status").exists())

    def test_sop_case_collision_is_rejected_before_output(self):
        c = self.formal_config()
        other = copy.deepcopy(c["data"]["sops"][0])
        other["SOP编号"] = "sup-001"
        c["data"]["sops"].append(other)
        with self.assertRaises(builder.ConfigError):
            builder.build(self.write_config(c), self.folder / "rejected-collision")
        self.assertFalse((self.folder / "rejected-collision").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
