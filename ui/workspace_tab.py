from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QComboBox, QMessageBox,
    QHeaderView, QLineEdit, QLabel, QTextEdit, QSplitter,
    QFileDialog, QAbstractItemView, QFrame, QCheckBox, QMenu,
    QRadioButton, QButtonGroup, QDialog, QDialogButtonBox, QFormLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication, QClipboard
import os
from pathlib import Path
import uuid
import copy

from core.rule_engine import RuleEngine
from core.search_service import SearchService
from utils.path_resolver import PathResolver, PathScope
from utils.command_template import CommandTemplateManager
from utils.safe_executor import SafeExecutor, CommandResult, CommandStatus
from utils.search_result import SearchResult, ResultType
from ui.ui_style import apply_flat_style


class NumericTableWidgetItem(QTableWidgetItem):
    """支持数值排序的 TableWidgetItem"""
    def __init__(self, text, sort_value=None):
        super().__init__(text)
        self.sort_value = sort_value if sort_value is not None else self._extract_numeric_value(text)
    
    def _extract_numeric_value(self, text):
        if text is None or text == "":
            return float("-inf")
        try:
            return int(text)
        except ValueError:
            try:
                return float(text)
            except ValueError:
                return float("-inf")
    
    def __lt__(self, other):
        if isinstance(other, NumericTableWidgetItem):
            return self.sort_value < other.sort_value
        return self.text() < other.text()


class RuleEditDialog(QDialog):
    """规则添加对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        apply_flat_style(self)
        self.setWindowTitle("新增规则")
        self._test_results = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.edt_id = QLineEdit(f"rule_{uuid.uuid4().hex[:8]}")
        self.edt_family = QLineEdit("custom")
        self.cmb_field = QComboBox()
        self.cmb_field.addItems([
            "command_line", "image_path", "entry", "description",
            "publisher", "company", "location", "category", "launch_string",
            "ip", "hash", "sha256", "md5"
        ])
        self.cmb_type = QComboBox()
        self.cmb_type.addItems(["包含", "正则", "等于"])
        self.edt_value = QLineEdit()
        self.cmb_severity = QComboBox()
        self.cmb_severity.addItems(["critical", "high", "medium", "low"])
        self.edt_date = QLineEdit()
        self.edt_note = QLineEdit()

        form.addRow("规则ID", self.edt_id)
        form.addRow("家族", self.edt_family)
        form.addRow("字段", self.cmb_field)
        form.addRow("匹配类型", self.cmb_type)
        form.addRow("匹配值", self.edt_value)
        form.addRow("严重级别", self.cmb_severity)
        form.addRow("发现日期", self.edt_date)
        form.addRow("备注", self.edt_note)

        layout.addLayout(form)

        # 测试规则区域
        test_layout = QHBoxLayout()
        self.btn_test_rule = QPushButton("测试规则")
        self.btn_test_rule.clicked.connect(self._on_test_rule)
        self.lbl_test_result = QLabel("点击测试规则验证有效性")
        self.lbl_test_result.setStyleSheet("color: gray;")
        test_layout.addWidget(self.btn_test_rule)
        test_layout.addWidget(self.lbl_test_result, 1)
        layout.addLayout(test_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_test_rule(self):
        """测试规则有效性"""
        field = self.cmb_field.currentText()
        match_type = self._normalize_match_type(self.cmb_type.currentText())
        value = self.edt_value.text().strip()

        if not value:
            QMessageBox.warning(self, "提示", "匹配值不能为空")
            return

        # 创建临时规则
        test_rule = {
            "id": "test_rule",
            "family": self.edt_family.text().strip() or "test",
            "match": [
                {
                    "field": field,
                    "type": match_type,
                    "value": value
                }
            ],
            "severity": self.cmb_severity.currentText(),
            "note": self.edt_note.text().strip()
        }

        # 根据字段类型生成测试样本
        test_entries = self._generate_test_entries(field, value, match_type)

        # 执行测试
        from core.rule_engine import RuleEngine
        engine = RuleEngine.__new__(RuleEngine)
        engine.rules = [test_rule]

        matched_count = 0
        test_details = []

        for test_name, entry in test_entries:
            matched = engine._match_rule(test_rule, entry)
            if matched:
                matched_count += 1
                test_details.append(f"✓ {test_name}")
            else:
                test_details.append(f"✗ {test_name}")

        # 显示测试结果
        # 判断测试是否完全通过：精确匹配和包含匹配应该匹配，不应匹配应该不匹配
        expected_matches = [name for name, _ in test_entries if "不应" not in name]
        expected_non_matches = [name for name, _ in test_entries if "不应" in name]
        
        actual_matches = [name for name, matched in zip([n for n, _ in test_entries], 
                                                         ["✓" in d for d in test_details]) if matched]
        actual_non_matches = [name for name, matched in zip([n for n, _ in test_entries], 
                                                            ["✓" in d for d in test_details]) if not matched]
        
        # 检查是否所有预期匹配的都被匹配了，且所有预期不匹配的都没被匹配
        all_expected_matched = all(name in actual_matches for name in expected_matches)
        all_expected_not_matched = all(name in actual_non_matches for name in expected_non_matches)
        
        if all_expected_matched and all_expected_not_matched:
            self.lbl_test_result.setText(f"规则配置正确！所有测试样本验证通过")
            self.lbl_test_result.setStyleSheet("color: green;")
            QMessageBox.information(
                self,
                "规则测试通过",
                f"规则配置正确！\n\n匹配类型: {match_type}\n测试字段: {field}\n匹配值: {value}\n\n测试结果:\n" + "\n".join(test_details)
            )
        else:
            self.lbl_test_result.setText(f"规则配置存在问题，请检查")
            self.lbl_test_result.setStyleSheet("color: red;")
            QMessageBox.warning(
                self,
                "规则测试未通过",
                f"规则配置存在问题，请检查。\n\n匹配类型: {match_type}\n测试字段: {field}\n匹配值: {value}\n\n测试结果:\n" + "\n".join(test_details)
            )

    def _generate_regex_test_sample(self, pattern):
        """根据正则表达式生成一个能匹配该正则的测试样本"""
        import re
        
        # 银狐 rundll32 混淆特征的特殊处理
        # 检测双引号混淆模式：\"{2,}u\"{2,}n\"{2,}d\"{2,}ll\"{2,}32
        if '\\"' in pattern and 'u' in pattern and 'n' in pattern and 'd' in pattern and 'll' in pattern and '32' in pattern:
            return 'r""u""n""d""ll""32.exe'
        
        # 对于简单的字符类，提取第一个选项
        result = pattern
        
        # 替换量词 {n,} 或 {n} 为固定次数
        result = re.sub(r'\{(\d+),?\}', lambda m: int(m.group(1)) * 'X', result)
        
        # 替换字符类 [abc] 为第一个字符
        result = re.sub(r'\[([^\]]+)\]', lambda m: m.group(1)[0], result)
        
        # 替换转义的特殊字符
        result = result.replace('\\d', '1').replace('\\w', 'a').replace('\\.', '.')
        result = result.replace('\\', '')
        
        # 移除正则元字符
        for char in '^$+?*(){}|':
            result = result.replace(char, '')
        
        return result if result else "test_sample"

    def _generate_test_entries(self, field, value, match_type="contains"):
        """根据字段类型和匹配类型生成测试条目"""
        entries = []
        
        # 针对正则类型的特殊处理：生成能匹配该正则的测试样本
        if match_type == "regex":
            # 尝试根据正则生成匹配样本
            test_value = self._generate_regex_test_sample(value)
            if field == "command_line":
                entries.append(("正则匹配", {"command_line": test_value}))
                entries.append(("包含匹配", {"command_line": f"prefix {test_value} suffix"}))
                entries.append(("不应匹配", {"command_line": "completely different command"}))
            elif field == "image_path":
                entries.append(("正则匹配", {"image_path": test_value}))
                entries.append(("不应匹配", {"image_path": "C:\\Windows\\notepad.exe"}))
            else:
                entries.append(("字段匹配", {field: test_value}))
                entries.append(("不应匹配", {field: "different_value"}))
            return entries

        if field == "command_line":
            # 测试命令行匹配
            entries.append(("精确匹配", {"command_line": value}))
            entries.append(("包含匹配", {"command_line": f"prefix {value} suffix"}))
            entries.append(("不应匹配", {"command_line": "completely different command"}))

        elif field == "image_path":
            entries.append(("精确匹配", {"image_path": value}))
            entries.append(("包含匹配", {"image_path": f"C:\\Windows\\{value}\\test.exe"}))
            entries.append(("不应匹配", {"image_path": "C:\\Windows\\notepad.exe"}))

        elif field == "ip":
            entries.append(("IP匹配", {"command_line": f"connect to {value}"}))
            entries.append(("不应匹配", {"command_line": "connect to 1.2.3.4"}))

        elif field in ("sha256", "md5", "hash"):
            entries.append(("Hash匹配", {"sha256": value, "md5": value}))
            entries.append(("不应匹配", {"sha256": "a" * 64, "md5": "b" * 32}))

        elif field == "entry":
            entries.append(("条目名匹配", {"entry": value}))
            entries.append(("不应匹配", {"entry": "LegitimateEntry"}))

        elif field in ("publisher", "company", "description", "category"):
            entries.append(("字段匹配", {field: value}))
            entries.append(("不应匹配", {field: "Unknown Publisher"}))

        else:
            # 通用测试
            entries.append(("字段匹配", {field: value}))
            entries.append(("不应匹配", {field: "different_value"}))

        return entries

    def _on_accept(self):
        if not self.edt_value.text().strip():
            QMessageBox.warning(self, "提示", "匹配值不能为空")
            return
        self.accept()

    def get_rule(self):
        return {
            "id": self.edt_id.text().strip() or f"rule_{uuid.uuid4().hex[:8]}",
            "family": self.edt_family.text().strip() or "custom",
            "match": [
                {
                    "field": self.cmb_field.currentText(),
                    "type": self._normalize_match_type(self.cmb_type.currentText()),
                    "value": self.edt_value.text().strip()
                }
            ],
            "severity": self.cmb_severity.currentText(),
            "date": self.edt_date.text().strip(),
            "note": self.edt_note.text().strip()
        }

    def _normalize_match_type(self, text: str) -> str:
        mapping = {
            "包含": "contains",
            "正则": "regex",
            "等于": "equals",
            "contains": "contains",
            "regex": "regex",
            "equals": "equals",
        }
        return mapping.get((text or "").strip(), "contains")


class RuleManagerDialog(QDialog):
    """规则管理对话框"""
    def __init__(self, rule_engine: RuleEngine, parent=None):
        super().__init__(parent)
        apply_flat_style(self)
        self.rule_engine = rule_engine
        self._rule_index_by_row = []
        self._loading = False
        self._dirty = False
        self._original_rules = copy.deepcopy(self.rule_engine.rules)
        self.setWindowTitle("规则管理")
        self.resize(900, 500)
        self._init_ui()
        self._load_rules()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["ID", "Family", "Field", "Type", "Value", "Severity", "Date", "Note"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table)

        # 搜索框
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("搜索:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入关键字搜索规则(Family/Field/Value/Note)...")
        self.search_input.textChanged.connect(self._filter_rules)
        search_layout.addWidget(self.search_input)
        self.btn_clear_search = QPushButton("清除")
        self.btn_clear_search.clicked.connect(self._clear_search)
        search_layout.addWidget(self.btn_clear_search)
        layout.addLayout(search_layout)

        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("新增")
        self.btn_delete = QPushButton("删除")
        self.btn_help = QPushButton("帮助")
        self.btn_test_all = QPushButton("测试所有规则")
        self.btn_import = QPushButton("导入")
        self.btn_import_ioc = QPushButton("导入IOC")
        self.btn_export = QPushButton("导出")
        self.btn_save = QPushButton("保存")
        self.btn_close = QPushButton("关闭")

        self.btn_add.clicked.connect(self._add_rule)
        self.btn_delete.clicked.connect(self._delete_rule)
        self.btn_help.clicked.connect(self._show_help)
        self.btn_test_all.clicked.connect(self._test_all_rules)
        self.btn_import.clicked.connect(self._import_rules)
        self.btn_import_ioc.clicked.connect(self._import_ioc)
        self.btn_export.clicked.connect(self._export_rules)
        self.btn_save.clicked.connect(self._save_rules_with_confirm)
        self.btn_close.clicked.connect(self.close)

        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_help)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_test_all)
        btn_layout.addWidget(self.btn_import)
        btn_layout.addWidget(self.btn_import_ioc)
        btn_layout.addWidget(self.btn_export)
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

    def _load_rules(self):
        rules = self.rule_engine.rules or []
        self._loading = True
        self.table.setRowCount(0)
        self._rule_index_by_row = []
        for idx, rule in enumerate(rules):
            self.table.insertRow(idx)
            match_list = rule.get("match", [])
            first_match = match_list[0] if match_list else {}
            display_type = self._display_match_type(first_match.get("type", ""))
            self.table.setItem(idx, 0, QTableWidgetItem(rule.get("id", "")))
            self.table.setItem(idx, 1, QTableWidgetItem(rule.get("family", "")))
            self.table.setItem(idx, 2, QTableWidgetItem(first_match.get("field", "")))
            self.table.setItem(idx, 3, QTableWidgetItem(display_type))
            # 使用_display_rule_value将JSON转义值转换为可读格式
            display_value = self._display_rule_value(
                first_match.get("value", ""),
                first_match.get("type", "contains")
            )
            self.table.setItem(idx, 4, QTableWidgetItem(display_value))
            self.table.setItem(idx, 5, QTableWidgetItem(rule.get("severity", "")))
            self.table.setItem(idx, 6, QTableWidgetItem(rule.get("date", "")))
            self.table.setItem(idx, 7, QTableWidgetItem(rule.get("note", "")))
            self._rule_index_by_row.append(idx)
        self.table.resizeColumnsToContents()
        self.table.setColumnHidden(0, True)
        self._loading = False
        self._dirty = False

    def _add_rule(self):
        dialog = RuleEditDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        new_rule = dialog.get_rule()
        
        # 检查重复规则
        if self._is_duplicate_rule(new_rule):
            match_list = new_rule.get("match", [])
            if match_list:
                match = match_list[0]
                QMessageBox.warning(
                    self, 
                    "重复规则", 
                    f"已存在相同的规则:\n"
                    f"字段: {match.get('field')}\n"
                    f"类型: {match.get('type')}\n"
                    f"值: {match.get('value')}\n\n"
                    f"请修改规则或删除现有规则后再添加。"
                )
                return
        
        self.rule_engine.rules.append(new_rule)
        self._load_rules()
        self._dirty = True

    def _delete_rule(self):
        rows = sorted(set(item.row() for item in self.table.selectedItems()), reverse=True)
        if not rows:
            QMessageBox.warning(self, "提示", "请选择要删除的规则")
            return
        for row in rows:
            if 0 <= row < len(self.rule_engine.rules):
                self.rule_engine.rules.pop(row)
        self._load_rules()
        self._dirty = True

    def _filter_rules(self):
        """根据搜索关键字过滤规则"""
        search_text = self.search_input.text().lower().strip()
        if not search_text:
            # 显示所有行
            for row in range(self.table.rowCount()):
                self.table.setRowHidden(row, False)
            return
        
        # 遍历所有行，根据关键字过滤
        for row in range(self.table.rowCount()):
            match = False
            # 检查所有列
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item and search_text in item.text().lower():
                    match = True
                    break
            self.table.setRowHidden(row, not match)

    def _clear_search(self):
        """清除搜索"""
        self.search_input.clear()
        # 显示所有行
        for row in range(self.table.rowCount()):
            self.table.setRowHidden(row, False)

    def _show_help(self):
        """显示规则添加帮助"""
        help_text = """
