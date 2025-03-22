/*
 * mq4.c
 *
 *  Created on: Feb 15, 2025
 *      Author: user
 */

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

