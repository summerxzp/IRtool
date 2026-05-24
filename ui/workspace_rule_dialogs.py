from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QMessageBox, QLineEdit, QLabel,
    QTextEdit, QFileDialog, QAbstractItemView, QDialog,
    QDialogButtonBox, QFormLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
import uuid
import copy

from core.rule_engine import RuleEngine
from ui.ui_style import apply_flat_style
from ui.dropdown_button import DropdownButton

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
        self.edt_rule_name = QLineEdit("custom")
        self.cmb_field = DropdownButton()
        self.cmb_field.addItems([
            "command_line", "image_path", "entry", "description",
            "publisher", "company", "location", "category", "launch_string",
            "ip", "hash", "sha256", "md5"
        ])
        self.cmb_type = DropdownButton()
        self.cmb_type.addItems(["包含", "正则", "等于"])
        self.edt_value = QLineEdit()
        self.cmb_severity = DropdownButton()
        self.cmb_severity.addItems(["critical", "high", "medium", "low"])
        self.edt_date = QLineEdit()
        self.edt_note = QLineEdit()

        form.addRow("规则ID", self.edt_id)
        form.addRow("规则名称", self.edt_rule_name)
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
            "family": self.edt_rule_name.text().strip() or "test",
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

        matched = []
        for entry in test_entries:
            if engine.match_entry(entry):
                matched.append(entry)

        # 显示结果
        if matched:
            self.lbl_test_result.setText(f"✓ 测试通过！命中 {len(matched)} 条样本")
            self.lbl_test_result.setStyleSheet("color: green;")
        else:
            self.lbl_test_result.setText("✗ 未命中任何测试样本，请检查规则配置")
            self.lbl_test_result.setStyleSheet("color: red;")

        self._test_results = matched

    def _generate_test_entries(self, field, value, match_type):
        """生成测试样本"""
        entries = []
        if field == "command_line":
            entries = [
                {"command_line": f"test {value} test", "entry": "test1"},
                {"command_line": value, "entry": "test2"},
                {"command_line": "normal command", "entry": "test3"}
            ]
        elif field == "image_path":
            entries = [
                {"image_path": f"C:\\Windows\\{value}", "entry": "test1"},
                {"image_path": value, "entry": "test2"},
                {"image_path": "C:\\normal.exe", "entry": "test3"}
            ]
        elif field in ("sha256", "md5", "hash"):
            entries = [
                {"sha256": value, "entry": "test1"},
                {"sha256": "a" * 64, "entry": "test2"}
            ]
        elif field == "ip":
            entries = [
                {"command_line": f"connect to {value}", "entry": "test1"},
                {"command_line": "normal traffic", "entry": "test2"}
            ]
        else:
            entries = [
                {field: value, "entry": "test1"},
                {field: f"prefix_{value}_suffix", "entry": "test2"},
                {field: "normal value", "entry": "test3"}
            ]
        return entries

    def _on_accept(self):
        if not self.edt_value.text().strip():
            QMessageBox.warning(self, "提示", "匹配值不能为空")
            return
        self.accept()

    def _normalize_match_type(self, text):
        mapping = {
            "包含": "contains",
            "正则": "regex",
            "等于": "equals",
            "contains": "contains",
            "regex": "regex",
            "equals": "equals",
        }
        return mapping.get((text or "").strip(), "contains")

    def get_rule(self):
        return {
            "id": self.edt_id.text().strip() or f"rule_{uuid.uuid4().hex[:8]}",
            "family": self.edt_rule_name.text().strip() or "custom",
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


class IOCImportDialog(QDialog):
    """IOC导入对话框：支持表格粘贴和编辑"""
    def __init__(self, parent=None):
        super().__init__(parent)
        apply_flat_style(self)
        self.setWindowTitle("导入IOC")
        self.setMinimumSize(900, 500)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 说明标签
        hint_label = QLabel("从<b>IOC情报协作</b>中复制数据后直接点击粘贴到表格，或选择文件导入。只提取：值、类型、名称、时间、备注")
        hint_label.setTextFormat(Qt.TextFormat.RichText)
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)

        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["值(必填)", "类型", "标签", "动作", "名称", "时间", "备注"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        # 按钮区域
        btn_layout = QHBoxLayout()
        self.btn_paste = QPushButton("粘贴")
        self.btn_paste.setToolTip("从剪贴板粘贴数据")
        self.btn_paste.clicked.connect(self._paste_from_clipboard)
        self.btn_select_file = QPushButton("选择文件...")
        self.btn_select_file.clicked.connect(self._select_file)
        self.btn_clear = QPushButton("清空")
        self.btn_clear.clicked.connect(self._clear_table)
        self.btn_delete_row = QPushButton("删除选中行")
        self.btn_delete_row.clicked.connect(self._delete_selected_rows)
        btn_layout.addWidget(self.btn_paste)
        btn_layout.addWidget(self.btn_select_file)
        btn_layout.addWidget(self.btn_clear)
        btn_layout.addWidget(self.btn_delete_row)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 对话框按钮
        dialog_buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        dialog_buttons.accepted.connect(self.accept)
        dialog_buttons.rejected.connect(self.reject)
        layout.addWidget(dialog_buttons)

    def _paste_from_clipboard(self):
        """从剪贴板粘贴数据到表格（追加模式）"""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if not text.strip():
            QMessageBox.information(self, "提示", "剪贴板为空")
            return

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return

        # 记录粘贴前的行数
        start_row = self.table.rowCount()

        # 解析并填充表格（追加）
        for line in lines:
            cols = self._split_line(line)
            if not cols or not cols[0].strip():
                continue

            row = self.table.rowCount()
            self.table.insertRow(row)

            # 填充7列数据
            for col_idx in range(min(len(cols), 7)):
                self.table.setItem(row, col_idx, QTableWidgetItem(cols[col_idx].strip()))

        self.table.resizeColumnsToContents()
        added_count = self.table.rowCount() - start_row
        QMessageBox.information(self, "粘贴完成", f"已新增 {added_count} 行数据，当前共 {self.table.rowCount()} 行")

    def _split_line(self, line: str) -> list:
        """分割一行数据，支持多种分隔符"""
        if "\t" in line:
            return [p.strip() for p in line.split("\t")]
        elif "｜" in line:
            return [p.strip() for p in line.split("｜")]
        elif "|" in line:
            return [p.strip() for p in line.split("|")]
        elif "," in line:
            return [p.strip() for p in line.split(",")]
        else:
            # 按任意空白字符分割
            return [p.strip() for p in line.split() if p.strip()]

    def _select_file(self):
        """选择文件并读取内容到表格"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择IOC文件", "", "文本/CSV/TSV (*.txt *.csv *.tsv);;所有文件 (*)"
        )
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            # 模拟粘贴
            from PyQt6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            old_text = clipboard.text()
            clipboard.setText(content)
            self._paste_from_clipboard()
            clipboard.setText(old_text)
        except Exception as e:
            QMessageBox.warning(self, "读取失败", f"无法读取文件: {str(e)}")

    def _clear_table(self):
        """清空表格"""
        self.table.setRowCount(0)

    def _delete_selected_rows(self):
        """删除选中的行"""
        rows = sorted(set(item.row() for item in self.table.selectedItems()), reverse=True)
        for row in rows:
            self.table.removeRow(row)

    def get_content(self) -> str:
        """获取表格内容，转换为文本格式供解析"""
        lines = []
        for row in range(self.table.rowCount()):
            cols = []
            for col in range(7):
                item = self.table.item(row, col)
                cols.append(item.text() if item else "")
            # 只提取需要的5个字段：值、类型、名称、时间、备注
            # 对应列：0(值)、1(类型)、4(名称)、5(时间)、6(备注)
            line = f"{cols[0]}\t{cols[1]}\t\t\t{cols[4]}\t{cols[5]}\t{cols[6]}"
            lines.append(line)
        return "\n".join(lines)


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
        self.table.setHorizontalHeaderLabels(["ID", "规则名称", "字段", "匹配类型", "匹配值", "严重级别", "发现日期", "备注"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table)

        # 搜索框
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("搜索:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入关键字搜索规则(规则名称/字段/匹配值/备注)...")
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
            field_combo = DropdownButton()
            field_combo.addItems(field_options)
            field_combo.setCurrentText(first_match.get("field", "command_line"))
            field_combo.currentTextChanged.connect(lambda: self._on_combo_changed())
            self.table.setCellWidget(idx, 2, field_combo)
            
            # Type 列 (下拉框)
            type_combo = DropdownButton()
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
            severity_combo = DropdownButton()
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
        
        # 遍历所有行进行过滤
        for row in range(self.table.rowCount()):
            # 获取该行的所有文本内容
            row_texts = []
            
            # ID (列0)
            id_item = self.table.item(row, 0)
            if id_item:
                row_texts.append(id_item.text().lower())
            
            # Family (列1)
            family_item = self.table.item(row, 1)
            if family_item:
                row_texts.append(family_item.text().lower())
            
            # Field (列2) - 下拉框
            field_combo = self.table.cellWidget(row, 2)
            if field_combo:
                row_texts.append(field_combo.currentText().lower())
            
            # Type (列3) - 下拉框
            type_combo = self.table.cellWidget(row, 3)
            if type_combo:
                row_texts.append(type_combo.currentText().lower())
            
            # Value (列4)
            value_item = self.table.item(row, 4)
            if value_item:
                row_texts.append(value_item.text().lower())
            
            # Note (列7)
            note_item = self.table.item(row, 7)
            if note_item:
                row_texts.append(note_item.text().lower())
            
            # 检查是否匹配
            match = any(search_text in text for text in row_texts)
            self.table.setRowHidden(row, not match)

    def _clear_search(self):
        """清除搜索框"""
        self.search_input.clear()

    def _show_help(self):
        help_text = """规则管理帮助

【基本操作】
1. 新增规则：点击"新增"按钮，填写规则信息后保存
2. 编辑规则：双击表格单元格直接编辑
3. 删除规则：选中规则行后点击"删除"
4. 搜索规则：在搜索框输入关键字，支持规则名称/字段/匹配值/备注
5. 导入规则：支持导入JSON格式的规则文件
6. 导入IOC：支持CSV/TSV格式，自动识别IP/Hash等类型
7. 导出规则：将当前规则导出为JSON文件
8. 保存变更：点击"保存"将规则写入文件

【规则字段说明】
- 规则名称：规则所属家族或分类（如：银狐、PowerShell）
- 字段：要匹配的Autoruns字段（command_line/image_path/entry/description/publisher/company/location/category/launch_string/ip/hash/sha256/md5）
- 匹配类型：包含(contains)/正则(regex)/等于(equals)
- 匹配值：具体的匹配内容
- 严重级别：critical/high/medium/low

【JSON规则格式】
规则文件为JSON数组，每条规则结构如下：
{
    "id": "规则唯一ID",
    "family": "规则家族/分类",
    "match": [
        {
            "field": "command_line",
            "type": "contains",
            "value": "匹配值"
        }
    ],
    "severity": "high",
    "note": "备注说明"
}

【匹配类型说明】
- contains: 包含匹配，value无需转义
- equals: 精确匹配，value无需转义
- regex: 正则匹配，value中的反斜杠需双写，如匹配\\使用"\\\\"

【字段转义规则】
- JSON文件中每个 \\ 需要写成 \\\\
- 例如：匹配路径 C:\\jnetpub\\wwwroot，JSON中应写 "C:\\\\jnetpub\\\\wwwroot"
- 正则中的双引号 " 需写成 \\"

【可用字段】
command_line, image_path, entry, description, publisher, company, location, category, launch_string, ip, hash, sha256, md5"""
        QMessageBox.information(self, "帮助", help_text)

    def _test_all_rules(self):
        """测试所有规则的有效性"""
        invalid_rules = []
        for rule in self.rule_engine.rules:
            match_list = rule.get("match", [])
            if not match_list:
                invalid_rules.append(f"{rule.get('id', '未知')}: 无匹配条件")
                continue
            for match in match_list:
                if not match.get("value", "").strip():
                    invalid_rules.append(f"{rule.get('id', '未知')}: 匹配值为空")
                    break
        
        if invalid_rules:
            QMessageBox.warning(
                self, 
                "测试结果", 
                f"发现 {len(invalid_rules)} 条无效规则:\n" + "\n".join(invalid_rules[:10])
            )
        else:
            QMessageBox.information(self, "测试结果", f"所有 {len(self.rule_engine.rules)} 条规则均有效")

    def _import_rules(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "导入规则", "", "JSON 文件 (*.json)")
        if not file_path:
            return
        ok, msg = self.rule_engine.load_rules_from_file(file_path)
        if ok:
            self._load_rules()
            self._dirty = True
            QMessageBox.information(self, "成功", msg)
        else:
            QMessageBox.warning(self, "失败", msg)

    def _import_ioc(self):
        """打开IOC导入对话框，支持粘贴或文件选择"""
        dialog = IOCImportDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        
        content = dialog.get_content()
        if not content:
            QMessageBox.warning(self, "提示", "没有输入内容")
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
        QMessageBox.information(self, "导入完成", f"新增 {added} 条，跳过 {skipped} 条\n请点击'保存'以写入规则文件")

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

            field = field_combo.currentText() if field_combo else "command_line"
            match_type = self._normalize_match_type(type_combo.currentText() if type_combo else "contains")
            severity = severity_combo.currentText() if severity_combo else "medium"

            rule = {
                "id": id_item.text() if id_item else f"rule_{uuid.uuid4().hex[:8]}",
                "family": family_item.text() if family_item else "custom",
                "match": [
                    {
                        "field": field,
                        "type": match_type,
                        "value": value_item.text() if value_item else ""
                    }
                ],
                "severity": severity,
                "date": date_item.text() if date_item else "",
                "note": note_item.text() if note_item else ""
            }
            rules.append(rule)
        self.rule_engine.rules = rules

    def _display_match_type(self, value):
        mapping = {
            "contains": "包含",
            "regex": "正则",
            "equals": "等于",
            "包含": "包含",
            "正则": "正则",
            "等于": "等于",
        }
        return mapping.get((value or "").strip(), "包含")

    def _display_rule_value(self, value, match_type):
        """显示规则值"""
        return value if value else ""

    def _normalize_match_type(self, value):
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
        else:
            # 没有明显分隔符，尝试用多个空格分割（从Excel复制时制表符可能变空格）
            delimiter = None  # 使用split()自动处理多个空格

        def split_line(line):
            if delimiter is None:
                # 按任意空白字符分割，自动处理多个空格
                parts = [p.strip() for p in line.split() if p.strip()]
            else:
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
