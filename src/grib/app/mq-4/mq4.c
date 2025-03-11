/*
 * mq4.c
 *
 *  Created on: Feb 15, 2025
 *      Author: user
 */

/*#include "mq4.h"

#define PL (20000.0f) // в даташите пункт load resistance 20 ТЫСЯЧ ОМЕГА
#define R0 (4000.0f) // сопротивление датчика в воздухе в омах

int mq4_ppm(ADC_HandleTypeDef* hadc, float *mq4_ppm){
	HAL_StatusTypeDef rc;

	rc = HAL_ADC_Start(hadc);
	if(rc != HAL_OK) return rc;

	rc = HAL_ADC_PollForConversion(hadc, 100);
	if(rc != HAL_OK) return rc;
	uint32_t aboba_mq4 = HAL_ADC_GetValue(hadc);
	float abobatovoltage = aboba_mq4 / 4095.0f * 3.3f; // ADC to напряжение

	float abobars = (3.3f - abobatovoltage) * PL / abobatovoltage; // считаем сопротивление
	float abobaotnoshenie = abobars / R0;

	float naklon = -0.374f;
	float smeshenie = 1.101f;

	float aboba_ppm = pow(10, (log10(abobaotnoshenie) - smeshenie) / naklon);
	*mq4_ppm = aboba_ppm;

	rc = HAL_ADC_Stop(hadc);

	return rc;
}*/

#include "mq4.h"

#define PL (20000.0f)
#define R0 (4000.0f)

#define NAKLON (-0.374f)
#define SMESHENIE (1.101f)

#define SCALE (powf(10, -SMESHENIE / NAKLON))

int mq4_ppm(ADC_HandleTypeDef* hadc, float *mq4_ppm) {
    HAL_StatusTypeDef rc;

    if ((rc = HAL_ADC_Start(hadc)) != HAL_OK) return rc;
    if ((rc = HAL_ADC_PollForConversion(hadc, 100)) != HAL_OK) return rc;

    uint32_t raw_adc = HAL_ADC_GetValue(hadc);
    HAL_ADC_Stop(hadc);

    float voltage = raw_adc * (3.3f / 4095.0f);

    float sensor_resistance = (3.3f - voltage) * PL / voltage;

    float ratio = sensor_resistance / R0;

    *mq4_ppm = powf(ratio, 1.0f / NAKLON) * SCALE;

    return HAL_OK;
}

