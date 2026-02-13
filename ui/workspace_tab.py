from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QComboBox, QMessageBox,
    QLineEdit, QLabel, QTextEdit, QSplitter,
    QFileDialog, QAbstractItemView, QFrame, QCheckBox, QMenu,
    QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication, QClipboard
import os

from core.rule_engine import RuleEngine
from core.search_service import SearchService
from utils.path_resolver import PathResolver, PathScope
from utils.command_template import CommandTemplateManager
from utils.safe_executor import SafeExecutor, CommandResult, CommandStatus
from utils.search_result import SearchResult, ResultType
from ui.ui_style import apply_flat_style
from ui.workspace_rule_dialogs import RuleManagerDialog


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
        self.search_box.setPlaceholderText("支持路径 / 命令行 / 条目名 / 描述等关键字搜索 (IP 请使用规则扫描)")
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

        # 添加说明标签
        note_label = QLabel("说明: IP 只能通过规则扫描发现，不支持搜索框直接搜索")
        note_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(note_label)

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
        """设置结果表格列

        注意: 移除了 "ip" 模式，IP 结果现在通过规则扫描呈现
        """
        self.result_mode = mode
        if mode == "autorun":
            headers = ["Category", "Entry", "Description", "Publisher", "Image Path"]
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
        """执行搜索 - 仅支持关键字搜索，IP 请使用规则扫描"""
        try:
            if not self.search_service:
                QMessageBox.warning(self, "警告", "搜索服务未初始化")
                return

            search_text = self.search_box.text().strip()
            if not search_text:
                QMessageBox.warning(self, "警告", "请输入搜索内容")
                return

            # 检查是否为 IP 地址（给出提示）
            if self._looks_like_ip(search_text):
                QMessageBox.information(
                    self,
                    "提示",
                    "搜索框不再支持直接搜索 IP 地址。\n\n"
                    "如需扫描 IP，请：\n"
                    "1. 点击'规则管理'添加 IP 规则\n"
                    "2. 点击'规则扫描'执行扫描\n\n"
                    "IP 只能通过规则扫描发现，作为'被规则命中的证据'呈现。"
                )
                return

            results_bundle = self.search_service.search(search_text)

            # 搜索只返回 keyword 模式
            if not self.search_service.has_autoruns_data():
                QMessageBox.warning(self, "警告", "暂无持久化数据，请先在持久化检测中扫描")
                return
            self._set_result_mode("autorun")

            self.matched_results = results_bundle.results
            self._update_results_table()
        except Exception as e:
            QMessageBox.warning(self, "错误", f"搜索失败: {str(e)}")

    def _looks_like_ip(self, value: str) -> bool:
        """检查值是否看起来像 IP 地址（排除文件路径）"""
        if not value:
            return False
        # 排除文件路径（包含盘符或反斜杠）
        if ":\\" in value or value.startswith("\\") or "/" in value:
            return False
        # IPv6 检查（包含 : 但不包含盘符）
        if ":" in value:
            # 排除 Windows 盘符格式（如 C: D:）
            if len(value) >= 2 and value[1] == ":" and value[0].isalpha():
                return False
            return True
        # IPv4 检查
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
                    
                    # 构建 matched_value：显示命中的字段和规则家族
                    matched_rules_text = ', '.join([r.get('family', r.get('id', '')) for r in matched_rules])
                    # 获取命中的字段信息
                    hit_fields = []
                    for rule in matched_rules:
                        for match in rule.get('match', []):
                            hit_fields.append(match.get('field', ''))
                    hit_fields_str = ','.join(set(hit_fields)) if hit_fields else ''
                    matched_value = f"{hit_fields_str}:{entry_name} | {matched_rules_text}"

                    result = SearchResult(
                        result_type=ResultType.AUTORUN,
                        summary=summary,
                        source='rule_scan',
                        detail={
                            'entry': entry,
                            'matched_rules': matched_rules,
                            'severity': max_severity
                        },
                        matched_value=matched_value,
                        related_entry=entry
                    )
                    self.matched_results.append(result)
            
            # 扫描网络连接数据（IP 规则）
            if "ip" in allowed_types:
                network_data = self.search_service.get_network_connections()
                print(f"[IP Rule Scan] 获取到 {len(network_data)} 条网络连接")
                for conn in network_data:
                    # 将网络连接转换为条目格式
                    # 注意：IP 规则匹配时会检查 command_line/launch_string/image_path 中的 IP
                    local_addr = conn.get('local_address', '')
                    remote_addr = conn.get('remote_address', '')
                    # 将 IP 地址放入 command_line 以便规则引擎能匹配到
                    ip_text = f"{local_addr} -> {remote_addr}"
                    entry = {
                        'location': 'Network',
                        'entry': f"PID:{conn.get('pid', '')}",
                        'category': 'Network',
                        'description': ip_text,
                        'publisher': '',
                        'company': '',
                        'image_path': conn.get('process_path', ''),
                        'launch_string': '',
                        'command_line': ip_text,  # 将 IP 放入 command_line 以便规则匹配
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
                        print(f"[IP Rule Scan] 命中: PID={conn.get('pid')}, {local_addr} -> {remote_addr}, rules={[r.get('id') for r in matched_rules]}")
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
                        
                        # 构建 matched_value：显示命中的 IP 和规则家族
                        matched_rules_text = ', '.join([r.get('family', r.get('id', '')) for r in matched_rules])
                        matched_value = f"IP:{remote_addr} | {matched_rules_text}"

                        result = SearchResult(
                            result_type=ResultType.IP_MATCH,
                            summary=summary,
                            source='rule_scan',
                            detail={
                                'entry': entry,
                                'matched_rules': matched_rules,
                                'severity': max_severity,
                                'kind': 'network',
                                'connection': conn,
                                'matched_ip': remote_addr  # 记录命中的 IP
                            },
                            matched_value=matched_value,
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
                            rule_note = rule.get('note', '')
                            if match_list:
                                match = match_list[0]
                                field = match.get('field', '')
                                match_type = match.get('type', '')
                                value = match.get('value', '')
                                # 简化显示
                                if len(value) > 30:
                                    value = value[:27] + "..."
                                detail_str = f"{field}({match_type})={value}"
                                if rule_note:
                                    detail_str += f" [{rule_note}]"
                                rule_details.append(detail_str)
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
