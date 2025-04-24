# 📦 Стандартные библиотеки Python
import os
import sys
import math
import time
import socket
import struct
import zipfile
import datetime
import configparser

from PySide6.QtWidgets import QMessageBox

# 🌐 Настройка Qt API
os.environ['QT_API'] = 'pyside6'

from collections import deque

from PySide6.QtCore import QEvent
from PySide6.QtGui  import QCursor
from PySide6.QtWidgets import QToolTip

# 🖼️ PySide6 — Виджеты и интерфейс
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFrame, QGridLayout,
    QSizePolicy, QTextEdit, QLineEdit, QCheckBox, QFileDialog, QScrollArea,
    QGraphicsDropShadowEffect, QSpinBox
)

from PySide6.QtGui    import QDrag, QMouseEvent, QDropEvent, QDragEnterEvent, QDragMoveEvent
from PySide6.QtCore   import QByteArray, QMimeData

# 🔄 Qt Core — Сигналы, Слоты, Таймеры, Потоки
from qtpy.QtCore import (
    Qt, QThread, Signal, Slot, QPointF, QTimer
)

from PySide6.QtGui import QVector3D

# 🎨 Qt GUI — Графика и Стили
from qtpy.QtGui import (
    QPalette, QColor, QFont, QPainter, QPen
)

# 📈 Qt Charts — Графики
from qtpy.QtCharts import (
    QChart, QChartView, QLineSeries, QValueAxis
)

# 📊 PyQtGraph — Быстрая 2D и 3D визуализация
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from pyqtgraph.opengl import MeshData, GLMeshItem

# === ПАРАМЕТРЫ ПАРСЕРА ===
PL, R0 = 1000, 4000
NAKLON, SMESHENIE = -0.7565, 1.269
SCALE = math.pow(10, -SMESHENIE / NAKLON)
STRUCT_FMT = "<2HIhI6hBHBH4h3fB3HB"  # 60 bytes

# === ЦВЕТОВАЯ СХЕМА ===
COLORS = {
    "bg_main": "#1a1a1a",         # Main background (darker)
    "bg_dark": "#121212",         # Sidebar/darker areas
    "bg_card": "#252525",         # Card backgrounds
    "bg_panel": "#202020",        # Panel backgrounds
    "accent": "#81c784",         # светло-зелёный
    "accent_darker": "#66bb6a",  # чуть темнее
    "btn_normal": "#333333",      # Button normal state
    "btn_hover": "#444444",       # Button hover state
    "btn_active": "#555555",      # Button active state
    "text_primary": "#ffffff",    # Main text
    "text_secondary": "#aaaaaa",  # Secondary text
    "text_highlight": "#4fc3f7",  # Highlighted text (same as accent)
    "success": "#81c784",         # Success color
    "warning": "#ffb74d",         # Warning color
    "danger": "#e57373",          # Danger/error color
    "info": "#64b5f6",            # Info color
    "chart_grid": "#3a3a3a",      # Chart grid lines
    "chart_bg": "#242424"        # Chart background (slightly lighter than dark bg)
}

class ExportLogsThread(QThread):
    finished = Signal(str, bool, str)

    def __init__(self, log_dir: str, parent=None):
        super().__init__(parent)
        self.log_dir = log_dir


    def run(self):
        # проверим, что папка существует и есть файлы
        if not os.path.isdir(self.log_dir):
            self.finished.emit("", False, f"Directory not found: {self.log_dir}")
            return
        files = [f for f in os.listdir(self.log_dir) if os.path.isfile(os.path.join(self.log_dir,f))]
        if not files:
            self.finished.emit("", False, f"No files in {self.log_dir} to zip")
            return
        now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        archive = os.path.join(self.log_dir, f"logs_{now}.zip")
        try:
            with zipfile.ZipFile(archive, 'w') as z:
                for fn in files:
                    z.write(os.path.join(self.log_dir, fn), arcname=fn)
            self.finished.emit(archive, True, "")
        except Exception as e:
            self.finished.emit("", False, str(e))

# === WORKER ДЛЯ UART + UDP + ЛОГОВ + CRC-ОШИБОК ===
class TelemetryWorker(QThread):
    data_ready    = Signal(dict)
    packet_ready  = Signal(list)
    log_ready     = Signal(str)
    error_crc     = Signal()
    sim_ended     = Signal()
    def __init__(self, port_name="COM3", baud=9600, parent=None):
        super().__init__(parent)
        self.last_data_time = None
        # для дросселя CRC‑варнингов
        self.last_crc_warning = 0.0
        self.crc_cooldown    = 1.0   # не более 1 варнинга в секунду
        self.port_name = port_name
        self.baud = baud
        self._running = True
        self._paused = False
        # UDP по умолчанию
        self.udp_enabled = False
        self.udp_host = "127.0.0.1"
        self.udp_port = 5005
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Для режима имитации
        self.sim_enabled   = False
        self.sim_file_path = ""
        # Логи
        now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        os.makedirs("log", exist_ok=True)
        self.bin_path = f"log/grib_{now}.bin"
        self.csv_path = f"log/grib_{now}.csv"
        self.f_bin = open(self.bin_path, "ab")
        self.f_csv = open(self.csv_path, "w", encoding="utf-8")
        headers = [f"field_{i}" for i in range(len(struct.unpack(STRUCT_FMT, b'\x00'*60)))]
        self.f_csv.write(";".join(headers) + "\n")

        #from functools import reduce
        #import operator
        #def xor_block(self, data: bytes) -> int:
            #return reduce(operator.xor, data, 0)
    def xor_block(self, data: bytes) -> int:
            res = 0
            for b in data:
                res ^= b
            return res

    @Slot(bool, str)
    def update_simulation(self, enabled, file_path):
        """Настройки режима имитации из файла."""
        self.sim_enabled   = enabled
        self.sim_file_path = file_path
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_ready.emit(f"[{ts}] Simulation: enabled={enabled}, file={file_path}")

    @Slot(bool, str, int)
    def update_udp(self, enabled, host, port):
        """Обновляем настройки UDP."""
        self.udp_enabled = enabled
        self.udp_host = host
        self.udp_port = port
        ts = datetime.datetime.now()

        # Закрываем старый и создаём новый сокет
        try:
            self.udp_socket.close()
        except Exception:
            pass
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #self.udp_socket.sendto(b"status", (self.udp_host, self.udp_port))

        self.log_ready.emit(f"[{ts}] UDP settings updated: enabled={enabled}, host={host}, port={port}")
        if enabled:
            self.udp_socket.bind(('', self.udp_port))
            self.udp_socket.sendto(b"status", (self.udp_host, self.udp_port))
            self.log_ready.emit(f"[{datetime.datetime.now()}] UDP bound to port {self.udp_port} and 'status' sent")
        else:
            self.log_ready.emit(f"[{datetime.datetime.now()}] UDP disabled; socket closed")

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def is_paused(self):
        return self._paused

    def stop(self):
        self._running = False

    def run(self):
        buf = b""
        self.log_ready.emit("Telemetry thread started. Version 1.9.0 ")
        self.log_ready.emit("Надёжная версия: 1.9.0")

        while self._running:
            try:
                if self.sim_enabled and not self.udp_enabled:
                    # Режим симуляции
                    rcv = self.sim_f.read(60)
                    if not rcv:
                        self.log_ready.emit("[SIM] End of file reached")
                        self.sim_ended.emit()      # <-- + эмитим сигнал о конце
                        break
                    time.sleep(1)  # чуть-чуть притормозим, как будто приходят данные
                else:
                    # Режим UDP
                    try:
                        rcv = self.udp_socket.recv(60*100)
                    except Exception as e:
                        continue
            except Exception as e:
                continue

            self.log_ready.emit(f"[DATA] Got {len(rcv)} bytes")
            buf += rcv

            if self._paused:
                continue

            while len(buf) >= 60:
                if buf[:2] == b"\xAA\xAA":
                    chunk = buf[:60]
                    try:
                        pkt = struct.unpack(STRUCT_FMT, chunk)
                    except struct.error:
                        buf = buf[1:]
                        continue
                    if self.xor_block(chunk[:-1]) == pkt[-1]:
                        try:
                            data = {
                                "packet_num": pkt[12],
                                "timestamp": pkt[2],
                                "temp_bmp": pkt[3]/100,
                                "press_bmp": pkt[4],
                                "accel": [v*488/1000/1000 for v in pkt[5:8]],
                                "gyro": [v*70/1000 for v in pkt[8:11]],
                                "state": pkt[13] & 0x07,
                                "photo": pkt[14]/1000,
                                "mag": [v/1711 for v in pkt[15:18]],
                                "temp_ds": pkt[18]/16,
                                "gps": tuple(pkt[19:22]),
                                "gps_fix": pkt[22],
                                "scd41": pkt[23],
                                "mq4": pkt[24],
                                "me2o2": pkt[25],
                                "crc": pkt[-1]
                            }
                        except Exception as e:
                            self.log_ready.emit(f"[ERROR] Ошибка парсинга пакета: {e}")
                            buf = buf[60:]
                            continue
                        self.data_ready.emit(data)
                        self.last_data_time = time.time()
                        self.f_csv.write(";".join(str(x) for x in pkt) + "\n")
                        self.f_bin.write(chunk)
                        buf = buf[60:]
                    else:
                        self.error_crc.emit()
                        self.log_ready.emit("[WARNING] CRC mismatch")
                        buf = buf[1:]
                else:
                    buf = buf[1:]

        if self.sim_f:
            self.sim_f.close()
            self.f_bin.close()
            self.f_csv.close()
            self.log_ready.emit(f"[{datetime.datetime.now()}] TelemetryWorker stopped")

    sim_ended = Signal()  # <-- новый сигнал

