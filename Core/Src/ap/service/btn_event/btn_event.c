/*
 * btn_event.c
 *
 *  Created on: 2026. 10. 30.
 *      Author: kccistc
 */

#include "btn_event.h"
#include "../../../common/queue/que_buffer.h"
#include "../../../driver/button/button.h"

#define BTN_QUE_SIZE	16

static button_t btn[BTN_MAX];

static que_buf_t btnQue;
static btn_event_t btnQueBuf[BTN_QUE_SIZE]; // queue 저장 공간

void btn_event_init(void)
{
	button_init(&btn[BTN_1], GPIOC, GPIO_PIN_0);
	button_init(&btn[BTN_2], GPIOC, GPIO_PIN_1);
	button_init(&btn[BTN_3], GPIOC, GPIO_PIN_3);

	que_buf_init(&btnQue, btnQueBuf, sizeof(btn_event_t), BTN_QUE_SIZE);
}

void btn_event_scan(void)
{
	btn_event_t evt;

	for (int i=0; i<BTN_MAX; i++) {
		button_state_t act = button_getState(&btn[i]);
		if (act == ACT_PUSH) {	// 눌렀을 때 event 발생
			evt.id = (uint8_t)i;
			evt.act = (uint8_t)act;
			que_put(&btnQue, &evt); // queue full 이면 event 버림
		}
	}
}

bool btn_event_get(btn_event_t *evt)
{
	return que_get(&btnQue, evt);
}
