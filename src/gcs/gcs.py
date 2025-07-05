import RPi.GPIO as GPIO
import struct
from time import sleep
import serial
import datetime
import math
import socket
import logging
import sys
import json
import time

# Настройка логирования
current_datetime = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_filename = f"log/grib_{current_datetime}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler(sys.stdout)
    ]
)
# ================================

def calculate_mq4_ppm(voltage):
    # Constants from MQ-4 datasheet
    PL = 20000.0  # Load resistor in ohms
    R0 = 4000.0   # Sensor resistance in clean air
    NAKLON = -0.374  # Slope
    SMESHENIE = 1.101  # Intercept
    SCALE = 10 ** (-SMESHENIE / NAKLON)
    
    # Calculate sensor resistance
    sensor_resistance = (3.3 - voltage) * PL / voltage
    
    # Calculate ratio to clean air
    ratio = sensor_resistance / R0
    
    # Apply formula for PPM calculation
    ppm = ratio ** (1.0 / NAKLON) * SCALE
    
    return ppm


# ===== Добавляем расчёт кислорода =====
# Параметры АЦП и усилителя
ADC_REF_VOLTAGE = 3.3    # опорное напряжение АЦП (V)
ADC_MAX = 4095.0         # разрешение 12-битного АЦП

# Вычислите эти два параметра по вашим измерениям:
#   V_zero — выход датчика при 0 % O2 (например, в чистом N2)
#   V_air  — выход датчика при ~21 % O2 (обычный воздух)
# Тогда:
#   O2_SLOPE  = (V_air  – V_zero) / 21.0
#   O2_OFFSET = V_zero

V_zero = 0.175   # В при 0 % O₂
V_air  = 1.05    # В при ~21 % O₂

O2_SLOPE = (V_air  - V_zero) / 21.0   # заменить на число, полученное по формуле
O2_OFFSET = V_zero                     # заменить на измеренное напряжение при 0 % O2

def calculate_o2_percent(voltage: float) -> float:
    """
    Переводим входное напряжение в % кислорода и ограничиваем в диапазоне 0–100%.
    """
    perc = (voltage - O2_OFFSET) / O2_SLOPE
    # Логируем для отладки: «сырое» АЦП, напряжение, рассчитанный %
    logging.debug(
        "O2 raw ADC=%d, voltage=%.3f V → perc=%.2f%%",
        raw_me2o2, voltage, perc
    )
    # Предотвращаем «взлет» значения за границы физических возможных
    if perc < 0.0 or perc > 100.0:
        logging.warning("O2 out of bounds: %.2f%% → clamped", perc)
    return max(0.0, min(100.0, perc))
# ======================================