<h2>规则添加规范与示例</h2>

<h3>一、基本格式</h3>
<p>每条规则包含以下要素：</p>
<ul>
<li><b>规则ID</b>：唯一标识，建议使用 rule_前缀 + 随机字符串</li>
<li><b>家族</b>：威胁家族名称，如"银狐"、"PowerShell"等</li>
<li><b>字段</b>：要匹配的字段类型</li>
<li><b>匹配类型</b>：包含 / 正则 / 等于</li>
<li><b>匹配值</b>：具体的匹配内容</li>
<li><b>严重级别</b>：critical / high / medium / low</li>
</ul>

<h3>二、字段类型说明</h3>

<h4>1. image_path (镜像路径)</h4>
<ul>
<li><b>说明</b>：可执行文件的完整路径</li>
<li><b>格式</b>：使用反斜杠或正斜杠均可，匹配时不区分大小写</li>
<li><b>示例</b>：
    <ul>
    <li><code>C:\\jnetpub\\wwwroot\\malware.exe</code> (精确路径)</li>
    <li><code>jnetpub</code> (路径中包含的特征字符串)</li>
    <li><code>\\inetpub\\</code> (目录特征)</li>
    </ul>
</li>
</ul>

<h4>2. command_line / launch_string (命令行)</h4>
<ul>
<li><b>说明</b>：启动命令或命令行参数</li>
<li><b>格式</b>：原始命令行字符串</li>
<li><b>示例</b>：
    <ul>
    <li><code>rundll32.exe "C:\\Program Files\\Windows Media Player\\Music.dll" Music</code></li>
    <li><code>powershell.exe -enc UwB0AGEAcgB0AC0AUwBsAGUAZQBw</code></li>
    <li><code>-enc</code> (参数特征)</li>
    </ul>
</li>
</ul>

<h4>3. ip (IP地址)</h4>
<ul>
<li><b>说明</b>：匹配命令行、启动字符串、镜像路径中的IP地址</li>
<li><b>格式</b>：标准IPv4或IPv6格式，<b>不需要带端口</b></li>
<li><b>示例</b>：
    <ul>
    <li><code>223.5.5.5</code> (阿里云DNS，用于测试)</li>
    <li><code>192.168.1.1</code></li>
    <li><code>[::1]</code> (IPv6格式)</li>
    </ul>
