"""프레임 codec : 펌웨어 protocol.h / uart.c 와 같은 형식

    SOF(0xAA) | LEN(0x05) | CMD | P0 P1 P2 P3 | CHK
    CHK = (LEN + CMD + P0 + P1 + P2 + P3) & 0xFF   (uart.c 덧셈 체크섬)
"""

SOF = 0xAA
PAYLOAD_LEN = 4
LEN = 1 + PAYLOAD_LEN

# GUI -> STM32
CMD_CARD_TAG = 0x01     # P0 리더(1~4), P1 카드 종류(0 권한없음, 1 손님, 2 직원)
CMD_DEST_BTN = 0x02     # P0 목적층 (마스터 모드일 때만 반영)
CMD_DOOR_OPENED = 0x03  # 문 다 열림
CMD_DOOR_CLOSED = 0x04  # 문 다 닫힘
CMD_STATUS_REQ = 0x05
CMD_INIT = 0x06

# STM32 -> GUI
CMD_STATUS = 0x81       # P0 층, P1 방향, P2 상태, P3 요청 레지스터
CMD_ARRIVED = 0x82      # P0 층, P1 방향  -> 문 열기
CMD_DOOR_CLOSE = 0x83   # P0 층           -> 문 닫기
CMD_DOOR_REOPEN = 0x84  # P0 층           -> 닫던 문 다시 열기
CMD_HW_EVENT = 0x85     # P0 버튼(1~5), P1 카드 번호, P2 누른 순간 마스터 모드
CMD_DONE = 0x86         # P0 층, P1 요청 레지스터

CMD_NAME = {
    CMD_CARD_TAG: "CARD_TAG", CMD_DEST_BTN: "DEST_BTN", CMD_DOOR_OPENED: "DOOR_OPENED",
    CMD_DOOR_CLOSED: "DOOR_CLOSED", CMD_STATUS_REQ: "STATUS_REQ", CMD_INIT: "INIT",
    CMD_STATUS: "STATUS", CMD_ARRIVED: "ARRIVED", CMD_DOOR_CLOSE: "DOOR_CLOSE",
    CMD_DOOR_REOPEN: "DOOR_REOPEN", CMD_HW_EVENT: "HW_EVENT", CMD_DONE: "DONE",
}

# ap_main.c run_state_t (STATUS P2)
FW_STATES = ["INIT", "IDLE", "MOVING_UP", "MOVING_DOWN", "DOOR_OPENING", "DOOR_OPEN", "DOOR_CLOSING"]
# scheduler.h sch_dir_t (STATUS P1)
FW_DIRS = ["-", "UP", "DOWN"]
# card_auth.h
CARD_TYPE_CODE = {"NO_AUTH": 0, "GUEST": 1, "STAFF": 2}


def checksum(body):
    return sum(body) & 0xFF


def build(cmd, p0=0, p1=0, p2=0, p3=0):
    body = [LEN, cmd, p0 & 0xFF, p1 & 0xFF, p2 & 0xFF, p3 & 0xFF]
    return bytes([SOF] + body + [checksum(body)])


def describe(cmd, p):
    return f"{CMD_NAME.get(cmd, hex(cmd))} [{' '.join(f'{x:02X}' for x in p)}]"


class FrameCodec:
    """바이트 -> (cmd, [p0..p3]) 프레임. uart.c rx_parse_byte 와 같은 상태 기계"""

    name = "frame"

    def __init__(self):
        self.state = "SOF"
        self.buf = []
        self.length = 0

    def feed(self, data: bytes):
        frames, errors = [], []
        for b in data:
            if self.state == "SOF":
                if b == SOF:
                    self.state = "LEN"
            elif self.state == "LEN":
                if b == 0 or b >= 16:
                    self.state = "SOF"
                else:
                    self.length, self.buf, self.state = b, [], "DATA"
            elif self.state == "DATA":
                self.buf.append(b)
                if len(self.buf) >= self.length:
                    self.state = "CHK"
            elif self.state == "CHK":
                if checksum([self.length] + self.buf) == b and self.length == LEN:
                    frames.append((self.buf[0], self.buf[1:]))
                else:
                    errors.append(f"bad frame {bytes([SOF, self.length] + self.buf + [b]).hex(' ').upper()}")
                self.state = "SOF"
        return frames, errors
