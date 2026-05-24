from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtSvg import QSvgRenderer
import os
import sys
import tempfile


_CHECK_SVG_CONTENT = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
    '<path d="M3.5 8.5L6.5 11.5L12.5 4.5" stroke="white" stroke-width="2.2" '
    'stroke-linecap="round" stroke-linejoin="round" fill="none"/>'
    '</svg>'
)

_check_svg_path = None


def _ensure_check_svg():
    global _check_svg_path
    if _check_svg_path and os.path.exists(_check_svg_path):
        return _check_svg_path
    try:
        base = os.path.dirname(__file__)
        path = os.path.join(base, '_check.svg')
        if os.path.isfile(path):
            _check_svg_path = path
            return path
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
            path = os.path.join(base, 'ui', '_check.svg')
            if os.path.isfile(path):
                _check_svg_path = path
                return path
        with open(path, 'w', encoding='utf-8') as f:
            f.write(_CHECK_SVG_CONTENT)
        _check_svg_path = path
        return path
    except Exception:
        try:
            tmp = os.path.join(tempfile.gettempdir(), '_check.svg')
            with open(tmp, 'w', encoding='utf-8') as f:
                f.write(_CHECK_SVG_CONTENT)
            _check_svg_path = tmp
            return tmp
        except Exception:
            return None


_BASE_STYLESHEET = """
QWidget {
    background-color: #f5f6f8;
    color: #2b2f33;
    font-family: "PingFang SC", "Microsoft YaHei", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 12px;
}

QFrame#panel {
    background-color: #ffffff;
    border: 1px solid #dce1e8;
    border-radius: 6px;
}

QFrame#panel QLabel,
QFrame#panel QCheckBox,
QFrame#panel QRadioButton {
    background: transparent;
}

QFrame#stats-bar {
    background-color: transparent;
    border: none;
    border-top: 1px solid #dce1e8;
    border-radius: 0px;
}

QFrame#stats-bar QLabel {
    background: transparent;
}

QTableWidget, QTableView, QTreeView {
    background-color: #ffffff;
    border: 1px solid #dce1e8;
    border-radius: 4px;
    gridline-color: #f0f2f5;
    alternate-background-color: #f8f9fc;
    selection-background-color: #dceaff;
    selection-color: #1a2a44;
}

QTableWidget::item:selected, QTableView::item:selected {
    background-color: #dceaff;
    color: #1a2a44;
}

QTableWidget::item:hover, QTableView::item:hover {
    background-color: #edf2fb;
}

QTreeView::item {
    padding: 2px 4px;
    border-radius: 3px;
}

QTreeView::item:selected {
    background-color: #dceaff;
    color: #1a2a44;
}

QTreeView::item:hover {
    background-color: #edf2fb;
}

QHeaderView::section {
    background-color: #f0f2f6;
    color: #3a3f47;
    border: none;
    border-bottom: 2px solid #dce1e8;
    border-right: 1px solid #e8ebf0;
    padding: 6px 8px;
    font-weight: 600;
    font-size: 12px;
}

QHeaderView::section:first {
    border-left: none;
}

QHeaderView::section:last {
    border-right: none;
}

QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #ffffff;
    border: 1px solid #d0d6e0;
    border-radius: 5px;
    padding: 5px 8px;
    selection-background-color: #dceaff;
    selection-color: #1a2a44;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1.5px solid #4c8dff;
    background-color: #ffffff;
}

QPushButton {
    background-color: #ffffff;
    border: 1px solid #d0d6e0;
    border-radius: 5px;
    padding: 5px 14px;
    font-weight: 500;
    color: #3a3f47;
}

QPushButton:hover {
    background-color: #f0f4ff;
    border-color: #b8c8e8;
    color: #1a5fbf;
}

QPushButton:pressed {
    background-color: #dceaff;
    border-color: #4c8dff;
}

QPushButton:disabled {
    background-color: #f5f6f8;
    color: #b0b5bd;
    border-color: #e4e8ee;
}

QPushButton[class="primary"] {
    background-color: #4c8dff;
    border: 1px solid #3a7af0;
    color: #ffffff;
    font-weight: 600;
    font-size: 13px;
    padding: 5px 16px;
}

QPushButton[class="primary"]:hover {
    background-color: #3a7af0;
    border-color: #2e6ae0;
}

QPushButton[class="primary"]:pressed {
    background-color: #2e6ae0;
}

QPushButton[class="primary"]:disabled {
    background-color: #a8c4f0;
    border-color: #90b4e8;
    color: #d0e0ff;
}

QPushButton[class="danger"] {
    background-color: #ffffff;
    border: 1px solid #e8a0a0;
    color: #c0392b;
    font-size: 13px;
    padding: 5px 16px;
}

QPushButton[class="danger"]:hover {
    background-color: #fde8e8;
    border-color: #e07070;
}

QPushButton[class="danger"]:pressed {
    background-color: #f8d0d0;
}

QPushButton[class="danger"]:disabled {
    background-color: #f5f6f8;
    border-color: #e4e8ee;
    color: #b0b5bd;
}

QPushButton[class="dropdown"] {
    background-color: #ffffff;
    border: 1px solid #d0d6e0;
    border-radius: 5px;
    padding: 5px 28px 5px 12px;
    font-weight: 500;
    color: #3a3f47;
    text-align: left;
}

QPushButton[class="dropdown"]:hover {
    background-color: #f0f4ff;
    border-color: #b8c8e8;
}

QPushButton[class="dropdown"]:pressed {
    background-color: #dceaff;
    border-color: #4c8dff;
}

QMenu#dropdown_menu {
    background-color: #ffffff;
    border: 1px solid #dce1e8;
    border-radius: 5px;
    padding: 4px 0px;
}

QMenu#dropdown_menu::item {
    padding: 6px 16px;
    border-radius: 3px;
    margin: 0px 4px;
    color: #3a3f47;
}

QMenu#dropdown_menu::item:selected {
    background-color: #edf2fb;
    color: #1a5fbf;
}

QCheckBox, QRadioButton {
    spacing: 6px;
    color: #3a3f47;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1.5px solid #c0c6d0;
    background-color: #ffffff;
}

QCheckBox::indicator:checked {
    background-color: #4c8dff;
    border-color: #4c8dff;
}

QCheckBox::indicator:hover {
    border-color: #4c8dff;
}

QRadioButton::indicator {
    width: 16px;
    height: 16px;
}

QSplitter::handle {
    background-color: #e4e8ee;
    height: 2px;
}

QSplitter::handle:hover {
    background-color: #4c8dff;
}

QTabWidget::pane {
    border: none;
    background-color: #f5f6f8;
}

QTabBar#mainTabBar {
    background-color: #ffffff;
    border-bottom: 1px solid #dce1e8;
}

QTabBar#mainTabBar::tab {
    background-color: transparent;
    color: #6b7280;
    border: none;
    border-bottom: 2px solid transparent;
    padding: 9px 20px;
    margin: 0px;
    font-size: 12px;
    font-weight: 500;
}

QTabBar#mainTabBar::tab:selected {
    background-color: transparent;
    color: #1a5fbf;
    font-weight: 600;
    border-bottom: 2px solid #4c8dff;
}

QTabBar#mainTabBar::tab:hover:!selected {
    background-color: rgba(76, 141, 255, 0.06);
    color: #3a3f47;
    border-bottom: 2px solid #d0d6e0;
}

QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #cdd3dc;
    min-height: 30px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #a8b0bc;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background: #cdd3dc;
    min-width: 30px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background: #a8b0bc;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
}

QMenu {
    background-color: #ffffff;
    border: 1px solid #dce1e8;
    border-radius: 6px;
    padding: 4px 0px;
}

QMenu::item {
    padding: 6px 20px;
    border-radius: 4px;
    margin: 0px 4px;
}

QMenu::item:selected {
    background-color: #edf2fb;
    color: #1a5fbf;
}

QMenu::separator {
    height: 1px;
    background: #eef0f4;
    margin: 4px 8px;
}

QToolTip {
    background-color: #ffffff;
    color: #2b2f33;
    border: 1px solid #dce1e8;
    border-radius: 4px;
    padding: 5px 8px;
    font-size: 12px;
}

QStatusBar {
    background-color: #f0f2f6;
    border-top: 1px solid #dce1e8;
    color: #6b7280;
}

QMessageBox {
    background-color: #ffffff;
}
"""