class UDPServer:
    def __init__(self, host='0.0.0.0', port=5005):
        self.host = host
        self.port = port
        self.socket = None
        self.clients = []
        self.last_check = time.time()
        self.create_socket()

    def create_socket(self):
        try:
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.bind((self.host, self.port))
            self.socket.setblocking(False)
            print("\n=== UDP Server Started ===")
            print(f"Listening on {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"ERROR: Failed to create UDP socket: {e}")
            self.socket = None
            return False

    def handle_client(self, data, addr):
        if addr not in self.clients:
            self.clients.append(addr)
            print(f"\nNew UDP client connected: {addr}")
            print(f"Total clients: {len(self.clients)}")
        
        if data == b"status":
            try:
                self.send_data(b"OK", addr)
                print(f"Sent status response to {addr}")
            except Exception as e:
                print(f"ERROR: Failed to send status response: {e}")
        else:
            try:
                json_data = json.loads(data.decode('utf-8'))
                print(f"Received JSON data from {addr}: {json_data}")
            except json.JSONDecodeError:
                print(f"Received non-JSON data from {addr}: {data}")
            except Exception as e:
                print(f"ERROR: Failed to process data from {addr}: {e}")

    def send_data(self, data, addr=None):
        if not self.socket:
            if not self.create_socket():
                return False
        
        try:
            if addr:
                self.socket.sendto(data, addr)
            else:
                active_clients = []
                for client in self.clients:
                    try:
                        self.socket.sendto(data, client)
                        print(f"Sent to client: {client}")
                        active_clients.append(client)
                    except Exception as e:
                        print(f"ERROR: Failed to send to client {client}: {e}")
                self.clients = active_clients
            return True
        except Exception as e:
            print(f"ERROR: Failed to send data: {e}")
            self.socket = None
            return False

    def check_clients(self):
        if time.time() - self.last_check > 5:
            active_clients = []
            for client in self.clients:
                try:
                    if self.send_data(b"ping", client):
                        active_clients.append(client)
                except:
                    pass
            self.clients = active_clients
            print(f"Active UDP clients: {len(self.clients)}")
            self.last_check = time.time()

# Создаем экземпляр UDP сервера
udp_server = UDPServer()

# Константы E220
E220_M0_PIN = 6
E220_M1_PIN = 5
E220_AUX_PIN = 25

E220_REG0_PORT_RATE_1200 = 0
E220_REG0_PORT_RATE_2400 = 1
E220_REG0_PORT_RATE_4800 = 2
E220_REG0_PORT_RATE_9600 = 3
E220_REG0_PORT_RATE_19200 = 4
E220_REG0_PORT_RATE_38400 = 5
E220_REG0_PORT_RATE_57600 = 6
E220_REG0_PORT_RATE_115200 = 7

E220_REG0_PARITY_8N1_DEF = 0
E220_REG0_PARITY_8O1 = 1
E220_REG0_PARITY_8E1 = 2
E220_REG0_PARITY_8N1_EQ = 3

E220_REG0_AIR_RATE_2400 = 2
E220_REG0_AIR_RATE_4800 = 3
E220_REG0_AIR_RATE_9600 = 4
E220_REG0_AIR_RATE_19200 = 5
E220_REG0_AIR_RATE_38400 = 6
E220_REG0_AIR_RATE_62500 = 7

E220_REG1_PACKET_LEN_200B = 0
E220_REG1_PACKET_LEN_128B = 1
E220_REG1_PACKET_LEN_64B = 2
E220_REG1_PACKET_LEN_32B = 3

E220_REG1_TPOWER_22 = 0
E220_REG1_TPOWER_17 = 1
E220_REG1_TPOWER_13 = 2
E220_REG1_TPOWER_10 = 3

E220_REG1_RSSI_OFF = 0
E220_REG1_RSSI_ON = 1

E220_REG3_RSSI_BYTE_OFF = 0
E220_REG3_RSSI_BYTE_ON = 1

E220_REG3_TRANS_M_TRANSPARENT = 0
E220_REG3_TRANS_M_FIXED = 1

E220_REG3_LBT_EN_OFF = 0
E220_REG3_LBT_EN_ON = 1

E220_REG3_WOR_CYCLE_500 = 0
E220_REG3_WOR_CYCLE_1000 = 1
E220_REG3_WOR_CYCLE_1500 = 2
E220_REG3_WOR_CYCLE_2000 = 3
E220_REG3_WOR_CYCLE_2500 = 4
E220_REG3_WOR_CYCLE_3000 = 5
E220_REG3_WOR_CYCLE_3500 = 6
E220_REG3_WOR_CYCLE_4000 = 7

# Инициализация GPIO
try:
    GPIO.cleanup()
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(E220_M0_PIN, GPIO.OUT)
    GPIO.setup(E220_M1_PIN, GPIO.OUT)
    GPIO.setup(E220_AUX_PIN, GPIO.IN)
    logging.info("GPIO initialized successfully")
except Exception as e:
    logging.error("GPIO initialization failed: %s", e)
    sys.exit(1)

# Открытие порта
try:
    port = serial.Serial("/dev/ttyRF2", baudrate=9600, timeout=0.3)
    if not port.is_open:
        port.open()
    logging.info("Serial port opened successfully")
except Exception as e:
    logging.error("Failed to open serial port: %s", e)
    sys.exit(1)

# Проверяем состояние AUX пина перед настройкой
aux_state = GPIO.input(E220_AUX_PIN)
logging.info("Initial AUX pin state: %d", aux_state)

# Файлы лога данных
binfile = f"log/grib_{current_datetime}.bin"
file_bin = open(binfile, "wb")
csvfile = f"log/grib_{current_datetime}.csv"
file_csv = open(csvfile, "w")
file_csv.write(
    "start;team_id;time;temp_bmp280;pressure_bmp280;"
    "acceleration_x;acceleration_y;acceleration_z;"
    "angular_x;angular_y;angular_z;cheksum_org;"
    "number_packet;state;photoresistor;"
    "lis3mdl_x;lis3mdl_y;lis3mdl_z;ds18b20;"
    "neo6mv2_latitude;neo6mv2_longitude;neo6mv2_height;neo6mv2_fix;"
    "scd41;mq_4;me2o2;checksum_grib;\n"
)

logging.info("Initialization complete. Logging to %s", log_filename)

def xor_block(data):
    result = 0x00
    for byte in data:
        result ^= byte
    return result

# Функции управления модулем E220

def e220_set_mode(regim):
    if regim == 0:
        GPIO.output(E220_M0_PIN, GPIO.LOW)
        GPIO.output(E220_M1_PIN, GPIO.LOW)
    elif regim == 1:
        GPIO.output(E220_M0_PIN, GPIO.HIGH)
        GPIO.output(E220_M1_PIN, GPIO.LOW)
    elif regim == 2:
        GPIO.output(E220_M0_PIN, GPIO.LOW)
        GPIO.output(E220_M1_PIN, GPIO.HIGH)
    elif regim == 3:
        GPIO.output(E220_M0_PIN, GPIO.HIGH)
        GPIO.output(E220_M1_PIN, GPIO.HIGH)


def e220_set_reg(adres, data):
    port.write(struct.pack("<4B", 0xC0, adres, 1, data))
    time.sleep(0.5)


def e220_set_adres(adres):
    e220_set_reg(0, adres >> 8)
    e220_set_reg(1, adres & 0xFF)


def e220_set_reg0(air_rate, parity, port_rate):
    e220_set_reg(2, air_rate | (parity << 3) | (port_rate << 5))


def e220_set_reg1(packet_len, rssi, power):
    e220_set_reg(3, power | (rssi << 5) | (packet_len << 6))


def e220_set_channel(chanel):
    e220_set_reg(4, chanel)


def e220_set_reg3(enable_rssi, method, lbt_enable, cycle):
    e220_set_reg(
        5,
        cycle | (lbt_enable << 4) | (method << 6) | (enable_rssi << 7)
    )


def e220_get_config():
    port.write(struct.pack("<BBB", 0xC1, 0, 9))
    recv = port.read(15)
    logging.info("E220 Settings (raw): %s", recv)
    if len(recv) >= 12:
        logging.info(
            "E220 Settings (parsed): %s",
            struct.unpack("<3BH7B", recv[:12])
        )

def setup_e220():
    try:
        print("\n=== E220 Module Setup ===")
        print("Checking initial state...")
        
        # Проверяем начальное состояние AUX
        aux_state = GPIO.input(E220_AUX_PIN)
        print(f"Initial AUX state: {aux_state}")
        
        # Проверяем состояние M0 и M1
        m0_state = GPIO.input(E220_M0_PIN)
        m1_state = GPIO.input(E220_M1_PIN)
        print(f"Initial M0 state: {m0_state}, M1 state: {m1_state}")
        
        # Устанавливаем режим 3 (конфигурация)
        print("\nSetting mode 3 (configuration)...")
        e220_set_mode(3)
        time.sleep(0.5)  # Увеличиваем задержку

        # Проверяем состояние M0 и M1
        m0_state = GPIO.input(E220_M0_PIN)
        m1_state = GPIO.input(E220_M1_PIN)
        print(f"Setting mode M0 state: {m0_state}, M1 state: {m1_state}")
        
        # Проверяем AUX после установки режима
        aux_state = GPIO.input(E220_AUX_PIN)
        print(f"AUX state after mode change: {aux_state}")
        
        if aux_state == 0:
            print("WARNING: AUX is LOW after mode change - module might be busy")
            time.sleep(0.5)  # Увеличиваем задержку
        
        # Очищаем буферы
        print("\nClearing buffers...")
        port.reset_input_buffer()
        port.reset_output_buffer()
        
        # Проверяем состояние порта
        print(f"Port is open: {port.is_open}")
        print(f"Port settings: {port.get_settings()}")
        
        # Настройка регистров
        print("\nConfiguring registers...")
        
        # Address = 0xFFFF
        print("Setting ADDR REG...")
        e220_set_adres(0xFFFF)
        time.sleep(0.5)
        response = port.read(10)
        print(f"ADDR REG response: {response.hex() if response else 'None'}")

        # Air rate = 9600, parity = 8N1, prot rate = 9600
        print("Setting REG0...")
        e220_set_reg0(E220_REG0_AIR_RATE_9600, E220_REG0_PARITY_8N1_DEF, E220_REG0_PORT_RATE_9600)
        time.sleep(0.5)
        response = port.read(10)
        print(f"REG0 response: {response.hex() if response else 'None'}")

        # REG1: packet len = 200, rssi off, power = 22
        print("Setting REG1...")
        e220_set_reg1(E220_REG1_PACKET_LEN_200B, E220_REG1_RSSI_OFF, E220_REG1_TPOWER_22)
        time.sleep(0.5)
        response = port.read(10)
        print(f"REG1 response: {response.hex() if response else 'None'}")

        # chanel = 1
        print("Setting CHANNEL...")
        e220_set_channel(1)
        time.sleep(0.5)
        response = port.read(10)
        print(f"CHANNEL response: {response.hex() if response else 'None'}")

        # REG3:
        print("Setting REG3...")
        e220_set_reg3(
            E220_REG3_RSSI_BYTE_OFF,
            E220_REG3_TRANS_M_TRANSPARENT,
            E220_REG3_LBT_EN_OFF,
            E220_REG3_WOR_CYCLE_500
        )
        time.sleep(0.5)
        response = port.read(10)
        print(f"REG3 response: {response.hex() if response else 'None'}")
        
        # Читаем настройки для проверки
        print("\nReading current settings...")
        e220_get_config()
        #print(f"Current settings: {settings.hex() if settings else 'None'}")
        
        # Возвращаем в режим 0 (передача)
        print("\nSetting mode 0 (transmission)...")
        e220_set_mode(0)
        time.sleep(0.5)
        
        # Проверяем AUX после возврата в режим передачи
        aux_state = GPIO.input(E220_AUX_PIN)
        print(f"Final AUX state: {aux_state}")

        print("\n=== E220 Setup Complete ===")
        return True
    except Exception as e:
        print(f"ERROR: E220 setup failed: {e}")
        return False

# Начальная настройка модуля
print("\n=== Starting E220 Configuration ===")
if not setup_e220():
    print("ERROR: Failed to configure E220 module. Exiting...")
    sys.exit(1)

# Основной цикл
try:
    # Инициализация буфера
    buf = bytearray()
    print("\n=== Starting main loop ===")
    print("Waiting for UART data...")

    while True:
        # UDP: проверка новых клиентов
        try:
            if udp_server.socket:
                data, addr = udp_server.socket.recvfrom(1024)
                udp_server.handle_client(data, addr)
        except socket.error as e:
            if e.errno != socket.EAGAIN:
                print(f"ERROR: UDP receive error: {e}")
                udp_server.create_socket()

        # UART: чтение данных
        try:
            print("\nTrying to read UART...")
            rcv = port.read(100)
            print(f"Read result: {rcv.hex() if rcv else 'No data'}")
            if rcv:
                aux_state = GPIO.input(E220_AUX_PIN)
                print(f"AUX state: {aux_state}")
                print(f"Buffer size before adding: {len(buf)}")
                buf += rcv
                print(f"Buffer size after adding: {len(buf)}")
                print(f"Current buffer content: {buf.hex()}")
                file_bin.write(rcv)
                file_bin.flush()
            else:
                # Проверяем состояние порта
                if not port.is_open:
                    print("ERROR: Serial port is closed!")
                    try:
                        port.open()
                        print("Serial port reopened")
                    except Exception as e:
                        print(f"ERROR: Failed to reopen serial port: {e}")
                # Проверяем AUX пин
                aux_state = GPIO.input(E220_AUX_PIN)
                if aux_state == 0:
                    print("WARNING: AUX pin is LOW - module might be busy")
        except serial.SerialException as e:
            print(f"ERROR: Serial port error: {e}")
            try:
                port.close()
                port.open()
                print("Serial port reopened")
            except Exception as e:
                print(f"ERROR: Failed to reopen serial port: {e}")
        except Exception as e:
            print(f"ERROR: UART read error: {e}")

        # обработка пакетов
        while len(buf) >= 60:
            print("\n=== Processing packet ===")
            print(f"Buffer size: {len(buf)}")
            print(f"First 10 bytes: {buf[:10].hex()}")
            if buf[0] == 0xAA and buf[1] == 0xAA:
                print("Found packet header!")
                chunk = buf[:60]
                print(f"Processing chunk: {chunk.hex()}")
                try:
                    pack = struct.unpack("<2HIhI6hBHBH4h3fB3HB", chunk)
                    print(f"Unpacked packet: {pack}")
                except struct.error as e:
                    print(f"ERROR: Struct unpack error: {e}. Skipping byte.")
                    buf = buf[1:]
                    continue

                calculated_crc = xor_block(chunk[:-1])
                received_crc = pack[-1]
                print(f"CRC check - Calculated: {calculated_crc}, Received: {received_crc}")

                if calculated_crc == received_crc:
                    raw_me2o2 = pack[25]      # «сырое» значение АЦП
                    voltage_o2 = raw_me2o2 / ADC_MAX * ADC_REF_VOLTAGE
                    me2o2_o2 = round(calculate_o2_percent(voltage_o2), 1)
                    data = {
                        "header": int(pack[0]),
                        "team_id": int(pack[1]),
                        "time": int(pack[2]),
                        "temp_bmp": float(pack[3] * 0.01),
                        "press_bmp": int(pack[4]),
                        "accel_x": float(pack[5] * 0.000488),
                        "accel_y": float(pack[6] * 0.000488),
                        "accel_z": float(pack[7] * 0.000488),
                        "gyro_x": float(pack[8] * 0.07),
                        "gyro_y": float(pack[9] * 0.07),
                        "gyro_z": float(pack[10] * 0.07),
                        "checksum_org": int(pack[11]),
                        "packet_num": int(pack[12]),
                        "state": int(pack[13] & 7),
                        "photo": float(pack[14] * 0.001),
                        "mag_x": float(pack[15] * 0.000584),
                        "mag_y": float(pack[16] * 0.000584),
                        "mag_z": float(pack[17] * 0.000584),
                        "temp_ds": float(pack[18] * 0.0625),
                        "gps_lat": float(pack[19]),
                        "gps_lon": float(pack[20]),
                        "gps_alt": float(pack[21]),
                        "gps_fix": int(pack[22]),
                        "scd41": int(pack[23]),
                        "mq4": int(pack[24]),
                        "me2o2": float(me2o2_o2),
                        "checksum_grib": int(pack[26])
                    }
                    print(f"Processed data: {data}")

                    try:
                        # Преобразуем все значения в базовые типы Python
                        json_string = json.dumps(data, ensure_ascii=False)
                        print(f"JSON string: {json_string}")
                        udp_message = json_string.encode('utf-8')
                        print(f"UDP message (hex): {udp_message.hex()}")
                        print(f"Sending UDP message to {len(udp_server.clients)} clients")
                        udp_server.send_data(udp_message)
                    except Exception as e:
                        print(f"ERROR: Failed to send JSON UDP packet: {e}")
                        print(f"Data that caused error: {data}")

                    buf = buf[60:]
                else:
                    print(f"WARNING: CRC mismatch! Calculated: {calculated_crc}, Received: {received_crc}")
                    buf = buf[1:]
            else:
                # Ищем следующий заголовок
                header_index = buf.find(b"\xAA\xAA")
                if header_index != -1:
                    print(f"Found header at index {header_index}, skipping {header_index} bytes")
                    buf = buf[header_index:]
                else:
                    # Если заголовок не найден, оставляем только последний байт
                    buf = buf[-1:]

        # Проверяем активных клиентов
        udp_server.check_clients()

except KeyboardInterrupt:
    print("\nUser interrupted")
finally:
    # Очистка
    print("\nCleaning up...")
    try:
        port.close()
        print("Serial port closed")
    except:
        pass
    try:
        if udp_server.socket:
            udp_server.socket.close()
        print("UDP socket closed")
    except:
        pass
    try:
        file_bin.close()
        file_csv.close()
        print("Log files closed")
    except:
        pass
    try:
        GPIO.cleanup()
        print("GPIO cleaned up")
    except:
        pass
    print("Cleanup complete")
