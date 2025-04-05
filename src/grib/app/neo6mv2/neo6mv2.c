/*
 * neo6mv2.c
 *
 *  Created on: 7 мар. 2025 г.
 *      Author: user
 */

#include "neo6mv2.h"

#include "cyclebuffer.h"


#define NEO6M2_RXBUFFER_SIZE (128)

static GPS_Data gpsData;
static char rxBuffer[NEO6M2_RXBUFFER_SIZE];
static uint8_t rxIndex = 0;
static uint8_t lineReady = 0;
static char nmeaLine[128];
static cbuffer_t gps_buffer;

extern float ne06mv2_height;
extern float ne06mv2_longitude;
extern float ne06mv2_latitude;

void neo6mv2_Init(){
    gpsData.latitude = 0.0f;
    gpsData.longitude = 0.0f;
    gpsData.altitude = 0.0f;
    gpsData.speed = 0.0f;
    gpsData.satellites = 0;
    gpsData.fixQuality = 0;
    gpsData.cookie = 0;
    strcpy(gpsData.time, "000000.00");
    strcpy(gpsData.date, "010100");

    sbuffer_init(&gps_buffer);
}

int neo6mv2_work()
{
	int i;

	while(1){
		if (rxIndex >= NEO6M2_RXBUFFER_SIZE)
			break;

		int candidate = sbuffer_pop(&gps_buffer);
		if (candidate < 0)
			break;

		rxBuffer[rxIndex] = candidate;
		rxIndex++;
	}

	while(rxIndex > 5 && rxBuffer[0] != '$')
	{
		for (int i = 0; i < rxIndex - 1; i++)
			rxBuffer[i] = rxBuffer[i+1];
		rxIndex--;
	}

	uint8_t flag = 0;

	for(i = 0; i < rxIndex; i++){
		if(rxBuffer[i] == '\n'){
			flag = 1;
			rxBuffer[i] = '\0';
			break;
		}
	}
	if ((!flag) && (rxIndex < NEO6M2_RXBUFFER_SIZE))
		return 1;



	neo6mv2_ParseLine(rxBuffer);

	rxBuffer[0] = 0;
	for (int j = 0; j < rxIndex - i; j++)
		rxBuffer[j] = rxBuffer[j+i];
	rxIndex -= i;
	return 0;

}


void neo6mv2_pushbyte(uint8_t byte){
	sbuffer_push(&gps_buffer, byte);
}

//char TEST_BUFF[200] = "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47";

uint8_t neo6mv2_ParseLine(char* line){
	char buf[6] = "GPGGA";
	for (int i = 0; i < 5; i++)
		if (line[i + 1] != buf[i])
			return 0;

    gpsData.cookie++;
	return neo6mv2_ParseGPGGA(line);
    /*if (strstr(line, "$GPRMC")) {
        //return neo6mv2_ParseGPRMC(line);
    } else if (strstr(line, "$GPGGA")){
        return neo6mv2_ParseGPGGA(line);
    }*/
    return 0;
}

static float neo6mv2_nmeaindecimal(char* coordinate, char dir) {
    float result = 0.0f;
    int degrees = 0;
    float minutes = 0.0f;
    int i = 0;
    int decimal = 0;
    float factor = 0.1f;

    if(dir == 'N' || dir == 'S') {
    	degrees = (coordinate[0] - '0') * 10 + (coordinate[1] - '0');
    	i = 2;
    }
    else
    {
        degrees = (coordinate[0] - '0') * 100 + (coordinate[1] - '0') * 10 + (coordinate[2] - '0');
        i = 3;
    }
    for(; coordinate[i] != '\0'; i++){
        if (coordinate[i] == '.'){
            decimal = 1;
        }
        else if (coordinate[i] >= '0' && coordinate[i] <= '9'){
            if (decimal){
                minutes += (coordinate[i] - '0') * factor;
                factor *= 0.1f;
            }
            else
            {
                minutes = minutes * 10 + (coordinate[i] - '0');
            }
        }
    }

    result = degrees + minutes/60.0f;
    if (dir == 'S' || dir == 'W'){
        result = -result;
    }
    return result;
}

uint8_t neo6mv2_ParseGPGGA(char* line){
    char latStr[15] = {0};
    char lonStr[15] = {0};
    char latDir = 0, lonDir = 0;
    int i = 0, field = 0, pos = 0;
    float alt = 0;
    int decimal = 0;
    float factor = 0.1f;

    latStr[0] = '\0';
    lonStr[0] = '\0';

    for(i = 0; line[i] != '\0'; i++) {
        if(line[i] == ',') {
            field++;
            pos = 0;
            continue;
        }

        switch(field) {
            case 0:
                break;
            case 1:
                break;
            case 2:
                if(pos < 14) {
                    latStr[pos] = line[i];
                    latStr[pos + 1] = '\0';
                }
                break;
            case 3:
                latDir = line[i];
                break;
            case 4:
                if(pos < 14) {
                    lonStr[pos] = line[i];
                    lonStr[pos + 1] = '\0';
                }
                break;
            case 5:
                lonDir = line[i];
                break;
            case 6:
                if(pos == 0){
                    gpsData.fixQuality = line[i] - '0';
                }
                break;
            case 7:
                break;
            case 8:
                break;
            case 9:
                if(line[i] == '.') {
                    decimal = 1;
                } else if(line[i] >= '0' && line[i] <= '9'){
                    if(decimal) {
                        alt += (line[i] - '0') * factor;
                        factor *= 0.1f;
                    } else {
                        alt = alt * 10 + (line[i] - '0');
                    }
                }
                break;
        }
        pos++;
    }

    if(latStr[0] != '\0' && lonStr[0] != '\0' && latDir != 0 && lonDir != 0){
        gpsData.latitude = neo6mv2_nmeaindecimal(latStr, latDir);
        gpsData.longitude = neo6mv2_nmeaindecimal(lonStr, lonDir);
        gpsData.altitude = alt;
        return 1;
    }

    return 0;
}

GPS_Data neo6mv2_GetData(void){
    if (lineReady) {
        neo6mv2_ParseLine(nmeaLine);
        lineReady = 0;
    }
    return gpsData;
}
