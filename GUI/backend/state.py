"""엘리베이터 상태 (backend 가 갱신, frontend 는 읽기만 함)"""

from dataclasses import dataclass, field

FLOORS = (1, 2, 3)

CARDS = {  # 펌웨어 card_auth.c card_db 와 같은 순서
    0: ("GUEST", "손님 A (2층)"),
    1: ("GUEST", "손님 B (2층)"),
    2: ("STAFF", "직원"),
    3: ("NO_AUTH", "권한 없음"),
}

READERS = {1: "HALL_1F", 2: "HALL_2F", 3: "HALL_3F", 4: "CAR"}


@dataclass
class ElevatorState:
    connected: bool = False
    floor: int = 1              # 현재 층 (STATUS P0)
    fw_state: str = "INIT"      # 펌웨어 상태 (STATUS P2) : INIT / IDLE / MOVING_UP ...
    direction: str = "-"        # UP / DOWN / -
    req: int = 0                # 요청 레지스터 (STATUS P3)
    door_target_open: bool = False  # 문을 열어야 하면 True (ARRIVED / REOPEN / DOOR_CLOSE 로 바뀜)
    door_sec: int = 0           # 문 닫힐 때까지 남은 초 (GUI 가 DOOR_OPENED 보낸 뒤 5초 계산)
    master: bool = False        # 마스터 모드 (GUI 추정 : 직원 내부 태그 후 5초)
    card_id: int = 0            # GUI 에서 태그할 카드 0~3
    card_type: str = "GUEST"
    hw_card_id: int = 0         # 보드 BTN5 로 고른 카드 (HW_EVENT P1)

    @property
    def moving(self):
        return self.fw_state in ("MOVING_UP", "MOVING_DOWN")

    def update(self, **kw):
        """바뀐 값이 있으면 True"""
        changed = False
        for k, v in kw.items():
            if hasattr(self, k) and getattr(self, k) != v:
                setattr(self, k, v)
                changed = True
        return changed


@dataclass
class Event:
    """backend -> frontend 알림"""
    kind: str                 # "state" / "log" / "error"
    text: str = ""
    extra: dict = field(default_factory=dict)
