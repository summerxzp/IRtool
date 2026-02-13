from PyQt6.QtWidgets import QWidget


_BASE_STYLESHEET = """
QWidget {
    background-color: #f6f7f9;
    color: #2b2f33;
    font-family: "PingFang SC", "Microsoft YaHei", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 12px;
}

QFrame#panel {
    background-color: #ffffff;
    border: 1px solid #d6dbe1;
    border-radius: 4px;
}

QTableWidget, QTableView, QTreeView {
    background-color: #ffffff;
    border: 1px solid #d6dbe1;
    gridline-color: #e3e8ef;
}

QHeaderView::section {
    background-color: #f0f2f5;
    color: #2b2f33;
    border-top: 1px solid #d6dbe1;
    border-bottom: 1px solid #d6dbe1;
    border-right: 1px solid #d6dbe1;
    padding: 4px 6px;
}

QHeaderView::section:first {
    border-left: 1px solid #d6dbe1;
}

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {
    background-color: #ffffff;
    border: 1px solid #cfd6de;
    border-radius: 4px;
    padding: 4px 6px;
    selection-background-color: #e6f0ff;
    selection-color: #1f2a44;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid #4c8dff;
}

QComboBox::drop-down {
    border: none;
    width: 18px;
}

QPushButton {
    background-color: #eef1f5;
    border: 1px solid #cfd6de;
    border-radius: 4px;
    padding: 4px 10px;
}

QPushButton:hover {
    background-color: #e3e8ee;
}

QPushButton:pressed {
    background-color: #d7dee6;
}

QPushButton:disabled {
    background-color: #f3f5f7;
    color: #9aa2ab;
    border-color: #e0e5eb;
}

QCheckBox, QRadioButton {
    spacing: 6px;
}

QSplitter::handle {
    background-color: #e4e8ee;
}

QScrollBar:vertical {
    background: #f1f3f6;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #c9d1db;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

QMenu {
    background-color: #ffffff;
    border: 1px solid #d6dbe1;
    padding: 4px 0px;
}

QMenu::item {
    padding: 4px 16px;
}

QMenu::item:selected {
    background-color: #e6f0ff;
}

QToolTip {
    background-color: #ffffff;
    color: #2b2f33;
    border: 1px solid #d6dbe1;
}
"""


# Autoruns Tab specific style tokens
AUTORUNS_CONTROL_HEIGHT = 28
AUTORUNS_HEADER_HEIGHT = 28
AUTORUNS_CATEGORY_WIDTH = 110
AUTORUNS_ENTRY_MAX_WIDTH = 340
AUTORUNS_DESC_MAX_WIDTH = 260
AUTORUNS_PUBLISHER_MAX_WIDTH = 230

AUTORUNS_TREE_STYLESHEET = """
QTreeView {
    border: 1px solid #d6dbe1;
    gridline-color: #e3e8ef;
    background-color: #ffffff;
    alternate-background-color: #f7f9fb;
}
"""

AUTORUNS_DETAIL_TITLE_STYLESHEET = "font-weight: 600; font-size: 12px; padding: 5px 4px;"
AUTORUNS_DETAIL_PLACEHOLDER_STYLESHEET = "color: #88919c; font-style: italic;"
AUTORUNS_SCROLL_AREA_STYLESHEET = """
QScrollArea {
    border: 1px solid #d6dbe1;
    background-color: #ffffff;
}
"""

AUTORUNS_HELP_BUTTON_STYLESHEET = """
QPushButton {
    font-weight: 700;
    font-size: 12px;
    text-align: center;
    padding: 0px;
    margin: 0px;
}
"""

AUTORUNS_RISK_HELP_TEXT_STYLESHEET = """
QTextEdit {
    background-color: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 4px;
    padding: 10px;
    line-height: 1.6;
}
"""


def apply_flat_style(widget: QWidget) -> None:
    widget.setStyleSheet(_BASE_STYLESHEET)
