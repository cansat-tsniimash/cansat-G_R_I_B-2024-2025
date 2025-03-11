/*
 * scd41.c
 *
 *  Created on: 22 февр. 2025 г.
 *      Author: user
 */

#include "scd41.h"
#include "../I2C_crutch/i2c-crutch.h"

extern I2C_HandleTypeDef hi2c1;

#define SCD41_I2C_ADDRESS 0x62 << 1

#define CRC8_POLYNOMIAL 0x31
#define CRC8_INIT 0xFF

#define start_periodic_measurement 0x21b1
#define read_measurement 0xec05
#define stop_periodic_measurement 0x3f86

#define set_temperature_offset 0x241d
#define set_sensor_alitutude 0x2427
#define set_ambient_pressure 0xe000


uint8_t sensirion_common_generate_crc(const uint8_t* data, uint16_t count) {
	uint16_t current_byte;
	uint8_t crc = CRC8_INIT;
	uint8_t crc_bit;
	/* calculates 8-Bit checksum with given polynomial */
	for (current_byte = 0; current_byte < count; ++current_byte) {
		crc ^= (data[current_byte]);
		for (crc_bit = 8; crc_bit > 0; --crc_bit) {
			if (crc & 0x80)
				crc = (crc << 1) ^ CRC8_POLYNOMIAL;
			else
				crc = (crc << 1);
		}
	}
	return crc;
}

SCD41_RET_TYPE scd41_write(uint16_t cmd, I2C_HandleTypeDef *hi2c1){
	uint8_t co2[2];

	co2[0] = (uint8_t)(cmd >> 8);
	co2[1] = (uint8_t)(cmd & 0xFF);

	int res = HAL_I2C_Master_Transmit(hi2c1, SCD41_I2C_ADDRESS, co2, 2, 100);
	if(res != HAL_OK){
		I2C_ClearBusyFlagErratum(hi2c1, 100);
		return 1;
	}
	return 0;
}

SCD41_RET_TYPE scd41_read(uint8_t *data, uint32_t len, I2C_HandleTypeDef *hi2c1){
	int res = HAL_I2C_Master_Receive(hi2c1, SCD41_I2C_ADDRESS, data, 2, 100);
	if(res != HAL_OK){
		I2C_ClearBusyFlagErratum(hi2c1, 100);
		return 1;
	}
	return 0;
}

SCD41_RET_TYPE scd41_send(uint16_t cmd, I2C_HandleTypeDef *hi2c1){
	uint8_t buffer[2];
    buffer[0] = (uint8_t)(cmd >> 8);
	buffer[1] = (uint8_t)(cmd & 0xFF);
	int res = HAL_I2C_Master_Transmit(hi2c1, SCD41_I2C_ADDRESS, buffer, 2, 100);
	if (res != HAL_OK) {
		I2C_ClearBusyFlagErratum(hi2c1, 100);
	    return 1;
	}
	return 0;
}

void scd_delay(uint32_t period, I2C_HandleTypeDef *hi2c1){
	dwt_delay_us(period);
}

SCD41_RET_TYPE scd41_start_measurement(I2C_HandleTypeDef *hi2c1){
	return scd41_send(start_periodic_measurement, hi2c1);
}

SCD41_RET_TYPE scd41_stop_measurement(I2C_HandleTypeDef *hi2c1){
    uint8_t status = scd41_send(stop_periodic_measurement, hi2c1);
    //dwt_delay_us(500000);
    return status;
}

SCD41_RET_TYPE scd41_write_cmd(uint16_t cmd, uint16_t data, I2C_HandleTypeDef *hi2c1){
    uint8_t buffer[5];

    buffer[0] = (uint8_t)(cmd >> 8);
    buffer[1] = (uint8_t)(cmd & 0xFF);

    buffer[2] = (uint8_t)(data >> 8);
    buffer[3] = (uint8_t)(data & 0xFF);

    buffer[4] = sensirion_common_generate_crc(&buffer[2], 2);

    int res = HAL_I2C_Master_Transmit(hi2c1, SCD41_I2C_ADDRESS, buffer, 5, 100);
    if (res != HAL_OK) {
        I2C_ClearBusyFlagErratum(hi2c1, 100);
        return 1;
    }
    return 0;
}

SCD41_RET_TYPE scd41_read_measurement(uint16_t *co2, float *temp, float *pressure, I2C_HandleTypeDef *hi2c1){
	uint8_t status;
	uint8_t buffer[9];
	uint16_t data[3];

    status = scd41_send(read_measurement, hi2c1);
    if (status != 0) return status;

    for (int i = 0; i < 5; i++) {
    	status = scd41_read(&buffer[i * 2], 2, hi2c1);
        if (status != 0) return status;
    }
    for(int i = 0; i < 3;  i++){
    	int pos = i * 3;
        if(sensirion_common_generate_crc(&buffer[pos], 2) != buffer[pos + 2]){
        	return 1;
        }
        data[i] = ((uint16_t)buffer[pos] << 8) | buffer[pos + 1];
    }

    *co2 = data[0];
    *temp = -45.0f + 175.0f * ((float)data[1] / 65535.0f);
    *pressure = 100.0f * ((float)data[2] / 65535.0f);

    return 0;
}

SCD41_RET_TYPE scd41_set_temp_offset(uint16_t temp, I2C_HandleTypeDef *hi2c1){
    return scd41_write_cmd(set_temperature_offset, temp, hi2c1);
}

SCD41_RET_TYPE scd41_set_altitude(uint16_t altitude, I2C_HandleTypeDef *hi2c1){
    return scd41_write_cmd(set_sensor_alitutude, altitude, hi2c1);
}

SCD41_RET_TYPE scd41_set_pressure(uint16_t pressure, I2C_HandleTypeDef *hi2c1){
    return scd41_write_cmd(set_ambient_pressure, pressure, hi2c1);
}


void scd41_init(){
	uint8_t ret = 0;
	dwt_delay_init();


}
