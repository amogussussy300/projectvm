from PyQt6.QtWidgets import QFormLayout, QDialog, QLineEdit, QDialogButtonBox


class InputMenu(QDialog):
    """
    будет изменен
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Введите данные")
        self.setFixedWidth(300)

        layout = QFormLayout(self)

        self.field1 = QLineEdit()
        self.field2 = QLineEdit()
        self.field3 = QLineEdit()
        self.field4 = QLineEdit()

        layout.addRow("CPU:", self.field1)
        layout.addRow("GPU:", self.field2)
        layout.addRow("RAM:", self.field3)
        layout.addRow("Memory:", self.field4)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                        QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(self.buttons)

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    def get_data(self):
        return {
            "CPU": self.field1.text(),
            "GPU": self.field2.text(),
            "RAM": self.field3.text(),
            "MEM": self.field4.text(),
            "REC": 777
        }
