import sys, struct, math, datetime, os, socket, configparser, zipfile
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QStackedWidget, QFrame,
    QGridLayout, QSplitter, QSizePolicy, QTextEdit, QLineEdit,
    QCheckBox #QFileDialog
)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QUrl
from PySide6.QtGui import QPalette, QColor, QPixmap, QFont
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis

# === ПАРАМЕТРЫ ПАРСЕРА ===
PL, R0 = 1000, 4000
NAKLON, SMESHENIE = -0.7565, 1.269
SCALE = math.pow(10, -SMESHENIE / NAKLON)
STRUCT_FMT = "<2HIhI6hBHBH4h3fB3HB"  # 60 bytes

# === ЦВЕТОВАЯ СХЕМА ===
COLORS = {
    "bg_main": "#1e1e1e",
    "bg_dark": "#1f2329",
    "bg_card": "#2e3238",
    "bg_panel": "#2e2e2e",
    "accent": "#3a7ebf",
    "btn_normal": "#3c3f41",
    "btn_hover": "#4a5055",
    "btn_active": "#5a6066",
    "text_primary": "#ffffff",
    "text_secondary": "#aaaaaa",
    "text_highlight": "#61afef",
    "success": "#98c379",
    "warning": "#e5c07b",
    "danger": "#e06c75",
    "info": "#56b6c2"
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
        self.log_ready.emit("Start UDP")
        while self._running:
            try:
                rcv = self.udp_socket.recv(60*100)
            except Exception as e:
                continue
            self.log_ready.emit(f"Got Data {rcv}")
            if rcv:
                buf += rcv
                self.f_bin.write(rcv)
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
                            # сохраняем и эмитим
                            self.f_csv.write(";".join(str(x) for x in pkt) + "\n")
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
                               self.log_ready.emit(f"ошипка {e}")
                            # UDP
                            self.data_ready.emit(data)
                            buf = buf[60:]
                        else:
                            # CRC error
                            self.error_crc.emit()
                            self.log_ready.emit("[WARNING] CRC mismatch")
                            buf = buf[1:]
                    else:
                        buf = buf[1:]
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

        # --- График температуры BMP ---
        self.temp_index = 0
        self.series_temp = QLineSeries()
        chart_temp = QChart()
        chart_temp.addSeries(self.series_temp)
        chart_temp.setTitle("Темп BMP, °C")
        ax_x_t = QValueAxis(); ax_x_t.setLabelFormat("%i"); ax_x_t.setTitleText("Точка")
        ax_y_t = QValueAxis(); ax_y_t.setLabelFormat("%.2f"); ax_y_t.setTitleText("°C")
        chart_temp.addAxis(ax_x_t, Qt.AlignBottom); self.series_temp.attachAxis(ax_x_t)
        chart_temp.addAxis(ax_y_t, Qt.AlignLeft);   self.series_temp.attachAxis(ax_y_t)
        self.chart_temp_view = QChartView(chart_temp)
        layout.addWidget(self.chart_temp_view, 9, 0)

        # --- График величины ускорения ---
        self.acc_index = 0
        self.series_acc = QLineSeries()
        chart_acc = QChart()
        chart_acc.addSeries(self.series_acc)
        chart_acc.setTitle("Величина ускорения, g")
        ax_x_a = QValueAxis(); ax_x_a.setLabelFormat("%i"); ax_x_a.setTitleText("Точка")
        ax_y_a = QValueAxis(); ax_y_a.setLabelFormat("%.2f"); ax_y_a.setTitleText("g")
        chart_acc.addAxis(ax_x_a, Qt.AlignBottom); self.series_acc.attachAxis(ax_x_a)
        chart_acc.addAxis(ax_y_a, Qt.AlignLeft);   self.series_acc.attachAxis(ax_y_a)
        self.chart_accel_view = QChartView(chart_acc)
        layout.addWidget(self.chart_accel_view, 9, 1)

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
        layout.addWidget(header); layout.addWidget(udp_card); layout.addWidget(self.save_btn)
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

# === ГЛАВНОЕ ОКНО ===
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Наземка – Интерфейс Телеметрии")
        self.resize(1000, 600)
        apply_dark_theme(QApplication.instance())

        self.menu = QListWidget()
        for name, icon in [
            ("Телеметрия", "📊"),
            ("Датчики", "🔌"),
            ("Лог", "📝"),
            ("Камера", "🎥"),
            ("Настройки", "⚙️")
        ]:
            self.menu.addItem(f"{icon} {name}")
        self.menu.currentRowChanged.connect(self.on_change)
        self.menu.setFixedWidth(180)
        self.menu.setStyleSheet(f"""
            QListWidget {{ background:{COLORS['bg_dark']}; color:{COLORS['text_primary']}; border:none }}
            QListWidget::item {{ padding:15px; font-size:12pt; border-bottom:1px solid #2c303a }}
            QListWidget::item:selected {{ background:{COLORS['accent']}; color:white }}
            QListWidget::item:hover:!selected {{ background:{COLORS['btn_hover']}; }}
        """)

        self.stack = QStackedWidget()
        self.tel = TelemetryPage()
        self.sens = SensorsPage()
        self.log_page = LogPage()
        self.camera = CameraPage()
        self.settings = SettingsPage()

        for w in (self.tel, self.sens, self.log_page, self.camera, self.settings):
            self.stack.addWidget(w)

        container = QWidget()
        hl = QHBoxLayout(container)
        hl.addWidget(self.menu); hl.addWidget(self.stack)
        hl.setContentsMargins(0,0,0,0); hl.setSpacing(0)
        self.setCentralWidget(container)
        self.menu.setCurrentRow(0)

        self.setStyleSheet(f"""
            QMainWindow {{ background:{COLORS['bg_main']} }}
            QScrollBar:vertical {{ background:{COLORS['bg_dark']}; width:10px }}
            QScrollBar::handle:vertical {{ background:{COLORS['btn_normal']}; min-height:20px; border-radius:5px }}
            QScrollBar::handle:vertical:hover {{ background:{COLORS['btn_hover']}; }}
            QScrollBar:horizontal {{ background:{COLORS['bg_dark']}; height:10px }}
            QScrollBar::handle:horizontal {{ background:{COLORS['btn_normal']}; min-width:20px; border-radius:5px }}
            QScrollBar::handle:horizontal:hover {{ background:{COLORS['btn_hover']}; }}
        """)

        # Запускаем worker
        self.worker = TelemetryWorker("COM3", 9600)
        self.tel.set_worker(self.worker)
        self.worker.data_ready.connect(self.tel.update_values)
        self.worker.data_ready.connect(self.tel.update_chart)
        self.worker.data_ready.connect(self.sens.update_data)
        self.worker.log_ready.connect(self.log_page.add_log_message)
        self.worker.error_crc.connect(QApplication.beep)
        # UDP settings
        self.settings.settings_changed.connect(self.worker.update_udp)
        # передать начальные из .ini
        self.worker.start()
        self.settings.save_settings()

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
