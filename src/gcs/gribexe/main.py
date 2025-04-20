import sys, struct, math, datetime, os, socket, configparser, zipfile, time
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFrame,
    QGridLayout, QSplitter, QSizePolicy, QTextEdit, QLineEdit,
    QCheckBox, QFileDialog, QScrollArea
)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QUrl, QPointF, QTimer
from PySide6.QtGui import QPalette, QColor, QPixmap, QFont, QPainter, QPen
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis

import pyqtgraph as pg
import pyqtgraph.opengl as gl
from pyqtgraph.opengl import MeshData, GLMeshItem

from OpenGL.GL import (
    GL_POLYGON_OFFSET_FILL,
    glEnable, glPolygonOffset, glDisable
)

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
    "accent": "#4fc3f7",          # Main accent color (light blue like in image)
    "accent_darker": "#2196f3",   # Darker accent for hover
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
    "chart_bg": "#1e1e1e"         # Chart background (slightly lighter than dark bg)
}

# === WORKER ДЛЯ UART + UDP + ЛОГОВ + CRC-ОШИБОК ===
class TelemetryWorker(QThread):
    data_ready    = Signal(dict)
    packet_ready  = Signal(list)
    log_ready     = Signal(str)
    error_crc     = Signal()
    def __init__(self, port_name="COM3", baud=9600, parent=None):
        super().__init__(parent)
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
        self.log_ready.emit("Telemetry thread started. Version 1.5.0")
        self.log_ready.emit("Надёжная версия: 1.2.2")

        while self._running:
            try:
                if self.sim_enabled and not self.udp_enabled:
                    # Режим симуляции
                    rcv = self.sim_f.read(60)
                    if not rcv:
                        self.log_ready.emit("[SIM] End of file reached")
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
            card.setStyleSheet(f"""
                QFrame {{
                    background: {COLORS["bg_card"]};
                    border-radius: 6px;
                    padding: 8px;
                }}
                QLabel#title {{
                    color: {COLORS["text_secondary"]};
                    font-size: 9pt;
                }}
                QLabel#value {{
                    color: {COLORS["text_primary"]};
                    font-size: 13pt;
                    font-weight: bold;
                }}
            """)
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
        if not self.pause_btn.isEnabled():
            self.pause_btn.setEnabled(True)
        for k, w in self.cards.items():
            if k in data:
                v = data[k]
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
        self.data_history = {}  # + Хранить историю значений для лучшего масштабирования

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

        # Create charts
        row, col = 0, 0
        columns = 2  # Теперь две колонки вместо трех
        for config in chart_configs:
            chart_view = self.create_chart(config)
            # Компактный минимум и растягиваемость
            chart_view.setMinimumSize(600, 350)
            chart_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            layout.addWidget(chart_view, row, col)
            # Store the max number of points to show
            self.data_points[config["name"]] = 200  # Show more points for better visualization
            # + Инициализировать историю данных
            self.data_history[config["name"]] = []

            # Next position
            col += 1
            if col >= columns:  # 2 columns of charts
                col = 0
                row += 1

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
        chart.setBackgroundBrush(QColor(COLORS["bg_dark"]))
        chart.setTitleBrush(QColor(COLORS["text_primary"]))
        chart.setTitleFont(QFont("Segoe UI", 12, QFont.Bold))
        chart.legend().setVisible(multi_axis)  # Show legend only for multi-axis charts
        chart.legend().setAlignment(Qt.AlignBottom)
        chart.legend().setFont(QFont("Segoe UI", 9))
        chart.legend().setLabelColor(QColor(COLORS["text_primary"]))

        # Axes
        ax_x = QValueAxis()
        ax_x.setLabelFormat("%i")
        ax_x.setTitleText("Точка")
        ax_x.setRange(0, 200)  # Show more points by default
        ax_x.setGridLineVisible(True)
        ax_x.setMinorTickCount(4)

        ax_y = QValueAxis()
        ax_y.setLabelFormat("%.2f")
        ax_y.setRange(y_range[0], y_range[1])
        ax_y.setGridLineVisible(True)
        ax_y.setMinorTickCount(4)

        # Styling axes
        for axis in [ax_x, ax_y]:
            axis.setLabelsColor(QColor(COLORS["text_secondary"]))
            axis.setTitleBrush(QColor(COLORS["text_secondary"]))
            axis.setGridLineColor(QColor(COLORS["chart_grid"]))
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
                pen.setWidthF(2.5)
                series.setPen(pen)
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
        chart_view.setBackgroundBrush(QColor(COLORS["bg_dark"]))
        chart_view.setMinimumHeight(250)  # Set minimum height for better visibility

        # Store the view reference
        self.charts[name]["view"] = chart_view

        return chart_view

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
        if new_min < current_axis_min or new_max > current_axis_max:
            y_axis.setRange(new_min, new_max)
            # обновляем доп. оси в мульти-графиках
            if chart_data.get("multi_axis"):
                chart = chart_data["chart"]
                for i, series in enumerate(chart_data["series"]):
                    if i > 0:
                        for axis in chart.axes(Qt.Vertical, series):
                            axis.setRange(new_min, new_max)
            return

        smooth_factor = 0.2  # Коэффициент сглаживания...
        final_min = current_axis_min + (new_min - current_axis_min) * smooth_factor
        final_max = current_axis_max + (new_max - current_axis_max) * smooth_factor
        # + Плавное изменение масштаба вместо резкого
        current_axis_min = y_axis.min()
        current_axis_max = y_axis.max()

        # + Применяем сглаживание для избежания "прыгающего" масштаба
        smooth_factor = 0.2  # Коэффициент сглаживания (меньше - плавнее, но медленнее)
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

    @Slot(dict)
    def update_charts(self, data):
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
def load_mesh_obj(filename: str) -> MeshData:
    """
    Загружает Wavefront OBJ файл (вершины и грани) и возвращает MeshData.
    Поддерживается триангуляция полигонов.
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
                idx = []
                for p in parts:
                    v = p.split('/')[0]
                    idx.append(int(v) - 1)
                # Триангуляция (fan triangulation)
                if len(idx) == 3:
                    faces.append(idx)
                else:
                    for i in range(1, len(idx) - 1):
                        faces.append([idx[0], idx[i], idx[i + 1]])

    # ❗ Обязательно преобразуем в numpy массивы
    vert_array = np.array(verts, dtype=np.float32)
    face_array = np.array(faces, dtype=np.int32)

    return MeshData(vertexes=vert_array, faces=face_array)



# Отключаем мыш. управление
class NoMouseView(gl.GLViewWidget):
    def mousePressEvent(self, ev): pass
    def mouseMoveEvent(self, ev):  pass
    def wheelEvent(self, ev):      pass


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
        self.fps_label.setFixedSize(50,16)
        layout.addWidget(self.fps_label)
        self.view.setCameraPosition(distance=10)
        self.view.setBackgroundColor(QColor(30,30,30))
        layout.addWidget(self.view)

        # Загружаем OBJ-модель
        meshdata = load_mesh_obj(obj_file)

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

        # Поворот и FPS
        self.roll = self.pitch = self.yaw = 0.0
        self.frame_count = 0
        self.last_fps_time = time.time()

        # Запускаем таймер на ~120 FPS
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_frame)
        self.timer.start(8)

    @Slot(dict)
    def update_orientation(self, data):
        gx, gy, gz = data.get('gyro', [0,0,0])
        dt = 0.05
        self.roll  += gx * dt
        self.pitch += gy * dt
        self.yaw   += gz * dt

    # +++ Добавляем новый метод для подстройки камеры +++
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

    def _on_frame(self):
        # Применяем трансформации ко всем мешам
        for mesh in (self.face_mesh, self.edge_mesh):
            mesh.resetTransform()
            mesh.rotate(self.roll, 1,0,0)
            mesh.rotate(self.pitch,0,1,0)
            mesh.rotate(self.yaw,  0,0,1)

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

# === СТРАНИЦА ДАТЧИКОВ ===
class SensorsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.current_data = {}
        self.telemetry_ok = False
        os.makedirs("sensor_images", exist_ok=True)
        self.descriptions = {
            "BMP280":       "Датчик давления и температуры.",
            "Accelerometer":"Акселерометр: измеряет ускорение по трем осям.",
            "Gyroscope":    "Гироскоп: измеряет угловую скорость.",
            "Magnetometer": "Магнитометр: измеряет магнитное поле.",
            "DS18B20":      "Термометр DS18B20: цифровая температура.",
            "GPS":          "GPS-модуль: координаты и высота."
        }
        splitter = QSplitter(Qt.Horizontal, self)
        left = QFrame(); left.setStyleSheet(f"QFrame {{ background: {COLORS['bg_dark']}; border-radius: 6px }}")
        gl = QGridLayout(left); gl.setContentsMargins(15,15,15,15); gl.setSpacing(10)
        self.sensor_names = list(self.descriptions.keys())
        for i, name in enumerate(self.sensor_names):
            btn = QPushButton(name); btn.setFixedSize(150,60)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS['btn_normal']};
                    color: {COLORS['text_primary']};
                    border-radius: 5px; font-weight: bold;
                }}
                QPushButton:hover {{ background: {COLORS['btn_hover']}; }}
                QPushButton:pressed {{ background: {COLORS['btn_active']}; }}
            """)
            btn.clicked.connect(lambda _, n=name: self.show_sensor(n))
            gl.addWidget(btn, i//2, i%2, Qt.AlignCenter)
        splitter.addWidget(left)
        right = QFrame(); right.setStyleSheet(f"QFrame {{ background: {COLORS['bg_panel']}; border-radius: 6px }}")
        v = QVBoxLayout(right); v.setContentsMargins(20,20,20,20)
        self.img_label = QLabel(); self.img_label.setFixedSize(240,240)
        self.img_label.setAlignment(Qt.AlignCenter); self.img_label.setStyleSheet("background: #353535; border-radius: 8px")
        self.info_label = QLabel("Выберите датчик"); self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet(f"""
            color: {COLORS['text_primary']}; font-size: 12pt;
            padding: 15px; background: {COLORS['bg_card']}; border-radius: 8px
        """)
        v.addWidget(self.img_label, alignment=Qt.AlignCenter); v.addSpacing(15); v.addWidget(self.info_label)
        splitter.addWidget(right); splitter.setStretchFactor(1, 1)
        layout = QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.addWidget(splitter)

    @Slot(dict)
    def update_data(self, data):
        self.current_data = data; self.telemetry_ok = True

    def show_sensor(self, name):
        code = 202 if self.telemetry_ok else 101
        img_path = os.path.join("sensor_images", f"{name}.png")
        if os.path.isfile(img_path):
            pix = QPixmap(img_path).scaled(self.img_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.img_label.setPixmap(pix)
        else:
            self.img_label.setPixmap(QPixmap())
        val_text = ""
        if self.telemetry_ok:
            d = self.current_data
            if name == "BMP280":
                val_text = f"Темп: {d.get('temp_bmp',0):.2f} °C\nДавл.: {d.get('press_bmp',0):.0f} Па"
            elif name == "Accelerometer":
                v3=d.get('accel',[0,0,0]); val_text="Ускор.: "+", ".join(f"{x:.2f}" for x in v3)
            elif name == "Gyroscope":
                v3=d.get('gyro',[0,0,0]); val_text="Угл.скор.: "+", ".join(f"{x:.2f}" for x in v3)
            elif name == "Magnetometer":
                v3=d.get('mag',[0,0,0]); val_text="Магн.п.: "+", ".join(f"{x:.2f}" for x in v3)
            elif name == "DS18B20":
                val_text=f"Темп: {d.get('temp_ds',0):.2f} °C"
            elif name == "GPS":
                gps=d.get('gps',(0,0,0)); fix=d.get('gps_fix',0)
                val_text=f"Коорд.: {gps[0]}, {gps[1]}\nВысота: {gps[2]}\nFix: {fix}"
        desc = self.descriptions.get(name,"")
        text = (f"<b>{name}</b><br>Код состояния: {code}<br>{desc}<br><br>{val_text}")
        self.info_label.setText(text)

# === СТРАНИЦА ЛОГОВ + ЭКСПОРТ В ZIP ===
class LogPage(QWidget):
    def __init__(self):
        super().__init__()
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
                    background: {COLORS['btn_normal']};
                    color: {COLORS['text_primary']};
                    border-radius:6px; font-size:11pt; padding:0 20px;
                }}
                QPushButton:hover {{ background: {COLORS['btn_hover']}; }}
                QPushButton:pressed {{ background: {COLORS['btn_active']}; }}
            """)
        self.clear_btn.clicked.connect(self.clear_log)
        self.save_btn.clicked.connect(self.save_log)
        self.export_btn.clicked.connect(self.export_logs)
        buttons_layout.addWidget(self.clear_btn)
        buttons_layout.addWidget(self.save_btn)
        buttons_layout.addWidget(self.export_btn)
        buttons_layout.addStretch()
        layout.addWidget(header); layout.addWidget(self.log_text); layout.addLayout(buttons_layout)

    @Slot(str)
    def add_log_message(self, message):
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

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
        now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        archive = f"log/logs_{now}.zip"
        try:
            with zipfile.ZipFile(archive, 'w') as z:
                for fn in os.listdir("log"):
                    z.write(os.path.join("log", fn), arcname=fn)
            self.add_log_message(f"[{datetime.datetime.now()}] Логи экспортированы в {archive}")
        except Exception as e:
            self.add_log_message(f"[ERROR] Экспорт ZIP не удался: {e}")

# === СТРАНИЦА КАМЕРЫ ===
class CameraPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self); layout.setContentsMargins(10,10,10,10)
        header = QLabel("Видеопоток")
        header.setStyleSheet(f"""
            font-size:16pt; font-weight:bold; color:{COLORS['text_primary']}; margin-bottom:10px
        """)
        self.web_view = QWebEngineView(); self.web_view.setUrl(QUrl("about:blank"))
        refresh_btn = QPushButton("⟳ Обновить страницу"); refresh_btn.setFixedHeight(40)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{ background:{COLORS['btn_normal']}; color:{COLORS['text_primary']};
            border-radius:6px; font-size:11pt; padding:0 20px; font-weight:bold }}
            QPushButton:hover {{ background:{COLORS['btn_hover']}; }}
            QPushButton:pressed {{ background:{COLORS['btn_active']}; }}
        """)
        refresh_btn.clicked.connect(self.web_view.reload)
        self.url_label = QLabel("URL: [будет вставлен позже]")
        self.url_label.setStyleSheet(f"color:{COLORS['text_secondary']}; font-style:italic")
        layout.addWidget(header); layout.addWidget(self.web_view)
        layout.addWidget(refresh_btn); layout.addWidget(self.url_label)

    def set_url(self, url):
        self.web_view.setUrl(QUrl(url))
        self.url_label.setText(f"URL: {url}")

