/*
 * Display.c
 *
 *  Created on: 2026. 10. 20.
 *      Author: kccistc
 */

#include "Display.h"
#include "../door/door.h"
#include "../../../driver/lcd/lcd.h"
#include <stdio.h>

void Disp_init(void)
{
	Lcd_init();
}

void Disp_LCD(uint8_t floor)
{
	static uint8_t prevFloor = 0xff;
	static uint8_t prevSec	 = 0xff;
	uint8_t doorSec = door_getSec();

	char floor_buf[30];
	char closing_buf[30];;

	if(floor != prevFloor){
		prevFloor = floor;
		sprintf(floor_buf, "floor : %d", floor);
		Lcd_writeStringXY(0, 0, floor_buf);
	}

	if(doorSec != prevSec){
		prevSec = doorSec;
		if(doorSec > 0) {
			sprintf(closing_buf, "Closing in %d sec", doorSec);
		}
		else {
			sprintf(closing_buf, "                 ");
		}
		Lcd_writeStringXY(1, 0, closing_buf);
	}
}
