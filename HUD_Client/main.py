import sys, os
import ctypes
import threading
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QPoint, QParallelAnimationGroup, QEasingCurve, QEvent, QObject, pyqtProperty
from PyQt5.QtGui import QColor, QPainter, QPen, QFont, QFontDatabase
from PyQt5.QtWidgets import QApplication, QWidget
from pynput import keyboard

from widgets import (LeftLineWidget, 
    RightLineWidget, 
    ShortLowWidget, 
    HeightWidget, 
    CompassWidget, 
    AzimuthWidget,
    StatusTextWidget,
    HitTableWidget,
)
from draw_tools import draw_neon_line

INF_LEFT = 1000  # 좌측 세로선 상단 x
INF_RIGHT = 1800  # 우측 세로선 상단 x
INF_HIGH = 60  # 좌측 세로선 상단 y
LINE_LEN = 30  # 가로선 길이

class HUDWindow(QWidget):
    ## Initializings
    def __init__(self):
        super().__init__()

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
        self.watch_lock = False
        self.left_line_widget = None
        self.center_shortlow : int = 100 # max: 550 min: 0, center0 = 55*30 - 15
        self.center_shortlow_widget = None
        self.shortlow_error = False
        self.right_line_widget = None
        self.center_height : int = 0  # max: 250 min: -250, center0 = 35*30 - 15
        self.center_height_widget = None
        self.height_error = False
        self.create_initial_left_widgets()
        self.create_initial_right_widgets()

        # CompassWidget 초기화
        self.azimuth : float = 0.0  # max: 360.0 min: 0.0
        self.compass_widget = None
        self.azimuth_widget = None
        self.create_initial_compass_widgets()

        # StatusWidget 초기화
        self.status_text_widget = None
        self.status_text = ""
        self.create_initial_status_text_widget()

        # # HitTableWidget 초기화
        self.hit_table_widget = None
        self.create_initial_hit_table_widget()

        # 타이머 설정
        self.timer1 = QTimer(self)
        self.timer2 = QTimer(self)
        self.timer3 = QTimer(self)

        self.timer1.timeout.connect(lambda: self.update_active_widgets(shortlow=100, height=0))

        self.timer2.timeout.connect(self.update_status_text)

        self.timer3.timeout.connect(self.update_hit_table)

        self.timer1.start(333)  # 333ms마다 실행
        self.timer2.start(111)  # 111ms마다 실행
        self.timer3.start(66)  # 66ms마다 실행, 스캔모드에서 on/off

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
        self.center_shortlow_widget = ShortLowWidget(self.center_shortlow, self)
        self.center_shortlow_widget.move(INF_LEFT + t + LINE_LEN + 22, center_y - 15)
        self.center_shortlow_widget.show()

    def create_initial_right_widgets(self):
        """초기 LeftLineWidget 17개 생성 및 배치"""
        center_y = self.height() // 2 # 중앙 y 좌표
        t = 2
        self.right_line_widget = RightLineWidget(self)
        self.right_line_widget.move(INF_RIGHT + t, center_y - 35*30 - 15)
        self.right_line_widget.show()
        """초기 HeightWidget 생성 및 배치"""
        self.center_height_widget = HeightWidget(self.center_height, self)
        self.center_height_widget.move(INF_RIGHT - t - 145, center_y - 15)
        self.center_height_widget.show()
    
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
        self.hit_table_widget.move(INF_RIGHT+200, 230)
        self.hit_table_widget.hide()

    # Update Widgets
    def update_active_widgets(self, shortlow=100, height=0, azimuth=0.0):
        # test
        from random import randint, uniform
        shortlow = randint(-100, 600)
        height = randint(-350, 350)
        azimuth = round(uniform(0.0, 360.0), 1)
        ## for real
        # diagonal = scan_diagonal()
        # angle = scan_angle()
        # shortlow = get_l(diagonal, angle)
        # height = get_h(diagonal, angle)
        # azimuth = scan_azimuth()

        shortlow_check = 0 < shortlow < 550
        height_check = -250 < height < 250
        azimuth_check = True # 화면인식 실패 시
        check_list = [
            (shortlow_check, 100),
            (height_check, 0),
            (azimuth_check, 0.0),
        ]
        value_dict = {
            'shortlow': shortlow,
            'height': height,
            'azimuth': azimuth,
        }
        widget_list = [
            (self.left_line_widget, self.center_shortlow_widget),
            (self.right_line_widget, self.center_height_widget),
            (self.compass_widget, self.azimuth_widget),
        ]
        for check, key, widgets in zip(check_list, value_dict, widget_list):
            if not check[0]:
                color = self._warnining_color
                value_dict[key] = check[1]
            else:
                color = self._base_color
            for widget in widgets:
                widget.change_color(color)

        origin_shortlow = self.center_shortlow
        origin_height = self.center_height
        self.center_shortlow = value_dict['shortlow']
        self.center_height = value_dict['height']

        # 방위각 반시계방향 시계방향 계산
        delta = azimuth - self.azimuth_widget.azimuth
        azimuth = azimuth-360 if delta > 180 else azimuth+360 if delta < -180 else azimuth

        # 여기서 LineWidget animate
        left_y_distance = (value_dict['shortlow'] - origin_shortlow) * 3
        right_y_distance = (value_dict['height'] - origin_height) * 3
        self.animate_widget(left_y_distance, right_y_distance, value_dict['shortlow'], value_dict['height'], azimuth)

    def update_status_text(self):
        self.status_text_widget.animate_text(self.status_text)

    # Animate Widgets
    def animate_widget(self, left_y_distance, right_y_distance, center_shortlow, center_height, azimuth):
        self.ani_group = QParallelAnimationGroup()
        ani_duration = 300
        if not self.watch_lock:
            l_line_ani = QPropertyAnimation(self.left_line_widget, b"pos")
            l_line_ani.setDuration(ani_duration)
            l_line_ani.setStartValue(self.left_line_widget.pos())
            l_line_ani.setEndValue(self.left_line_widget.pos() + QPoint(0, left_y_distance))
            l_line_ani.setEasingCurve(QEasingCurve.InOutQuad)
            self.ani_group.addAnimation(l_line_ani)
            short_low_ani = QPropertyAnimation(self.center_shortlow_widget, b"value")
            short_low_ani.setDuration(ani_duration)
            short_low_ani.setEasingCurve(QEasingCurve.InOutQuad)
            short_low_ani.setStartValue(self.center_shortlow_widget.value)
            short_low_ani.setEndValue(center_shortlow)
            self.ani_group.addAnimation(short_low_ani)

            r_line_ani = QPropertyAnimation(self.right_line_widget, b"pos")
            r_line_ani.setDuration(ani_duration)
            r_line_ani.setStartValue(self.right_line_widget.pos())
            r_line_ani.setEndValue(self.right_line_widget.pos() + QPoint(0, right_y_distance))
            r_line_ani.setEasingCurve(QEasingCurve.InOutQuad)
            self.ani_group.addAnimation(r_line_ani)
            height_ani = QPropertyAnimation(self.center_height_widget, b"value")
            height_ani.setDuration(ani_duration)
            height_ani.setEasingCurve(QEasingCurve.InOutQuad)
            height_ani.setStartValue(self.center_height_widget.value)
            height_ani.setEndValue(center_height)
            self.ani_group.addAnimation(height_ani)

        azimuth_ani = QPropertyAnimation(self.azimuth_widget, b"azimuth")
        azimuth_ani.setDuration(ani_duration)
        azimuth_ani.setEasingCurve(QEasingCurve.InOutQuad)
        azimuth_ani.setStartValue(self.azimuth_widget.azimuth)
        azimuth_ani.setEndValue(azimuth)
        self.ani_group.addAnimation(azimuth_ani)
        compass_ani = QPropertyAnimation(self.compass_widget, b"rotation")
        compass_ani.setDuration(ani_duration)
        compass_ani.setEasingCurve(QEasingCurve.InOutQuad)
        compass_ani.setStartValue(self.compass_widget.rotation)
        compass_ani.setEndValue(azimuth)
        self.ani_group.addAnimation(compass_ani)

        self.ani_group.finished.connect(self.cleanup_sl_ht_az_animations)
        self.ani_group.start()

    # HIT TABLE
    def update_hit_table(self):
        self.hit_table_widget.update()

    def cleanup_sl_ht_az_animations(self):
        """애니메이션 그룹을 정리"""
        if self.ani_group:
            self.ani_group.clear()  # 모든 애니메이션 제거
            self.ani_group = None
        self.azimuth_widget.azimuth %= 360
        self.compass_widget.rotation %= 360

    ## Key Actions
    def on_press(self, key):
        try:
            if key == keyboard.Key.f11:  # F11 키가 눌리면
                # 이건 스캔 동작 상태 조작 로직
                # self.watch_lock = not self.watch_lock
                # print("F11 키가 눌렸습니다!", self.watch_lock)

                # 이건 status문자 변경 조작 로직
                # from random import randint
                # random_list = ["CONNECTING..", "CONNECTED", "SCANNING...", "FIXED", "CRITICAL ERROR"]
                # self.status_text = random_list[randint(0, 4)]
                # print("F11 키가 눌렸습니다!", self.status_text)

                # 이건 hit table active 로직
                self.hit_table_widget.ani_count = -1
                self.hit_table_widget.show()
                
        except AttributeError:
            pass

    def start_listener(self):
        # 키보드 리스너 시작
        with keyboard.Listener(on_press=self.on_press) as listener:
            listener.join()

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