</li>
<li><b>注意</b>：IP匹配会自动从文本中提取所有IP地址进行比对</li>
</ul>

<h4>4. sha256 / md5 / hash (文件哈希)</h4>
<ul>
<li><b>说明</b>：文件哈希值匹配</li>
<li><b>格式</b>：
    <ul>
    <li>SHA256: 64位十六进制字符串</li>
    <li>MD5: 32位十六进制字符串</li>
    </ul>
</li>
<li><b>匹配条件</b>：
    <ul>
    <li>条目必须包含有效的哈希值（通过扫描时计算或导入）</li>
    <li>使用"等于"匹配类型进行精确匹配</li>
    </ul>
</li>
<li><b>示例</b>：
    <ul>
    <li><code>e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855</code> (SHA256)</li>
    <li><code>5d41402abc4b2a76b9719d911017c592</code> (MD5)</li>
    </ul>
</li>
</ul>

<h4>5. entry (条目名称)</h4>
<ul>
<li><b>说明</b>：自启动项的名称，如服务名、任务计划名</li>
<li><b>示例</b>：<code>BitLocker MDM policy</code>、<code>QIpqUotP</code></li>
</ul>

<h4>6. 其他字段</h4>
<ul>
<li><b>publisher</b>：发布者名称</li>
<li><b>company</b>：公司名称</li>
<li><b>description</b>：描述信息</li>
<li><b>category</b>：类别信息</li>
</ul>

<h3>三、匹配类型说明</h3>

<h4>1. 包含 (contains)</h4>
<ul>
<li>不区分大小写的子串匹配</li>
<li>适用于：路径特征、命令行参数、关键字</li>
<li>示例：<code>jnetpub</code> 可匹配 <code>C:\\jnetpub\\wwwroot\\test.exe</code></li>
</ul>

<h4>2. 正则 (regex)</h4>
<ul>
<li><b>重要</b>：这是<b>纯正则表达式</b>，不是Python代码，不要写 r"..." 前缀</li>
<li>自动添加 re.IGNORECASE 标志（不区分大小写）</li>
<li>JSON中的反斜杠和引号需要正确转义</li>
<li>示例：
    <ul>
    <li><code>\"{2,}u\"{2,}n\"{2,}d\"{2,}l\"{2,}l\"{2,}32</code> (匹配双引号混淆的rundll32)</li>
    <li><code>temp\\d{3,}\\.exe$</code> (匹配temp目录下数字命名的exe)</li>
    <li><code>https?://[\\w\\.-]+</code> (匹配HTTP/HTTPS URL)</li>
    </ul>
</li>
</ul>

<h4>3. 等于 (equals)</h4>
<ul>
<li>完全匹配，不区分大小写</li>
<li>适用于：哈希值、精确IP地址、精确条目名</li>
</ul>

<h3>四、可直接复制的规则示例</h3>

<h4>示例1：rundll32双引号混淆检测</h4>
<pre style="background:#f5f5f5;padding:10px;border-radius:5px;">
{
  "id": "silverfox_rundll_obfuscation",
  "family": "银狐",
  "match": [{
    "field": "command_line",
    "type": "regex",
    "value": "\\\"{2,}u\\\"{2,}n\\\"{2,}d\\\"{2,}ll\\\"{2,}32"
  }],
  "severity": "high",
  "note": "rundll32双引号混淆调用检测"
}
</pre>
<p><b>说明</b>：匹配如 <code>r""u""n""d""ll""32.exe</code> 这种双引号分割的混淆形式</p>

<h4>示例2：URL匹配</h4>
<pre style="background:#f5f5f5;padding:10px;border-radius:5px;">
{
  "id": "suspicious_url",
  "family": "恶意URL",
  "match": [{
    "field": "command_line",
    "type": "regex",
    "value": "https?://[\\w\\.-]+\\.(ru|cn|tk)/"
  }],
  "severity": "medium",
  "note": "命令行包含可疑URL"
}
</pre>

<h4>示例3：Windows路径匹配</h4>
<pre style="background:#f5f5f5;padding:10px;border-radius:5px;">
{
  "id": "temp_executable",
  "family": "可疑路径",
  "match": [{
    "field": "image_path",
    "type": "regex",
    "value": "temp\\d{3,}\\.exe$"
  }],
  "severity": "medium",
  "note": "temp目录下数字命名的可执行文件"
}
</pre>

<h3>五、常见错误（反例）</h3>
<table border="1" cellpadding="5" style="border-collapse:collapse;width:100%;">
<tr style="background:#ffebee;">
    <th>错误写法</th>
    <th>错误原因</th>
    <th>正确写法</th>
</tr>
<tr>
    <td><code>r"..."</code></td>
    <td>JSON中不需要Python原始字符串前缀</td>
    <td>直接写正则内容</td>
</tr>
<tr>
    <td><code>\d</code></td>
    <td>JSON中反斜杠需要转义</td>
    <td><code>\\d</code></td>
</tr>
<tr>
    <td><code>[Il]</code> 或 <code>[Ii]</code></td>
    <td>试图用正则做语义判断（I/l混淆）</td>
    <td>明确指定要匹配的字符</td>
</tr>
<tr>
    <td><code>"value": "C:\\Users"</code></td>
    <td>JSON中反斜杠需要双重转义</td>
    <td><code>"value": "C:\\\\Users"</code></td>
</tr>
</table>

