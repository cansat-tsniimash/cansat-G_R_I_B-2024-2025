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

    *minilux = voltage;

    rc = HAL_ADC_Stop(hadc);
    return rc;
}

/*
 * resistor.c
 *
 *  Created on: Nov 12, 2024
 *      Author: user
 */

/*#include "resistor.h"
#include <math.h>

#define RESISTOR       (10000.0f)
#define ADC_REF        (3.3f)
#define ADC_MAX        (4095.0f)
#define CONVERSION     (ADC_REF / ADC_MAX)
#define LUX_FACTOR     (1162.77f)
#define EXPONENT       (-1.22549f)

int megalux(ADC_HandleTypeDef* hadc, float *minilux) {
    HAL_StatusTypeDef rc = HAL_ADC_Start(hadc);
    if(rc != HAL_OK) return rc;

    rc = HAL_ADC_PollForConversion(hadc, 100);
    if(rc != HAL_OK) return rc;

    uint32_t adc_val = HAL_ADC_GetValue(hadc);
    float voltage = adc_val * CONVERSION;
    float ratio = (RESISTOR * voltage / (ADC_REF - voltage)) / 1000.0f;
    *minilux = LUX_FACTOR * powf(ratio, EXPONENT);
    *minilux = voltage;

    rc = HAL_ADC_Stop(hadc);
    return rc;
}*/