# === ТЁМНАЯ ТЕМА ===
def apply_dark_theme(app: QApplication):
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(COLORS["bg_main"]))
    pal.setColor(QPalette.WindowText, QColor(COLORS["text_primary"]))
    pal.setColor(QPalette.Base, QColor(COLORS["bg_panel"]))
    pal.setColor(QPalette.AlternateBase, QColor("#353535"))
    pal.setColor(QPalette.Text, QColor(COLORS["text_primary"]))
    pal.setColor(QPalette.Button, QColor(COLORS["btn_normal"]))
    pal.setColor(QPalette.ButtonText, QColor(COLORS["text_primary"]))
    pal.setColor(QPalette.Highlight, QColor(COLORS["accent"]))
    pal.setColor(QPalette.HighlightedText, Qt.white)
    app.setPalette(pal)
    app.setStyle("Fusion")

    app.setStyleSheet(f"""
        /* Карточки со светящимся бэкграундом и тенью */
        QFrame#card {{
            border-radius: 12px;
            background-color: {COLORS['bg_dark']};
            border: 1px solid {COLORS['chart_grid']};
            padding: 16px;
        }}
        QFrame#card QCheckBox {{
            spacing: 8px;
            font-size: 10pt;
            color: {COLORS['text_primary']};
        }}
        QFrame#card QSpinBox {{
            min-width: 50px;
            font-size: 10pt;
            color: {COLORS['text_primary']};
            background: {COLORS['bg_panel']};
            border: 1px solid {COLORS['chart_grid']};
            border-radius: 4px;
            padding: 2px 4px;
        }}
        QPushButton#resetLayoutBtn {{
            background-color: {COLORS['btn_normal']};
            color: {COLORS['text_primary']};
            border-radius: 8px;
            padding: 8px 16px;
            font-size: 10pt;
        }}
        QPushButton#resetLayoutBtn:hover {{
            background-color: {COLORS['accent_darker']};
        }}
        QPushButton#resetLayoutBtn:pressed {{
            background-color: {COLORS['accent']};
        }}
        QChartView {{
            border-radius: 12px;
            background-color: transparent;
        }}
        QScrollArea {{
            border-radius: 10px;
        }}
        QPushButton {{
            border: none;
            border-radius: 8px;
            padding: 8px 14px;
            background-color: {COLORS['btn_normal']};
            color: {COLORS['text_primary']};
        }}
        QPushButton:hover {{
            background-color: {COLORS['btn_hover']};
        }}
        QToolTip {{
            background-color: #202020;
            color: #ffffff;
            border: 1px solid #81c784;
            border-radius: 4px;
            padding: 4px;
            font-size: 10pt;
        }}
        QPushButton:pressed {{
            background-color: {COLORS['btn_active']};
        }}
        QLineEdit, QTextEdit, QPlainTextEdit {{
            background-color: {COLORS['bg_panel']};
            border: 1px solid {COLORS['chart_grid']};
            border-radius: 6px;
            padding: 6px;
            color: {COLORS['text_primary']};
        }}
        QLabel {{
            font-size: 10.5pt;
        }}
    """)