# === СТРАНИЦА НАСТРОЕК + .ini ===
class SettingsPage(QWidget):
    settings_changed = Signal(bool, str, int)
    simulator_changed  = Signal(bool, str)
    def __init__(self):
        super().__init__()
        self.cfg = configparser.ConfigParser()
        if os.path.isfile("config.ini"):
            self.cfg.read("config.ini")
        udp = self.cfg.get("UDP", "enabled", fallback="False") == "True"
        host = self.cfg.get("UDP", "host", fallback="127.0.0.1")
        port = self.cfg.getint("UDP", "port", fallback=5005)

        layout = QVBoxLayout(self); layout.setContentsMargins(20,20,20,20)
        header = QLabel("Настройки")
        header.setStyleSheet(f"""
            font-size:18pt; font-weight:bold; color:{COLORS['text_primary']}; margin-bottom:20px
        """)
        # UDP
        udp_card = QFrame()
        udp_card.setStyleSheet(f"QFrame {{ background:{COLORS['bg_card']}; border-radius:8px; padding:15px }}")
        v = QVBoxLayout(udp_card)
        lab = QLabel("<b>UDP настройки</b>"); lab.setStyleSheet("font-size:14pt;")
        self.udp_enable = QCheckBox("Включить UDP отправку"); self.udp_enable.setChecked(udp)
        self.udp_ip = QLineEdit(host); self.udp_ip.setPlaceholderText("IP адрес")
        self.udp_port = QLineEdit(str(port)); self.udp_port.setPlaceholderText("Порт")
        for w in (lab, self.udp_enable, self.udp_ip, self.udp_port):
            v.addWidget(w)
        self.save_btn = QPushButton("Сохранить настройки")
        self.save_btn.setFixedHeight(40)
        self.save_btn.setStyleSheet(f"""
            QPushButton {{ background:{COLORS['btn_normal']}; color:{COLORS['text_primary']};
            border-radius:6px; font-size:11pt; padding:0 20px }}
            QPushButton:hover {{ background:{COLORS['btn_hover']}; }}
            QPushButton:pressed {{ background:{COLORS['btn_active']}; }}
        """)
        self.save_btn.clicked.connect(self.save_settings)
        layout.addWidget(header)
        layout.addWidget(udp_card)

        # --- Блок имитации из файла ---
        sim_card = QFrame()
        sim_card.setStyleSheet(f"QFrame {{ background:{COLORS['bg_card']}; border-radius:8px; padding:15px }}")
        v2 = QVBoxLayout(sim_card)
        lab2 = QLabel("<b>Имитация из файла</b>")
        self.sim_enable = QCheckBox("Включить имитацию")
        self.sim_file_path = QLineEdit()
        self.sim_file_path.setPlaceholderText("Путь к бинарному лог-файлу")
        self.sim_file_path.setReadOnly(True)
        btn_browse = QPushButton("Выбрать файл")
        btn_browse.clicked.connect(self.browse_sim_file)
        # Разметка
        v2.addWidget(lab2)
        v2.addWidget(self.sim_enable)
        hl = QHBoxLayout()
        hl.addWidget(self.sim_file_path)
        hl.addWidget(btn_browse)
        v2.addLayout(hl)
        layout.addWidget(sim_card)
        # Блок имитации недоступен, если включён UDP
        self.udp_enable.stateChanged.connect(
            lambda s: (
                self.sim_enable.setEnabled(not s),
                self.sim_file_path.setEnabled(not s),
                btn_browse.setEnabled(not s)
            )
        )
        # установить начальное состояние
        self.sim_enable.setEnabled(not udp)
        self.sim_file_path.setEnabled(not udp)
        btn_browse.setEnabled(not udp)



        #🔼 Конец вставки имитатора

        # кнопка «Сохранить» и отступ внизу
        layout.addWidget(self.save_btn)
        layout.addStretch()

    def save_settings(self):
        self.cfg["UDP"] = {
            "enabled": str(self.udp_enable.isChecked()),
            "host": self.udp_ip.text(),
            "port": self.udp_port.text()
        }
        with open("config.ini", "w") as f:
            self.cfg.write(f)
        enabled = self.udp_enable.isChecked()
        host = self.udp_ip.text()
        port = int(self.udp_port.text() or 0)
        self.settings_changed.emit(enabled, host, port)
        # эмитируем настройки симулятора
        sim_enabled = self.sim_enable.isChecked()
        sim_path    = self.sim_file_path.text()
        self.simulator_changed.emit(sim_enabled, sim_path)

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

