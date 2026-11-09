/*
 * sound.h
 *
 *  Created on: 2026. 10. 30.
 *      Author: kccistc
 */

#ifndef SRC_AP_SERVICE_SOUND_SOUND_H_
#define SRC_AP_SERVICE_SOUND_SOUND_H_

#include "stm32f4xx_hal.h"

void sound_init(void);
void sound_button(void);
void sound_task(void);;

#endif /* SRC_AP_SERVICE_SOUND_SOUND_H_ */