# === СТРАНИЦА ТЕЛЕМЕТРИИ + ГРАФИКИ ===
class TelemetryPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QGridLayout(self)
        layout.setSpacing(12)

        # ... (весь код карточек без изменений) ...
        self.pause_btn = QPushButton("⏸ Пауза")
        self.pause_btn.setFixedHeight(40)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS["btn_normal"]};
                color: {COLORS["text_primary"]};
                border-radius: 6px;
                font-size: 11pt;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: {COLORS["btn_hover"]}; }}
            QPushButton:pressed {{ background: {COLORS["btn_active"]}; }}
        """)
        self.pause_btn.clicked.connect(self.toggle_pause)
        layout.addWidget(self.pause_btn, 0, 0, 1, 2)

        self.cards = {}
        self._last_values = {}
        labels = [
            ("Номер пакета",    "packet_num"),
            ("Время, мс",       "timestamp"),
            ("Темп BMP, °C",    "temp_bmp"),
            ("Давл BMP, Па",    "press_bmp"),
            ("Ускор (X Y Z)",   "accel"),
            ("Угл.скор (X Y Z)","gyro"),
            ("Сост.аппарата",   "state"),
            ("Фото.рез, В",     "photo"),
            ("Магн.поле (X Y Z)","mag"),
            ("Темп DS18, °C",   "temp_ds"),
            ("GPS (lat lon h)", "gps"),
            ("GPS fix",         "gps_fix"),
            ("SCD41",           "scd41"),
            ("MQ-4, ppm",       "mq4"),
            ("ME2-O2, ppm",     "me2o2"),
            ("Контр.сумма",     "crc")
        ]
        for i, (title, key) in enumerate(labels):
            card = QFrame()
            card.setObjectName("card")
            # включаем hover-события и фильтр
            card.setAttribute(Qt.WA_Hover, True)
            card.installEventFilter(self)
            card.installEventFilter(self)
            shadow = QGraphicsDropShadowEffect(card)
            shadow.setBlurRadius(12)
            shadow.setOffset(0, 4)
            shadow.setColor(QColor(0, 0, 0, 80))
            card.setGraphicsEffect(shadow)

            v = QVBoxLayout(card)
            v.setContentsMargins(10, 8, 10, 8)
            t = QLabel(title, objectName="title")
            val = QLabel("-", objectName="value")
            val.setAlignment(Qt.AlignCenter)
            val.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            v.addWidget(t); v.addWidget(val)
            layout.addWidget(card, i//2 + 1, i%2)
            self.cards[key] = val

    @Slot(dict)
    def update_values(self, data):
        self._last_values = data.copy()
        if not self.pause_btn.isEnabled():
            self.pause_btn.setEnabled(True)
        for k, w in self.cards.items():
            if k in data:
                v = data[k]
                self._last_values[k] = data[k]
                w.setText(
                    ", ".join(f"{x:.2f}" for x in v)
                    if isinstance(v, (list, tuple))
                    else (f"{v:.2f}" if isinstance(v, float) else str(v))
                )

    @Slot(dict)
    def update_chart(self, data):
        # Температура
        t = data.get("temp_bmp", 0.0)
        self.series_temp.append(self.temp_index, t)
        self.temp_index += 1
        if self.series_temp.count() > 100:
            self.series_temp.remove(0)
        # Ускорение
        a = data.get("accel", [0,0,0])
        mag = math.sqrt(a[0]**2 + a[1]**2 + a[2]**2)
        self.series_acc.append(self.acc_index, mag)
        self.acc_index += 1
        if self.series_acc.count() > 100:
            self.series_acc.remove(0)

    def eventFilter(self, obj, ev):
            from PySide6.QtCore import QEvent
            from PySide6.QtGui  import QCursor
            from PySide6.QtWidgets import QToolTip

            if ev.type() in (QEvent.HoverEnter, QEvent.HoverMove):
                # нашли карту, к которой относится obj
                for key, label in self.cards.items():
                    if label.parent() is obj:
                        val = self._last_values.get(key, None)
                        ts  = self._last_values.get("timestamp", None)
                        QToolTip.showText(
                            QCursor.pos(),
                            f"<b>{key}</b><br>raw: {val}<br>ts: {ts}"
                        )
                        break
            return super().eventFilter(obj, ev)

    @Slot()
    def toggle_pause(self):
        if hasattr(self, 'worker'):
            if self.worker.is_paused():
                self.worker.resume();    self.pause_btn.setText("⏸ Пауза")
            else:
                self.worker.pause();     self.pause_btn.setText("▶ Продолжить")

    def set_worker(self, worker):
        self.worker = worker

        # + Replace the GraphsPage class with this enhanced version

class DraggableCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def mousePressEvent(self, ev: QMouseEvent):
        mime = QMimeData()
        # передаём адрес объекта
        mime.setData("application/x-card", QByteArray(str(id(self)).encode()))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.MoveAction)

    def dragEnterEvent(self, ev: QDragEnterEvent):
        if ev.mimeData().hasFormat("application/x-card"):
            ev.acceptProposedAction()

    def dragMoveEvent(self, ev: QDragMoveEvent):
        if ev.mimeData().hasFormat("application/x-card"):
            ev.acceptProposedAction()

    def dropEvent(self, ev: QDropEvent):
        source = ev.source()
        target = self
        if isinstance(source, DraggableCard) and source is not target:
            layout = target.parent().layout()  # это QGridLayout

            # найдём позицию source и target
            idx_src = layout.indexOf(source)
            idx_tgt = layout.indexOf(target)
            r_src, c_src, _, _ = layout.getItemPosition(idx_src)
            r_tgt, c_tgt, _, _ = layout.getItemPosition(idx_tgt)

            # убираем виджеты из layout
            layout.removeWidget(source)
            layout.removeWidget(target)

            # ставим обратно на swapped позиции
            layout.addWidget(source, r_tgt, c_tgt)
            layout.addWidget(target, r_src, c_src)

        ev.acceptProposedAction()

class GraphsPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QGridLayout(self)
        # Оборачиваем сетку в прокручиваемую область
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QGridLayout(content)
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(scroll)
        scroll.setWidget(content)
        layout.setSpacing(12)

        # Dictionary to store all chart views and series
        self.charts = {}
        self.indexes = {}
        self.data_points = {}  # Store maximum points to display
        self.data_history     = {}      # Имя -> список значений
        self.default_y_ranges = {}      # Имя -> исходный диапазон по Y
        self.last_extreme     = {}      # Имя -> время последнего выхода за пределы
        self.extreme_decay    = 5.0     # секунд до сброса к дефолтному диапазону

        # Define all the charts we want to display
        chart_configs = [
            {"name": "temp_bmp", "title": "Температура BMP, °C", "color": "#5cceee", "y_range": [0, 40]},
            {"name": "press_bmp", "title": "Давление, Па", "color": "#ff9e80", "y_range": [80000, 110000]},
            {"name": "accel", "title": "Ускорение, g", "color": "#7bed9f", "y_range": [0, 3], "multi_axis": True,
             "axis_names": ["X", "Y", "Z"]},
            {"name": "gyro", "title": "Угловая скорость, °/с", "color": "#ffeb3b", "y_range": [-180, 180], "multi_axis": True,
             "axis_names": ["X", "Y", "Z"]},
            {"name": "mag", "title": "Магнитное поле", "color": "#ba68c8", "y_range": [-1, 1], "multi_axis": True,
             "axis_names": ["X", "Y", "Z"]},
            {"name": "temp_ds", "title": "Температура DS18B20, °C", "color": "#4db6ac", "y_range": [0, 40]},
            {"name": "photo", "title": "Фоторезистор, В", "color": "#fff176", "y_range": [0, 5]},
            {"name": "scd41", "title": "SCD41 (CO₂), ppm", "color": "#aed581", "y_range": [0, 2000]},
            {"name": "mq4", "title": "MQ-4 (CH₄), ppm", "color": "#f48fb1", "y_range": [0, 1000]},
            {"name": "me2o2", "title": "ME2-O2, ppm", "color": "#90caf9", "y_range": [0, 25]}
        ]

        # — load saved order —
        import configparser
        cfg = configparser.ConfigParser()
        cfg.read("config.ini")
        pos_map = {}
        if cfg.has_option("Layout", "chart_positions"):
            for token in cfg.get("Layout", "chart_positions").split(","):
                name, rs, cs = token.split(":")
                pos_map[name] = (int(rs), int(cs))

        # Добавляем виджеты по сохранённым позициям, а незаписанные — в конец
        used = set()
        for config in chart_configs:
            name = config["name"]
            if name in pos_map:
                r, c = pos_map[name]
                w = self.create_chart(config)
                layout.addWidget(w, r, c)
                used.add(name)

        # Create charts
        row, col = 0, 0
        columns = 2  # Теперь две колонки вместо трех
        for config in chart_configs:
            name = config["name"]
            if name in used:
                continue
            w = self.create_chart(config)

            while layout.itemAtPosition(row, col) is not None:
                    col += 1
                    if col >= columns:
                        col = 0
                        row += 1
            layout.addWidget(w, row, col)


    def create_chart(self, config):
        """Create a chart based on configuration"""
        name = config["name"]
        title = config["title"]
        color = config["color"]
        y_range = config["y_range"]
        multi_axis = config.get("multi_axis", False)
        axis_names = config.get("axis_names", ["X", "Y", "Z"])

        # Initialize index and series
        self.indexes[name] = 0

        # Create chart and setup
        chart = QChart()
        chart.setTitle(title)
        # - Удаляем анимацию для устранения подергиваний
        # chart.setAnimationOptions(QChart.SeriesAnimations)

        # Styling
        chart.setBackgroundVisible(False)
        chart.setBackgroundVisible(True)
        chart.setBackgroundBrush(Qt.transparent)
        chart.setTitleFont(QFont("Segoe UI", 12, QFont.Bold))
        chart.legend().setVisible(multi_axis)  # Show legend only for multi-axis charts
        chart.legend().setAlignment(Qt.AlignBottom)
        chart.legend().setFont(QFont("Segoe UI", 9))
        chart.legend().setLabelColor(QColor(COLORS["text_primary"]))

        # Axes
        ax_x = QValueAxis()
        ax_x.setLabelsVisible(True)
        ax_x.setTitleText("")              # без заголовка, но подписи видны
        ax_x.setGridLineVisible(True)
        ax_x.setMinorGridLineVisible(True)

        ax_y = QValueAxis()
        ax_y.setLabelsVisible(True)
        ax_y.setTitleText("")              # без заголовка, но подписи видны
        ax_y.setGridLineVisible(True)
        ax_y.setMinorGridLineVisible(True)

        # Styling axes
        for axis in [ax_x, ax_y]:
            axis.setLabelsColor(QColor(COLORS["text_secondary"]))
            axis.setTitleBrush(QColor(COLORS["text_secondary"]))
            ax_x.setGridLineColor(QColor(COLORS["chart_grid"]))
            ax_x.setMinorGridLineColor(QColor(COLORS["chart_grid"]))
            ax_y.setGridLineColor(QColor(COLORS["chart_grid"]))
            ax_y.setMinorGridLineColor(QColor(COLORS["chart_grid"]))
            axis.setMinorGridLineColor(QColor("#2a2a2a"))
            axis.setTitleFont(QFont("Segoe UI", 9))
            axis.setLabelsFont(QFont("Segoe UI", 8))

        # Create series
        if multi_axis:
            # For multi-axis data (like accelerometer with x,y,z)
            colors = ["#4fc3f7", "#ff9e80", "#aed581"]  # Blue, Orange, Green for X, Y, Z
            series_list = []

            for i in range(3):
                series = QLineSeries()
                series.setName(axis_names[i])
                pen = QPen()
                pen.setColor(QColor(colors[i]))
                pen.setWidthF(2.0)
                series.setPen(pen)
                series.setUseOpenGL(True)  # для сглаживания
                chart.addSeries(series)

                # We must create separate Y axis for each series to avoid scaling issues
                if i == 0:
                    # Use the main Y axis for the first series
                    chart.addAxis(ax_y, Qt.AlignLeft)
                    series.attachAxis(ax_y)
                else:
                    # Create additional Y axes that will share the same scale
                    extra_y = QValueAxis()
                    extra_y.setRange(y_range[0], y_range[1])
                    extra_y.setVisible(False)  # Hide additional Y axes, only use for scaling
                    chart.addAxis(extra_y, Qt.AlignLeft)
                    series.attachAxis(extra_y)

                # All series share the X axis
                if i == 0:
                    chart.addAxis(ax_x, Qt.AlignBottom)
                series.attachAxis(ax_x)

                series_list.append(series)

            self.charts[name] = {
                "view": None,  # Will be set below
                "chart": chart,
                "series": series_list,
                "x_axis": ax_x,
                "y_axis": ax_y,
                "multi_axis": True,
                "y_range": y_range  # + Сохраняем исходный диапазон
            }
        else:
            # For single value data
            series = QLineSeries()
            pen = QPen()
            pen.setColor(QColor(color))
            pen.setWidthF(2.5)
            series.setPen(pen)

            chart.addSeries(series)
            chart.addAxis(ax_x, Qt.AlignBottom)
            chart.addAxis(ax_y, Qt.AlignLeft)
            series.attachAxis(ax_x)
            series.attachAxis(ax_y)

            self.charts[name] = {
                "view": None,  # Will be set below
                "chart": chart,
                "series": series,
                "x_axis": ax_x,
                "y_axis": ax_y,
                "multi_axis": False,
                "y_range": y_range  # + Сохраняем исходный диапазон
            }

        # Create chart view with enhanced rendering
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.Antialiasing)
        chart_view.setRenderHint(QPainter.TextAntialiasing)
        chart_view.setRenderHint(QPainter.SmoothPixmapTransform)
        chart_view.setBackgroundBrush(Qt.transparent)
        chart_view.setMinimumHeight(250)

        # wrap into card for rounded background
        wrapper = DraggableCard()
        wrapper.setObjectName("card")
        wrapper.setProperty("chart_name", name)
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0,0,0,0)
        wrapper_layout.addWidget(chart_view)
        # +++ кнопка Save PNG +++
        btn = QPushButton("💾 Save PNG")
        btn.setFixedHeight(24)
        btn.setCursor(Qt.PointingHandCursor)
        wrapper_layout.addWidget(btn, alignment=Qt.AlignRight)
        btn.clicked.connect(lambda _, w=chart_view, n=name: self._save_chart_png(w, n))

        # Store the view reference
        self.charts[name]["view"] = chart_view

        return wrapper

    def auto_scale_y_axis(self, name, data_values):
        """Automatically scale the Y axis based on current data values with improved logic"""
        chart_data = self.charts.get(name)
        if not chart_data:
            return

        y_axis = chart_data["y_axis"]
        # + Получаем историю значений
        history = self.data_history.get(name, [])

        # + Если новых значений нет или они пустые - не меняем масштаб
        if not data_values:
            return

        # + Работаем с историей + текущими значениями для стабильного масштабирования
        all_values = history + data_values

        # + Если данных все еще мало - используем исходный диапазон
        # Всегда вычисляем мин/макс из всех собранных значений
        valid_values = [v for v in all_values if v is not None and not math.isnan(v)]
        if not valid_values:
            return
        current_min = min(valid_values)
        current_max = max(valid_values)

        # + Не допускаем, чтобы мин и макс были слишком близко друг к другу
        if abs(current_max - current_min) < 0.1:
            current_min -= 0.5
            current_max += 0.5

        # + Добавляем отступ для лучшей визуализации (20%)
        padding = (current_max - current_min) * 0.2
        new_min = current_min - padding
        new_max = current_max + padding

        current_axis_min = y_axis.min()
        current_axis_max = y_axis.max()
        now = time.time()
        if new_min < current_axis_min or new_max > current_axis_max:
            self.last_extreme[name] = now
            y_axis.setRange(new_min, new_max)
            # обновляем доп. оси в мульти-графиках
            if chart_data.get("multi_axis"):
                chart = chart_data["chart"]
                for i, series in enumerate(chart_data["series"]):
                    if i > 0:
                        for axis in chart.axes(Qt.Vertical, series):
                            axis.setRange(new_min, new_max)
            return

            # --- Если длительное время не было экстремумов, сбрасываем к дефолту ---
            if now - self.last_extreme[name] > self.extreme_decay:
                dmin, dmax = self.default_y_ranges[name]
                y_axis.setRange(dmin, dmax)
                if chart_data.get("multi_axis"):
                    chart = chart_data["chart"]
                    for i, series in enumerate(chart_data["series"]):
                        if i > 0:
                            for axis in chart.axes(Qt.Vertical, series):
                                axis.setRange(dmin, dmax)
                return

            # --- Постепенная подстройка диапазона (сглаженное сжатие) ---
            contract_alpha = 0.1
            final_min = current_axis_min + (new_min - current_axis_min) * contract_alpha
            final_max = current_axis_max + (new_max - current_axis_max) * contract_alpha
        # + Плавное изменение масштаба вместо резкого
        current_axis_min = y_axis.min()
        current_axis_max = y_axis.max()

        smooth_factor = 0.2  # Коэффициент сглаживания…
        final_min = current_axis_min + (new_min - current_axis_min) * smooth_factor
        final_max = current_axis_max + (new_max - current_axis_max) * smooth_factor
        # + Меняем масштаб только если разница существенная
        threshold = (current_axis_max - current_axis_min) * 0.1  # 10% порог изменения
        if (abs(final_min - current_axis_min) > threshold or
            abs(final_max - current_axis_max) > threshold):
            y_axis.setRange(final_min, final_max)

            # + Также обновляем дополнительные оси в мульти-графиках
            if chart_data.get("multi_axis"):
                chart = chart_data["chart"]
                for i, series in enumerate(chart_data["series"]):
                    if i > 0:  # Пропускаем первую серию, т.к. она использует основную ось
                        axes = chart.axes(Qt.Vertical, series)
                        if axes:
                            for axis in axes:
                                axis.setRange(final_min, final_max)


    @Slot(object, str)
    def _save_chart_png(self, chart_view, name: str):
        """Save given chart view to PNG via dialog."""
        path, _ = QFileDialog.getSaveFileName(
            self, f"Save chart «{name}» as PNG", f"{name}.png", "PNG Files (*.png)"
        )
        if path:
            pix = chart_view.grab()
            pix.save(path, "PNG")

    def save_layout(self):
        """Save current grid positions into config.ini as name:row:col,..."""
        import configparser
        # получаем layout, в котором лежат карточки
        scroll = self.parent().findChild(QScrollArea)
        content = scroll.widget()
        layout = content.layout()  # QGridLayout

        pairs = []
        # для каждого элемента layout
        for idx in range(layout.count()):
            item = layout.itemAt(idx)
            w = item.widget()
            if not w: continue
            name = w.property("chart_name")
            # узнаём где он
            r, c, rs, cs = layout.getItemPosition(idx)
            pairs.append(f"{name}:{r}:{c}")

        cfg = configparser.ConfigParser()
        cfg.read("config.ini")
        if "Layout" not in cfg:
            cfg["Layout"] = {}
        cfg["Layout"]["chart_positions"] = ",".join(pairs)
        with open("config.ini", "w") as f:
            cfg.write(f)

    @Slot(dict)
    def update_charts(self, data):
        import time
        now = time.time()
        if not hasattr(self, '_last_chart_update'):
            self._last_chart_update = 0
        # не чаще 20 FPS
        if now - self._last_chart_update < 0.05:
            return
        self._last_chart_update = now
        """Update all charts with new data"""
        for name, chart_data in self.charts.items():
            if name not in data:
                continue

            value = data.get(name)
            index = self.indexes.get(name, 0)
            x_axis = chart_data["x_axis"]
            max_points = self.data_points.get(name, 200)

            # + Блокируем обновления для предотвращения мерцания
            chart_view = chart_data["view"]
            chart_view.setUpdatesEnabled(False)

            # Check if this is a multi-axis chart
            if chart_data.get("multi_axis", False):
                # Multi-axis data (accel, gyro, mag)
                series_list = chart_data["series"]

                if isinstance(value, list) and len(value) >= 3:
                    data_values = []

                    for i in range(3):
                        series = series_list[i]
                        if series.count() >= max_points:
                            # + Удаляем старые точки разом вместо поштучного удаления
                            points_to_keep = []
                            for j in range(1, series.count()):
                                point = series.at(j)
                                # Сдвигаем X-координаты
                                points_to_keep.append(QPointF(j-1, point.y()))

                            series.clear()
                            series.append(points_to_keep)

                        # Add new point
                        series.append(series.count(), value[i])
                        data_values.append(value[i])

                    # + Обновляем историю данных для автомасштабирования
                    history = self.data_history.get(name, [])
                    history.extend(data_values)
                    # Ограничиваем количество сохраненных точек
                    max_history = max_points * 3  # Храним максимум в 3 раза больше точек чем отображаем
                    if len(history) > max_history:
                        history = history[-max_history:]
                    self.data_history[name] = history

                    # Auto-scale Y axis based on all three values
                    self.auto_scale_y_axis(name, data_values)

            else:
                # Single-value data
                series = chart_data["series"]

                if isinstance(value, (int, float)):
                    if series.count() >= max_points:
                        # + Оптимизация: вместо поштучного обновления точек
                        points_to_keep = []
                        for j in range(1, series.count()):
                            point = series.at(j)
                            # Сдвигаем X-координаты
                            points_to_keep.append(QPointF(j-1, point.y()))

                        series.clear()
                        series.append(points_to_keep)

                    # Add new point
                    series.append(series.count(), value)

                    # + Обновляем историю данных
                    history = self.data_history.get(name, [])
                    history.append(value)
                    # Ограничиваем количество сохраненных точек
                    if len(history) > max_points * 3:
                        history = history[-max_points*3:]
                    self.data_history[name] = history

                    # Auto-scale Y axis based on current value
                    self.auto_scale_y_axis(name, [value])

            # Update index
            self.indexes[name] = index + 1

            # Update X axis to always show the latest points
            visible_points = min(max_points, series.count() if not chart_data.get("multi_axis") else series_list[0].count())
            if visible_points > 0:
                # + Устанавливаем диапазон X с небольшим отступом справа
                x_axis.setRange(0, visible_points + 5)  # +5 для небольшого отступа справа

            # + Разрешаем обновления после всех изменений
            chart_view.setUpdatesEnabled(True)

            # + Обновляем только по необходимости
            chart_data["view"].update()
import numpy as np
def load_mesh_obj(filename: str, max_faces: int = 1000) -> MeshData:
    """
    Загружает Wavefront OBJ файл и возвращает MeshData.
    Делает триангуляцию и динамическое упрощение до max_faces треугольников.
    """
    verts = []
    faces = []

    with open(filename, 'r') as f:
        for line in f:
            if line.startswith('v '):
                parts = line.strip().split()[1:]
                verts.append(tuple(map(float, parts)))
            elif line.startswith('f '):
                parts = line.strip().split()[1:]
                idx = [int(p.split('/')[0]) - 1 for p in parts]
                # Триангуляция (fan)
                if len(idx) == 3:
                    faces.append(idx)
                else:
                    for i in range(1, len(idx) - 1):
                        faces.append([idx[0], idx[i], idx[i + 1]])

    # Конвертация в numpy
    vert_array = np.array(verts, dtype=np.float32)
    face_array = np.array(faces, dtype=np.int32)

    # --- Оптимизация: если граней слишком много, уменьшаем до max_faces ---
    total = face_array.shape[0]
    if total > max_faces:
        step = math.ceil(total / max_faces)
        face_array = face_array[::step]

    return MeshData(vertexes=vert_array, faces=face_array)

# Отключаем мыш. управление
class NoMouseView(gl.GLViewWidget):
    def mousePressEvent(self, ev): pass
    def mouseMoveEvent(self, ev):  pass
    def wheelEvent(self, ev):      pass
    def keyPressEvent(self, event):
        # Полностью игнорируем события нажатия клавиш
        event.ignore()

# === Асинхронная загрузка 3D‑модели в отдельном потоке ===
class ModelLoader(QThread):
    loaded = Signal(object)  # отдаст MeshData

    def __init__(self, obj_file: str, max_faces: int = 20000):
        super().__init__()
        self.obj_file = obj_file
        self.max_faces = max_faces

    def run(self):
        mesh = load_mesh_obj(self.obj_file, max_faces=self.max_faces)
        self.loaded.emit(mesh)


class TestPage(QWidget):
    """Вкладка Test: 3D-модель из OBJ, плавно поворачивается на 120 FPS, без мерцания граней и ребер."""
    def __init__(self, obj_file: str):
        super().__init__()
        layout = QVBoxLayout(self)

        # Виджет 3D и метка FPS
        self.view = NoMouseView()
        self.fps_label = QLabel("FPS: 0")
        self.fps_label.setStyleSheet(
            "color:white; font-size:10px; background-color:rgba(0,0,0,100);"
            "padding:2px 4px; border-radius:3px;"
        )

        self.obj_file = obj_file
        self._loaded = False

        def keyPressEvent(self, event):
            # Игнорируем нажатия клавиш в TestPage
            event.ignore()

        self.fps_label.setFixedSize(50,16)
        layout.addWidget(self.fps_label)
        self.view.setCameraPosition(distance=10)
        self.view.setBackgroundColor(pg.mkColor(36, 36, 36))
        layout.addWidget(self.view)

        # Загружаем OBJ-модель
        meshdata = load_mesh_obj(obj_file, max_faces=20000)

        # 1) Грани модели: ровный белый цвет, без ребер
        self.face_mesh = GLMeshItem(
            meshdata=meshdata,
            smooth=True,
            drawFaces=True,
            drawEdges=False,
            faceColor=(0.2, 0.4, 0.8, 1.0),
            shader='shaded'
        )
        self.view.addItem(self.face_mesh)
        self.face_mesh.setGLOptions('opaque')

        # 2) Рёбра: рисуем поверх граней
        self.edge_mesh = GLMeshItem(
            meshdata=meshdata,
            smooth=False,
            drawFaces=False,
            drawEdges=True,
            edgeColor=(1.0,1.0,1.0,1.0)
        )
        self.edge_mesh.setGLOptions('additive')
        self.view.addItem(self.edge_mesh)

        self._adjust_camera(meshdata)

        # Создаем оси координат для ориентации
        axis_length = 5.0  # Длина осей
        axis_x = gl.GLLinePlotItem(pos=np.array([[0,0,0], [axis_length,0,0]]), color=(1,0,0,1), width=2)
        axis_y = gl.GLLinePlotItem(pos=np.array([[0,0,0], [0,axis_length,0]]), color=(0,1,0,1), width=2)
        axis_z = gl.GLLinePlotItem(pos=np.array([[0,0,0], [0,0,axis_length]]), color=(0,0,1,1), width=2)

        # Добавляем подписи к осям

        # Добавляем элементы в сцену
        # Добавляем их в виджет
        self.view.addItem(axis_x)
        self.view.addItem(axis_y)
        self.view.addItem(axis_z)

        # Сетка для привязки
        grid_size = 10  # Размер сетки
        grid_item = gl.GLGridItem(size=QVector3D(grid_size, grid_size, 1))
        grid_item.setColor((0.5, 0.5, 0.5, 0.3))  # Полупрозрачный серый
        self.view.addItem(grid_item)

        # Добавляем индикаторы текущей ориентации
        self.orientation_label = QLabel("Ориентация: 0.0, 0.0, 0.0")
        self.orientation_label.setStyleSheet(
            "color:white; font-size:10px; background-color:rgba(0,0,0,100);"
            "padding:2px 4px; border-radius:3px;"
        )
        self.orientation_label.setFixedSize(200, 16)
        layout.addWidget(self.orientation_label)

        # Последние показания акселерометра
                # +++ Sensor fusion init +++
        self.accel = [0.0, 0.0, 0.0]           # последнее значение акселя
        self.gyro  = [0.0, 0.0, 0.0]           # последнее значение гиры
        self.roll = self.pitch = self.yaw = 0.0  # отфильтрованные углы (рад)
        self.last_update = time.time()         # метка времени предыдущего кадра
        self.alpha = 0.98                      # коэффициент комплементарного фильтра
        self.frame_count = 0
        self.last_fps_time = time.time()

        # Запускаем таймер на ~120 FPS
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_frame)
        self.timer.start(12)

        # === AHRS Madgwick + LPF accel ===
        self.q = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)  # кватернион
        self.beta = 0.1     # константа Madgwick (0.1…0.5, чем меньше — тем плавнее)
        self.last_update = time.time()

        # LPF для акселя
        self.accel_lpf = np.array([0.0, 0.0, 0.0], dtype=np.float64)
        self.lpf_alpha = 0.5  # 0.0 — без фильтра, 1.0 — полностью старые данные

        # Добавляем маркеры ориентации на модель
        # Добавьте это в метод __init__ класса TestPage после создания edge_mesh:
        # Маркер "нос" модели - красная точка (исправлено на −1 по X)
        nose_point = gl.GLScatterPlotItem(pos=np.array([[-1, 0, 0]]), color=(1,0,0,1), size=10)
        self.view.addItem(nose_point)

        # Маркер "верх" модели - зеленая точка
        top_point = gl.GLScatterPlotItem(pos=np.array([[0, 1, 0]]), color=(0,1,0,1), size=10)
        self.view.addItem(top_point)

        # Маркеры будут поворачиваться вместе с моделью
        self.markers = [nose_point, top_point]

        # === Начальная коррекция ориентации модели ===
        # 1) Выравниваем «вверх/вниз» (модель лежала на боку)
        # 2) Переворачиваем лицом к +X
        for mesh in (self.face_mesh, self.edge_mesh):
            mesh.rotate(-90, 1, 0, 0)   # повернуть вокруг X
            mesh.rotate(180, 0, 1, 0)   # развернуть вокруг Y
            # Если нужно подкрутить «вокруг Z», раскомментируй и поэкспериментируй:
            # mesh.rotate(90, 0, 0, 1)

        # Подправляем позицию маркера «нос» на +X
        nose_point.setData(pos=np.array([[1, 0, 0]]), size=10)

        # Коэффициент сглаживания итоговых углов (0=резко, 1=медленно)
        self.angle_alpha = 0.95
        self.smoothed    = {"roll": 0.0, "pitch": 0.0, "yaw": 0.0}

    @Slot(dict)
    def update_orientation(self, data):
        # Сохраняем сырые данные
        ax, ay, az = data.get('accel', [0.0, 0.0, 0.0])
        gx, gy, gz = data.get('gyro',  [0.0, 0.0, 0.0])
        # Перевод gyro → рад/с (если у тебя в deg/s, умножить на π/180)
        self.gyro = np.array([num * 3.14 / 180 for num in [gx, gy, gz]], dtype=np.float64)
        self.accel = np.array([ax, ay, az], dtype=np.float64)

    # +++ Добавляем новый метод для подстройки камеры +++

    def madgwick_update(self, gx, gy, gz, ax, ay, az, dt):
        """
        Обновление кватерниона по алгоритму Madgwick.
        gx,gy,gz в рад/с; ax,ay,az в g; dt в сек.
        """
        import math

        # 1) LPF на аксель
        raw = np.array([ax, ay, az], dtype=np.float64)
        self.accel_lpf = self.lpf_alpha * self.accel_lpf + (1 - self.lpf_alpha) * raw
        ax, ay, az = self.accel_lpf

        # 2) нормируем аксель
        norm = math.sqrt(ax*ax + ay*ay + az*az)
        if norm == 0:
            return
        ax, ay, az = ax/norm, ay/norm, az/norm

        # 3) текущий кватернион
        w, x, y, z = self.q

        # 4) вычисляем градиент коррекции (обратно Madgwick paper)
        f1 = 2*(x*z - w*y) - ax
        f2 = 2*(w*x + y*z) - ay
        f3 = 2*(w*w - x*x - y*y + z*z) - az
        J_11or24 = 2*y
        J_12or23 = 2*z
        J_13or22 = 2*w
        J_14or21 = 2*x
        J_32 = 2*J_14or21
        J_33 = 2*J_11or24

        # градиент
        grad = np.array([
            J_14or21 * f2 - J_11or24 * f1,
            J_12or23 * f1 + J_13or22 * f2 - J_32 * f3,
            J_12or23 * f2 - J_33 * f3 - J_13or22 * f1,
            J_14or21 * f1 + J_11or24 * f2
        ], dtype=np.float64)

        # нормируем градиент
        grad_norm = np.linalg.norm(grad)
        if grad_norm != 0:
            grad /= grad_norm

        # 5) интегрируем производную кватерниона
        qDot = 0.5 * np.array([
            -x*gx - y*gy - z*gz,
             w*gx + y*gz - z*gy,
             w*gy - x*gz + z*gx,
             w*gz + x*gy - y*gx
        ], dtype=np.float64) - self.beta * grad

        w += qDot[0] * dt
        x += qDot[1] * dt
        y += qDot[2] * dt
        z += qDot[3] * dt

        # 6) нормируем кватернион
        q_norm = math.sqrt(w*w + x*x + y*y + z*z)
        self.q = np.array([w/q_norm, x/q_norm, y/q_norm, z/q_norm], dtype=np.float64)

    def _adjust_camera(self, meshdata):
        # Получаем все вершины модели
        vertices = meshdata.vertexes()

        # Находим минимальные и максимальные координаты модели по всем осям
        min_coords = vertices.min(axis=0)
        max_coords = vertices.max(axis=0)

        # Центр модели
        center = (min_coords + max_coords) / 2

        # Размер модели — дистанция между минимальной и максимальной точками
        size = np.linalg.norm(max_coords - min_coords)

        # Настройка центра и размера
        self.view.opts['center'] = pg.Vector(center[0], center[1], center[2])

        # Устанавливаем камеру на достаточное расстояние от модели, чтобы она полностью влезла в кадр
        self.view.opts['distance'] = size * 2.5  # Можно уменьшить или увеличить множитель для корректировки видимости
    # --- Конец вставки новых строк ---

    # --- + новый метод для сброса ориентации ---
    def reset_orientation(self):
        """Сбросить модель в начальное положение."""
        self.roll = self.pitch = self.yaw = 0.0
        for mesh in (self.face_mesh, self.edge_mesh):
            mesh.resetTransform()
        self.orientation_label.setText("Ориентация: R:0.0° P:0.0° Y:0.0°")

    def _on_frame(self):
        import math
        now = time.time()
        dt = now - self.last_update if self.last_update else 0.016
        self.last_update = now

        # обновляем кватернион через Madgwick
        self.madgwick_update(
            self.gyro[0], self.gyro[1], self.gyro[2],
            self.accel[0], self.accel[1], self.accel[2],
            dt
        )

        # извлекаем Эйлеровы углы из q
        w, x, y, z = self.q
        roll  = math.atan2(2*(w*x + y*z),    w*w - x*x - y*y + z*z)
        pitch = math.asin(  max(-1.0, min(1.0, 2*(w*y - z*x))) )
        yaw   = math.atan2(2*(w*z + x*y),    w*w + x*x - y*y - z*z)

        # Перевод в градусы
        r_deg = math.degrees(roll)
        p_deg = math.degrees(pitch)
        y_deg = math.degrees(yaw)

        # Фильтруем мелкие колебания (<0.5°)
        threshold = 2
        if abs(r_deg) < threshold: r_deg = 0
        if abs(p_deg) < threshold: p_deg = 0
        if abs(y_deg) < threshold: y_deg = 0

        # --- Сглаживаем углы ---
        self.smoothed["roll"]  = self.smoothed["roll"]  * self.angle_alpha + r_deg  * (1 - self.angle_alpha)
        self.smoothed["pitch"] = self.smoothed["pitch"] * self.angle_alpha + p_deg  * (1 - self.angle_alpha)
        self.smoothed["yaw"]   = self.smoothed["yaw"]   * self.angle_alpha + y_deg  * (1 - self.angle_alpha)

        # === Применяем только динамические сглаженные углы ===
        for mesh in (self.face_mesh, self.edge_mesh):
            mesh.resetTransform()  # сбросим предыдущие динамические повороты
            mesh.rotate(-self.smoothed["yaw"],   0, 0, 1)
            mesh.rotate( self.smoothed["pitch"], 0, 1, 0)
            mesh.rotate(-self.smoothed["roll"],  1, 0, 0)

        # Вращаем маркеры вместе с моделью (с тем же оффсетом)
        # === Аналогично обновляем маркеры ===
        for marker in self.markers:
            marker.resetTransform()
            marker.rotate( self.smoothed["yaw"],   0, 0, 1)
            marker.rotate( self.smoothed["pitch"], 0, 1, 0)
            marker.rotate( self.smoothed["roll"],  1, 0, 0)

        # Обновляем надпись с ориентацией
        self.orientation_label.setText(f"R:{r_deg:.1f}° P:{p_deg:.1f}° Y:{y_deg:.1f}°")

        # Считаем FPS
        self.frame_count += 1
        now = time.time()
        if now - self.last_fps_time >= 1.0:
            fps = self.frame_count / (now - self.last_fps_time)
            self.fps_label.setText(f"FPS: {fps:.1f}")
            self.frame_count = 0
            self.last_fps_time = now

        # Обновляем вид
        self.view.update()

# === СТРАНИЦА ЛОГОВ + ЭКСПОРТ В ZIP ===
class LogPage(QWidget):
    def __init__(self):
        super().__init__()
        auto_save_timer: QTimer = None
        self.error_list: list[str] = []
        layout = QVBoxLayout(self); layout.setContentsMargins(15,15,15,15)
        header = QLabel("Системный журнал")
        header.setStyleSheet(f"""
            font-size: 16pt; font-weight: bold; color: {COLORS['text_primary']}; margin-bottom:10px
        """)
        self.log_text = QTextEdit(); self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas",10))
        self.log_text.setStyleSheet(f"""
            QTextEdit {{ background: {COLORS['bg_dark']}; color: {COLORS['text_primary']};
            border-radius:6px; padding:10px; border:none }}
        """)
        buttons_layout = QHBoxLayout()
        self.clear_btn = QPushButton("Очистить лог")
        self.save_btn = QPushButton("Сохранить лог")
        self.export_btn = QPushButton("Экспорт ZIP")
        for btn in (self.clear_btn, self.save_btn, self.export_btn):
            btn.setFixedHeight(40)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['bg_panel']};
                    color: {COLORS['text_primary']};
                    border-radius:8px; font-size:11pt; padding:0 20px;
                }}
                QPushButton:hover {{ background-color: {COLORS['accent_darker']}; }}
                QPushButton:pressed {{ background-color: {COLORS['accent']}; }}
            """)
        self.clear_btn.clicked.connect(self.clear_log)
        self.save_btn.clicked.connect(self.save_log)
        self.export_btn.clicked.connect(self.export_logs)
        # авто-сохранение
        self.auto_save_timer = QTimer(self)
        self.auto_save_timer.timeout.connect(self._on_auto_save)
        buttons_layout.addWidget(self.clear_btn)
        buttons_layout.addWidget(self.save_btn)
        buttons_layout.addWidget(self.export_btn)
        buttons_layout.addStretch()
        layout.addWidget(header); layout.addWidget(self.log_text); layout.addLayout(buttons_layout)

    @Slot(str)
    def configure_auto_save(self, enabled: bool, interval_min: int):
        if self.auto_save_timer.isActive():
            self.auto_save_timer.stop()
        if enabled:
            self.auto_save_timer.start(interval_min * 60 * 1000)

    @Slot()
    def _on_auto_save(self):
        # пометим, что это автосохранение
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.add_log_message(f"[AUTO] Автосохранение логов: {ts}")
        self.save_log()

    @Slot(str)
    def add_log_message(self, message):
        # Определяем уровень
        level = "info"
        if message.startswith("[ERROR]") or message.startswith("ERROR"):
            level = "danger"
        elif message.startswith("[WARNING]") or message.startswith("WARNING"):
            level = "warning"

        # Сохраняем WARN/ERROR в список
        if level in ("warning", "danger"):
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.error_list.append(f"{ts} {message}")

        # HTML-раскраска
        color_map = {
            "info":    COLORS["text_secondary"],
            "warning": COLORS["warning"],
            "danger":  COLORS["danger"],
        }
        color = color_map[level]
        # QTextEdit.append поддерживает HTML
        self.log_text.append(f'<span style="color:{color};">{message}</span>')

        # Скроллим вниз
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def clear_log(self):
        self.log_text.clear()

    def save_log(self):
        now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = f"log/system_log_{now}.txt"
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.log_text.toPlainText())
            self.add_log_message(f"[{datetime.datetime.now()}] Лог сохранен в {path}")
        except Exception as e:
            self.add_log_message(f"[ERROR] Не удалось сохранить лог: {e}")

    def export_logs(self):
            # Запускаем фоновый поток для архивации
            self.add_log_message(f"[{datetime.datetime.now()}] Запуск экспорта ZIP...")
            self._export_thread = ExportLogsThread(log_dir="log")
            self._export_thread.finished.connect(self._on_export_finished)
            self._export_thread.start()

    @Slot(str, bool, str)
    def _on_export_finished(self, archive: str, success: bool, error: str):
        if success:
            self.add_log_message(f"[{datetime.datetime.now()}] Логи экспортированы в {archive}")
        else:
            self.add_log_message(f"[ERROR] Экспорт ZIP не удался: {error}")

    def get_errors(self) -> list[str]:
        """Вернуть все WARN/ERROR сообщения."""
        return self.error_list

