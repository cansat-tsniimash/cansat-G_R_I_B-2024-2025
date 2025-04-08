/*
 * me2o2f20.c
 *
 *  Created on: 21 февр. 2025 г.
 *      Author: user
 */

#include "me2o2f20.h"

#define RL (100000.0f);
#define SENSITIVITY (9.52e-6f);

int me2o2f20_read(ADC_HandleTypeDef* hadc, float *o2_percent){
	HAL_StatusTypeDef rc;

	rc = HAL_ADC_Start(hadc);
	if(rc != HAL_OK) return rc;

	rc = HAL_ADC_PollForConversion(hadc, 100);
	if(rc != HAL_OK) return rc;

	uint32_t aboba_o2 = HAL_ADC_GetValue(hadc);

	float voltage = ((float)aboba_o2 / 4095.0f) * 3.3f;
	//float sensor_current = voltage / RL;
	//float oxygen_percentage = sensor_current / SENSITIVITY;

	//*o2_percent = oxygen_percentage;
	*o2_percent = voltage;

	rc = HAL_ADC_Stop(hadc);

	return rc;
}
