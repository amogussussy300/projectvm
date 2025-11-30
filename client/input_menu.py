
from PyQt6.QtWidgets import (
    QFormLayout, QDialog, QWidget, QLineEdit, QListWidget, QListWidgetItem,
    QVBoxLayout, QDialogButtonBox, QSizePolicy
)
from PyQt6.QtCore import Qt


class InlineSearchWidget(QWidget):
    def __init__(self, parent=None, items: list[str] | None = None):
        super().__init__(parent)
        self._all_items = list(items or [])

        l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(2)

        self.le = QLineEdit(self)
        self.le.setPlaceholderText("Поиск...")
        l.addWidget(self.le)

        self.listw = QListWidget(self)
        self.listw.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.listw.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        l.addWidget(self.listw)

        self._repopulate(self._all_items)

        self.le.textEdited.connect(self._on_text_edited)
        self.le.returnPressed.connect(self._on_return_pressed)
        self.le.installEventFilter(self)
        self.listw.itemClicked.connect(self._on_item_clicked)

        self._update_list_visibility()

    def set_items(self, items: list[str]):
        self._all_items = list(items or [])
        self._repopulate(self._all_items)
        self._update_list_visibility()

    def currentText(self) -> str:
        return self.le.text().strip()

    def setText(self, text: str):
        self.le.setText(text or "")

    def _repopulate(self, items: list[str]):
        self.listw.clear()
        for s in items:
            QListWidgetItem(s, self.listw)

    def _on_text_edited(self, text: str):
        txt = (text or "").strip().lower()
        if not txt:
            matches = self._all_items[:]
        else:
            matches = [s for s in self._all_items if txt in s.lower()]
        self._repopulate(matches)
        self._update_list_visibility()
        self.le.setCursorPosition(len(text))

    def _on_item_clicked(self, item: QListWidgetItem):
        self.le.setText(item.text())
        self._update_list_visibility()
        self.le.setFocus()

    def _on_return_pressed(self):
        current = self.listw.currentItem()
        if current:
            self.le.setText(current.text())
        self._update_list_visibility()
        self.le.setFocus()

    def _update_list_visibility(self):
        visible = self.listw.count() > 0
        self.listw.setVisible(visible)

    def eventFilter(self, watched, event):
        if watched is self.le and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Down:
                if self.listw.count() == 0:
                    return True
                cur = self.listw.currentRow()
                if cur < 0:
                    self.listw.setCurrentRow(0)
                else:
                    nxt = min(self.listw.count() - 1, cur + 1)
                    self.listw.setCurrentRow(nxt)
                return True
        return super().eventFilter(watched, event)


class InputMenu(QDialog):
    def __init__(self, parent=None, cpus: list = None, gpus: list = None):
        super().__init__(parent)
        self.setWindowTitle("Введите данные")
        self.setFixedWidth(520)

        layout = QFormLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        cpus = cpus or []
        gpus = gpus or []

        cpu_names = [c.get("name", "") for c in cpus if c.get("name")]
        gpu_names = [g.get("name", "") for g in gpus if g.get("name")]

        self.cpu_widget = InlineSearchWidget(self, cpu_names)
        self.gpu_widget = InlineSearchWidget(self, gpu_names)

        layout.addRow("CPU:", self.cpu_widget)
        layout.addRow("GPU:", self.gpu_widget)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                        QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(self.buttons)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    def get_data(self):
        return {
            "CPU": self.cpu_widget.currentText(),
            "GPU": self.gpu_widget.currentText()
        }
