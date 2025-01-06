/*
 * dwt_delay.h
 *
 *  Created on: Nov 15, 2024
 *      Author: user
 */

#ifndef DWT_DELAY_H_
#define DWT_DELAY_H_

int dwt_delay_init(void);
// ждет..
void dwt_delay_us(uint32_t pause_us);
// инициализирует.....
void dwt_delay_ms(uint32_t pause_ms);


#endif /* DWT_DELAY_H_ */
