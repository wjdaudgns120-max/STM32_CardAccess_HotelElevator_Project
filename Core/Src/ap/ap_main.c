#include "ap_main.h"
#include "service/door/door.h"
#include "service/Display/Display.h"
#include "service/scheduler/scheduler.h"
#include "service/protocol/protocol.h"
#include "service/card_auth/card_auth.h"
#include "service/master_mode/master_mode.h"
#include "service/sound/sound.h"

#include "../driver/button/button.h"
#include "../driver/stepmotor/stepmotor.h"
#include "../driver/photo_interrupter/photo_interrupter.h"

#include <stdio.h>

extern UART_HandleTypeDef huart2;

#define MOTOR_UP		STEP_MOTOR_DIR_CW	// 상승 방향 (실물 확인)
#define MOTOR_DOWN		STEP_MOTOR_DIR_CCW
#define MOTOR_TICK_MS	3					// 한 스텝 간격
#define MAX_STEPS		30000				// 층을 못 찾으면 멈추는 한계
#define FLOOR_COUNT		3

enum {BTN_1F, BTN_2F, BTN_3F, BTN_CAR, BTN_CARD, BTN_COUNT};

// STATUS 프레임 P2 값
typedef enum {
	ST_INIT,
	ST_IDLE,
	ST_MOVING_UP,
	ST_MOVING_DOWN,
	ST_DOOR_OPENING,
	ST_DOOR_OPEN,
	ST_DOOR_CLOSING,
} run_state_t;

static button_t btn[BTN_COUNT];
static photo_int_t sensor[FLOOR_COUNT];
static stepMotor_pin_t motor_pin = {
		.port = {GPIOC, GPIOC, GPIOC, GPIOD},
		.pin  = {GPIO_PIN_10, GPIO_PIN_11, GPIO_PIN_12, GPIO_PIN_2},
};
static stepMotor_t motor;

static run_state_t state = ST_INIT;
static sch_dir_t dir = DIR_NONE;
static uint8_t cur_floor = 1;

// 이번 루프의 입력
static bool in_door_opened;
static bool in_door_closed;
static bool in_init;

// 모터
static uint32_t motor_tick;
static uint32_t motor_steps;
static bool motor_fail;

static bool floor_detected(uint8_t floor)
{
	return floor >= 1 && floor <= FLOOR_COUNT && photo_interrupt_isClosed(&sensor[floor - 1]);
}

static uint8_t next_floor(void)
{
	return (dir == DIR_UP) ? cur_floor + 1 : cur_floor - 1;
}

static void motor_task(stepMotor_dir_t motor_dir)
{
	if (HAL_GetTick() - motor_tick < MOTOR_TICK_MS) return;
	motor_tick = HAL_GetTick();

	if (++motor_steps > MAX_STEPS) {
		motor_fail = true;
		return;
	}
	StepMotor_stepPhase(&motor, motor_dir);
}

static run_state_t moving_state(sch_dir_t move_dir)
{
	return (move_dir == DIR_UP) ? ST_MOVING_UP : ST_MOVING_DOWN;
}

