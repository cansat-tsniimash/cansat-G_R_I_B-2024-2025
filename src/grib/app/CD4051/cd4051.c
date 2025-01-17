/*
 * cd4051.c
 *
 *  Created on: Jan 17, 2025
 *      Author: user
 */

#include "cd4051.h"

void cd4051_change_ch(uint8_t ch){
	uint8_t A = ch & (1 << 0);
    uint8_t B = ch & (1 << 1);
    uint8_t C = ch & (1 << 2);

    // MUX A
    if (A) {
        HAL_GPIO_WritePin(A_PORT, A_PIN13, GPIO_PIN_SET);
    } else {
        HAL_GPIO_WritePin(A_PORT, A_PIN13, GPIO_PIN_RESET);
    }
    // MUX B
    if (B) {
        HAL_GPIO_WritePin(A_PORT, A_PIN14, GPIO_PIN_SET);
    } else {
        HAL_GPIO_WritePin(A_PORT, A_PIN14, GPIO_PIN_RESET);
    }
    // MUX C
    if (C) {
        HAL_GPIO_WritePin(A_PORT, A_PIN15, GPIO_PIN_SET);
    } else {
        HAL_GPIO_WritePin(A_PORT, A_PIN15, GPIO_PIN_RESET);
    }
}
