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

#include <stm32f1xx.h>

extern ADC_HandleTypeDef hadc1;
extern I2C_HandleTypeDef hi2c1;
extern UART_HandleTypeDef huart2;

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

typedef struct{
	uint16_t start;
	uint16_t team_id;
	uint32_t time;
	uint16_t temp_bmp280;
	uint32_t pressure_bmp280;
	uint16_t acceleration_x;
	uint16_t acceleration_y;

	uint16_t acceleration_z;
	uint16_t angular_x;
	uint16_t angular_y;
	uint16_t angular_z;
	uint8_t cheksum_org;
	uint16_t number_packet;
	uint8_t state;
	uint16_t photoresistor;
	uint16_t lis3mdl_x;
	uint16_t lis3mdl_y;
	uint16_t lis3mdl_z;
	uint16_t ds18b20;
	float ne06mv2_height;
	float ne06mv2_longitude;
	float ne06mv2_latitude;
	uint8_t neo6mv2_fix;
	uint16_t scd41;
	uint16_t mq_4;
	uint16_t me2o2;
	uint8_t checksum_grib;
} packet_t;


void appmain(){
	packet_t packet;
	packet.start = 0xAAAA;
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

	/*FATFS fileSystem; // переменная типа FATFS
	FIL testFile; // хендлер файла
    char testBuffer[16] = "TestTestTestTest";  // Данные для записи
    UINT testBytes;  // Количество записанных байт
    uint8_t path[] = "testfile.txt\0";  // Путь к файлу

    FRESULT mount_res;
    FRESULT res;
    int mount_attemps;
    for(mount_attemps = 0; mount_attemps < 5; mount_attemps++)
    {
    	mount_res = f_mount(&fileSystem, "", 0);
        if (mount_res == FR_OK) {
        	res = f_open(&testFile, (char*)path, FA_WRITE | FA_CREATE_ALWAYS);
        	break;
        }
    }*/

	//e220-400t22s



	//
	e220_pins_t e220_bus;
	e220_bus.m0_pinchik = GPIO_PIN_1;
	e220_bus.m1_pinchik = GPIO_PIN_0;
	e220_bus.m0_port = GPIOB;
    e220_bus.m1_port = GPIOB;
    e220_bus.aux_pin = GPIO_PIN_3;
	e220_bus.aux_port = GPIOB;
    e220_bus.uart = &huart2;
    //e220_set_mode(e220_bus, E220_MODE_DSM);
    char helloworld[200] = "Privet GRIBI moyi";
	float result;

	while(1){
		uint8_t reg_addr = 7;
		uint8_t reg_data = 0x88;

	    e220_send_packet(e220_bus, 0xFFFF, (uint8_t *)helloworld, 200, 23);










		// BMP280
		bme280_get_sensor_data(BME280_ALL, &data, &bmp); // вывод давления и температуры
		packet.pressure_bmp280 = data.pressure;
		packet.temp_bmp280 = data.temperature;
		// LSM6DS3
		//printf("temp = %f\n bmp = %f", data.temperature, data.pressure);
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

		/*for(int i = 0; i < 3 ; i++){
			my_data.gyro[i] = lsm6ds3_from_fs2000dps_to_mdps(temp_gyro[i]);
		}
		my_data.accel_error = lsm6ds3_acceleration_raw_get(&lsm, temp_accel);
		for(int i = 0; i < 3 ; i++){
			my_data.accel[i] = lsm6ds3_from_fs16g_to_mg(temp_accel[i]);
		}

		my_data.magn_error = lis3mdl_magnetic_raw_get(&lis, temp_magn);
		for (int i = 0; i < 3; i++) {
		    my_data.magn[i] = lis3mdl_from_fs16_to_gauss(temp_magn[i]);
		}*/

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
		//e220_set_mode(e220_bus, E220_MODE_DSM);
		//uint8_t bufer_uart_read[9] = {0};
		//uint8_t bufer_uart[5] = {0xC1, 0, 0x07, 0x88, 0x88};
		//HAL_UART_Transmit(&huart2, bufer_uart, 3, 1000);
		//HAL_UART_Receive(&huart2, bufer_uart_read, 9, 1000);

		//e220_set_addr(e220_bus, 0x8888);

		//sd

		/*if (mount_res == FR_OK)
		{
			res = f_write(&testFile, (uint8_t*) testBuffer, sizeof(testBuffer), &testBytes);

			if(res != FR_OK){
				f_close(&testFile);
				f_mount(NULL, "", 0);
				mount_res = f_mount(&fileSystem, "", 1);
				if(res == FR_OK){
					res = f_open(&testFile, (char*)path, FA_WRITE | FA_CREATE_ALWAYS);
				}
			}
		}
		else
		{
			f_mount(NULL, "", 0);
			mount_res = f_mount(&fileSystem, "", 1);
		}*/

	}
}


