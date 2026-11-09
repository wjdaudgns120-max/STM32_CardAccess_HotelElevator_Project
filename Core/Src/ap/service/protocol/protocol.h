/*
 * protocol.h
 *
 *  Created on: 2026. 11. 5.
 *      Author: kccistc
 */

#ifndef SRC_AP_SERVICE_PROTOCOL_PROTOCOL_H_
#define SRC_AP_SERVICE_PROTOCOL_PROTOCOL_H_

#include "stm32f4xx_hal.h"
#include <stdbool.h>

// GUI -> STM32 (계획서 6.3)
#define CMD_CARD_TAG	0x01
#define CMD_DEST_BTN	0x02
#define CMD_DOOR_OPENED	0x03
#define CMD_DOOR_CLOSED	0x04
#define CMD_STATUS_REQ	0x05
#define CMD_INIT		0x06

// STM32 -> GUI
#define CMD_STATUS		0x81
#define CMD_ARRIVED		0x82
#define CMD_DOOR_CLOSE	0x83
#define CMD_DOOR_REOPEN	0x84
#define CMD_HW_EVENT	0x85
#define CMD_DONE		0x86

#define PAYLOAD_LEN		4

typedef struct {
	uint8_t cmd;
	uint8_t payload[PAYLOAD_LEN];
} protocol_frame_t;

void protocol_init(UART_HandleTypeDef *huart);
bool protocol_get(protocol_frame_t *frame);		// 받은 프레임 꺼내기, 없으면 false
void protocol_send(uint8_t cmd, uint8_t p0, uint8_t p1, uint8_t p2, uint8_t p3);

#endif /* SRC_AP_SERVICE_PROTOCOL_PROTOCOL_H_ */
