/*
 * appmain.c
 *
 *  Created on: Jan 6, 2025
 *      Author: norfa
 */

/*
 * (проверить)

 * lis3mdl (работает)
 * me2o2f20 (проверить)
 * mq-4 (проверить)
 *
 * (готово и работает)
 * пьезодинамик (пины поменял / работает)
 * пережигатель (пины поменял)
 * scd41 (работает)
 * e220-400t22s (работает, но надо доделать наземку)
 * micro-sd (работает)
 * neo6mv2 (работает)
 * bmp280 (работает)
 * lsm6ds3 (работает)
 * ds18b20 (работает)
 * фоторезистор (работает)
 * переключатель (работает)
 *
 * оптимизация кода (ВАЖНО!)
 */

#include <stm32f1xx.h>

#include <stdint.h>
#include <stdio.h>
#include <math.h>
#include <stdbool.h>

#include "lsm6ds3\lsm6ds3.h" // датчик lsm6ds3 (I2C)
#include "lis3mdl\lis3mdl.h" // датчик lis3mdl (I2C)
#include "scd41\scd41.h" // датчик co2 (I2C)

#include "resistor\resistor.h" // фоторезистор (ADC)
#include "me2-o2-f20\me2o2f20.h" // ME2-O2-Ф20 (ADC)
#include "mq-4\mq4.h" // mq-4 (ADC)

#include "neo6mv2\neo6mv2.h" // датчик gps (UART)
#include "e220400t22s/e220_400t22s.h" // радио (UART)

#include "ds18b20\onewire.h" // датчик ds18b20 (1-WIRE)

#include "fatfs_sd\fatfs_sd.h" // micro sd (SPI)
#include "..\Middlewares\Third_Party\FatFs\src\ff.h" // micro sd (SPI)

#include "bmp280/bmp.h" // датчик BMP280 (I2C)
#include "cd4051/cd4051.h" // мультиплексор
#include "dwt_delay.h" // тайминги

#define PIEZOSPEAKER_PIN GPIO_PIN_0
#define PIEZOSPEAKER_PORT GPIOA
я
#define BURNER_PIN GPIO_PIN_4
#define BURNER_PORT GPIOB

#define SWITCH_PIN GPIO_PIN_1
#define SWITCH_PORT GPIOA

// обработчики для ADC, I2C и UART1/UART2
extern ADC_HandleTypeDef hadc1;
extern I2C_HandleTypeDef hi2c1;
extern UART_HandleTypeDef huart2;
extern UART_HandleTypeDef huart1;

typedef enum{
	MS_PREPARATION = 0, // подготовка
	MS_BEFORE_LAYING = 1, // до укладки
	MS_FLIGHT_IN_THE_ROCKET = 2, // в ракете
	MS_DESCENT_A = 3, // Спуск A
	MS_DESCENT_B = 4, // Спуск B
	MS_DESCENT_C = 5, // Спуск C
	MS_ROUT = 6 // разгром

} mission_state_t;

// Вычисление контрольной суммы массива байтов
uint8_t xorBlock(const uint8_t *data, size_t size) {
    uint8_t result = 0x00;

    for (size_t i = 0; i < size; i++) {
        result ^= data[i];
    }

    return result;
}

// пьезодинамик

void piezospeaker_status(uint8_t status){
	if(status == 1){
		HAL_GPIO_WritePin(PIEZOSPEAKER_PORT, PIEZOSPEAKER_PIN, GPIO_PIN_SET);
	}
	else{
		HAL_GPIO_WritePin(PIEZOSPEAKER_PORT, PIEZOSPEAKER_PIN, GPIO_PIN_RESET);
	}
}
// пережигатель

void burner_status(uint8_t status){
	if(status == 1){
		HAL_GPIO_WritePin(BURNER_PORT, BURNER_PIN, GPIO_PIN_SET);
	}
	else{
		HAL_GPIO_WritePin(BURNER_PORT, BURNER_PIN, GPIO_PIN_RESET);
	}
}

// структура для хранения данных с датчиков
typedef struct{
	uint8_t accel_error;
	uint8_t gyro_error;
	uint8_t magn_error;
	uint8_t lis_err;
	uint8_t lsm_err;
	uint8_t scd_temp;
} data_t;

