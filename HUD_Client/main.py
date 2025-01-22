import sys, os
import threading
import math
from PyQt5.QtCore import QMetaObject, Qt, QTimer, QObject, pyqtSignal, QEvent, pyqtProperty
from PyQt5.QtGui import QColor, QPainter, QPen, QFont, QFontDatabase, QPixmap
from PyQt5.QtWidgets import QApplication, QWidget
from pynput import keyboard

from widgets import (LeftLineWidget, 
    RightLineWidget, 
    ShortLowWidget, 
    CNAngleWidget, 
    CompassWidget, 
    AzimuthWidget,
    StatusTextWidget,
    HitTableWidget,
)
from screen_scan import (
    AzimuthCaptureThread,
)
from draw_tools import draw_neon_line
from conf import(
    AZIMUTH_DURATION,
)
from tools import Cannon

INF_LEFT = 1000  # 좌측 세로선 상단 x
INF_RIGHT = 1800  # 우측 세로선 상단 x
INF_HIGH = 60  # 좌측 세로선 상단 y
LINE_LEN = 30  # 가로선 길이

class HUDWindow(QWidget):
    ## Initializings
    def __init__(self):
        super().__init__()
        self.cannon = Cannon()

        # 윈도우 설정, click-through 설정 (WindowTransparentForInput)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(0.75)

        # 폰트, 색 설정
        current_dir = os.path.dirname(os.path.abspath(__file__))
        font_path = os.path.join(current_dir, "fonts/ocr-b.ttf")
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            font = QFont(QFontDatabase.applicationFontFamilies(font_id)[0], 14)
            self.setFont(font)
        else:
            self.setFont(QFont("Arial", 14))
        self._warnining_color = QColor(255, 0, 0, 192)  # 50% 투명한 빨간색
        self._base_color = QColor(0, 255, 0, 192)  # 50% 투명한 초록색

        # 창 크기 및 위치
        self.setGeometry(0, 0, 2800, 630)  # 크기 설정
        screen_geometry = QApplication.desktop().availableGeometry()
        self.move(screen_geometry.center() - self.rect().center())  # 화면 중앙에 배치

        # LineWidget 리스트 초기화
        self._scanning_status = False # scan상태 비활성 상태로 윈도우 활성화

        self.left_line_widget = None
        self.right_line_widget = None
        self.new_shortlow : int = 100 # max: 550 min: 0, center0 = 55*30 - 15
        self.center_shortlow_widget = None
        self.center_cn_angle_widget = None
        self.new_cannon_angle : int = 0 # max: 250 min: -250, center0 = 35*30 - 15

        self.create_initial_left_widgets()
        self.create_initial_right_widgets()

        # CompassWidget 초기화
        self.azimuth_thread = AzimuthCaptureThread((3122, 30, 3420, 290))
        self.azimuth_thread.angle_signal.connect(self.update_azimuth)
        self.new_azimuth : float = 0.0  # max: 360.0 min: 0.0
        self.compass_widget = None
        self.azimuth_widget = None
        self.create_initial_compass_widgets()

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

        self.compass_timer = QTimer(self) # ALWAYS
        self.compass_timer.setInterval(AZIMUTH_DURATION)
        self.compass_timer.timeout.connect(lambda: self.compass_widget.set_rotation_start_ani(self.new_azimuth))
        self.compass_timer.timeout.connect(lambda: self.azimuth_widget.set_azimuth_start_ani(self.new_azimuth))
        self.compass_timer.start()
        self.azimuth_thread.start()

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
        center_y = self.height() // 2 # 중앙 y 좌표
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
        center_y = self.height() // 2 # 중앙 y 좌표
        t = 2
        self.right_line_widget = RightLineWidget(self)
        self.right_line_widget.move(INF_RIGHT + t, center_y - 60*30 - 15)
        self.right_line_widget.show()
        """초기 CNAngleWidget 생성 및 배치"""
        self.center_cn_angle_widget = CNAngleWidget(self)
        self.center_cn_angle_widget.move(INF_RIGHT - t - 145, center_y - 15)
        self.center_cn_angle_widget.show()
    
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
        self.hit_table_widget = HitTableWidget(self)
        self.hit_table_widget.move(INF_RIGHT+180, 390)
        self.hit_table_widget.hide()

    # hit table handling
    def hit_table_fix(self):
        QMetaObject.invokeMethod(self.lr_timer, "stop", Qt.QueuedConnection)
        QMetaObject.invokeMethod(self.background_value_generator_timer, "stop", Qt.QueuedConnection)
        shortlow_check = 0 < self.new_shortlow < 550
        height_check = -450 < self.new_cannon_angle < 450
        if not (shortlow_check and height_check):
            self.status_text_widget.change_color(self._warnining_color)
            self.status_text_widget.new_text = "CRITICAL ERROR"
            return

        # cannon calc
        new_hit_table = self.cannon.setting_hit_table(self.new_cannon_angle/10, self.new_shortlow)
        import time
        time.sleep(0.3)

        self.status_text_widget.change_color(self._base_color)
        self.status_text_widget.new_text = "FIXED"

        self.hit_table_widget.hit_table = new_hit_table
        self.hit_table_widget.show()
        self.hit_table_widget.ani_count = -1
    
    # just hide widget
    def hit_table_off(self):
        if True:
            self.status_text_widget.change_color(self._base_color)
            self.status_text_widget.new_text = "ONLINE"
        else:
            self.status_text_widget.change_color(self._warnining_color)
            self.status_text_widget.new_text = "OFFLINE"
        self.hit_table_widget.hide()
        self.hit_table_widget.pixmap.fill(Qt.transparent)
    
    def update_azimuth(self, azimuth):
        self.new_azimuth = azimuth

    def update_angle(self, cannon_angle):\
        self.new_cannon_angle = cannon_angle

    def load_hit_table(self):
        '''
        fix: shortlow, height
        request 서버
        json 로드
        self.hit_table 변경
        self.hit_table_widget.ani_count = 0
        '''

