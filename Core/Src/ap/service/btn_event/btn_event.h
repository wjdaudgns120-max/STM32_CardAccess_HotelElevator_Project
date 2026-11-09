/*
 * btn_event.h
 *
 *  Created on: 2026. 10. 30.
 *      Author: kccistc
 */

#ifndef SRC_AP_SERVICE_BTN_EVENT_BTN_EVENT_H_
#define SRC_AP_SERVICE_BTN_EVENT_BTN_EVENT_H_

#include <stdint.h>
#include <stdbool.h>

typedef enum {
	BTN_1 = 0,	// PC0 : mode change
	BTN_2,		// PC1 : run/stop, measure
	BTN_3,		// PC3 : clear
	BTN_MAX
} btn_id_t;

typedef struct {
	uint8_t id;		// btn_id_t
	uint8_t act;	// button_state_t (ACT_PUSH / ACT_RELEASE)
} btn_event_t;

void btn_event_init(void);
void btn_event_scan(void);				// producer : button 상태 -> queue
bool btn_event_get(btn_event_t *evt);	// consumer : queue -> event

#endif /* SRC_AP_SERVICE_BTN_EVENT_BTN_EVENT_H_ */
