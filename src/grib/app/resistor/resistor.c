/*
 * resistor.c
 *
 *  Created on: Nov 12, 2024
 *      Author: user
 */

#include "resistor.h"

#define RESISTOR (10000.0)

int megalux(ADC_HandleTypeDef* hadc, float *minilux){
	HAL_StatusTypeDef rc;
	rc = HAL_ADC_Start(hadc);
	if(rc != HAL_OK) return rc;

	rc = HAL_ADC_PollForConversion(hadc, 100);
	if(rc != HAL_OK) return rc;
	uint32_t aboba = HAL_ADC_GetValue(hadc);
	float zov = aboba / 4095.0 * 3.3;
	float zzzz = zov*(RESISTOR)/(3.3-zov);
	*minilux = exp((3.823 - log(zzzz/1000.0))/0.816)*10.764;
	rc = HAL_ADC_Stop(hadc);

	printf("Hi! UART %f\n", zov);

	return rc;
}
