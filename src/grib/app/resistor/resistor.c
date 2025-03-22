/*
 * resistor.c
 *
 *  Created on: Nov 12, 2024
 *      Author: user
 */

#include "resistor.h"
#include <math.h>

#define RESISTOR (10000.0)

int megalux(ADC_HandleTypeDef* hadc, float *minilux) {
    HAL_StatusTypeDef rc = HAL_ADC_Start(hadc);
    if(rc != HAL_OK) return rc;

    rc = HAL_ADC_PollForConversion(hadc, 100);
    if(rc != HAL_OK) return rc;

    uint32_t adc_val = HAL_ADC_GetValue(hadc);
    float voltage = adc_val / 4095.0f * 3.3f;
    float resistor_value = voltage * RESISTOR / (3.3f - voltage);
    float ratio = resistor_value / 1000.0f;

    const float factor = 10.764f * expf(3.823f / 0.816f);
    const float exponent = -1.0f / 0.816f;
    *minilux = factor * powf(ratio, exponent);

    rc = HAL_ADC_Stop(hadc);
    return rc;
}

