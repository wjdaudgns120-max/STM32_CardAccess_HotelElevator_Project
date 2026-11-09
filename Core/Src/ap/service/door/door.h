/*
 * door.h
 *
 *  Created on: 2026. 11. 5.
 *      Author: kccistc
 */

#ifndef SRC_AP_SERVICE_DOOR_DOOR_H_
#define SRC_AP_SERVICE_DOOR_DOOR_H_

#include <stdbool.h>
#include <stdint.h>

#define DOOR_OPEN_MS	5000

void    door_start(void);			// 5초 카운트 시작, 재시작
void    door_stop(void);			// 카운트 종료
bool    door_is_closing(void);		// 5초 경과 여부
uint8_t door_getSec(void);			// 남은 초, 카운트 중이 아니면

#endif /* SRC_AP_SERVICE_DOOR_DOOR_H_ */
