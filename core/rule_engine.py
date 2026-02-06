import json
import re
from pathlib import Path


class RuleEngine:
    """规则扫描引擎（核心层）"""

    def __init__(self, rules_path: str = None):
        base_dir = Path(__file__).parent.parent
        default_path = base_dir / "data" / "rules.json"
        self.rules_path = Path(rules_path) if rules_path else default_path
        self.rules = []
        self._load_rules()

    def _default_rules(self):
        return [
            {
                "id": "silverfox_rundll_obfuscation",
                "family": "银狐",
                "match": [
                    {
                        "field": "command_line",
                        "type": "regex",
                        "value": "r\"\"u\"\"n\"\"d\"\"[IiI]{2}32"
                    }
                ],
                "severity": "high",
                "note": "仿冒 rundll32 的银狐变种"
            },
            {
                "id": "silverfox_jnetpub_path",
                "family": "银狐",
                "match": [
                    {
                        "field": "image_path",
                        "type": "contains",
                        "value": "jnetpub"
                    }
                ],
                "severity": "high",
                "note": "银狐常见路径特征"
            },
            {
                "id": "silverfox_jnetpub_cmd",
                "family": "银狐",
                "match": [
                    {
                        "field": "command_line",
                        "type": "contains",
                        "value": "jnetpub\\\\wwwroot"
                    }
                ],
                "severity": "high",
                "note": "命令行包含 jnetpub\\\\wwwroot"
            },
            {
                "id": "silverfox_inetpub_path",
                "family": "银狐",
                "match": [
                    {
                        "field": "image_path",
                        "type": "contains",
                        "value": "\\\\inetpub\\\\"
                    }
                ],
                "severity": "medium",
                "note": "inetpub 路径在普通终端不常见"
            },
            {
                "id": "silverfox_wmp_music_dll",
                "family": "银狐",
                "match": [
                    {
                        "field": "command_line",
                        "type": "contains",
                        "value": "Windows Media Player Music.dll"
                    }
                ],
                "severity": "high",
                "note": "疑似仿冒 Windows Media Player Music.dll"
            },
            {
                "id": "silverfox_wab_dll",
                "family": "银狐",
                "match": [
                    {
                        "field": "command_line",
                        "type": "contains",
                        "value": "Windows Mail\\\\wab.dll"
                    }
                ],
                "severity": "high",
                "note": "疑似仿冒 Windows Mail\\\\wab.dll"
            },
            {
                "id": "powershell_encoded",
                "family": "PowerShell",
                "match": [
                    {
                        "field": "command_line",
                        "type": "contains",
                        "value": "-enc "
                    }
                ],
                "severity": "medium",
                "note": "PowerShell 编码执行"
            }
        ]

    def _load_rules(self):
        if self.rules_path.exists():
            try:
                with open(self.rules_path, "r", encoding="utf-8") as f:
                    self.rules = json.load(f)
                if not isinstance(self.rules, list):
                    self.rules = []
            except Exception:
                self.rules = []
        if not self.rules:
            self.rules = self._default_rules()
            self._ensure_rules_file()

    def _ensure_rules_file(self):
        try:
            self.rules_path.parent.mkdir(parents=True, exist_ok=True)
            self.save_rules_to_file(str(self.rules_path))
        except Exception:
            pass

    def load_rules_from_file(self, file_path):
        """从文件加载规则"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                rules = json.load(f)
            if not isinstance(rules, list):
                return False, "规则格式错误：应为列表"
            self.rules = rules
            return True, f"成功加载 {len(self.rules)} 条规则"
        except Exception as e:
            return False, f"加载规则失败: {str(e)}"

    def save_rules_to_file(self, file_path):
        """保存规则到文件"""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.rules, f, ensure_ascii=False, indent=2)
            return True, f"成功保存 {len(self.rules)} 条规则"
        except Exception as e:
            return False, f"保存规则失败: {str(e)}"

    def scan_entry(self, entry):
        """扫描单个条目，返回命中的规则列表"""
        matched_rules = []
        for rule in self.rules:
            if self._match_rule(rule, entry):
                matched_rules.append(rule)
        return matched_rules

    def _match_rule(self, rule, entry):
        """检查条目是否匹配规则"""
        match_conditions = rule.get("match", [])
        for condition in match_conditions:
            field = condition.get("field")
            match_type = condition.get("type")
            value = condition.get("value")

            field_value = entry.get(field, "")
            if not field_value:
                detail = entry.get("detail_data")
                if isinstance(detail, dict):
                    field_value = detail.get(field, "")
            if not field_value and field == "command_line":
                field_value = entry.get("launch_string", "")

            if match_type == "contains":
                if str(value).lower() not in str(field_value).lower():
                    return False
            elif match_type == "regex":
                try:
                    if not re.search(str(value), str(field_value), re.IGNORECASE):
                        return False
                except re.error:
                    return False
            elif match_type == "equals":
                if str(field_value).lower() != str(value).lower():
                    return False
        return True
