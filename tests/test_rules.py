import json
import os
import tempfile
from pathlib import Path

import pytest

from core.rule_engine import RuleEngine, RuleValidationError, RuleMatchDebugInfo


@pytest.fixture
def tmp_rules_file(tmp_path):
    rules = [
        {
            "id": "test_contains_path",
            "family": "测试",
            "match": [{"field": "image_path", "type": "contains", "value": "inetpub"}],
            "severity": "high",
            "note": "contains 匹配测试",
        },
        {
            "id": "test_regex_cmd",
            "family": "测试",
            "match": [{"field": "command_line", "type": "regex", "value": "rundll32\\.exe"}],
            "severity": "high",
            "note": "regex 匹配测试",
        },
        {
            "id": "test_equals_status",
            "family": "测试",
            "match": [{"field": "enabled", "type": "equals", "value": "disabled"}],
            "severity": "medium",
            "note": "equals 匹配测试",
        },
        {
            "id": "test_ip_equals",
            "family": "测试",
            "match": [{"field": "ip", "type": "equals", "value": "8.8.8.8"}],
            "severity": "low",
            "note": "IP equals 匹配测试",
        },
        {
            "id": "test_ip_contains",
            "family": "测试",
            "match": [{"field": "ip", "type": "contains", "value": "192.168"}],
            "severity": "low",
            "note": "IP contains 匹配测试",
        },
        {
            "id": "test_sha256_equals",
            "family": "测试",
            "match": [{"field": "sha256", "type": "equals", "value": "abc123"}],
            "severity": "low",
            "note": "sha256 equals 匹配测试",
        },
        {
            "id": "test_md5_equals",
            "family": "测试",
            "match": [{"field": "md5", "type": "equals", "value": "deadbeef"}],
            "severity": "low",
            "note": "md5 equals 匹配测试",
        },
        {
            "id": "test_multi_condition",
            "family": "测试",
            "match": [
                {"field": "image_path", "type": "contains", "value": "temp"},
                {"field": "command_line", "type": "contains", "value": "powershell"},
            ],
            "severity": "high",
            "note": "多条件 AND 匹配测试",
        },
    ]
    rules_path = tmp_path / "test_rules.json"
    rules_path.write_text(json.dumps(rules, ensure_ascii=False), encoding="utf-8")
    return str(rules_path)


@pytest.fixture
def engine(tmp_rules_file):
    return RuleEngine(rules_path=tmp_rules_file)


