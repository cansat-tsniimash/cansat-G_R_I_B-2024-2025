/*
 * appmain.c
 *
 *  Created on: Jan 6, 2025
 *      Author: user
 */

#include <stdint.h>
#include <stdio.h>
#include <math.h>
#include <stdbool.h>

#include "dwt_delay.h"

#include "BMP280\bmp.h" // датчик BMP280

#include "lsm6ds3\lsm6ds3.h" // датчик lsm6ds3

#include "lis3mdl\lis3mdl.h" // датчик lis3mdl

#include "ds18b20\onewire.h"

#include "resistor\resistor.h"

#include "CD4051\cd4051.h"

#include "fatfs_sd\fatfs_sd.h" // micro sd

#include "E220400T22S/e220_400t22s.h"

#include "..\Middlewares\Third_Party\FatFs\src\ff.h" // micro sd

#include "mq-4\mq4.h" // mq-4

#include "me2-o2-f20\me2o2f20.h" // ME2-O2-Ф20

#include <stm32f1xx.h>

#include "scd41\scd41.h"

#include "neo6mv2\neo6mv2.h"

extern ADC_HandleTypeDef hadc1;
extern I2C_HandleTypeDef hi2c1;
extern UART_HandleTypeDef huart2;

uint8_t xorBlock(const uint8_t *data, size_t size) {
    uint8_t result = 0x00;

    for (size_t i = 0; i < size; i++) {
        result ^= data[i];
    }

    return result;
}

typedef struct{
	float temp;
	float pressure;
	float accel[3];
	float gyro[3];
	float magn[3];
	uint8_t accel_error;
	uint8_t gyro_error;
	uint8_t magn_error;
	uint8_t lis_err;
	uint8_t lsm_err;
} data_t;

#pragma pack(push, 1)
typedef struct{
	uint16_t start;
	uint16_t team_id;
	uint32_t time;
	int16_t temp_bmp280;
	uint32_t pressure_bmp280;
	int16_t acceleration_x;
	int16_t acceleration_y;
	int16_t acceleration_z;
	int16_t angular_x;
	int16_t angular_y;
	int16_t angular_z;
	uint8_t cheksum_org;
	uint16_t number_packet;
	uint8_t state;
	uint16_t photoresistor;
	int16_t lis3mdl_x;
	int16_t lis3mdl_y;
	int16_t lis3mdl_z;
	int16_t ds18b20;
	float ne06mv2_height;
	float ne06mv2_longitude;
	float ne06mv2_latitude;
	uint8_t neo6mv2_fix;
	uint16_t scd41;
	uint16_t mq_4;
	uint16_t me2o2;
	uint8_t checksum_grib;
} packet_t;
#pragma pack(pop)