// 다음 상태 계산: 값만 판단하고 동작은 하지 않는다
static run_state_t run_next_state(void)
{
	sch_dir_t next_dir;

	if (in_init) return ST_INIT;

	switch (state)
	{
	case ST_INIT:
		return (floor_detected(1) || motor_fail) ? ST_IDLE : ST_INIT;

	case ST_IDLE:
		if (sch_should_stop(cur_floor, DIR_NONE)) return ST_DOOR_OPENING;
		next_dir = sch_next_dir(cur_floor, DIR_NONE);
		return (next_dir == DIR_NONE) ? ST_IDLE : moving_state(next_dir);

	case ST_MOVING_UP:
	case ST_MOVING_DOWN:
		if (motor_fail) return ST_IDLE;
		// 안전장치: 1층에서 아래로, 3층에서 위로는 갈 층이 없으므로 바로 정지
		if (next_floor() < 1 || next_floor() > FLOOR_COUNT) return ST_IDLE;
		if (floor_detected(next_floor()) && sch_should_stop(next_floor(), dir)) {
			return ST_DOOR_OPENING;
		}
		return state;

	case ST_DOOR_OPENING:
		return in_door_opened ? ST_DOOR_OPEN : ST_DOOR_OPENING;

	case ST_DOOR_OPEN:
		return door_is_closing() ? ST_DOOR_CLOSING : ST_DOOR_OPEN;

	case ST_DOOR_CLOSING:
		if (sch_should_stop(cur_floor, dir)) return ST_DOOR_OPENING;
		if (!in_door_closed) return ST_DOOR_CLOSING;
		next_dir = sch_next_dir(cur_floor, dir);
		return (next_dir == DIR_NONE) ? ST_IDLE : moving_state(next_dir);

	default:
		return ST_INIT;
	}
}

// 상태 진입 동작
static void run_enter(run_state_t next)
{
	bool was_moving = (state == ST_MOVING_UP || state == ST_MOVING_DOWN);

	if (state == ST_INIT || was_moving) {
		StepMotor_release(&motor);
	}

	switch (next)
	{
	case ST_INIT:
		StepMotor_release(&motor);
		sch_init();
		master_mode_init();
		door_stop();
		dir = DIR_NONE;
		motor_steps = 0;
		motor_fail = false;
		break;

	case ST_IDLE:
		if (state == ST_INIT) {
			cur_floor = 1;
		}
		if (motor_fail) {
			sch_init();		// 센서를 못 찾으면 요청을 버리고 정지
			motor_fail = false;
		}
		if (state == ST_DOOR_CLOSING) {
			protocol_send(CMD_DONE, cur_floor, sch_get_req(), 0, 0);
		}
		dir = DIR_NONE;
		break;

	case ST_MOVING_UP:
	case ST_MOVING_DOWN:
		dir = (next == ST_MOVING_UP) ? DIR_UP : DIR_DOWN;
		motor_steps = 0;
		break;

	case ST_DOOR_OPENING:
		if (was_moving) {
			cur_floor = next_floor();
		}
		sch_serve(cur_floor, dir);
		if (state == ST_DOOR_CLOSING) {
			protocol_send(CMD_DOOR_REOPEN, cur_floor, 0, 0, 0);
		}
		else {
			protocol_send(CMD_ARRIVED, cur_floor, dir, 0, 0);
		}
		break;

	case ST_DOOR_OPEN:
		door_start();
		break;

	case ST_DOOR_CLOSING:
		door_stop();
		protocol_send(CMD_DOOR_CLOSE, cur_floor, 0, 0, 0);
		break;

	default:
		break;
	}
}

// 상태 유지 동작
static void run_hold(void)
{
	switch (state)
	{
	case ST_INIT:
		motor_task(MOTOR_DOWN);
		break;

	case ST_MOVING_UP:
	case ST_MOVING_DOWN:
		// 서지 않고 지나가는 층만 여기서 처리한다.
		// 멈춰야 하는 층은 다음 루프의 run_next_state()가 정지시킨다.
		// (센서를 두 번 읽는 사이에 값이 바뀌면 멈출 층을 통과로 처리하던 문제 수정)
		if (floor_detected(next_floor()) && !sch_should_stop(next_floor(), dir)) {
			cur_floor = next_floor();
			motor_steps = 0;
		}
		motor_task((dir == DIR_UP) ? MOTOR_UP : MOTOR_DOWN);
		break;

	case ST_DOOR_OPENING:
		if (sch_should_stop(cur_floor, dir)) {
			sch_serve(cur_floor, dir);
		}
		break;

	case ST_DOOR_OPEN:
		if (sch_should_stop(cur_floor, dir)) {
			sch_serve(cur_floor, dir);
			door_start();	// 같은 층 호출이면 5초 다시 시작
		}
		break;

	default:
		break;
	}
}

