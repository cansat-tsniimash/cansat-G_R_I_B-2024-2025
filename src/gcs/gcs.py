import RPi.GPIO as GPIO
import struct
from time import sleep
import serial
import datetime
import math
import socket
import logging
import sys

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

# Настройка UDP сервера
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_socket.bind(('0.0.0.0', 5005))
server_socket.setblocking(False)
clients = []  # Список подключенных клиентов

# Константы E220
E220_M0_PIN = 5
E220_M1_PIN = 6
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
GPIO.cleanup()
GPIO.setmode(GPIO.BCM)
GPIO.setup(E220_M0_PIN, GPIO.OUT)
GPIO.setup(E220_M1_PIN, GPIO.OUT)
GPIO.setup(E220_AUX_PIN, GPIO.IN)

# Открытие порта
port = serial.Serial("/dev/ttyRF2", baudrate=9600, timeout=0.3)

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
    sleep(1)


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

# Начальная настройка модуля
logging.info("Configuring E220 module...")
e220_set_mode(3)
e220_set_adres(0xFFFF)
sleep(1)
e220_set_reg0(E220_REG0_AIR_RATE_9600, E220_REG0_PARITY_8N1_DEF, E220_REG0_PORT_RATE_9600)
sleep(1)
e220_set_reg1(E220_REG1_PACKET_LEN_200B, E220_REG1_RSSI_OFF, E220_REG1_TPOWER_22)
sleep(1)
e220_set_channel(1)
sleep(1)
e220_set_reg3(
    E220_REG3_RSSI_BYTE_OFF,
    E220_REG3_TRANS_M_TRANSPARENT,
    E220_REG3_LBT_EN_OFF,
    E220_REG3_WOR_CYCLE_500
)
sleep(1)
recv = port.read(1500)
e220_get_config()
e220_set_mode(0)

logging.info("Entering main loop")
buf = b""
try:
    while True:
        # UDP: прием от клиентов
        try:
            data, addr = server_socket.recvfrom(1024)
            if addr not in clients:
                clients.append(addr)
                logging.info("New client: %s", addr)
            if data == b"status":
                server_socket.sendto(b"OK", addr)
                logging.info("Status OK sent to %s", addr)
        except BlockingIOError:
            pass

        # UART: чтение данных
        rcv = port.read(100)
        if rcv:
            aux_state = GPIO.input(E220_AUX_PIN)
            logging.debug("AUX state: %d", aux_state)
            file_bin.write(rcv)
            file_bin.flush()
            buf += rcv

            # ретрансляция сырого
            for client in clients:
                server_socket.sendto(rcv, client)

        # обработка пакетов
        while len(buf) >= 60:
            if buf[0] == 0xAA and buf[1] == 0xAA:
                pack = struct.unpack("<2HIhI6hBHBH4h3fB3HB", buf[:60])
                if xor_block(buf[:59]) == pack[26]:
                    # запись CSV
                    file_csv.write(";".join(str(x) for x in pack) + ";")
                    file_csv.flush()

                    # расчёты
                    accel = [num * 488 / 1000 / 1000 for num in pack[5:8]]
                    gyro = [num * 70 / 1000 for num in pack[8:11]]
                    magnet = [num / 1711 for num in pack[15:18]]

                    # вывод в консоль
                    print("Контрольная сумма сошлась")
                    print("Н.пакета", pack[12])
                    print("Время:", pack[2])
                    #print("Темп BMP", pack[3] / 100)
                    #print("Давл BMP", pack[4])
                    #print("Ускор LSM6D {:4.2f} {:4.2f} {:4.2f}".format(*accel))
                    #print("Угл.скор LSM6D {:4.2f} {:4.2f} {:4.2f}".format(*gyro))
                    print("Сост.апарт", pack[13] & 0x07)
                    print("Фото.рез {:2.2f}".format(pack[14] / 1000))
                    #print("Магнит.поле {:4.2f} {:4.2f} {:4.2f}".format(*magnet))
                    #print("Темп DS18 {:4.2f}".format(pack[18] / 16))
                    #print("GPS {:3.6f} {:3.6f} {:4.2f}".format(*pack[19:22]))
                    #print("GPS fix", pack[22])
                    #print("SCD41", pack[23])
                    mq4_voltage = pack[24] / 1000.0  # Assuming pack[24] is in millivolts
                    mq4_ppm = calculate_mq4_ppm(mq4_voltage)
                    #print("MQ4 Voltage: {:.2f}V".format(mq4_voltage))
                    #print("me2o2f20", pack[25])

                    # отправка json-подобного
                    data_dict = {
                        "packet": pack[12],
                        "time": pack[2],
                        "temp_bmp": pack[3] / 100,
                        "pressure": pack[4],
                        "accel": accel,
                        "gyro": gyro,
                        "state": pack[13] & 0x07,
                        "photores": pack[14] / 1000,
                        "magnet": magnet,
                        "temp_ds18": pack[18] / 16,
                        "gps": {"lat": pack[19], "lon": pack[20], "alt": pack[21], "fix": pack[22]},
                        "scd41": pack[23],
                        "mq4": {
                        "voltage": pack[24] / 1000.0,  # Assuming pack[24] is in millivolts
                        "ppm": calculate_mq4_ppm(pack[24] / 1000.0)
                        },
                        "me2o2": pack[25]
                    }
                    msg = str(data_dict).encode()
                    for client in clients:
                        server_socket.sendto(msg, client)

                    buf = buf[60:]
                else:
                    logging.warning("Bad checksum, discard byte")
                    buf = buf[1:]
            else:
            	buf = buf[1:]
except KeyboardInterrupt:
    logging.info("User interrupted")
finally:
    logging.info("Cleanup and exit")
    file_bin.close()
    file_csv.close()
    port.close()
    server_socket.close()
    GPIO.cleanup()
