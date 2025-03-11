/*
 * neo6mv2.c
 *
 *  Created on: 7 мар. 2025 г.
 *      Author: user
 */

#include "neo6mv2.h"

static UART_HandleTypeDef* GPS_UART;
static GPS_Data gpsData;
static char rxBuffer[128];
static uint8_t rxIndex = 0;
static uint8_t lineReady = 0;
static char nmeaLine[128];

extern float ne06mv2_height;
extern float ne06mv2_longitude;
extern float ne06mv2_latitude;

void neo6mv2_Init(UART_HandleTypeDef *huart){
    GPS_UART = huart;

    gpsData.latitude = 0.0f;
    gpsData.longitude = 0.0f;
    gpsData.altitude = 0.0f;
    gpsData.speed = 0.0f;
    gpsData.satellites = 0;
    gpsData.fixQuality = 0;
    strcpy(gpsData.time, "000000.00");
    strcpy(gpsData.date, "010100");

    ne06mv2_height = 0.0f;
    ne06mv2_longitude = 0.0f;
    ne06mv2_latitude = 0.0f;

    HAL_UART_Receive_IT(GPS_UART, (uint8_t*)&rxBuffer[rxIndex], 1);
}

void neo6mv2_UART_RxCallback(void){
    if (rxBuffer[rxIndex] == '\n'){
        rxBuffer[rxIndex] = '\0';

        if (rxIndex > 5 && rxBuffer[0] == '$'){
            strcpy(nmeaLine, rxBuffer);
            lineReady = 1;
        }
        rxIndex = 0;
    } else if (rxBuffer[rxIndex] == '\r'){
    } else {
        rxIndex++;
        if (rxIndex >= sizeof(rxBuffer) - 1){
            rxIndex = 0;
        }
    }
    HAL_UART_Receive_IT(GPS_UART, (uint8_t*)&rxBuffer[rxIndex], 1);
}

uint8_t neo6mv2_ParseLine(char* line){
    if (strstr(line, "$GPRMC")) {
        return neo6mv2_ParseGPRMC(line);
    } else if (strstr(line, "$GPGGA")){
        return neo6mv2_ParseGPGGA(line);
    }
    return 0;
}

static float neo6mv2_nmeaindecimal(char* coordinate, char dir) {
    float result = 0.0f;
    int degrees = 0;
    float minutes = 0.0f;

    if (dir == 'N' || dir == 'S') {
        degrees = (coordinate[0] - '0') * 10 + (coordinate[1] - '0');
        minutes = atof(&coordinate[2]);
    } else {
        degrees = (coordinate[0] - '0') * 100 + (coordinate[1] - '0') * 10 + (coordinate[2] - '0');
        minutes = atof(&coordinate[3]);
    }
    result = degrees + minutes/60.0f;
    if (dir == 'S' || dir == 'W'){
        result = -result;
    }
    return result;
}

uint8_t neo6mv2_ParseGPRMC(char* line) {
    char* token;
    char* ptr = line;
    int tokenIndex = 0;
    char latStr[15];
    char lonStr[15];
    char latDir, lonDir;

    while ((token = strtok(ptr, ",")) != NULL){
        ptr = NULL;
        switch (tokenIndex){
            case 1:
                strncpy(gpsData.time, token, sizeof(gpsData.time)-1);
                gpsData.time[sizeof(gpsData.time)-1] = '\0';
                break;
            case 2:
                if (token[0] != 'A'){
                    return 0;
                }
                break;
            case 3:
                strcpy(latStr, token);
                break;
            case 4:
                latDir = token[0];
                break;
            case 5:
                strcpy(lonStr, token);
                break;
            case 6:
                lonDir = token[0];
                break;
            case 7:
                gpsData.speed = atof(token) * 1.852f;
                break;
            case 9:
                strncpy(gpsData.date, token, sizeof(gpsData.date)-1);
                gpsData.date[sizeof(gpsData.date)-1] = '\0';
                break;
        }
        tokenIndex++;
    }
    if (tokenIndex > 9 && latStr[0] != '\0' && lonStr[0] != '\0'){
        gpsData.latitude = neo6mv2_nmeaindecimal(latStr, latDir);
        gpsData.longitude = neo6mv2_nmeaindecimal(lonStr, lonDir);

        ne06mv2_latitude = gpsData.latitude;
        ne06mv2_longitude = gpsData.longitude;

        return 1;
    }
    return 0;
}

uint8_t neo6mv2_ParseGPGGA(char* line){
    char* token;
    char* ptr = line;
    int tokenIndex = 0;
    char latStr[15];
    char lonStr[15];
    char latDir, lonDir;

    while ((token = strtok(ptr, ",")) != NULL){
        ptr = NULL;

        switch (tokenIndex) {
            case 2:
                strcpy(latStr, token);
                break;
            case 3:
                latDir = token[0];
                break;
            case 4:
                strcpy(lonStr, token);
                break;
            case 5:
                lonDir = token[0];
                break;
            case 6:
                gpsData.fixQuality = atoi(token);
                break;
            case 7:
                gpsData.satellites = atoi(token);
                break;
            case 9:
                gpsData.altitude = atof(token);
                ne06mv2_height = gpsData.altitude;
                break;
        }

        tokenIndex++;
    }
    if (tokenIndex > 9 && latStr[0] != '\0' && lonStr[0] != '\0'){
        gpsData.latitude = neo6mv2_nmeaindecimal(latStr, latDir);
        gpsData.longitude = neo6mv2_nmeaindecimal(lonStr, lonDir);
        ne06mv2_latitude = gpsData.latitude;
        ne06mv2_longitude = gpsData.longitude;
        return 1;
    }
    return 0;
}
GPS_Data neo6mv2_GetData(void){
    if (lineReady) {
        neo6mv2_ParseLine(nmeaLine);
        lineReady = 0;
        ne06mv2_height = gpsData.altitude;
        ne06mv2_longitude = gpsData.longitude;
        ne06mv2_latitude = gpsData.latitude;
    }
    return gpsData;
}
