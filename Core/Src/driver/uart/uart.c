/*
 * uart_protocol.c
 *
 *  Created on: 2026. 11. 4.
 *      Author: kccistc
 */


#include "uart.h"

#include <stdint.h>


typedef enum { RX_WAIT_START, RX_WAIT_LEN, RX_WAIT_DATA, RX_WAIT_CHK } rx_state_t;

void packet_do_func(uint8_t cmd, uint8_t *payload, uint8_t payload_len);
void rx_parse_byte(uint8_t rx_data);

static volatile uint8_t rx_byte;
static rx_state_t rx_state = RX_WAIT_START;
static uint8_t rx_len;
static uint8_t rx_idx;
static uint8_t rx_buf[PKT_MAX_LEN];

UART_HandleTypeDef *protocol_huart;

// 함수 포인터 변수 선언, 함수의 주소를 넣을 수 있는 공간, 함수 주소를 받은 함수를 대신하는 함수
static uart_packet_callback_t packet_callback = 0;

void UART_protocol_init(UART_HandleTypeDef *huart, uart_packet_callback_t packet_cb)
{
	protocol_huart = huart;
	packet_callback = packet_cb;
	rx_state = RX_WAIT_START;
	HAL_UART_Receive_IT(protocol_huart, (uint8_t *)&rx_byte, 1);
}

void UART_protocol_send(uint8_t cmd, uint8_t *payload, uint8_t payload_len)
{
	uint8_t tx[3+PKT_MAX_LEN];
	uint8_t len = 1 + payload_len;
	uint8_t cksum = len;

	tx[0] = PKT_START;
	tx[1] = len;
	tx[2] = cmd;
	cksum += cmd;

	for(int i=0; i<payload_len; i++){
		tx[3+i] = payload[i];
		cksum += payload[i];
	}
	tx[3+payload_len] = cksum;

	HAL_UART_Transmit(protocol_huart, tx, (3 + payload_len + 1), 1000); //3: sof + len + cmd
}

void rx_parse_byte(uint8_t rx_data)
{
	switch(rx_state)
	{
	case RX_WAIT_START:
		if (rx_data ==PKT_START){
			rx_state = RX_WAIT_LEN;
		}
		break;
	case RX_WAIT_LEN:
		if(rx_data == 0 || rx_data >= PKT_MAX_LEN){
			rx_state = RX_WAIT_START;
		}
		else {
			rx_len = rx_data;
			rx_idx = 0;
			rx_state = RX_WAIT_DATA;
		}
		break;
	case RX_WAIT_DATA:
		rx_buf[rx_idx++] = rx_data;
		if(rx_idx >= rx_len){
			rx_state = RX_WAIT_CHK;
		}
		break;
	case RX_WAIT_CHK:
		uint8_t cksum = rx_len;
		for(int i=0; i<rx_len; i++){
			cksum += rx_buf[i];
		}
		if(cksum == rx_data){
			// 수신한 명령 내용 함수 실행
			packet_callback(rx_buf[0], &rx_buf[1], (rx_len-1));
			// ok -> 전송
		}
		else{
			// error 전송

		}
		rx_state = RX_WAIT_START;
		break;
	default:
		break;
	}
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
	if(huart ->Instance == USART2){
		rx_parse_byte(rx_byte);
		HAL_UART_Receive_IT(protocol_huart, (uint8_t *)&rx_byte, 1);
	}
}
