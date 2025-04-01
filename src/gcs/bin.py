import struct
import sys

file_bin = open(sys.argv[1], "rb")

file_csv = open(sys.argv[1] + ".csv", "w")
file_csv.write("start; team_id; time; temp_bmp280; pressure_bmp280; acceleration_x; acceleration_y; acceleration_z; angular_x; angular_y; angular_z; cheksum_org; number_packet; state; photoresistor; lis3mdl_x; lis3mdl_y; lis3mdl_z; ds18b20; neo6mv2_latitude; neo6mv2_latitude; neo6mv2_height; neo6mv2_fix; scd41; mq_4; me2o2; checksum_grib;\n")

def xor_block(data):
    result = 0x00 

    for byte in data:
        result ^= byte

    return result

buf = b""

while True:
	rcv = file_bin.read(100)
	print(rcv)
	if(len(rcv) == 0):
		break
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