static void run_fsm(void)
{
	run_state_t next = run_next_state();

	if (next != state) {
		run_enter(next);
		state = next;
	}
	run_hold();

	in_door_opened = false;
	in_door_closed = false;
	in_init = false;
}

// GUI 프레임 처리
static void rx_task(void)
{
	protocol_frame_t frame;

	while (protocol_get(&frame)) {
		switch (frame.cmd)
		{
		case CMD_CARD_TAG:
			card_auth_tag(frame.payload[0], frame.payload[1]);
			sound_button();
			break;
		case CMD_DEST_BTN:
			sound_button();
			if (master_mode_is_active()) {
				master_mode_press(frame.payload[0], cur_floor);
			}
			break;
		case CMD_DOOR_OPENED:
			in_door_opened = true;
			break;
		case CMD_DOOR_CLOSED:
			in_door_closed = true;
			break;
		case CMD_INIT:
			in_init = true;
			break;
		default:
			break;
		}

		protocol_send(CMD_STATUS, cur_floor, dir, state, sch_get_req());
	}
}

// 버튼 입력: 일반 모드는 카드 태그, 마스터 모드의 BTN1~3은 층 버튼, BTN5는 카드 변경
static void button_task(void)
{
	for (int i = 0; i < BTN_COUNT; i++) {
		if (button_getState(&btn[i]) == ACT_PUSH) {
			bool master = master_mode_is_active();	// 누른 순간의 모드를 GUI로 보냄
			sound_button();

			if (i == BTN_CARD) {
				card_auth_next();
			}
			else if (!master) {
				card_auth_tag(i + 1, card_auth_get_type());	// 리더 번호 = 버튼 번호
			}
			else if (i != BTN_CAR) {
				master_mode_press(i + 1, cur_floor);
			}
			protocol_send(CMD_HW_EVENT, i + 1, card_auth_get_id(), master, 0);
		}
	}
}

static void ap_init(void)
{
	button_init(&btn[BTN_1F],   GPIOC, GPIO_PIN_0);
	button_init(&btn[BTN_2F],   GPIOC, GPIO_PIN_1);
	button_init(&btn[BTN_3F],   GPIOC, GPIO_PIN_2);
	button_init(&btn[BTN_CAR],  GPIOC, GPIO_PIN_3);
	button_init(&btn[BTN_CARD], GPIOB, GPIO_PIN_0);
	photo_interrupt_init(&sensor[0], GPIOA, GPIO_PIN_4);
	photo_interrupt_init(&sensor[1], GPIOA, GPIO_PIN_1);
	photo_interrupt_init(&sensor[2], GPIOA, GPIO_PIN_0);
	Disp_init();
	StepMotor_init(&motor, &motor_pin);
	sch_init();
	card_auth_init();
	master_mode_init();
	protocol_init(&huart2);
	sound_init();
}

int ap_main(void)
{
	ap_init();

	while (1)
	{
		button_task();
		rx_task();
		run_fsm();
		Disp_LCD(cur_floor);
		sound_task();
	}
	return 0;
}

//test
//int ap_main(void)
//{
//   ap_init();
//
//   // 임시: 센서 값 출력, 시험 후 삭제
//   while (1) {
//      char buf[32];
//      int len = snprintf(buf, sizeof(buf), "PA15:%d PA14:%d PA13:%d\r\n",
//            HAL_GPIO_ReadPin(GPIOA, GPIO_PIN_4),
//            HAL_GPIO_ReadPin(GPIOA, GPIO_PIN_1),
//            HAL_GPIO_ReadPin(GPIOA, GPIO_PIN_0));
//
//      HAL_UART_Transmit(&huart2, (uint8_t *)buf, len, 100);
//      HAL_Delay(200);
//   }
//
//   while (1)
//   {
//      button_task();
//      rx_task();
//      run_fsm();
//      Disp_LCD(cur_floor);
//      sound_task();
//   }
//   return 0;
//}