void appmain(){
	packet_t packet = {0};
	packet.start = 0xAAAA;
	packet.number_packet = 0;
	volatile data_t my_data;
	int16_t temp_gyro[3]; // temp = ВРЕМЕННО!
	int16_t temp_accel[3];


	// BMP280
	bme280_dev_t bmp;
	bmp.delay_us = bmp_delay;
	bmp.settings.filter = BME280_FILTER_COEFF_2;
	bmp.settings.osr_h = BME280_OVERSAMPLING_16X;
	bmp.settings.osr_p = BME280_OVERSAMPLING_16X;
	bmp.settings.osr_t = BME280_OVERSAMPLING_16X;
	bmp.settings.standby_time = BME280_STANDBY_TIME_500_MS;
	struct bme280_data data;
	bmp_init(&bmp, &hi2c1);

	// LSM6DS3
	stmdev_ctx_t lsm;
	my_data.lsm_err = lsm_init(&lsm, &hi2c1);



	// LIS3MDL
	stmdev_ctx_t lis;
	my_data.lis_err = lis_init(&lis, &hi2c1);
	int16_t temp_magn[3];

	// DS18B20
	one_wire_bus_t bus;
	bus.port = GPIOA;
	bus.pinchik = GPIO_PIN_15;
	one_wire_init(bus);
	ds18b20_write_config(bus, DS18B20_RES_750MS);
	one_wire_start_convertion(bus);
	uint32_t get_time = HAL_GetTick();

	// resistor

	// мультплексер CD4051

	// sd

	FATFS fileSystem; // переменная типа FATFS
	FIL binFile, csvFile; // хендлер файла
    UINT testBytes;  // Количество записанных байт

    FRESULT mount_res = 255;
    FRESULT bin_res = 255;
    FRESULT csv_res = 255;
    uint8_t bin_path[] = "grib.bin\0";
    uint8_t csv_path[] = "grib.csv\0";
    char str_buffer[300] = {0};
    char str_header[300] = "number_packet; time; temp_bmp280; pressure_bmp280; acceleration x; acceleration y; acceleration z; angular x; angular y; angular z; state; photoresistor; lis3mdl_x; lis3mdl_y; lis3mdl_z; ds18b20; ne06mv2_height; ne06mv2_longitude; ne06mv2_latitude; neo6mv2_fix; scd41; mq_4; me2o2;\n";
    /*int mount_attemps;
    for(mount_attemps = 0; mount_attemps < 5; mount_attemps++)
    {
    	mount_res = f_mount(&fileSystem, "0:", 0);
        if (mount_res == FR_OK) {
        	res = f_open(&binFile, "gribochek_raw.bin\0", FA_WRITE | FA_CREATE_ALWAYS);
        	break;
        }
    }*/

	//e220-400t22s

    // scd41


    scd41_start_measurement(&hi2c1);
    uint16_t co2 = 0;
	float temp = 0;
	float pressure = 0;
    scd41_read_measurement(&co2, &temp, &pressure, &hi2c1);


	//
	e220_pins_t e220_bus;
	e220_bus.m0_pinchik = GPIO_PIN_1;
	e220_bus.m1_pinchik = GPIO_PIN_0;
	e220_bus.m0_port = GPIOB;
    e220_bus.m1_port = GPIOB;
    e220_bus.aux_pin = GPIO_PIN_3;
	e220_bus.aux_port = GPIOB;
    e220_bus.uart = &huart2;
    e220_set_mode(e220_bus, E220_MODE_DSM);

    e220_set_addr(e220_bus, 0xFFFF);
    HAL_Delay(100);
    e220_set_reg0(e220_bus, E220_REG0_AIR_RATE_2400, E220_REG0_PARITY_8N1_DEF, E220_REG0_PORT_RATE_9600);
    HAL_Delay(100);
    e220_set_reg1(e220_bus, E220_REG1_PACKET_LEN_200B, E220_REG1_RSSI_OFF, E220_REG1_TPOWER_22);
    HAL_Delay(100);
    e220_set_channel(e220_bus, 1);
    HAL_Delay(100);
    e220_set_reg3(e220_bus, E220_REG3_RSSI_BYTE_OFF, E220_REG3_TRANS_M_TRANSPARENT, E220_REG3_LBT_EN_OFF, E220_REG3_WOR_CYCLE_500);
    e220_set_mode(e220_bus, E220_MODE_TM);

    //char helloworld3[25] = "Bye, Anton! [FIX]";
    float result;
	float mq_result;
	float me2o2_result;

	while(1){
		// BMP280
		bme280_get_sensor_data(BME280_ALL, &data, &bmp); // вывод давления и температуры
		packet.pressure_bmp280 = data.pressure;
		packet.temp_bmp280 = data.temperature * 100;
		// LSM6DS3
		my_data.gyro_error = lsm6ds3_angular_rate_raw_get(&lsm, temp_gyro);
		packet.angular_x = temp_gyro[0];
		packet.angular_y = temp_gyro[1];
		packet.angular_z = temp_gyro[2];

		my_data.accel_error = lsm6ds3_acceleration_raw_get(&lsm, temp_accel);
		packet.acceleration_x = temp_accel[0];
		packet.acceleration_y = temp_accel[1];
		packet.acceleration_z = temp_accel[2];
		// LIS3MDL
		my_data.magn_error = lis3mdl_magnetic_raw_get(&lis, temp_magn);
		packet.lis3mdl_x = temp_magn[0];
		packet.lis3mdl_y = temp_magn[1];
		packet.lis3mdl_z = temp_magn[2];

		//DS18B20
		if(get_time + 750 < HAL_GetTick()){
			get_time = HAL_GetTick();
			packet.ds18b20 = ds18b20_read_temp(bus);
			one_wire_start_convertion(bus);
		}
		// resistor
		cd4051_change_ch(0);
		megalux(&hadc1, &result);
		packet.photoresistor = result;

		cd4051_change_ch(1);
		mq4_ppm(&hadc1, &mq_result);
		packet.mq_4 = mq_result;

		cd4051_change_ch(2);
		me2o2f20_read(&hadc1, &me2o2_result);
		packet.me2o2 = me2o2_result;


		packet.time = HAL_GetTick();
		packet.number_packet++;
		packet.cheksum_org = xorBlock((uint8_t *)&packet, 26);
		packet.checksum_grib = xorBlock((uint8_t *)&packet, sizeof(packet_t) - 1);

	    e220_send_packet(e220_bus, 0xFFFF, (uint8_t *)&packet, sizeof(packet_t), 23);

		//sd

		if (mount_res != FR_OK){
			f_mount(NULL, "", 0);
			mount_res = f_mount(&fileSystem, "", 1);
			bin_res = f_open(&binFile, (char*)bin_path, FA_WRITE | 0x30);
			csv_res = f_open(&csvFile, (char*)csv_path, FA_WRITE | 0x30);
			csv_res = f_write(&csvFile, str_header, 300, &testBytes);
		}

		if  (mount_res == FR_OK && bin_res != FR_OK){
			f_close(&binFile);
			bin_res = f_open(&binFile, (char*)bin_path, FA_WRITE | 0x30);
		}

		if (mount_res == FR_OK && bin_res == FR_OK)
		{
			bin_res = f_write(&binFile, (uint8_t*)&packet, sizeof(packet_t), &testBytes);
			f_sync(&binFile);
		}

		if  (mount_res == FR_OK && csv_res != FR_OK){
			f_close(&csvFile);
			csv_res = f_open(&csvFile, (char*)csv_path, FA_WRITE | 0x30);
			csv_res = f_write(&csvFile, str_header, 300, &testBytes);
			//f_puts("time; temp_bmp280; pressure_bmp280; acceleration x; acceleration y; acceleration z; angular x; angular y; angular z; state; photoresistor; lis3mdl_x; lis3mdl_y; lis3mdl_z; ds18b20; ne06mv2_height; ne06mv2_longitude; ne06mv2_latitude; neo6mv2_fix; scd41; mq_4; me2o2;\n", &csvFile);
		}
		if (mount_res == FR_OK && csv_res == FR_OK)
		{
			uint16_t csv_write = snprintf(str_buffer, 300, "%d;%ld;%d;%ld;%d;%d;%d;%d;%d;%d;%d;%d;%d;%d;%d;%d;%ld;%ld;%ld;%d;%d;%d;%d;\n", packet.number_packet , packet.time, packet.temp_bmp280, packet.pressure_bmp280, packet.acceleration_x, packet.acceleration_y, packet.acceleration_z, packet.angular_x, packet.angular_y, packet.angular_z, packet.state, packet.photoresistor, packet.lis3mdl_x, packet.lis3mdl_y, packet.lis3mdl_z, packet.ds18b20, (long int)(packet.ne06mv2_height * 1000), (long int)(packet.ne06mv2_longitude * 1000), (long int)(packet.ne06mv2_latitude * 1000), packet.neo6mv2_fix, packet.scd41, packet.mq_4, packet.me2o2);
			csv_res = f_write(&csvFile, str_buffer, csv_write, &testBytes);
			f_sync(&csvFile);
		}
	}
}


