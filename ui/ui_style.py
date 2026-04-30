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
    alternate-background-color: #f9fafc;
}

QTableWidget::item:selected, QTableView::item:selected {
    background-color: #d6e8ff;
    color: #1a2a44;
}

QTableWidget::item:hover, QTableView::item:hover {
    background-color: #eef3fb;
}

QTreeView::item:selected {
    background-color: #d6e8ff;
    color: #1a2a44;
}

QTreeView::item:hover {
    background-color: #eef3fb;
}

QHeaderView::section {
    background-color: #f0f2f5;
    color: #2b2f33;
    border-top: 1px solid #d6dbe1;
    border-bottom: 1px solid #d6dbe1;
    border-right: 1px solid #d6dbe1;
    padding: 4px 6px;
    font-weight: 600;
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

QSplitter::handle:hover {
    background-color: #c5cdd9;
}

QTabWidget::pane {
    border: 1px solid #d6dbe1;
    border-top: none;
    background-color: #f6f7f9;
}

QTabBar::tab {
    background-color: #eef1f5;
    color: #555e6b;
    border: 1px solid #d6dbe1;
    border-bottom: none;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    padding: 5px 14px;
    margin-right: 2px;
    font-size: 12px;
}

QTabBar::tab:selected {
    background-color: #f6f7f9;
    color: #1a5fbf;
    font-weight: 600;
    border-bottom: 2px solid #4c8dff;
}

QTabBar::tab:hover:!selected {
    background-color: #e3e8ee;
    color: #2b2f33;
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

QScrollBar:horizontal {
    background: #f1f3f6;
    height: 10px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background: #c9d1db;
    min-width: 20px;
    border-radius: 5px;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
}

QMenu {
    background-color: #ffffff;
    border: 1px solid #d6dbe1;
    border-radius: 4px;
    padding: 4px 0px;
}

QMenu::item {
    padding: 5px 18px;
    border-radius: 3px;
}

QMenu::item:selected {
    background-color: #e6f0ff;
    color: #1a5fbf;
}

QMenu::separator {
    height: 1px;
    background: #e3e8ef;
    margin: 3px 6px;
}

QToolTip {
    background-color: #ffffff;
    color: #2b2f33;
    border: 1px solid #d6dbe1;
    border-radius: 3px;
    padding: 4px 6px;
}
"""


# Autoruns Tab specific style tokens
AUTORUNS_SPACING_XS = 4
AUTORUNS_SPACING_SM = 8
AUTORUNS_SPACING_MD = 10
AUTORUNS_RADIUS_SM = 4
AUTORUNS_FONT_SIZE_SM = 12
AUTORUNS_CONTROL_HEIGHT = 28
AUTORUNS_HEADER_HEIGHT = 28
AUTORUNS_CATEGORY_WIDTH = 110
AUTORUNS_ENTRY_MAX_WIDTH = 340
AUTORUNS_DESC_MAX_WIDTH = 260
AUTORUNS_PUBLISHER_MAX_WIDTH = 230

AUTORUNS_TREE_STYLESHEET = """
QTreeView {
    border: 1px solid #d6dbe1;
    background-color: #ffffff;
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
