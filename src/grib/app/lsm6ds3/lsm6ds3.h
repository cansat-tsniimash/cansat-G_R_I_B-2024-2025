/*
 * lsm6ds3.h
 *
 *  Created on: Jan 6, 2025
 *      Author: user
 */

#ifndef LSM6DS3_LSM6DS3_H_
#define LSM6DS3_LSM6DS3_H_

#include <stdio.h>
#include <math.h>
#include <stdint.h>
#include <stm32f1xx.h>
#include "..\dwt_delay.h"

#include "lsm6ds3_reg.h"

int32_t lsm_read(void* handle, uint8_t reg_addr, uint8_t* data_ptr, uint16_t len);
int32_t lsm_write(void* handle, uint8_t reg_addr, const uint8_t *data_ptr, uint16_t len);
uint8_t lsm_init(stmdev_ctx_t* lsm_dev, I2C_HandleTypeDef* i2c_handle);

#endif /* LSM6DS3_LSM6DS3_H_ */
