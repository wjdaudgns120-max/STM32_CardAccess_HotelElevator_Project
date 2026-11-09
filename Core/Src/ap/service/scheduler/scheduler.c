/*
 * scheduler.c
 *
 *  Created on: 2026. 11. 5.
 *      Author: kccistc
 */

#include "scheduler.h"

static uint8_t req;				// 요청 레지스터
static uint8_t pending_1up;		// 1층 상행 호출에 묶인 대기 목적층
static uint8_t pending_2down;	// 2층 하행 호출에 묶인 대기 목적층

static uint8_t floor_mask(uint8_t floor)
{
	switch (floor)
	{
	case 1:  return REQ_1F_UP | REQ_DEST(1);
	case 2:  return REQ_2F_DOWN | REQ_2F_ANY | REQ_DEST(2);
	case 3:  return REQ_3F_DOWN | REQ_DEST(3);
	default: return 0;
	}
}

void sch_init(void)
{
	req = 0;
	pending_1up = 0;
	pending_2down = 0;
}

void sch_add(uint8_t bits)
{
	req |= bits;
}

void sch_add_call(uint8_t call, uint8_t dest)
{
	req |= call;
	if (call & REQ_1F_UP)   pending_1up |= dest;
	if (call & REQ_2F_DOWN) pending_2down |= dest;
}

uint8_t sch_get_req(void)
{
	return req;
}

bool sch_req_ahead(uint8_t floor, sch_dir_t dir)
{
	if (dir == DIR_UP) {
		for (uint8_t f = floor + 1; f <= 3; f++) {
			if (req & floor_mask(f)) return true;
		}
	}
	else if (dir == DIR_DOWN) {
		for (uint8_t f = 1; f < floor; f++) {
			if (req & floor_mask(f)) return true;
		}
	}
	return false;
}

bool sch_should_stop(uint8_t floor, sch_dir_t dir)
{
	uint8_t here = req & floor_mask(floor);

	if (here == 0) return false;
	if (here & ~REQ_2F_DOWN) return true;	// 2층 하행 외의 요청은 항상 정지

	// 2층 하행 호출만 있을 때: 상승 중이고 위에 요청이 남아 있으면 통과
	return (dir != DIR_UP) || !sch_req_ahead(floor, DIR_UP);
}

void sch_serve(uint8_t floor, sch_dir_t dir)
{
	uint8_t clear = req & floor_mask(floor);

	// 상승 중 2층에 섰고 위에 요청이 남아 있으면 2층 하행 호출은 처리하지 않음
	if (dir == DIR_UP && sch_req_ahead(floor, DIR_UP)) {
		clear &= ~REQ_2F_DOWN;
	}

	req &= ~clear;

	// 호출이 지워지는 순간에만 대기 목적층을 등록
	if (clear & REQ_1F_UP) {
		req |= pending_1up;
		pending_1up = 0;
	}
	if (clear & REQ_2F_DOWN) {
		req |= pending_2down;
		pending_2down = 0;
	}
}

sch_dir_t sch_next_dir(uint8_t floor, sch_dir_t dir)
{
	if (sch_req_ahead(floor, dir)) return dir;	// 같은 방향 우선
	if (sch_req_ahead(floor, DIR_UP)) return DIR_UP;
	if (sch_req_ahead(floor, DIR_DOWN)) return DIR_DOWN;
	return DIR_NONE;
}
