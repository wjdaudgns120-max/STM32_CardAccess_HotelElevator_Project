#ifndef SRC_AP_SERVICE_CARD_AUTH_CARD_AUTH_H_
#define SRC_AP_SERVICE_CARD_AUTH_CARD_AUTH_H_

#include <stdint.h>

// 리더 번호, 카드 종류 : CARD_TAG 프레임 P0, P1 값과 같음
enum {READER_1F = 1, READER_2F, READER_3F, READER_CAR};
enum {CARD_NO_AUTH, CARD_GUEST, CARD_STAFF};

void    card_auth_init(void);
void    card_auth_next(void);						// BTN5: 다음 카드
uint8_t card_auth_get_id(void);						// 현재 카드 번호 0~3
uint8_t card_auth_get_type(void);					// 현재 카드 종류
void    card_auth_tag(uint8_t reader, uint8_t type);	// 리더에 태그

#endif /* SRC_AP_SERVICE_CARD_AUTH_CARD_AUTH_H_ */
