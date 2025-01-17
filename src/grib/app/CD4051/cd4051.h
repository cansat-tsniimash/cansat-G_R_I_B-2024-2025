/*
 * cd4051.h
 *
 *  Created on: Jan 17, 2025
 *      Author: user
 */

#ifndef CD4051_CD4051_H_
#define CD4051_CD4051_H_

#include <stdint.h>
#include <stdio.h>
#include <math.h>

#include <stm32f1xx.h>

#define A_PORT (GPIOC)
#define A_PIN13 (GPIO_PIN_13)
#define A_PIN14 (GPIO_PIN_14)
#define A_PIN15 (GPIO_PIN_15)

void cd4051_change_ch(uint8_t ch);

#endif /* CD4051_CD4051_H_ */
