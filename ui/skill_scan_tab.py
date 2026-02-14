import json
import os
import subprocess
from datetime import datetime
from typing import List, Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.skill_scan import SkillFileEntry, SkillScanConfig, SkillScanResult, SkillScanScanner
from core.threat_intel import IOCQuery, IOCType, ThreatIntelService, VirusTotalProvider, WeibuProvider
from ui.ui_style import apply_flat_style


class NumericTableWidgetItem(QTableWidgetItem):
    def __init__(self, text: str, sort_value: int = 0):
        super().__init__(text)
        self.sort_value = sort_value

    def __lt__(self, other):
        if isinstance(other, NumericTableWidgetItem):
            return self.sort_value < other.sort_value
        return self.text() < other.text()


class DateTimeTableWidgetItem(QTableWidgetItem):
    def __init__(self, text: str, sort_value: float = 0.0):
        super().__init__(text)
        self.sort_value = sort_value

    def __lt__(self, other):
        if isinstance(other, DateTimeTableWidgetItem):
            return self.sort_value < other.sort_value
        return self.text() < other.text()


class SkillScanWorker(QThread):
    finished_ok = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, config: SkillScanConfig):
        super().__init__()
        self.config = config

    def run(self):
        try:
            scanner = SkillScanScanner()
            result = scanner.scan(self.config)
            self.finished_ok.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class SkillScanTab(QWidget):
    COL_FILE_NAME = 0
    COL_FULL_PATH = 1
    COL_SIZE = 2
    COL_MTIME = 3
    COL_SHA256 = 4
    COL_SOURCE = 5
    COL_RULES = 6
    COL_STATUS = 7

    def __init__(self):
        super().__init__()
        apply_flat_style(self)

        self.scan_worker: Optional[SkillScanWorker] = None
        self.scan_result = SkillScanResult(entries=[], scan_time=datetime.now(), total_files=0)
        self.entries_by_path = {}
        self.last_threat_intel_results = []

        self.threat_intel_service = ThreatIntelService()
        self._init_threat_intel()
        self._init_ui()

    def _init_threat_intel(self):
        api_key = os.getenv("SECTOOL_WEIBU_API_KEY", "").strip()
        vt_api_key = os.getenv("SECTOOL_VT_API_KEY", "").strip()

        if not api_key or not vt_api_key:
            try:
                config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
                if os.path.exists(config_path):
                    with open(config_path, "r", encoding="utf-8") as f:
                        config = json.load(f)
                    if not api_key:
                        api_key = str(config.get("weibu_api_key", "")).strip()
                    if not vt_api_key:
                        vt_api_key = str(config.get("virustotal_api_key", "")).strip()
            except Exception:
                pass

        self.threat_intel_service.register_provider(WeibuProvider(api_key=api_key))
        self.threat_intel_service.register_provider(VirusTotalProvider(api_key=vt_api_key))

    def _init_ui(self):
        root_layout = QVBoxLayout(self)

        config_panel = self._build_config_panel()
        result_panel = self._build_result_panel()
        action_panel = self._build_action_panel()

        root_layout.addWidget(config_panel)
        root_layout.addWidget(result_panel, 1)
        root_layout.addWidget(action_panel)

    def _build_config_panel(self):
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)

        title = QLabel("扫描配置")
        layout.addWidget(title)
        layout.addWidget(QLabel("说明：该功能用于可疑文件发现，不做自动判恶，结果需人工确认。"))

        checkbox_layout = QHBoxLayout()
        self.chk_claude_home = QCheckBox("Claude (%USERPROFILE%\\.claude)")
        self.chk_openclaw_home = QCheckBox("OpenClaw (%USERPROFILE%\\.openclaw)")
        self.chk_codex_home = QCheckBox("Codex (%USERPROFILE%\\.codex)")
        self.chk_claude_config = QCheckBox("Claude Config (%USERPROFILE%\\.config\\claude)")
        self.chk_openclaw_config = QCheckBox("OpenClaw Config (%USERPROFILE%\\.config\\openclaw)")

        self.chk_claude_home.setChecked(True)
        self.chk_openclaw_home.setChecked(True)
        self.chk_codex_home.setChecked(True)
        self.chk_claude_config.setChecked(False)
        self.chk_openclaw_config.setChecked(False)

        checkbox_layout.addWidget(self.chk_claude_home)
        checkbox_layout.addWidget(self.chk_openclaw_home)
        checkbox_layout.addWidget(self.chk_codex_home)
        checkbox_layout.addWidget(self.chk_claude_config)
        checkbox_layout.addWidget(self.chk_openclaw_config)
        checkbox_layout.addStretch()
        layout.addLayout(checkbox_layout)

        advanced_toggle_layout = QHBoxLayout()
        self.btn_advanced = QPushButton("高级选项 ▸")
        self.btn_advanced.setCheckable(True)
        self.btn_advanced.toggled.connect(self._toggle_advanced_panel)
        advanced_toggle_layout.addWidget(self.btn_advanced)
        advanced_toggle_layout.addStretch()
        layout.addLayout(advanced_toggle_layout)

        self.advanced_panel = QFrame()
        self.advanced_panel.setVisible(False)
        adv_layout = QVBoxLayout(self.advanced_panel)

        lbl_custom = QLabel("自定义扫描路径（每行一个）")
        self.edit_custom_paths = QPlainTextEdit()
        self.edit_custom_paths.setPlaceholderText("例如:\nC:\\Users\\Alice\\Desktop\nD:\\Suspicious")
        self.edit_custom_paths.setMaximumHeight(90)

        filter_layout = QHBoxLayout()
        self.edit_exact_names = QLineEdit()
        self.edit_exact_names.setPlaceholderText("精确文件名（逗号分隔，如 chrome.exe,svchost.exe）")
        self.edit_wildcards = QLineEdit()
        self.edit_wildcards.setPlaceholderText("通配符（逗号分隔，如 *.tmp,svchost*.exe）")
        filter_layout.addWidget(self.edit_exact_names, 1)
        filter_layout.addWidget(self.edit_wildcards, 1)

        self.chk_recursive = QCheckBox("递归子目录")
        self.chk_recursive.setChecked(True)
        lbl_known_list = QLabel("已知 Skill 文件名清单（逗号分隔，可留空使用默认）")
        self.edit_known_skill_files = QLineEdit()
        self.edit_known_skill_files.setPlaceholderText("例如: SKILL.md,manifest.json,mcpservers.json")
        lbl_malicious_hashes = QLabel("恶意 Hash 清单（每行一个 SHA256，可选）")
        self.edit_malicious_hashes = QPlainTextEdit()
        self.edit_malicious_hashes.setPlaceholderText("例如:\\n0123...abcd")
        self.edit_malicious_hashes.setMaximumHeight(72)

        adv_layout.addWidget(lbl_custom)
        adv_layout.addWidget(self.edit_custom_paths)
        adv_layout.addLayout(filter_layout)
        adv_layout.addWidget(self.chk_recursive)
        adv_layout.addWidget(lbl_known_list)
        adv_layout.addWidget(self.edit_known_skill_files)
        adv_layout.addWidget(lbl_malicious_hashes)
        adv_layout.addWidget(self.edit_malicious_hashes)

        layout.addWidget(self.advanced_panel)

        actions_layout = QHBoxLayout()
        self.btn_start_scan = QPushButton("Start Scan")
        self.btn_start_scan.clicked.connect(self._start_scan)
        self.lbl_scan_status = QLabel("就绪")

        actions_layout.addWidget(self.btn_start_scan)
        actions_layout.addWidget(self.lbl_scan_status)
        actions_layout.addStretch()
        layout.addLayout(actions_layout)

        return panel

    def _build_result_panel(self):
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)

        title = QLabel("扫描结果")
        layout.addWidget(title)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(8)
        self.results_table.setHorizontalHeaderLabels(
            [
                "文件名",
                "完整路径",
                "文件大小",
                "修改时间",
                "SHA256",
                "来源路径类型",
                "命中规则",
                "状态",
            ]
        )
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.setSortingEnabled(True)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setColumnWidth(self.COL_FILE_NAME, 220)
        self.results_table.setColumnWidth(self.COL_FULL_PATH, 460)
        self.results_table.setColumnWidth(self.COL_SIZE, 100)
        self.results_table.setColumnWidth(self.COL_MTIME, 160)
        self.results_table.setColumnWidth(self.COL_SHA256, 380)
        self.results_table.setColumnWidth(self.COL_SOURCE, 120)
        self.results_table.setColumnWidth(self.COL_RULES, 300)
        self.results_table.setColumnWidth(self.COL_STATUS, 110)
        self.results_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.results_table.customContextMenuRequested.connect(self._show_context_menu)
        self.results_table.itemSelectionChanged.connect(self._on_selection_changed)

        layout.addWidget(self.results_table)
        return panel

    def _build_action_panel(self):
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)

        tip = QLabel("查询仅提交 hash，不上传文件；默认不自动触发，请手动点击。")
        layout.addWidget(tip)

        actions = QHBoxLayout()
        self.btn_query_vt = QPushButton("查询 VirusTotal")
        self.btn_query_weibu = QPushButton("查询 微步")
        self.btn_rule_help = QPushButton("?")
        self.btn_rule_help.setFixedWidth(28)
        self.btn_rule_help.clicked.connect(self._show_rule_help_dialog)
        self.btn_query_vt.setEnabled(False)
        self.btn_query_weibu.setEnabled(False)

        self.btn_query_vt.clicked.connect(lambda: self._query_selected_hashes("virustotal"))
        self.btn_query_weibu.clicked.connect(lambda: self._query_selected_hashes("weibu"))

        actions.addWidget(self.btn_query_vt)
        actions.addWidget(self.btn_query_weibu)
        actions.addStretch()
        actions.addWidget(self.btn_rule_help)

        layout.addLayout(actions)
        return panel

    def _toggle_advanced_panel(self, checked: bool):
        self.advanced_panel.setVisible(checked)
        self.btn_advanced.setText("高级选项 ▾" if checked else "高级选项 ▸")

    def _start_scan(self):
        if self.scan_worker and self.scan_worker.isRunning():
            QMessageBox.information(self, "提示", "扫描正在进行中，请稍候。")
            return

        config = self._build_scan_config()
        if not config.builtin_paths and not config.custom_paths:
            QMessageBox.warning(self, "警告", "请至少选择一个扫描路径。")
            return

        self.btn_start_scan.setEnabled(False)
        self.lbl_scan_status.setText("扫描中...")

        self.scan_worker = SkillScanWorker(config)
        self.scan_worker.finished_ok.connect(self._on_scan_finished)
        self.scan_worker.failed.connect(self._on_scan_failed)
        self.scan_worker.finished.connect(self._on_scan_worker_finished)
        self.scan_worker.start()

    def _build_scan_config(self) -> SkillScanConfig:
        builtin_paths: List[str] = []
        if self.chk_claude_home.isChecked():
            builtin_paths.append("claude_home")
        if self.chk_openclaw_home.isChecked():
            builtin_paths.append("openclaw_home")
        if self.chk_codex_home.isChecked():
            builtin_paths.append("codex_home")
        if self.chk_claude_config.isChecked():
            builtin_paths.append("claude_config")
        if self.chk_openclaw_config.isChecked():
            builtin_paths.append("openclaw_config")

        custom_paths = []
        for line in self.edit_custom_paths.toPlainText().splitlines():
            path = line.strip()
            if path:
                custom_paths.append(path)

        filters: List[str] = []
        filters.extend(self._split_csv_like_text(self.edit_exact_names.text()))
        filters.extend(self._split_csv_like_text(self.edit_wildcards.text()))
        known_skill_files = self._split_csv_like_text(self.edit_known_skill_files.text())
        malicious_hashes = self._split_lines(self.edit_malicious_hashes.toPlainText())

        return SkillScanConfig(
            builtin_paths=builtin_paths,
            custom_paths=custom_paths,
            filename_filters=filters,
            known_skill_files=known_skill_files,
            malicious_hashes=malicious_hashes,
            recursive=self.chk_recursive.isChecked(),
        )

    @staticmethod
    def _split_csv_like_text(raw_text: str) -> List[str]:
        values: List[str] = []
        for chunk in (raw_text or "").replace(";", ",").split(","):
            text = chunk.strip()
            if text:
                values.append(text)
        return values

    @staticmethod
    def _split_lines(raw_text: str) -> List[str]:
        values: List[str] = []
        for line in (raw_text or "").splitlines():
            text = line.strip()
            if text:
                values.append(text)
        return values

    def _on_scan_finished(self, result: SkillScanResult):
        self.scan_result = result
        self.entries_by_path = {entry.full_path: entry for entry in result.entries}
        self._render_result_table(result.entries)
        summary = (
            f"完成: 输出 {result.total_files} / 扫描 {result.scanned_files} / 可疑 {result.suspicious_files} "
            f"({result.scan_time.strftime('%Y-%m-%d %H:%M:%S')})"
        )
        if result.errors:
            summary += f" | 错误 {len(result.errors)}"
        self.lbl_scan_status.setText(summary)

    def _on_scan_failed(self, error_text: str):
        self.lbl_scan_status.setText("扫描失败")
        QMessageBox.warning(self, "错误", f"Skill Scan 失败: {error_text}")

    def _on_scan_worker_finished(self):
        self.btn_start_scan.setEnabled(True)

    def _render_result_table(self, entries: List[SkillFileEntry]):
        self.results_table.setSortingEnabled(False)
        self.results_table.setUpdatesEnabled(False)
        self.results_table.clearContents()
        self.results_table.setRowCount(len(entries))

        for row, entry in enumerate(entries):
            file_name_item = QTableWidgetItem(entry.file_name)
            file_name_item.setData(Qt.ItemDataRole.UserRole, entry.full_path)
            self.results_table.setItem(row, self.COL_FILE_NAME, file_name_item)

            self.results_table.setItem(row, self.COL_FULL_PATH, QTableWidgetItem(entry.full_path))

            size_text = self._format_size(entry.size)
            size_item = NumericTableWidgetItem(size_text, entry.size)
            self.results_table.setItem(row, self.COL_SIZE, size_item)

            mtime_text = entry.mtime.strftime("%Y-%m-%d %H:%M:%S")
            mtime_item = DateTimeTableWidgetItem(mtime_text, entry.mtime.timestamp())
            self.results_table.setItem(row, self.COL_MTIME, mtime_item)

            self.results_table.setItem(row, self.COL_SHA256, QTableWidgetItem(entry.sha256))
            self.results_table.setItem(row, self.COL_SOURCE, QTableWidgetItem(entry.path_category))
            rules_text = self._format_rule_hits(entry.matched_rules)
            rules_item = QTableWidgetItem(rules_text)
            if entry.matched_rules:
                rules_item.setToolTip("\n".join(entry.matched_rules))
            self.results_table.setItem(row, self.COL_RULES, rules_item)

            status_text = self._status_text(entry)
            self.results_table.setItem(row, self.COL_STATUS, QTableWidgetItem(status_text))
            self._style_row(row, entry)

        self.results_table.setUpdatesEnabled(True)
        self.results_table.setSortingEnabled(True)
        self._on_selection_changed()

    @staticmethod
    def _status_text(entry: SkillFileEntry) -> str:
        if "confirmed_safe" in entry.tags:
            return "已确认安全"
        if entry.is_malicious_hash:
            return "命中恶意Hash"
        if entry.risk_flags:
            return "可疑"
        if entry.is_known_skill_file:
            return "已知Skill文件"
        return "待分析"

    def _style_row(self, row: int, entry: SkillFileEntry):
        if entry.is_malicious_hash:
            bg = QColor(255, 226, 226)
        elif entry.risk_flags:
            bg = QColor(255, 245, 215)
        elif "confirmed_safe" in entry.tags:
            bg = QColor(227, 244, 227)
        else:
            return
        for col in range(self.results_table.columnCount()):
            item = self.results_table.item(row, col)
            if item:
                item.setBackground(bg)

    @staticmethod
    def _format_rule_hits(matched_rules: List[str]) -> str:
        if not matched_rules:
            return "-"
        if len(matched_rules) <= 2:
            return " | ".join(matched_rules)
        return " | ".join(matched_rules[:2]) + f" | +{len(matched_rules) - 2}"

    def _show_rule_help_dialog(self):
        text = (
            "Skill Scan 判定标准（启发式，不等同于最终恶意结论）:\n\n"
            "1. R_HASH_BLOCKLIST: 文件 SHA256 命中恶意 Hash 清单\n"
            "2. R_EXT_HIGH_RISK: 文件扩展名属于高风险类型（如 .exe/.dll/.ps1 等）\n"
            "3. R_NAME_KEYWORD: 文件名包含常见恶意关键词（loader/dropper/payload 等）\n"
            "4. R_UNKNOWN_IN_SKILL: Skill 工具链路径中出现未归类的未知文件\n\n"
            "说明:\n"
            "- 命中规则用于快速筛查与排序，最终仍需人工复核。\n"
            "- ‘已确认安全’仅为本地标记，不会修改文件本身。"
        )
        QMessageBox.information(self, "规则说明", text)

    @staticmethod
    def _format_size(size: int) -> str:
        value = float(size)
        units = ["B", "KB", "MB", "GB", "TB"]
        for unit in units:
            if value < 1024.0 or unit == units[-1]:
                if unit == "B":
                    return f"{int(value)} {unit}"
                return f"{value:.2f} {unit}"
            value /= 1024.0
        return f"{size} B"

    def _show_context_menu(self, pos):
        index = self.results_table.indexAt(pos)
        if not index.isValid():
            return
        row = index.row()
        self.results_table.selectRow(row)
        entry = self._entry_from_row(row)
        if not entry:
            return

        menu = QMenu(self)
        action_copy_sha256 = menu.addAction("复制 SHA256")
        action_open_folder = menu.addAction("打开文件所在目录")
        action_mark_safe = menu.addAction("标记为已确认安全")

        action_copy_sha256.triggered.connect(lambda: self._copy_to_clipboard(entry.sha256))
        action_open_folder.triggered.connect(lambda: self._open_folder(entry.full_path))
        action_mark_safe.triggered.connect(lambda: self._mark_selected_safe())

        menu.exec(self.results_table.viewport().mapToGlobal(pos))

    def _mark_selected_safe(self):
        entries = self._selected_entries()
        if not entries:
            return
        for entry in entries:
            if "confirmed_safe" not in entry.tags:
                entry.tags.append("confirmed_safe")
        self._render_result_table(self.scan_result.entries)

    def _on_selection_changed(self):
        has_selection = bool(self._selected_entries())
        self.btn_query_vt.setEnabled(has_selection)
        self.btn_query_weibu.setEnabled(has_selection)

    def _selected_entries(self) -> List[SkillFileEntry]:
        selection_model = self.results_table.selectionModel()
        if not selection_model:
            return []
        rows = sorted({index.row() for index in selection_model.selectedRows(self.COL_FILE_NAME)})
        entries = []
        for row in rows:
            entry = self._entry_from_row(row)
            if entry:
                entries.append(entry)
        return entries

    def _entry_from_row(self, row: int) -> Optional[SkillFileEntry]:
        if row < 0:
            return None
        file_name_item = self.results_table.item(row, self.COL_FILE_NAME)
        if not file_name_item:
            return None
        full_path = file_name_item.data(Qt.ItemDataRole.UserRole)
        if not full_path:
            return None
        return self.entries_by_path.get(full_path)

    def _query_selected_hashes(self, provider_name: str):
        entries = self._selected_entries()
        if not entries:
            QMessageBox.information(self, "提示", "请先选择至少一条记录。")
            return

        hashes = []
        seen = set()
        for entry in entries:
            hv = (entry.sha256 or "").strip().lower()
            if not hv:
                continue
            if hv in seen:
                continue
            seen.add(hv)
            hashes.append(
                IOCQuery(
                    value=hv,
                    ioc_type=IOCType.HASH,
                    context={
                        "source": "skill_scan",
                        "path": entry.full_path,
                    },
                )
            )

        if not hashes:
            QMessageBox.information(self, "提示", "选中项中没有可查询的 SHA256。")
            return

        results = self.threat_intel_service.query_batch(
            hashes,
            provider_name,
            timeout=8.0,
            max_workers=4,
            qps_limit=5.0,
        )
        self._show_threat_intel_result_dialog(provider_name, results)

    def _show_threat_intel_result_dialog(self, provider_name: str, results: list):
        if not results:
            QMessageBox.information(self, "提示", "无查询结果")
            return

        self.last_threat_intel_results = list(results)
        success_count = sum(1 for item in results if item.success)
        fail_count = len(results) - success_count

        lines = []
        for item in results[:12]:
            text = f"{item.query.value[:16]}..."
            if item.success:
                lines.append(f"[OK] {text} -> {item.verdict} ({item.severity})")
            else:
                lines.append(f"[FAIL] {text} -> {item.error or 'unknown_error'}")
        if len(results) > 12:
            lines.append(f"... 其余 {len(results) - 12} 条省略")

        summary = (
            f"Provider: {provider_name}\n"
            f"总数: {len(results)}\n"
            f"成功: {success_count}\n"
            f"失败: {fail_count}\n\n"
            + "\n".join(lines)
        )

        if any((item.error or "") == "missing_api_key" for item in results):
            summary += (
                "\n\n未配置 API Key：\n"
                "- 微步: SECTOOL_WEIBU_API_KEY 或 config.json.weibu_api_key\n"
                "- VT: SECTOOL_VT_API_KEY 或 config.json.virustotal_api_key"
            )

        if fail_count > 0:
            QMessageBox.warning(self, f"{provider_name} 查询结果", summary)
        else:
            QMessageBox.information(self, f"{provider_name} 查询结果", summary)

    def _open_folder(self, file_path: str):
        if not file_path:
            return
        folder = os.path.dirname(file_path)
        if not folder or not os.path.exists(folder):
            QMessageBox.warning(self, "警告", f"目录不存在: {folder}")
            return
        try:
            subprocess.run(["explorer", folder], check=False)
        except Exception as exc:
            QMessageBox.warning(self, "错误", f"打开目录失败: {exc}")

    @staticmethod
    def _copy_to_clipboard(text: str):
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(text or "")
