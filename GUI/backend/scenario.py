"""랜덤 시나리오 : 계획서에 없는 상황을 매번 새로 만들어서 STM32 를 시험한다

카드 DB(0~3번)에 묶이지 않고, 누를 때마다 이용객을 새로 만든다.
  - 손님 n명 : 각자 1층 또는 2층에서 아무 때나 외부 리더 태그 (펌웨어는 카드 종류만 보므로 몇 명이든 가능)
  - 직원 m명 : 각자 출발층에서 호출 -> 엘리베이터가 와서 문이 열리면 내부 리더 태그 -> 목적층 선택
  - 방해 입력 : 권한 없는 카드, 손님의 3층 태그, 문 닫히는 중 같은 층 태그 (REOPEN) ...
타이밍은 "시작 후 몇 초" 또는 "이동 중 / 문 열림 / 문 닫히는 중" 같은 상황에 맞춰 흩어 놓는다.
결과는 backend 의 응답 비교(model.py)가 판정한다.
"""

import random
import time

GUEST, STAFF, NO_AUTH = "GUEST", "STAFF", "NO_AUTH"
COND_NAME = {"moving": "이동 중", "door_open": "문 열림", "door_closing": "문 닫히는 중", "idle": "대기"}


class Step:
    def __init__(self, desc, action, at=None, when=None, delay=0.0, check=None, fallback=False):
        self.desc = desc
        self.action = action      # action(backend)
        self.at = at              # 시작 후 몇 초에 (when 이 없을 때)
        self.when = when          # 조건 이름 : "moving" / "door_open" / "door_closing" / "idle"
        self.delay = delay        # 조건이 된 뒤 기다릴 시간
        self.check = check        # 추가 조건 check(state) -> bool
        self.fallback = fallback  # 조건이 끝내 안 오면 건너뛰지 않고 그냥 실행 (이용객은 어쨌든 도착함)
        self.ready_at = None
        self.done = False

    def label(self):
        return f"{self.at:.0f}초" if self.when is None else COND_NAME[self.when]


class Person:
    def __init__(self, kind, name, start, dest=None):
        self.kind, self.name, self.start, self.dest = kind, name, start, dest


