import shutil
from pathlib import Path

from PyQt6.QtCore import QDir, QFileSystemWatcher, QPoint, Qt, pyqtSignal
from PyQt6.QtGui import (
    QAction,
    QDragEnterEvent,
    QDropEvent,
    QFileSystemModel,
)
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QTreeView,
    QVBoxLayout,
    QWidget,
)


class _DragTreeView(QTreeView):
    """QTreeView subclass that accepts file drag-and-drop from OS."""

    file_dropped = pyqtSignal(str)
    gds_context_menu = pyqtSignal(str)
    action_requested = pyqtSignal(str, str)  # action, context_path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

    def _current_path(self) -> str | None:
        idx = self.currentIndex()
        if idx.isValid():
            return self.model().filePath(idx)
        return None

    def _context_path(self, pos: QPoint) -> str:
        idx = self.indexAt(pos)
        if idx.isValid():
            return self.model().filePath(idx)
        return ""

    def _on_context_menu(self, pos: QPoint):
        ctx_path = self._context_path(pos)
        is_dir = Path(ctx_path).is_dir() if ctx_path else False
        menu = QMenu(self)

        if ctx_path:
            act_copy = QAction("Copy", self)
            act_copy.triggered.connect(lambda: self.action_requested.emit("copy", ctx_path))
            menu.addAction(act_copy)

            act_cut = QAction("Cut", self)
            act_cut.triggered.connect(lambda: self.action_requested.emit("cut", ctx_path))
            menu.addAction(act_cut)

            act_duplicate = QAction("Duplicate", self)
            act_duplicate.triggered.connect(lambda: self.action_requested.emit("duplicate", ctx_path))
            menu.addAction(act_duplicate)

            menu.addSeparator()

            act_delete = QAction("Delete", self)
            act_delete.triggered.connect(lambda: self.action_requested.emit("delete", ctx_path))
            menu.addAction(act_delete)

            if is_dir:
                menu.addSeparator()
                act_folder = QAction("New Folder", self)
                act_folder.triggered.connect(lambda: self.action_requested.emit("new_folder", ctx_path))
                menu.addAction(act_folder)

        menu.addSeparator()
        act_paste = QAction("Paste", self)
        act_paste.triggered.connect(lambda: self.action_requested.emit("paste", ctx_path))
        menu.addAction(act_paste)

        if ctx_path and Path(ctx_path).suffix.lower() == ".gds":
            menu.addSeparator()
            act_gen = QAction("Detect R23 Marks...", self)
            act_gen.triggered.connect(lambda: self.gds_context_menu.emit(ctx_path))
            menu.addAction(act_gen)

        menu.exec(self.viewport().mapToGlobal(pos))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            path = self._current_path()
            if path:
                self.action_requested.emit("delete", path)
            event.accept()
        else:
            super().keyPressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()

    def dropEvent(self, event: QDropEvent):
        pos = event.position().toPoint()
        idx = self.indexAt(pos)
        if idx.isValid():
            target_path = self.model().filePath(idx)
            target_dir = str(Path(target_path) if Path(target_path).is_dir()
                            else Path(target_path).parent)
        else:
            target_dir = self.model().filePath(self.rootIndex())
        if not target_dir:
            target_dir = ""

        for url in event.mimeData().urls():
            src_path = url.toLocalFile()
            if not src_path:
                continue
            src = Path(src_path)
            dst = Path(target_dir) / src.name
            try:
                if src.is_dir():
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)
                self.file_dropped.emit(str(dst.resolve()))
            except Exception:
                pass
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()


