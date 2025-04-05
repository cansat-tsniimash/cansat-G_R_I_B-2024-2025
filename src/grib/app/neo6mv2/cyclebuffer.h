/*
 * cyclebuffer.h
 *
 *  Created on: 14 мар. 2025 г.
 *      Author: user
 */

#ifndef NEO6MV2_CYCLEBUFFER_H_
#define NEO6MV2_CYCLEBUFFER_H_

#include <stdio.h>
#include <math.h>
#include <stdint.h>
#include <stm32f1xx.h>
#include <string.h>
#include <stdlib.h>

#define SBUFFER_SIZE (1000)

typedef struct cbuffer_t{
	uint8_t data[SBUFFER_SIZE];
    size_t head;
    size_t tail;
} cbuffer_t;


void sbuffer_init(cbuffer_t* this);
int sbuffer_push(cbuffer_t* this, uint8_t byte);
int sbuffer_pop(cbuffer_t* this);
int sbuffer_peek(cbuffer_t* this);
int sbuffer_size(cbuffer_t* this);


#endif /* NEO6MV2_CYCLEBUFFER_H_ */
