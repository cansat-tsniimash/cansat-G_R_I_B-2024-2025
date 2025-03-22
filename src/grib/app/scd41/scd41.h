/*
 * scd41.h
 *
 *  Created on: 22 февр. 2025 г.
 *      Author: user
 */

#ifndef SCD41_SCD41_H_
#define SCD41_SCD41_H_

#include <stdio.h>
#include <math.h>
#include <stdint.h>
#include <stm32f1xx.h>

#include "../dwt_delay.h"

typedef int8_t SCD41_RET_TYPE;

uint8_t sensirion_common_generate_crc(const uint8_t* data, uint16_t count);
SCD41_RET_TYPE scd41_write(uint16_t cmd, uint16_t data, I2C_HandleTypeDef *hi2c1);
SCD41_RET_TYPE scd41_read(uint16_t cmd, uint16_t *data, uint16_t len, I2C_HandleTypeDef *hi2c1);
void scd_delay(uint32_t period, I2C_HandleTypeDef *hi2c1);
SCD41_RET_TYPE scd41_send(uint16_t cmd, I2C_HandleTypeDef *hi2c1);
void scd_delay(uint32_t period, I2C_HandleTypeDef *hi2c1);
SCD41_RET_TYPE scd41_start_measurement(I2C_HandleTypeDef *hi2c1);
SCD41_RET_TYPE scd41_stop_measurement(I2C_HandleTypeDef *hi2c1);
SCD41_RET_TYPE scd41_write_cmd(uint16_t cmd, uint16_t data, I2C_HandleTypeDef *hi2c1);
SCD41_RET_TYPE scd41_read_measurement(uint16_t *co2, float *temp, float *pressure, I2C_HandleTypeDef *hi2c1);
SCD41_RET_TYPE scd41_set_temp_offset(uint16_t temp, I2C_HandleTypeDef *hi2c1);
SCD41_RET_TYPE scd41_set_altitude(uint16_t altitude, I2C_HandleTypeDef *hi2c1);
SCD41_RET_TYPE scd41_set_pressure(uint16_t pressure, I2C_HandleTypeDef *hi2c1);
void scd41_init();


#endif /* SCD41_SCD41_H_ */
