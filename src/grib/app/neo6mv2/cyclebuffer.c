/*
 * cyclebuffer.c
 *
 *  Created on: 14 мар. 2025 г.
 *      Author: user
 */

#include "cyclebuffer.h"

void sbuffer_init(cbuffer_t* this){
	this->head = 0;
	this->tail = 0;
}

int sbuffer_push(cbuffer_t* this, uint8_t byte){
	this->data[this->head] = byte;
	this->head = (this->head+1) % SBUFFER_SIZE;
	if(this->head == this->tail){
		this->tail = (this->tail+1) % SBUFFER_SIZE;
	}
	return 0;
}

int sbuffer_pop(cbuffer_t* this){
	__disable_irq();

	if(this->head == this->tail)
	{
		__enable_irq();
		return -1;
	}

	int rv = this->data[this->tail];
	this->tail = (this->tail + 1) % SBUFFER_SIZE;

	__enable_irq();
	return rv;
}


int sbuffer_peek(cbuffer_t* this)
{
	__disable_irq();

	if(this->head == this->tail )
		return -1;


	int rv = this->data[this->tail];
	__enable_irq();
	return rv;
}


int sbuffer_size(cbuffer_t* this){
	if(this->tail > this->head){
		return SBUFFER_SIZE + this->head - this->tail;
	} else {
		return this->head - this->tail;
	}
}

