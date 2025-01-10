/*
 * onewire.h
 *
 *  Created on: Nov 15, 2024
 *      Author: user
 */

#ifndef ONEWIRE_H_
#define ONEWIRE_H_

#include <stm32f1xx.h>

typedef enum{
	DS18B20_RES_93P75MS = 0,
	DS18B20_RES_187P5MS = 1,
	DS18B20_RES_375MS = 2,
	DS18B20_RES_750MS = 3
}DS18B20_RES_t;

typedef struct{
	GPIO_TypeDef *port;
	uint16_t pinchik;
} one_wire_bus_t;

int one_wire_init(one_wire_bus_t bus);
void one_wire_start_convertion(one_wire_bus_t bus);
uint16_t ds18b20_read_temp(one_wire_bus_t bus);
void ds18b20_write_config(one_wire_bus_t bus, DS18B20_RES_t res);

#endif /* ONEWIRE_H_ */
