#include "card_auth.h"
#include "../scheduler/scheduler.h"
#include "../master_mode/master_mode.h"

#define CARD_COUNT	4

// 카드 DB: 손님 A, 손님 B, 직원, 권한 없음 (계획서 3.1)
static const uint8_t card_db[CARD_COUNT] = {CARD_GUEST, CARD_GUEST, CARD_STAFF, CARD_NO_AUTH};
static uint8_t card_id;

void card_auth_init(void)
{
	card_id = 0;
}

void card_auth_next(void)
{
	card_id = (card_id + 1) % CARD_COUNT;
}

uint8_t card_auth_get_id(void)
{
	return card_id;
}

uint8_t card_auth_get_type(void)
{
	return card_db[card_id];
}

void card_auth_tag(uint8_t reader, uint8_t type)
{
	if (type == CARD_GUEST) {
		switch (reader)
		{
		case READER_1F: sch_add_call(REQ_1F_UP, REQ_DEST(2));
		break;
		case READER_2F: sch_add_call(REQ_2F_DOWN, REQ_DEST(1));
		break;
		default:
			break;		// 3층, 내부 리더는 무시
		}
	}
	else if (type == CARD_STAFF) {
		switch (reader)
		{
		case READER_1F:  sch_add(REQ_1F_UP);
		break;
		case READER_2F:  sch_add(REQ_2F_ANY);
		break;
		case READER_3F:  sch_add(REQ_3F_DOWN);
		break;
		case READER_CAR: master_mode_enter();
		break;
		default:
			break;
		}
	}
	// 권한 없는 카드는 무시
}
