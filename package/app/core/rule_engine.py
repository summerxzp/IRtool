import json
import re
import ipaddress
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

    def scan_entry(self, entry, allowed_types=None):
        """扫描单个条目，返回命中的规则列表"""
        matched_rules = []
        for rule in self.rules:
            if allowed_types:
                rule_types = self._rule_types(rule)
                if not rule_types.intersection(allowed_types):
                    continue
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

            field_value = self._get_field_value(entry, field)

            if field == "ip":
                if not self._match_ip_rule(match_type, value, entry):
                    return False
                continue

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

    def _rule_types(self, rule):
        types = set()
        match_conditions = rule.get("match", [])
        for condition in match_conditions:
            field = condition.get("field", "")
            if field in ("hash", "sha256", "md5"):
                types.add("hash")
            elif field == "ip":
                types.add("ip")
            elif field in ("image_path",):
                types.add("path")
            elif field in ("command_line", "launch_string"):
                types.add("command")
            else:
                types.add("other")
        if not types:
            types.add("other")
        return types

    def _get_field_value(self, entry, field):
        if not field:
            return ""
        if field in ("hash", "sha256", "md5"):
            return self._get_hash_value(entry, field)
        value = entry.get(field, "")
        if not value:
            detail = entry.get("detail_data")
            if isinstance(detail, dict):
                value = detail.get(field, "")
        if not value and field == "command_line":
            value = entry.get("launch_string", "")
        return value or ""

    def _get_hash_value(self, entry, field):
        if field == "md5":
            value = entry.get("md5", "")
        elif field == "sha256":
            value = entry.get("sha256", "")
        else:
            value = entry.get("sha256", "")
        if not value:
            detail = entry.get("detail_data")
            if isinstance(detail, dict):
                if field == "md5":
                    value = detail.get("md5", "")
                elif field == "sha256":
                    value = detail.get("sha256", "")
                else:
                    value = detail.get("hash", "")
        return value or ""

    def _match_ip_rule(self, match_type, value, entry):
        text = self._get_ip_search_text(entry)
        if not text:
            return False
        value_text = str(value).strip()
        if not value_text:
            return False
        if match_type == "equals":
            ips = self._extract_ips(text)
            return value_text in ips
        if match_type == "regex":
            try:
                return re.search(str(value_text), text, re.IGNORECASE) is not None
            except re.error:
                return False
        return value_text.lower() in text.lower()

    def _get_ip_search_text(self, entry):
        parts = [
            self._get_field_value(entry, "command_line"),
            self._get_field_value(entry, "launch_string"),
            self._get_field_value(entry, "image_path"),
        ]
        return " ".join([p for p in parts if p])

    def _extract_ips(self, text):
        candidates = []
        if not text:
            return candidates
        ipv4_pattern = r"(?<!\\d)(?:\\d{1,3}\\.){3}\\d{1,3}(?!\\d)"
        for match in re.finditer(ipv4_pattern, text):
            ip = match.group(0)
            if self._is_ip_address(ip):
                candidates.append(ip)
        ipv6_bracket_pattern = r"\\[([0-9a-fA-F:]+)\\]"
        for match in re.finditer(ipv6_bracket_pattern, text):
            ip = match.group(1)
            if self._is_ip_address(ip):
                candidates.append(ip)
        return list(dict.fromkeys(candidates))

    def _is_ip_address(self, text):
        try:
            ipaddress.ip_address(text)
            return True
        except ValueError:
            return False