<h3>六、注意事项</h3>
<ol>
<li><b>路径分隔符</b>：Windows路径使用反斜杠(<code>\\</code>)，但匹配时不区分正斜杠和反斜杠</li>
<li><b>大小写敏感</b>：所有匹配默认不区分大小写</li>
<li><b>正则转义</b>：JSON中的反斜杠需要双重转义（如 <code>\\d</code> 表示数字）</li>
<li><b>字段回退</b>：command_line规则若未命中，会自动回退到launch_string</li>
<li><b>测试验证</b>：添加规则后务必点击"测试规则"按钮验证有效性</li>
<li><b>避免误报</b>：规则值要有足够特异性，避免过于宽泛的匹配</li>
</ol>"""
        
        dialog = QDialog(self)
        dialog.setWindowTitle("规则添加帮助")
        dialog.resize(700, 600)
        apply_flat_style(dialog)
        
        layout = QVBoxLayout(dialog)
        
        text_edit = QTextEdit()
        text_edit.setHtml(help_text)
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)
        
        btn_ok = QPushButton("确定")
        btn_ok.clicked.connect(dialog.accept)
        layout.addWidget(btn_ok)
        
        dialog.exec()

    def _test_all_rules(self):
        """测试所有规则的有效性"""
        if not self.rule_engine.rules:
            QMessageBox.information(self, "提示", "当前没有规则需要测试")
            return
        
        # 清除所有行的背景色
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item:
                    item.setBackground(QColor("white"))
        
        failed_rules = []
        passed_count = 0
        
        for row, rule in enumerate(self.rule_engine.rules):
            match_list = rule.get("match", [])
            if not match_list:
                continue
            
            first_match = match_list[0]
            field = first_match.get("field", "")
            match_type = first_match.get("type", "contains")
            value = first_match.get("value", "")
            
            # 生成测试样本
            test_entries = self._generate_test_entries_for_field(field, value, match_type)
            
            # 执行测试
            all_passed = True
            for test_name, entry in test_entries:
                try:
                    matched = self.rule_engine._match_rule(rule, entry)
                    # "不应匹配"的样本如果被匹配了，说明规则有问题
                    if "不应" in test_name and matched:
                        all_passed = False
                        break
                    # 其他样本应该被匹配
                    elif "不应" not in test_name and not matched:
                        all_passed = False
                        break
                except Exception:
                    all_passed = False
                    break
            
            if all_passed:
                passed_count += 1
            else:
                failed_rules.append({
                    "row": row,
                    "rule_id": rule.get("id", "unknown"),
                    "family": rule.get("family", "unknown"),
                    "field": field,
                    "value": value
                })
                # 将失败行的背景设为浅红色
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item:
                        item.setBackground(QColor("#ffcccc"))
        
        # 显示测试结果
        total = len(self.rule_engine.rules)
        if failed_rules:
            QMessageBox.warning(
                self,
                "规则测试完成",
                f"测试完成！\n\n"
                f"通过: {passed_count}/{total} 条规则\n"
                f"失败: {len(failed_rules)} 条规则\n\n"
                f"失败的规则已用浅红色背景标出，请检查配置。\n\n"
                f"失败规则列表:\n" +
                "\n".join([f"- [{r['family']}] {r['rule_id']}: {r['field']}={r['value'][:50]}" 
                          for r in failed_rules[:5]]) +
                ("\n..." if len(failed_rules) > 5 else "")
            )
        else:
            QMessageBox.information(
                self,
                "规则测试完成",
                f"恭喜！所有规则测试通过！\n\n"
                f"共测试 {total} 条规则，全部正常工作。"
            )

    def _generate_test_entries_for_field(self, field, value, match_type="contains"):
        """根据字段类型和匹配类型生成测试条目"""
        entries = []
        
        # 针对正则类型的特殊处理
        if match_type == "regex":
            test_value = self._generate_regex_test_sample_for_batch(value)
            if field == "command_line":
                entries.append(("正则匹配", {"command_line": test_value}))
                entries.append(("包含匹配", {"command_line": f"prefix {test_value} suffix"}))
                entries.append(("不应匹配", {"command_line": "completely different command"}))
            elif field == "image_path":
                entries.append(("正则匹配", {"image_path": test_value}))
                entries.append(("不应匹配", {"image_path": "C:\\Windows\\notepad.exe"}))
            else:
                entries.append(("字段匹配", {field: test_value}))
                entries.append(("不应匹配", {field: "different_value"}))
            return entries
        
        if field == "command_line":
            entries.append(("精确匹配", {"command_line": value}))
            entries.append(("包含匹配", {"command_line": f"prefix {value} suffix"}))
            entries.append(("不应匹配", {"command_line": "completely different command"}))
        elif field == "image_path":
            entries.append(("精确匹配", {"image_path": value}))
            entries.append(("包含匹配", {"image_path": f"C:\\Windows\\{value}\\test.exe"}))
            entries.append(("不应匹配", {"image_path": "C:\\Windows\\notepad.exe"}))
        elif field == "ip":
            entries.append(("IP匹配", {"command_line": f"connect to {value}"}))
            entries.append(("不应匹配", {"command_line": "connect to 1.2.3.4"}))
        elif field in ("sha256", "md5", "hash"):
            entries.append(("Hash匹配", {"sha256": value, "md5": value}))
            entries.append(("不应匹配", {"sha256": "a" * 64, "md5": "b" * 32}))
        elif field == "entry":
            entries.append(("条目名匹配", {"entry": value}))
            entries.append(("不应匹配", {"entry": "LegitimateEntry"}))
        elif field in ("publisher", "company", "description", "category"):
            entries.append(("字段匹配", {field: value}))
            entries.append(("不应匹配", {field: "Unknown Publisher"}))
        else:
            entries.append(("字段匹配", {field: value}))
            entries.append(("不应匹配", {field: "different_value"}))
        
        return entries
    
    def _generate_regex_test_sample_for_batch(self, pattern):
        """为批量测试生成正则匹配样本"""
        import re
        
        # 银狐 rundll32 混淆特征的特殊处理
        # 检测双引号混淆模式：\"{2,}u\"{2,}n\"{2,}d\"{2,}ll\"{2,}32
        if '\\"' in pattern and 'u' in pattern and 'n' in pattern and 'd' in pattern and 'll' in pattern and '32' in pattern:
            return 'r""u""n""d""ll""32.exe'
        
        # 对于简单的字符类，提取第一个选项
        result = pattern
        
        # 替换量词 {n,} 或 {n} 为固定次数
        result = re.sub(r'\{(\d+),?\}', lambda m: int(m.group(1)) * 'X', result)
        
        # 替换字符类 [abc] 为第一个字符
        result = re.sub(r'\[([^\]]+)\]', lambda m: m.group(1)[0], result)
        
        # 替换转义的特殊字符
        result = result.replace('\\d', '1').replace('\\w', 'a').replace('\\.', '.')
        result = result.replace('\\', '')
        
        # 移除正则元字符
        for char in '^$+?*(){}|':
            result = result.replace(char, '')
        
        return result if result else "test_sample"

    def _import_rules(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "导入规则", "", "JSON 文件 (*.json)")
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                import json
                new_rules = json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "失败", f"读取文件失败: {str(e)}")
            return

        # 过滤掉重复规则
        added = 0
        skipped = 0
        duplicate_details = []

        for rule in new_rules:
            if isinstance(rule, dict) and rule.get("id", "").startswith("_"):
                # 跳过注释项
                continue
            if self._is_duplicate_rule(rule):
                skipped += 1
                match_list = rule.get("match", [])
                if match_list and len(duplicate_details) < 5:  # 只记录前5个重复项
                    match = match_list[0]
                    duplicate_details.append(f"- {match.get('field')}={match.get('value', '')[:50]}")
                continue
            self.rule_engine.rules.append(rule)
            added += 1

        self._load_rules()
        self._dirty = True

        # 构建提示信息
        msg_parts = [f"成功导入 {added} 条规则"]
        if skipped > 0:
            msg_parts.append(f"跳过 {skipped} 条重复规则")
        msg_parts.append("请点击\"保存\"以写入规则文件")

        if duplicate_details:
            msg_parts.append("\n重复规则示例:")
            msg_parts.extend(duplicate_details)
            if skipped > 5:
                msg_parts.append(f"... 还有 {skipped - 5} 条重复规则")

        QMessageBox.information(self, "导入完成", "\n".join(msg_parts))

    def _import_ioc(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "导入IOC", "", "文本/CSV/TSV (*.txt *.csv *.tsv);;所有文件 (*)")
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            QMessageBox.warning(self, "失败", f"读取失败: {str(e)}")
            return

        added = 0
        skipped = 0
        for rule in self._parse_ioc_rules(content):
            if self._is_duplicate_rule(rule):
                skipped += 1
                continue
            self.rule_engine.rules.append(rule)
            added += 1

        self._load_rules()
        self._dirty = True
        QMessageBox.information(self, "导入完成", f"新增 {added} 条，跳过 {skipped} 条\n请点击“保存”以写入规则文件")

    def _export_rules(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "导出规则", "rules.json", "JSON 文件 (*.json)")
        if not file_path:
            return
        ok, msg = self.rule_engine.save_rules_to_file(file_path)
        if ok:
            QMessageBox.information(self, "成功", msg)
        else:
            QMessageBox.warning(self, "失败", msg)

    def _save_rules(self, show_msg=True):
        self._apply_table_to_rules()
        ok, msg = self.rule_engine.save_rules_to_file(str(self.rule_engine.rules_path))
        if show_msg:
            if ok:
                QMessageBox.information(self, "成功", msg)
            else:
                QMessageBox.warning(self, "失败", msg)
        if ok:
            self._dirty = False

    def _save_rules_with_confirm(self):
        if not self._dirty:
            QMessageBox.information(self, "提示", "没有需要保存的变更")
            return
        reply = QMessageBox.question(
            self,
            "确认保存",
            "是否保存规则变更？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._save_rules(show_msg=True)

    def _on_item_changed(self, item):
        if self._loading:
            return
        self._dirty = True

    def closeEvent(self, event):
        if not self._dirty:
            event.accept()
            return
        reply = QMessageBox.question(
            self,
            "保存变更",
            "规则已修改，是否保存变更？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._save_rules(show_msg=True)
            event.accept()
        elif reply == QMessageBox.StandardButton.No:
            self.rule_engine.rules = copy.deepcopy(self._original_rules)
            event.accept()
        else:
            event.ignore()

    def _apply_table_to_rules(self):
        rules = []
        for row in range(self.table.rowCount()):
            field_item = self.table.item(row, 2)
            type_item = self.table.item(row, 3)
            value_item = self.table.item(row, 4)
            family_item = self.table.item(row, 1)
            severity_item = self.table.item(row, 5)
            date_item = self.table.item(row, 6)
            note_item = self.table.item(row, 7)
            id_item = self.table.item(row, 0)

            field = field_item.text().strip() if field_item else ""
            match_type = self._normalize_match_type(type_item.text() if type_item else "")
            # 使用_normalize_rule_value将UI输入值转换为JSON转义格式
            display_value = value_item.text().strip() if value_item else ""
            value = self._normalize_rule_value(display_value, match_type)
            family = family_item.text().strip() if family_item else ""
            severity = severity_item.text().strip() if severity_item else ""
            date = date_item.text().strip() if date_item else ""
            note = note_item.text().strip() if note_item else ""
            rule_id = id_item.text().strip() if id_item else f"rule_{uuid.uuid4().hex[:8]}"

            if not field or not match_type or not value:
                continue
            rule = {
                "id": rule_id,
                "family": family or "custom",
                "match": [
                    {"field": field, "type": match_type, "value": value}
                ],
                "severity": severity or "medium",
                "date": date,
                "note": note
            }
            rules.append(rule)
        self.rule_engine.rules = rules

    def _display_match_type(self, value: str) -> str:
        mapping = {
            "contains": "包含",
            "regex": "正则",
            "equals": "等于",
            "包含": "包含",
            "正则": "正则",
            "等于": "等于",
        }
        return mapping.get((value or "").strip(), value)

    def _display_rule_value(self, value: str, match_type: str = "contains") -> str:
        """将JSON转义值转换为可读格式显示
        
        JSON中的转义在UI显示时转换为实际字符:
        - \\\\  -> \\  (两个反斜杠显示为一个)
        - \\\"  -> \"  (转义的双引号显示为双引号)
        """
        if not value:
            return value
        # 将JSON转义转换为可读格式
        result = value.replace('\\\\', '\\').replace('\\"', '"')
        return result

    def _normalize_rule_value(self, value: str, match_type: str = "contains") -> str:
        """将UI输入值转换为JSON转义格式保存
        
        用户输入的实际字符需要转义为JSON格式:
        - \\  -> \\\\  (一个反斜杠转为两个)
        - \"  -> \\\"  (双引号需要转义)
        
        【重要】此函数检测值是否已经是JSON转义格式，避免重复转义
        """
        if not value:
            return value
        
        # 检测是否已经是JSON转义格式（包含\\或\\\"）
        # 如果已经是转义格式，直接返回
        if '\\\\' in value or '\\"' in value:
            return value
        
        # 将实际字符转义为JSON格式
        # 先处理双引号，再处理反斜杠
        result = value.replace('\\', '\\\\').replace('"', '\\"')
        return result

    def _normalize_match_type(self, value: str) -> str:
        mapping = {
            "包含": "contains",
            "正则": "regex",
            "等于": "equals",
            "contains": "contains",
            "regex": "regex",
            "equals": "equals",
        }
        return mapping.get((value or "").strip(), "contains")

    def _parse_ioc_rules(self, content: str):
        rules = []
        if not content:
            return rules

        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if not lines:
            return rules

        delimiter = "\t"
        sample = lines[0]
        if "\t" in sample:
            delimiter = "\t"
        elif "｜" in sample:
            delimiter = "｜"
        elif "|" in sample:
            delimiter = "|"
        elif "," in sample:
            delimiter = ","

        def split_line(line):
            parts = [p.strip() for p in line.split(delimiter)]
            return parts

        start_index = 0
        header = split_line(lines[0])
        if header:
            header_first = header[0].lower()
            if "ioc" in header_first or "indicator" in header_first or "指标" in header_first:
                start_index = 1

        for line in lines[start_index:]:
            cols = split_line(line)
            if not cols:
                continue
            ioc = cols[0].strip()
            if not ioc:
                continue
            ioc_type = cols[1].strip() if len(cols) > 1 else ""
            threat = cols[4].strip() if len(cols) > 4 else ""
            date = cols[5].strip() if len(cols) > 5 else ""
            note = cols[6].strip() if len(cols) > 6 else ""

            field, match_type = self._map_ioc_type(ioc_type, ioc)
            rule_note = self._compose_ioc_note(note)

            rule = {
                "id": f"ioc_{uuid.uuid4().hex[:8]}",
                "family": threat or "IOC",
                "match": [
                    {
                        "field": field,
                        "type": match_type,
                        "value": ioc
                    }
                ],
                "severity": "medium",
                "date": date,
                "note": rule_note
            }
            rules.append(rule)
        return rules

    def _map_ioc_type(self, ioc_type: str, ioc_value: str):
        text = (ioc_type or "").lower()
        value = (ioc_value or "").strip()
        if "ip" in text or "ip地址" in text:
            return "ip", "equals"
        if "sha256" in text or "sha-256" in text:
            return "sha256", "equals"
        if "md5" in text:
            return "md5", "equals"
        if "hash" in text or "哈希" in text:
            return self._guess_hash_field(value), "equals"
        if "域名" in text or "domain" in text:
            return "command_line", "contains"
        if "url" in text or "链接" in text:
            return "command_line", "contains"
        # auto detect
        if self._looks_like_ip(value):
            return "ip", "equals"
        if self._looks_like_hash(value):
            return self._guess_hash_field(value), "equals"
        return "command_line", "contains"

    def _compose_ioc_note(self, note: str):
        return (note or "").strip()

    def _looks_like_hash(self, value: str) -> bool:
        if not value:
            return False
        v = value.lower().strip()
        if len(v) in (32, 64):
            return all(c in "0123456789abcdef" for c in v)
        return False

    def _guess_hash_field(self, value: str) -> str:
        v = (value or "").strip()
        if len(v) == 64:
            return "sha256"
        if len(v) == 32:
            return "md5"
        return "sha256"

    def _looks_like_ip(self, value: str) -> bool:
        if not value:
            return False
        if ":" in value:
            return True
        parts = value.split(".")
        if len(parts) != 4:
            return False
        for part in parts:
            if not part.isdigit():
                return False
            num = int(part)
            if num < 0 or num > 255:
                return False
        return True

    def _is_duplicate_rule(self, rule):
        match_list = rule.get("match", [])
        if not match_list:
            return False
        target = match_list[0]
        field = target.get("field")
        match_type = target.get("type")
        value = target.get("value")
        for existing in self.rule_engine.rules:
            ex_list = existing.get("match", [])
            if not ex_list:
                continue
            ex = ex_list[0]
            if ex.get("field") == field and ex.get("type") == match_type and str(ex.get("value")).lower() == str(value).lower():
                return True
        return False


class WorkspaceTab(QWidget):
    """工作台标签页 - 聚合搜索、经验规则扫描与快速调查处置"""
    
    search_requested = pyqtSignal(str)  # 搜索请求信号
    jump_to_autorun = pyqtSignal(dict)  # 跳转到 Autoruns 条目信号
    
    def __init__(self, data_store=None, search_service=None):
        super().__init__()
        apply_flat_style(self)
        self.data_store = data_store
        self.search_service = search_service or SearchService(self.data_store)
        self.rule_engine = RuleEngine()
        self.command_manager = CommandTemplateManager()
        self.executor = SafeExecutor(self)
        self.path_resolver = PathResolver()
        self.current_data = []
        self.matched_results = []
        self.selected_entry = None
        self.selected_scope = PathScope.SELF
        self.result_mode = "autorun"
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        
        # 创建垂直分割器
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 上部：搜索区
        search_widget = self._create_search_widget()
        splitter.addWidget(search_widget)
        
        # 中部：结果列表
        results_widget = self._create_results_widget()
        splitter.addWidget(results_widget)
        
        # 下部：操作区
        action_widget = self._create_action_widget()
        splitter.addWidget(action_widget)
        
        # 设置分割器比例
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)
        
        layout.addWidget(splitter)
    
    def _create_search_widget(self):
        """创建搜索区域"""
        widget = QFrame()
        widget.setFrameStyle(QFrame.Shape.StyledPanel)
        widget.setObjectName("panel")
        layout = QVBoxLayout(widget)
        
        # 搜索框
        search_layout = QHBoxLayout()
        search_label = QLabel("全局搜索:")
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("支持 IP / 路径 / 命令行 / 关键字")
        self.search_box.textChanged.connect(self._on_search_changed)
        
        # 搜索按钮
        self.btn_search = QPushButton("搜索")
        self.btn_search.clicked.connect(self._perform_search)
        
        # 规则扫描按钮
        self.btn_scan_rules = QPushButton("规则扫描")
        self.btn_scan_rules.clicked.connect(self._scan_rules)
        
        # 规则管理按钮
        self.btn_manage_rules = QPushButton("规则管理")
        self.btn_manage_rules.clicked.connect(self._manage_rules)
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_box, 1)
        search_layout.addWidget(self.btn_search)
        search_layout.addWidget(self.btn_scan_rules)
        search_layout.addWidget(self.btn_manage_rules)
        
        layout.addLayout(search_layout)

        # 规则类型筛选
        rule_layout = QHBoxLayout()
        rule_label = QLabel("规则类型:")
        self.chk_rule_command = QCheckBox("命令行")
        self.chk_rule_path = QCheckBox("路径")
        self.chk_rule_ip = QCheckBox("IP")
        self.chk_rule_hash = QCheckBox("Hash")
        self.chk_rule_other = QCheckBox("其他")

        for chk in [self.chk_rule_command, self.chk_rule_path, self.chk_rule_ip, self.chk_rule_hash, self.chk_rule_other]:
            chk.setChecked(True)

        rule_layout.addWidget(rule_label)
        rule_layout.addWidget(self.chk_rule_command)
        rule_layout.addWidget(self.chk_rule_path)
        rule_layout.addWidget(self.chk_rule_ip)
        rule_layout.addWidget(self.chk_rule_hash)
        rule_layout.addWidget(self.chk_rule_other)
        rule_layout.addStretch()

        layout.addLayout(rule_layout)
        
        return widget
    
    def _create_results_widget(self):
        """创建结果列表区域"""
        widget = QFrame()
        widget.setFrameStyle(QFrame.Shape.StyledPanel)
        widget.setObjectName("panel")
        layout = QVBoxLayout(widget)
        
        # 结果表格
        self.results_table = QTableWidget()
        self._set_result_mode(self.result_mode)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setSortingEnabled(True)
        self.results_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.results_table.customContextMenuRequested.connect(self._show_context_menu)
        self.results_table.itemSelectionChanged.connect(self._on_result_selected)
        self.results_table.itemDoubleClicked.connect(self._on_result_double_clicked)
        
        layout.addWidget(self.results_table)
        
        return widget
    
    def _create_action_widget(self):
        """创建操作区域"""
        widget = QFrame()
        widget.setFrameStyle(QFrame.Shape.StyledPanel)
        widget.setObjectName("panel")
        layout = QVBoxLayout(widget)
        
        # Target Scope 选择
        scope_layout = QHBoxLayout()
        scope_label = QLabel("操作目标:")
        self.scope_group = QButtonGroup(self)
        
        self.rb_current_file = QRadioButton("当前文件")
        self.rb_current_dir = QRadioButton("所在目录")
        self.rb_parent_dir = QRadioButton("上一级目录")
        self.rb_manual = QRadioButton("手动选择")
        
        self.rb_current_file.setChecked(True)
        
        self.scope_group.addButton(self.rb_current_file, 0)
        self.scope_group.addButton(self.rb_current_dir, 1)
        self.scope_group.addButton(self.rb_parent_dir, 2)
        self.scope_group.addButton(self.rb_manual, 3)
        
        self.scope_group.idClicked.connect(self._on_scope_changed)
        
        scope_layout.addWidget(scope_label)
        scope_layout.addWidget(self.rb_current_file)
        scope_layout.addWidget(self.rb_current_dir)
        scope_layout.addWidget(self.rb_parent_dir)
        scope_layout.addWidget(self.rb_manual)
        scope_layout.addStretch()
        
        layout.addLayout(scope_layout)
        
        # 命令模板选择
        preset_layout = QHBoxLayout()
        preset_label = QLabel("命令模板:")
        self.cmb_preset = QComboBox()
        self._populate_presets()
        self.cmb_preset.currentTextChanged.connect(self._on_preset_changed)
        
        preset_layout.addWidget(preset_label)
        preset_layout.addWidget(self.cmb_preset, 1)
        
        layout.addLayout(preset_layout)
        
        # 命令预览
        cmd_label = QLabel("命令预览:")
        layout.addWidget(cmd_label)
        
        self.cmd_preview = QTextEdit()
        self.cmd_preview.setMaximumHeight(80)
        self.cmd_preview.setReadOnly(True)
        layout.addWidget(self.cmd_preview)
        
        # 执行按钮
        btn_layout = QHBoxLayout()
        self.btn_execute = QPushButton("执行命令")
        self.btn_execute.setEnabled(False)
        self.btn_execute.clicked.connect(self._execute_command)
        
        self.btn_clear = QPushButton("清空结果")
        self.btn_clear.clicked.connect(self._clear_results)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_clear)
        btn_layout.addWidget(self.btn_execute)
        
        layout.addLayout(btn_layout)
        
        return widget
    
    def _populate_presets(self):
        """填充命令模板下拉框"""
        self.cmb_preset.clear()
        self.cmb_preset.addItem("选择命令模板...")
        for template in self.command_manager.get_all_templates():
            self.cmb_preset.addItem(template.name, template.template_id)

    def _set_result_mode(self, mode: str):
        """设置结果表格列"""
        self.result_mode = mode
        if mode == "autorun":
            headers = ["Category", "Entry", "Description", "Publisher", "Image Path"]
        elif mode == "ip":
            headers = ["Type", "Matched", "Source", "PID", "进程名", "源IP:端口 -> 目的IP:端口", "路径"]
        else:
            # rule 模式：添加规则详情列显示匹配的规则和值
            headers = ["Type", "Matched", "Source", "Summary", "规则详情"]
        self.results_table.setColumnCount(len(headers))
        self.results_table.setHorizontalHeaderLabels(headers)
        self.results_table.horizontalHeader().setStretchLastSection(True)
    
    def _on_search_changed(self):
        """搜索文本变化"""
        try:
            pass
        except Exception as e:
            QMessageBox.warning(self, "错误", f"搜索文本变化处理失败: {str(e)}")
    
    def _get_entry_field_value(self, entry: dict, key: str):
        """从 entry 或 detail_data 中获取字段值"""
        value = entry.get(key)
        if value:
            return value
        detail = entry.get('detail_data')
        if isinstance(detail, dict):
            value = detail.get(key)
            if value:
                return value
        return ""
    
    def _perform_search(self):
        """执行搜索"""
        try:
            if not self.search_service:
                QMessageBox.warning(self, "警告", "搜索服务未初始化")
                return
            
            search_text = self.search_box.text().strip()
            if not search_text:
                QMessageBox.warning(self, "警告", "请输入搜索内容")
                return

            results_bundle = self.search_service.search(search_text)

            if results_bundle.mode == "keyword":
                if not self.search_service.has_autoruns_data():
                    QMessageBox.warning(self, "警告", "暂无持久化数据，请先在持久化检测中扫描")
                    return
                self._set_result_mode("autorun")
            else:
                if not self.search_service.has_autoruns_data() and not self.search_service.has_network_data():
                    QMessageBox.warning(self, "警告", "暂无可搜索的数据，请先扫描/刷新")
                    return
                self._set_result_mode("ip")

            self.matched_results = results_bundle.results
            self._update_results_table()
        except Exception as e:
            QMessageBox.warning(self, "错误", f"搜索失败: {str(e)}")
    
    def _scan_rules(self):
        """执行规则扫描"""
        try:
            if not self.search_service:
                QMessageBox.warning(self, "警告", "搜索服务未初始化")
                return

            allowed_types = self._get_selected_rule_types()
            if not allowed_types:
                QMessageBox.warning(self, "提示", "请至少选择一种规则类型")
                return

            # 判断是否需要扫描持久化数据
            needs_autoruns = bool(allowed_types - {"ip"})  # 除了 IP 之外还有其他类型
            
            # 获取 Autoruns 数据（如果需要）
            self.current_data = []
            if needs_autoruns:
                self.current_data = self.search_service.get_autoruns_entries()
                if not self.current_data:
                    QMessageBox.warning(self, "警告", "暂无持久化数据，请先在持久化检测中扫描")
                    return

                if "hash" in allowed_types and self._has_hash_rules(allowed_types) and self._hash_missing_all(self.current_data):
                    QMessageBox.information(
                        self,
                        "提示",
                        "检测到 Hash 规则，但当前条目未计算 Hash。\n\n"
                        "建议在持久化检测中勾选\"计算Hash\"后重新扫描。"
                    )
            
            # 扫描规则
            self.matched_results = []
            
            # 扫描 Autoruns 数据
            for entry in self.current_data:
                matched_rules = self.rule_engine.scan_entry(entry, allowed_types)
                if matched_rules:
                    # 获取最高严重级别
                    severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
                    max_severity = min(
                        matched_rules, 
                        key=lambda r: severity_order.get(r.get('severity', 'low'), 99)
                    ).get('severity', 'low')
                    
                    # 构建更详细的摘要，包含条目的位置和名称
                    entry_name = entry.get('entry', 'Unknown')
                    entry_location = entry.get('location', 'Unknown')
                    summary = f"[{entry_location}] {entry_name} 命中 {len(matched_rules)} 条规则"
                    
                    result = SearchResult(
                        result_type=ResultType.AUTORUN,
                        summary=summary,
                        source='rule_scan',
                        detail={
                            'entry': entry,
                            'matched_rules': matched_rules,
                            'severity': max_severity
                        },
                        matched_value=', '.join([r.get('family', r.get('id', '')) for r in matched_rules]),
                        related_entry=entry
                    )
                    self.matched_results.append(result)
            
            # 扫描网络连接数据（IP 规则）
            if "ip" in allowed_types:
                network_data = self.search_service.get_network_connections()
                for conn in network_data:
                    # 将网络连接转换为条目格式
                    entry = {
                        'location': 'Network',
                        'entry': f"PID:{conn.get('pid', '')}",
                        'category': 'Network',
                        'description': f"{conn.get('local_address', '')} -> {conn.get('remote_address', '')}",
                        'publisher': '',
                        'company': '',
                        'image_path': conn.get('process_path', ''),
                        'launch_string': '',
                        'timestamp': '',
                        'md5': '',
                        'sha256': '',
                        'signer': '',
                        'signer_status': '',
                        'signature_detail': '',
                        'file_size': '',
                        'file_version': '',
                        'service_name': '',
                        'file_exists': True,
                        'detail_data': conn
                    }
                    
                    matched_rules = self.rule_engine.scan_entry(entry, allowed_types)
                    if matched_rules:
                        # 获取最高严重级别
                        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
                        max_severity = min(
                            matched_rules, 
                            key=lambda r: severity_order.get(r.get('severity', 'low'), 99)
                        ).get('severity', 'low')
                        
                        # 构建摘要
                        local_addr = conn.get('local_address', '')
                        remote_addr = conn.get('remote_address', '')
                        summary = f"[Network] {local_addr} -> {remote_addr} 命中 {len(matched_rules)} 条规则"
                        
                        result = SearchResult(
                            result_type=ResultType.IP_MATCH,
                            summary=summary,
                            source='rule_scan',
                            detail={
                                'entry': entry,
                                'matched_rules': matched_rules,
                                'severity': max_severity,
                                'kind': 'network',
                                'connection': conn
                            },
                            matched_value=', '.join([r.get('family', r.get('id', '')) for r in matched_rules]),
                            related_entry=None
                        )
                        self.matched_results.append(result)

            self._set_result_mode("rule")
            self._update_results_table()
            if not self.matched_results:
                QMessageBox.information(self, "扫描完成", "规则扫描完成，未发现命中项。")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"规则扫描失败: {str(e)}")

    def _get_selected_rule_types(self):
        types = set()
        if self.chk_rule_command.isChecked():
            types.add("command")
        if self.chk_rule_path.isChecked():
            types.add("path")
        if self.chk_rule_ip.isChecked():
            types.add("ip")
        if self.chk_rule_hash.isChecked():
            types.add("hash")
        if self.chk_rule_other.isChecked():
            types.add("other")
        return types

    def _has_hash_rules(self, allowed_types=None) -> bool:
        if allowed_types and "hash" not in allowed_types:
            return False
        for rule in self.rule_engine.rules:
            match_list = rule.get("match", [])
            for cond in match_list:
                if cond.get("field") in ("hash", "sha256", "md5"):
                    return True
        return False

    def _hash_missing_all(self, entries):
        for entry in entries:
            sha256 = entry.get("sha256", "")
            md5 = entry.get("md5", "")
            detail = entry.get("detail_data")
            detail_hash = ""
            if isinstance(detail, dict):
                detail_hash = detail.get("hash", "") or detail.get("sha256", "") or detail.get("md5", "")
            if sha256 or md5 or detail_hash:
                return False
        return True
    
    def _update_results_table(self):
        """更新结果表格"""
        try:
            sorting_enabled = self.results_table.isSortingEnabled()
            if sorting_enabled:
                self.results_table.setSortingEnabled(False)
            self.results_table.setRowCount(0)
            if self.result_mode == "autorun":
                for idx, result in enumerate(self.matched_results):
                    entry = result.related_entry or result.detail.get('entry', {})
                    self.results_table.insertRow(idx)

                    self.results_table.setItem(idx, 0, QTableWidgetItem(entry.get('category', '')))
                    self.results_table.setItem(idx, 1, QTableWidgetItem(entry.get('entry', '')))
                    self.results_table.setItem(idx, 2, QTableWidgetItem(entry.get('description', '')))
                    self.results_table.setItem(idx, 3, QTableWidgetItem(entry.get('publisher', '')))
                    self.results_table.setItem(idx, 4, QTableWidgetItem(entry.get('image_path', '')))
            elif self.result_mode == "ip":
                for idx, result in enumerate(self.matched_results):
                    self.results_table.insertRow(idx)

                    # Type
                    detail_kind = result.detail.get('kind') if isinstance(result.detail, dict) else None
                    if detail_kind == "network":
                        type_text = "Network"
                    elif detail_kind == "autorun":
                        type_text = "Autorun"
                    else:
                        type_text = "IP" if result.result_type == ResultType.IP_MATCH else "Autorun"
                    type_item = QTableWidgetItem(type_text)
                    if result.result_type == ResultType.IP_MATCH:
                        type_item.setBackground(QColor(200, 220, 255))
                    self.results_table.setItem(idx, 0, type_item)

                    # Matched
                    self.results_table.setItem(idx, 1, QTableWidgetItem(result.matched_value))

                    # Source
                    source_text = result.source
                    if result.source == 'command_line':
                        source_text = 'Command Line'
                    elif result.source == 'image_path':
                        source_text = 'Image Path'
                    elif result.source == 'rule_scan':
                        source_text = 'Rule Scan'
                    elif result.source == 'local_address':
                        source_text = 'Local Address'
                    elif result.source == 'remote_address':
                        source_text = 'Remote Address'
                    self.results_table.setItem(idx, 2, QTableWidgetItem(source_text))

                    # PID / 进程名 / 流向
                    pid_text = ""
                    proc_name = ""
                    flow_text = ""
                    proc_path = ""
                    if isinstance(result.detail, dict) and result.detail.get('kind') == "network":
                        conn = result.detail.get('connection', {})
                        pid_value = conn.get('pid', '')
                        pid_text = str(pid_value) if pid_value is not None else ""
                        proc_name = str(conn.get('process_name', '') or '')
                        proc_path = str(conn.get('process_path', '') or '')
                        local_addr = str(conn.get('local_address', '') or '')
                        remote_addr = str(conn.get('remote_address', '') or '')
                        local_port = conn.get('local_port', '')
                        remote_port = conn.get('remote_port', '')
                        local_display = f"{local_addr}:{local_port}" if local_addr else ""
                        remote_display = f"{remote_addr}:{remote_port}" if remote_addr else ""
                        if local_display or remote_display:
                            flow_text = f"{local_display} -> {remote_display}"

                    pid_item = NumericTableWidgetItem(pid_text, int(pid_text) if pid_text.isdigit() else None)
                    self.results_table.setItem(idx, 3, pid_item)
                    self.results_table.setItem(idx, 4, QTableWidgetItem(proc_name))
                    self.results_table.setItem(idx, 5, QTableWidgetItem(flow_text))
                    self.results_table.setItem(idx, 6, QTableWidgetItem(proc_path))
            else:
                for idx, result in enumerate(self.matched_results):
                    self.results_table.insertRow(idx)

                    # Type
                    type_text = "IP" if result.result_type == ResultType.IP_MATCH else "Autorun"
                    type_item = QTableWidgetItem(type_text)
                    if result.result_type == ResultType.IP_MATCH:
                        type_item.setBackground(QColor(200, 220, 255))
                    self.results_table.setItem(idx, 0, type_item)

                    # Matched
                    self.results_table.setItem(idx, 1, QTableWidgetItem(result.matched_value))

                    # Source
                    source_text = result.source
                    if result.source == 'command_line':
                        source_text = 'Command Line'
                    elif result.source == 'image_path':
                        source_text = 'Image Path'
                    elif result.source == 'rule_scan':
                        source_text = 'Rule Scan'
                    self.results_table.setItem(idx, 2, QTableWidgetItem(source_text))

                    # Summary
                    summary_item = QTableWidgetItem(result.summary)

                    # 如果是规则扫描结果，显示严重级别颜色
                    if result.source == 'rule_scan' and result.detail.get('severity'):
                        severity = result.detail.get('severity')
                        if severity == 'high':
                            summary_item.setBackground(QColor(255, 200, 200))
                        elif severity == 'medium':
                            summary_item.setBackground(QColor(255, 255, 200))

                    self.results_table.setItem(idx, 3, summary_item)

                    # 规则详情列：显示匹配的规则和值
                    rule_details = []
                    if result.source == 'rule_scan' and result.detail.get('matched_rules'):
                        for rule in result.detail['matched_rules']:
                            match_list = rule.get('match', [])
                            if match_list:
                                match = match_list[0]
                                field = match.get('field', '')
                                match_type = match.get('type', '')
                                value = match.get('value', '')
                                # 简化显示
                                if len(value) > 30:
                                    value = value[:27] + "..."
                                rule_details.append(f"{field}({match_type})={value}")
                    rule_detail_text = "; ".join(rule_details) if rule_details else ""
                    self.results_table.setItem(idx, 4, QTableWidgetItem(rule_detail_text))

            # 调整列宽
            self.results_table.resizeColumnsToContents()
            if sorting_enabled:
                self.results_table.setSortingEnabled(True)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"更新结果表格失败: {str(e)}")
    
    def _on_result_selected(self):
        """结果选中时触发"""
        try:
            selected_items = self.results_table.selectedItems()
            if not selected_items:
                self.btn_execute.setEnabled(False)
                self.cmd_preview.clear()
                self.selected_entry = None
                return
            
            row = selected_items[0].row()
            if row < len(self.matched_results):
                result = self.matched_results[row]
                if result.related_entry:
                    self.selected_entry = result.related_entry
                    self._update_command_preview()
                else:
                    self.selected_entry = None
                    self.cmd_preview.clear()
                    self.btn_execute.setEnabled(False)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"结果选中处理失败: {str(e)}")
    
    def _on_result_double_clicked(self, item):
        """结果双击时触发"""
        try:
            row = item.row()
            if row < len(self.matched_results):
                result = self.matched_results[row]
                if result.related_entry:
                    self.jump_to_autorun.emit(result.related_entry)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"跳转失败: {str(e)}")
    
    def _on_scope_changed(self, scope_id):
        """Target Scope 变化时触发"""
        try:
            # 映射 scope_id 到 PathScope
            scope_map = {
                0: PathScope.SELF,
                1: PathScope.DIRECTORY,
                2: PathScope.PARENT,
                3: PathScope.SELF  # 手动选择后仍然是 SELF
            }
            self.selected_scope = scope_map.get(scope_id, PathScope.SELF)
            
            # 如果是手动选择，弹出对话框
            if scope_id == 3:
                path = PathResolver.select_directory(self, "选择目标目录")
                if path:
                    self.selected_entry = {'image_path': path}
            
            self._update_command_preview()
        except Exception as e:
            QMessageBox.warning(self, "错误", f"Target Scope 变化处理失败: {str(e)}")
    
    def _on_preset_changed(self):
        """命令模板变化时触发"""
        try:
            self._update_command_preview()
        except Exception as e:
            QMessageBox.warning(self, "错误", f"命令模板变化处理失败: {str(e)}")
    
    def _update_command_preview(self):
        """更新命令预览"""
        try:
            if not self.selected_entry:
                return
            
            image_path = self.selected_entry.get('image_path', '')
            preset_id = self.cmb_preset.currentData()
            
            if not preset_id:
                self.cmd_preview.clear()
                self.btn_execute.setEnabled(False)
                return
            
            # 根据 Target Scope 确定目标
            target = PathResolver.resolve(image_path, self.selected_scope)
            
            if not target:
                self.cmd_preview.clear()
                self.btn_execute.setEnabled(False)
                return
            
            # 应用命令模板
            if preset_id == "encrypt_compress":
                # 加密压缩需要 input 和 output 参数
                output_path = self._generate_output_path(target)
                command = self.command_manager.apply_template(
                    preset_id, 
                    input=target, 
                    output=output_path, 
                    password="1"
                )
            else:
                # 其他命令只需要 target 参数
                command = self.command_manager.apply_template(preset_id, target=target)
            
            if not command:
                self.cmd_preview.clear()
                self.btn_execute.setEnabled(False)
                return
            
            self.cmd_preview.setText(command)
            self.btn_execute.setEnabled(True)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"更新命令预览失败: {str(e)}")
    
    def _generate_output_path(self, input_path: str) -> str:
        """生成输出路径"""
        import os
        # 如果输入是文件，生成同名 .zip 文件
        if os.path.isfile(input_path):
            base = os.path.splitext(input_path)[0]
            return f"{base}.zip"
        # 如果输入是目录，生成 目录名.zip
        else:
            dir_name = os.path.basename(input_path.rstrip(os.sep))
            return os.path.join(os.path.dirname(input_path), f"{dir_name}.zip")
    
    def _execute_command(self):
        """执行命令"""
        try:
            command = self.cmd_preview.toPlainText()
            if not command:
                return
            
            preset_id = self.cmb_preset.currentData()
            
            # 如果是加密压缩，让用户选择输出路径
            if preset_id == "encrypt_compress":
                image_path = self.selected_entry.get('image_path', '')
                target = PathResolver.resolve(image_path, self.selected_scope)
                default_output = self._generate_output_path(target)
                
                # 弹出保存对话框
                output_path = PathResolver.save_file(
                    self,
                    "选择压缩文件保存位置",
                    os.path.basename(default_output),
                    "ZIP 文件 (*.zip)"
                )
                
                if not output_path:
                    return  # 用户取消
                
                # 检测 7z 是否可用
                if self._check_7z_available():
                    # 使用 7z 命令
                    command = self.command_manager.apply_template(
                        preset_id,
                        input=target,
                        output=output_path,
                        password="1"
                    )
                    
                    # 使用 SafeExecutor 执行命令
                    def callback(result: CommandResult):
                        print(f"[Workspace] 命令执行完成")
                        print(f"[Workspace] 状态: {result.status}")
                        print(f"[Workspace] 返回码: {result.return_code}")
                        print(f"[Workspace] 标准输出: {result.stdout}")
                        print(f"[Workspace] 标准错误: {result.stderr}")
                        print(f"[Workspace] 错误信息: {result.error_message}")
                        
                        if result.status == CommandStatus.SUCCESS:
                            QMessageBox.information(self, "成功", "命令执行成功")
                        else:
                            error_msg = result.error_message or result.stderr
                            full_msg = f"命令执行失败\n\n错误信息:\n{error_msg}\n\n返回码: {result.return_code}"
                            QMessageBox.warning(self, "执行失败", full_msg)
                    
                    print(f"[Workspace] 准备执行命令: {command}")
                    self.executor.execute(command, callback)
                else:
                    # 使用 pyzipper 作为备选方案
                    self._compress_with_pyzipper(target, output_path, "1")
                return
            
            # 其他命令执行
            command = self.cmd_preview.toPlainText()
            if not command:
                return
            
            # 使用 SafeExecutor 执行命令
            def callback(result: CommandResult):
                print(f"[Workspace] 命令执行完成")
                print(f"[Workspace] 状态: {result.status}")
                print(f"[Workspace] 返回码: {result.return_code}")
                print(f"[Workspace] 标准输出: {result.stdout}")
                print(f"[Workspace] 标准错误: {result.stderr}")
                print(f"[Workspace] 错误信息: {result.error_message}")
                
                if result.status == CommandStatus.SUCCESS:
                    QMessageBox.information(self, "成功", "命令执行成功")
                else:
                    error_msg = result.error_message or result.stderr
                    full_msg = f"命令执行失败\n\n错误信息:\n{error_msg}\n\n返回码: {result.return_code}"
                    QMessageBox.warning(self, "执行失败", full_msg)
            
            print(f"[Workspace] 准备执行命令: {command}")
            self.executor.execute(command, callback)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"执行命令失败: {str(e)}")
    
    def _check_7z_available(self) -> bool:
        """检测 7z 是否可用"""
        try:
            import shutil
            return shutil.which("7z") is not None
        except Exception:
            return False
    
    def _compress_with_pyzipper(self, input_path: str, output_path: str, password: str):
        """使用 pyzipper 进行加密压缩"""
        try:
            import pyzipper
            import os
            
            print(f"[Workspace] 使用 pyzipper 压缩: {input_path} -> {output_path}")
            
            # 创建加密的 ZIP 文件
            with pyzipper.AESZipFile(
                output_path, 
                'w', 
                compression=pyzipper.ZIP_DEFLATED, 
                encryption=pyzipper.WZ_AES
            ) as zipf:
                zipf.setpassword(password.encode('utf-8'))
                
                # 如果是文件，直接添加
                if os.path.isfile(input_path):
                    filename = os.path.basename(input_path)
                    zipf.write(input_path, filename)
                # 如果是目录，递归添加所有文件
                elif os.path.isdir(input_path):
                    for root, dirs, files in os.walk(input_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, os.path.dirname(input_path))
                            zipf.write(file_path, arcname)
            
            print(f"[Workspace] 压缩完成")
            QMessageBox.information(self, "成功", f"文件已加密压缩并保存到：\n{output_path}\n\n密码: {password}")
            
        except ImportError:
            QMessageBox.critical(self, "错误", "pyzipper 库未安装\n\n请运行: pip install pyzipper")
        except PermissionError as e:
            QMessageBox.critical(self, "错误", f"权限不足: {str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"压缩失败: {str(e)}")
    
    def _clear_results(self):
        """清空结果"""
        try:
            self.matched_results = []
            self.results_table.setRowCount(0)
            self._set_result_mode("autorun")
            self.cmd_preview.clear()
            self.btn_execute.setEnabled(False)
            self.selected_entry = None
        except Exception as e:
            QMessageBox.warning(self, "错误", f"清空结果失败: {str(e)}")
    
    def _manage_rules(self):
        """规则管理"""
        try:
            dialog = RuleManagerDialog(self.rule_engine, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.warning(self, "错误", f"规则管理失败: {str(e)}")
    
    def _show_context_menu(self, pos):
        """显示右键菜单"""
        try:
            selected_items = self.results_table.selectedItems()
            if not selected_items:
                return
            
            row = selected_items[0].row()
            if row >= len(self.matched_results):
                return
            
            result = self.matched_results[row]
            if result:
                entry = result.related_entry or result.detail.get('entry', {})
            else:
                entry = {}
            if not entry:
                return
            image_path = self._get_entry_field_value(entry, 'image_path')
            launch_string = self._get_entry_field_value(entry, 'launch_string') or self._get_entry_field_value(entry, 'command_line')
            
            menu = QMenu(self)
            
            # 在资源管理器中打开
            if image_path and image_path.lower() != 'file not found':
                action_open = menu.addAction("在资源管理器中打开")
                action_open.triggered.connect(lambda: self._open_in_explorer(image_path))
            
            # 复制路径
            if image_path:
                action_copy_path = menu.addAction("复制路径")
                action_copy_path.triggered.connect(lambda: self._copy_to_clipboard(image_path))
            
            # 复制命令
            if launch_string:
                action_copy_cmd = menu.addAction("复制命令")
                action_copy_cmd.triggered.connect(lambda: self._copy_to_clipboard(launch_string))
            
            menu.exec(self.results_table.viewport().mapToGlobal(pos))
        except Exception as e:
            QMessageBox.warning(self, "错误", f"显示右键菜单失败: {str(e)}")
    
    def _open_in_explorer(self, path):
        """在资源管理器中打开文件"""
        try:
            import subprocess
            if os.path.exists(path):
                if os.path.isdir(path):
                    subprocess.run(['explorer', path], check=False)
                else:
                    subprocess.run(['explorer', '/select,', path], check=False)
            else:
                QMessageBox.warning(self, "警告", f"文件不存在: {path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开文件: {str(e)}")
    
    def _copy_to_clipboard(self, text):
        """复制到剪贴板"""
        try:
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(text)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"复制到剪贴板失败: {str(e)}")
    
    def search(self, search_text):
        """执行搜索（供外部调用）"""
        try:
            self.search_box.setText(search_text)
            self._perform_search()
        except Exception as e:
            QMessageBox.warning(self, "错误", f"搜索失败: {str(e)}")
    
    def cleanup(self):
        """清理资源"""
        self.executor.cleanup()