// структура для хранения и передачи телеметрии
#pragma pack(push, 1) // Обращение к компилятору не выравнивать структуру и хранить её в памяти без пустых байтов
typedef struct{
	uint16_t start;
	uint16_t team_id;
	uint32_t time;
	int16_t temp_bmp280;
	uint32_t pressure_bmp280;
	int16_t acceleration_x;
	int16_t acceleration_y;
	int16_t acceleration_z;
	int16_t angular_x;
	int16_t angular_y;
	int16_t angular_z;
	uint8_t cheksum_org;
	uint16_t number_packet;
	uint8_t state;
	uint16_t photoresistor;
	int16_t lis3mdl_x;
	int16_t lis3mdl_y;
	int16_t lis3mdl_z;
	int16_t ds18b20;
	float neo6mv2_latitude;
	float neo6mv2_longitude;
	float neo6mv2_height;
	uint8_t neo6mv2_fix;
	uint16_t scd41;
	uint16_t mq_4;
	uint16_t me2o2;
	uint8_t checksum_grib;
} packet_t;
#pragma pack(pop) // Компилятор может добавлять выравнивающие байты для оптимизации работы процессора

void appmain(){
	burner_status(0);

	int i;
	piezospeaker_status(0);
	packet_t packet = {0};
	packet_t team_id = 0xD9;
	packet.start = 0xAAAA;
	packet.number_packet = 0;
	volatile data_t my_data;
	int16_t temp_gyro[3] = {0}; // temp = ВРЕМЕННО!
	int16_t temp_accel[3] = {0};

	// BMP280
	bme280_dev_t bmp;
	bmp.delay_us = bmp_delay;
	bmp.settings.filter = BME280_FILTER_COEFF_2;
	bmp.settings.osr_h = BME280_OVERSAMPLING_16X;
	bmp.settings.osr_p = BME280_OVERSAMPLING_16X;
	bmp.settings.osr_t = BME280_OVERSAMPLING_16X;
	bmp.settings.standby_time = BME280_STANDBY_TIME_500_MS;
	struct bme280_data data;
	bmp_init(&bmp, &hi2c1);

	bme280_get_sensor_data(BME280_ALL, &data, &bmp); // вывод давления и температуры
	float pressure_zero  = data.pressure;

	// LSM6DS3
	stmdev_ctx_t lsm;
	my_data.lsm_err = lsm_init(&lsm, &hi2c1);

	// LIS3MDL
	stmdev_ctx_t lis;
	my_data.lis_err = lis_init(&lis, &hi2c1);
	int16_t temp_magn[3] = {0};

	// DS18B20
	one_wire_bus_t bus;
	bus.port = GPIOA;
	bus.pinchik = GPIO_PIN_15;
	one_wire_init(bus);
	ds18b20_write_config(bus, DS18B20_RES_750MS);
	one_wire_start_convertion(bus);
	uint32_t get_time = HAL_GetTick();

	// sd
	FATFS fileSystem; // переменная типа FATFS
	FIL binFile;
	//csvFile; // хендлер файла
    UINT testBytes;  // Количество записанных байт

    FRESULT mount_res = 255;
    FRESULT bin_res = 255;
    //FRESULT csv_res = 255;
    uint8_t bin_path[] = "grib.bin\0";
    //uint8_t csv_path[] = "grib.csv\0";
    //char str_buffer[300] = {0};
    //char str_header[330] = "number_packet; time; temp_bmp280; pressure_bmp280; acceleration x; acceleration y; acceleration z; angular x; angular y; angular z; checksum_org; state; photoresistor; lis3mdl_x; lis3mdl_y; lis3mdl_z; ds18b20; ne06mv2_height; ne06mv2_latitude; ne06mv2_longitude; ne06mv2_height; ne06mv2_fix; scd41; mq_4; me2o2; checksum_grib;\n";
    /*int mount_attemps;
    for(mount_attemps = 0; mount_attemps < 5; mount_attemps++)
    {
    	mount_res = f_mount(&fileSystem, "0:", 0);
        if (mount_res == FR_OK) {
        	res = f_open(&binFile, "gribochek_raw.bin\0", FA_WRITE | FA_CREATE_ALWAYS);
        	break;
        }
    }*/

    //neo6mv2
    neo6mv2_Init();
    __HAL_UART_ENABLE_IT(&huart1, UART_IT_RXNE);
    __HAL_UART_ENABLE_IT(&huart1, UART_IT_ERR);

	// e220-400t22s
	e220_pins_t e220_bus;
	e220_bus.m0_pinchik = GPIO_PIN_1;
	e220_bus.m1_pinchik = GPIO_PIN_0;
	e220_bus.m0_port = GPIOB;
    e220_bus.m1_port = GPIOB;
    e220_bus.aux_pin = GPIO_PIN_3;
	e220_bus.aux_port = GPIOB;
    e220_bus.uart = &huart2;
    e220_set_mode(e220_bus, E220_MODE_DSM);

    e220_set_addr(e220_bus, 0xFFFF);
    HAL_Delay(100);
    e220_set_reg0(e220_bus, E220_REG0_AIR_RATE_9600, E220_REG0_PARITY_8N1_DEF, E220_REG0_PORT_RATE_9600);
    HAL_Delay(100);
    e220_set_reg1(e220_bus, E220_REG1_PACKET_LEN_200B, E220_REG1_RSSI_OFF, E220_REG1_TPOWER_22);
    HAL_Delay(100);
    e220_set_channel(e220_bus, 1);
    HAL_Delay(100);
    e220_set_reg3(e220_bus, E220_REG3_RSSI_BYTE_OFF, E220_REG3_TRANS_M_TRANSPARENT, E220_REG3_LBT_EN_OFF, E220_REG3_WOR_CYCLE_500);
    e220_set_mode(e220_bus, E220_MODE_TM);

    float result;
	float mq_result;
	float me2o2_result;

	float lux = 0;
	int lux_cnt = 0;

	uint32_t get_time_burner = HAL_GetTick();
	#define BURNER_TIME 3000
	mission_state_t device_condition = MS_PREPARATION;

	scd41_init(&hi2c1);
	volatile int time_last = HAL_GetTick();
	volatile int dt = HAL_GetTick() - time_last;

	while(1){
		//HAL_Delay(100);
		// BMP280
		bme280_get_sensor_data(BME280_ALL, &data, &bmp); // вывод давления и температуры
		packet.pressure_bmp280 = data.pressure;
		packet.temp_bmp280 = data.temperature * 100;
		float altitude = 44330 * (1- pow(data.pressure/pressure_zero, 1/5.255));

		dt = HAL_GetTick() - time_last;
		time_last = HAL_GetTick();

		// LSM6DS3
		my_data.gyro_error = lsm6ds3_angular_rate_raw_get(&lsm, temp_gyro);
		packet.angular_x = temp_gyro[0];
		packet.angular_y = temp_gyro[1];
		packet.angular_z = temp_gyro[2];

		my_data.accel_error = lsm6ds3_acceleration_raw_get(&lsm, temp_accel);
		packet.acceleration_x = temp_accel[0];
		packet.acceleration_y = temp_accel[1];
		packet.acceleration_z = temp_accel[2];
		// LIS3MDL
		my_data.magn_error = lis3mdl_magnetic_raw_get(&lis, temp_magn);
		packet.lis3mdl_x = temp_magn[0];
		packet.lis3mdl_y = temp_magn[1];
		packet.lis3mdl_z = temp_magn[2];

		//DS18B20
		if(get_time + 750 < HAL_GetTick()){
			get_time = HAL_GetTick();
			packet.ds18b20 = ds18b20_read_temp(bus);
			one_wire_start_convertion(bus);
		}
		dt = HAL_GetTick() - time_last;
		time_last = HAL_GetTick();
		/*
		 * мультиплексор
		 * (1) - фоторезистор
		 * (2) - датчик метана
		 * (3) - датчик кислорода
		 */


		// (1)
		cd4051_change_ch(0);
		megalux(&hadc1, &result);
		packet.photoresistor = result * 1000;
		// (2)
		cd4051_change_ch(4);
		mq4_ppm(&hadc1, &mq_result);
		packet.mq_4 = mq_result * 1000;

		// (3)
		cd4051_change_ch(7);
		me2o2f20_read(&hadc1, &me2o2_result);
		packet.me2o2 = me2o2_result * 1000;
		dt = HAL_GetTick() - time_last;
		time_last = HAL_GetTick();
	    // scd41
	    uint16_t co2 = 0;
		float temp = 0;
		float pressure = 0;
		my_data.scd_temp = scd41_read_measurement(&co2, &temp, &pressure, &hi2c1);
	    if(my_data.scd_temp == 0){
	    	 packet.scd41 = co2;
	    }
		dt = HAL_GetTick() - time_last;
		time_last = HAL_GetTick();
		//neo6mv2
	    for (i = 0; i < 50; i++)
	    {
	    	if (neo6mv2_work())
	    		break;
	    }
		dt = HAL_GetTick() - time_last;
		time_last = HAL_GetTick();
		GPS_Data gps_data = neo6mv2_GetData();
		packet.neo6mv2_latitude = gps_data.latitude;
		packet.neo6mv2_longitude = gps_data.longitude;
		packet.neo6mv2_height = gps_data.altitude;
		packet.neo6mv2_fix = gps_data.fixQuality;

		// Состояние аппарата
	    switch (device_condition){
	        case MS_PREPARATION:
	        	if (HAL_GPIO_ReadPin(SWITCH_PORT, SWITCH_PIN) == GPIO_PIN_RESET)
	        	{
	        		lux = packet.photoresistor;
	        		device_condition = MS_BEFORE_LAYING;
	        	}
	            break;
	        case MS_BEFORE_LAYING:
	        	if(HAL_GPIO_ReadPin(SWITCH_PORT, SWITCH_PIN) == GPIO_PIN_SET){
	        		device_condition = MS_FLIGHT_IN_THE_ROCKET;
	        		lux_cnt = 0;
	        	}
	            break;
	        case MS_FLIGHT_IN_THE_ROCKET:
	        	if(packet.photoresistor > lux)// && (altitude >= 100))
	        	{
	        		lux_cnt++;
	        		if(lux_cnt > 2){
	        			device_condition = MS_DESCENT_A;
	        		}
	        	}
	            break;
	        case MS_DESCENT_A:
	        	if(altitude <= 100.0){
	        		burner_status(1);
	        		get_time_burner = HAL_GetTick();
	        		device_condition = MS_DESCENT_B;
	        	}
	            break;
	        case MS_DESCENT_B:
        		if(get_time_burner + BURNER_TIME < HAL_GetTick()){
        			burner_status(0);
        			piezospeaker_status(1);
        			device_condition = MS_DESCENT_C;
        		}
	            break;
	        case MS_DESCENT_C:
	            break;
	        default:
	        	device_condition = MS_ROUT;
	    }
	    packet.state = device_condition & 0x07;
	    packet.state |= (gps_data.cookie & 0x01) << 3;
	    if(my_data.scd_temp == 1){
	    	packet.state |= 1 << 4;
	    }
	    if(my_data.magn_error != 0){
	    	packet.state |= 1 << 5;
	    }
	    if(my_data.lsm_err != 0){
	    	packet.state |= 1 << 6;
	    }
	    if(bmp.intf_rslt != 0){
	    	packet.state |= 1 << 7;
	    }

		packet.time = HAL_GetTick();
		packet.number_packet++;
		packet.cheksum_org = xorBlock((uint8_t *)&packet, 26);
		packet.checksum_grib = xorBlock((uint8_t *)&packet, sizeof(packet_t) - 1);

		// e220-400t22s
	    e220_send_packet(e220_bus, 0xFFFF, (uint8_t *)&packet, sizeof(packet_t), 23);

		// sd
		if (mount_res != FR_OK){
			f_mount(NULL, "", 0);
			mount_res = f_mount(&fileSystem, "", 1);
			bin_res = f_open(&binFile, (char*)bin_path, FA_WRITE | 0x30);
			//csv_res = f_open(&csvFile, (char*)csv_path, FA_WRITE | 0x30);
			//csv_res = f_write(&csvFile, str_header, 300, &testBytes);
		}

		if  (mount_res == FR_OK && bin_res != FR_OK){
			f_close(&binFile);
			bin_res = f_open(&binFile, (char*)bin_path, FA_WRITE | 0x30);
		}

		if (mount_res == FR_OK && bin_res == FR_OK)
		{
			bin_res = f_write(&binFile, (uint8_t*)&packet, sizeof(packet_t), &testBytes);
			f_sync(&binFile);
		}

		/*if  (mount_res == FR_OK && csv_res != FR_OK){
			f_close(&csvFile);
			csv_res = f_open(&csvFile, (char*)csv_path, FA_WRITE | 0x30);
			//csv_res = f_write(&csvFile, str_header, 300, &testBytes);
		}
		if (mount_res == FR_OK && csv_res == FR_OK)
		{
			//uint16_t csv_write = snprintf(str_buffer, 300, "%d;%ld;%d;%ld;%d;%d;%d;%d;%d;%d;%d;%d;%d;%d;%d;%d;%d;%ld;%ld;%ld;%d;%d;%d;%d;%d;\n", packet.number_packet, packet.time, packet.temp_bmp280, packet.pressure_bmp280, packet.acceleration_x, packet.acceleration_y, packet.acceleration_z, packet.angular_x, packet.angular_y, packet.angular_z, packet.cheksum_org, packet.state, packet.photoresistor, packet.lis3mdl_x, packet.lis3mdl_y, packet.lis3mdl_z, packet.ds18b20, (long int)(packet.neo6mv2_height * 1000), (long int)(packet.neo6mv2_latitude * 1000000), (long int)(packet.neo6mv2_longitude * 1000000), packet.neo6mv2_fix, packet.scd41, packet.mq_4, packet.me2o2, packet.checksum_grib);
			//csv_res = f_write(&csvFile, str_buffer, csv_write, &testBytes);
			//f_sync(&csvFile);
		}*/
	}
}
