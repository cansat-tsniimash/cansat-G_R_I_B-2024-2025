import RPi.GPIO as GPIO
import struct
from time import sleep
import serial
import datetime

E220_M0_PIN = 23
E220_M1_PIN = 24
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

GPIO.cleanup()
GPIO.setmode(GPIO.BCM)
GPIO.setup(E220_M0_PIN, GPIO.OUT)
GPIO.setup(E220_M1_PIN, GPIO.OUT)
GPIO.setup(E220_AUX_PIN, GPIO.IN)

current_datetime = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")

port = serial.Serial("/dev/ttyUSB0", baudrate=9600, timeout=0.3)

binfile = f"log/grib_{current_datetime}.bin"
file_bin = open(binfile, "wb")

csvfile = f"log/grib_{current_datetime}.csv"
file_csv = open(csvfile, "w")
file_csv.write("start; team_id; time; temp_bmp280; pressure_bmp280; acceleration_x; acceleration_y; acceleration_z; angular_x; angular_y; angular_z; cheksum_org; number_packet; state; photoresistor; lis3mdl_x; lis3mdl_y; lis3mdl_z; ds18b20; neo6mv2_latitude; neo6mv2_latitude; neo6mv2_height; neo6mv2_fix; scd41; mq_4; me2o2; checksum_grib;\n")

def xor_block(data):
    result = 0x00 

    for byte in data:
        result ^= byte

    return result


#function
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
	e220_set_reg(5, cycle | (lbt_enable << 4) | (method << 6) | (enable_rssi << 7))

def e220_get_config():
	port.write(struct.pack("<BBB", 0xC1, 0, 9))
	recv = port.read(15)
	print("Settings:", recv)
	if (len(recv) >= 12):
		print(struct.unpack("<3BH7B", recv[:12]))


buf = b""

e220_set_mode(3)
e220_set_adres(0xFFFF)
sleep(1)
e220_set_reg0(E220_REG0_AIR_RATE_9600, E220_REG0_PARITY_8N1_DEF, E220_REG0_PORT_RATE_9600)
sleep(1)
e220_set_reg1(E220_REG1_PACKET_LEN_200B, E220_REG1_RSSI_OFF, E220_REG1_TPOWER_22)
sleep(1)
e220_set_channel(1)
sleep(1)
e220_set_reg3(E220_REG3_RSSI_BYTE_OFF, E220_REG3_TRANS_M_TRANSPARENT, E220_REG3_LBT_EN_OFF, E220_REG3_WOR_CYCLE_500)
sleep(1)
recv = port.read(1500)
e220_get_config()
e220_set_mode(0)


while True:
	rcv = port.read(100)
	print(rcv)
	file_bin.write(rcv)
	buf += rcv
	while len(buf) >= 60:
		if (buf[0] == 170) and (buf[1] == 170):
			print(buf[:60])
			pack = struct.unpack("<2HIhI6hBHBH4h3fB3HB", buf[:60])
			if xor_block(buf[:60-1]) == pack[26]:
				for num in pack:
					file_csv.write(str(num) + ";") 
				file_csv.write("\n")
				print("Контрольная сумма сошлась")
				print("Н.пакета", pack[12])
				print("Время:", pack[2])
				print("Темп BMP", pack[3] / 100)
				print("Давл BMP", pack[4])
				print("Ускор LSM6D {:4.2f} {:4.2f} {:4.2f}".format(*[num * 488 / 1000 / 1000 for num in pack[5:8]]))
				print("Угл.скор LSM6D {:4.2f} {:4.2f} {:4.2f}".format(*[num * 70 / 1000 for num in pack[8:11]]))
				print("Сост.апарт", pack[13])
				print("Фото.рез {:2.2f}" .format(pack[14] / 1000))
				print("Магнит.поле", [num / 1711 for num in pack[15:18]])
				print("Темп DS18 {:4.2f}".format(pack[18]/16))
				print("GPS {:3.6f} {:3.6f} {:4.2f}".format(*pack[19:22]))
				print("GPS fix", pack[22])
				print("SCD41", pack[23])
				print("MQ4", pack[24])
				print("me2o2f20", pack[25])
				print(pack)
				buf = buf[60:]
			else:
				buf = buf[1:]
		else:
			buf = buf[1:]

file_bin.close()
file_csv.close()

GPIO.cleanup()
