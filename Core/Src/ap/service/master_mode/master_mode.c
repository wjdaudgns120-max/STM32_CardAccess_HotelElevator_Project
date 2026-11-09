/*
 * master_mode.c
 *
 *  Created on: 2026. 11. 5.
 *      Author: kccistc
 */

#include "master_mode.h"
#include "../scheduler/scheduler.h"
#include "stm32f4xx_hal.h"

static bool active;
static uint32_t start_tick;

void master_mode_init(void)
{
	active = false;
}

void master_mode_enter(void)
{
	start_tick = HAL_GetTick();
	active = true;
}

bool master_mode_is_active(void)
{
	if (active && HAL_GetTick() - start_tick >= MASTER_TIME_MS) {
		active = false;
	}
	return active;
}

void master_mode_press(uint8_t floor, uint8_t cur_floor)
{
	if (floor != cur_floor) {
		sch_add(REQ_DEST(floor));	// 서 있는 층이면 요청 없음
	}
	active = false;
}
