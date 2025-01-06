/*
 * bmp.h
 *
 *  Created on: Nov 23, 2024
 *      Author: user
 */

#ifndef BMP280_BMP_H_
#define BMP280_BMP_H_

#include <stdio.h>
#include <math.h>
#include <stdint.h>
#include <stm32f1xx.h>

#include "bme280.h"
#include "../dwt_delay.h"

typedef struct bme280_dev bme280_dev_t;

BME280_INTF_RET_TYPE bmp_read(uint8_t reg_addr, uint8_t *reg_data, uint32_t len, void *intf_ptr);
BME280_INTF_RET_TYPE bmp_write(uint8_t reg_addr, const uint8_t *reg_data, uint32_t len, void *intf_ptr);
void bmp_delay(uint32_t period, void *intf_ptr);
void bmp_init(bme280_dev_t* bmp_ptr, I2C_HandleTypeDef* i2c_ptr);

#endif /* BMP280_BMP_H_ */
