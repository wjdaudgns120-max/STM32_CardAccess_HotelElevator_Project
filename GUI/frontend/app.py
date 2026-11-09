"""frontend : 화면만 담당 (tkinter)

- 사용자가 누른 것은 backend 메서드로 넘김
- backend 가 보낸 Event 를 받아 화면만 다시 그림
- 통신, 프로토콜, 상태 판단 코드는 여기에 넣지 않음
"""

import json
import os
import time
import tkinter as tk
from tkinter import ttk

from backend import ElevatorBackend
from backend.mock_fw import FLOOR_TIME as MOCK_FLOOR_TIME
from backend.state import CARDS, FLOORS

# 그림 크기 (실물 나무 엘리베이터 비율)
CANVAS_W, CANVAS_H = 330, 480
SHAFT_CX = 140                             # 승강로 가운데 x
FRAME_L, FRAME_R, POST_W = 60, 220, 12     # 양쪽 기둥
TOP_Y, AXLE_Y, BASE_Y = 60, 86, 448        # 윗판, 축, 바닥판
CAR_W, CAR_H = 110, 104                    # 엘리베이터 칸
FLOOR_H = 110                              # 층 간격 (화면)

ANIM_MS = 30                # 애니메이션 주기 (약 33fps)
FLOOR_TRAVEL_S = 3.0        # 한 층 이동 시간 처음 추정값 (실제 이동하면 측정값으로 바뀜)
DOOR_MOVE_S = 2.0           # 문 열림 / 닫힘 시간 (계획서 3.8 : 각 2초)

SETTINGS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "settings.json")


def load_settings():
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(values):
    data = load_settings()
    data.update(values)
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


WOOD, WOOD_EDGE, WOOD_DARK, WOOD_LIGHT = "#ecd9b8", "#9c6b3e", "#e0c9a0", "#f6ead3"
DOOR_COLOR = "#d7b98e"
COP_W = 130                                # 조작반 폭
HALL_X = 284                               # 승강장 외부 리더 x
STEEL, STEEL_EDGE = "#cfd8dc", "#90a4ae"
BTN_OFF, BTN_ON, BTN_PRESS, BTN_DISABLED = "#ffffff", "#ffd180", "#ffab40", "#cfd8dc"
CARD_COLOR = {"GUEST": "#c8e6c9", "STAFF": "#bbdefb", "NO_AUTH": "#ffcdd2"}
SUMMARY_TAGS = ("[랜덤", "[손님]", "[검증", "[GUI]", "[모델 칸]")   # 디버그 로그를 끈 상태에서 보이는 로그
HW_MARK = "#e53935"                        # 실제 STM32 위치 표시 (점선)
LED_COLOR = {"IDLE": "#9e9e9e", "MOVING": "#1e88e5", "DOOR": "#43a047"}


