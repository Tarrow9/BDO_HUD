import sys, os
import threading
import math
import json
from PyQt5.QtCore import (
    QMetaObject,
    Qt,
    QTimer,
    QObject,
    pyqtSignal,
    QEvent,
    pyqtProperty,
    QPointF,
    QThread,
    pyqtSlot,
)
from PyQt5.QtGui import (
    QColor,
    QPainter,
    QPen, QFont,
    QFontDatabase,
    QPixmap,
    QCursor,
    QIcon,
)
from PyQt5.QtWidgets import QApplication, QWidget, QSystemTrayIcon, QMenu, QAction
from pynput import keyboard

from widgets import (
    LeftLineWidget, 
    RightLineWidget, 
    ShortLowWidget, 
    CNAngleWidget, 
    CompassWidget, 
    AzimuthWidget,
    StatusTextWidget,
    HitTableWidget,
    ChatLogWidget,
)
from screen_scan import (
    AzimuthCaptureThread,
)
from draw_tools import draw_neon_line
from conf import(
    AZIMUTH_DURATION,
)
from tools import Cannon, HitTableWorker, SimpleGetWorker

INF_LEFT = 1000  # 좌측 세로선 상단 x
INF_RIGHT = 1800  # 우측 세로선 상단 x
INF_HIGH = 60  # 좌측 세로선 상단 y
LINE_LEN = 30  # 가로선 길이

## venv init
import PyQt5
dirname = os.path.dirname(PyQt5.__file__)
plugin_path = os.path.join(dirname, 'Qt5', 'plugins', 'platforms')
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = plugin_path

def resource_path(relative_path: str):
    """PyInstaller onefile 대응 경로 헬퍼"""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def inertia_init(widget, *, gain_x=0.25, gain_y=0.20, damping=0.82, follow=0.18,
                 max_x=70, max_y=50, teleport_ratio=0.45):
    """widget: 움직일 창(QWIdget). widget.move()로 이동."""
    state = {}
    state["base_pos"] = widget.pos()
    state["prev_cursor"] = QCursor.pos()
    state["offset"] = QPointF(0.0, 0.0)
    state["vel"] = QPointF(0.0, 0.0)

    state["gain_x"] = gain_x
    state["gain_y"] = gain_y
    state["damping"] = damping
    state["follow"] = follow
    state["max_x"] = max_x
    state["max_y"] = max_y

    # wrap/teleport 감지 임계값(해상도 기반)
    screen_geo = QApplication.primaryScreen().geometry()
    state["teleport_x"] = int(screen_geo.width() * teleport_ratio)
    state["teleport_y"] = int(screen_geo.height() * teleport_ratio)

    return state

def inertia_tick(widget, state):
    """한 틱 업데이트: 마우스 이동에 따른 잔상 관성 적용 + wrap 방지."""
    cur = QCursor.pos()
    prev = state["prev_cursor"]
    dx = cur.x() - prev.x()
    dy = cur.y() - prev.y()
    state["prev_cursor"] = cur

    # ✅ wrap/teleport 감지: 그 프레임 입력 무시
    if abs(dx) > state["teleport_x"] or abs(dy) > state["teleport_y"]:
        # 튐 방지: velocity 죽이기
        v = state["vel"]
        state["vel"] = QPointF(v.x() * 0.2, v.y() * 0.2)
        return

    # 마우스 속도 크기 → 큰 이동일수록 더 크게 반응(선택)
    speed = math.hypot(dx, dy)
    mult = 1.0 + min(1.5, speed / 25.0)

    # vel 업데이트(반대방향)
    v = state["vel"]
    v = QPointF(
        v.x() + (-dx * state["gain_x"] * mult),
        v.y() + (-dy * state["gain_y"] * mult),
    )

    # vel 감쇠
    v = QPointF(v.x() * 0.75, v.y() * 0.75)
    state["vel"] = v

    # offset 업데이트 + 감쇠
    o = state["offset"]
    o = QPointF((o.x() + v.x()) * state["damping"], (o.y() + v.y()) * state["damping"])

    # clamp offset
    ox = max(-state["max_x"], min(state["max_x"], o.x()))
    oy = max(-state["max_y"], min(state["max_y"], o.y()))
    o = QPointF(ox, oy)
    state["offset"] = o

    base = state["base_pos"]
    target_x = base.x() + ox
    target_y = base.y() + oy

    now = widget.pos()
    new_x = now.x() + (target_x - now.x()) * state["follow"]
    new_y = now.y() + (target_y - now.y()) * state["follow"]
    widget.move(int(new_x), int(new_y))

