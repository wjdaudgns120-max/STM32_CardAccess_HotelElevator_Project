"""펌웨어 운행 규칙을 Python 으로 그대로 옮긴 모델 (계획서 6.1 "GUI 는 같은 운행 규칙을 따로 돌린다")

- scheduler.c  : 요청 레지스터, 대기 목적층, sch_should_stop / sch_serve / sch_next_dir
- card_auth.c  : 카드 종류 x 리더 -> 호출 / 마스터 모드
- master_mode.c: 5초, 층 버튼 1회

STM32 가 보낸 ARRIVED / STATUS / DONE 을 이 모델의 예상과 비교해서 다르면 알린다.
손님 카드의 태그, 탑승, 하차도 여기서 추적한다.
"""

import time

REQ_1F_UP, REQ_2F_DOWN, REQ_2F_ANY, REQ_3F_DOWN = 0x01, 0x02, 0x04, 0x08
FLOORS = (1, 2, 3)

GUEST, STAFF, NO_AUTH = "GUEST", "STAFF", "NO_AUTH"
CARD_DB = {0: (GUEST, "손님 A"), 1: (GUEST, "손님 B"), 2: (STAFF, "직원"), 3: (NO_AUTH, "권한 없음")}
MASTER_S = 5.0


def REQ_DEST(f):
    return 1 << (3 + f)


def floor_mask(f):
    return {1: REQ_1F_UP | REQ_DEST(1), 2: REQ_2F_DOWN | REQ_2F_ANY | REQ_DEST(2), 3: REQ_3F_DOWN | REQ_DEST(3)}.get(f, 0)


def req_str(req):
    names = []
    for bit, n in ((REQ_1F_UP, "1F▲"), (REQ_2F_DOWN, "2F▼"), (REQ_2F_ANY, "2F*"), (REQ_3F_DOWN, "3F▼")):
        if req & bit:
            names.append(n)
    for f in FLOORS:
        if req & REQ_DEST(f):
            names.append(f"→{f}F")
    return " ".join(names) if names else "없음"


