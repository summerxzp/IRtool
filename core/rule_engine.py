"""
规则引擎 - JSON 转义规则说明

【重要】规则文件中的 value 字段必须按以下规则转义：

1. contains 类型（路径匹配）
   - 正常路径: C:\inetpub\wwwroot
   - JSON 填写: "C:\\inetpub\\wwwroot"
   - 规则: 每个 \ 需要写成 \\

2. regex 类型（正则表达式）
   - 正则中的双引号: "
   - JSON 填写: \\"
   - 示例: 匹配 r""u""n""d""ll""32 → "\\\"{2,}u\\\"{2,}n\\\"{2,}d\\\"{2,}ll\\\"{2,}32"

3. 其他类型
   - equals 类型: 直接写值，无需转义
   - hash 类型: 直接写哈希值，无需转义

【注意】
- 不要在 JSON 中写 Python 的 r"..." 前缀
- UI 显示时会自动转换为可读格式
"""

import json
import re
import ipaddress
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set


class RuleValidationError:
    """规则校验错误信息"""
    def __init__(self, rule_id: str, field: str, error_type: str, message: str):
        self.rule_id = rule_id
        self.field = field
        self.error_type = error_type  # 'regex_syntax', 'invalid_field', 'missing_required'
        self.message = message

    def to_dict(self) -> Dict[str, str]:
        return {
            "rule_id": self.rule_id,
            "field": self.field,
            "error_type": self.error_type,
            "message": self.message
        }


class RuleMatchDebugInfo:
    """规则匹配调试信息"""
    def __init__(self, rule_id: str, matched: bool, details: List[Dict[str, Any]]):
        self.rule_id = rule_id
        self.matched = matched
        self.details = details  # 每个条件的匹配详情

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "matched": self.matched,
            "details": self.details
        }


