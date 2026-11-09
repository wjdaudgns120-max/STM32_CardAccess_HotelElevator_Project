"""backend 중심 : link(통신) + codec(프레임) + state(상태) + 문 핸드셰이크 + 모델 비교 + 랜덤 시나리오

펌웨어(ap_main.c run_fsm)와의 약속 (계획서 3.8)
  1. STM32 가 ARRIVED / DOOR_REOPEN 을 보내면 GUI 는 문을 열고(2초), 다 열리면 DOOR_OPENED 를 보낸다.
  2. 펌웨어가 5초를 센 뒤 DOOR_CLOSE 를 보내면 GUI 는 문을 닫고(2초), 다 닫히면 DOOR_CLOSED 를 보낸다.
  3. 펌웨어는 프레임을 받을 때마다 STATUS 로 답하므로, 주기적으로 STATUS_REQ 를 보내 상태를 받는다.

계획서 6.1 : GUI 는 같은 운행 규칙(model.py)을 따로 돌리고 STM32 응답과 비교한다.
frontend 는 이 클래스의 메서드만 부르고, on_event 로 알림만 받는다.
"""

import time

from . import codec as C
from .link import MockLink, SerialLink
from .model import CARD_DB, ElevatorModel
from .model_car import ModelCar
from .scenario import ScenarioRunner
from .state import CARDS, READERS, ElevatorState, Event

STATUS_POLL_S = 0.2      # STATUS_REQ 주기
ACK_RETRY_S = 1.0        # 펌웨어가 아직 OPENING/CLOSING 이면 DOOR_OPENED/CLOSED 다시 보내는 간격
DOOR_OPEN_S = 5.0        # 펌웨어 door.h DOOR_OPEN_MS
SETTLE_S = 0.6           # 입력 / 도착 직후 이 시간 동안은 요청 레지스터 비교를 쉼


