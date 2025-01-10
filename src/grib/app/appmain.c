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

#include <stm32f1xx.h>

extern ADC_HandleTypeDef hadc1;
extern I2C_HandleTypeDef hi2c1;

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

void appmain(){
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
	one_wire_init(bus);
	ds18b20_write_config(bus, DS18B20_RES_750MS);
	one_wire_start_convertion(bus);
	uint32_t get_time = HAL_GetTick();

	// resistor

	float result;

	while(1){
		// BMP280
		bme280_get_sensor_data(BME280_ALL, &data, &bmp); // вывод давления и температуры
		// LSM6DS3
		my_data.pressure = data.pressure;
		my_data.temp = data.temperature;
		//printf("temp = %f\n bmp = %f", data.temperature, data.pressure);
		my_data.gyro_error = lsm6ds3_angular_rate_raw_get(&lsm, temp_gyro);
		for(int i = 0; i < 3 ; i++){
			my_data.gyro[i] = lsm6ds3_from_fs2000dps_to_mdps(temp_gyro[i]);
		}
		my_data.accel_error = lsm6ds3_acceleration_raw_get(&lsm, temp_accel);
		for(int i = 0; i < 3 ; i++){
			my_data.accel[i] = lsm6ds3_from_fs16g_to_mg(temp_accel[i]);
		}
		// LIS3MDL
		my_data.magn_error = lis3mdl_magnetic_raw_get(&lis, temp_magn);
		for (int i = 0; i < 3; i++) {
		    my_data.magn[i] = lis3mdl_from_fs16_to_gauss(temp_magn[i]);
		}
		//DS18B20
		if(get_time + 750 < HAL_GetTick()){
			get_time = HAL_GetTick();
			volatile uint16_t temp = ds18b20_read_temp(bus);
			one_wire_start_convertion(bus);
		}
		// resistor
		megalux(&hadc1, &result);

	}
}