class DirectoryTreeWidget(QWidget):
    gds_clicked = pyqtSignal(str)
    con_clicked = pyqtSignal(str)
    gds_context_menu = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = QFileSystemModel()
        self._model.setFilter(QDir.Filter.AllDirs | QDir.Filter.Files | QDir.Filter.NoDotAndDotDot)
        self._model.setNameFilters(["*.gds", "*.GDS", "*.CON", "*.con", "*.CBC", "*.CCC", "*.log"])
        self._model.setNameFilterDisables(False)
        self._root_path = ""
        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self._on_directory_changed)

        self._clipboard_path: str | None = None
        self._is_cut: bool = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        top = QHBoxLayout()
        title = QLabel("Project Files")
        title.setStyleSheet("font-size: 14px; font-weight: 700;")
        top.addWidget(title)
        top.addStretch()
        layout.addLayout(top)

        hint = QLabel("Double-click a GDS or CON file to open it.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: palette(text);")
        layout.addWidget(hint)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Show:"))
        self._filter_combo = QComboBox()
        self._filter_combo.addItems(["All supported files", "GDS files", "CON files"])
        self._filter_combo.currentTextChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self._filter_combo, 1)
        layout.addLayout(filter_row)

        self._tree = _DragTreeView()
        self._tree.setModel(self._model)
        self._tree.setRootIsDecorated(True)
        self._tree.setAnimated(True)
        self._tree.setSortingEnabled(True)
        self._tree.setIndentation(16)
        self._tree.setColumnWidth(0, 200)
        self._tree.setColumnHidden(1, True)
        self._tree.setColumnHidden(2, True)
        self._tree.setColumnHidden(3, True)
        self._tree.doubleClicked.connect(self._on_item_clicked)
        self._tree.file_dropped.connect(self._on_file_dropped)
        self._tree.gds_context_menu.connect(self.gds_context_menu.emit)
        self._tree.action_requested.connect(self._on_action)
        layout.addWidget(self._tree)
        self.set_root(str(Path.home()))

    def set_root(self, path: str):
        self._root_path = path
        if path:
            self._model.setRootPath(path)
            self._tree.setRootIndex(self._model.index(path))
            existing = self._watcher.directories()
            if existing:
                self._watcher.removePaths(existing)
            self._watcher.addPath(path)

    def _on_directory_changed(self, path: str):
        if path == self._root_path:
            self._model.setRootPath(self._root_path)
            self._tree.setRootIndex(self._model.index(self._root_path))

    def _on_item_clicked(self, index):
        path = self._model.filePath(index)
        if not path or path == self._root_path:
            return
        p = Path(path)
        if p.suffix.upper() == ".CON":
            self.con_clicked.emit(str(p.resolve()))
        elif p.suffix.lower() == ".gds":
            self.gds_clicked.emit(str(p.resolve()))

    def _on_filter_changed(self, filter_text: str):
        if filter_text == "All supported files":
            self._model.setNameFilters(["*.gds", "*.GDS", "*.CON", "*.con", "*.CBC", "*.CCC", "*.log"])
        elif filter_text == "GDS files":
            self._model.setNameFilters(["*.gds", "*.GDS"])
        elif filter_text == "CON files":
            self._model.setNameFilters(["*.CON", "*.con"])

    def _on_file_dropped(self, path: str):
        p = Path(path)
        if not p.exists():
            return
        if p.suffix.upper() == ".CON":
            self.con_clicked.emit(str(p.resolve()))
        elif p.suffix.lower() == ".gds":
            self.gds_clicked.emit(str(p.resolve()))

    # ── File operations ─────────────────────────────────────────

    def _on_action(self, action: str, ctx_path: str):
        handler = {
            "copy": self._copy_item,
            "cut": self._cut_item,
            "paste": self._paste_item,
            "duplicate": self._duplicate_item,
            "delete": self._delete_item,
            "new_folder": self._new_folder,
        }.get(action)
        if handler:
            handler(ctx_path)

    def _target_dir(self, ctx_path: str) -> str:
        if not ctx_path:
            return self._root_path
        p = Path(ctx_path)
        return str(p.parent) if p.is_file() else str(p)

    def _copy_item(self, ctx_path: str):
        if not ctx_path:
            return
        self._clipboard_path = ctx_path
        self._is_cut = False

    def _cut_item(self, ctx_path: str):
        if not ctx_path:
            return
        self._clipboard_path = ctx_path
        self._is_cut = True

    def _paste_item(self, ctx_path: str):
        if not self._clipboard_path:
            return
        src = Path(self._clipboard_path)
        if not src.exists():
            QMessageBox.warning(self, "Paste Failed", "The source file no longer exists.")
            self._clipboard_path = None
            return
        target = self._target_dir(ctx_path)
        if not target:
            QMessageBox.warning(self, "Paste Failed", "Select a destination folder first.")
            return
        dst = Path(target) / src.name
        try:
            if self._is_cut:
                shutil.move(str(src), str(dst))
                self._clipboard_path = None
            else:
                if src.is_dir():
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)
        except Exception as e:
            QMessageBox.critical(self, "Paste Failed", str(e))

    def _duplicate_item(self, ctx_path: str):
        p = Path(ctx_path)
        if not p.is_file():
            QMessageBox.warning(self, "Duplicate", "Only files can be duplicated.")
            return
        parent = p.parent
        stem, suf = p.stem, p.suffix
        for i in range(1, 100):
            dst = parent / f"{stem} ({i}){suf}"
            if not dst.exists():
                try:
                    shutil.copy2(p, dst)
                except Exception as e:
                    QMessageBox.critical(self, "File Operation Failed", str(e))
                return
        QMessageBox.warning(self, "Duplicate Failed", "Could not create a copy.")

    def _delete_item(self, ctx_path: str):
        p = Path(ctx_path)
        if not p.exists():
            return
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete \"{p.name}\"?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
            except Exception as e:
                QMessageBox.critical(self, "Delete Failed", str(e))

    def _new_folder(self, ctx_path: str):
        target = self._target_dir(ctx_path)
        if not target:
            QMessageBox.warning(self, "New Folder", "Select a destination folder first.")
            return
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name:
            try:
                (Path(target) / name).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "New Folder Failed", str(e))