# === ГЛАВНОЕ ОКНО ===
class MainWindow(QMainWindow):
    # In MainWindow class, modify the init method to include a more modern sidebar:
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Telemetry Dashboard")
        self.resize(1200, 700)  # Slightly larger default size
        apply_dark_theme(QApplication.instance())

        # Create main layout with sidebar and content
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        sidebar = QWidget()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet(f"background-color: {COLORS['bg_dark']};")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(15, 30, 15, 20)
        sidebar_layout.setSpacing(10)

        # Navigation menu items
        menu_items = [
            {"name": "Telemetry", "icon": "📊", "index": 0},
            {"name": "Graphs", "icon": "📈", "index": 1},
            {"name": "Sensors", "icon": "🔌", "index": 2},
            {"name": "Logs", "icon": "📝", "index": 3},
            {"name": "Camera", "icon": "🎥", "index": 4},
            {"name": "Settings", "icon": "⚙️", "index": 5},
            {"name": "Test",      "icon": "🧪", "index": 6}
        ]

        self.nav_buttons = []
        for item in menu_items:
            btn = QPushButton(f" {item['icon']} {item['name']}")
            btn.setProperty("index", item["index"])
            btn.setStyleSheet(f"""
                QPushButton {{
                    text-align: left;
                    padding: 12px 15px;
                    border-radius: 8px;
                    color: {COLORS['text_secondary']};
                    background: transparent;
                    font-size: 14px;
                }}
                QPushButton:hover {{
                    background: {COLORS['btn_hover']};
                    color: {COLORS['text_primary']};
                }}
                QPushButton:checked {{
                    background: {COLORS['accent']};
                    color: white;
                    font-weight: bold;
                }}
            """)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, idx=item["index"], b=btn: self.on_nav_click(idx, b))
            self.nav_buttons.append(btn)
            sidebar_layout.addWidget(btn)

        # Make first button selected by default
        self.nav_buttons[0].setChecked(True)

        sidebar_layout.addStretch()
        main_layout.addWidget(sidebar)

        # Content area
        content_area = QWidget()
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(20, 20, 20, 20)

        # Menu button for mobile (can be hidden on desktop)
        menu_btn = QPushButton("≡")
        menu_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['accent']};
                color: white;
                font-size: 18px;
                font-weight: bold;
                border-radius: 20px;
                padding: 5px 15px;
            }}
            QPushButton:hover {{
                background: {COLORS['accent_darker']};
            }}
        """)
        menu_btn.setFixedSize(40, 40)

        # Stack of pages
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background: {COLORS['bg_main']};")

        # Add pages to stack
        self.tel = TelemetryPage()
        self.graphs = GraphsPage()
        self.sens = SensorsPage()
        self.log_page = LogPage()
        self.camera = CameraPage()
        self.settings = SettingsPage()
        self.test = TestPage("models/grib.obj")
        for w in (self.tel, self.graphs, self.sens, self.log_page, self.camera, self.settings, self.test):
            self.stack.addWidget(w)

        content_layout.addWidget(self.stack)
        main_layout.addWidget(content_area)

        self.setCentralWidget(main_widget)

        #self.tabs.addTab(self.settings, "Настройки")
        #self.tabs.addTab(self.graphs, "Графики")
        #self.setCentralWidget(self.tabs)

        # Запускаем worker
        self.worker = TelemetryWorker("COM3", 9600)
        self.tel.set_worker(self.worker)
        self.worker.data_ready.connect(self.tel.update_values)
        self.worker.data_ready.connect(self.graphs.update_charts)
        self.worker.data_ready.connect(self.sens.update_data)
        self.worker.log_ready.connect(self.log_page.add_log_message)
        self.worker.error_crc.connect(QApplication.beep)
        # UDP settings
        self.settings.settings_changed.connect(self.worker.update_udp)
        # Simulation settings
        self.settings.simulator_changed.connect(self.on_simulator_changed)
        # передать начальные из .ini
        self.worker.start()
        self.settings.save_settings()
        self.worker.data_ready.connect(self.test.update_orientation)

    def on_nav_click(self, idx, btn):
        for b in self.nav_buttons:
            b.setChecked(False)
        btn.setChecked(True)
        self.stack.setCurrentIndex(idx)

    def on_simulator_changed(self, enabled: bool, filepath: str):
        """Обработчик включения симуляции из файла."""
        self.worker.sim_enabled = enabled
        if enabled:
            try:
                # открываем файл только при включении симуляции
                self.worker.sim_f = open(filepath, "rb")
            except Exception as e:
                print(f"[Ошибка открытия файла симуляции]: {e}")
                # отключаем симуляцию при неудаче
                self.worker.sim_enabled = False

    def on_change(self, idx):
        self.stack.setCurrentIndex(idx)

    def closeEvent(self, event):
        self.worker.stop()
        self.worker.wait(1000)
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    window.camera.set_url("https://sporadic.ru/cams/")
    sys.exit(app.exec())
