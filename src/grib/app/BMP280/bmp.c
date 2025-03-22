/*
 * bmp.c
 *
 *  Created on: Nov 23, 2024
 *      Author: user
 */
#include "bmp.h"

#include "../I2C_crutch/i2c-crutch.h"

#define BME280_I2C_ADDRESS (0b1110110 << 1) // читаю, поэтому сдвигаю на единицу

BME280_INTF_RET_TYPE bmp_read(uint8_t reg_addr, uint8_t *reg_data, uint32_t len, void *intf_ptr)
{
	int res = HAL_I2C_Master_Transmit(intf_ptr, BME280_I2C_ADDRESS, &reg_addr, 1, 100);
	if(res != HAL_OK){
		I2C_ClearBusyFlagErratum(intf_ptr, 100);
		return 1;
	}
	res = HAL_I2C_Master_Receive(intf_ptr, BME280_I2C_ADDRESS, reg_data, len, 100);
	if(res != HAL_OK){
		I2C_ClearBusyFlagErratum(intf_ptr, 100);
		return 1;
	}
	return 0;
}
BME280_INTF_RET_TYPE bmp_write(uint8_t reg_addr, const uint8_t *reg_data, uint32_t len, void *intf_ptr)
{
	uint8_t tmp[2];
	for(uint32_t i = 0; i < len ; i++){
		tmp[0] = reg_addr + i;
		tmp[1] = reg_data[i];
		int res = HAL_I2C_Master_Transmit(intf_ptr, BME280_I2C_ADDRESS, tmp, 2, 100);
		if(res != HAL_OK){
			I2C_ClearBusyFlagErratum(intf_ptr, 100);
			return 1;
		}
	}
	return 0;
}

void bmp_delay(uint32_t period, void *intf_ptr){
	dwt_delay_us(period);
}

void bmp_init(bme280_dev_t* bmp_ptr, I2C_HandleTypeDef* i2c_ptr){
	dwt_delay_init();
	bmp_ptr->read = bmp_read;
	bmp_ptr->write = bmp_write;
	bmp_ptr->intf_ptr = i2c_ptr;
	bmp_ptr->intf = BME280_I2C_INTF;
	bme280_init(bmp_ptr);
	uint8_t sss_macros = BME280_OSR_PRESS_SEL | BME280_OSR_TEMP_SEL | BME280_OSR_HUM_SEL | BME280_FILTER_SEL | BME280_STANDBY_SEL | BME280_ALL_SETTINGS_SEL;
	bme280_set_sensor_settings(sss_macros, bmp_ptr);
	bme280_set_sensor_mode(BME280_NORMAL_MODE, bmp_ptr);
}
