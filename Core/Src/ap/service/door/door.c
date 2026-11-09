/*
 * door.c
 *
 *  Created on: 2026. 11. 5.
 *      Author: kccistc
 */

#include "door.h"
#include "stm32f4xx_hal.h"
#include "stdbool.h"

static bool running = false;
static uint32_t start_tick;

void door_start(void)
{
	start_tick = HAL_GetTick();
	running = true;
}

void door_stop(void)
{
	running = false;
}

bool door_is_closing(void)
{
	return running && (HAL_GetTick() - start_tick >= DOOR_OPEN_MS);
}

uint8_t door_getSec(void)
{
	uint32_t elapsed = HAL_GetTick() - start_tick;

	if (!running || elapsed >= DOOR_OPEN_MS){
		return 0;
	}
	return(DOOR_OPEN_MS - elapsed + 999) / 1000;
}