class ScanAreaWindow(QWidget):
    angle_signal = pyqtSignal(int)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.resize(200, 450)  # 윈도우 크기 설정
        self.setGeometry(1450, 440, 200, 450)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setWindowOpacity(0.5)  # 불투명
        
        self.pixmap = QPixmap(self.size())  # QPixmap 버퍼 생성
        self.pixmap.fill(QColor(0, 0, 0))  # 초기화
        
        self.start_x = None
        self.start_y = None
        self.end_x = None
        self.end_y = None

        self.is_window_visible = False
        self._angle: float = 0.0
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)  # 안티앨리어싱 활성화
        painter.fillRect(self.rect(), QColor(0, 0, 0, 128))
        painter.drawPixmap(0, 0, self.pixmap)

        draw_neon_line(painter, 2, 2, 198, 2, 2, 64)
        draw_neon_line(painter, 198, 2, 198, 448, 2, 64)
        draw_neon_line(painter, 2, 448, 198, 448, 2, 64)
        draw_neon_line(painter, 2, 2, 2, 448, 2, 64)
    
    def hideEvent(self, event: QEvent):
        self.pixmap.fill(QColor(0, 0, 0))
        super().hideEvent(event)
    
    def mouseMoveEvent(self,event):
        self.draw_Line(event.x(),event.y())
    
    def mouseReleaseEvent(self,event):
        self.draw_Line(event.x(),event.y())
        self.return_angle = (self.start_x, self.start_y, self.end_x, self.end_y)
        self.start_x = None
        self.start_y = None
    
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
    
    @pyqtProperty(int)
    def angle(self):
        return round(self._angle*10)

    @angle.setter
    def angle(self, new_angle):
        if self._angle != new_angle:
            self._angle = new_angle
            self.angle_signal.emit(self.angle)

class KeyboardActions(QObject):
    def __init__(self, hud_window: HUDWindow, scan_area_window: ScanAreaWindow):
        super().__init__()
        self.listener = None
        self.hud_window = hud_window
        self.scan_area_window = scan_area_window
    
    def scanning_start(self):
        # hud window
        self.hud_window.status_text_widget.change_color(self.hud_window._base_color)
        self.hud_window.status_text_widget.new_text = "SCANNING..."
        QMetaObject.invokeMethod(self.hud_window.lr_timer, "start", Qt.QueuedConnection)

        # scan area window
        if self.scan_area_window.is_window_visible:
            QMetaObject.invokeMethod(self.scan_area_window, "hide", Qt.QueuedConnection)
        else:
            QMetaObject.invokeMethod(self.scan_area_window, "show", Qt.QueuedConnection)
        self.scan_area_window.is_window_visible = not self.scan_area_window.is_window_visible

    ## Key Actions
    def on_press(self, key):
        try:
            if key == keyboard.Key.left:
                self.scanning_start()
            
            if key == keyboard.Key.f10:
                # 이건 status문자 변경 조작 로직
                from random import randint
                random_list = ["CONNECTING..", "CONNECTED", "SCANNING...", "FIXED", "CRITICAL ERROR"]
                self.hud_window.status_text_widget.new_text = random_list[randint(0, 4)]
                print("F10: ", self.hud_window.status_text_widget.new_text)
            
            # hit table update
            if key == keyboard.Key.f11:
                self.hud_window.hit_table_fix()
            
            if key == keyboard.Key.f12:
                self.hud_window.hit_table_off()
            
        except AttributeError:
            pass

    def start_listener(self):
        # 키보드 리스너 시작
        with keyboard.Listener(on_press=self.on_press) as listener:
            listener.join()

if __name__ == '__main__':
    # init
    app = QApplication([])

    # windows
    hud_window = HUDWindow()
    scan_area_window = ScanAreaWindow()
    hud_window.show()
    scan_area_window.hide()
    scan_area_window.angle_signal.connect(hud_window.update_angle)

    # keyboard thread
    keyboard_actions = KeyboardActions(hud_window, scan_area_window)
    listener_thread = threading.Thread(target=keyboard_actions.start_listener)
    listener_thread.daemon = True  # 프로그램 종료 시 스레드 종료
    listener_thread.start()

    sys.exit(app.exec_())