def _letters():
    return iter("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def build_random(rng=random, travel_s=3.0):
    """이용객과 사건을 새로 만든다. travel_s : 한 층 이동 시간 (타이밍을 흩어 놓는 기준)"""
    span = max(10.0, travel_s * 4)          # 처음 입력들을 흩어 놓을 시간 범위
    people, steps = [], []
    letters = _letters()

    # ---- 손님 ----
    for _ in range(rng.randint(1, 4)):
        p = Person(GUEST, f"손님 {next(letters)}", rng.choice((1, 2)))
        people.append(p)
        if rng.random() < 0.6:
            at = round(rng.uniform(0, span), 1)
            steps.append(Step(f"{p.name} {p.start}층 외부 리더 태그", _tag(p.start, GUEST, p.name), at=at))
        else:
            when = rng.choice(("moving", "door_open", "door_closing"))
            steps.append(Step(f"{p.name} {p.start}층 외부 리더 태그", _tag(p.start, GUEST, p.name),
                              when=when, delay=rng.uniform(0.3, 3.0), fallback=True))

    # ---- 직원 : 호출 -> 탑승(문 열림) -> 내부 리더 -> 목적층 ----
    for i in range(rng.randint(0, 2)):
        start = rng.choice((1, 2, 3))
        dest = rng.choice([f for f in (1, 2, 3) if f != start])
        p = Person(STAFF, f"직원 {i + 1}", start, dest)
        people.append(p)
        call = Step(f"{p.name} {start}층 외부 리더 호출", _tag(start, STAFF, p.name),
                    at=round(rng.uniform(0, span), 1))
        steps.append(call)
        steps.append(Step(f"{p.name} {start}층에서 탑승, 내부 리더 태그 -> {dest}층 선택", _board_staff(dest, p.name),
                          when="door_open", delay=rng.uniform(0.5, 2.0),
                          check=lambda st, f=start, c=call: c.done and st.floor == f))

    # ---- 방해 입력 (무시되거나 특수 처리돼야 함) ----
    extras = [
        lambda: Step(f"권한 없는 카드 {(r := rng.choice((1, 2, 3, 4)))}번 리더 태그 (무시돼야 함)",
                     _tag(r, NO_AUTH, "권한 없음"), at=round(rng.uniform(0, span), 1)),
        lambda: Step("손님 카드 3층 외부 리더 태그 (무시돼야 함)", _tag(3, GUEST, "손님 X"),
                     at=round(rng.uniform(0, span), 1)),
        lambda: Step("손님 카드 내부 리더 태그 (무시돼야 함)", _tag(4, GUEST, "손님 X"),
                     when="door_open", delay=rng.uniform(0.3, 2.0)),
        lambda: Step("문 닫히는 중 그 층 외부 리더 태그 (DOOR_REOPEN)", _here(rng), when="door_closing", delay=0.3),
        lambda: Step("문 열려 있을 때 그 층 외부 리더 태그 (5초 다시 시작)", _here(rng), when="door_open",
                     delay=rng.uniform(1.0, 3.0)),
        lambda: Step("마스터 모드 아닐 때 목적층 버튼 (무시돼야 함)",
                     lambda b: b.master_dest(rng.choice((1, 2, 3))), at=round(rng.uniform(0, span), 1)),
    ]
    for _ in range(rng.randint(0, 3)):
        steps.append(rng.choice(extras)())

    # 시작하자마자 아무 일도 없으면 재미가 없으니, 가장 이른 시각 입력을 0초로 당김
    timed = [s for s in steps if s.when is None]
    if timed:
        min(timed, key=lambda s: s.at).at = 0.0
    else:
        p = people[0]
        steps.insert(0, Step(f"{p.name} {p.start}층 외부 리더 태그", _tag(p.start, p.kind, p.name), at=0.0))
    steps.sort(key=lambda s: (s.when is not None, s.at or 0))
    return people, steps


def _tag(reader, kind, name):
    return lambda b: b.tag_person(reader, kind, name)


def _board_staff(dest, name):
    def act(b):
        b.tag_person(4, STAFF, name)
        b.after(1.0, lambda: b.master_dest(dest))
    return act


def _here(rng):
    def act(b):
        f = b.state.floor
        kind = GUEST if (f in (1, 2) and rng.random() < 0.5) else STAFF
        b.tag_person(f, kind, "손님 Y" if kind == GUEST else "직원 Y")
    return act


class ScenarioRunner:
    def __init__(self, backend, log):
        self.b = backend
        self.log = log
        self.steps = []
        self.start = 0.0
        self.count = 0
        self.mismatch_at_start = 0
        self.idle_since = None
        self.last_action = 0.0

    @property
    def running(self):
        return any(not s.done for s in self.steps)

    def start_random(self, travel_s=3.0):
        self.count += 1
        people, self.steps = build_random(travel_s=travel_s)
        self.start = time.time()
        self.idle_since = None
        self.last_action = 0.0
        self.mismatch_at_start = self.b.model.mismatch
        who = ", ".join(f"{p.name}({p.start}층" + (f"->{p.dest}층)" if p.dest else ")") for p in people)
        self.log(f"[랜덤 #{self.count}] 시나리오 시작 : 이용객 {len(people)}명 - {who}")
        for i, s in enumerate(self.steps, 1):
            self.log(f"[랜덤 #{self.count}]    {i}) [{s.label()}] {s.desc}")

    def tick(self):
        if not self.steps:
            return
        now = time.time()
        st = self.b.state
        cond = {
            "moving": st.moving,
            "door_open": st.fw_state == "DOOR_OPEN",
            "door_closing": st.fw_state == "DOOR_CLOSING",
            "idle": st.fw_state == "IDLE",
        }
        for i, s in enumerate(self.steps, 1):
            if s.done:
                continue
            if s.when is None:
                due = now - self.start >= s.at
            else:
                ok = cond.get(s.when) and (s.check is None or s.check(st))
                if s.ready_at is None and ok:
                    s.ready_at = now + s.delay
                elif s.ready_at is not None and not ok:
                    s.ready_at = None       # 기다리는 사이 조건이 끝났으면 다음 기회에
                due = s.ready_at is not None and now >= s.ready_at
            if due:
                s.done = True
                self.log(f"[랜덤 #{self.count}] ▶ {i}) {s.desc}")
                s.action(self.b)
                self.last_action = now
            elif s.when is not None and (now - self.start > 300 or self._quiet(now)):
                s.done = True       # 조건이 끝내 안 오면 건너뜀 (이용객 태그는 지금 실행)
                if s.fallback:
                    self.log(f"[랜덤 #{self.count}] ▶ {i}) {s.desc} (엘리베이터가 대기 중이라 지금 태그)")
                    s.action(self.b)
                    self.last_action = now
                    self.idle_since = None
                else:
                    self.log(f"[랜덤 #{self.count}] {i}) 조건이 오지 않아 건너뜀 : {s.desc}")
        if (not self.running and st.fw_state == "IDLE" and st.req == 0 and not st.door_target_open
                and now - self.last_action > 3.0):
            self.on_done()

    def _quiet(self, now):
        """엘리베이터가 할 일 없이 10초 넘게 서 있으면, 남은 상황 조건은 더 오지 않는다고 봄"""
        st = self.b.state
        timed_left = any(not s.done and s.when is None for s in self.steps)
        if st.fw_state == "IDLE" and st.req == 0 and not timed_left:
            if self.idle_since is None:
                self.idle_since = now
            return now - self.idle_since > 10
        self.idle_since = None
        return False

    def on_done(self):
        """STM32 DONE : 시나리오가 다 실행됐으면 결과 정리"""
        if self.steps and not self.running:
            n = self.b.model.mismatch - self.mismatch_at_start
            self.log(f"[랜덤 #{self.count}] 끝 : 검증 불일치 {n}건" + (" -> PASS" if n == 0 else " -> 확인 필요"))
            self.steps = []
