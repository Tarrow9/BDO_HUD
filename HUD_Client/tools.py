import base64
import json
import threading
import time
import zlib
from typing import Any, Dict, Optional

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
        # session_key는 서버가 hello 메시지로 내려주니 여기서 따로 할 건 없음

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
                    self._append_chat({"type": "ws", "msg": f"{nick} Authorized."})
                else:
                    self._append_chat({"type": "ws_error", "msg": f"bad session_key length={len(key_bytes)}"})
            except Exception as e:
                self._append_chat({"type": "ws_error", "msg": f"session_key decode error: {e}"})

        # 나머지 메시지는 채팅/로그로 저장
        self._append_chat({"type": "log", "msg": f"{ts} {nick} {msg}"})

    def _on_close(self, ws, close_status_code, close_msg):
        self._append_chat({"type": "ws", "msg": f"closed code={close_status_code} reason={close_msg}"})

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
    def request_hit_table(self, h: int, v: int) -> Dict[str, Any]:
        """
        1) /api/ingest로 {h,v} POST
        2) 받은 암호문을 decrypt_payload로 복호화
        3) 복호화된 dict(= hit_table 포함)를 반환
        """
        url = f"{self.http_base_url}/msr"
        resp = requests.post(url, json={"h": h, "v": v}, timeout=self.connect_timeout_sec)
        resp.raise_for_status()
        enc_obj = resp.json()
        return self.decrypt_payload(enc_obj)

    # -------------------------
    # 기존 로컬 계산 (지금은 서버가 return 형태로 준다고 가정하니 그냥 placeholder)
    # -------------------------
    def setting_hit_table(self, new_cannon_angle, new_shortlow):
        return {  # base table
            0: [67.55, 75.63, 80.7, 84.17, 89.51, 96.89, 106.52, 114.56, 122.89, 138.17],
            1: [91.38, 97.86, 104.57, 113.86, 123.55, 131.07, 138.82, 152.23, 166.25, 189.97],
            2: [141.25, 155.73, 167.05, 174.82, 186.8, 199.18, [220.7], [238.71], 262.21, 302.12],
            3: [171.36, 184.12, 197.35, "211.03", [225.18], [239.78], 265.14, 291.70, 313.99, 366.97],
            4: [182.76, 190.88, 199.18, "211.96", [220.7], [229.62], "243.32", 262.21, 276.85, 296.97],
            5: [184.18, 191.47, 198.91, 202.68, "210.33", "218.12", [226.05], [238.21], 250.69, 267.83],
            6: [157.52, 163.41, 169.4, 175.51, 181.72, 188.04, 194.47, 204.31, "214.4", [231.75]],
        }
