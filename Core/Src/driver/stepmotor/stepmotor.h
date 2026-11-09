/*
 * stepmotor.h
 *
 *  Created on: 2026. 10. 23.
 *      Author: kccistc
 */

#ifndef SRC_DRIVER_STEPMOTOR_STEPMOTOR_H_
#define SRC_DRIVER_STEPMOTOR_STEPMOTOR_H_

#include "stm32f4xx_hal.h"

#define STEP_COUNT      8
#define STEPS_PER_REV   4096   // 28BYJ-48 하프스텝 기준 1바퀴
#define STEP_DELAY_MS   2
#define STEP_FAST_DELAY_MS      2   // 목표와 많이 벌어졌을 때 (모드 변경 등)
#define STEP_NORMAL_DELAY_MS   10   // 평소 추종 속도 (60초 1바퀴 = 약 14.6ms/스텝보다 빠르게)
#define STEP_CATCHUP_THRESHOLD   (STEPS_PER_REV / 60)   // 1초 이상 차이나면 빠르게

typedef struct {
   GPIO_TypeDef* port[4];
   uint16_t pin[4];
}stepMotor_pin_t;

typedef struct {
   stepMotor_pin_t *pin;
   uint8_t          stepCounter;
   uint16_t       position;   // 12시 = 0, CW 방향으로 증가
   uint16_t       target;   // StepMotor_task()가 이동할 목표 위치
   uint32_t       lastTick;
}stepMotor_t;

typedef enum {STEP_MOTOR_DIR_CW, STEP_MOTOR_DIR_CCW} stepMotor_dir_t;

void StepMotor_init(stepMotor_t *m, stepMotor_pin_t *pin);
void StepMotor_moveToHome(stepMotor_t *m);
void StepMotor_setTarget(stepMotor_t *m, uint16_t target);
void StepMotor_task(stepMotor_t *m);
void StepMotor_stepPhase(stepMotor_t *m, stepMotor_dir_t dir);
void StepMotor_release(stepMotor_t *m);


#endif /* SRC_DRIVER_STEPMOTOR_STEPMOTOR_H_ */
