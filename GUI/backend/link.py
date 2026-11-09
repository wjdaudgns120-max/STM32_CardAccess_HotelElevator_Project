"""통신 링크 : 바이트를 보내고 받기만 함 (내용 해석은 codec 담당)

SerialLink : 실제 보드 (pyserial)
MockLink   : 보드 없이 GUI 개발용. mock_fw.MockFirmware 와 바이트로 주고받음
"""

import queue
import threading

from .mock_fw import MockFirmware


class SerialLink:
    def __init__(self):
        self._ser = None
        self._rx = queue.Queue()
        self._run = False

    @staticmethod
    def ports():
        try:
            from serial.tools import list_ports
        except ImportError:
            return []
        return [p.device for p in list_ports.comports()]

    def open(self, port, baud=115200):
        import serial  # pyserial 이 없으면 여기서 에러 -> backend 가 로그로 알림
        self._ser = serial.Serial(port, baud, timeout=0.05)
        self._run = True
        threading.Thread(target=self._rx_loop, daemon=True).start()

    def close(self):
        self._run = False
        if self._ser:
            self._ser.close()
            self._ser = None

    def write(self, data: bytes):
        if self._ser:
            self._ser.write(data)

    def read_all(self) -> bytes:
        """지금까지 받은 바이트 전부 (GUI 스레드에서 호출)"""
        chunks = []
        while not self._rx.empty():
            chunks.append(self._rx.get_nowait())
        return b"".join(chunks)

    def _rx_loop(self):
        while self._run and self._ser:
            try:
                data = self._ser.read(64)
            except Exception:
                break
            if data:
                self._rx.put(data)


class MockLink:
    def __init__(self):
        self._rx = bytearray()
        self.fw = None

    @staticmethod
    def ports():
        return ["MOCK"]

    def open(self, port=None, baud=115200):
        self.fw = MockFirmware(send=self._rx.extend)

    def close(self):
        self.fw = None

    def write(self, data: bytes):
        if self.fw:
            self.fw.receive(data)

    def read_all(self) -> bytes:
        if self.fw:
            self.fw.tick()
        data, self._rx[:] = bytes(self._rx), b""
        return data
