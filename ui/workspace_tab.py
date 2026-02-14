from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QComboBox, QMessageBox,
    QLineEdit, QLabel, QTextEdit, QSplitter,
    QAbstractItemView, QFrame, QCheckBox, QMenu,
    QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QClipboard
import os
import json

from core.rule_engine import RuleEngine
from core.search_service import SearchService
from core.threat_intel import ThreatIntelService, WeibuProvider, VirusTotalProvider, IOCQuery, IOCType
from utils.path_resolver import PathResolver, PathScope
from utils.command_template import CommandTemplateManager
from utils.safe_executor import SafeExecutor
from utils.search_result import SearchResult, ResultType
from ui.ui_style import apply_flat_style
from ui.workspace_rule_dialogs import RuleManagerDialog
from ui.workspace_results_presenter import WorkspaceResultsPresenter
from ui.workspace_action_executor import WorkspaceActionExecutor


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
        self.action_executor = WorkspaceActionExecutor(self, self.command_manager, self.executor)
        self.threat_intel_service = ThreatIntelService()
        self._init_threat_intel()
        self.current_data = []
        self.matched_results = []
        self.last_threat_intel_results = []
        self.selected_entry = None
        self.selected_scope = PathScope.SELF
        self.result_mode = "autorun"
        self.results_presenter = None
        
        self._init_ui()

    def _init_threat_intel(self):
        """初始化威胁情报服务（当前优先微步）。"""
        api_key = os.getenv("IRTOOL_WEIBU_API_KEY", "").strip()
        vt_api_key = os.getenv("IRTOOL_VT_API_KEY", "").strip()
        if not api_key:
            try:
                config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
                if os.path.exists(config_path):
                    with open(config_path, "r", encoding="utf-8") as f:
                        config = json.load(f)
                    api_key = str(config.get("weibu_api_key", "")).strip()
                    vt_api_key = vt_api_key or str(config.get("virustotal_api_key", "")).strip()
            except Exception:
                api_key = ""
                vt_api_key = vt_api_key or ""
        self.threat_intel_service.register_provider(WeibuProvider(api_key=api_key))
        self.threat_intel_service.register_provider(VirusTotalProvider(api_key=vt_api_key))
    
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

        # self.btn_export_intel = QPushButton("导出情报")
        # self.btn_export_intel.clicked.connect(self._export_last_threat_intel_results)
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_box, 1)
        search_layout.addWidget(self.btn_search)
        search_layout.addWidget(self.btn_scan_rules)
        search_layout.addWidget(self.btn_manage_rules)
        # search_layout.addWidget(self.btn_export_intel)
        
        layout.addLayout(search_layout)

        # 规则类型筛选
        rule_layout = QHBoxLayout()
        rule_label = QLabel("规则类型:")
        self.chk_rule_command = QCheckBox("命令行")
        self.chk_rule_path = QCheckBox("路径")
        self.chk_rule_ip = QCheckBox("IP")
        self.chk_rule_hash = QCheckBox("Hash")
        self.chk_rule_other = QCheckBox("其他")

        # 默认只选中 IP
        self.chk_rule_command.setChecked(False)
        self.chk_rule_path.setChecked(False)
        self.chk_rule_ip.setChecked(True)
        self.chk_rule_hash.setChecked(False)
        self.chk_rule_other.setChecked(False)

        # 全选/取消按钮
        self.btn_select_all_rules = QPushButton("全选")
        self.btn_select_all_rules.setFixedWidth(50)
        self.btn_select_all_rules.clicked.connect(self._select_all_rule_types)
        self.btn_deselect_all_rules = QPushButton("全部取消")
        self.btn_deselect_all_rules.setFixedWidth(70)
        self.btn_deselect_all_rules.clicked.connect(self._deselect_all_rule_types)

        rule_layout.addWidget(rule_label)
        rule_layout.addWidget(self.chk_rule_command)
        rule_layout.addWidget(self.chk_rule_path)
        rule_layout.addWidget(self.chk_rule_ip)
        rule_layout.addWidget(self.chk_rule_hash)
        rule_layout.addWidget(self.chk_rule_other)
        rule_layout.addWidget(self.btn_select_all_rules)
        rule_layout.addWidget(self.btn_deselect_all_rules)
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
        self.results_presenter = WorkspaceResultsPresenter(self.results_table)
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
        self.action_executor.populate_presets(self.cmb_preset)

    def _set_result_mode(self, mode: str):
        """设置结果表格列

        注意: 移除了 "ip" 模式，IP 结果现在通过规则扫描呈现
        """
        self.result_mode = mode
        if self.results_presenter:
            self.results_presenter.set_mode(mode)
    
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

                    # 获取条目信息
                    entry_name = entry.get('entry', 'Unknown')
                    command_line = entry.get('command_line', '')

                    # Matched：显示命中的匹配值（从规则的match.value中提取）
                    matched_values = []
                    for rule in matched_rules:
                        for match in rule.get('match', []):
                            match_value = match.get('value', '')
                            if match_value:
                                matched_values.append(match_value)
                    matched_value = ', '.join(set(matched_values)) if matched_values else entry_name

                    # Summary：Entry | CommandLine
                    summary = f"{entry_name} | command line: {command_line}"

                    # Source：规则名称
                    source = matched_rules[0].get('family', 'rule_scan')

                    result = SearchResult(
                        result_type=ResultType.AUTORUN,
                        summary=summary,
                        source=source,
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

    def _select_all_rule_types(self):
        """全选所有规则类型"""
        self.chk_rule_command.setChecked(True)
        self.chk_rule_path.setChecked(True)
        self.chk_rule_ip.setChecked(True)
        self.chk_rule_hash.setChecked(True)
        self.chk_rule_other.setChecked(True)

    def _deselect_all_rule_types(self):
        """取消全选所有规则类型"""
        self.chk_rule_command.setChecked(False)
        self.chk_rule_path.setChecked(False)
        self.chk_rule_ip.setChecked(False)
        self.chk_rule_hash.setChecked(False)
        self.chk_rule_other.setChecked(False)

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
            if self.results_presenter:
                self.results_presenter.update_table(self.result_mode, self.matched_results)
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
            self.action_executor.update_command_preview(
                selected_entry=self.selected_entry,
                selected_scope=self.selected_scope,
                cmb_preset=self.cmb_preset,
                cmd_preview=self.cmd_preview,
                btn_execute=self.btn_execute,
            )
        except Exception as e:
            QMessageBox.warning(self, "错误", f"更新命令预览失败: {str(e)}")
    
    def _execute_command(self):
        """执行命令"""
        try:
            self.action_executor.execute_command(
                selected_entry=self.selected_entry or {},
                selected_scope=self.selected_scope,
                cmb_preset=self.cmb_preset,
                cmd_preview=self.cmd_preview,
            )
        except Exception as e:
            QMessageBox.warning(self, "错误", f"执行命令失败: {str(e)}")
    
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

            # iocs = self._extract_iocs_for_result(result, entry)
            # if iocs:
            #     menu.addSeparator()
            #     action_weibu_single = menu.addAction("微步查询（当前条目）")
            #     action_weibu_single.triggered.connect(
            #         lambda: self._query_weibu_single(result, entry)
            #     )

            # if self.matched_results:
            #     action_weibu_batch = menu.addAction("微步批量查询（当前结果）")
            #     action_weibu_batch.triggered.connect(self._query_weibu_batch_from_results)
            
            menu.exec(self.results_table.viewport().mapToGlobal(pos))
        except Exception as e:
            QMessageBox.warning(self, "错误", f"显示右键菜单失败: {str(e)}")

    def _extract_iocs_for_result(self, result, entry: dict):
        iocs = []
        seen = set()

        def add_ioc(value: str, ioc_type: IOCType):
            text = (value or "").strip()
            if not text:
                return
            key = (ioc_type.value, text.lower())
            if key in seen:
                return
            seen.add(key)
            iocs.append(IOCQuery(value=text, ioc_type=ioc_type, context={"source": result.source}))

        # 1) 优先提取 IP（规则扫描网络结果）
        detail = result.detail if result else {}
        matched_ip = ""
        if isinstance(detail, dict):
            matched_ip = str(detail.get("matched_ip", "") or "").strip()
            connection = detail.get("connection", {}) if isinstance(detail.get("connection", {}), dict) else {}
            remote_ip = str(connection.get("remote_address", "") or "").strip()
            local_ip = str(connection.get("local_address", "") or "").strip()
            if matched_ip and self._looks_like_ip(matched_ip):
                add_ioc(matched_ip, IOCType.IP)
            if remote_ip and self._looks_like_ip(remote_ip):
                add_ioc(remote_ip, IOCType.IP)
            if local_ip and self._looks_like_ip(local_ip):
                add_ioc(local_ip, IOCType.IP)

        # 2) 提取 Hash（sha256 > md5）
        hash_candidates = []
        sha256 = str(entry.get("sha256", "") or "").strip()
        md5 = str(entry.get("md5", "") or "").strip()
        if sha256:
            hash_candidates.append(sha256)
        if md5:
            hash_candidates.append(md5)
        detail_data = entry.get("detail_data")
        if isinstance(detail_data, dict):
            for key in ("hash", "sha256", "md5"):
                value = str(detail_data.get(key, "") or "").strip()
                if value:
                    hash_candidates.append(value)
        for hv in hash_candidates:
            if self._looks_like_hash(hv):
                add_ioc(hv.lower(), IOCType.HASH)

        return iocs

    @staticmethod
    def _looks_like_hash(value: str) -> bool:
        text = (value or "").strip().lower()
        if len(text) not in (32, 40, 64):
            return False
        return all(c in "0123456789abcdef" for c in text)

    def _query_weibu_single(self, result, entry: dict):
        iocs = self._extract_iocs_for_result(result, entry)
        if not iocs:
            QMessageBox.information(self, "提示", "当前条目未提取到可查询 IOC（IP/Hash）")
            return

        query = iocs[0]
        query_result = self.threat_intel_service.query_one(query, "weibu", timeout=8.0)
        self._show_weibu_result_dialog([query_result], title="微步查询结果（单条）")

    def _query_weibu_batch_from_results(self):
        iocs = []
        seen = set()
        for result in self.matched_results:
            entry = result.related_entry or (result.detail.get("entry", {}) if isinstance(result.detail, dict) else {})
            for item in self._extract_iocs_for_result(result, entry if isinstance(entry, dict) else {}):
                key = (item.ioc_type.value, item.value.lower())
                if key in seen:
                    continue
                seen.add(key)
                iocs.append(item)

        if not iocs:
            QMessageBox.information(self, "提示", "当前结果集中未提取到可查询 IOC（IP/Hash）")
            return

        # 先限制数量，避免 UI 无保护情况下误触发过大批量
        max_batch = 50
        query_items = iocs[:max_batch]
        results = self.threat_intel_service.query_batch(
            query_items,
            "weibu",
            timeout=8.0,
            max_workers=4,
            qps_limit=5.0,
        )
        self._show_weibu_result_dialog(results, title=f"微步查询结果（批量 {len(query_items)} 条）")

    def _show_weibu_result_dialog(self, results: list, title: str):
        if not results:
            QMessageBox.information(self, "提示", "无查询结果")
            return
        self.last_threat_intel_results = list(results)

        success_count = sum(1 for r in results if r.success)
        failed = [r for r in results if not r.success]

        lines = []
        for r in results[:10]:
            ioc_text = f"{r.query.ioc_type.value}:{r.query.value}"
            if r.success:
                lines.append(f"[OK] {ioc_text} -> {r.verdict} ({r.severity})")
            else:
                lines.append(f"[FAIL] {ioc_text} -> {r.error or 'unknown_error'}")

        if len(results) > 10:
            lines.append(f"... 其余 {len(results) - 10} 条省略")

        detail = "\n".join(lines)
        summary = (
            f"Provider: weibu\n"
            f"总数: {len(results)}\n"
            f"成功: {success_count}\n"
            f"失败: {len(failed)}\n\n"
            f"{detail}"
        )

        missing_key = any((r.error or "") == "missing_api_key" for r in failed)
        if missing_key:
            summary += (
                "\n\n当前未配置微步 API Key。\n"
                "可通过以下方式配置：\n"
                "1. 环境变量 `IRTOOL_WEIBU_API_KEY`\n"
                "2. `config.json` 中字段 `weibu_api_key`"
            )

        if failed:
            QMessageBox.warning(self, title, summary)
        else:
            QMessageBox.information(self, title, summary)

    def _export_last_threat_intel_results(self):
        if not self.last_threat_intel_results:
            QMessageBox.information(self, "提示", "暂无可导出的情报查询结果")
            return

        default_name = "threat_intel_results.json"
        save_path = PathResolver.save_file(
            self,
            "导出情报查询结果",
            default_name,
            "JSON 文件 (*.json)",
        )
        if not save_path:
            return

        payload = []
        for item in self.last_threat_intel_results:
            payload.append(
                {
                    "provider": item.provider,
                    "ioc_type": item.query.ioc_type.value,
                    "ioc_value": item.query.value,
                    "success": item.success,
                    "verdict": item.verdict,
                    "severity": item.severity,
                    "confidence": item.confidence,
                    "summary": item.summary,
                    "error": item.error,
                    "raw": item.raw,
                    "context": item.query.context,
                }
            )

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "导出成功", f"已导出 {len(payload)} 条结果：\n{save_path}")
        except Exception as exc:
            QMessageBox.warning(self, "导出失败", f"导出情报结果失败: {exc}")
    
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
