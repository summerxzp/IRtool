from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QComboBox, QMessageBox, QLineEdit, QLabel,
    QTextEdit, QFileDialog, QAbstractItemView, QDialog,
    QDialogButtonBox, QFormLayout
)
from PyQt6.QtGui import QColor
import uuid
import copy

from core.rule_engine import RuleEngine
from ui.ui_style import apply_flat_style

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
        
        # 定义下拉框选项
        field_options = [
            "command_line", "image_path", "entry", "description",
            "publisher", "company", "location", "category", "launch_string",
            "ip", "hash", "sha256", "md5"
        ]
        type_options = ["包含", "正则", "等于"]
        severity_options = ["critical", "high", "medium", "low"]
        
        for idx, rule in enumerate(rules):
            self.table.insertRow(idx)
            match_list = rule.get("match", [])
            first_match = match_list[0] if match_list else {}
            display_type = self._display_match_type(first_match.get("type", ""))
            
            # ID 列 (隐藏)
            self.table.setItem(idx, 0, QTableWidgetItem(rule.get("id", "")))
            
            # Family 列 (文本)
            self.table.setItem(idx, 1, QTableWidgetItem(rule.get("family", "")))
            
            # Field 列 (下拉框)
            field_combo = QComboBox()
            field_combo.addItems(field_options)
            field_combo.setCurrentText(first_match.get("field", "command_line"))
            field_combo.currentTextChanged.connect(lambda: self._on_combo_changed())
            self.table.setCellWidget(idx, 2, field_combo)
            
            # Type 列 (下拉框)
            type_combo = QComboBox()
            type_combo.addItems(type_options)
            type_combo.setCurrentText(display_type)
            type_combo.currentTextChanged.connect(lambda: self._on_combo_changed())
            self.table.setCellWidget(idx, 3, type_combo)
            
            # Value 列 (文本)
            display_value = self._display_rule_value(
                first_match.get("value", ""),
                first_match.get("type", "contains")
            )
            self.table.setItem(idx, 4, QTableWidgetItem(display_value))
            
            # Severity 列 (下拉框)
            severity_combo = QComboBox()
            severity_combo.addItems(severity_options)
            severity_combo.setCurrentText(rule.get("severity", "medium"))
            severity_combo.currentTextChanged.connect(lambda: self._on_combo_changed())
            self.table.setCellWidget(idx, 5, severity_combo)
            
            # Date 列 (文本)
            self.table.setItem(idx, 6, QTableWidgetItem(rule.get("date", "")))
            
            # Note 列 (文本)
            self.table.setItem(idx, 7, QTableWidgetItem(rule.get("note", "")))
            
            self._rule_index_by_row.append(idx)
        
        self.table.resizeColumnsToContents()
        self.table.setColumnHidden(0, True)
        self._loading = False
        self._dirty = False
    
    def _on_combo_changed(self):
        """下拉框值改变时触发"""
        if not self._loading:
            self._dirty = True

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

<div style="background:#fff3cd;padding:15px;border-radius:5px;margin-bottom:20px;">
<h3>重要设计理念</h3>
<p><b>本工具是分析型安全工具，不是 IOC 查询工具。</b></p>
<ul>
<li>IP 不支持搜索框直接搜索，只能通过<b>规则扫描</b>发现</li>
<li>IP 扫描基于历史数据快照，<b>非实时监控</b></li>
<li>规则目标是发现"相同特征的可疑条目"，不进行自动定性</li>
<li>最终判定需要人工确认</li>
</ul>
</div>

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
<li><b>重要提示</b>：
    <ul>
    <li><b>搜索框不再支持直接搜索 IP</b> - IP 只能通过规则扫描发现</li>
    <li>IP 扫描基于历史连接记录和已采集的数据快照，<b>非实时监控</b></li>
    <li>IP 匹配结果会绑定到具体条目，作为"被规则命中的证据"呈现</li>
    <li>扫描结果是辅助分析，<b>不代表最终定性</b></li>
    </ul>
</li>
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
            value_item = self.table.item(row, 4)
            family_item = self.table.item(row, 1)
            date_item = self.table.item(row, 6)
            note_item = self.table.item(row, 7)
            id_item = self.table.item(row, 0)

            # 从下拉框获取值
            field_combo = self.table.cellWidget(row, 2)
            type_combo = self.table.cellWidget(row, 3)
            severity_combo = self.table.cellWidget(row, 5)
            
            field = field_combo.currentText() if field_combo else ""
            match_type = self._normalize_match_type(type_combo.currentText() if type_combo else "")
            severity = severity_combo.currentText() if severity_combo else ""
            
            # 使用_normalize_rule_value将UI输入值转换为JSON转义格式
            display_value = value_item.text().strip() if value_item else ""
            value = self._normalize_rule_value(display_value, match_type)
            family = family_item.text().strip() if family_item else ""
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


