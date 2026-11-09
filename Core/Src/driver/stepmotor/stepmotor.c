/*
 * stepmotor.c
 *
 *  Created on: 2026. 10. 23.
 *      Author: kccistc
 */
#include "stepmotor.h"

static uint8_t step_table[STEP_COUNT] = {0x01, 0x03, 0x02, 0x06, 0x04, 0x0c, 0x08, 0x09};

static void StepMotor_writePattern(stepMotor_t *m, uint8_t step)
{
   for (int i = 0; i < 4; i++){
      GPIO_PinState s = (step & (1<<i)) ? GPIO_PIN_SET : GPIO_PIN_RESET;
      HAL_GPIO_WritePin(m->pin->port[i], m->pin->pin[i], s);
   }
}

// m은 전역(또는 static) 변수로 선언해야 position이 0으로 시작한다.
// 첫 전원 투입 시에는 바늘이 12시에 있다고 가정하므로 손으로 맞춰 둘 것.
// 이후 다시 호출하면 지금까지 움직인 만큼 되돌아가 12시로 이동한다.
void StepMotor_init(stepMotor_t *m, stepMotor_pin_t *pin)
{
   m->pin = pin;
   StepMotor_moveToHome(m);
}

void StepMotor_moveToHome(stepMotor_t *m)
{
   if (m->position == 0) {
      StepMotor_release(m);
      m->target = 0;
      return;
   }

   // 가까운 방향으로 회전
   stepMotor_dir_t dir = (m->position <= STEPS_PER_REV / 2) ? STEP_MOTOR_DIR_CCW : STEP_MOTOR_DIR_CW;

   StepMotor_writePattern(m, step_table[m->stepCounter]);
   while (m->position != 0) {
      StepMotor_stepPhase(m, dir);
      HAL_Delay(STEP_DELAY_MS);
   }
   StepMotor_release(m);
   m->target = 0;
}

void StepMotor_setTarget(stepMotor_t *m, uint16_t target)
{
   m->target = target % STEPS_PER_REV;
}

// 타이머 인터럽트(1ms)에서 계속 호출. 목표 쪽으로 한 스텝씩 이동한다 (블로킹 없음).
// 목표와 1초 이상 차이나면 빠르게, 따라잡은 뒤에는 평소 속도로 움직인다.
// 스텝을 놓치지 않도록 이동 중에는 코일 전원을 끄지 않는다.
void StepMotor_task(stepMotor_t *m)
{
   if (m->position == m->target) {
      return;
   }

   // 가까운 방향과 남은 거리
   uint16_t cwDist = (m->target + STEPS_PER_REV - m->position) % STEPS_PER_REV; // 양수 처리를 위해 +STEPS_PER_REV
   stepMotor_dir_t dir = (cwDist <= STEPS_PER_REV / 2) ? STEP_MOTOR_DIR_CW : STEP_MOTOR_DIR_CCW;
   uint16_t dist = (dir == STEP_MOTOR_DIR_CW) ? cwDist : STEPS_PER_REV - cwDist;

   uint32_t delay = (dist > STEP_CATCHUP_THRESHOLD) ? STEP_FAST_DELAY_MS : STEP_NORMAL_DELAY_MS;
   if (HAL_GetTick() - m->lastTick < delay) {
      return;
   }
   m->lastTick = HAL_GetTick();

   StepMotor_stepPhase(m, dir);
}

void StepMotor_stepPhase(stepMotor_t *m, stepMotor_dir_t dir)
{
   if (dir == STEP_MOTOR_DIR_CW) {
      m->stepCounter = (m->stepCounter + 1) %STEP_COUNT;
      m->position = (m->position + 1) %STEPS_PER_REV;
   }
   else {
      m->stepCounter = (m->stepCounter + STEP_COUNT - 1) %STEP_COUNT;
      m->position = (m->position + STEPS_PER_REV - 1) %STEPS_PER_REV;
   }
   StepMotor_writePattern(m, step_table[m->stepCounter]);
}

void StepMotor_release(stepMotor_t *m)
{
   StepMotor_writePattern(m, 0x00);
}
