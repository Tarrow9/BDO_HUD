import base64
import json
import threading
import time
import zlib
from typing import Any, Dict, Optional
from PyQt5.QtCore import QThread, pyqtSignal, QObject

import requests
import websocket  # websocket-client
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class Cannon:
    """
    - 프로그램 시작 시 WS 연결 시도(실패해도 OK)
    - WS로 session_key 수신 저장
    - WS broadcast 메시지(chat/log)를 chat_log에 누적
    - HTTP 응답(암호문)을 session_key로 복호화해 dict로 반환
    """

    def __init__(
        self,
        ws_url: str,
        http_base_url: str,
        connect_timeout_sec: float = 3.0,
        chat_log_max: int = 30,
    ):
        self.ws_url = ws_url
        self.http_base_url = http_base_url.rstrip("/")
        self.connect_timeout_sec = connect_timeout_sec
        self.chat_log_max = chat_log_max

        self._ws_app: Optional[websocket.WebSocketApp] = None
        self._ws_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self._lock = threading.Lock()
        self._session_key: Optional[bytes] = None  # AES-256 key bytes
        self.chat_log: list[dict] = []  # WS에서 받은 로그들을 계속 저장

        # ✅ 시작하자마자 WS 연결 시도 (실패해도 프로그램은 계속)
        self.start_ws()

    # -------------------------
    # WS lifecycle
    # -------------------------
    def start_ws(self) -> None:
        if self._ws_thread and self._ws_thread.is_alive():
            return

        self._stop_event.clear()

        def _run():
            # 끊기면 재연결(간단 백오프)
            backoff = 1.0
            while not self._stop_event.is_set():
                try:
                    self._ws_app = websocket.WebSocketApp(
                        self.ws_url,
                        on_open=self._on_open,
                        on_message=self._on_message,
                        on_close=self._on_close,
                        on_error=self._on_error,
                    )
                    # ping으로 연결 유지(선택)
                    self._ws_app.run_forever(
                        ping_interval=20,
                        ping_timeout=10,
                        ping_payload="ping",
                    )
                except Exception as e:
                    self._append_chat({"type": "ws_error", "msg": f"run_forever exception: {e}"})

                if self._stop_event.is_set():
                    break

                time.sleep(backoff)
                backoff = min(backoff * 1.7, 10.0)

        self._ws_thread = threading.Thread(target=_run, daemon=True)
        self._ws_thread.start()

    def stop_ws(self, timeout_sec: float = 2.0) -> None:
        self._stop_event.set()
        try:
            if self._ws_app:
                # 정상 종료 시도
                self._ws_app.close(status=1000, reason="client exit")
        except Exception:
            pass

        if self._ws_thread and self._ws_thread.is_alive():
            self._ws_thread.join(timeout=timeout_sec)

    # WS callbacks
    def _on_open(self, ws):
        self._append_chat({"type": "ws", "msg": "connected"})

    def _on_message(self, ws, message: str):
        # 서버가 보내는 모든 브로드캐스트/hello를 여기서 받음
        try:
            data = json.loads(message)
        except Exception:
            data = {"type": "raw", "msg": message}

        # hello 메시지에서 session_key 받기
        # 예: {"code":1,"msg":"connected","nick":"...","session_key":"..."}
        nick = data.get("nick")
        ts = data.get("ts")
        msg = data.get("msg")
        sk = data.get("session_key")
        if isinstance(sk, str) and sk:
            try:
                key_bytes = base64.urlsafe_b64decode(sk.encode("ascii"))
                if len(key_bytes) in (16, 24, 32):
                    with self._lock:
                        self._session_key = key_bytes
                    self._append_chat({"type": "log", "msg": f"{nick} Authorized."})
                else:
                    self._append_chat({"type": "ws_error", "msg": f"bad session"})
            except Exception as e:
                self._append_chat({"type": "ws_error", "msg": f"session error"})
        # 나머지 메시지는 채팅/로그로 저장
        else:
            self._append_chat({"type": "log", "msg": f"{ts} {nick} {msg}"})

    def _on_close(self, ws, close_status_code, close_msg):
        self._append_chat({"type": "ws", "msg": f"closed by {close_msg}"})

    def _on_error(self, ws, error):
        self._append_chat({"type": "ws_error", "msg": str(error)})

    def _append_chat(self, item: dict) -> None:
        with self._lock:
            self.chat_log.append(item)
            if len(self.chat_log) > self.chat_log_max:
                # 오래된 로그 버림
                self.chat_log = self.chat_log[-self.chat_log_max :]

    # -------------------------
    # Crypto: decrypt response
    # -------------------------

    def _get_session_key(self) -> Optional[bytes]:
        with self._lock:
            return self._session_key

    def decrypt_payload(self, enc_obj: Dict[str, Any]) -> Dict[str, Any]:
        """
        서버 응답(enc_obj: {"n": "...", "c": "...", "z": 1, "v": 1})을 복호화해 dict로 반환
        - session_key 없으면 예외
        """
        key = self._get_session_key()
        if not key:
            raise RuntimeError("no session_key yet (WS not connected or not authorized)")

        # 최소 포맷 가정: n=nonce, c=ciphertext, z=compressed 여부
        n = enc_obj.get("n") or enc_obj.get("nonce")
        c = enc_obj.get("c") or enc_obj.get("ct")
        z = enc_obj.get("z") or enc_obj.get("zip") or 0

        if not isinstance(n, str) or not isinstance(c, str):
            raise ValueError("invalid encrypted object: missing n/c")

        nonce = base64.urlsafe_b64decode(n.encode("ascii"))
        ct = base64.urlsafe_b64decode(c.encode("ascii"))

        aesgcm = AESGCM(key)
        raw = aesgcm.decrypt(nonce, ct, associated_data=None)

        if int(z) == 1:
            raw = zlib.decompress(raw)

        return json.loads(raw.decode("utf-8"))

    # -------------------------
    # HTTP request example
    # -------------------------
    def request_hit_table(self, new_cannon_angle: int, new_shortlow: int) -> Dict[str, Any]:
        """
        1) /api/ingest로 {h,v} POST
        2) 받은 암호문을 decrypt_payload로 복호화
        3) 복호화된 dict(= hit_table 포함)를 반환
        """
        url = f"{self.http_base_url}/msr"
        resp = requests.post(url, json={"rawangle": new_cannon_angle, "diagonal": new_shortlow}, timeout=self.connect_timeout_sec)
        resp.raise_for_status()
        enc_obj = resp.json()
        return self.decrypt_payload(enc_obj)


class HitTableWorker(QObject):
    finished = pyqtSignal(dict)   # 성공 시 평문 dict
    failed = pyqtSignal(str)      # 실패 시 에러 문자열

    def __init__(self, cannon, rawangle: float, diagonal: int):
        super().__init__()
        self.cannon = cannon
        self.rawangle = rawangle
        self.diagonal = diagonal

    def run(self):
        try:
            # 서버 요청, 복호화
            data = self.cannon.request_hit_table(self.rawangle, self.diagonal)
            if data.get("ok") != True:
                self.failed.emit(f"{data.get('error')}")
            chart = data.get("chart")
            refine_chart = {int(k): v for k, v in chart.items()} if isinstance(chart, dict) else {}
            self.finished.emit(refine_chart)
        except Exception as e:
            self.failed.emit(str(e))
