from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFontDatabase, QKeySequence, QTextCursor
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from utils.file_io import atomic_write_text


class FileEditor(QWidget):
    content_changed = pyqtSignal(str)
    save_requested = pyqtSignal()
    open_requested = pyqtSignal(str)
    state_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_filepath: str | None = None
        self._updating = False
        self._modified = False
        self._save_error = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        bar = QHBoxLayout()
        self._label = QLabel("CON Preview & Advanced Editor")
        self._label.setStyleSheet("font-weight: 700;")
        self._label.setToolTip(
            "The generated CON text. Direct edits are allowed and validated before saving."
        )
        bar.addWidget(self._label)
        bar.addStretch()

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: gray;")
        bar.addWidget(self._status_label)

        self._save_button = QPushButton("Save CON")
        self._save_button.clicked.connect(self.save_requested.emit)
        bar.addWidget(self._save_button)
        layout.addLayout(bar)

        self._editor = _ConEdit()
        self._editor.textChanged.connect(self._on_text_changed)
        self._editor.file_dropped.connect(self.open_requested.emit)
        layout.addWidget(self._editor)

    def _on_text_changed(self):
        if not self._updating:
            self._save_error = ""
            self._modified = True
            self._status_label.setText("Unsaved changes")
            self.content_changed.emit(self._editor.toPlainText())
            self.state_changed.emit()

    def load_file(self, filepath: str) -> bool:
        self._updating = True
        try:
            text = Path(filepath).read_text(encoding="utf-8-sig")
            self._editor.setPlainText(text)
            self._current_filepath = filepath
            self._label.setText(f"CON Preview: {Path(filepath).name}")
            self._status_label.setText("Loaded from disk")
            self._modified = False
            self._save_error = ""
            self.state_changed.emit()
            return True
        except Exception as error:
            QMessageBox.critical(self, "Open CON Failed", f"Could not open the file:\n{error}")
            return False
        finally:
            self._updating = False

    def set_content(self, text: str, label: str = "", modified: bool = True):
        self._updating = True
        self._editor.setPlainText(text)
        if label:
            self._label.setText(f"CON Preview: {label}")
        self._modified = modified
        self._save_error = ""
        self._status_label.setText("Unsaved changes" if modified else "Loaded from disk")
        self._updating = False
        self.state_changed.emit()

    def set_save_error(self, reason: str):
        self._save_error = reason
        self._modified = True
        self._status_label.setText("CON invalid — saving is blocked")
        self.state_changed.emit()

    def confirm_discard_changes(self) -> bool:
        if not self._modified:
            return True
        choice = QMessageBox.warning(
            self,
            "Unsaved CON File",
            "Save changes to the current CON file before continuing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if choice == QMessageBox.StandardButton.Cancel:
            return False
        if choice == QMessageBox.StandardButton.Save:
            return self.save()
        return True

    def save(self, filepath: str | None = None) -> bool:
        if self._save_error:
            QMessageBox.warning(
                self,
                "Saving Blocked",
                self._save_error
                + "\n\nCorrect the assignments or format, or reopen the source CON "
                "and discard the invalid edits.",
            )
            return False
        path = filepath or self._current_filepath
        if not path:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save CON File", "", "CON Files (*.CON *.con);;All Files (*)"
            )
            if not path:
                return False
        try:
            backup_path = atomic_write_text(
                path,
                self._editor.toPlainText(),
                create_backup=True,
            )
            self._current_filepath = path
            self._label.setText(f"CON Preview: {Path(path).name}")
            self._modified = False
            if backup_path:
                self._status_label.setText(
                    f"Saved — backup: {backup_path.name}"
                )
            else:
                self._status_label.setText("Saved")
            self.state_changed.emit()
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save CON Failed",
                f"Could not save the file:\n{e}")
            return False

    @property
    def current_filepath(self) -> str | None:
        return self._current_filepath

    @property
    def plain_text(self) -> str:
        return self._editor.toPlainText()

    @property
    def is_modified(self) -> bool:
        return self._modified

    def set_read_only(self, ro: bool):
        self._editor.setReadOnly(ro)


class _ConEdit(QPlainTextEdit):
    """Internal text editor with CON-specific context menu."""

    file_dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(10)
        self.setFont(font)
        self.setTabStopDistance(20)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setAcceptDrops(True)

    def contextMenuEvent(self, event):
        menu = QMenu(self)

        act_cut = menu.addAction("Cut")
        act_cut.setShortcut(QKeySequence.StandardKey.Cut)
        act_cut.triggered.connect(self.cut)
        act_cut.setEnabled(self.textCursor().hasSelection())

        act_copy = menu.addAction("Copy")
        act_copy.setShortcut(QKeySequence.StandardKey.Copy)
        act_copy.triggered.connect(self.copy)
        act_copy.setEnabled(self.textCursor().hasSelection())

        act_paste = menu.addAction("Paste")
        act_paste.setShortcut(QKeySequence.StandardKey.Paste)
        act_paste.triggered.connect(self.paste)

        menu.addSeparator()

        act_duplicate = menu.addAction("Duplicate Line")
        act_duplicate.setShortcut("Ctrl+D")
        act_duplicate.triggered.connect(self._duplicate_line)

        act_delete = menu.addAction("Delete Line")
        act_delete.setShortcut("Ctrl+Del")
        act_delete.triggered.connect(self._delete_line)

        menu.exec(event.globalPos())

    def _duplicate_line(self):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine,
                            QTextCursor.MoveMode.KeepAnchor)
        text = cursor.selectedText()
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine)
        cursor.insertText("\n" + text)

    def _delete_line(self):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine,
                            QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.deleteChar()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                p = Path(path)
                if p.suffix.upper() == ".CON":
                    self.file_dropped.emit(str(p.resolve()))
                break
