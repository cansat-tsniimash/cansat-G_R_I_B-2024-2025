/*
 * e220_400t22s.h
 *
 *  Created on: 7 февр. 2025 г.
 *      Author: user
 */

#ifndef E220400T22S_E220_400T22S_H_
#define E220400T22S_E220_400T22S_H_

#include <stdio.h>
#include <math.h>
#include <stdint.h>
#include <stm32f1xx.h>

typedef struct{
	GPIO_TypeDef *m0_port;
	GPIO_TypeDef *m1_port;
	uint16_t m0_pinchik;
	uint16_t m1_pinchik;
	UART_HandleTypeDef *uart;

}e220_pins_t;

void e220_write_reg(e220_pins_t pin, uint8_t *reg_data ,uint8_t reg_addr);

#endif /* E220400T22S_E220_400T22S_H_ */
