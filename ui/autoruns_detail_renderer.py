import os

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QGuiApplication, QMouseEvent
from PyQt6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QWidget,
    QPushButton,
    QSizePolicy,
)

# ============================================================
# 样式常量 - 现代 Inspector Panel 风格
# ============================================================
_FONT_UI = "'Segoe UI', 'Microsoft YaHei', sans-serif"
_FONT_MONO = "Consolas, 'Courier New', monospace"

# 颜色
_C_BG = "#ffffff"
_C_BG_CODE = "#f4f6f9"
_C_BG_CODE_ERR = "#fff0f0"
_C_TEXT_PRIMARY = "#1a2a44"
_C_TEXT_SECONDARY = "#5a6270"
_C_TEXT_MUTED = "#8a94a6"
_C_TEXT_GREEN = "#2e7d32"
_C_TEXT_RED = "#d32f2f"
_C_TEXT_ORANGE = "#f57c00"
_C_BORDER = "#e4e8ee"
_C_BORDER_CODE = "#d0d6e0"

# 标题
_S_TITLE = (
    f"font-family: {_FONT_UI}; font-size: 17px; font-weight: 600; "
    f"color: {_C_TEXT_PRIMARY}; padding: 2px 0px;"
)
# 元信息
_S_META = (
    f"font-family: {_FONT_UI}; font-size: 12px; "
    f"color: {_C_TEXT_MUTED}; padding-bottom: 4px;"
)
# 字段标签
_S_LABEL = (
    f"font-family: {_FONT_UI}; font-size: 12px; "
    f"color: {_C_TEXT_MUTED}; padding-top: 10px; padding-bottom: 2px;"
)
# 普通值
_S_VALUE = (
    f"font-family: {_FONT_UI}; font-size: 13px; "
    f"color: {_C_TEXT_SECONDARY}; padding: 2px 0px;"
)
# 代码值（路径、命令行）
_S_CODE = (
    f"font-family: {_FONT_MONO}; font-size: 13px; "
    f"color: {_C_TEXT_PRIMARY}; background: {_C_BG_CODE}; "
    f"padding: 6px 8px; border-radius: 4px; border: 1px solid {_C_BORDER_CODE};"
)
_S_CODE_ERR = (
    f"font-family: {_FONT_MONO}; font-size: 13px; "
    f"color: {_C_TEXT_RED}; background: {_C_BG_CODE_ERR}; "
    f"padding: 6px 8px; border-radius: 4px; border: 1px solid #f0c0c0;"
)

# 签名状态
_S_SIG_VERIFIED = f"font-family: {_FONT_UI}; font-size: 12px; color: {_C_TEXT_GREEN}; font-weight: 600;"
_S_SIG_UNSIGNED = f"font-family: {_FONT_UI}; font-size: 12px; color: {_C_TEXT_RED}; font-weight: 600;"
_S_SIG_ERROR = f"font-family: {_FONT_UI}; font-size: 12px; color: {_C_TEXT_ORANGE}; font-weight: 600;"

# 文本链接（复制、展开共用样式）
_LINK_STYLE = (
    "color: #4a6fa5; font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif; "
    "font-size: 12px;"
)
_LINK_HOVER_STYLE = "color: #2a4f85; text-decoration: underline;"

# 分割线
_S_SEPARATOR = f"background-color: {_C_BORDER};"


# ============================================================
# 组件
# ============================================================

