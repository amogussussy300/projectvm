from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QAction
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QGraphicsDropShadowEffect, QWidget, QMenu, QInputDialog, QFileDialog, QMessageBox, QDialog,
    QSizePolicy
)



class ConfigCard(QFrame):
    request_delete = pyqtSignal(object)
    renamed = pyqtSignal(object, str)

    def __init__(self, win_height, name, cpu, gpu, ram, mem, date, watts="---", psus=None, db_id=None):
        super().__init__()
        self._db_id = db_id
        self._name = name or ""
        self._cpu = cpu or ""
        self._gpu = gpu or ""
        self._ram = ram or ""
        self._mem = mem or ""
        self._watts = watts
        self._date = date if hasattr(date, "strftime") else datetime.now()

        self._psus = psus or []

        self.setObjectName("ConfigCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMouseTracking(True)

        base_min = int((win_height or 700) * 0.12)
        extra = min(120, 18 * max(0, len(self._psus)))
        self.setMinimumHeight(base_min + extra)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        self.setStyleSheet(":hover {border: 1px solid #3b82f6; background-color: #1e293b;}")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(12)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        self.name_lbl = QLabel(self._name)
        self.name_lbl.setObjectName("ConfigCardName")
        self.name_lbl.setStyleSheet("font-weight: bold; font-size: 15px; color: white; border: none; background: transparent;")
        header.addWidget(self.name_lbl)
        header.addStretch()

        formatted_time = self._date.strftime("%b %d, %Y в %I:%M %p")
        self.date_lbl = QLabel(formatted_time)
        self.date_lbl.setStyleSheet("color: #64748b; font-size: 11px; border: none; background: transparent;")
        header.addWidget(self.date_lbl)
        layout.addLayout(header)

        self.cpu_lbl = QLabel(f"CPU: {self._cpu}")
        self.cpu_lbl.setStyleSheet("border: none; background: transparent; color: #e6eef8;")
        layout.addWidget(self.cpu_lbl)

        self.gpu_lbl = QLabel(f"GPU: {self._gpu}")
        self.gpu_lbl.setStyleSheet("border: none; background: transparent; color: #e6eef8;")
        layout.addWidget(self.gpu_lbl)

        self.ram_lbl = QLabel(f"RAM: {self._ram}")
        self.ram_lbl.setStyleSheet("border: none; background: transparent; color: #e6eef8;")
        layout.addWidget(self.ram_lbl)

        self.mem_lbl = QLabel(f"MEM: {self._mem}")
        self.mem_lbl.setStyleSheet("border: none; background: transparent; color: #e6eef8;")
        layout.addWidget(self.mem_lbl)

        footer = QHBoxLayout()
        footer.addStretch()
        self.res_lbl = QLabel(f"{self._watts}W рекомендуется")
        self.res_lbl.setStyleSheet("color: #60a5fa; font-weight: bold; border: none; background: transparent;")
        footer.addWidget(self.res_lbl)
        layout.addLayout(footer)

        self.psu_lbl = QLabel()
        self.psu_lbl.setWordWrap(True)
        self.psu_lbl.setStyleSheet("color: #cbd5e1; font-size: 11px; border: none; background: transparent;")
        max_lines = min(6, max(1, len(self._psus)))
        self.psu_lbl.setMaximumHeight(18 * max_lines)
        self.psu_lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
        layout.addWidget(self.psu_lbl)

        self._refresh_psu_label()

        for child in self.findChildren(QWidget):
            if child is self:
                continue
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            child.setMouseTracking(True)

    def _refresh_psu_label(self):
        if self._psus:
            parts = []
            for p in self._psus:
                if isinstance(p, dict):
                    name = p.get("name", "")
                    watt = p.get("wattage", "")
                    parts.append(f"{name} ({watt}W)")
                else:
                    parts.append(str(p))
            text = "; ".join(parts)
        else:
            text = "Нет рекомендаций PSU"
        self.psu_lbl.setText(f"Рекомендуемые БП: {text}")
        max_lines = min(6, max(1, len(self._psus)))
        self.psu_lbl.setMaximumHeight(18 * max_lines)

    def update_psus(self, psus: list, required: int | None = None):
        self._psus = psus or []
        if required is not None:
            self._watts = required
            self.res_lbl.setText(f"{self._watts}W рекомендуется")
        self._refresh_psu_label()


    def enterEvent(self, event):
        print("ConfigCard: enterEvent")
        super().enterEvent(event)

    def leaveEvent(self, event):
        print("ConfigCard: leaveEvent")
        super().leaveEvent(event)

    def contextMenuEvent(self, event):
        parent_for_menu = self.window() or self
        menu = QMenu(parent_for_menu)
        menu.setObjectName("ConfigCardContextMenu")
        menu.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        menu.setStyleSheet("""
            QMenu#ConfigCardContextMenu { background-color: #0f172a; color: #e2e8f0; border: 1px solid #334155; }
            QMenu#ConfigCardContextMenu::item { padding: 8px 16px; min-width: 160px; }
            QMenu#ConfigCardContextMenu::item:selected { background-color: #1e293b; color: #ffffff; }
        """) # +

        act_rename = QAction("Переименовать", self)
        act_export = QAction("Сохранить в .txt", self)
        act_delete = QAction("Удалить", self)

        menu.addAction(act_rename)
        menu.addAction(act_export)
        menu.addSeparator()
        menu.addAction(act_delete)

        act_rename.triggered.connect(lambda: QTimer.singleShot(0, lambda: self._on_rename(parent_for_menu)))
        act_export.triggered.connect(lambda: QTimer.singleShot(0, lambda: self._on_export(parent_for_menu)))
        act_delete.triggered.connect(lambda: QTimer.singleShot(0, lambda: self._on_delete(parent_for_menu)))

        menu.exec(event.globalPos())

    def _on_rename(self, dialog_parent):
        try:
            current = self.name_lbl.text() if hasattr(self, "name_lbl") else self._name
            dlg = QInputDialog(dialog_parent)
            dlg.setWindowTitle("Переименовать")
            dlg.setLabelText("Название:")
            dlg.setTextValue(current)
            dlg.setModal(True)

            if dlg.exec() == QDialog.DialogCode.Accepted:
                new_text = dlg.textValue().strip()
                if new_text and new_text != self._name:
                    self._name = new_text
                    if hasattr(self, "name_lbl"):
                        self.name_lbl.setText(new_text)

                        self.name_lbl.repaint()
                        self.name_lbl.updateGeometry()
                    self.updateGeometry()
                    self.repaint()
                    self.update()

                    try:
                        self.renamed.emit(self, new_text)
                    except Exception:
                        pass

        except Exception as e:
            print("не удалось переименовать configcard:", e)

    def _on_export(self, dialog_parent):
        default_name = f"{self._name}.txt" if self._name else "configuration.txt"
        options = QFileDialog.Option.DontUseNativeDialog
        path, _ = QFileDialog.getSaveFileName(dialog_parent, "Сохранить конфигурацию", default_name,
                                               "Text Files (*.txt);;All Files (*)", options=options)
        if path:
            try:
                content = self._build_export_text()
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                QMessageBox.information(dialog_parent, "Экспортирована", f"Конфигурация сохранена в:\n{path}")
            except Exception as e:
                QMessageBox.critical(dialog_parent, "Ошибка", f"Не удалось сохранить конфигурацию:\n{e}")

    def _build_export_text(self):
        date_text = None
        if hasattr(self, "date_lbl") and self.date_lbl is not None:
            try:
                date_text = self.date_lbl.text()
            except Exception:
                date_text = None
        if not date_text:
            try:
                date_text = self._date.strftime("%b %d, %Y в %I:%M %p")
            except Exception:
                date_text = str(self._date)

        lines = [
            f"Name: {self._name}",
            f"Date: {date_text}",
            f"CPU: {self._cpu}",
            f"GPU: {self._gpu}",
            f"RAM: {self._ram}",
            f"MEM: {self._mem}",
            f"PSUs: {' '.join(map(str, self._psus))}"
            f"Рекомендовано ватт: {self._watts}W",
        ]
        return "\n".join(lines)

    def _on_delete(self, dialog_parent):
        name = self.name_lbl.text() if hasattr(self, "name_lbl") else self._name
        reply = QMessageBox.question(
            dialog_parent, "Удаление конфигурации",
            f"Вы точно хотите удалить конфигурацию '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.request_delete.emit(self)