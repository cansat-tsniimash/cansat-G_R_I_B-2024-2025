/*
 * neo6mv.h
 *
 *  Created on: 7 мар. 2025 г.
 *      Author: user
 */

#ifndef NEO6MV2_NEO6MV2_H_
#define NEO6MV2_NEO6MV2_H_



#endif /* NEO6MV2_NEO6MV2_H_ */

#include <stdio.h>
#include <math.h>
#include <stdint.h>
#include <stm32f1xx.h>
#include <string.h>
#include <stdlib.h>

typedef struct {
    float latitude;
    float longitude;
    float altitude;
    float speed;
    int satellites;
    int fixQuality;
    char time[10];
    char date[7];
} GPS_Data;

void neo6mv2_Init();

void neo6mv2_pushbyte(uint8_t byte);

uint8_t neo6mv2_ParseLine(char* line);

GPS_Data neo6mv2_GetData(void);

void neo6mv2_work();

uint8_t neo6mv2_ParseGPRMC(char* line);
uint8_t neo6mv2_ParseGPGGA(char* line);