class TestRuleEngineLoad:

    def test_load_rules_count(self, engine):
        assert len(engine.rules) == 8

    def test_load_valid_rules(self, engine):
        assert engine.is_rules_valid()

    def test_load_nonexistent_file(self, tmp_path):
        engine = RuleEngine(rules_path=str(tmp_path / "nonexistent.json"))
        assert engine.rules == []

    def test_load_invalid_json(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json", encoding="utf-8")
        engine = RuleEngine(rules_path=str(bad_file))
        assert engine.rules == []

    def test_load_non_list_json(self, tmp_path):
        bad_file = tmp_path / "not_list.json"
        bad_file.write_text('{"key": "value"}', encoding="utf-8")
        engine = RuleEngine(rules_path=str(bad_file))
        assert engine.rules == []


class TestRuleEngineValidation:

    def test_duplicate_id_detected(self, tmp_path):
        rules = [
            {"id": "dup_id", "match": [{"field": "image_path", "type": "contains", "value": "a"}]},
            {"id": "dup_id", "match": [{"field": "image_path", "type": "contains", "value": "b"}]},
        ]
        rules_path = tmp_path / "dup_rules.json"
        rules_path.write_text(json.dumps(rules), encoding="utf-8")
        engine = RuleEngine(rules_path=str(rules_path))
        errors = engine.get_validation_errors()
        dup_errors = [e for e in errors if e["error_type"] == "duplicate_id"]
        assert len(dup_errors) == 1
        assert not engine.is_rules_valid()

    def test_missing_match_condition(self, tmp_path):
        rules = [{"id": "no_match", "match": []}]
        rules_path = tmp_path / "no_match.json"
        rules_path.write_text(json.dumps(rules), encoding="utf-8")
        engine = RuleEngine(rules_path=str(rules_path))
        errors = engine.get_validation_errors()
        match_errors = [e for e in errors if e["error_type"] == "missing_required"]
        assert len(match_errors) >= 1

    def test_invalid_regex_detected(self, tmp_path):
        rules = [{"id": "bad_regex", "match": [{"field": "command_line", "type": "regex", "value": "[invalid"}]}]
        rules_path = tmp_path / "bad_regex.json"
        rules_path.write_text(json.dumps(rules), encoding="utf-8")
        engine = RuleEngine(rules_path=str(rules_path))
        errors = engine.get_validation_errors()
        regex_errors = [e for e in errors if e["error_type"] == "regex_syntax"]
        assert len(regex_errors) == 1

    def test_empty_field_detected(self, tmp_path):
        rules = [{"id": "no_field", "match": [{"field": "", "type": "contains", "value": "test"}]}]
        rules_path = tmp_path / "no_field.json"
        rules_path.write_text(json.dumps(rules), encoding="utf-8")
        engine = RuleEngine(rules_path=str(rules_path))
        errors = engine.get_validation_errors()
        field_errors = [e for e in errors if "field" in e["field"] and e["error_type"] == "missing_required"]
        assert len(field_errors) >= 1


class TestRuleEngineMatchContains:

    def test_contains_match(self, engine):
        entry = {"image_path": r"C:\inetpub\wwwroot\shell.exe"}
        matched = engine.scan_entry(entry)
        ids = [r["id"] for r in matched]
        assert "test_contains_path" in ids

    def test_contains_no_match(self, engine):
        entry = {"image_path": r"C:\Windows\System32\cmd.exe"}
        matched = engine.scan_entry(entry)
        ids = [r["id"] for r in matched]
        assert "test_contains_path" not in ids

    def test_contains_case_insensitive(self, engine):
        entry = {"image_path": r"C:\INETPUB\wwwroot\shell.exe"}
        matched = engine.scan_entry(entry)
        ids = [r["id"] for r in matched]
        assert "test_contains_path" in ids


class TestRuleEngineMatchRegex:

    def test_regex_match(self, engine):
        entry = {"command_line": "rundll32.exe evil.dll,EntryPoint"}
        matched = engine.scan_entry(entry)
        ids = [r["id"] for r in matched]
        assert "test_regex_cmd" in ids

    def test_regex_no_match(self, engine):
        entry = {"command_line": "cmd.exe /c dir"}
        matched = engine.scan_entry(entry)
        ids = [r["id"] for r in matched]
        assert "test_regex_cmd" not in ids


class TestRuleEngineMatchEquals:

    def test_equals_match(self, engine):
        entry = {"enabled": "disabled"}
        matched = engine.scan_entry(entry)
        ids = [r["id"] for r in matched]
        assert "test_equals_status" in ids

    def test_equals_no_match(self, engine):
        entry = {"enabled": "enabled"}
        matched = engine.scan_entry(entry)
        ids = [r["id"] for r in matched]
        assert "test_equals_status" not in ids

    def test_equals_case_insensitive(self, engine):
        entry = {"enabled": "Disabled"}
        matched = engine.scan_entry(entry)
        ids = [r["id"] for r in matched]
        assert "test_equals_status" in ids


class TestRuleEngineMatchIP:

    def test_ip_equals_match(self, engine):
        entry = {"command_line": "ping 8.8.8.8"}
        matched = engine.scan_entry(entry)
        ids = [r["id"] for r in matched]
        assert "test_ip_equals" in ids

    def test_ip_equals_no_match(self, engine):
        entry = {"command_line": "ping 1.1.1.1"}
        matched = engine.scan_entry(entry)
        ids = [r["id"] for r in matched]
        assert "test_ip_equals" not in ids

    def test_ip_contains_match(self, engine):
        entry = {"command_line": "connect 192.168.1.100:443"}
        matched = engine.scan_entry(entry)
        ids = [r["id"] for r in matched]
        assert "test_ip_contains" in ids


class TestRuleEngineMatchHash:

    def test_sha256_match(self, engine):
        entry = {"sha256": "abc123"}
        matched = engine.scan_entry(entry)
        ids = [r["id"] for r in matched]
        assert "test_sha256_equals" in ids

    def test_md5_match(self, engine):
        entry = {"md5": "deadbeef"}
        matched = engine.scan_entry(entry)
        ids = [r["id"] for r in matched]
        assert "test_md5_equals" in ids

    def test_hash_from_detail_data(self, engine):
        entry = {"detail_data": {"sha256": "abc123"}}
        matched = engine.scan_entry(entry)
        ids = [r["id"] for r in matched]
        assert "test_sha256_equals" in ids


class TestRuleEngineMultiCondition:

    def test_multi_condition_both_match(self, engine):
        entry = {"image_path": r"C:\temp\evil.exe", "command_line": "powershell -enc abc"}
        matched = engine.scan_entry(entry)
        ids = [r["id"] for r in matched]
        assert "test_multi_condition" in ids

    def test_multi_condition_partial_match(self, engine):
        entry = {"image_path": r"C:\temp\evil.exe", "command_line": "cmd.exe"}
        matched = engine.scan_entry(entry)
        ids = [r["id"] for r in matched]
        assert "test_multi_condition" not in ids


class TestRuleEngineCommandLineFallback:

    def test_command_line_fallback_to_launch_string(self, engine):
        entry = {"launch_string": "rundll32.exe evil.dll,Entry"}
        matched = engine.scan_entry(entry)
        ids = [r["id"] for r in matched]
        assert "test_regex_cmd" in ids

    def test_command_line_preferred_over_launch_string(self, engine):
        entry = {"command_line": "rundll32.exe evil.dll,Entry", "launch_string": "something_else"}
        matched = engine.scan_entry(entry)
        ids = [r["id"] for r in matched]
        assert "test_regex_cmd" in ids


class TestRuleEngineDebug:

    def test_scan_with_debug(self, engine):
        entry = {"image_path": r"C:\inetpub\wwwroot\shell.exe"}
        matched, debug_infos = engine.scan_entry(entry, debug=True)
        assert len(debug_infos) > 0
        assert isinstance(debug_infos[0], RuleMatchDebugInfo)
        hit_debug = [d for d in debug_infos if d.matched]
        assert len(hit_debug) >= 1

    def test_scan_with_allowed_types(self, engine):
        entry = {"image_path": r"C:\inetpub\wwwroot\shell.exe", "command_line": "rundll32.exe evil"}
        matched = engine.scan_entry(entry, allowed_types={"path"})
        ids = [r["id"] for r in matched]
        assert "test_contains_path" in ids
        assert "test_regex_cmd" not in ids


class TestRuleEngineSaveLoad:

    def test_save_and_reload(self, engine, tmp_path):
        save_path = str(tmp_path / "saved_rules.json")
        success, msg = engine.save_rules_to_file(save_path)
        assert success
        assert os.path.exists(save_path)

        engine2 = RuleEngine(rules_path=save_path)
        assert len(engine2.rules) == len(engine.rules)

    def test_load_rules_from_file(self, tmp_rules_file, tmp_path):
        engine2 = RuleEngine(rules_path=str(tmp_path / "empty.json"))
        success, msg = engine2.load_rules_from_file(tmp_rules_file)
        assert success
        assert len(engine2.rules) == 8


class TestRuleEngineTestRule:

    def test_test_rule_valid(self, engine):
        rule = {"id": "test_rule", "match": [{"field": "image_path", "type": "contains", "value": "evil"}]}
        entries = [
            {"image_path": r"C:\evil\app.exe"},
            {"image_path": r"C:\clean\app.exe"},
        ]
        result = engine.test_rule(rule, entries)
        assert result["valid"]
        assert result["regex_valid"]
        assert result["matches"] == [True, False]

    def test_test_rule_invalid_regex(self, engine):
        rule = {"id": "bad", "match": [{"field": "cmd", "type": "regex", "value": "[invalid"}]}
        result = engine.test_rule(rule, [])
        assert not result["valid"]
        assert not result["regex_valid"]

    def test_test_rule_no_match_condition(self, engine):
        rule = {"id": "empty", "match": []}
        result = engine.test_rule(rule, [])
        assert not result["valid"]
