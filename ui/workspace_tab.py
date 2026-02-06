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

from core.rule_engine import RuleEngine
from core.search_service import SearchService
from utils.path_resolver import PathResolver, PathScope
from utils.command_template import CommandTemplateManager
from utils.safe_executor import SafeExecutor, CommandResult, CommandStatus
from utils.search_result import SearchResult, ResultType


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
        self.setWindowTitle("新增规则")
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
        self.cmb_type.addItems(["contains", "regex", "equals"])
        self.edt_value = QLineEdit()
        self.cmb_severity = QComboBox()
        self.cmb_severity.addItems(["critical", "high", "medium", "low"])
        self.edt_note = QLineEdit()

        form.addRow("规则ID", self.edt_id)
        form.addRow("家族", self.edt_family)
        form.addRow("字段", self.cmb_field)
        form.addRow("匹配类型", self.cmb_type)
        form.addRow("匹配值", self.edt_value)
        form.addRow("严重级别", self.cmb_severity)
        form.addRow("备注", self.edt_note)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

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
                    "type": self.cmb_type.currentText(),
                    "value": self.edt_value.text().strip()
                }
            ],
            "severity": self.cmb_severity.currentText(),
            "note": self.edt_note.text().strip()
        }


class RuleManagerDialog(QDialog):
    """规则管理对话框"""
    def __init__(self, rule_engine: RuleEngine, parent=None):
        super().__init__(parent)
        self.rule_engine = rule_engine
        self._rule_index_by_row = []
        self.setWindowTitle("规则管理")
        self.resize(900, 500)
        self._init_ui()
        self._load_rules()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["ID", "Family", "Field", "Type", "Value", "Severity", "Note"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("新增")
        self.btn_delete = QPushButton("删除")
        self.btn_import = QPushButton("导入")
        self.btn_import_ioc = QPushButton("导入IOC")
        self.btn_export = QPushButton("导出")
        self.btn_save = QPushButton("保存")
        self.btn_close = QPushButton("关闭")

        self.btn_add.clicked.connect(self._add_rule)
        self.btn_delete.clicked.connect(self._delete_rule)
        self.btn_import.clicked.connect(self._import_rules)
        self.btn_import_ioc.clicked.connect(self._import_ioc)
        self.btn_export.clicked.connect(self._export_rules)
        self.btn_save.clicked.connect(self._save_rules)
        self.btn_close.clicked.connect(self.close)

        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_import)
        btn_layout.addWidget(self.btn_import_ioc)
        btn_layout.addWidget(self.btn_export)
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

    def _load_rules(self):
        rules = self.rule_engine.rules or []
        self.table.setRowCount(0)
        self._rule_index_by_row = []
        for idx, rule in enumerate(rules):
            self.table.insertRow(idx)
            match_list = rule.get("match", [])
            first_match = match_list[0] if match_list else {}
            self.table.setItem(idx, 0, QTableWidgetItem(rule.get("id", "")))
            self.table.setItem(idx, 1, QTableWidgetItem(rule.get("family", "")))
            self.table.setItem(idx, 2, QTableWidgetItem(first_match.get("field", "")))
            self.table.setItem(idx, 3, QTableWidgetItem(first_match.get("type", "")))
            self.table.setItem(idx, 4, QTableWidgetItem(first_match.get("value", "")))
            self.table.setItem(idx, 5, QTableWidgetItem(rule.get("severity", "")))
            self.table.setItem(idx, 6, QTableWidgetItem(rule.get("note", "")))
            self._rule_index_by_row.append(idx)
        self.table.resizeColumnsToContents()

    def _add_rule(self):
        dialog = RuleEditDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.rule_engine.rules.append(dialog.get_rule())
        self._save_rules(show_msg=False)
        self._load_rules()

    def _delete_rule(self):
        rows = sorted(set(item.row() for item in self.table.selectedItems()), reverse=True)
        if not rows:
            QMessageBox.warning(self, "提示", "请选择要删除的规则")
            return
        for row in rows:
            if 0 <= row < len(self.rule_engine.rules):
                self.rule_engine.rules.pop(row)
        self._save_rules(show_msg=False)
        self._load_rules()

    def _import_rules(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "导入规则", "", "JSON 文件 (*.json)")
        if not file_path:
            return
        ok, msg = self.rule_engine.load_rules_from_file(file_path)
        if ok:
            self._save_rules(show_msg=False)
            self._load_rules()
            QMessageBox.information(self, "成功", msg)
        else:
            QMessageBox.warning(self, "失败", msg)

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

        self._save_rules(show_msg=False)
        self._load_rules()
        QMessageBox.information(self, "导入完成", f"新增 {added} 条，跳过 {skipped} 条")

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
        ok, msg = self.rule_engine.save_rules_to_file(str(self.rule_engine.rules_path))
        if show_msg:
            if ok:
                QMessageBox.information(self, "成功", msg)
            else:
                QMessageBox.warning(self, "失败", msg)

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
        if header and header[0].lower() in ("ioc", "indicator"):
            start_index = 1

        for line in lines[start_index:]:
            cols = split_line(line)
            if not cols:
                continue
            ioc = cols[0].strip()
            if not ioc:
                continue
            ioc_type = cols[1].strip() if len(cols) > 1 else ""
            platform = cols[2].strip() if len(cols) > 2 else ""
            action = cols[3].strip() if len(cols) > 3 else ""
            threat = cols[4].strip() if len(cols) > 4 else ""
            date = cols[5].strip() if len(cols) > 5 else ""
            note = cols[6].strip() if len(cols) > 6 else ""

            field, match_type = self._map_ioc_type(ioc_type)
            rule_note = self._compose_ioc_note(platform, action, threat, date, note)

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
                "note": rule_note
            }
            rules.append(rule)
        return rules

    def _map_ioc_type(self, ioc_type: str):
        text = (ioc_type or "").lower()
        if "ip" in text:
            return "ip", "equals"
        if "sha256" in text or "sha-256" in text:
            return "sha256", "equals"
        if "md5" in text:
            return "md5", "equals"
        if "hash" in text or "哈希" in text:
            return "hash", "equals"
        if "域名" in text or "domain" in text:
            return "command_line", "contains"
        return "command_line", "contains"

    def _compose_ioc_note(self, platform: str, action: str, threat: str, date: str, note: str):
        parts = []
        if platform:
            parts.append(f"平台:{platform}")
        if action:
            parts.append(f"处置:{action}")
        if threat:
            parts.append(f"威胁:{threat}")
        if date:
            parts.append(f"发现:{date}")
        if note:
            parts.append(f"备注:{note}")
        return "; ".join(parts)

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
            headers = ["Type", "Matched", "Source", "Summary"]
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

            # 获取 Autoruns 数据
            self.current_data = self.search_service.get_autoruns_entries()
            if not self.current_data:
                QMessageBox.warning(self, "警告", "暂无持久化数据，请先在持久化检测中扫描")
                return

            allowed_types = self._get_selected_rule_types()
            if not allowed_types:
                QMessageBox.warning(self, "提示", "请至少选择一种规则类型")
                return

            if "hash" in allowed_types and self._has_hash_rules(allowed_types) and self._hash_missing_all(self.current_data):
                QMessageBox.information(
                    self,
                    "提示",
                    "检测到 Hash 规则，但当前条目未计算 Hash。\n\n"
                    "建议在持久化检测中勾选“计算Hash”后重新扫描。"
                )
            
            # 扫描规则
            self.matched_results = []
            for entry in self.current_data:
                matched_rules = self.rule_engine.scan_entry(entry, allowed_types)
                if matched_rules:
                    # 获取最高严重级别
                    severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
                    max_severity = min(
                        matched_rules, 
                        key=lambda r: severity_order.get(r.get('severity', 'low'), 99)
                    ).get('severity', 'low')
                    
                    summary = f"Autorun 项 {entry.get('entry', 'Unknown')} 命中规则"
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

            self._set_result_mode("rule")
            self._update_results_table()
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
