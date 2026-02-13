import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QLabel, QGridLayout, QSplitter


class AutorunsDetailRenderer:
    """Detail Pane 渲染器：负责控件初始化与增量更新。"""

    def __init__(self, splitter: QSplitter, detail_layout: QGridLayout, placeholder_style: str):
        self.splitter = splitter
        self.detail_layout = detail_layout
        self.placeholder_style = placeholder_style
        self.current_entry_id = None
        self.detail_labels = {}

    def _clear_layout(self):
        while self.detail_layout.count():
            item = self.detail_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.detail_labels.clear()

    def clear(self):
        self._clear_layout()

    def show_placeholder(self):
        self._clear_layout()
        detail_placeholder = QLabel("Select an entry to view details")
        detail_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail_placeholder.setStyleSheet(self.placeholder_style)
        self.detail_layout.addWidget(detail_placeholder, 0, 0, 1, 2)
        self.current_entry_id = None

    def _ensure_widgets(self):
        if self.detail_labels:
            return

        self._clear_layout()

        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setFamily("Segoe UI, Arial, sans-serif")

        value_font = QFont()
        value_font.setPointSize(9)
        value_font.setFamily("Segoe UI, Arial, sans-serif")

        mono_font = QFont(value_font)
        mono_font.setFamily("Consolas, Menlo, Monaco, Courier New, monospace")

        def add_title(text, row, col, col_span=1):
            label = QLabel(text)
            label.setStyleSheet("font-weight: bold; color: #000;")
            label.setFont(title_font)
            self.detail_layout.addWidget(label, row, col, 1, col_span)

        def add_value(key, row, col, col_span=1, selectable=True, mono=False):
            label = QLabel("")
            label.setFont(mono_font if mono else value_font)
            label.setWordWrap(True)
            if selectable:
                label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.detail_layout.addWidget(label, row, col, 1, col_span)
            self.detail_labels[key] = label

        row = 0
        add_title("Entry", row, 0)
        add_value("entry", row + 1, 0)
        add_title("Size", row, 1)
        add_value("size", row + 1, 1)

        row += 2
        add_title("Description", row, 0)
        add_value("description", row + 1, 0)
        add_title("Timestamp", row, 1)
        add_value("timestamp", row + 1, 1)

        row += 2
        add_title("Publisher", row, 0)
        add_value("publisher", row + 1, 0)
        add_title("Signature", row, 1)
        add_value("signature", row + 1, 1)

        row += 2
        add_title("Version", row, 0)
        add_value("version", row + 1, 0)
        add_title("Hash (SHA256)", row, 1)
        add_value("hash", row + 1, 1, mono=True)

        row += 2
        add_title("Image Path", row, 0, 2)
        add_value("image_path", row + 1, 0, 2, mono=True)

        row += 2
        add_title("Command Line", row, 0, 2)
        add_value("command_line", row + 1, 0, 2, mono=True)

        self.detail_layout.setRowStretch(row + 2, 1)

    @staticmethod
    def _set_text_if_changed(label: QLabel, text: str):
        if label.text() != text:
            label.setText(text)

    @staticmethod
    def _set_style_if_changed(label: QLabel, style: str):
        cached = label.property("_style_cache")
        if cached != style:
            label.setStyleSheet(style)
            label.setProperty("_style_cache", style)

    @staticmethod
    def _set_tooltip_if_changed(label: QLabel, tooltip: str):
        if label.toolTip() != tooltip:
            label.setToolTip(tooltip)

    def render_detail(self, data: dict, format_file_size):
        self._ensure_widgets()
        self.splitter.setSizes([700, 300])

        detail_data = data.get("detail_data", {})
        entry_id = data.get("id")

        signer_status = data.get("signer_status", "")
        signature_display = "Unsigned"
        signature_style = "color: #d32f2f; font-weight: bold;"
        if "(Verified)" in signer_status:
            signature_display = "Verified"
            signature_style = "color: #2e7d32; font-weight: bold;"
        elif "(Error)" in signer_status:
            signature_display = f"Error: {data.get('signature_detail', 'Unknown error')}"
            signature_style = "color: #f57c00; font-weight: bold;"

        image_path = detail_data.get("image_path", "")
        file_not_found = False
        if image_path and image_path.lower() != "file not found":
            file_not_found = not os.path.exists(image_path)
        image_path_display = f"{image_path} (File not found)" if file_not_found else image_path

        hash_value = detail_data.get("hash", "")
        hash_display = hash_value if hash_value else "Not calculated"

        command_line = str(detail_data.get("command_line", "") or "")

        self._set_text_if_changed(self.detail_labels["entry"], str(data.get("entry", "") or ""))
        self._set_text_if_changed(self.detail_labels["size"], format_file_size(detail_data.get("size", "")))
        self._set_text_if_changed(self.detail_labels["description"], str(data.get("description", "") or ""))
        self._set_text_if_changed(self.detail_labels["timestamp"], str(detail_data.get("timestamp", "") or ""))
        self._set_text_if_changed(self.detail_labels["publisher"], str(detail_data.get("publisher", "") or ""))
        self._set_text_if_changed(self.detail_labels["signature"], signature_display)
        self._set_style_if_changed(self.detail_labels["signature"], signature_style)
        self._set_text_if_changed(self.detail_labels["version"], str(detail_data.get("version", "") or ""))
        self._set_text_if_changed(self.detail_labels["hash"], hash_display)
        self._set_text_if_changed(self.detail_labels["image_path"], str(image_path_display or ""))
        self._set_style_if_changed(
            self.detail_labels["image_path"],
            "background-color: #ffe0e0; padding: 5px; border-radius: 3px;"
            if file_not_found
            else "background-color: #f0f0f0; padding: 5px; border-radius: 3px;",
        )
        self._set_text_if_changed(self.detail_labels["command_line"], command_line)
        self._set_style_if_changed(
            self.detail_labels["command_line"],
            "background-color: #f0f0f0; padding: 5px; border-radius: 3px;",
        )

        self._set_tooltip_if_changed(self.detail_labels["hash"], hash_display)
        self._set_tooltip_if_changed(self.detail_labels["image_path"], image_path_display)
        self._set_tooltip_if_changed(self.detail_labels["command_line"], command_line)

        self.current_entry_id = entry_id