class ElevatorModel:
    def __init__(self, notify):
        self.notify = notify            # notify(kind, text) : "check" 검증 결과 / "guest" 손님 내역
        self.reset()

    def reset(self):
        self.req = 0
        self.pending_1up = 0
        self.pending_2down = 0
        self.master_until = 0.0
        self.riders = []                # 손님 : {card, name, from, to, state("대기"/"탑승")}
        self.mismatch = 0
        self._req_bad = 0

    # ================= scheduler.c =================
    def add(self, bits):
        self.req |= bits

    def add_call(self, call, dest):
        self.req |= call
        if call & REQ_1F_UP:
            self.pending_1up |= dest
        if call & REQ_2F_DOWN:
            self.pending_2down |= dest

    def req_ahead(self, floor, d):
        if d == "UP":
            return any(self.req & floor_mask(f) for f in range(floor + 1, 4))
        if d == "DOWN":
            return any(self.req & floor_mask(f) for f in range(1, floor))
        return False

    def should_stop(self, floor, d):
        here = self.req & floor_mask(floor)
        if here == 0:
            return False
        if here & ~REQ_2F_DOWN:
            return True
        return d != "UP" or not self.req_ahead(floor, "UP")

    def serve(self, floor, d):
        clear = self.req & floor_mask(floor)
        if d == "UP" and self.req_ahead(floor, "UP"):
            clear &= ~REQ_2F_DOWN
        self.req &= ~clear
        if clear & REQ_1F_UP:
            self.req |= self.pending_1up
            self.pending_1up = 0
            self._board(1)
        if clear & REQ_2F_DOWN:
            self.req |= self.pending_2down
            self.pending_2down = 0
            self._board(2)
        if clear & REQ_DEST(floor):
            self._alight(floor)

    def next_dir(self, floor, d):
        if d in ("UP", "DOWN") and self.req_ahead(floor, d):
            return d
        if self.req_ahead(floor, "UP"):
            return "UP"
        if self.req_ahead(floor, "DOWN"):
            return "DOWN"
        return "-"

    # ================= master_mode.c =================
    @property
    def master(self):
        return time.time() < self.master_until

    def master_press(self, floor, cur_floor):
        if floor != cur_floor:
            self.add(REQ_DEST(floor))
        self.master_until = 0.0

    # ================= card_auth.c =================
    def card_tag(self, reader, card_type, card_id=None, name=None):
        """True 면 펌웨어가 받아들이는 태그, False 면 무시되는 태그"""
        if name is None:
            name = CARD_DB[card_id][1] if card_id in CARD_DB else card_type
        if card_id is None:
            card_id = name          # 랜덤 이용객은 이름으로 구분
        if card_type == GUEST:
            if reader == 1:
                self.add_call(REQ_1F_UP, REQ_DEST(2))
                self._wait(card_id, name, 1, 2)
                return True
            if reader == 2:
                self.add_call(REQ_2F_DOWN, REQ_DEST(1))
                self._wait(card_id, name, 2, 1)
                return True
            return False
        if card_type == STAFF:
            if reader in (1, 2, 3):
                self.add({1: REQ_1F_UP, 2: REQ_2F_ANY, 3: REQ_3F_DOWN}[reader])
                return True
            if reader == 4:
                self.master_until = time.time() + MASTER_S
                return True
        return False

    # ================= 손님 이용 내역 =================
    def _wait(self, card_id, name, f, to):
        if any(r["card"] == card_id and r["from"] == f and r["state"] == "대기" for r in self.riders):
            self.notify("guest", f"[손님] {name} {f}층 리더 다시 태그 (이미 호출 대기 중)")
            return
        self.riders.append({"card": card_id, "name": name, "from": f, "to": to, "state": "대기", "t": time.time()})
        self.notify("guest", f"[손님] {name} {f}층 리더 태그 -> {to}층행 호출 등록")

    def _board(self, f):
        for r in self.riders:
            if r["state"] == "대기" and r["from"] == f:
                r["state"] = "탑승"
                self.notify("guest", f"[손님] {r['name']} {f}층에서 탑승 -> 목적층 {r['to']}층 등록")

    def _alight(self, f):
        for r in list(self.riders):
            if r["state"] == "탑승" and r["to"] == f:
                took = time.time() - r["t"]
                self.riders.remove(r)
                self.notify("guest", f"[손님] {r['name']} {f}층 하차 ({r['from']}층 -> {r['to']}층, 태그부터 {took:.0f}초)")

    # ================= STM32 응답과 비교 =================
    def on_arrived(self, floor, d, reopen=False):
        """STM32 가 floor 에 섰음 (ARRIVED / DOOR_REOPEN)"""
        if not self.should_stop(floor, d):
            self._bad(f"{floor}층 정지 : 모델은 설 이유가 없다고 봄 (요청 {req_str(self.req)}, 방향 {d})")
        else:
            self._ok(f"{floor}층 {'다시 열림' if reopen else '정지'} 예상과 같음")
        self.serve(floor, d)

    def on_pass(self, floor, d):
        """STATUS 로 보니 멈추지 않고 floor 를 지나감"""
        if self.should_stop(floor, d):
            self._bad(f"{floor}층 통과 : 모델은 여기서 서야 한다고 봄 (요청 {req_str(self.req)}, 방향 {d})")

    def on_door_open_tick(self, floor, d):
        """문이 열려 있는 동안 그 층 새 요청은 펌웨어가 바로 처리 (run_hold)"""
        if self.should_stop(floor, d):
            self.serve(floor, d)

    def on_depart(self, floor, d_fw, d_prev):
        exp = self.next_dir(floor, d_prev)
        if exp != d_fw:
            self._bad(f"{floor}층 출발 방향 {d_fw} : 모델 예상 {exp} (요청 {req_str(self.req)})")

    def on_done(self, floor, fw_req):
        if self.req != fw_req:
            self._bad(f"DONE 요청 레지스터 STM32 0x{fw_req:02X} / 모델 0x{self.req:02X}")
        else:
            self._ok(f"{floor}층에서 모든 요청 처리 완료")

    def compare_status(self, fw_req, stable):
        """STATUS 요청 레지스터 비교. 입력 직후에는 값이 잠깐 다를 수 있어서 안정된 STATUS 3번 연속일 때만 판정"""
        if not stable:
            self._req_bad = 0
            return
        if fw_req == self.req:
            self._req_bad = 0
            return
        self._req_bad += 1
        if self._req_bad == 3:
            self._bad(f"요청 레지스터 STM32 0x{fw_req:02X}({req_str(fw_req)}) / 모델 0x{self.req:02X}({req_str(self.req)})")
            self.req = fw_req       # 한 번 알린 뒤에는 STM32 값에 맞춰서 계속 비교

    def _ok(self, text):
        self.notify("check", f"[검증 OK] {text}")

    def _bad(self, text):
        self.mismatch += 1
        self.notify("check_bad", f"[검증 불일치] {text}")
