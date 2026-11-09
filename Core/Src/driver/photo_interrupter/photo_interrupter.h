/*
 * photo_interrupter.h
 *
 *  Created on: 2026. 11. 5.
 *      Author: kccistc
 */

#ifndef SRC_DRIVER_PHOTO_INTERRUPTER_PHOTO_INTERRUPTER_H_
#define SRC_DRIVER_PHOTO_INTERRUPTER_PHOTO_INTERRUPTER_H_

#include "stm32f4xx_hal.h"

typedef enum {
	NO_INT,
	ACT_OPENED,
	ACT_CLOSED,
}photo_int_state_t;

typedef struct {
	GPIO_TypeDef* GPIOx;
	uint16_t GPIO_Pin;
	int prevState;
}photo_int_t;

enum {CLOSED = 1, OPENED = 0};

void photo_interrupt_init(photo_int_t *pt_int, GPIO_TypeDef* GPIOx, uint16_t GPIO_Pin);
photo_int_state_t photo_interrupt_getState(photo_int_t *pt_int);
int photo_interrupt_isClosed(photo_int_t *pt_int);


#endif /* SRC_DRIVER_PHOTO_INTERRUPTER_PHOTO_INTERRUPTER_H_ */
