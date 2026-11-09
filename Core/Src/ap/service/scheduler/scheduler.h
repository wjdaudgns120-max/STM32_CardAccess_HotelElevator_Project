/*
 * scheduler.h
 *
 *  Created on: 2026. 11. 5.
 *      Author: kccistc
 */

#ifndef SRC_AP_SERVICE_SCHEDULER_SCHEDULER_H_
#define SRC_AP_SERVICE_SCHEDULER_SCHEDULER_H_

#include <stdbool.h>
#include <stdint.h>

// 요청 레지스터 비트 (계획서 5.2)
#define REQ_1F_UP		(1 << 0)	// 1층 상행 호출
#define REQ_2F_DOWN		(1 << 1)	// 2층 하행 호출 (손님)
#define REQ_2F_ANY		(1 << 2)	// 2층 방향 무관 호출 (직원)
#define REQ_3F_DOWN		(1 << 3)	// 3층 하행 호출
#define REQ_DEST(floor)	(1 << (3 + (floor)))	// 목적층: 1층 bit4, 2층 bit5, 3층 bit6

typedef enum {DIR_NONE, DIR_UP, DIR_DOWN} sch_dir_t;	// STATUS 프레임 값과 같음

void    sch_init(void);
void    sch_add(uint8_t bits);						// 요청 비트 등록
void    sch_add_call(uint8_t call, uint8_t dest);	// 호출 + 대기 목적층 등록
uint8_t sch_get_req(void);							// 요청 레지스터 값

bool      sch_req_ahead(uint8_t floor, sch_dir_t dir);
bool      sch_should_stop(uint8_t floor, sch_dir_t dir);
void      sch_serve(uint8_t floor, sch_dir_t dir);
sch_dir_t sch_next_dir(uint8_t floor, sch_dir_t dir);

#endif /* SRC_AP_SERVICE_SCHEDULER_SCHEDULER_H_ */
