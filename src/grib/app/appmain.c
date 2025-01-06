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

#include "BMP280\bmp.h"

#include <stm32f1xx.h>

extern I2C_HandleTypeDef hi2c1;

void appmain(){
	dwt_delay_init();
	bme280_dev_t bmp;
	bmp.delay_us = bmp_delay;
	bmp.settings.filter = BME280_FILTER_COEFF_2;
	bmp.settings.osr_h = BME280_OVERSAMPLING_16X;
	bmp.settings.osr_p = BME280_OVERSAMPLING_16X;
	bmp.settings.osr_t = BME280_OVERSAMPLING_16X;
	bmp.settings.standby_time = BME280_STANDBY_TIME_500_MS;
	struct bme280_data data;
	bmp_init(&bmp, &hi2c1);

	while(1){
		HAL_GPIO_WritePin(GPIOA, GPIO_PIN_8, GPIO_PIN_SET);
		HAL_Delay(100);
		HAL_GPIO_WritePin(GPIOA, GPIO_PIN_8, GPIO_PIN_RESET);
		HAL_Delay(100);
		bme280_get_sensor_data(BME280_ALL, &data, &bmp);
		//printf("temp = %f\n bmp = %f", data.temperature, data.pressure);
	}
}


