/*
 * lis3mdl.c
 *
 *  Created on: Jan 8, 2025
 *      Author: user
 */

#include "../lis3mdl/lis3mdl.h"

#include "../I2C_crutch/i2c-crutch.h"

#define LIS3MDL_I2C_ADDRESS (0x1C << 1)

typedef int32_t (*stmdev_read_ptr)(void *, uint8_t, uint8_t *, uint16_t);
typedef int32_t (*stmdev_write_ptr)(void *, uint8_t, const uint8_t *, uint16_t);

int32_t lis_read(void* handle, uint8_t reg_addr, uint8_t* data_ptr, uint16_t len){
	HAL_StatusTypeDef res = HAL_I2C_Master_Transmit(handle, LIS3MDL_I2C_ADDRESS, &reg_addr, 1, 100);
    if (res != HAL_OK) {
        I2C_ClearBusyFlagErratum(handle, 100);
        return 1;
    }
        res = HAL_I2C_Master_Receive(handle, LIS3MDL_I2C_ADDRESS, data_ptr, len, 100);
    if (res != HAL_OK) {
    	I2C_ClearBusyFlagErratum(handle, 100);
        return 1;
    }
    return 0;
}

int32_t lis_write(void* handle, uint8_t reg_addr, const uint8_t *data_ptr, uint16_t len){
	uint8_t lis[2];
    for (uint16_t i = 0; i < len; i++) {
        lis[0] = reg_addr + i;
        lis[1] = data_ptr[i];
        HAL_StatusTypeDef res = HAL_I2C_Master_Transmit(handle, LIS3MDL_I2C_ADDRESS, lis, 2, 100);
        if (res != HAL_OK) {
            I2C_ClearBusyFlagErratum(handle, 100);
            return 1;
        }
    }
    return 0;
}

uint8_t lis_init(stmdev_ctx_t* lis_dev, I2C_HandleTypeDef* i2c_handle){
	uint8_t ret = 0;
	uint8_t whoami;
	dwt_delay_init();
	lis_dev->read_reg = lis_read;
	lis_dev->write_reg = lis_write;
	lis_dev->handle = i2c_handle;
	if(lis3mdl_reset_set(lis_dev, 1) != 0) ret = 1;;
	HAL_Delay(100);
	if(lis3mdl_fast_low_power_set(lis_dev, 0) != 0) ret = 1;
	if(lis3mdl_block_data_update_set(lis_dev, 1) != 0) ret = 1;
	if(lis3mdl_operating_mode_set(lis_dev, LIS3MDL_CONTINUOUS_MODE) != 0) ret = 1;
	if(lis3mdl_data_rate_set(lis_dev, LIS3MDL_UHP_80Hz) != 0) ret = 1;
	if(lis3mdl_full_scale_set(lis_dev, LIS3MDL_16_GAUSS) != 0) ret = 1;
	if(lis3mdl_device_id_get(lis_dev, &whoami) != 0) ret = 1;
	return ret;
}