class RuleEngine:
    """规则扫描引擎（核心层）"""

    def __init__(self, rules_path: str = None):
        base_dir = self._get_app_dir()
        # 尝试多个路径: 1) 根目录/data 2) _internal/data (PyInstaller onedir)
        possible_paths = [
            base_dir / "data" / "rules.json",
            base_dir / "_internal" / "data" / "rules.json",
        ]
        default_path = possible_paths[0]
        for path in possible_paths:
            if path.exists():
                default_path = path
                break
        self.rules_path = Path(rules_path) if rules_path else default_path
        self.rules = []
        self._validation_errors: List[RuleValidationError] = []
        self._compiled_patterns: Dict[str, re.Pattern] = {}  # 缓存编译后的正则
        self._load_rules()

    def _get_app_dir(self) -> Path:
        """获取应用根目录（支持源码运行和PyInstaller打包）"""
        import sys
        if getattr(sys, 'frozen', False):
            # PyInstaller打包后，使用可执行文件所在目录
            return Path(sys.executable).parent
        else:
            # 源码运行，使用脚本所在目录
            return Path(__file__).parent.parent

    def _get_rules_template(self):
        return []

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
            self.rules = self._get_rules_template()
            self._ensure_rules_file()
        
        self._validate_all_rules()

    def _ensure_rules_file(self):
        try:
            self.rules_path.parent.mkdir(parents=True, exist_ok=True)
            self.save_rules_to_file(str(self.rules_path))
        except Exception:
            pass

    def _validate_all_rules(self):
        """校验所有规则，记录错误信息"""
        self._validation_errors = []
        self._compiled_patterns = {}
        
        for rule in self.rules:
            rule_id = rule.get("id", "unknown")
            match_conditions = rule.get("match", [])
            
            if not match_conditions:
                self._validation_errors.append(
                    RuleValidationError(rule_id, "match", "missing_required", "规则缺少match条件")
                )
                continue
            
            for idx, condition in enumerate(match_conditions):
                field = condition.get("field", "")
                match_type = condition.get("type", "")
                value = condition.get("value", "")
                
                if not field:
                    self._validation_errors.append(
                        RuleValidationError(rule_id, f"match[{idx}].field", "missing_required", "字段不能为空")
                    )
                
                if not match_type:
                    self._validation_errors.append(
                        RuleValidationError(rule_id, f"match[{idx}].type", "missing_required", "匹配类型不能为空")
                    )
                
                # 对regex类型进行编译校验
                if match_type == "regex" and value:
                    pattern_key = f"{rule_id}:{idx}"
                    try:
                        compiled = re.compile(value, re.IGNORECASE)
                        self._compiled_patterns[pattern_key] = compiled
                    except re.error as e:
                        self._validation_errors.append(
                            RuleValidationError(
                                rule_id, 
                                f"match[{idx}].value", 
                                "regex_syntax", 
                                f"正则语法错误: {str(e)}"
                            )
                        )

    def get_validation_errors(self) -> List[Dict[str, str]]:
        """获取规则校验错误列表"""
        return [err.to_dict() for err in self._validation_errors]

    def is_rules_valid(self) -> bool:
        """检查所有规则是否有效"""
        return len(self._validation_errors) == 0

    def load_rules_from_file(self, file_path):
        """从文件加载规则"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                rules = json.load(f)
            if not isinstance(rules, list):
                return False, "规则格式错误：应为列表"
            self.rules = rules
            # 重新校验
            self._validate_all_rules()
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

    def scan_entry(self, entry, allowed_types=None, debug=False):
        """扫描单个条目，返回命中的规则列表
        
        Args:
            entry: 要扫描的条目
            allowed_types: 允许的规则类型集合
            debug: 是否返回调试信息
        
        Returns:
            如果debug=False: 返回命中的规则列表
            如果debug=True: 返回 (命中规则列表, 调试信息列表)
        """
        matched_rules = []
        debug_infos = []
        
        for rule in self.rules:
            if allowed_types:
                rule_types = self._rule_types(rule)
                if not rule_types.intersection(allowed_types):
                    continue
            
            is_matched, debug_info = self._match_rule_with_debug(rule, entry)
            if is_matched:
                matched_rules.append(rule)
            
            if debug:
                debug_infos.append(debug_info)
        
        if debug:
            return matched_rules, debug_infos
        return matched_rules

    def _match_rule(self, rule, entry):
        """检查条目是否匹配规则（兼容旧接口）"""
        is_matched, _ = self._match_rule_with_debug(rule, entry)
        return is_matched

    def _match_rule_with_debug(self, rule, entry) -> Tuple[bool, RuleMatchDebugInfo]:
        """检查条目是否匹配规则，返回调试信息"""
        rule_id = rule.get("id", "unknown")
        match_conditions = rule.get("match", [])
        details = []
        all_matched = True
        
        for idx, condition in enumerate(match_conditions):
            field = condition.get("field")
            match_type = condition.get("type")
            value = condition.get("value")
            
            # 获取字段值（支持command_line自动回退launch_string）
            field_value = self._get_field_value_with_fallback(entry, field)
            
            condition_matched = False
            condition_detail = {
                "condition_index": idx,
                "field": field,
                "match_type": match_type,
                "pattern": value,
                "field_value": field_value[:200] if field_value else "",  # 截断避免过长
                "matched": False,
                "error": None
            }
            
            if field == "ip":
                condition_matched = self._match_ip_rule(match_type, value, entry)
                condition_detail["matched"] = condition_matched
            elif match_type == "contains":
                condition_matched = str(value).lower() in str(field_value).lower()
                condition_detail["matched"] = condition_matched
            elif match_type == "regex":
                pattern_key = f"{rule_id}:{idx}"
                compiled = self._compiled_patterns.get(pattern_key)
                
                if compiled:
                    try:
                        condition_matched = compiled.search(str(field_value)) is not None
                        condition_detail["matched"] = condition_matched
                    except Exception as e:
                        condition_detail["error"] = f"匹配异常: {str(e)}"
                else:
                    # 尝试即时编译（如果之前校验失败）
                    try:
                        condition_matched = re.search(str(value), str(field_value), re.IGNORECASE) is not None
                        condition_detail["matched"] = condition_matched
                    except re.error as e:
                        condition_detail["error"] = f"正则语法错误: {str(e)}"
            elif match_type == "equals":
                condition_matched = str(field_value).lower() == str(value).lower()
                condition_detail["matched"] = condition_matched
            
            if not condition_matched:
                all_matched = False
            
            details.append(condition_detail)
        
        debug_info = RuleMatchDebugInfo(rule_id, all_matched, details)
        return all_matched, debug_info

    def _get_field_value_with_fallback(self, entry, field):
        """获取字段值，支持command_line自动回退launch_string"""
        if not field:
            return ""
        
        # command_line规则：优先使用command_line，若为空自动回退launch_string
        if field == "command_line":
            value = self._get_field_value(entry, "command_line")
            if not value:
                value = self._get_field_value(entry, "launch_string")
            return value
        
        return self._get_field_value(entry, field)

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
        ipv4_pattern = r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)"
        for match in re.finditer(ipv4_pattern, text):
            ip = match.group(0)
            if self._is_ip_address(ip):
                candidates.append(ip)
        ipv6_bracket_pattern = r"\[([0-9a-fA-F:]+)\]"
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

    def test_rule(self, rule: Dict[str, Any], test_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """测试单条规则的有效性
        
        Returns:
            {
                "valid": bool,  # 规则是否有效
                "regex_valid": bool,  # 正则语法是否正确
                "matches": List[bool],  # 每个测试条目的匹配结果
                "debug_info": List[RuleMatchDebugInfo]  # 详细调试信息
            }
        """
        result = {
            "valid": True,
            "regex_valid": True,
            "matches": [],
            "debug_info": []
        }
        
        # 校验规则格式
        match_conditions = rule.get("match", [])
        if not match_conditions:
            result["valid"] = False
            return result
        
        # 校验正则语法
        for idx, condition in enumerate(match_conditions):
            if condition.get("type") == "regex":
                value = condition.get("value", "")
                try:
                    re.compile(value)
                except re.error as e:
                    result["valid"] = False
                    result["regex_valid"] = False
                    return result
        
        # 测试匹配
        for entry in test_entries:
            is_matched, debug_info = self._match_rule_with_debug(rule, entry)
            result["matches"].append(is_matched)
            result["debug_info"].append(debug_info.to_dict())
        
        return result
