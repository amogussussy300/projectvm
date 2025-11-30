import sys
from datetime import datetime
from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QScrollArea,
    QLineEdit
)

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
    Основное окно приложения
    """
    def __init__(self):
        super().__init__()

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
        self.add_btn = QPushButton("Рассчитать")
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
        """
        загружаем карточки из бд с помощью add_card_from_db
        :return:
        """
        rows = storage.get_all_configs()
        for row in rows:
            self.add_card_from_db(row)

    def add_card_from_db(self, row: dict) -> None:
        """
        добавляем карточку в card_layout из бд
        :param row: карточка
        :return:
        """
        d = datetime.fromisoformat(row["created_at"]) if row.get("created_at") else datetime.now()
        card = ConfigCard(self.height(),
                          row["name"], row.get("cpu"), row.get("gpu"),
                          row.get("ram"), row.get("mem"), d, row.get("watts", "---"),
                          db_id=row["id"])
        card._name = row.get("name", "") or ""
        card._cpu = row.get("cpu", "") or ""
        card._gpu = row.get("gpu", "") or ""
        card._ram = row.get("ram", "") or ""
        card._mem = row.get("mem", "") or ""
        card._watts = str(row.get("watts", "")) or ""

        card.request_delete.connect(self._remove_card)
        card.renamed.connect(self._on_card_renamed)
        self.card_layout.insertWidget(0, card)

    def add_card(self, name: str, cpu: str, gpu: str, ram: str, mem: str, watts: int) -> None:
        """
        добавляем карточку в card_layout из приложения
        :param name: имя конфига
        :param cpu: проц
        :param gpu: гп
        :param ram: озу
        :param mem: память
        :param watts: потребление
        :return:
        """
        data = {"name": name, "cpu": cpu, "gpu": gpu, "ram": ram, "mem": mem, "watts": watts}
        new_id = storage.add_config_dict(data)
        d = datetime.now()
        card = ConfigCard(self.height(), name, cpu, gpu, ram, mem, d, watts, db_id=new_id)

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
                w.show()
            else:
                ok = all(tok in searchable for tok in tokens)
                w.setVisible(ok)

    # def _rebuild_cards(self, rows: list[dict]) -> None:
    #     while self.card_layout.count():
    #         item = self.card_layout.takeAt(0)
    #         w = item.widget()
    #         if w:
    #             w.setParent(None)
    #             w.deleteLater()
    #
    #     for row in rows:
    #         self.add_card_from_db(row)

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
        """
        запускает background-воркера для эмуляции api-колла и рассчета (будет изменен, но суть останется: чтоб не вис gui при рассчетах)
        :return:
        """
        self.add_btn.setText("Идет рассчет...")
        self.add_btn.setEnabled(False)

        self.worker = CalculationWorker(1, 1, 1, 1)
        self.worker.finished.connect(self.open_menu)
        self.worker.start()

    def open_menu(self) -> None:
        """
        открывает диалоговое окно InputMenu, обрабатывает данные (см. handle_result)
        :return:
        """
        self.overlay.resize(self.size())
        self.overlay.show()

        dialog = InputMenu(self)

        if dialog.exec():
            data = dialog.get_data()
            self.handle_result(data)

        self.overlay.hide()

        self.add_btn.setText("Рассчитать")
        self.add_btn.setEnabled(True)

    def handle_result(self, result: dict):
        """
        добавляет карточку в приложение и бд по данным из result (будет изменен)
        :param result: данные введенные пользователем
        :return:
        """
        self.add_btn.setText("+ Новая конфигурация")
        self.add_btn.setEnabled(True)
        self.add_card(
            "Результат",
            result["CPU"],
            result["GPU"],
            result["RAM"],
            result["MEM"],
            str(result['REC'])
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    storage.setup()
    stylesheet = load_stylesheet("style.qss")
    if stylesheet:
        app.setStyleSheet(stylesheet)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())