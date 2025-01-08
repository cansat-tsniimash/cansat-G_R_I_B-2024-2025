/*
 * lsm6ds3.c
 *
 *  Created on: Jan 6, 2025
 *      Author: user
 */

#include "../I2C_crutch/i2c-crutch.h"
#include "lsm6ds3.h"

#define LSM6DS3_I2C_ADDRESS (0x6A << 1)

typedef int32_t (*stmdev_read_ptr)(void *, uint8_t, uint8_t *, uint16_t);
typedef int32_t (*stmdev_write_ptr)(void *, uint8_t, const uint8_t *, uint16_t);

int32_t lsm_read(void* handle, uint8_t reg_addr, uint8_t* data_ptr, uint16_t len){
	int res = HAL_I2C_Master_Transmit(handle, LSM6DS3_I2C_ADDRESS, &reg_addr, 1, 100);
    if (res != HAL_OK) {
        I2C_ClearBusyFlagErratum(handle, 100);
        return 1;
    }
        res = HAL_I2C_Master_Receive(handle, LSM6DS3_I2C_ADDRESS, data_ptr, len, 100);
    if (res != HAL_OK) {
    	I2C_ClearBusyFlagErratum(handle, 100);
        return 1;
    }
    return 0;
}

int32_t lsm_write(void* handle, uint8_t reg_addr, const uint8_t *data_ptr, uint16_t len){
	uint8_t lsm[2];
    for (uint16_t i = 0; i < len; i++) {
        lsm[0] = reg_addr + i;
        lsm[1] = data_ptr[i];
        int res = HAL_I2C_Master_Transmit(handle, LSM6DS3_I2C_ADDRESS, lsm, 2, 100);
        if (res != HAL_OK) {
            I2C_ClearBusyFlagErratum(handle, 100);
            return 1;
        }
    }
    return 0;
}

uint8_t lsm_init(stmdev_ctx_t* lsm_dev, I2C_HandleTypeDef* i2c_handle){
	uint8_t ret = 0;
	dwt_delay_init();
	lsm_dev->read_reg = lsm_read;
	lsm_dev->write_reg = lsm_write;
	lsm_dev->handle = i2c_handle;
	if (lsm6ds3_reset_set(lsm_dev, 1) != 0) ret = 1;
	HAL_Delay(100);
	if(lsm6ds3_xl_full_scale_set(lsm_dev, LSM6DS3_16g) != 0) ret = 1;
	if(lsm6ds3_xl_data_rate_set(lsm_dev, LSM6DS3_XL_ODR_52Hz) != 0) ret = 1;
	if(lsm6ds3_gy_full_scale_set(lsm_dev, LSM6DS3_2000dps) != 0) ret = 1;
	if(lsm6ds3_gy_data_rate_set(lsm_dev, LSM6DS3_GY_ODR_1k66Hz) != 0) ret = 1;
	return ret;
}
