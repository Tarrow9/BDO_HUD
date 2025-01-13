import sys, os
import ctypes
import threading
from PyQt5.QtCore import QMetaObject, Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QPen, QFont, QFontDatabase
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
from draw_tools import draw_neon_line
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

        # 윈도우 설정
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
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

        # click-through 설정
        self.setClickThrough()

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
        self.background_value_generator_timer = QTimer(self) # ALWAYS
        self.background_value_generator_timer.setInterval(500)
        self.background_value_generator_timer.timeout.connect(self.random_generator)
        self.background_value_generator_timer.start()

        self.lr_timer = QTimer(self) # ON / OFF
        self.lr_timer.setInterval(333)
        self.lr_timer.timeout.connect(lambda: self.left_line_widget.set_shortlow_start_ani(self.new_shortlow))
        self.lr_timer.timeout.connect(lambda: self.center_shortlow_widget.set_shortlow_start_ani(self.new_shortlow))
        self.lr_timer.timeout.connect(lambda: self.right_line_widget.set_height_start_ani(self.new_cannon_angle))
        self.lr_timer.timeout.connect(lambda: self.center_cn_angle_widget.set_height_start_ani(self.new_cannon_angle))

        self.compass_timer = QTimer(self) # ALWAYS
        self.compass_timer.setInterval(333)
        self.compass_timer.timeout.connect(lambda: self.compass_widget.set_rotation_start_ani(self.new_azimuth))
        self.compass_timer.timeout.connect(lambda: self.azimuth_widget.set_azimuth_start_ani(self.new_azimuth))
        self.compass_timer.start()

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

    def setClickThrough(self):
        hwnd = int(self.winId())  # PyQt 창의 핸들 ID 가져오기
        # Windows API 호출을 위한 설정
        GWL_EXSTYLE = -20  # Extended window style
        WS_EX_LAYERED = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020

        # 기존 창 스타일에 투명 및 클릭 무시 옵션 추가
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT)

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
        # lr_line stop
        QMetaObject.invokeMethod(self.lr_timer, "stop", Qt.QueuedConnection)
        # QMetaObject.invokeMethod(self.scanner_timer, "stop", Qt.QueuedConnection)
        QMetaObject.invokeMethod(self.background_value_generator_timer, "stop", Qt.QueuedConnection)
        shortlow_check = 0 < self.new_shortlow < 550
        height_check = -450 < self.new_cannon_angle < 450
        if not (shortlow_check and height_check):
            self.status_text_widget.change_color(self._warnining_color)
            self.status_text_widget.new_text = "CRITICAL ERROR"
            return

        # cannon calc
        new_hit_table = self.cannon.setting_hit_table(self.new_cannon_angle/10, self.new_shortlow)
        print(self.new_cannon_angle/10, self.new_shortlow)
        import time
        time.sleep(0.3)

        self.status_text_widget.change_color(self._base_color)
        self.status_text_widget.new_text = "FIXED"

        self.hit_table_widget.hit_table = new_hit_table
        self.hit_table_widget.show()
        self.hit_table_widget.ani_count = -1
        print("F11")
    # scan shortlow, height
    def hit_table_scanning(self):
        # start scanning
        self.status_text_widget.change_color(self._base_color)
        self.status_text_widget.new_text = "SCANNING..."
        QMetaObject.invokeMethod(self.lr_timer, "start", Qt.QueuedConnection)
        # QMetaObject.invokeMethod(self.scanner_timer, "stop", Qt.QueuedConnection)
        QMetaObject.invokeMethod(self.background_value_generator_timer, "start", Qt.QueuedConnection)

        # self.new_shortlow = randint(-100, 600)
        # self.new_cannon_angle = randint(-350, 350) # *10한 int로 주기
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
    
    ## Key Actions
    def on_press(self, key):
        try:
            if key == keyboard.Key.f9:
                self.hit_table_scanning()
            
            if key == keyboard.Key.f10:
                # 이건 status문자 변경 조작 로직
                from random import randint
                random_list = ["CONNECTING..", "CONNECTED", "SCANNING...", "FIXED", "CRITICAL ERROR"]
                self.status_text_widget.new_text = random_list[randint(0, 4)]
                print("F10: ", self.status_text_widget.new_text)
            
            # hit table update
            if key == keyboard.Key.f11:
                self.hit_table_fix()
            
            if key == keyboard.Key.f12:
                self.hit_table_off()
            
        except AttributeError:
            pass

    def start_listener(self):
        # 키보드 리스너 시작
        with keyboard.Listener(on_press=self.on_press) as listener:
            listener.join()
    
    ## For Test
    def random_generator(self):
        from random import randint, uniform
        self.new_shortlow = randint(-100, 600)
        self.new_cannon_angle = randint(-600, 600)
        self.new_azimuth = round(uniform(0.0, 360.0), 1)

    def load_hit_table(self):
        '''
        fix: shortlow, height
        request 서버
        json 로드
        self.hit_table 변경
        self.hit_table_widget.ani_count = 0
        '''

if __name__ == '__main__':
    app = QApplication([])
    window = HUDWindow()
    window.show()

    listener_thread = threading.Thread(target=window.start_listener)
    listener_thread.daemon = True  # 프로그램 종료 시 스레드 종료
    listener_thread.start()

    sys.exit(app.exec_())