class _CopyLink(QLabel):
    """文本链接样式的复制标签（比 QPushButton 更容易和字段名对齐）"""

    def __init__(self, get_text_fn, parent=None):
        super().__init__("复制", parent)
        self._get_text = get_text_fn
        self.setStyleSheet(_LINK_STYLE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("点击复制")

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            text = self._get_text()
            if text:
                clipboard = QGuiApplication.clipboard()
                clipboard.setText(text)
                original = self.text()
                self.setText("已复制")
                self.setStyleSheet(
                    "color: #2e7d32; font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif; font-size: 12px;"
                )
                QTimer.singleShot(1200, lambda: (
                    self.setText(original),
                    self.setStyleSheet(_LINK_STYLE),
                ))
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self.setStyleSheet(_LINK_HOVER_STYLE)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet(_LINK_STYLE)
        super().leaveEvent(event)


class _CodeBlock(QWidget):
    """代码块：Label行 + 代码值 + 复制按钮在Label行右侧"""

    def __init__(self, label_text: str, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Label 行：字段名 + 复制按钮
        label_row = QWidget()
        label_layout = QHBoxLayout(label_row)
        label_layout.setContentsMargins(0, 0, 0, 0)
        label_layout.setSpacing(4)
        label_layout.setAlignment(Qt.AlignmentFlag.AlignBottom)

        self.label = QLabel(label_text)
        self.label.setStyleSheet(_S_LABEL)
        label_layout.addWidget(self.label)

        self.copy_btn = _CopyLink(lambda: self.value_label.text())
        label_layout.addWidget(self.copy_btn)
        label_layout.addStretch(1)

        layout.addWidget(label_row)

        # 代码值
        self.value_label = QLabel("")
        self.value_label.setWordWrap(True)
        self.value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.value_label.setStyleSheet(_S_CODE)
        self.value_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.value_label)

    def set_text(self, text: str):
        self.value_label.setText(text)

    def set_error(self, error: bool):
        self.value_label.setStyleSheet(_S_CODE_ERR if error else _S_CODE)

    def set_tooltip(self, tooltip: str):
        self.value_label.setToolTip(tooltip)


class _ExpandableValue(QWidget):
    """可展开/收起的单行值显示组件，展开后自动换行"""

    _MAX_WIDTH_PX = 360

    def __init__(self, parent=None):
        super().__init__(parent)
        self._full_text = ""
        self._expanded = False
        self._needs_expand = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.value_label = QLabel("")
        self.value_label.setWordWrap(False)  # 收起时单行
        self.value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.value_label.setStyleSheet(_S_VALUE)
        self.value_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.value_label)

        self.expand_btn = QLabel("")
        self.expand_btn.setStyleSheet(_LINK_STYLE)
        self.expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.expand_btn.mousePressEvent = self._on_expand_click
        self.expand_btn.enterEvent = self._on_expand_enter
        self.expand_btn.leaveEvent = self._on_expand_leave
        self.expand_btn.hide()
        layout.addWidget(self.expand_btn)

    def _on_expand_click(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_expand()

    def _on_expand_enter(self, event):
        self.expand_btn.setStyleSheet(_LINK_HOVER_STYLE)

    def _on_expand_leave(self, event):
        self.expand_btn.setStyleSheet(_LINK_STYLE)

    def set_text(self, text: str):
        self._full_text = text
        self._expanded = False
        self._update_display()

    def _check_needs_expand(self) -> bool:
        if not self._full_text:
            return False
        fm = self.value_label.fontMetrics()
        adv = fm.horizontalAdvance(self._full_text)
        if adv <= 0 and len(self._full_text) > 30:
            return True
        return adv > self._MAX_WIDTH_PX

    def _truncate_to_width(self) -> str:
        if not self._full_text:
            return ""
        fm = self.value_label.fontMetrics()
        adv = fm.horizontalAdvance(self._full_text)
        if adv <= 0:
            if len(self._full_text) > 35:
                return self._full_text[:35] + "..."
            return self._full_text
        if adv <= self._MAX_WIDTH_PX:
            return self._full_text
        ellipsis = "..."
        ellipsis_w = fm.horizontalAdvance(ellipsis)
        avail = self._MAX_WIDTH_PX - ellipsis_w
        if avail <= 0:
            return self._full_text[:10] + ellipsis
        low, high = 0, len(self._full_text)
        while low < high:
            mid = (low + high + 1) // 2
            if fm.horizontalAdvance(self._full_text[:mid]) <= avail:
                low = mid
            else:
                high = mid - 1
        return self._full_text[:low] + ellipsis

    def _update_display(self):
        if not self._full_text:
            self.value_label.setText("")
            self.expand_btn.hide()
            return

        self._needs_expand = self._check_needs_expand()

        if not self._needs_expand:
            self.value_label.setText(self._full_text)
            self.value_label.setWordWrap(False)
            self.expand_btn.hide()
            return

        if self._expanded:
            self.value_label.setText(self._full_text)
            self.value_label.setWordWrap(True)  # 展开时自动换行
            self.expand_btn.setText("收起")
            self.expand_btn.show()
        else:
            truncated = self._truncate_to_width()
            self.value_label.setText(truncated)
            self.value_label.setWordWrap(False)
            self.expand_btn.setText("展开")
            self.expand_btn.show()

    def _toggle_expand(self):
        self._expanded = not self._expanded
        self._update_display()

    def set_tooltip(self, tooltip: str):
        self.value_label.setToolTip(tooltip)


class _Field(QWidget):
    """普通字段：Label + Value"""

    def __init__(self, label_text: str, expandable=False, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.label = QLabel(label_text)
        self.label.setStyleSheet(_S_LABEL)
        layout.addWidget(self.label)

        if expandable:
            self.value_widget = _ExpandableValue()
            layout.addWidget(self.value_widget)
            self.value_label = self.value_widget.value_label
        else:
            self.value_label = QLabel("")
            self.value_label.setWordWrap(True)
            self.value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.value_label.setStyleSheet(_S_VALUE)
            layout.addWidget(self.value_label)
            self.value_widget = None

    def set_text(self, text: str):
        if self.value_widget:
            self.value_widget.set_text(text)
        else:
            self.value_label.setText(text)

    def set_tooltip(self, tooltip: str):
        if self.value_widget:
            self.value_widget.set_tooltip(tooltip)
        else:
            self.value_label.setToolTip(tooltip)


class _Separator(QWidget):
    """水平分割线"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(1)
        self.setStyleSheet(_S_SEPARATOR)


# ============================================================
# 主渲染器
# ============================================================

class AutorunsDetailRenderer:
    """Detail Pane 渲染器 - Inspector Panel 风格"""

    def __init__(self, splitter: QSplitter, detail_container: QWidget, placeholder_style: str):
        self.splitter = splitter
        self.detail_container = detail_container
        self.placeholder_style = placeholder_style
        self.current_entry_id = None
        self._path_exists_cache = {}

        # 主布局
        self.main_layout = QVBoxLayout(self.detail_container)
        self.main_layout.setContentsMargins(16, 14, 16, 14)
        self.main_layout.setSpacing(0)

        # 占位符状态
        self._placeholder_label = None
        self._content_widget = None

        # 内容区控件引用
        self._entry_label = None
        self._meta_label = None
        self._fields = {}

    def _clear_content(self):
        if self._content_widget:
            self._content_widget.deleteLater()
            self._content_widget = None
        if self._placeholder_label:
            self._placeholder_label.deleteLater()
            self._placeholder_label = None
        self._fields.clear()

    def clear(self):
        self._clear_content()

    def show_placeholder(self):
        self._clear_content()
        self._placeholder_label = QLabel("选择一条记录以查看详情")
        self._placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder_label.setStyleSheet(self.placeholder_style)
        self.main_layout.addWidget(self._placeholder_label)
        self.main_layout.addStretch()
        self.current_entry_id = None

    def _ensure_content_widgets(self):
        if self._content_widget is not None:
            return

        self._clear_content()

        self._content_widget = QWidget()
        layout = QVBoxLayout(self._content_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # === 第一行：标题区 + SHA256 并排 ===
        title_row = QWidget()
        title_layout = QHBoxLayout(title_row)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(0)
        title_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # 左栏：Entry名称 + 元信息
        title_left = QWidget()
        title_left_layout = QVBoxLayout(title_left)
        title_left_layout.setContentsMargins(0, 0, 0, 0)
        title_left_layout.setSpacing(0)

        self._entry_label = QLabel("")
        self._entry_label.setStyleSheet(_S_TITLE)
        self._entry_label.setWordWrap(True)
        title_left_layout.addWidget(self._entry_label)

        self._meta_label = QLabel("")
        self._meta_label.setStyleSheet(_S_META)
        title_left_layout.addWidget(self._meta_label)

        title_layout.addWidget(title_left, 7)

        # 固定间距
        title_layout.addSpacing(24)

        # 右栏：SHA256
        self._fields["hash"] = _Field("SHA256")
        title_layout.addWidget(self._fields["hash"], 3)

        layout.addWidget(title_row)
        layout.addSpacing(6)
        layout.addWidget(_Separator())

        # === 第二行：描述 + 时间戳 并排 ===
        row1 = QWidget()
        row1_layout = QHBoxLayout(row1)
        row1_layout.setContentsMargins(0, 0, 0, 0)
        row1_layout.setSpacing(0)
        row1_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._fields["description"] = _Field("描述", expandable=True)
        row1_layout.addWidget(self._fields["description"], 7)

        row1_layout.addSpacing(24)

        self._fields["timestamp"] = _Field("时间戳")
        row1_layout.addWidget(self._fields["timestamp"], 3)

        layout.addWidget(row1)
        layout.addWidget(_Separator())

        # === 第三行：发布者 + 版本 并排 ===
        row2 = QWidget()
        row2_layout = QHBoxLayout(row2)
        row2_layout.setContentsMargins(0, 0, 0, 0)
        row2_layout.setSpacing(0)
        row2_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._fields["publisher"] = _Field("发布者")
        row2_layout.addWidget(self._fields["publisher"], 7)

        row2_layout.addSpacing(24)

        self._fields["version"] = _Field("版本")
        row2_layout.addWidget(self._fields["version"], 3)

        layout.addWidget(row2)
        layout.addWidget(_Separator())

        # === 全宽数据区：路径、命令行 ===
        self._path_block = _CodeBlock("文件路径")
        layout.addWidget(self._path_block)

        self._cmd_block = _CodeBlock("命令行")
        layout.addWidget(self._cmd_block)

        layout.addStretch()
        self.main_layout.addWidget(self._content_widget)

    @staticmethod
    def _set_text_if_changed(label: QLabel, text: str):
        if label.text() != text:
            label.setText(text)

    def _should_probe_path_synchronously(self, image_path: str) -> bool:
        if not image_path:
            return False
        if image_path.startswith("\\\\"):
            return False
        drive, _ = os.path.splitdrive(image_path)
        return bool(drive)

    def _path_exists(self, image_path: str) -> bool:
        cached = self._path_exists_cache.get(image_path)
        if cached is not None:
            return cached
        exists = os.path.exists(image_path)
        self._path_exists_cache[image_path] = exists
        return exists

    def render_detail(self, data: dict, format_file_size):
        self._ensure_content_widgets()
        self.splitter.setSizes([700, 300])

        detail_data = data.get("detail_data", {})
        entry_id = data.get("id")

        signer_status = data.get("signer_status", "")
        if "(Verified)" in signer_status:
            signature_display = "Verified"
        elif "(Error)" in signer_status:
            signature_display = f"Error: {data.get('signature_detail', 'Unknown error')}"
        else:
            signature_display = "Unsigned"

        image_path = detail_data.get("image_path", "")
        file_not_found = False
        if (
            image_path
            and image_path.lower() != "file not found"
            and self._should_probe_path_synchronously(image_path)
        ):
            file_not_found = not self._path_exists(image_path)
        image_path_display = f"{image_path}  (文件不存在)" if file_not_found else image_path

        hash_value = detail_data.get("hash", "")
        hash_display = hash_value if hash_value else "未计算"
        command_line = str(detail_data.get("command_line", "") or "")

        # 标题
        self._set_text_if_changed(
            self._entry_label, str(data.get("entry", "") or "")
        )

        # 元信息
        meta_parts = []
        if signature_display:
            meta_parts.append(signature_display)
        category = str(data.get("category", "") or "")
        if category:
            meta_parts.append(category)
        file_size = format_file_size(detail_data.get("size", ""))
        if file_size:
            meta_parts.append(file_size)
        self._set_text_if_changed(
            self._meta_label, "  ·  ".join(meta_parts)
        )
        # 签名颜色
        if signature_display == "Verified":
            self._meta_label.setStyleSheet(_S_SIG_VERIFIED)
        elif signature_display.startswith("Error"):
            self._meta_label.setStyleSheet(_S_SIG_ERROR)
        else:
            self._meta_label.setStyleSheet(_S_SIG_UNSIGNED)
        self._meta_label.setText("  ·  ".join(meta_parts))

        # 标题行右栏：SHA256
        self._fields["hash"].set_text(hash_display)

        # 第二行：描述 + 时间戳
        self._fields["description"].set_text(
            str(data.get("description", "") or "")
        )
        self._fields["timestamp"].set_text(
            str(detail_data.get("timestamp", "") or "")
        )

        # 第三行：发布者 + 版本
        self._fields["publisher"].set_text(
            str(detail_data.get("publisher", "") or "")
        )
        self._fields["version"].set_text(
            str(detail_data.get("version", "") or "")
        )

        # 全宽代码块
        self._path_block.set_text(str(image_path_display or ""))
        self._path_block.set_error(file_not_found)
        self._path_block.set_tooltip(image_path_display)

        self._cmd_block.set_text(command_line)
        self._cmd_block.set_tooltip(command_line)

        self.current_entry_id = entry_id
