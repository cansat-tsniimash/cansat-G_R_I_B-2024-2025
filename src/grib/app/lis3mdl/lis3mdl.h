/*
 * lis3mdl.h
 *
 *  Created on: Jan 8, 2025
 *      Author: user
 */

#ifndef LI3MDL_LIS3MDL_H_
#define LI3MDL_LIS3MDL_H_

#include <stdio.h>
#include <math.h>
#include <stdint.h>
#include <stm32f1xx.h>
#include "..\dwt_delay.h"

#include "lis3mdl_reg.h"

int32_t lis_read(void* handle, uint8_t reg_addr, uint8_t* data_ptr, uint16_t len);
int32_t lsm_write(void* handle, uint8_t reg_addr, const uint8_t *data_ptr, uint16_t len);
uint8_t lis_init(stmdev_ctx_t* lis_dev, I2C_HandleTypeDef* i2c_handle);

#endif /* LI3MDL_LIS3MDL_H_ */
