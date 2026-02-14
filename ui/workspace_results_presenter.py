from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem
from PyQt6.QtGui import QColor

from utils.search_result import ResultType


class WorkspaceResultsPresenter:
    """工作台结果表格渲染器：负责表头模式和结果行填充。"""

    def __init__(self, table: QTableWidget):
        self.table = table

    def set_mode(self, mode: str) -> None:
        """设置结果表格列模式。"""
        if mode == "autorun":
            headers = ["Category", "Entry", "Description", "Publisher", "Image Path"]
        else:
            headers = ["Type", "Matched", "Source", "Summary", "规则详情"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setStretchLastSection(True)

    def update_table(self, mode: str, matched_results: list) -> None:
        """刷新结果表格。"""
        sorting_enabled = self.table.isSortingEnabled()
        if sorting_enabled:
            self.table.setSortingEnabled(False)

        self.table.setRowCount(0)
        if mode == "autorun":
            self._render_autorun_rows(matched_results)
        else:
            self._render_rule_rows(matched_results)

        self.table.resizeColumnsToContents()
        if sorting_enabled:
            self.table.setSortingEnabled(True)

    def _render_autorun_rows(self, matched_results: list) -> None:
        for idx, result in enumerate(matched_results):
            entry = result.related_entry or result.detail.get("entry", {})
            self.table.insertRow(idx)
            self.table.setItem(idx, 0, QTableWidgetItem(entry.get("category", "")))
            self.table.setItem(idx, 1, QTableWidgetItem(entry.get("entry", "")))
            self.table.setItem(idx, 2, QTableWidgetItem(entry.get("description", "")))
            self.table.setItem(idx, 3, QTableWidgetItem(entry.get("publisher", "")))
            self.table.setItem(idx, 4, QTableWidgetItem(entry.get("image_path", "")))

    def _render_rule_rows(self, matched_results: list) -> None:
        for idx, result in enumerate(matched_results):
            self.table.insertRow(idx)

            type_text = "IP" if result.result_type == ResultType.IP_MATCH else "Autorun"
            type_item = QTableWidgetItem(type_text)
            if result.result_type == ResultType.IP_MATCH:
                type_item.setBackground(QColor(200, 220, 255))
            self.table.setItem(idx, 0, type_item)

            # IP匹配时只显示IP地址
            if result.result_type == ResultType.IP_MATCH:
                display_matched = result.detail.get('matched_ip', result.matched_value)
            else:
                display_matched = result.matched_value
            self.table.setItem(idx, 1, QTableWidgetItem(display_matched))

            # Source显示规则名称(family)
            source_text = self._normalize_source(result.source)
            if result.source == "rule_scan" and result.detail.get("matched_rules"):
                # 获取第一个匹配规则的family作为source显示
                first_rule = result.detail["matched_rules"][0]
                source_text = first_rule.get("family", first_rule.get("id", "Rule Scan"))
            self.table.setItem(idx, 2, QTableWidgetItem(source_text))

            summary_item = QTableWidgetItem(result.summary)
            if result.source == "rule_scan" and result.detail.get("severity"):
                severity = result.detail.get("severity")
                if severity == "high":
                    summary_item.setBackground(QColor(255, 200, 200))
                elif severity == "medium":
                    summary_item.setBackground(QColor(255, 255, 200))
            self.table.setItem(idx, 3, summary_item)

            self.table.setItem(idx, 4, QTableWidgetItem(self._build_rule_details(result)))

    def _normalize_source(self, source: str) -> str:
        if source == "command_line":
            return "Command Line"
        if source == "image_path":
            return "Image Path"
        if source == "rule_scan":
            return "Rule Scan"
        return source

    def _build_rule_details(self, result) -> str:
        rule_details = []
        if result.source == "rule_scan" and result.detail.get("matched_rules"):
            for rule in result.detail["matched_rules"]:
                match_list = rule.get("match", [])
                rule_note = rule.get("note", "")
                if not match_list:
                    continue
                match = match_list[0]
                field = match.get("field", "")
                match_type = match.get("type", "")
                value = match.get("value", "")
                if len(value) > 30:
                    value = value[:27] + "..."
                detail_str = f"{field}({match_type})={value}"
                if rule_note:
                    detail_str += f" [Note: {rule_note}]"
                rule_details.append(detail_str)
        return "; ".join(rule_details) if rule_details else ""