class ElevatorBackend:
    def __init__(self, on_event):
        self.on_event = on_event          # Event 를 받는 콜백 (frontend)
        self.state = ElevatorState()
        self.codec = C.FrameCodec()
        self.link = None
        self.log_status = False           # True 면 STATUS 프레임도 로그에 출력
        self.model = ElevatorModel(self._model_note)
        self.scenario = ScenarioRunner(self, lambda t: self._emit("log", t))
        self._timers = []                 # (시각, 함수) : after()
        self._last_poll = 0.0
        self._door_done = None            # frontend 가 알려준 문 위치 : True 열림 / False 닫힘 / None 움직이는 중
        self._last_ack = 0.0
        self._door_open_at = None
        self._last_event = 0.0
        self._prev = None                 # 직전 STATUS (floor, fw_state, direction)
        self._last_dir = "-"
        self.travel_hint = 3.0            # 한 층 이동 시간 (frontend 가 알려줌, 랜덤 타이밍 기준)
        self.car = ModelCar()             # 화면에 그리는 모델 칸 (STM32 와 같은 입력만 받고 혼자 움직임)
        self._car_synced = False          # 연결 직후 첫 STATUS 의 층에서 모델 칸을 시작
        self._car_last = time.time()
        self._both_idle_since = None

    @property
    def is_mock(self):
        return isinstance(self.link, MockLink)

    # ---------------- 연결 ----------------
    def ports(self):
        return MockLink.ports() + SerialLink.ports()

    def connect(self, port):
        self.link = MockLink() if port == "MOCK" else SerialLink()
        try:
            self.link.open(port)
        except Exception as e:  # 포트 사용 중, pyserial 없음 등
            self.link = None
            self._emit("error", f"연결 실패 : {e}")
            if "PermissionError" in str(e) or "Access" in str(e):
                self._emit("error", "다른 프로그램(ComPortMaster, CubeIDE 터미널 등)이 이 포트를 쓰고 있어요. 닫고 다시 Connect 하세요.")
            return False
        self.codec = C.FrameCodec()
        self.model.reset()
        self._prev = None
        self._car_synced = False
        self.state.update(connected=True)
        self._emit("log", f"connected {port}")
        self._send(C.CMD_STATUS_REQ)
        self._emit("state")
        return True

    def disconnect(self):
        if self.link:
            self.link.close()
        self.link = None
        self.scenario.steps = []
        self.state.update(connected=False)
        self._emit("log", "disconnected")
        self._emit("state")

    def after(self, sec, fn):
        self._timers.append((time.time() + sec, fn))

    # ---------------- 주기 처리 (frontend 가 30~50ms 마다 호출) ----------------
    def poll(self):
        if not self.link:
            return
        now = time.time()

        frames, errors = self.codec.feed(self.link.read_all())
        for e in errors:
            self._emit("error", e)
        for cmd, p in frames:
            self._handle(cmd, p)

        if now - self._last_poll >= STATUS_POLL_S:
            self._last_poll = now
            self._send(C.CMD_STATUS_REQ, quiet=True)

        due = [t for t in self._timers if t[0] <= now]
        self._timers = [t for t in self._timers if t[0] > now]
        for _, fn in due:
            fn()

        self._door_handshake(now)
        self._tick_timers(now)
        self._tick_car(now)
        self.scenario.tick()

    # ---------------- 수신 프레임 처리 ----------------
    def _handle(self, cmd, p):
        s = self.state
        if cmd == C.CMD_STATUS:
            self._on_status(p)
            return

        self._emit("log", "RX " + C.describe(cmd, p))
        self._last_event = time.time()
        if cmd == C.CMD_ARRIVED:
            d = C.FW_DIRS[p[1]] if p[1] < 3 else "-"
            s.update(floor=p[0], fw_state="DOOR_OPENING")
            self.model.on_arrived(p[0], d)
            self._set_door(True)
        elif cmd == C.CMD_DOOR_REOPEN:
            s.update(floor=p[0], fw_state="DOOR_OPENING")
            self.model.on_arrived(p[0], self._last_dir, reopen=True)
            self._set_door(True)
        elif cmd == C.CMD_DOOR_CLOSE:
            s.update(fw_state="DOOR_CLOSING")
            self._set_door(False)
        elif cmd == C.CMD_HW_EVENT:
            self._on_hw_event(p[0], p[1], p[2])
        elif cmd == C.CMD_DONE:
            s.update(floor=p[0], req=p[1], fw_state="IDLE")
            self.model.on_done(p[0], p[1])
            self.scenario.on_done()
        self._emit("state")

    def _on_status(self, p):
        s = self.state
        fw = C.FW_STATES[p[2]] if p[2] < len(C.FW_STATES) else f"?{p[2]}"
        d = C.FW_DIRS[p[1]] if p[1] < 3 else "?"
        floor, req = p[0], p[3]
        prev = self._prev
        self._prev = (floor, fw, d)
        if not self._car_synced:
            self.car.reset(floor)
            self._car_synced = True

        # ---- 모델 비교 ----
        if prev:
            p_floor, p_fw, p_dir = prev
            was_moving = p_fw in ("MOVING_UP", "MOVING_DOWN")
            moving = fw in ("MOVING_UP", "MOVING_DOWN")
            if moving and not was_moving:
                self.model.on_depart(floor, d, p_dir if p_fw.startswith("DOOR") else "-")
                self._last_event = time.time()
            if moving and was_moving and floor != p_floor:
                self.model.on_pass(floor, d)          # 서지 않고 지나간 층
                self._last_event = time.time()
            stable = (fw == p_fw and floor == p_floor and time.time() - self._last_event > SETTLE_S)
            if fw in ("DOOR_OPENING", "DOOR_OPEN"):
                self.model.on_door_open_tick(floor, d)
            self.model.compare_status(req, stable)
        if d in ("UP", "DOWN"):
            self._last_dir = d

        changed = s.update(floor=floor, direction=d, fw_state=fw, req=req)
        # 프레임을 놓쳤어도 펌웨어 상태로 문 목표를 맞춘다
        if fw in ("DOOR_OPENING", "DOOR_OPEN") and not s.door_target_open:
            self._set_door(True)
        elif fw == "DOOR_CLOSING" and s.door_target_open:
            self._set_door(False)
        elif fw in ("IDLE", "MOVING_UP", "MOVING_DOWN", "INIT") and s.door_target_open:
            self._set_door(False)
        if self.log_status or changed:
            self._emit("log", "RX " + C.describe(C.CMD_STATUS, p) + f"  floor={floor} {fw} dir={d} req=0x{req:02X}")
        if changed:
            self._emit("state")

    def _on_hw_event(self, btn, card, master):
        """보드 버튼 (계획서 4.1). 펌웨어가 이미 처리한 입력을 모델에도 똑같이 넣는다"""
        s = self.state
        s.update(hw_card_id=card)
        ctype = CARD_DB.get(card, ("?", "?"))[0]
        names = {1: "BTN1", 2: "BTN2", 3: "BTN3", 4: "BTN4(내부 리더)", 5: "BTN5(카드 선택)"}
        if btn in (1, 2, 3) and master:
            self._emit("log", f"    보드 {names[btn]} : 마스터 모드 목적층 {btn}층")
            self.model.master_press(btn, s.floor)
            self.car.master_press(btn)
        elif btn in (1, 2, 3, 4):
            what = "내부 리더" if btn == 4 else f"{btn}층 외부 리더"
            ok = self.model.card_tag(btn, ctype, card)
            self.car.card_tag(btn, ctype, card)
            self._emit("log", f"    보드 {names[btn]} : 카드{card}({ctype}) {what} 태그" + ("" if ok else " (권한 없음, 무시)"))
        else:
            self._emit("log", f"    보드 {names.get(btn, btn)} : 카드{card}({ctype})")
        self._last_event = time.time()

    # ---------------- 모델 칸 (화면에 그리는 엘리베이터) ----------------
    def _tick_car(self, now):
        dt = min(now - self._car_last, 0.2)
        self._car_last = now
        if not self._car_synced:
            return
        for kind, f in self.car.tick(dt, self.travel_hint):
            if kind in ("arrive", "reopen"):
                self._emit("log", f"[모델 칸] {f}층 {'다시 열림' if kind == 'reopen' else '도착'}")
        # 둘 다 할 일 없이 섰는데 층이 다르면 알리고 모델 칸을 STM32 층에 맞춤
        s = self.state
        both_idle = (s.fw_state == "IDLE" and s.req == 0 and self.car.state == "IDLE" and self.car.sch.req == 0)
        if both_idle and s.floor != self.car.floor:
            if self._both_idle_since is None:
                self._both_idle_since = now
            elif now - self._both_idle_since > 1.0:
                self._emit("error", f"[검증 불일치] 대기 층 STM32 {s.floor}층 / 모델 칸 {self.car.floor}층 "
                                    f"-> 모델 칸을 {s.floor}층에 맞춤")
                self.car.reset(s.floor)
                self._both_idle_since = None
        else:
            self._both_idle_since = None

    def _model_note(self, kind, text):
        self._emit("error" if kind == "check_bad" else "log", text)

    # ---------------- 문 핸드셰이크 ----------------
    def _set_door(self, open_):
        self.state.update(door_target_open=open_)
        self._door_done = None      # frontend 애니메이션이 끝나면 door_anim_done() 으로 알려줌
        self._last_ack = 0.0
        if not open_:
            self._door_open_at = None
        self._emit("state")

    def door_anim_done(self, opened: bool):
        """frontend : 문 애니메이션이 목표(열림/닫힘)에 도착했을 때 호출"""
        if opened == self.state.door_target_open and self._door_done is None:
            self._door_done = opened
            if opened:
                self._door_open_at = time.time()

    def _door_handshake(self, now):
        s = self.state
        if self._door_done is None or now - self._last_ack < ACK_RETRY_S:
            return
        if self._door_done and s.door_target_open and s.fw_state == "DOOR_OPENING":
            self._last_ack = now
            self._send(C.CMD_DOOR_OPENED, s.floor)
        elif not self._door_done and not s.door_target_open and s.fw_state == "DOOR_CLOSING":
            self._last_ack = now
            self._send(C.CMD_DOOR_CLOSED, s.floor)

    def _tick_timers(self, now):
        s = self.state
        sec = 0
        if self._door_open_at and s.door_target_open:
            sec = max(0, int(DOOR_OPEN_S - (now - self._door_open_at) + 0.999))
        if s.update(door_sec=sec, master=self.model.master):
            self._emit("state")

    # ---------------- 사용자 입력 ----------------
    def select_card(self, card_id):
        self.state.update(card_id=card_id, card_type=CARDS[card_id][0])
        self._emit("log", f"GUI 카드 선택 {card_id}({CARDS[card_id][0]})")
        self._emit("state")

    def tag(self, reader):
        """GUI 에서 선택한 카드로 태그"""
        self.tag_as(reader, self.state.card_id)

    def tag_person(self, reader, ctype, name):
        """랜덤 시나리오 : 카드 DB 와 상관없는 이용객 (펌웨어는 카드 종류만 봄)"""
        ok = self.model.card_tag(reader, ctype, name=name)
        self.car.card_tag(reader, ctype, name=name)
        self._send(C.CMD_CARD_TAG, reader, C.CARD_TYPE_CODE[ctype],
                   note=f"{READERS[reader]} {name}({ctype})" + ("" if ok else " (권한 없음 -> 무시돼야 함)"))
        self._last_event = time.time()

    def tag_as(self, reader, card_id):
        ctype = CARD_DB[card_id][0]
        ok = self.model.card_tag(reader, ctype, card_id)
        self.car.card_tag(reader, ctype, card_id)
        self._send(C.CMD_CARD_TAG, reader, C.CARD_TYPE_CODE[ctype],
                   note=f"{READERS[reader]} 카드{card_id}({ctype})" + ("" if ok else " (권한 없음 -> 무시돼야 함)"))
        self._last_event = time.time()

    def master_dest(self, floor):
        master = self.model.master
        self._send(C.CMD_DEST_BTN, floor, note=f"목적층 {floor}F" + ("" if master else " (마스터 모드 아님 -> 펌웨어가 무시)"))
        if master:
            self.model.master_press(floor, self.state.floor)
        if self.car.master:
            self.car.master_press(floor)
        self._last_event = time.time()

    def request_init(self):
        self.model.reset()
        self.car.reset(self.car.floor, go_home=True)
        self._send(C.CMD_INIT, note="1층으로 초기화")

    def start_random(self):
        if not self.link:
            self._emit("error", "연결 안 됨")
            return
        if self.scenario.steps:
            self._emit("log", f"[랜덤 #{self.scenario.count}] 아직 진행 중이에요. 끝난 뒤 다시 눌러 주세요.")
            return
        self.scenario.start_random(travel_s=self.travel_hint)

    # ---------------- 내부 ----------------
    def _send(self, cmd, p0=0, p1=0, p2=0, p3=0, note="", quiet=False):
        if not self.link:
            self._emit("error", "연결 안 됨")
            return
        frame = C.build(cmd, p0, p1, p2, p3)
        try:
            self.link.write(frame)
        except Exception as e:
            self._emit("error", f"송신 실패 : {e}")
            return
        if not quiet:
            self._emit("log", "TX " + C.describe(cmd, [p0, p1, p2, p3]) + (f"  {note}" if note else ""))

    def _emit(self, kind, text=""):
        self.on_event(Event(kind, text))
