/*
 * protocol.c
 *
 *  Created on: 2026. 11. 5.
 *      Author: kccistc
 */

#include "protocol.h"
#include "../../../common/queue/que_buffer.h"
#include "../../../driver/uart/uart.h"
#include <string.h>

#define RX_QUE_SIZE		8

static que_buf_t rx_que;
static protocol_frame_t rx_que_buf[RX_QUE_SIZE];

// UART 수신 인터럽트 안에서 호출된다. 큐에 넣기만 한다.
static void on_packet(uint8_t cmd, uint8_t *payload, uint8_t payload_len)
{
	protocol_frame_t frame;

	if (payload_len != PAYLOAD_LEN) return;		// LEN 불일치 프레임은 버림

	frame.cmd = cmd;
	memcpy(frame.payload, payload, PAYLOAD_LEN);
	que_put(&rx_que, &frame);
}

void protocol_init(UART_HandleTypeDef *huart)
{
	que_buf_init(&rx_que, rx_que_buf, sizeof(protocol_frame_t), RX_QUE_SIZE);
	UART_protocol_init(huart, on_packet);
}

bool protocol_get(protocol_frame_t *frame)
{
	return que_get(&rx_que, frame);
}

void protocol_send(uint8_t cmd, uint8_t p0, uint8_t p1, uint8_t p2, uint8_t p3)
{
	uint8_t payload[PAYLOAD_LEN] = {p0, p1, p2, p3};

	UART_protocol_send(cmd, payload, PAYLOAD_LEN);
}
