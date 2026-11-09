/*
 * sound.c
 *
 *  Created on: 2026. 10. 30.
 *      Author: kccistc
 */

#include "sound.h"
#include "../../../driver/buzzer/buzzer.h"

extern TIM_HandleTypeDef htim1;

static uint32_t beep_tick;
static uint8_t beep_step;

#define C4 262 // 도
#define D4 293 // 레
#define E4 330 // 미
#define F4 350 // 파
#define G4 392 // 솔
#define A4 440 // 라
#define B4 494 // 시

#define C5 (C4*2) // 도
#define D5 (D4*2) // 레
#define E5 (E4*2) // 미
#define F5 (F4*2) // 파
#define G5 (G4*2) // 솔
#define A5 (A4*2) // 라
#define B5 (B4*2) // 시

#define C6 (C5*2) // 도
#define D6 (D5*2) // 레
#define E6 (E5*2) // 미
#define F6 (F5*2) // 파
#define G6 (G5*2) // 솔
#define A6 (A5*2) // 라
#define B6 (B5*2) // 시

#define C7 (C6*2) // 도
#define D7 (D6*2) // 레
#define E7 (E6*2) // 미
#define F7 (F6*2) // 파
#define G7 (G6*2) // 솔
#define A7 (A6*2) // 라
#define B7 (B6*2) // 시

#define Db5 554   // 레♭
#define Eb5 622   // 미♭
#define Ab5 831   // 라♭
#define Bb5 932   // 시♭

#define Db6 1109   // 레
#define Eb6 1245   // 미
#define Ab6 1661   // 라
#define Bb6 1865   // 시

#define Db7 (Db6*2)   // 레
#define Eb7 (Eb6*2)   // 미
#define Ab7 (Ab6*2)   // 라
#define Bb7 (Bb6*2)   // 시

void sound_init(void)
{
	buzzer_init(&htim1, TIM_CHANNEL_4);
}

// 버튼음 시작: 끝내는 일은 sound_task()가 한다
void sound_button(void)
{
	buzzer_on(G6);
	beep_tick = HAL_GetTick();
	beep_step = 1;
}

// 슈퍼 루프에서 계속 호출
void sound_task(void)
{
	uint32_t elapsed = HAL_GetTick() - beep_tick;

	if (beep_step == 1 && elapsed >= 40) {
		buzzer_on(C7);
		beep_tick = HAL_GetTick();
		beep_step = 2;
	}
	else if (beep_step == 2 && elapsed >= 60) {
		buzzer_off();
		beep_step = 0;
	}
}
