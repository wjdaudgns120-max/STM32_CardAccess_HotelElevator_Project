"""엘리베이터 GUI 실행

VS Code : 이 파일을 열고 오른쪽 위 ▶ (Run Python File) 또는 F5
터미널  : python main.py

구조
  frontend/app.py        화면 (tkinter) : 버튼, 엘리베이터 그림, 상태, 로그
  backend/controller.py  frontend 가 부르는 유일한 창구
  backend/link.py        통신 (SerialLink = 보드, MockLink = 보드 없이 테스트)
  backend/codec.py       통신 내용 해석 (지금은 펌웨어 텍스트 로그, 나중에 프로토콜로 교체)
  backend/state.py       엘리베이터 상태 데이터

보드 없이 확인 : 포트에서 MOCK 선택
"""

import os
import subprocess
import sys

# 어느 폴더에서 실행해도 frontend / backend 를 찾도록
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)


def ensure_pyserial():
    """pyserial 이 없으면 지금 실행 중인 파이썬에 자동 설치 (처음 한 번만)"""
    try:
        import serial  # noqa: F401
        return
    except ImportError:
        pass
    print("pyserial 이 없어서 설치합니다 ...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyserial"])
    except Exception as e:
        print(f"pyserial 설치 실패 ({e}). MOCK 모드만 사용할 수 있어요.")


if __name__ == "__main__":
    ensure_pyserial()
    from frontend.app import run
    run()
