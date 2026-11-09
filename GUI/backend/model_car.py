"""모델 칸 : GUI 화면에 그리는 엘리베이터 (운행 규칙 모델 + 시간)

실제 엘리베이터는 하드웨어(STM32)이고, 화면의 칸은 이 모델이 스스로 계산한 위치와 문으로 움직인다.
- 운행 규칙 : model.ElevatorModel (scheduler.c / card_auth.c / master_mode.c 를 옮긴 것) 의 별도 인스턴스
- 상태 흐름 : ap_main.c run_fsm (IDLE -> MOVING -> DOOR_OPENING -> DOOR_OPEN -> DOOR_CLOSING)
- 시간     : 한 층 이동 시간(측정값), 문 열림/닫힘 2초, 문 열림 유지 5초

STM32 응답으로 위치를 맞추지 않고 입력(카드 태그, 목적층 버튼)만 똑같이 받아 혼자 움직인다.
그래서 화면의 칸과 실제 STM32 위치(점선 표시)가 갈라지면 그 자리가 예상과 다른 곳이다.
"""

from .model import ElevatorModel

DOOR_MOVE_S = 2.0       # 문 열림 / 닫힘 (계획서 3.8)
DOOR_OPEN_S = 5.0       # 문 열림 유지 (door.h DOOR_OPEN_MS)
INIT_SPEED = 1.0        # INIT 때 1층으로 내려가는 속도 배율


class ModelCar:
    def __init__(self):
        self.sch = ElevatorModel(lambda k, t: None)
        self.reset(1)

    def reset(self, floor=1, go_home=False):
        """floor 에 멈춘 상태로 시작. go_home 이면 INIT 처럼 1층까지 내려감"""
        self.sch.reset()
        self.floor = floor
        self.pos = float(floor)
        self.dir = "-"
        self.door = 0.0             # 0 닫힘 ~ 1 열림
        self.open_left = 0.0        # 문 닫힐 때까지 남은 초
        self.state = "INIT" if go_home and floor != 1 else "IDLE"

    @property
    def moving(self):
        return self.state in ("MOVING_UP", "MOVING_DOWN")

    @property
    def door_sec(self):
        return int(self.open_left + 0.999) if self.state == "DOOR_OPEN" else 0

    # ---------------- 입력 (STM32 에 보낸 것과 같은 입력) ----------------
    def card_tag(self, reader, card_type, card_id=None, name=None):
        self.sch.card_tag(reader, card_type, card_id, name)

    def master_press(self, floor):
        self.sch.master_press(floor, self.floor)

    @property
    def master(self):
        return self.sch.master

    # ---------------- 시간 진행 ----------------
    def tick(self, dt, travel_s):
        """dt 초만큼 진행. 반환 : 이번에 일어난 일 목록 [("arrive", 층), ("pass", 층), ("idle", 층)]"""
        events = []
        s = self.sch
        speed = 1.0 / max(travel_s, 0.3)

        if self.state == "INIT":
            self.pos = max(1.0, self.pos - speed * INIT_SPEED * dt)
            self.floor = int(self.pos + 0.999)
            if self.pos <= 1.0:
                self.floor, self.state = 1, "IDLE"
            return events

        if self.state == "IDLE":
            if s.should_stop(self.floor, "-"):
                self._open(events)
            else:
                d = s.next_dir(self.floor, "-")
                if d != "-":
                    self._move(d)

        elif self.moving:
            step = 1 if self.dir == "UP" else -1
            nf = self.floor + step
            self.pos += step * speed * dt
            if (step > 0 and self.pos >= nf) or (step < 0 and self.pos <= nf):   # 다음 층 센서
                if s.should_stop(nf, self.dir):
                    self.floor, self.pos = nf, float(nf)
                    self._open(events)
                else:
                    self.floor = nf                                             # 서지 않고 지나감
                    events.append(("pass", nf))
                    if nf in (1, 3):                                            # 끝 층에서는 더 갈 곳이 없음
                        self.pos = float(nf)

        elif self.state == "DOOR_OPENING":
            if s.should_stop(self.floor, self.dir):
                s.serve(self.floor, self.dir)
            self.door = min(1.0, self.door + dt / DOOR_MOVE_S)
            if self.door >= 1.0:
                self.state, self.open_left = "DOOR_OPEN", DOOR_OPEN_S

        elif self.state == "DOOR_OPEN":
            if s.should_stop(self.floor, self.dir):
                s.serve(self.floor, self.dir)
                self.open_left = DOOR_OPEN_S        # 같은 층 호출이면 5초 다시 시작
            self.open_left -= dt
            if self.open_left <= 0:
                self.state, self.open_left = "DOOR_CLOSING", 0.0

        elif self.state == "DOOR_CLOSING":
            if s.should_stop(self.floor, self.dir):
                self._open(events, reopen=True)
            else:
                self.door = max(0.0, self.door - dt / DOOR_MOVE_S)
                if self.door <= 0.0:
                    d = s.next_dir(self.floor, self.dir)
                    if d == "-":
                        self.state, self.dir = "IDLE", "-"
                        events.append(("idle", self.floor))
                    else:
                        self._move(d)
        return events

    def _open(self, events, reopen=False):
        self.sch.serve(self.floor, self.dir)
        self.state = "DOOR_OPENING"
        events.append(("reopen" if reopen else "arrive", self.floor))

    def _move(self, d):
        self.dir = d
        self.state = "MOVING_UP" if d == "UP" else "MOVING_DOWN"
