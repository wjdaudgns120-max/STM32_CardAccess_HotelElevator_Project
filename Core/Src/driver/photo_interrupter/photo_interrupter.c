/*
 * photo_interrupter.c
 *
 *  Created on: 2026. 11. 5.
 *      Author: kccistc
 */

#include "photo_interrupter.h"

void photo_interrupt_init(photo_int_t *pt_int, GPIO_TypeDef* GPIOx, uint16_t GPIO_Pin)
{
	pt_int->GPIOx = GPIOx;
	pt_int->GPIO_Pin = GPIO_Pin;
	pt_int->prevState = OPENED;
}

photo_int_state_t photo_interrupt_getState(photo_int_t *pt_int)
{
	int curState;

	curState = HAL_GPIO_ReadPin(pt_int->GPIOx, pt_int->GPIO_Pin);

	if ((pt_int->prevState == OPENED) && (curState == CLOSED)) {
		pt_int->prevState = CLOSED;
		HAL_Delay(5); // debounce code
		return ACT_CLOSED;
	}
	else if ((pt_int->prevState == CLOSED) && (curState == OPENED)) {
		pt_int->prevState = OPENED;
		HAL_Delay(5); // debounce code
		return ACT_OPENED;
	}
	return NO_INT;
}

int photo_interrupt_isClosed(photo_int_t *pt_int)
{
	int curState = HAL_GPIO_ReadPin(pt_int->GPIOx, pt_int->GPIO_Pin);

	return curState == CLOSED;
}
