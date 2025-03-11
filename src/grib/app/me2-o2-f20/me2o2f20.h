/*
 * me2o2f20.h
 *
 *  Created on: 21 февр. 2025 г.
 *      Author: user
 */

#ifndef ME2_O2_F20_ME2O2F20_H_
#define ME2_O2_F20_ME2O2F20_H_

#include <stdio.h>
#include <math.h>
#include <stdint.h>
#include <stm32f1xx.h>

int me2o2f20_read(ADC_HandleTypeDef* hadc, float *o2_percent);

#endif /* ME2_O2_F20_ME2O2F20_H_ */
