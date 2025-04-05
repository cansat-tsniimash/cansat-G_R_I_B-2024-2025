/*
 * e220_400t22s.c
 *
 *  Created on: 7 февр. 2025 г.
 *      Author: user
 */

#include "e220_400t22s.h"

#include <stdio.h>


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
	uint16_t try = 0;
	uint8_t pon[4];
	pon[0] = 0xC0;
	pon[1] = reg_addr;
	pon[2] = 0x01;
	pon[3] = *reg_data;

	e220_set_mode(pin, E220_MODE_DSM);
	HAL_UART_Transmit(pin.uart, pon, 4, 100);
	while((HAL_GPIO_ReadPin(pin.aux_port, pin.aux_pin) == GPIO_PIN_RESET) && (try < 200)){
		try++;
		HAL_Delay(1);
	}
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

void e220_send_packet(e220_pins_t e220_bus, uint16_t addr, uint8_t *reg_data, uint16_t len, uint8_t target_channel){
	e220_set_mode(e220_bus, E220_MODE_TM);
	uint16_t try = 0;
	HAL_UART_Transmit(e220_bus.uart, (uint8_t *)&addr, 2, 100);
	HAL_UART_Transmit(e220_bus.uart, (uint8_t *)&target_channel, 1, 100);
	HAL_UART_Transmit(e220_bus.uart, reg_data, len, 100);
	while((HAL_GPIO_ReadPin(e220_bus.aux_port, e220_bus.aux_pin) == GPIO_PIN_RESET) && (try < 20)){
		try++;
		HAL_Delay(1);
	}
}

void e220_read_reg(e220_pins_t pin){

}
