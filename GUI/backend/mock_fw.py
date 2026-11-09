"""보드 없이 GUI 를 시험하기 위한 가짜 펌웨어

ap_main.c 의 run_fsm 을 그대로 흉내 내고, 요청 판단은 scheduler.c 를 옮긴 model.ElevatorModel 을 쓴다.
진짜 보드와 같은 바이너리 프레임으로 주고받는다. (FLOOR_TIME 초에 한 층)
"""

import time

from . import codec as C
from .model import CARD_DB, ElevatorModel

FLOOR_TIME = 1.5
DOOR_OPEN_S = 5.0

DIR_CODE = {"-": 0, "UP": 1, "DOWN": 2}


class MockFirmware:
    def __init__(self, send):
        self.send = send                # send(bytes) : GUI 쪽으로 보낼 함수
        self.codec = C.FrameCodec()
        self.sch = ElevatorModel(lambda k, t: None)   # scheduler / card_auth / master_mode
        self.reset()

    def reset(self):
        self.sch.reset()
        self.st = "IDLE"
        self.floor, self.dir = 1, "-"
        self.t = time.time()
        self.in_opened = self.in_closed = False

    # ---------- GUI -> 펌웨어 (rx_task) ----------
    def receive(self, data):
        frames, _ = self.codec.feed(data)
        for cmd, p in frames:
            if cmd == C.CMD_CARD_TAG:
                ctype = {0: "NO_AUTH", 1: "GUEST", 2: "STAFF"}.get(p[1], "NO_AUTH")
                self.sch.card_tag(p[0], ctype)
            elif cmd == C.CMD_DEST_BTN:
                if self.sch.master:
                    self.sch.master_press(p[0], self.floor)
            elif cmd == C.CMD_DOOR_OPENED:
                self.in_opened = True
            elif cmd == C.CMD_DOOR_CLOSED:
                self.in_closed = True
            elif cmd == C.CMD_INIT:
                self.reset()
            self.send(C.build(C.CMD_STATUS, self.floor, DIR_CODE[self.dir],
                              C.FW_STATES.index(self.st), self.sch.req))

    # ---------- run_fsm ----------
    def tick(self):
        now = time.time()
        nxt = self._next_state(now)
        if nxt != self.st:
            self._enter(nxt)
            self.st = nxt
            self.t = now
        self._hold()
        self.in_opened = self.in_closed = False

    def _next_state(self, now):
        s = self.sch
        if self.st == "IDLE":
            if s.should_stop(self.floor, "-"):
                return "DOOR_OPENING"
            d = s.next_dir(self.floor, "-")
            return "IDLE" if d == "-" else ("MOVING_UP" if d == "UP" else "MOVING_DOWN")
        if self.st.startswith("MOVING"):
            if now - self.t >= FLOOR_TIME:          # 다음 층 센서 감지
                nf = self.floor + (1 if self.dir == "UP" else -1)
                if s.should_stop(nf, self.dir):
                    return "DOOR_OPENING"
                self.floor, self.t = nf, now        # 지나가는 층
            return self.st
        if self.st == "DOOR_OPENING":
            return "DOOR_OPEN" if self.in_opened else self.st
        if self.st == "DOOR_OPEN":
            return "DOOR_CLOSING" if now - self.t >= DOOR_OPEN_S else self.st
        if self.st == "DOOR_CLOSING":
            if s.should_stop(self.floor, self.dir):
                return "DOOR_OPENING"
            if not self.in_closed:
                return self.st
            d = s.next_dir(self.floor, self.dir)
            return "IDLE" if d == "-" else ("MOVING_UP" if d == "UP" else "MOVING_DOWN")
        return self.st

    def _enter(self, nxt):
        was_moving = self.st.startswith("MOVING")
        if nxt == "IDLE":
            if self.st == "DOOR_CLOSING":
                self.send(C.build(C.CMD_DONE, self.floor, self.sch.req))
            self.dir = "-"
        elif nxt.startswith("MOVING"):
            self.dir = "UP" if nxt == "MOVING_UP" else "DOWN"
        elif nxt == "DOOR_OPENING":
            if was_moving:
                self.floor += 1 if self.dir == "UP" else -1
            self.sch.serve(self.floor, self.dir)
            if self.st == "DOOR_CLOSING":
                self.send(C.build(C.CMD_DOOR_REOPEN, self.floor))
            else:
                self.send(C.build(C.CMD_ARRIVED, self.floor, DIR_CODE[self.dir]))
        elif nxt == "DOOR_CLOSING":
            self.send(C.build(C.CMD_DOOR_CLOSE, self.floor))

    def _hold(self):
        if self.st in ("DOOR_OPENING", "DOOR_OPEN") and self.sch.should_stop(self.floor, self.dir):
            self.sch.serve(self.floor, self.dir)
            if self.st == "DOOR_OPEN":
                self.t = time.time()              # 같은 층 호출이면 5초 다시 시작
