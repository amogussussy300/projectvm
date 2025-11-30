import sys
from datetime import datetime
from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QScrollArea,
    QLineEdit, QProgressDialog
)
import json
from functools import partial
from input_menu import InputMenu
from config_card import ConfigCard
from calls import CalculationWorker
import storage_sql as storage


def load_stylesheet(filepath: str) -> str:
    """
    считывает все что в stylesheet
    :param filepath: путь до таблицы
    :return: внутренности таблицы
    """
    try:
        with open(filepath, "r") as f:
            return f.read()
    except FileNotFoundError:
        print(f"таблица не найдена {filepath}")
        return ""


class MainWindow(QMainWindow):
    """
    основное окно приложения
    """
    def __init__(self):
        super().__init__()
        self._loading_workers = []

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.default_width, self.default_height = 1000, 700
        self.resize(self.default_width, self.default_height)

        self.drag_pos = None
        self.resizing_edge = None
        self.resize_margin = 8

        self.setMouseTracking(True)

        # центральный виджет для хранения title bar'а и content'а
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        central_widget.setMouseTracking(True)

        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # title bar
        self.title_bar_widget = self._create_title_bar()
        self.main_layout.addWidget(self.title_bar_widget)

        # content widget и layout (хранят все кроме title bar)
        content = QWidget()
        content.setMouseTracking(True)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(30, 30, 30, 30)
        content_layout.setSpacing(20)
        self.main_layout.addWidget(content)

        # поиск
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск...")
        self.search_input.setFixedWidth(300)
        self.search_input.textChanged.connect(self.on_search_text_changed)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._perform_search)

        # рассчитать
        self.add_btn = QPushButton("+ Новая конфигурация")
        self.add_btn.setObjectName("PrimaryButton")
        self.add_btn.clicked.connect(self.start_calculation)

        # бар для хранения кнопки и поиска
        action_bar = QHBoxLayout()
        action_bar.addWidget(self.search_input)
        action_bar.addStretch()
        action_bar.addWidget(self.add_btn)
        content_layout.addLayout(action_bar)

        # scrollarea (хранит card_container, позволяет крутить)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")

        # card_container (хранит карточки конфигураций)
        self.card_container = QWidget()
        self.card_container.setStyleSheet("background: transparent;")
        self.card_layout = QVBoxLayout(self.card_container)
        self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.card_layout.setSpacing(15)

        scroll.setWidget(self.card_container)
        content_layout.addWidget(scroll)

        # загружаем карточки из бд
        self.load_from_db()

    def _create_title_bar(self) -> QFrame:
        """
        инициализация title bar'а
        :return: title bar
        """
        title_bar = QFrame()
        title_bar.setFixedHeight(50)
        title_bar.setStyleSheet("background-color: #0f172a; border-bottom: 1px solid #1e293b;") # зацыганил

        title_bar.setMouseTracking(True)

        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(15, 0, 10, 0)

        title = QLabel("Client")
        title.setStyleSheet("font-weight: bold; font-size: 16px; color: white; border: none;") # тоже
        layout.addWidget(title)

        layout.addStretch()

        btn_min = QPushButton("—") # +
        btn_min.setFixedSize(30, 30)
        btn_min.setObjectName("MinButton")
        btn_min.clicked.connect(self.showMinimized)

        btn_close = QPushButton("✕") # +
        btn_close.setFixedSize(30, 30)
        btn_close.setObjectName("IconButton")
        btn_close.clicked.connect(self.close)

        layout.addWidget(btn_min)
        layout.addWidget(btn_close)

        self.overlay = QWidget(self)

        self.overlay.setStyleSheet("background-color: rgba(0, 0, 0, 120);") # +

        self.overlay.hide()

        return title_bar

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        отвечает за передвижение окна + за resize
        :param event:
        :return:
        """
        if event.button() == Qt.MouseButton.LeftButton:
            local_pos = self.mapFromGlobal(event.globalPosition().toPoint())
            self.resizing_edge = self._get_resize_edge(local_pos)

            if self.resizing_edge: # если клик на resize edge -> resize
                self.drag_pos = event.globalPosition().toPoint()
                event.accept()

            elif event.pos().y() < self.title_bar_widget.height(): # если клик на title bar но не на resize edge -> передвигаем
                child = self.childAt(event.pos())
                if not isinstance(child, QPushButton):
                    self.windowHandle().startSystemMove()
                    event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """
        отвечает за изменение иконки курсора и resize (пока зажата лкм)
        :param event:
        :return:
        """
        pos = self.mapFromGlobal(event.globalPosition().toPoint())

        # меняем курсор в зависимости от положения
        edge = self._get_resize_edge(pos)
        self._set_cursor_shape(edge)

        # изменяем размер
        if self.resizing_edge:
            if event.buttons() == Qt.MouseButton.LeftButton:
                self._handle_resize(event.globalPosition().toPoint()) # см. _handle_resize
                event.accept()
                return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        """
        возвращаем переменные в дефолтное состояние
        :param event:
        :return:
        """
        self.resizing_edge = None
        self.drag_pos = None

    def _get_resize_edge(self, pos: QPoint) -> str | None:
        """
        определяем в каком месте у нас курсор
        :param pos:
        :return:
        """
        rect = self.rect()
        m = self.resize_margin

        x, y, w, h = pos.x(), pos.y(), rect.width(), rect.height()

        on_left = x < m
        on_right = x > w - m
        on_top = y < m
        on_bottom = y > h - m

        if on_top and on_left: return "top_left"
        if on_top and on_right: return "top_right"
        if on_bottom and on_left: return "bottom_left"
        if on_bottom and on_right: return "bottom_right"
        if on_left: return "left"
        if on_right: return "right"
        if on_top: return "top"
        if on_bottom: return "bottom"

        return None

    def _set_cursor_shape(self, edge: str) -> None:
        """
        меняем иконку курсора
        :param edge:
        :return:
        """
        if edge in ["top_left", "bottom_right"]:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edge in ["top_right", "bottom_left"]:
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif edge in ["left", "right"]:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edge in ["top", "bottom"]:
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def _on_db_calc_finished(self, result: dict, card: ConfigCard, worker: CalculationWorker):
        try:
            if worker in self._loading_workers:
                self._loading_workers.remove(worker)
        except Exception:
            pass

        if not result or result.get("error"):
            return

        psus = result.get("psus", [])
        required = result.get("required", None)

        try:
            if card is None or not hasattr(card, "psu_lbl"):
                return
        except Exception:
            return

        try:
            card.update_psus(psus or [], required)
            db_id = getattr(card, "_db_id", None)
            if db_id:
                try:
                    storage.update_config_psus(db_id, psus or [])
                except Exception as e:
                    print("Failed to persist psus to DB:", e)
        except Exception as e:
            print("Failed to update card PSUs:", e)

    def _handle_resize(self, global_pos: QPoint) -> None:
        """
        меняет размеры окна в зависимости от наличия и т.п. resize'а\n
        необходим, т.к. у нас безрамочное приложение
        :param global_pos: позиция курсора по отношению ко всему монитору (разрешению экрана)
        :return:
        """
        if not self.drag_pos: return

        delta = global_pos - self.drag_pos
        rect = self.geometry()

        if "right" in self.resizing_edge:
            rect.setWidth(rect.width() + delta.x())
        if "left" in self.resizing_edge:
            new_width = rect.width() - delta.x()
            if new_width > self.minimumWidth():
                rect.setLeft(rect.left() + delta.x())

        if "bottom" in self.resizing_edge:
            rect.setHeight(rect.height() + delta.y())
        if "top" in self.resizing_edge:
            new_height = rect.height() - delta.y()
            if new_height > self.minimumHeight():
                rect.setTop(rect.top() + delta.y())

        self.setGeometry(rect)
        self.drag_pos = global_pos

    def load_from_db(self) -> None:
        rows = storage.get_all_configs()
        for row in rows:
            self.add_card_from_db(row)

        QTimer.singleShot(0, lambda: (self.card_container.adjustSize(), self.card_container.updateGeometry()))

        try:
            self.card_container.adjustSize()
            self.card_container.updateGeometry()
        except Exception:
            pass

    def add_card_from_db(self, row: dict) -> None:
        d = datetime.fromisoformat(row["created_at"]) if row.get("created_at") else datetime.now()
        base_h = self._card_base_height()
        psus_data = None
        if row.get("psus") is not None:
            p = row.get("psus")
            try:
                if isinstance(p, str):
                    psus_data = json.loads(p)
                else:
                    psus_data = p
            except Exception:
                psus_data = None

        card = ConfigCard(base_h,
                          row.get("name", ""),
                          row.get("cpu"),
                          row.get("gpu"),
                          row.get("ram"),
                          row.get("mem"),
                          d,
                          row.get("watts", "---"),
                          db_id=row.get("id"),
                          psus=psus_data)
        card._name = row.get("name", "") or ""
        card._cpu = row.get("cpu", "") or ""
        card._gpu = row.get("gpu", "") or ""
        card._ram = row.get("ram", "") or ""
        card._mem = row.get("mem", "") or ""
        card._watts = str(row.get("watts", "")) or ""

        card.request_delete.connect(self._remove_card)
        card.renamed.connect(self._on_card_renamed)
        self.card_layout.insertWidget(0, card)

        if not psus_data:
            cpu_name = row.get("cpu", "") or ""
            gpu_name = row.get("gpu", "") or ""
            if cpu_name or gpu_name:
                w = CalculationWorker(task='calc', cpu_name=cpu_name, gpu_name=gpu_name)
                self._loading_workers.append(w)
                w.finished.connect(partial(self._on_db_calc_finished, card=card, worker=w))
                w.start()

    def add_card(self, name: str, cpu: str, gpu: str, ram: str, mem: str, watts: int, psus: str) -> None:
        data = {"name": name, "cpu": cpu, "gpu": gpu, "ram": ram, "mem": mem, "watts": watts, "psus": psus}
        new_id = storage.add_config_dict(data)
        d = datetime.now()
        base_h = self._card_base_height()
        card = ConfigCard(base_h, name, cpu, gpu, ram, mem, d, watts, psus=psus, db_id=new_id)

        card._name = name or ""
        card._cpu = cpu or ""
        card._gpu = gpu or ""
        card._ram = ram or ""
        card._mem = mem or ""
        card._watts = str(watts) or ""

        card.request_delete.connect(self._remove_card)
        card.renamed.connect(self._on_card_renamed)
        self.card_layout.insertWidget(0, card)

    def on_search_text_changed(self) -> None:
        """
        нужен для реализации debounce (т.е. чтобы реальный поиск начинался только после 220 мс после окончания написания названия пользователем)
        :return:
        """
        self.search_timer.start(220)

    def _perform_search(self):
        """
        координатор; читает текст из поля поиска, если пустое - то выводит все, если нет, то _filter_cards(..)
        :return:
        """
        query = self.search_input.text().strip()
        if not query:
            self._filter_cards("")
            return

        self._filter_cards(query)

    def _filter_cards(self, query: str) -> None:
        """
        поиск по карточкам в card_layout; убирает с экрана неподходящее
        :param query: текст пользователя
        :return:
        """
        q = (query or "").strip().lower()
        tokens = [t for t in q.split() if t]

        for i in range(self.card_layout.count()):
            item = self.card_layout.itemAt(i)
            w = item.widget() if item else None
            if not w:
                continue

            parts = [
                str(getattr(w, "_name", "")),
                str(getattr(w, "_cpu", "")),
                str(getattr(w, "_gpu", "")),
                str(getattr(w, "_ram", "")),
                str(getattr(w, "_mem", "")),
                str(getattr(w, "_watts", "")),
            ]
            searchable = " ".join(parts).lower()

            if not tokens:
                w.setVisible(True)
            else:
                ok = all(tok in searchable for tok in tokens)
                w.setVisible(ok)

    def _remove_card(self, card: ConfigCard) -> None:
        """
        при удалении убирает конфигурацию из приложения и бд
        :param card: карточка
        :return:
        """
        try:
            db_id = getattr(card, "_db_id", None)
            if db_id:
                storage.delete_config(db_id)
        except Exception as e:
            print("не удалось удалить карточку из бд:", e)

        self.card_layout.removeWidget(card)
        card.setParent(None)
        card.deleteLater()

    def _on_card_renamed(self, card: ConfigCard, new_name: str) -> None:
        """
        сохраняет в бд новое имя карточки
        :param card: карточка
        :param new_name: новое имя
        :return:
        """
        db_id = getattr(card, "_db_id", None)
        if db_id:
            try:
                storage.rename_config(db_id, new_name)
            except Exception as e:
                print("не удалось переименовать карточку в бд:", e)

    def start_calculation(self) -> None:
        self.add_btn.setText("Загрузка компонентов...")
        self.add_btn.setEnabled(False)

        self.worker = CalculationWorker(task='fetch')
        self.worker.finished.connect(self.open_menu)
        self.worker.start()

    def _on_calc_finished(self, result: dict):
        try:
            if hasattr(self, "progress") and self.progress:
                self.progress.close()
        except Exception:
            pass

        self.add_btn.setText("+ Новая конфигурация")
        self.add_btn.setEnabled(True)

        self.handle_result(result)

    def open_menu(self, api_data=None) -> None:
        self.add_btn.setText("+ Новая конфигурация")
        self.add_btn.setEnabled(True)

        if not api_data:
            api_data = {"cpus": [], "gpus": [], "psus": []}

        if api_data.get("error"):
            print("ошибка при получении данных из API:", api_data["error"])

        self.overlay.resize(self.size())
        self.overlay.show()

        dialog = InputMenu(self, cpus=api_data.get("cpus", []), gpus=api_data.get("gpus", []))

        if dialog.exec():
            data = dialog.get_data()
            cpu_name = data.get("CPU", "")
            gpu_name = data.get("GPU", "")

            self.progress = QProgressDialog("Вычисление конфигурации...", None, 0, 0, self)
            self.progress.setWindowModality(Qt.WindowModality.WindowModal)
            self.progress.setCancelButton(None)
            self.progress.setWindowTitle("Пожалуйста подождите")
            self.progress.setMinimumDuration(0)
            self.progress.show()

            self.calc_worker = CalculationWorker(task='calc', cpu_name=cpu_name, gpu_name=gpu_name)
            self.calc_worker.finished.connect(self._on_calc_finished)
            self.calc_worker.start()

        self.overlay.hide()

    def _card_base_height(self) -> int:
        h = self.height()
        if not h or h < 200:
            return getattr(self, "default_height", 700)
        return h

    def handle_result(self, result: dict):
        try:
            if hasattr(self, "progress") and self.progress:
                self.progress.close()
        except Exception:
            pass

        if not result:
            print("пустой результат от воркера")
            return

        if result.get("error"):
            print("ошибка при расчете:", result["error"])
            return

        required = result.get("required", "---")
        psus = result.get("psus", [])

        try:
            cpu_name = getattr(self, "calc_worker").cpu_name if hasattr(self, "calc_worker") else ""
            gpu_name = getattr(self, "calc_worker").gpu_name if hasattr(self, "calc_worker") else ""

            data = {
                "name": "Результат",
                "cpu": cpu_name,
                "gpu": gpu_name,
                "ram": "",
                "mem": "",
                "watts": required,
                "psus": psus
            }
            new_id = storage.add_config_dict(data)
            d = datetime.now()
            base_h = self._card_base_height()
            card = ConfigCard(base_h, "Результат", cpu_name, gpu_name, "", "", d, required, psus=psus, db_id=new_id)

            card._name = "Результат"
            card._cpu = cpu_name or ""
            card._gpu = gpu_name or ""
            card._ram = ""
            card._mem = ""
            card._watts = str(required) or ""

            card.request_delete.connect(self._remove_card)
            card.renamed.connect(self._on_card_renamed)
            self.card_layout.insertWidget(0, card)
        except Exception as e:
            print("Не удалось сохранить/создать карточку:", e)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    storage.setup()
    stylesheet = load_stylesheet("style.qss")
    if stylesheet:
        app.setStyleSheet(stylesheet)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())