class ElevatorApp:
    def __init__(self, root):
        self.root = root
        root.title("Elevator GUI")
        self.backend = ElevatorBackend(on_event=self.on_event)

        self._build_top()
        body = ttk.Frame(root, padding=8)
        body.pack(fill="both", expand=True)
        self._build_shaft(body)
        self._build_hall_readers()
        self._build_cop(body)
        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self._build_status(right)
        self._build_settings(right)
        self._build_log(right)

        self.refresh_ports()
        self.redraw()
        self._poll()
        self._animate()

    # ================= 화면 구성 =================
    def _build_top(self):
        top = ttk.Frame(self.root, padding=(8, 8, 8, 0))
        top.pack(fill="x")
        ttk.Label(top, text="Port").pack(side="left")
        self.port_cb = ttk.Combobox(top, width=12, state="readonly")
        self.port_cb.pack(side="left", padx=4)
        ttk.Button(top, text="↻", width=3, command=self.refresh_ports).pack(side="left")
        self.conn_btn = ttk.Button(top, text="Connect", command=self.toggle_connect)
        self.conn_btn.pack(side="left", padx=8)
        self.conn_lbl = ttk.Label(top, text="● 연결 안 됨", foreground="#c62828")
        self.conn_lbl.pack(side="left")
        ttk.Button(top, text="INIT (1층 복귀)", command=lambda: self.backend.request_init()).pack(side="right")
        ttk.Button(top, text="랜덤 시나리오", command=self._start_random).pack(side="right", padx=6)

    def _build_shaft(self, parent):
        """실물(나무 프레임 엘리베이터)을 본뜬 그림
        바닥판 + 양쪽 기둥 + 윗판, 가운데 뒷기둥과 층 센서,
        실에 매달린 나무 칸(윗판, 양옆 벽, 뒷판, 바닥판)
        """
        cv = self.cv = tk.Canvas(parent, width=CANVAS_W, height=CANVAS_H, bg="#fafafa", highlightthickness=1)
        cv.pack(side="left")
        cx = SHAFT_CX

        # 바닥판
        cv.create_rectangle(FRAME_L - 14, BASE_Y, FRAME_R + 14, BASE_Y + 12, fill=WOOD, outline=WOOD_EDGE, width=2)
        cv.create_oval(FRAME_L - 8, BASE_Y + 11, FRAME_L + 8, BASE_Y + 17, fill="#1e88e5", outline="")
        cv.create_oval(FRAME_R - 8, BASE_Y + 11, FRAME_R + 8, BASE_Y + 17, fill="#1e88e5", outline="")

        # 가운데 뒷기둥 (칸 뒤에 있음)
        cv.create_rectangle(cx - 12, TOP_Y + 14, cx + 12, BASE_Y, fill=WOOD_DARK, outline=WOOD_EDGE)

        # 양쪽 기둥
        cv.create_rectangle(FRAME_L, TOP_Y + 8, FRAME_L + POST_W, BASE_Y, fill=WOOD, outline=WOOD_EDGE, width=2)
        cv.create_rectangle(FRAME_R - POST_W, TOP_Y + 8, FRAME_R, BASE_Y, fill=WOOD, outline=WOOD_EDGE, width=2)
        # 오른쪽 기둥의 층 번호 (실물처럼 동그라미 숫자)
        for f in FLOORS:
            y = self.sensor_y(f)
            cv.create_oval(FRAME_R - POST_W + 1, y - 8, FRAME_R - 1, y + 8, outline="#5d4037")
            cv.create_text(FRAME_R - POST_W / 2, y, text=str(f), font=("Arial", 9, "bold"), fill="#5d4037")
            cv.create_text(FRAME_L - 22, self.floor_y(f), text=f"{f}F", font=("Arial", 13, "bold"), fill="#37474f")

        # 윗판
        cv.create_rectangle(FRAME_L - 14, TOP_Y, FRAME_R + 14, TOP_Y + 14, fill=WOOD, outline=WOOD_EDGE, width=2)

        # 실 (윗판 -> 칸 윗판)
        self.rope = cv.create_line(cx + 5, TOP_Y + 14, cx + 5, TOP_Y + 14, fill="#bdbdbd", width=2)

        # 엘리베이터 칸
        self.car_back = cv.create_rectangle(0, 0, 0, 0, fill=WOOD_LIGHT, outline="")          # 뒷판
        self.car_txt = cv.create_text(0, 0, font=("Arial", 13, "bold"), fill="#5d4037")
        self.door_l = cv.create_rectangle(0, 0, 0, 0, fill=DOOR_COLOR, outline=WOOD_EDGE)
        self.door_r = cv.create_rectangle(0, 0, 0, 0, fill=DOOR_COLOR, outline=WOOD_EDGE)
        self.car_wall_l = cv.create_rectangle(0, 0, 0, 0, fill=WOOD, outline=WOOD_EDGE, width=2)
        self.car_wall_r = cv.create_rectangle(0, 0, 0, 0, fill=WOOD, outline=WOOD_EDGE, width=2)
        self.car_top = cv.create_rectangle(0, 0, 0, 0, fill=WOOD, outline=WOOD_EDGE, width=2)
        self.car_floor = cv.create_rectangle(0, 0, 0, 0, fill=WOOD, outline=WOOD_EDGE, width=2)
        self.screws = [cv.create_oval(0, 0, 0, 0, fill="#b0bec5", outline="#607d8b") for _ in range(3)]
        self.led = cv.create_oval(0, 0, 0, 0, fill="#9e9e9e", outline="")                      # 상태 표시등
        self.arrow_txt = cv.create_text(0, 0, font=("Arial", 12, "bold"), fill="#1565c0")

        # 실제 STM32 위치 (점선 테두리). 칸 그림은 모델 칸이고, 이 점선이 하드웨어 위치
        self.hw_mark = cv.create_rectangle(0, 0, 0, 0, outline=HW_MARK, width=2, dash=(5, 3))
        self.hw_lbl = cv.create_text(0, 0, text="HW", font=("Arial", 8, "bold"), fill=HW_MARK, anchor="e")
        cv.create_text(CANVAS_W / 2, 14, text="칸 = 모델 예상   빨간 점선 = 실제 STM32",
                       font=("Arial", 8, "bold"), fill="#455a64")

        # 애니메이션 상태
        self.car_pos = 1.0                  # 실제 STM32 위치 (1.0 ~ 3.0, 소수 = 층 사이) : 점선 표시
        self.door_open = 0.0                # 실제 문 (0 = 닫힘, 1 = 열림) : DOOR_OPENED / CLOSED 회신용
        self.travel_s = float(load_settings().get("floor_travel_s", FLOOR_TRAVEL_S))  # 한 층 이동 시간
        self._measured_once = False
        self._last_floor = None
        self._floor_tick = None
        self._was_moving = False
        self._anim_last = time.time()

    def _build_status(self, parent):
        box = ttk.LabelFrame(parent, text="상태", padding=6)
        box.pack(fill="x")
        self.st_vars = {}
        for i, (key, label) in enumerate([("floor", "현재 층"), ("fw_state", "펌웨어 상태"), ("direction", "방향"),
                                          ("door_sec", "문 닫힘"), ("card", "GUI 카드"),
                                          ("hw_card", "보드 카드(BTN5)"), ("master", "마스터 모드"), ("req", "요청 비트")]):
            ttk.Label(box, text=label, width=12).grid(row=i // 2, column=(i % 2) * 2, sticky="w")
            v = tk.StringVar(value="-")
            ttk.Label(box, textvariable=v, width=16, font=("Consolas", 10, "bold")).grid(
                row=i // 2, column=(i % 2) * 2 + 1, sticky="w")
            self.st_vars[key] = v

    # ---------- 승강장 외부 리더 (층마다, 승강로 오른쪽. 카드 리더만) ----------
    def _build_hall_readers(self):
        cv = self.cv
        x = HALL_X
        self.hall_reader = {}
        for f in FLOORS:
            y = self.floor_y(f)
            cv.create_rectangle(x - 22, y - 30, x + 22, y + 30, fill=STEEL, outline=STEEL_EDGE, width=2)
            cv.create_text(x, y - 20, text=f"{f}F", font=("Arial", 9, "bold"), fill="#37474f")
            box = cv.create_rectangle(x - 15, y - 10, x + 15, y + 22, fill="#263238", outline="#455a64", width=2,
                                      tags=(f"hreader{f}", "btn"))
            cv.create_text(x, y + 6, text=")))", font=("Arial", 9, "bold"), fill="#80deea", tags=(f"hreader{f}", "btn"))
            self.hall_reader[f] = box
            cv.tag_bind(f"hreader{f}", "<Button-1>", lambda e, f=f: self._press_hall_reader(f))
        cv.tag_bind("btn", "<Enter>", lambda e: cv.config(cursor="hand2"))
        cv.tag_bind("btn", "<Leave>", lambda e: cv.config(cursor=""))
    # ---------- 칸 안 조작반 (COP) ----------
    def _build_cop(self, parent):
        """엘리베이터 안쪽 벽의 조작반 : 층 표시창, 층 버튼(마스터 모드 목적층), 내부 카드 리더, 내 카드"""
        cv = self.cop = tk.Canvas(parent, width=COP_W, height=CANVAS_H, bg="#fafafa", highlightthickness=0)
        cv.pack(side="left", padx=(8, 0))
        x0, x1 = 8, COP_W - 8
        mx = COP_W // 2
        cv.create_rectangle(x0, 6, x1, CANVAS_H - 6, fill=STEEL, outline=STEEL_EDGE, width=3)
        cv.create_text(mx, 20, text="조작반", font=("Arial", 9, "bold"), fill="#455a64")

        # 층 표시창
        cv.create_rectangle(x0 + 14, 32, x1 - 14, 86, fill="#111", outline="#455a64", width=2)
        self.cop_arrow = cv.create_text(mx - 24, 59, text="", font=("Arial", 16, "bold"), fill="#ff6d00")
        self.cop_floor = cv.create_text(mx + 10, 59, text="1", font=("Consolas", 30, "bold"), fill="#ff6d00")

        # 마스터 모드 표시등
        self.cop_master = cv.create_oval(x0 + 18, 98, x0 + 30, 110, fill="#9e9e9e", outline="")
        cv.create_text(x0 + 36, 104, text="MASTER", anchor="w", font=("Arial", 8, "bold"), fill="#455a64")

        # 층 버튼 3, 2, 1 : 카드 권한에 맞는 버튼만 눌림 (_allowed_floors)
        self.cop_btn = {}
        for i, f in enumerate((3, 2, 1)):
            y = 140 + i * 48
            btn = cv.create_oval(mx - 20, y - 20, mx + 20, y + 20, fill=BTN_OFF, outline="#78909c", width=3,
                                 tags=(f"cop{f}", "btn"))
            txt = cv.create_text(mx, y, text=str(f), font=("Arial", 14, "bold"), fill="#455a64", tags=(f"cop{f}", "btn"))
            self.cop_btn[f] = (btn, txt)
            cv.tag_bind(f"cop{f}", "<Button-1>", lambda e, f=f: self._press_cop(f))

        # 내부 카드 리더 (직원 -> 마스터 모드). 문이 열려 있을 때(탑승한 뒤)만 사용
        self.cop_hint = cv.create_text(mx, 280, text="", font=("Arial", 8, "bold"), fill="#37474f")
        ry = 300
        self.reader_box = cv.create_rectangle(x0 + 14, ry, x1 - 14, ry + 46, fill="#263238", outline="#455a64",
                                              width=2, tags=("reader", "btn"))
        cv.create_text(mx, ry + 16, text=")))", font=("Arial", 12, "bold"), fill="#80deea", tags=("reader", "btn"))
        cv.create_text(mx, ry + 34, text="내부 리더", font=("Arial", 8), fill="#b2ebf2", tags=("reader", "btn"))
        cv.tag_bind("reader", "<Button-1>", lambda e: self._press_reader())
        # 내 카드 (누르면 그 카드를 들고 리더에 태그함)
        cv.create_text(mx, 366, text="내 카드", font=("Arial", 9, "bold"), fill="#455a64")
        self.card_items = {}
        for cid, (ctype, name) in CARDS.items():
            y = 384 + cid * 22
            r = cv.create_rectangle(x0 + 10, y, x1 - 10, y + 18, fill=CARD_COLOR[ctype], outline="#607d8b",
                                    width=1, tags=(f"card{cid}", "btn"))
            cv.create_text(mx, y + 9, text=f"{cid} {name}", font=("Arial", 8, "bold"), fill="#263238",
                           tags=(f"card{cid}", "btn"))
            self.card_items[cid] = r
            cv.tag_bind(f"card{cid}", "<Button-1>", lambda e, c=cid: self.backend.select_card(c))
        cv.tag_bind("btn", "<Enter>", lambda e: cv.config(cursor="hand2"))
        cv.tag_bind("btn", "<Leave>", lambda e: cv.config(cursor=""))

    def _allowed_floors(self):
        """층 버튼 3·2·1 : 목적층 버튼. 직원이 내부 리더에 카드를 대서 마스터 모드인 5초 동안만 눌림"""
        s = self.backend.state
        return set(FLOORS) if (s.connected and s.card_type == "STAFF" and s.master) else set()

    def _hall_allowed(self):
        """외부 리더 : 손님 1·2층, 직원 1~3층, 권한 없음은 없음 (계획서 3.2, 3.3)"""
        s = self.backend.state
        if not s.connected:
            return set()
        return {"STAFF": set(FLOORS), "GUEST": {1, 2}}.get(s.card_type, set())

    def _reader_allowed(self):
        """내부 리더 : 직원이 탑승한 뒤 (문이 열려 있을 때) 카드를 한 번 더 대서 마스터 모드"""
        s = self.backend.state
        return s.connected and s.card_type == "STAFF" and s.fw_state in ("DOOR_OPENING", "DOOR_OPEN")

    def _press_cop(self, f):
        if f not in self._allowed_floors():
            return                      # 마스터 모드가 아니면 눌리지 않음
        self._flash(self.cop, self.cop_btn[f][0])
        self.backend.master_dest(f)

    def _press_hall_reader(self, f):
        if f not in self._hall_allowed():
            return                      # 권한 없음 : 눌리지 않음
        self._flash(self.cv, self.hall_reader[f])
        self.backend.tag(f)             # 그 층 외부 리더에 태그 -> 호출
    def _press_reader(self):
        if self._reader_allowed():
            self.backend.tag(4)         # 내부 리더 (직원 -> 마스터 모드 5초)
    def _flash(self, cv, item):
        cv.itemconfig(item, fill=BTN_PRESS)
        self.root.after(150, self._draw_panels)

    def _draw_panels(self):
        """버튼 불빛 / 표시창을 펌웨어 상태에 맞춤"""
        s = self.backend.state
        allowed = self._allowed_floors()
        call_bits = {1: 0x01, 2: 0x02 | 0x04, 3: 0x08}
        for f, (btn, txt) in self.cop_btn.items():
            on = bool(s.req & (1 << (3 + f)))                      # 목적층이 등록돼 있으면 불
            if on:
                fill, fg, outline = BTN_ON, "#bf360c", "#78909c"
            elif f in allowed:
                fill, fg, outline = BTN_OFF, "#455a64", "#1565c0"
            else:
                fill, fg, outline = BTN_DISABLED, "#90a4ae", "#b0bec5"
            self.cop.itemconfig(btn, fill=fill, outline=outline)
            self.cop.itemconfig(txt, fill=fg)
        # 외부 리더 : 호출 대기 중이면 주황, 쓸 수 있으면 하늘색, 권한 없으면 어두운 테두리
        hall_ok = self._hall_allowed()
        for f, box in self.hall_reader.items():
            if s.req & call_bits[f]:
                outline, width = "#ff9100", 3
            elif f in hall_ok:
                outline, width = "#80deea", 2
            else:
                outline, width = "#455a64", 2
            self.cv.itemconfig(box, fill="#263238", outline=outline, width=width)
        self.cop.itemconfig(self.reader_box, fill="#263238")
        if s.card_type == "GUEST":
            hint = "손님: 외부 리더로 호출"
        elif s.card_type == "STAFF":
            if s.master:
                hint = "목적층 선택 (5초)"
            elif self._reader_allowed():
                hint = "내부 리더에 카드"
            else:
                hint = "직원: 외부 리더로 호출"
        else:
            hint = "권한 없음"
        self.cop.itemconfig(self.reader_box, outline="#80deea" if self._reader_allowed() else "#455a64")
        self.cop.itemconfig(self.cop_hint, text=hint)
        m = self.backend.car                                     # 칸 안 표시창도 모델 칸 기준
        self.cop.itemconfig(self.cop_floor, text=str(m.floor))
        self.cop.itemconfig(self.cop_arrow, text={"MOVING_UP": "▲", "MOVING_DOWN": "▼"}.get(m.state, ""))
        self.cop.itemconfig(self.cop_master, fill="#ffab00" if s.master else "#9e9e9e")
        for cid, r in self.card_items.items():
            sel = cid == s.card_id
            self.cop.itemconfig(r, width=3 if sel else 1, outline="#1565c0" if sel else "#607d8b")

    def _build_settings(self, parent):
        # GUI 이동 속도 : 실제 모터가 한 층 가는 데 걸리는 시간 (자동 측정 / 직접 입력)
        box = ttk.Frame(parent, padding=(0, 6, 0, 0))
        box.pack(fill="x")
        ttk.Label(box, text="한 층 이동(초)").pack(side="left")
        self.travel_var = tk.DoubleVar(value=round(self.travel_s, 1))
        sp = ttk.Spinbox(box, from_=0.5, to=60, increment=0.5, width=6, textvariable=self.travel_var,
                         command=self._on_travel_edit)
        sp.pack(side="left", padx=4)
        sp.bind("<Return>", self._on_travel_edit)
        sp.bind("<FocusOut>", self._on_travel_edit)
        self.auto_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(box, text="실제 이동으로 자동 측정", variable=self.auto_var).pack(side="left", padx=8)

    def _build_log(self, parent):
        box = ttk.LabelFrame(parent, text="로그", padding=4)
        box.pack(fill="both", expand=True)
        self.log = tk.Text(box, height=12, width=70, font=("Consolas", 9), state="disabled")
        # 로그 색 : 손님 이용 내역 / 검증 / 랜덤 시나리오
        self.log.tag_configure("guest", foreground="#2e7d32", font=("Consolas", 9, "bold"))
        self.log.tag_configure("ok", foreground="#1565c0")
        self.log.tag_configure("bad", foreground="#c62828", font=("Consolas", 9, "bold"))
        self.log.tag_configure("rand", foreground="#6a1b9a", font=("Consolas", 9, "bold"))
        sb = ttk.Scrollbar(box, command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        self.log.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(4, 0))
        self.debug_var = tk.BooleanVar(value=False)     # 끄면 [랜덤] [손님] [검증] [GUI] 로그만 보임
        ttk.Checkbutton(bar, text="디버그 로그 (TX/RX 프레임)", variable=self.debug_var).pack(side="left")
        ttk.Button(bar, text="로그 지우기", command=self.clear_log).pack(side="right")

    # ================= 동작 =================
    def refresh_ports(self):
        ports = self.backend.ports()
        self.port_cb["values"] = ports
        if ports and not self.port_cb.get():
            self.port_cb.set(ports[-1] if len(ports) > 1 else ports[0])

    def _start_random(self):
        # 랜덤 입력 타이밍을 실제 이동 속도에 맞춰 흩어 놓음
        self.backend.travel_hint = MOCK_FLOOR_TIME if self.backend.is_mock else self.travel_s
        self.backend.start_random()

    def toggle_connect(self):
        if self.backend.state.connected:
            self.backend.disconnect()
        elif self.port_cb.get():
            self.backend.connect(self.port_cb.get())

    def _poll(self):
        self.backend.poll()
        self.root.after(50, self._poll)

    def on_event(self, ev):
        if ev.kind == "state":
            self.redraw()
        elif ev.kind == "error":
            self.write_log("[ERR] " + ev.text)          # 오류, 검증 불일치는 항상 표시
        elif ev.kind == "log":
            if self.debug_var.get() or ev.text.lstrip().startswith(SUMMARY_TAGS):
                self.write_log(ev.text)

    # ================= 그리기 =================
    @staticmethod
    def floor_y(f):
        "칸 중심의 y 좌표"
        return BASE_Y - 10 - CAR_H / 2 - FLOOR_H * (f - 1)

    def sensor_y(self, f):
        return self.floor_y(f) - CAR_H / 2 + 14

    # ---------- 애니메이션 (펌웨어 상태를 보고 화면 위치 / 문을 부드럽게 따라감) ----------
    def _animate(self):
        now = time.time()
        dt = min(now - self._anim_last, 0.1)
        self._anim_last = now
        s = self.backend.state

        # 층이 바뀐 시간 간격으로 한 층 이동 시간을 측정
        # (마지막 층 도착은 floor 와 DOOR 가 같이 오므로 '직전 상태가 MOVING' 으로 판단)
        if s.floor != self._last_floor:
            if self._last_floor is not None and self._was_moving and self._floor_tick:
                self._learn_travel(now - self._floor_tick)
            self._last_floor = s.floor
            self._floor_tick = now
        if s.moving and not self._was_moving:
            self._floor_tick = now          # 출발 시각부터 측정
        self._was_moving = s.moving

        # 1) 실제 위치 (점선) : 이동 중이면 다음 층 쪽으로 서서히, 아니면 현재 층으로
        travel = MOCK_FLOOR_TIME if self.backend.is_mock else self.travel_s
        self.backend.travel_hint = travel                # 모델 칸도 같은 이동 시간으로 움직임
        speed = 1.0 / max(travel, 0.3)                   # 층 / 초
        if s.moving:
            step = 1 if s.fw_state == "MOVING_UP" else -1
            nxt = min(max(s.floor + step, FLOORS[0]), FLOORS[-1])
            # 펌웨어는 층 센서가 감지될 때만 층을 바꿔 줌 -> 다음 층 바로 앞까지 가서 대기
            limit = s.floor + 0.95 * (nxt - s.floor)
            self.car_pos = self._approach(self.car_pos, limit, speed * dt)
        else:
            self.car_pos = self._approach(self.car_pos, float(s.floor), max(speed, 2.0) * dt)

        # 2) 문 : 펌웨어가 ARRIVED/REOPEN 을 보내면 열고, DOOR_CLOSE 를 보내면 닫음
        #    다 열리거나 닫히면 backend 에 알려서 DOOR_OPENED / DOOR_CLOSED 를 보내게 함
        at_floor = abs(self.car_pos - s.floor) < 0.02
        want_open = s.door_target_open and at_floor
        self.door_open = self._approach(self.door_open, 1.0 if want_open else 0.0, dt / DOOR_MOVE_S)
        if want_open and self.door_open >= 1.0:
            self.backend.door_anim_done(True)
        elif not s.door_target_open and self.door_open <= 0.0:
            self.backend.door_anim_done(False)

        self._draw_car()
        self.root.after(ANIM_MS, self._animate)

    def _learn_travel(self, measured):
        """측정한 한 층 이동 시간을 반영 (튀는 값은 무시, 평균으로 부드럽게) 하고 저장"""
        if not (0.3 < measured < 60):
            return
        if self.backend.is_mock:
            return          # MOCK 속도로 실제 보드용 값을 덮어쓰지 않음
        if self.auto_var.get():
            first = not self._measured_once
            self.travel_s = measured if first else 0.5 * self.travel_s + 0.5 * measured
            self._measured_once = True
            self.travel_var.set(round(self.travel_s, 1))
            save_settings({"floor_travel_s": round(self.travel_s, 2)})
        self.write_log(f"[GUI] 한 층 이동 시간 측정 {measured:.1f}s -> 사용 {self.travel_s:.1f}s")

    def _on_travel_edit(self, *_):
        try:
            v = float(self.travel_var.get())
        except (tk.TclError, ValueError):
            return
        if 0.3 <= v <= 60:
            self.travel_s = v
            save_settings({"floor_travel_s": v})

    @staticmethod
    def _approach(cur, target, max_step):
        if abs(target - cur) <= max_step:
            return target
        return cur + max_step if target > cur else cur - max_step

    def _draw_car(self):
        """칸 그림 = 모델 칸 (backend.car). 실제 STM32 위치는 점선으로만 표시"""
        m = self.backend.car
        cv = self.cv
        cx = SHAFT_CX
        x0, x1 = cx - CAR_W / 2, cx + CAR_W / 2

        # 실제 STM32 위치 (점선)
        hy = self.floor_y(1) - (self.car_pos - 1) * FLOOR_H
        cv.coords(self.hw_mark, x0 - 4, hy - CAR_H / 2 - 4, x1 + 4, hy + CAR_H / 2 + 4)
        cv.coords(self.hw_lbl, x0 - 8, hy + CAR_H / 2 - 4)

        yc = self.floor_y(1) - (m.pos - 1) * FLOOR_H
        y0, y1 = yc - CAR_H / 2, yc + CAR_H / 2
        wall, plate = 9, 10

        cv.coords(self.rope, cx + 5, TOP_Y + 14, cx + 5, y0)
        cv.coords(self.car_back, x0 + wall, y0, x1 - wall, y1)
        cv.coords(self.car_wall_l, x0, y0, x0 + wall, y1)
        cv.coords(self.car_wall_r, x1 - wall, y0, x1, y1)
        cv.coords(self.car_top, x0 - 6, y0 - plate, x1 + 6, y0)
        cv.coords(self.car_floor, x0 - 6, y1 - 2, x1 + 6, y1 + plate - 2)
        for i, sx in enumerate((x0 + 6, cx, x1 - 6)):
            cv.coords(self.screws[i], sx - 3, y0 - plate / 2 - 3, sx + 3, y0 - plate / 2 + 3)

        # 문 : 양옆 벽 사이에서 가운데부터 열림
        inner_l, inner_r = x0 + wall, x1 - wall
        half = (inner_r - inner_l) / 2
        gap = half * m.door
        hidden = "hidden" if gap >= half - 1 else "normal"
        cv.coords(self.door_l, inner_l, y0, inner_l + half - gap, y1 - 2)
        cv.coords(self.door_r, inner_l + half + gap, y0, inner_r, y1 - 2)
        cv.itemconfig(self.door_l, state=hidden)
        cv.itemconfig(self.door_r, state=hidden)

        kind = "MOVING" if m.moving else ("DOOR" if m.state.startswith("DOOR") else "IDLE")
        cv.coords(self.led, x1 - 18, y0 - plate / 2 - 3, x1 - 12, y0 - plate / 2 + 3)
        cv.itemconfig(self.led, fill=LED_COLOR[kind])

        cv.coords(self.car_txt, cx, yc)
        cv.itemconfig(self.car_txt, text=f"{m.door_sec}s" if m.door_sec > 0 else "")
        cv.coords(self.arrow_txt, x0 - 16, yc)
        cv.itemconfig(self.arrow_txt, text={"MOVING_UP": "▲", "MOVING_DOWN": "▼"}.get(m.state, ""))

        for item in (self.car_txt, self.arrow_txt, self.hw_mark, self.hw_lbl):
            cv.tag_raise(item)

    def redraw(self):
        s = self.backend.state
        v = self.st_vars
        v["floor"].set(f"{s.floor}F")
        v["fw_state"].set(s.fw_state)
        v["direction"].set(s.direction)
        v["door_sec"].set(f"{s.door_sec}s")
        v["card"].set(f"{s.card_id} ({s.card_type})")
        v["hw_card"].set(f"{s.hw_card_id} ({CARDS[s.hw_card_id][0]})" if s.hw_card_id in CARDS else "-")
        v["master"].set("ON" if s.master else "OFF")
        v["req"].set(f"0x{s.req:02X}")
        self._draw_panels()

        self.conn_btn.config(text="Disconnect" if s.connected else "Connect")
        self.conn_lbl.config(text="● 연결됨" if s.connected else "● 연결 안 됨",
                             foreground="#2e7d32" if s.connected else "#c62828")

    def write_log(self, text):
        self.log.configure(state="normal")
        tag = ("guest" if "[손님]" in text else "bad" if ("[검증 불일치]" in text or text.startswith("[ERR]"))
               else "ok" if "[검증 OK]" in text else "rand" if "[랜덤" in text else "")
        self.log.insert("end", text + "\n", tag)
        if int(self.log.index("end-1c").split(".")[0]) > 500:
            self.log.delete("1.0", "100.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")


def run():
    root = tk.Tk()
    ElevatorApp(root)
    root.mainloop()
