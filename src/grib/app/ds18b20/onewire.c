/*
 * onewire.c
 *
 *  Created on: Nov 15, 2024
 *      Author: user
 */

#include <stdint.h>
#include <stdio.h>
#include <math.h>

#include "..\dwt_delay.h"
#include "onewire.h"
#include <stm32f1xx.h>
#include <stdbool.h>

#define  GPIO_CR_MODE_INPUT         0x00000000u /*!< 00: Input mode (reset state)  */
#define  GPIO_CR_CNF_INPUT_FLOATING 0x00000004u /*!< 01: Floating input (reset state)  */



int one_wire_init(one_wire_bus_t bus){

	dwt_delay_init();
	GPIO_InitTypeDef pin_init = {0};
	pin_init.Mode = GPIO_MODE_INPUT;
	pin_init.Pin = bus.pinchik;
	pin_init.Pull = GPIO_NOPULL;
	pin_init.Speed = GPIO_SPEED_FREQ_HIGH;
	HAL_GPIO_Init(bus.port, &pin_init);


	HAL_GPIO_WritePin(bus.port, bus.pinchik, GPIO_PIN_RESET);
	return 0;
}

void one_wire_force_down(one_wire_bus_t bus){
	GPIO_InitTypeDef pin_init = {0};
	pin_init.Mode = GPIO_MODE_OUTPUT_OD;
	pin_init.Pin = bus.pinchik;
	pin_init.Pull = GPIO_NOPULL;
	pin_init.Speed = GPIO_SPEED_FREQ_HIGH;
	HAL_GPIO_Init(bus.port, &pin_init);
	HAL_GPIO_WritePin(bus.port, bus.pinchik, GPIO_PIN_RESET);

}

void one_wire_release(one_wire_bus_t bus){
	uint32_t position = 0x00u;
	uint32_t config = 0x00u;
	__IO uint32_t *configregister; /* Store the address of CRL or CRH register based on pin number */
	uint32_t registeroffset;       /* offset used during computation of CNF and MODE bits placement inside CRL or CRH register */

	  /* Configure the port pins */
	while(((bus.pinchik) >> position) != 0x00u)
	{
		position++;
	}
	position--;
	/* Get the current IO position */
	//iocurrent = (uint32_t)(pin_init.Pin) & (0x01uL << position);

	config = GPIO_CR_MODE_INPUT + GPIO_CR_CNF_INPUT_FLOATING;

	/* Check if the current bit belongs to first half or last half of the pin count number
	 in order to address CRH or CRL register*/
	configregister = (bus.pinchik < GPIO_PIN_8) ? &bus.port->CRL     : &bus.port->CRH;
	registeroffset = (bus.pinchik < GPIO_PIN_8) ? (position << 2u) : ((position - 8u) << 2u);

	/* Apply the new configuration of the pin to the register */
	MODIFY_REG((*configregister), ((GPIO_CRL_MODE0 | GPIO_CRL_CNF0) << registeroffset), (config << registeroffset));

}

void one_wire_write_bit(one_wire_bus_t bus, bool value){
	if(value == 0){
		one_wire_force_down(bus);
		dwt_delay_us(60 - 10);
		one_wire_release(bus);
	}
	else{
		one_wire_force_down(bus);
		dwt_delay_us(2);
		one_wire_release(bus);
		dwt_delay_us(60 - 2);
	}
}

int one_wire_read_bit(one_wire_bus_t bus){
	one_wire_force_down(bus);
	dwt_delay_us(2);
	one_wire_release(bus);
	dwt_delay_us(10);
	int res = HAL_GPIO_ReadPin(bus.port, bus.pinchik) == GPIO_PIN_SET;
	dwt_delay_us(40);
	return res;
}

int one_wire_reset(one_wire_bus_t bus){
	one_wire_force_down(bus);
	dwt_delay_us(500);
	one_wire_release(bus);
	dwt_delay_us(70);
	int result = HAL_GPIO_ReadPin(bus.port, bus.pinchik) == GPIO_PIN_SET;
	dwt_delay_us(410);
	return result;
}

void one_wire_write_byte(one_wire_bus_t bus, char byte){
	for(int i = 0; i < 8; i++){
		one_wire_write_bit(bus, byte & (1 << i));
	}
}

int one_wire_read_byte(one_wire_bus_t bus){
	char byte = 0;
	for(int i = 0; i < 8; i++){
		byte = byte | (one_wire_read_bit(bus) << i);
	}
	return byte;
}

void one_wire_write(one_wire_bus_t bus, uint8_t *poof, uint16_t mnogochisel){
	for(int i = 0; i < mnogochisel; i++){
		one_wire_write_byte(bus, *(i + poof));
	}
}

void one_wire_read(one_wire_bus_t bus, uint8_t *poof, uint16_t mnogochisel){
	for(int i = 0; i < 8; i++){
		*(poof + i) = one_wire_read_byte(bus);
	}
}

void one_wire_skip_rom(one_wire_bus_t bus){
	one_wire_write_byte(bus, 0xCC);
}

void one_wire_start_convertion(one_wire_bus_t bus){
	one_wire_reset(bus);
	one_wire_skip_rom(bus);
	one_wire_write_byte(bus, 0x44);
}

uint16_t ds18b20_read_temp(one_wire_bus_t bus){
	uint8_t poof[8] = {0};
	uint16_t temp = 0;
	one_wire_reset(bus);
	one_wire_skip_rom(bus);
	one_wire_write_byte(bus, 0xBE);
	one_wire_read(bus, poof, 8);
	temp = poof[0] | (poof[1] << 8);

	return temp;
}

void ds18b20_write_config(one_wire_bus_t bus, DS18B20_RES_t res){
	uint8_t poof[3] = {0};
	poof[2] = (res << 5 ) | 0x1F;
	one_wire_reset(bus);
	one_wire_skip_rom(bus);
	one_wire_write_byte(bus, 0x4E);
	one_wire_write(bus, poof, 3);
}