AUTORUNS_SPACING_XS = 4
AUTORUNS_SPACING_SM = 8
AUTORUNS_SPACING_MD = 10
AUTORUNS_RADIUS_SM = 5
AUTORUNS_FONT_SIZE_SM = 12
AUTORUNS_CONTROL_HEIGHT = 30
AUTORUNS_HEADER_HEIGHT = 30
AUTORUNS_CATEGORY_WIDTH = 110
AUTORUNS_ENTRY_MAX_WIDTH = 340
AUTORUNS_DESC_MAX_WIDTH = 260
AUTORUNS_PUBLISHER_MAX_WIDTH = 230

AUTORUNS_TREE_STYLESHEET = """
QTreeView {
    border: 1px solid #dce1e8;
    background-color: #ffffff;
    border-radius: 4px;
}
"""

AUTORUNS_DETAIL_TITLE_STYLESHEET = "font-weight: 600; font-size: 13px; padding: 6px 4px; color: #1a2a44;"
AUTORUNS_DETAIL_PLACEHOLDER_STYLESHEET = "color: #9aa2ab; font-style: italic; font-size: 12px;"
AUTORUNS_SCROLL_AREA_STYLESHEET = """
QScrollArea {
    border: 1px solid #dce1e8;
    background-color: #ffffff;
    border-radius: 4px;
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
    background-color: #f8f9fc;
    border: 1px solid #dce1e8;
    border-radius: 6px;
    padding: 12px;
    line-height: 1.6;
}
"""


_CHECK_PIXMAP = None


def _render_check_pixmap():
    global _CHECK_PIXMAP
    if _CHECK_PIXMAP is not None:
        return _CHECK_PIXMAP
    try:
        from PyQt6.QtCore import QByteArray
        svg_bytes = QByteArray(_CHECK_SVG_CONTENT.encode('utf-8'))
        renderer = QSvgRenderer(svg_bytes)
        if renderer.isValid():
            size = renderer.defaultSize()
            pm = QPixmap(size)
            pm.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pm)
            renderer.render(painter)
            painter.end()
            _CHECK_PIXMAP = pm
            return pm
    except Exception:
        pass
    pm = QPixmap(16, 16)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(255, 255, 255), 2.2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.drawLine(QPointF(3.5, 8.5), QPointF(6.5, 11.5))
    painter.drawLine(QPointF(6.5, 11.5), QPointF(12.5, 4.5))
    painter.end()
    _CHECK_PIXMAP = pm
    return pm


def apply_flat_style(widget: QWidget) -> None:
    svg_path = _ensure_check_svg()
    if svg_path:
        svg_url = svg_path.replace('\\', '/')
        extra = (
            f"QCheckBox::indicator:checked {{ "
            f"background-color: #4c8dff; border-color: #4c8dff; "
            f"image: url({svg_url}); "
            f"}}"
        )
        widget.setStyleSheet(_BASE_STYLESHEET + extra)
    else:
        widget.setStyleSheet(_BASE_STYLESHEET)