def load_server_address_from_file() -> tuple[str, int]:
    """
    드래그앤드롭으로 받은 파일에서 ip:port 읽어서 반환
    기본값은 localhost
    """
    default_ip = "127.0.0.1"
    default_port = 8001

    if len(sys.argv) < 2:
        return default_ip, default_port

    path = sys.argv[1]

    if not os.path.exists(path):
        return default_ip, default_port

    with open(path, "r", encoding="utf-8") as f:
        raw = f.read().strip()

    # 172.30.1.12:8001 형태
    if ":" in raw:
        ip, port = raw.split(":", 1)
        return ip.strip(), int(port.strip())

    # ip만 적혀있으면 기본포트 사용
    return raw.strip(), default_port


class HUDWindow(QWidget):
    ## Initializings
    def __init__(self):
        super().__init__()
        ip, port = load_server_address_from_file()
        self.cannon = Cannon(ws_url=f"ws://{ip}:{port}/ws/logs/", http_base_url=f"http://{ip}:{port}")
        self._hit_thread = None
        self._hit_worker = None
        self._hit_request_inflight = False

        # 윈도우 설정, click-through 설정 (WindowTransparentForInput)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(0.75)

        # 폰트, 색 설정
        font_path = resource_path("fonts/ocr-b.ttf")
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            font = QFont(QFontDatabase.applicationFontFamilies(font_id)[0], 14)
            self.setFont(font)
        else:
            self.setFont(QFont("Arial", 14))
        self._warning_color = QColor(255, 0, 0, 192)  # 50% 투명한 빨간색
        self._base_color = QColor(0, 255, 0, 192)  # 50% 투명한 초록색

        # 창 크기 및 위치
        self.setGeometry(0, 0, 2800, 630)  # 크기 설정
        screen_geometry = QApplication.desktop().availableGeometry()
        self.move(screen_geometry.center() - self.rect().center())  # 화면 중앙에 배치

        # LineWidget 리스트 초기화
        ## shortlow, cannon angle => diagonal, rawangle
        self.left_line_widget = None
        self.right_line_widget = None
        self.new_shortlow : int = 100 # max: 550 min: 0, center0 = 55*30 - 15
        self.center_shortlow_widget = None
        self.center_cn_angle_widget = None
        self.new_cannon_angle : int = 0 # max: 450 min: -450, center0 = 35*30 - 15

        self.create_initial_left_widgets()
        self.create_initial_right_widgets()

        # StatusWidget 초기화
        self.status_text_widget = None
        self.create_initial_status_text_widget()

        # # HitTableWidget 초기화
        self.hit_table_widget = None
        self.create_initial_hit_table_widget()

        # 타이머 설정
        self.lr_timer = QTimer(self) # ON / OFF
        self.lr_timer.setInterval(300)
        self.lr_timer.timeout.connect(lambda: self.left_line_widget.set_shortlow_start_ani(self.new_shortlow))
        self.lr_timer.timeout.connect(lambda: self.center_shortlow_widget.set_shortlow_start_ani(self.new_shortlow))
        self.lr_timer.timeout.connect(lambda: self.right_line_widget.set_height_start_ani(self.new_cannon_angle))
        self.lr_timer.timeout.connect(lambda: self.center_cn_angle_widget.set_height_start_ani(self.new_cannon_angle))

        # inertia for HUDWindow
        self._inertia_state = inertia_init(
            self,
            gain_x=0.25, gain_y=0.20,
            damping=0.45, follow=0.55,
            max_x=70, max_y=50,
        )
        self._inertia_timer = QTimer(self)
        self._inertia_timer.setInterval(16)
        self._inertia_timer.timeout.connect(lambda: inertia_tick(self, self._inertia_state))
        self._inertia_timer.start()

        # ✅ chat log polling
        self._last_chat_len = 0
        self._chat_timer = QTimer(self)
        self._chat_timer.setInterval(300)
        self._chat_timer.timeout.connect(self._drain_chat_log_to_widget)
        self._chat_timer.start()

    def _update_trail_motion(self):
        cur = QCursor.pos()
        dx = cur.x() - self._prev_cursor.x()
        dy = cur.y() - self._prev_cursor.y()

        # ✅ 랩/텔레포트 감지: 이 프레임 입력 무시
        if abs(dx) > self._teleport_x or abs(dy) > self._teleport_y:
            self._prev_cursor = cur
            # 튐 방지: velocity도 살짝 죽여주면 더 안정적
            self._vel.setX(self._vel.x() * 0.2)
            self._vel.setY(self._vel.y() * 0.2)
            return

        self._prev_cursor = cur

        # 마우스 이동을 "반대 방향 offset"에 누적
        speed = math.hypot(dx, dy)  # 마우스 이동 "크기"
        
        # speed가 커질수록 multiplier가 커짐 (1.0 ~ 2.5 정도)
        mult = 1.0 + min(1.5, speed / 25.0)
        # mult = 1.0 + min(2.0, (speed / 20.0) ** 1.4)  # 1.2~1.8 사이 추천
        
        self._vel.setX(self._vel.x() + (-dx * self._gain_x * mult))
        self._vel.setY(self._vel.y() + (-dy * self._gain_y * mult))

        # velocity도 감쇠시키기 (너무 폭주 방지)
        self._vel.setX(self._vel.x() * 0.75)
        self._vel.setY(self._vel.y() * 0.75)

        # offset에 velocity를 반영
        self._offset.setX(self._offset.x() + self._vel.x())
        self._offset.setY(self._offset.y() + self._vel.y())

        # offset 감쇠 (마우스 멈추면 자연스럽게 0으로 복귀)
        self._offset.setX(self._offset.x() * self._damping)
        self._offset.setY(self._offset.y() * self._damping)

        # 최대 범위 제한
        ox = max(-self._max_x, min(self._max_x, self._offset.x()))
        oy = max(-self._max_y, min(self._max_y, self._offset.y()))
        self._offset = QPointF(ox, oy)

        # 목표 위치
        target_x = self._hud_base_pos.x() + ox
        target_y = self._hud_base_pos.y() + oy

        # 현재 위치에서 목표로 "조금씩" 이동 (잔상 느낌 핵심)
        now = self.pos()
        new_x = now.x() + (target_x - now.x()) * self._follow
        new_y = now.y() + (target_y - now.y()) * self._follow

        self.move(int(new_x), int(new_y))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 테두리 색상 및 두께 설정
        border_color = QColor(0, 255, 0, 192)
        pen = QPen(border_color)
        t = 3  # 테두리 두께
        pen.setWidth(t)
        painter.setPen(pen)

        inf_left = INF_LEFT
        inf_right = self.width() - inf_left
        inf_high = INF_HIGH
        inf_low = self.height() - inf_high
        line_len = LINE_LEN
        center_x = self.width() // 2
        center_y = self.height() // 2
        arrow_box_low = 60
        arrow_box_half = 15

        # 화살표상자
        l_arrow_box_x = inf_left+line_len+t
        draw_neon_line(painter, l_arrow_box_x, center_y, l_arrow_box_x+arrow_box_half, center_y-arrow_box_half, t, 192)
        draw_neon_line(painter, l_arrow_box_x, center_y, l_arrow_box_x+arrow_box_half, center_y+arrow_box_half, t, 192)
        draw_neon_line(painter, l_arrow_box_x+arrow_box_half, center_y-arrow_box_half, l_arrow_box_x+arrow_box_low+10, center_y-arrow_box_half, t, 192)
        draw_neon_line(painter, l_arrow_box_x+arrow_box_half, center_y+arrow_box_half, l_arrow_box_x+arrow_box_low+10, center_y+arrow_box_half, t, 192)
        draw_neon_line(painter, l_arrow_box_x+arrow_box_low+10, center_y-arrow_box_half, l_arrow_box_x+arrow_box_low+10, center_y+arrow_box_half, t, 192)

        # 화살표상자
        r_arrow_box_x = inf_right-line_len-t
        draw_neon_line(painter, r_arrow_box_x-arrow_box_half, center_y-arrow_box_half, r_arrow_box_x, center_y, t, 192)
        draw_neon_line(painter, r_arrow_box_x-arrow_box_half, center_y+arrow_box_half, r_arrow_box_x, center_y, t, 192)
        draw_neon_line(painter, r_arrow_box_x-arrow_box_low-25, center_y-arrow_box_half, r_arrow_box_x-arrow_box_half, center_y-arrow_box_half, t, 192)
        draw_neon_line(painter, r_arrow_box_x-arrow_box_low-25, center_y+arrow_box_half, r_arrow_box_x-arrow_box_half, center_y+arrow_box_half, t, 192)
        draw_neon_line(painter, r_arrow_box_x-arrow_box_low-25, center_y-arrow_box_half, r_arrow_box_x-arrow_box_low-25, center_y+arrow_box_half, t, 192)

        # 중앙 맨 위 역삼각형 그리기
        draw_neon_line(painter, center_x - 15, 0, center_x, 15, 2, 192)
        draw_neon_line(painter, center_x + 15, 0, center_x, 15, 2, 192)

    ## Handling Widgets
    def create_initial_left_widgets(self):
        """초기 LeftLineWidget 생성 및 배치"""
        center_y = self.height() // 2
        t = 2
        self.left_line_widget = LeftLineWidget(self)
        self.left_line_widget.move(INF_LEFT - self.left_line_widget.width() - t, center_y - 55*30 - 15)
        self.left_line_widget.show()
        """초기 ShortLowWidget 생성 및 배치"""
        self.center_shortlow_widget = ShortLowWidget(self)
        self.center_shortlow_widget.move(INF_LEFT + t + LINE_LEN + 22, center_y - 15)
        self.center_shortlow_widget.show()

    def create_initial_right_widgets(self):
        """초기 LeftLineWidget 17개 생성 및 배치"""
        center_y = self.height() // 2
        t = 2
        self.right_line_widget = RightLineWidget(self)
        self.right_line_widget.move(INF_RIGHT + t, center_y - 60*30 - 15)
        self.right_line_widget.show()
        """초기 CNAngleWidget 생성 및 배치"""
        self.center_cn_angle_widget = CNAngleWidget(self)
        self.center_cn_angle_widget.move(INF_RIGHT - t - 145, center_y - 15)
        self.center_cn_angle_widget.show()

        # ✅ ChatLogWidget (ShortLowWidget 왼쪽에 배치)
        self.chat_log_widget = ChatLogWidget(self, max_lines=12)
        gap = 150
        chat_x = self.center_shortlow_widget.x() + self.chat_log_widget.width() + gap
        chat_y = self.center_shortlow_widget.y() - 130  # 위로 조금 올려서 “맨 위부터 출력” 느낌
        self.chat_log_widget.move(chat_x, chat_y)
        self.chat_log_widget.show()
    
    def create_initial_compass_widgets(self):
        """초기 CompassWidget 생성 및 배치"""
        center_x = self.width() // 2
        self.compass_widget = CompassWidget(self)
        self.compass_widget.move(center_x-self.compass_widget.width()//2, 515)
        self.compass_widget.show()
        """초기 AzimuthWidget 생성 및 배치"""
        self.azimuth_widget = AzimuthWidget(self)
        self.azimuth_widget.move(center_x-self.azimuth_widget.width()//2, 565)
        self.azimuth_widget.show()

    def create_initial_status_text_widget(self):
        """초기 StatusTextWidget 생성 및 배치"""
        self.status_text_widget = StatusTextWidget("INITIALIZING...", self)
        self.status_text_widget.move(INF_LEFT, 600)
        self.status_text_widget.show()

    def create_initial_hit_table_widget(self):
        """초기 HitTableWidget 생성 및 배치"""
        self.hit_table_widget = HitTableWidget(self)
        self.hit_table_widget.move(INF_RIGHT+180, 390)
        self.hit_table_widget.hide()

    def _drain_chat_log_to_widget(self):
        # cannon.chat_log는 스레드에서 append 될 수 있으니 “스냅샷”으로 읽기
        logs = list(self.cannon.chat_log)
        cur_len = len(logs)

        if cur_len <= self._last_chat_len:
            return

        new_items = logs[self._last_chat_len:cur_len]
        self._last_chat_len = cur_len

        for item in new_items:
            if item["type"] == "log":
                self.chat_log_widget.append_line(item["msg"])
            else:
                print(item["msg"])

    # hit table handling
    def hit_table_fix(self):
        # request 후  실패하면 CONNECT FAIL 출력
        shortlow_check = 0 < self.new_shortlow < 550
        height_check = -450 < self.new_cannon_angle < 450
        if not (shortlow_check and height_check):
            self.status_text_widget.change_color(self._warning_color)
            self.status_text_widget.new_text = "CRITICAL ERROR"
            return

        self.request_hit_table_async(self.new_cannon_angle/10, self.new_shortlow)

    def request_hit_table_async(self, rawangle: float, diagonal: int):
        # 중복 요청 방지(원하면 큐로 바꿀 수도 있어요)
        if self._hit_request_inflight:
            return
        self._hit_request_inflight = True

        # UI 상태 표시
        self.status_text_widget.change_color(self._base_color)
        self.status_text_widget.new_text = "REQUESTING..."

        self._hit_thread = QThread(self)
        self._hit_worker = HitTableWorker(self.cannon, rawangle, diagonal)
        self._hit_worker.moveToThread(self._hit_thread)

        # 스레드 시작 시 worker.run 실행
        self._hit_thread.started.connect(self._hit_worker.run)

        # 결과 처리(메인 스레드에서 실행됨)
        self._hit_worker.finished.connect(self.on_hit_table_success)
        self._hit_worker.failed.connect(self.on_hit_table_failed)

        # 정리
        self._hit_worker.finished.connect(self._hit_thread.quit)
        self._hit_worker.failed.connect(self._hit_thread.quit)
        self._hit_thread.finished.connect(self._cleanup_hit_thread)

        self._hit_thread.start()

    def on_hit_table_success(self, hit_table: dict):
        self._hit_request_inflight = False

        self.status_text_widget.change_color(self._base_color)
        self.status_text_widget.new_text = "FIXED"

        self.hit_table_widget.hit_table = hit_table
        self.hit_table_widget.show()
        self.hit_table_widget.ani_count = -1
        print(self.cannon.chat_log[-1])  # 가장 최근 채팅 로그 출력

    def on_hit_table_failed(self, err: str):
        self._hit_request_inflight = False

        self.status_text_widget.change_color(self._warning_color)
        self.status_text_widget.new_text = "CONNECT FAIL"

    def _cleanup_hit_thread(self):
        # QObject/QThread 누수 방지
        if self._hit_worker is not None:
            self._hit_worker.deleteLater()
            self._hit_worker = None
        if self._hit_thread is not None:
            self._hit_thread.deleteLater()
            self._hit_thread = None

    # closechart handling
    @pyqtSlot()
    def request_closechart_async(self):
        # 중복 호출 방지(원하면 제거 가능)
        if getattr(self, "_closechart_inflight", False):
            return
        self._closechart_inflight = True

        url = f"{self.cannon.http_base_url}/closechart"  # cannon에 base_url 넣어둔 상태 가정

        self._closechart_thread = QThread(self)
        self._closechart_worker = SimpleGetWorker(url, timeout_sec=2.0)
        self._closechart_worker.moveToThread(self._closechart_thread)

        self._closechart_thread.started.connect(self._closechart_worker.run)

        self._closechart_worker.finished.connect(self._on_closechart_ok)
        self._closechart_worker.failed.connect(self._on_closechart_fail)

        self._closechart_worker.finished.connect(self._closechart_thread.quit)
        self._closechart_worker.failed.connect(self._closechart_thread.quit)
        self._closechart_thread.finished.connect(self._cleanup_closechart_thread)

        self._closechart_thread.start()


    def _on_closechart_ok(self, status_code: int):
        self._closechart_inflight = False
        self.status_text_widget.change_color(self._base_color)
        self.status_text_widget.new_text = "ONLINE"


    def _on_closechart_fail(self, err: str):
        self._closechart_inflight = False
        self.status_text_widget.change_color(self._warning_color)
        self.status_text_widget.new_text = "OFFLINE"


    def _cleanup_closechart_thread(self):
        if getattr(self, "_closechart_worker", None) is not None:
            self._closechart_worker.deleteLater()
            self._closechart_worker = None
        if getattr(self, "_closechart_thread", None) is not None:
            self._closechart_thread.deleteLater()
            self._closechart_thread = None

    # Update Methods
    def update_azimuth(self, new_azimuth):
        self.new_azimuth = new_azimuth

    def update_angle(self, new_cannon_angle):
        self.new_cannon_angle = new_cannon_angle

    def update_shortlow(self, new_shortlow):
        self.new_shortlow = new_shortlow


class ScanAreaWindow(QWidget):
    angle_signal = pyqtSignal(int)
    shortlow_signal = pyqtSignal(int)
    hit_calculation_signal = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.resize(250, 550)
        
        # 화면 중앙 하단에 고정 배치(원하면 좌표 조절)
        screen_geo = QApplication.desktop().availableGeometry()
        x = screen_geo.center().x() - (self.width() // 2) - 265
        y = screen_geo.center().y() - (self.height() // 2) - 5
        self.move(x, y)
        
        # self.setGeometry(1330, 440, 250, 550)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setWindowOpacity(0.5)  # 불투명

        current_dir = os.path.dirname(os.path.abspath(__file__))
        font_path = os.path.join(current_dir, "fonts/ocr-b.ttf")
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            font = QFont(QFontDatabase.applicationFontFamilies(font_id)[0], 14)
            self.setFont(font)
        else:
            self.setFont(QFont("Arial", 14))
        
        self.pixmap = QPixmap(self.size())  # QPixmap 버퍼 생성
        self.pixmap.fill(QColor(0, 0, 0))  # 초기화
        
        self.start_x = None
        self.start_y = None
        self.end_x = None
        self.end_y = None

        self.is_window_visible = False
        self._angle: float = 0.0
        self._shortlow: str = ""

        self.window_timer_150 = QTimer(self)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 128))
        painter.drawPixmap(0, 0, self.pixmap)
        painter.setPen(QColor('green'))
        painter.setFont(self.font())
        painter.drawText(10, 410, 180, 30, Qt.AlignLeft | Qt.AlignVCenter, '>> ' + str(self.shortlow))

        draw_neon_line(painter, 2, 2, 248, 2, 2, 64)
        draw_neon_line(painter, 248, 2, 248, 548, 2, 64)
        draw_neon_line(painter, 2, 548, 248, 548, 2, 64)
        draw_neon_line(painter, 2, 2, 2, 548, 2, 64)
    
    def hideEvent(self, event: QEvent):
        self.pixmap.fill(QColor(0, 0, 0))
        super().hideEvent(event)
    
    def mouseMoveEvent(self,event):
        self.draw_Line(event.x(),event.y())
        event.accept()
    
    def mouseReleaseEvent(self, event):
        self.draw_Line(event.x(), event.y())
        self.return_angle = (self.start_x, self.start_y, self.end_x, self.end_y)
        self.start_x = None
        self.start_y = None
        event.accept()
    
    def draw_Line(self,x,y):
        if self.start_x is None:
            self.start_x = x
            self.start_y = y
        else:
            self.end_x = x
            self.end_y = y
            self.pixmap.fill(QColor(0, 0, 0))
            painter = QPainter(self.pixmap)
            painter.setPen(QPen(Qt.red, 2, Qt.SolidLine))
            painter.drawLine(self.start_x, self.start_y, self.end_x, self.end_y)
            dx = abs(self.end_x - self.start_x)
            dy = self.end_y - self.start_y
            self.angle = round(math.degrees(math.atan2(dy, dx)), 3)
            painter.end()
        self.update()
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Plus:
            self.shortlow = self.shortlow[:-1]
        elif event.text().isdigit():
            self.shortlow += event.text()
        elif event.key() == Qt.Key_Enter:
            self.hit_calculation_signal.emit()
        event.accept()
    
    @pyqtProperty(int)
    def angle(self):
        return round(self._angle*10)

    @angle.setter
    def angle(self, new_angle):
        if self._angle != new_angle:
            self._angle = new_angle
            self.angle_signal.emit(self.angle)
    
    @pyqtProperty(str)
    def shortlow(self):
        return self._shortlow

    @shortlow.setter
    def shortlow(self, new_shortlow):
        if self._shortlow != new_shortlow:
            self._shortlow = new_shortlow
            if self.shortlow != '':
                self.shortlow_signal.emit(int(self.shortlow))
            else:
                self.shortlow_signal.emit(0)
        self.update()


class KeyboardActions(QObject):
    def __init__(self, hud_window: HUDWindow, scan_area_window: ScanAreaWindow):
        super().__init__()
        self.listener = None
        self.hud_window = hud_window
        self.scan_area_window = scan_area_window
    
    def scanning_toggle(self):
        if self.scan_area_window.is_window_visible:
            QMetaObject.invokeMethod(self.scan_area_window, "hide", Qt.QueuedConnection)
            QMetaObject.invokeMethod(self.hud_window.hit_table_widget, "hide", Qt.QueuedConnection)
            QMetaObject.invokeMethod(self.hud_window.lr_timer, "stop", Qt.QueuedConnection)
            if self.hud_window.cannon._session_key is not None: # server request 성공시
                self.hud_window.status_text_widget.change_color(self.hud_window._base_color)
                self.hud_window.status_text_widget.new_text = "REQUESTING..."
                QMetaObject.invokeMethod(
                    self.hud_window,
                    "request_closechart_async",
                    Qt.QueuedConnection
                )
            else:
                self.hud_window.status_text_widget.change_color(self.hud_window._warning_color)
                self.hud_window.status_text_widget.new_text = "OFFLINE"
        else:
            self.hud_window.status_text_widget.change_color(self.hud_window._base_color)
            self.hud_window.status_text_widget.new_text = "SCANNING..."
            QMetaObject.invokeMethod(self.hud_window.lr_timer, "start", Qt.QueuedConnection)
            QMetaObject.invokeMethod(self.scan_area_window, "show", Qt.QueuedConnection)
        self.scan_area_window.is_window_visible = not self.scan_area_window.is_window_visible

    ## Key Actions
    def on_press(self, key):
        try:
            if key.char == '*':
                self.scanning_toggle()
        except AttributeError:
            pass

    def start_listener(self):
        # 키보드 리스너 시작
        with keyboard.Listener(on_press=self.on_press) as listener:
            listener.join()


class CompassWindow(QWidget):
    def __init__(self):
        super().__init__()

        # HUDWindow와 같은 성격(투명/클릭스루/항상 위)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(0.75)

        # HUDWindow랑 비슷하게 폰트 적용(원하면 제거 가능)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        font_path = os.path.join(current_dir, "fonts/ocr-b.ttf")
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            font = QFont(QFontDatabase.applicationFontFamilies(font_id)[0], 14)
            self.setFont(font)
        else:
            self.setFont(QFont("Arial", 14))

        # 창 크기: 나침반+방위각 텍스트 정도만
        # (CompassWidget 250x250, AzimuthWidget 100x100)*
        self.resize(260, 115)

        self.new_azimuth: float = 0.0
        self.compass_widget = CompassWidget(self)
        self.azimuth_widget = AzimuthWidget(self)

        # 배치
        self.compass_widget.move(5, 0)
        self.azimuth_widget.move(80, 55) # 방향값 텍스트 위치 조정

        self.compass_widget.show()
        self.azimuth_widget.show()

        # 업데이트 타이머(기존 compass_timer 역할)
        self.compass_timer = QTimer(self)
        self.compass_timer.setInterval(AZIMUTH_DURATION)
        self.compass_timer.timeout.connect(lambda: self.compass_widget.set_rotation_start_ani(self.new_azimuth))
        self.compass_timer.timeout.connect(lambda: self.azimuth_widget.set_azimuth_start_ani(self.new_azimuth))
        self.compass_timer.start()

        # 화면 중앙 하단에 고정 배치(원하면 좌표 조절)
        screen_geo = QApplication.desktop().availableGeometry()
        x = screen_geo.center().x() - self.width() // 2
        y = screen_geo.center().y() + 195   # 나침반 창 위치 조절
        self.move(x, y)

    def update_azimuth(self, new_azimuth):
        self.new_azimuth = new_azimuth


if __name__ == '__main__':
    app = QApplication([])

    hud_window = HUDWindow()
    scan_area_window = ScanAreaWindow()

    tray_icon = QIcon(resource_path("main.ico"))
    tray = QSystemTrayIcon(tray_icon, app)
    tray.setToolTip("BDO_HUD")

    menu = QMenu()
    quit_action = QAction("Quit")
    quit_action.triggered.connect(app.quit)
    menu.addAction(quit_action)

    tray.setContextMenu(menu)
    tray.show()

    # ✅ 나침반 전용 창
    compass_window = CompassWindow()
    compass_window.show()

    hud_window.show()
    scan_area_window.hide()

    # 기존 시그널 연결
    scan_area_window.hit_calculation_signal.connect(hud_window.hit_table_fix)
    scan_area_window.angle_signal.connect(hud_window.update_angle)
    scan_area_window.shortlow_signal.connect(hud_window.update_shortlow)

    # ✅ 방위각 캡처 스레드 시작 + compass_window로 연결
    screen = QApplication.primaryScreen().geometry()
    x1 = screen.width() - 20 - 298
    y1 = 30
    x2 = x1 + 298
    y2 = y1 + 260
    azimuth_thread = AzimuthCaptureThread((x1, y1, x2, y2))
    azimuth_thread.angle_signal.connect(compass_window.update_azimuth)
    azimuth_thread.start()

    # keyboard thread
    keyboard_actions = KeyboardActions(hud_window, scan_area_window)
    listener_thread = threading.Thread(target=keyboard_actions.start_listener)
    listener_thread.daemon = True  # 프로그램 종료 시 스레드 종료
    listener_thread.start()

    # 종료 시 스레드 정리(권장)
    def _cleanup():
        azimuth_thread.stop()
        hud_window.cannon.stop_ws()

    app.aboutToQuit.connect(_cleanup)

    sys.exit(app.exec_())