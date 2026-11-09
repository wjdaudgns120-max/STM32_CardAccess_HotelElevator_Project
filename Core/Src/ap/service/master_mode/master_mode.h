/*
 * master_mode.c
 *
 *  Created on: 2026. 11. 5.
 *      Author: kccistc
 */
#ifndef SRC_AP_SERVICE_MASTER_MODE_MASTER_MODE_H_
#define SRC_AP_SERVICE_MASTER_MODE_MASTER_MODE_H_

#include <stdbool.h>
#include <stdint.h>

#define MASTER_TIME_MS	5000

void master_mode_init(void);
void master_mode_enter(void);								// 진입, 5초 재시작
bool master_mode_is_active(void);							// 5초가 지나면 자동으로 false
void master_mode_press(uint8_t floor, uint8_t cur_floor);	// 층 버튼 입력

#endif /* SRC_AP_SERVICE_MASTER_MODE_MASTER_MODE_H_ */