# === СТРАНИЦА НАСТРОЕК + .ini ===
class SettingsPage(QWidget):
    settings_changed      = Signal(bool, str, int)
    simulator_changed     = Signal(bool, str)

    def __init__(self):
        super().__init__()
        self.cfg = configparser.ConfigParser()
        if os.path.isfile("config.ini"):
            self.cfg.read("config.ini")

        # --- Read saved settings ---
        udp_enabled  = self.cfg.get("UDP", "enabled", fallback="False") == "True"
        host         = self.cfg.get("UDP", "host",    fallback="127.0.0.1")
        port         = self.cfg.getint("UDP", "port", fallback=5005)
        sim_enabled  = self.cfg.get("Settings", "simulation",    fallback="False") == "True"
        auto_save    = self.cfg.getboolean("Settings", "auto_save",            fallback=False)
        auto_interval= self.cfg.getint    ("Settings", "auto_save_interval",  fallback=5)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        header = QLabel("Настройки")
        header.setStyleSheet(f"""
            font-size:18pt; font-weight:bold; color:{COLORS['text_primary']};
            margin-bottom:20px
        """)
        layout.addWidget(header)

        # --- UDP settings ---
        udp_card = QFrame()
        udp_card.setObjectName("card")
        v = QVBoxLayout(udp_card)
        lab = QLabel("<b>UDP настройки</b>")
        lab.setStyleSheet("font-size:14pt;")
        self.udp_enable = QCheckBox("Включить UDP отправку")
        self.udp_enable.setChecked(udp_enabled)
        self.udp_ip     = QLineEdit(host)
        self.udp_ip.setPlaceholderText("IP адрес")
        self.udp_port   = QLineEdit(str(port))
        self.udp_port.setPlaceholderText("Порт")
        for w in (lab, self.udp_enable, self.udp_ip, self.udp_port):
            v.addWidget(w)
        layout.addWidget(udp_card)

        # --- Simulation from file ---
        sim_card = QFrame()
        sim_card.setObjectName("card")
        v2 = QVBoxLayout(sim_card)
        lab2 = QLabel("<b>Имитация из файла</b>")
        self.sim_enable    = QCheckBox("Включить имитацию")
        self.sim_enable.setChecked(sim_enabled)
        self.sim_file_path = QLineEdit()
        self.sim_file_path.setPlaceholderText("Путь к бинарному лог-файлу")
        self.sim_file_path.setReadOnly(True)
        btn_browse = QPushButton("Выбрать файл")
        btn_browse.clicked.connect(self.browse_sim_file)
        v2.addWidget(lab2)
        v2.addWidget(self.sim_enable)
        hl = QHBoxLayout()
        hl.addWidget(self.sim_file_path)
        hl.addWidget(btn_browse)
        v2.addLayout(hl)
        layout.addWidget(sim_card)

        # Disable simulation block when UDP is on
        # Когда включаем UDP — выключаем симуляцию, и наоборот
        self.udp_enable.stateChanged.connect(lambda state: (
            # если UDP включили — убираем галочку и блокируем симуляцию
            self.sim_enable.setChecked(False) if state else None,
            self.sim_enable.setEnabled(not state),
            self.sim_file_path.setEnabled(not state),
            btn_browse.setEnabled(not state)
        ))
        self.sim_enable.stateChanged.connect(lambda state: (
            # если симуляцию включили — убираем галочку и блокируем UDP
            self.udp_enable.setChecked(False) if state else None,
            self.udp_enable.setEnabled(not state),
            self.udp_ip.setEnabled(not state),
            self.udp_port.setEnabled(not state)
        ))
        # initial enable/disable
        self.sim_enable.setEnabled(not udp_enabled)
        self.sim_file_path.setEnabled(not udp_enabled)
        btn_browse.setEnabled(not udp_enabled)

        # --- Save button ---
        self.save_btn = QPushButton("Сохранить настройки")
        self.save_btn.setFixedHeight(40)
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS["bg_panel"]};
                color:{COLORS['text_primary']};
                border-radius:6px; font-size:11pt;
                padding:0 20px
            }}
            QPushButton:hover {{ background: {COLORS["accent_darker"]}; }}
            QPushButton:pressed {{ background: {COLORS["accent"]}; }}
        """)
        self.save_btn.clicked.connect(self.save_settings)
        layout.addWidget(self.save_btn)
        # --- Auto-save logs every N minutes ---
        # wrap into card
        auto_card = QFrame()
        auto_card.setObjectName("card")
        v_auto = QVBoxLayout(auto_card)
        self.auto_save_chk = QCheckBox("Автосохранение логов каждые N минут")
        self.auto_save_spin = QSpinBox()
        self.auto_save_spin.setRange(1, 60)
        self.auto_save_chk.setChecked(auto_save)
        self.auto_save_spin.setValue(auto_interval)
        h = QHBoxLayout()
        h.addWidget(self.auto_save_chk)
        h.addWidget(self.auto_save_spin)
        v_auto.addLayout(h)
        layout.addWidget(auto_card)
        # --- Reset graph layout ---
        self.reset_layout_btn = QPushButton("Сбросить расположение графиков")
        self.reset_layout_btn.setObjectName("resetLayoutBtn")
        self.reset_layout_btn.setFixedHeight(30)
        self.reset_layout_btn.clicked.connect(self._reset_graph_layout)
        # wrap reset button into its own card
        reset_card = QFrame()
        reset_card.setObjectName("card")
        v_reset = QVBoxLayout(reset_card)
        v_reset.addWidget(self.reset_layout_btn, alignment=Qt.AlignCenter)
        layout.addWidget(reset_card)
        layout.addStretch()
    def save_settings(self):
        # UDP section
        self.cfg["UDP"] = {
            "enabled": str(self.udp_enable.isChecked()),
            "host":    self.udp_ip.text(),
            "port":    self.udp_port.text()
        }
        # Settings section (simulation)
        if "Settings" not in self.cfg:
            self.cfg["Settings"] = {}
        self.cfg["Settings"]["simulation"]    = str(self.sim_enable.isChecked())

        # store auto-save into cfg
        self.cfg["Settings"]["auto_save"] = str(self.auto_save_chk.isChecked())
        self.cfg["Settings"]["auto_save_interval"] = str(self.auto_save_spin.value())
        # Write to file
        with open("config.ini", "w") as f:
            self.cfg.write(f)
        # store auto-save
        self.cfg["Settings"]["auto_save"] = str(self.auto_save_chk.isChecked())
        self.cfg["Settings"]["auto_save_interval"] = str(self.auto_save_spin.value())

        # Emit signals
        self.settings_changed.emit(
            self.udp_enable.isChecked(),
            self.udp_ip.text(),
            int(self.udp_port.text() or 0)
        )
        self.simulator_changed.emit(
            self.sim_enable.isChecked(),
            self.sim_file_path.text()
        )
    def browse_sim_file(self):
        """Открыть диалог выбора бинарного файла для симуляции."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выбрать бинарный файл",
            "",
            "Binary files (*.bin);;All files (*)"
        )
        if path:
            self.sim_file_path.setText(path)

    def _reset_graph_layout(self):
        """Сбросить сохранённый порядок графиков."""
        import configparser
        from PySide6.QtWidgets import QMessageBox

        cfg = configparser.ConfigParser()
        cfg.read("config.ini")
        if cfg.has_section("Layout") and cfg.has_option("Layout", "graph_order"):
            cfg.remove_option("Layout", "graph_order")
            with open("config.ini", "w") as f:
                cfg.write(f)
        QMessageBox.information(self, "Сброс",
                                "Порядок графиков сброшен. Перезапустите приложение.")

