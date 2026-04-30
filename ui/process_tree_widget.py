import html
from typing import List

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit

from core.process_tree import get_process_chain, ProcessNode


class _ProcessTreeWorker(QThread):
    finished = pyqtSignal(int, list)

    def __init__(self, pid: int):
        super().__init__()
        self._pid = pid

    def run(self):
        chain = get_process_chain(self._pid)
        self.finished.emit(self._pid, chain)


class ProcessTreeWidget(QWidget):
    """显示进程及其父进程链（按需异步查询）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_pid: int = -1
        self._worker: _ProcessTreeWorker = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel("父进程链")
        title.setStyleSheet(
            "font-weight: bold; font-size: 11px; color: #555; "
            "padding: 3px 6px; background: #f0f2f5; "
            "border-top: 1px solid #d6dbe1;"
        )
        layout.addWidget(title)

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setStyleSheet(
            "QTextEdit { background:#fafbfc; border:none; "
            "border-top:1px solid #e8ecf1; "
            "font-family:'Microsoft YaHei','Consolas','Segoe UI',monospace; "
            "font-size:12px; padding:6px; }"
        )
        layout.addWidget(self._text)
        self._show_placeholder()

    def _show_placeholder(self):
        self._text.setHtml(
            '<span style="color:#aaa;font-style:italic;">选择一行以查看父进程链</span>'
        )

    def load_pid(self, pid: int):
        if pid == self._current_pid:
            return
        self._current_pid = pid

        if self._worker and self._worker.isRunning():
            self._worker.finished.disconnect()
            self._worker.quit()

        self._text.setHtml('<span style="color:#aaa;">查询中…</span>')
        self._worker = _ProcessTreeWorker(pid)
        self._worker.finished.connect(self._on_result)
        self._worker.start()

    def clear(self):
        self._current_pid = -1
        if self._worker and self._worker.isRunning():
            self._worker.finished.disconnect()
            self._worker.quit()
        self._worker = None
        self._show_placeholder()

    def _on_result(self, queried_pid: int, chain: List[ProcessNode]):
        if queried_pid != self._current_pid:
            return
        self._worker = None
        if not chain:
            self._text.setHtml(
                f'<span style="color:#aaa;">PID {queried_pid} 进程已退出</span>'
            )
            return
        self._text.setHtml(self._render_html(chain))

    @staticmethod
    def _render_html(chain: List[ProcessNode]) -> str:
        rows = []
        for i, node in enumerate(chain):
            indent = '&nbsp;' * (i * 4)
            prefix = '↑&nbsp;' if i > 0 else ''

            if node.is_suspicious:
                name_color = '#c62828'
                name_weight = 'bold'
            elif node.is_target:
                name_color = '#1565c0'
                name_weight = 'bold'
            else:
                name_color = '#2b2f33'
                name_weight = 'normal'

            name_part = (
                f'<span style="color:{name_color};font-weight:{name_weight};">'
                f'{html.escape(node.name)}</span>'
                f'&nbsp;<span style="color:#888;">(PID:&nbsp;{node.pid})</span>'
            )

            if node.is_suspicious and node.suspicious_reason:
                name_part += (
                    f'&nbsp;<span style="color:#c62828;font-size:11px;">'
                    f'[{html.escape(node.suspicious_reason)}]</span>'
                )

            if node.create_time:
                name_part += (
                    f'&nbsp;<span style="color:#aaa;font-size:11px;">'
                    f'{node.create_time}</span>'
                )

            exe_part = ''
            if node.exe:
                exe_color = '#c62828' if node.is_suspicious else '#666'
                exe_part = (
                    f'<br>{indent}&nbsp;&nbsp;&nbsp;&nbsp;'
                    f'<span style="color:{exe_color};font-size:11px;">'
                    f'{html.escape(node.exe)}</span>'
                )

            rows.append(f'{indent}{prefix}{name_part}{exe_part}')

        return '<br>'.join(rows)
