/*
 * e220_400t22s.c
 *
 *  Created on: 7 февр. 2025 г.
 *      Author: user
 */

#include <stdio.h>

#include "e220_400t22s.h"

typedef enum{
	E220_MODE_TM = 0,
	E220_MODE_WTM = 1,
	E220_MODE_WRM = 2,
	E220_MODE_DSM = 3
}E220_MODE_t;

//REG0

typedef enum{
	E220_REG0_PORT_RATE_1200 = 0,
	E220_REG0_PORT_RATE_2400 = 1,
	E220_REG0_PORT_RATE_4800 = 2,
	E220_REG0_PORT_RATE_9600 = 3,
	E220_REG0_PORT_RATE_19200 = 4,
	E220_REG0_PORT_RATE_38400 = 5,
	E220_REG0_PORT_RATE_57600 = 6,
	E220_REG0_PORT_RATE_115200 = 7
}e220_set_reg0_portrate;

typedef enum{
	E220_REG0_PARITY_8N1_DEF = 0,
	E220_REG0_PARITY_8O1 = 1,
	E220_REG0_PARITY_8E1 = 2,
	E220_REG0_PARITY_8N1_EQ = 3
}e220_set_reg0_parity;

typedef enum{
	E220_REG0_AIR_RATE_2400 = 0,
	E220_REG0_AIR_RATE_4800 = 1,
	E220_REG0_AIR_RATE_9600 = 2,
	E220_REG0_AIR_RATE_19200 = 3,
	E220_REG0_AIR_RATE_38400 = 4,
	E220_REG0_AIR_RATE_62500 = 5
}e220_set_reg0_airrate;

//REG1

typedef enum{
	E220_REG1_PACKET_LEN_200B = 0,
	E220_REG1_PACKET_LEN_128B = 1,
	E220_REG1_PACKET_LEN_64B = 2,
	E220_REG1_PACKET_LEN_32B = 3

}e220_set_reg1_packetlen;

typedef enum{
	E220_REG1_TPOWER_22 = 0,
	E220_REG1_TPOWER_17 = 1,
	E220_REG1_TPOWER_13 = 2,
	E220_REG1_TPOWER_10 = 3

}e220_set_reg1_tpower;

typedef enum{
	E220_REG1_RSSI_OFF = 0,
	E220_REG1_RSSI_ON = 1

}e220_set_reg1_rssi;

//REG3

typedef enum{
	E220_REG3_RSSI_BYTE_OFF = 0,
	E220_REG3_RSSI_BYTE_ON = 1

}e220_set_reg1_rssibyte;

typedef enum{
	E220_REG3_TRANS_M_TRANSPARENT = 0,
	E220_REG3_TRANS_M_FIXED = 1
}e220_set_reg1_transm;

typedef enum{
	E220_REG3_LBT_EN_OFF = 0,
	E220_REG3_LBT_EN_ON = 1

}e220_set_reg1_lbten;

typedef enum{
	E220_REG3_WOR_CYCLE_500 = 0,
	E220_REG3_WOR_CYCLE_1000 = 1,
	E220_REG3_WOR_CYCLE_1500 = 2,
	E220_REG3_WOR_CYCLE_2000 = 3,
	E220_REG3_WOR_CYCLE_2500 = 4,
	E220_REG3_WOR_CYCLE_3000 = 5,
	E220_REG3_WOR_CYCLE_3500 = 6,
	E220_REG3_WOR_CYCLE_4000 = 7

}e220_set_reg1_worcycle;

void e220_set_mode(e220_pins_t pin, E220_MODE_t mode){
	switch(mode){
	case E220_MODE_TM:
		HAL_GPIO_WritePin(pin.m1_port, pin.m1_pinchik, GPIO_PIN_RESET);
		HAL_GPIO_WritePin(pin.m0_port, pin.m0_pinchik, GPIO_PIN_RESET);
		break;
	case E220_MODE_WTM:
		HAL_GPIO_WritePin(pin.m1_port, pin.m1_pinchik, GPIO_PIN_RESET);
		HAL_GPIO_WritePin(pin.m0_port, pin.m0_pinchik, GPIO_PIN_SET);
		break;
	case E220_MODE_WRM:
		HAL_GPIO_WritePin(pin.m1_port, pin.m1_pinchik, GPIO_PIN_SET);
		HAL_GPIO_WritePin(pin.m0_port, pin.m0_pinchik, GPIO_PIN_RESET);
		break;
	case E220_MODE_DSM:
		HAL_GPIO_WritePin(pin.m1_port, pin.m1_pinchik, GPIO_PIN_SET);
		HAL_GPIO_WritePin(pin.m0_port, pin.m0_pinchik, GPIO_PIN_SET);
		break;
	}
}

void e220_write_reg(e220_pins_t pin, uint8_t *reg_data, uint8_t reg_addr){
	uint8_t pon[4];
	pon[0] = 0xC0;
	pon[1] = reg_addr;
	pon[2] = 0x01;
	pon[3] = *reg_data;

	e220_set_mode(pin, E220_MODE_DSM);
	HAL_UART_Transmit(pin.uart, pon, 4, 100);

}

void e220_set_addr(e220_pins_t e220_bus, uint16_t addr){
	uint8_t *byte = (uint8_t*) &addr;
	e220_write_reg(e220_bus, &byte[0], 0x00);
	e220_write_reg(e220_bus, &byte[1], 0x01);
}

void e220_set_reg0(e220_pins_t e220_bus, uint8_t air_rate, uint8_t parity, uint8_t port_rate){
	uint8_t reg0 = air_rate + (parity << 3) + (port_rate << 5);
	e220_write_reg(e220_bus, &reg0, 0x02);
}

void e220_set_reg1(e220_pins_t e220_bus, uint8_t packet_len, uint8_t rssi, uint8_t t_power){
	uint8_t reg1 = (rssi << 5) + (packet_len << 6) + t_power;
	e220_write_reg(e220_bus, &reg1, 0x03);
}

void e220_set_channel(e220_pins_t e220_bus, uint8_t ch){
	e220_write_reg(e220_bus, &ch, 0x04);
}

void e220_set_reg3(e220_pins_t e220_bus, uint8_t rssi_byte, uint8_t trans_m, uint8_t lbt_en, uint8_t wor_cycle){
	uint8_t reg3 = (rssi_byte << 7) + (trans_m << 6) + (lbt_en << 4) + wor_cycle;
	e220_write_reg(e220_bus, &reg3, 0x05);
}

void e220_read_reg(e220_pins_t pin){

}