class ConsolePage(QWidget):
    """Простейшая консоль для команд TelemetryWorker."""
    def __init__(self):
        super().__init__()
        self.setLayout(QVBoxLayout())
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Введите команду и Enter…")
        self.layout().addWidget(self.output)
        self.layout().addWidget(self.input)
        self.input.returnPressed.connect(self._on_enter)

    def _on_enter(self):
        cmd = self.input.text().strip()
        if not cmd:
            return
        # отобразить в консоли
        self.output.append(f"> {cmd}")
        # послать сигнал
        self.command_entered.emit(cmd)
        self.input.clear()

    # сигнал команд
    command_entered = Signal(str)

    def write_response(self, text: str):
        self.output.append(text)


# === ГЛАВНОЕ ОКНО ===
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Telemetry Dashboard")
        self.resize(1200, 700)
        apply_dark_theme(QApplication.instance())

        # Pages
        self.tel      = TelemetryPage()
        self.graphs   = GraphsPage()
        self.log_page = LogPage()
        self.settings = SettingsPage()
        self.console  = ConsolePage()
        self.test     = TestPage("models/grib.obj")

        # Layout: sidebar + content
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        sidebar = QWidget()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet(f"background-color: {COLORS['bg_main']};")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(15, 30, 15, 20)
        sidebar_layout.setSpacing(10)

        menu_items = [
            {"name": "Telemetry", "icon": "📊", "index": 0},
            {"name": "Graphs",    "icon": "📈", "index": 1},
            {"name": "Logs",      "icon": "📝", "index": 2},
            {"name": "Settings",  "icon": "⚙️", "index": 3},
            {"name": "Console",   "icon": "💻", "index": 4},
            {"name": "Test",      "icon": "🧪", "index": 5}
        ]
        self.nav_buttons = []
        for item in menu_items:
            btn = QPushButton(f" {item['icon']} {item['name']}")
            btn.setProperty("index", item["index"])
            btn.setCheckable(True)
            btn.setStyleSheet(f"""
                QPushButton {{
                    text-align: left;
                    padding: 12px 15px;
                    border-radius: 8px;
                    color: {COLORS['text_primary']};
                    background: transparent;
                    font-size: 14px;
                }}
                QPushButton:hover {{
                    background: {COLORS['accent_darker']};
                    color: {COLORS['text_primary']};
                }}
                QPushButton:checked {{
                    background: {COLORS['accent']};
                    color: white;
                    font-weight: bold;
                }}
            """)
            btn.clicked.connect(lambda _, idx=item["index"], b=btn: self.on_nav_click(idx, b))
            self.nav_buttons.append(btn)
            sidebar_layout.addWidget(btn)

        self.nav_buttons[0].setChecked(True)
        sidebar_layout.addStretch()
        main_layout.addWidget(sidebar)

        # Content
        content_area   = QWidget()
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(20, 20, 20, 20)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background: {COLORS['bg_main']};")
        for page in (self.tel, self.graphs, self.log_page, self.settings, self.console, self.test):
            self.stack.addWidget(page)
        content_layout.addWidget(self.stack)
        main_layout.addWidget(content_area)

        self.setCentralWidget(main_widget)

        # Telemetry worker
        self.worker = TelemetryWorker("COM3", 9600)

        # Буфер пакетов и таймер для отложенного UI-обновления
        self.packet_buffer = deque()
        self.ui_timer      = QTimer(self)
        self.ui_timer.timeout.connect(self.flush_buffered_packets)
        self.ui_timer.start(50)  # обновлять UI не чаще чем раз в 50 ms

        self.worker.sim_ended.connect(self.test.reset_orientation)

        self.tel.set_worker(self.worker)
        self.worker.data_ready.connect(self.packet_buffer.append)
        self.worker.log_ready.connect(self.log_page.add_log_message)
        self.worker.error_crc.connect(QApplication.beep)

        # Сначала сохраняем настройки, без подключённых слотов — чтобы не было всплывашек на старте
        self.settings.save_settings()
        # Теперь подключаем обработчики сигналов
        self.settings.settings_changed.connect(self.worker.update_udp)
        self.settings.simulator_changed.connect(self.on_simulator_changed)
        # автосохранение логов
        self.settings.save_settings()  # чтобы cfg обновился
        self.log_page.configure_auto_save(
            self.settings.auto_save_chk.isChecked(),
            self.settings.auto_save_spin.value()
        )
        self.settings.auto_save_chk.stateChanged.connect(
            lambda s: self.log_page.configure_auto_save(
                bool(s), self.settings.auto_save_spin.value()
            )
        )
        self.settings.auto_save_spin.valueChanged.connect(
            lambda v: self.log_page.configure_auto_save(
                self.settings.auto_save_chk.isChecked(), v
            )
        )

        # Start
        self.worker.start()
        # Чтобы на старте и при сохранении настроек не вылезали уведомления:
        self.settings.save_settings()
        self.console.command_entered.connect(self._handle_console_command)

    def eventFilter(self, obj, ev):
            if ev.type() == QEvent.Enter:
                # нашли какой ключ за этим card
                for key, lbl in self.cards.items():
                    if lbl.parent() is obj:
                        val = self._last_values.get(key, None)
                        ts  = self._last_values.get("timestamp", "")
                        QToolTip.showText(QCursor.pos(), f"{key}\nraw: {val}\n ts: {ts}")
                        break
            return super().eventFilter(obj, ev)

    def on_nav_click(self, idx, btn):
        for b in self.nav_buttons:
            b.setChecked(False)
        btn.setChecked(True)
        self.stack.setCurrentIndex(idx)

    def on_simulator_changed(self, enabled: bool, filepath: str):
        self.worker.sim_enabled = enabled
        if enabled:
            try:
                self.worker.sim_f = open(filepath, "rb")
            except Exception as e:
                print(f"[Ошибка открытия файла симуляции]: {e}")
                self.worker.sim_enabled = False
        self.test.reset_orientation()

    def closeEvent(self, event):
        # save graph layout
        try:
            self.graphs.save_layout()
        except Exception:
            pass
        self.worker.stop()
        self.worker.wait(1000)
        super().closeEvent(event)

    def flush_buffered_packets(self):
        # Берём только самый свежий пакет и сбрасываем устаревшие
        if self.packet_buffer:
            data = self.packet_buffer.pop()
            self.packet_buffer.clear()
            self.tel.update_values(data)
            self.graphs.update_charts(data)
            self.test.update_orientation(data)
    @Slot(str)
    def _handle_console_command(self, cmd: str):
        import time
        cmd = cmd.lower()
        # help
        if cmd in ("help", "?"):
            cmds = ["pause", "resume", "version", "help"]
            self.console.write_response("Commands: " + ", ".join(cmds))
            return

        # version
        if cmd == "version":
            self.console.write_response("Grib Telemetry Dashboard v1.9.0 — program 'grib'")
            return

        # pause/resume without data-check
        if cmd in ("pause", "resume"):
            if cmd == "pause":
                self.worker.pause()
                self.log_page.add_log_message("[INFO] Telemetry paused via console")
                self.console.write_response("OK: paused")
            else:
                self.worker.resume()
                self.console.write_response("OK: resumed")
            return

        # show errors/warnings from log
        if cmd in ("errors", "show errors", "warnings"):
            errs = self.log_page.get_errors()
            if not errs:
                self.console.write_response("No warnings or errors.")
            for e in errs:
                self.console.write_response(e)
            return

        self.console.write_response(f"Unknown command: {cmd}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
