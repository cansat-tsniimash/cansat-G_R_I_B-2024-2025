/*
 * collect.h
 *
 *  Created on: Nov 12, 2024
 *      Author: user
 */

#ifndef COLLECT_H_
#define COLLECT_H_

#include <stdint.h>
#include <stdio.h>
#include <math.h>

#include <stm32f1xx.h>

int megalux(ADC_HandleTypeDef* hadc, float *minilux);

#endif /* COLLECT_H_ */
