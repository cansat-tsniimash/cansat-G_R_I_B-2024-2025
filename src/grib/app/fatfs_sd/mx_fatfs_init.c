#include "fatfs.h"
#include "fatfs_sd.h"



static Diskio_drvTypeDef spisd_driver =
{
  SD_disk_initialize,
  SD_disk_status,
  SD_disk_read,
#if  _USE_WRITE
  SD_disk_write,
#endif  /* _USE_WRITE == 1 */
#if  _USE_IOCTL == 1
  SD_disk_ioctl,
#endif /* _USE_IOCTL == 1 */
};


static char spisd_user_path[4];


void MX_FATFS_Init(void)
{
  FATFS_LinkDriver(&spisd_driver, spisd_user_path);
}


extern __IO uint32_t uwTick;
extern HAL_TickFreqTypeDef uwTickFreq;
extern volatile uint16_t Timer1, Timer2;

void HAL_IncTick(void)
{
  uwTick += uwTickFreq;
  if(Timer1 > 0){
	  Timer1--;
  }
  if(Timer2 > 0){
	  Timer2--;
  }
}
