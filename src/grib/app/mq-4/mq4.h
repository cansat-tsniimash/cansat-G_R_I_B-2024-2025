/*
 * mq4.h
 *
 *  Created on: Feb 15, 2025
 *      Author: user
 */

#ifndef MQ_4_MQ4_H_
#define MQ_4_MQ4_H_

#include <stdio.h>
#include <math.h>
#include <stdint.h>
#include <stm32f1xx.h>

int mq4_ppm(ADC_HandleTypeDef* hadc, float *mq4_ppm);

#endif /* MQ_4_MQ4_H_ */
