import math

from PyQt5.QtCore import Qt, QPoint, pyqtProperty, QPropertyAnimation, QEasingCurve, QTimer
from PyQt5.QtGui import QColor, QPainter, QPen, QFont, QPixmap
from PyQt5.QtWidgets import QWidget, QLabel

from draw_tools import draw_neon_line

INF_LEFT = 1000  # 좌측 세로선 상단 x
INF_RIGHT = 1800  # 우측 세로선 상단 x
INF_HIGH = 60  # 좌측 세로선 상단 y
LINE_LEN = 30  # 가로선 길이

class LeftLineWidget(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.resize(120, 2400)  # 위젯 크기 설정
        self.line_color = QColor(0, 255, 0, 218)

        self.l_line_ani = None
        self._default_shortlow = 100
        self.shortlow = self._default_shortlow

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 초록색 투명한 선 설정
        pen = QPen(self.line_color)
        pen.setWidth(2)
        painter.setPen(pen)

        for i, line_number in enumerate(range(650, -160, -10)):
            target_y = (i*30)+15
            if line_number % 100 == 0:
                # 100의 배수인 경우: 중앙(50, 15)에서 오른쪽 끝(100, 15)까지 선 그리기
                painter.drawLine(60, target_y, 100, target_y)
                painter.setFont(self.font())
                painter.drawText(0, target_y-15, 60, 30, Qt.AlignLeft | Qt.AlignVCenter, str(line_number))
            else:
                painter.drawLine(70, target_y, 90, target_y)
    
    def set_shortlow_start_ani(self, new_shortlow):
        if not (0 < new_shortlow < 550):
            new_shortlow = self._default_shortlow
            self.change_color(QColor(255, 0, 0, 218))
        else:
            self.change_color(QColor(0, 255, 0, 218))
        
        if self.l_line_ani is None:
            self.l_line_ani = QPropertyAnimation(self, b"pos")
        if self.l_line_ani.state() == QPropertyAnimation.Running:
            return
        self.l_line_ani.setDuration(300)
        self.l_line_ani.setStartValue(self.pos())
        self.l_line_ani.setEndValue(self.pos() + QPoint(0, (new_shortlow - self.shortlow)*3))
        self.l_line_ani.setEasingCurve(QEasingCurve.InOutQuad)
        self.l_line_ani.start()
        self.shortlow = new_shortlow
    
    def change_color(self, color):
        color.setAlpha(218)
        if self.line_color != color:
            self.line_color = color
            self.update()

class RightLineWidget(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.resize(150, 2100)  # 위젯 크기 설정
        self.line_color = QColor(0, 255, 0, 218)  # 50% 투명한 초록색

        self.r_line_ani = None
        self._default_height = 0
        self._height = self._default_height

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 초록색 투명한 선 설정
        pen = QPen(self.line_color)
        pen.setWidth(2)
        painter.setPen(pen)

        for i, line_number in enumerate(range(350, -360, -10)):
            target_y = (i * 30) + 15
            if line_number % 100 == 0:
                # 100의 배수인 경우: 중앙(50, 15)에서 오른쪽 끝(100, 15)까지 선 그리기
                painter.drawLine(0, target_y, 50, target_y)
                painter.setFont(self.font())
                painter.drawText(55, target_y-15, 55, 30, Qt.AlignRight | Qt.AlignVCenter, str(line_number//10))
            else:
                # 짧은 선 그리기
                painter.drawLine(10, target_y, 30, target_y)
    
    def set_height_start_ani(self, new_height):
        if not (-450 < new_height < 450):
            new_height = self._default_height
            self.change_color(QColor(255, 0, 0, 218))
        else:
            self.change_color(QColor(0, 255, 0, 218))
        
        if self.r_line_ani is None:
            self.r_line_ani = QPropertyAnimation(self, b"pos")
        if self.r_line_ani.state() == QPropertyAnimation.Running:
            return
        self.r_line_ani.setDuration(300)
        self.r_line_ani.setStartValue(self.pos())
        self.r_line_ani.setEndValue(self.pos() + QPoint(0, (new_height - self._height)*3))
        self.r_line_ani.setEasingCurve(QEasingCurve.InOutQuad)
        self.r_line_ani.start()
        self._height = new_height
    
    def change_color(self, color):
        color.setAlpha(218)
        if self.line_color != color:
            self.line_color = color
            self.update()

class ShortLowWidget(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._default_shortlow = 100
        self._shortlow = self._default_shortlow
        self.line_color = QColor(0, 255, 0, 218)
        self.short_low_ani = None
        
    def paintEvent(self, event):
        self.line_color.setAlpha(218)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 텍스트 그리기
        painter.setPen(self.line_color)
        painter.setFont(self.font())
        painter.drawText(self.rect(), Qt.AlignLeft | Qt.AlignVCenter, str(self._shortlow))
    
    def change_color(self, color):
        color.setAlpha(192)
        if self.line_color != color:
            self.line_color = color
            self.update()
    
    def set_shortlow_start_ani(self, new_shortlow):
        if not (0 < new_shortlow < 550):
            new_shortlow = self._default_shortlow
            self.change_color(QColor(255, 0, 0, 218))
        else:
            self.change_color(QColor(0, 255, 0, 218))

        if self.short_low_ani is None:
            self.short_low_ani = QPropertyAnimation(self, b"shortlow")
        if self.short_low_ani.state() == QPropertyAnimation.Running:
            return
        self.short_low_ani.setDuration(300)
        self.short_low_ani.setStartValue(self._shortlow)
        self.short_low_ani.setEndValue(new_shortlow)
        self.short_low_ani.setEasingCurve(QEasingCurve.InOutQuad)
        self.short_low_ani.start()
        self._shortlow = new_shortlow
    
    @pyqtProperty(int)
    def shortlow(self):
        return self._shortlow
    @shortlow.setter
    def shortlow(self, new_shortlow):
        self._shortlow = new_shortlow
        self.update()  # 숫자가 변경될 때 화면 갱신

class HeightWidget(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._default_height = 0
        self._height = self._default_height
        self.line_color = QColor(0, 255, 0, 218)
        self.height_ani = None

    def paintEvent(self, event):
        self.line_color.setAlpha(218)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 텍스트 그리기
        painter.setPen(self.line_color)
        painter.setFont(self.font())
        painter.drawText(self.rect(), Qt.AlignRight | Qt.AlignVCenter, str(self._height/10))
    
    def change_color(self, color):
        color.setAlpha(218)
        if self.line_color != color:
            self.line_color = color
            self.update()
    
    def set_height_start_ani(self, new_height):
        if not (-450 < new_height < 450):
            new_height = self._default_height
            self.change_color(QColor(255, 0, 0, 218))
        else:
            self.change_color(QColor(0, 255, 0, 218))

        if self.height_ani is None:
            self.height_ani = QPropertyAnimation(self, b"height")
        if self.height_ani.state() == QPropertyAnimation.Running:
            return
        self.height_ani.setDuration(300)
        self.height_ani.setStartValue(self._height)
        self.height_ani.setEndValue(new_height)
        self.height_ani.setEasingCurve(QEasingCurve.InOutQuad)
        self.height_ani.start()
        self.center_shortlow = new_height
    
    @pyqtProperty(int)
    def height(self):
        return self._height
    @height.setter
    def height(self, new_height):
        self._height = new_height
        self.update()  # 숫자가 변경될 때 화면 갱신

class HidingWidget(QWidget):
    def __init__(self, parent=None, width=200, height=60):
        super().__init__(parent)
        # 위젯을 화면 최상단에 위치시키는 설정
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)  # 배경을 투명하게 설정
        self.setAttribute(Qt.WA_DeleteOnClose)  # 창이 닫힐 때 메모리 정리
        self.width = width
        self.height = height
        self.resize(width, height)  # 크기 설정

        # 색상 및 투명도 설정
        self.overlay_color = QColor(0, 0, 0, 128)  # 반투명 검정 (RGBA: 50% 투명)

    def paintEvent(self, event):
        """위젯의 배경을 그리는 함수"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 전체 영역을 overlay_color로 채우기
        painter.fillRect(self.rect(), self.overlay_color)

        # 뒤에 있는 위젯을 보이지 않게 함
        painter.setCompositionMode(QPainter.CompositionMode_Clear)
        # 이 위젯의 위치에 fillRect를 사용하여 투명한 사각형을 그림
        painter.fillRect(0, 0, self.width, self.height, QColor(0, 0, 0, 0))

class CompassWidget(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.resize(250, 250)  # 크기 설정
        self._rotation = 0.0  # 회전 각도
        self.line_color = QColor(0, 255, 0, 127)  # 50% 투명한 초록색

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)  # 안티앨리어싱 활성화

        # 중심점과 반지름 계산
        center = self.rect().center()
        radius = min(self.width(), self.height()) // 2 - 10

        # 외곽 원 그리기
        painter.setPen(QPen(QColor(0, 0, 0, 0), 2))
        painter.drawEllipse(center, radius, radius)

        # 회전 중심 이동
        painter.translate(center)  # 중심을 (125, 125)로 설정, 이때 (0, 0) 기준
        # 회전 적용
        painter.rotate(-self._rotation)

        # 폰트 정의
        mini_text = QFont("Bahnschrift Light", 8)
        bold_text = QFont("Bahnschrift Light", 11)
        painter.setFont(mini_text)

        # 시침마다 직선 및 숫자 그리기
        for i in range(12):
            angle = (i * 30) - 90  # 각 시각의 각도 (-90도로 조정해 12가 위로 이동)
            angle_rad = math.radians(angle)

            # 시침 선 그리기
            inner_point = QPoint(
                int(radius * 0.8 * math.cos(angle_rad)),
                int(radius * 0.8 * math.sin(angle_rad))
            )
            if i % 3 == 0:
                painter.setFont(bold_text)
                text_radius = radius * 0.65
                outer_point = QPoint(
                    int(radius * math.cos(angle_rad)),
                    int(radius * math.sin(angle_rad))
                )
                draw_neon_line(painter, inner_point.x(), inner_point.y(), outer_point.x(), outer_point.y(), 3, 255)
            else:
                painter.setFont(mini_text)
                text_radius = radius * 0.6
                outer_point = QPoint(
                    int(radius * 0.95 * math.cos(angle_rad)),
                    int(radius * 0.95 * math.sin(angle_rad))
                )
                draw_neon_line(painter, inner_point.x(), inner_point.y(), outer_point.x(), outer_point.y(), 1, 127)

            # 숫자 그리기
            text_x = int(text_radius * math.cos(angle_rad))
            text_y = int(text_radius * math.sin(angle_rad))

            # 텍스트 회전 및 그리기
            painter.save()  # 현재 상태 저장
            painter.translate(text_x, text_y)  # 텍스트 위치로 이동
            painter.rotate(angle + 90)  # 각도를 반시계 방향으로 회전
            painter.drawText(
                -10, -10, 20, 20,  # 텍스트 박스 크기
                Qt.AlignCenter,  # 가운데 정렬
                str((i + 11) % 12 + 1)  # 시각 계산 (1부터 12까지)
            )
            painter.restore()  # 이전 상태 복원
    
    def set_rotation_start_ani(self, new_rotation):
        # 회전각 재계산
        delta = new_rotation - self.rotation
        new_rotation = new_rotation-360 if delta > 180 else new_rotation+360 if delta < -180 else new_rotation

        if not hasattr(self, "compass_ani"):
            self.compass_ani = QPropertyAnimation(self, b"rotation")
        if self.compass_ani.state() == QPropertyAnimation.Running:
            return
        self.compass_ani.setDuration(300)
        self.compass_ani.setEasingCurve(QEasingCurve.InOutQuad)
        self.compass_ani.setStartValue(self.rotation)
        self.compass_ani.setEndValue(new_rotation)
        self.compass_ani.start()
        self.rotation %= 360

    # 회전을 위한 프로퍼티
    @pyqtProperty(float)
    def rotation(self):
        return self._rotation
    @rotation.setter
    def rotation(self, rotation):
        self._rotation = round(rotation, 1)
        self.update()

    def change_color(self, color):
        if self.line_color != color:
            self.line_color = color
            self.update()

class AzimuthWidget(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._azimuth = 0.0
        self.line_color = QColor(0, 255, 0, 255)  # 50% 투명한 초록색
        self.resize(100, 100)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 텍스트 그리기
        painter.setPen(self.line_color)
        painter.setFont(self.font())
        painter.drawText(self.rect(), Qt.AlignCenter | Qt.AlignVCenter, str(round(self._azimuth) % 360))

    def change_color(self, color):
        color.setAlpha(255)
        if self.line_color != color:
            self.line_color = color
            self.update()
    
    def set_azimuth_start_ani(self, new_azimuth):
        # 방위각 재계산
        delta = new_azimuth - self.azimuth
        new_azimuth = new_azimuth-360 if delta > 180 else new_azimuth+360 if delta < -180 else new_azimuth

        if not hasattr(self, "azimuth_ani"):
            self.azimuth_ani = QPropertyAnimation(self, b"azimuth")
        if self.azimuth_ani.state() == QPropertyAnimation.Running:
            return
        self.azimuth_ani.setDuration(300)
        self.azimuth_ani.setEasingCurve(QEasingCurve.InOutQuad)
        self.azimuth_ani.setStartValue(self.azimuth)
        self.azimuth_ani.setEndValue(new_azimuth)
        self.azimuth_ani.start()
        self.azimuth %= 360

    @pyqtProperty(float)
    def azimuth(self):
        return round(self._azimuth, 1)
    @azimuth.setter
    def azimuth(self, new_value):
        self._azimuth = round(new_value, 1)
        self.update()  # 숫자가 변경될 때 화면 갱신 

class StatusTextWidget(QWidget):
    def __init__(self, text, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.line_color = QColor(0, 255, 0, 192)  # 75% 투명한 초록색
        self.resize(350, 30)

        self.widget_timer_33_150 = QTimer(self) # DURING RUN
        self.widget_timer_33_150.setInterval(150)
        self.widget_timer_33_150.timeout.connect(self.animate_text)
        self.widget_timer_33_150.start()
        # NeonLabel setting
        self.text = "CONNECTTING..."
        self.new_text = "CONNECTTING..."

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setFont(self.font())
        painter.setPen(self.line_color)
        painter.drawText(self.rect(), Qt.AlignLeft | Qt.AlignVCenter, str(self.text))
    
    def animate_underscore(self):
        self.text += "_"

    def animate_text(self):
        # 완성
        if self.text in [self.new_text, self.new_text + '_']:
            if self.widget_timer_33_150.interval() == 33:
                self.widget_timer_33_150.setInterval(150)
            if self.text == self.new_text:
                self.text += "_"
            else:
                self.text = self.text[:-1]
        # 업데이트중
        else:
            if self.widget_timer_33_150.interval() == 150:
                self.widget_timer_33_150.setInterval(33)
            
            if self.new_text.startswith(self.text):
                self.text += self.new_text[len(self.text)]
            else:
                self.text = self.text[:-1]
        self.update()

    def change_color(self, color):
        color.setAlpha(192)
        if self.line_color != color:
            self.line_color = color
            self.update()

class HitTableWidget(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.green_color = QColor(0, 255, 0, 255)
        self.yellow_color = QColor(255, 255, 0, 255)
        self.red_color = QColor(255, 0, 0, 255)
        self.resize(790, 240) # 70px, 30px

        self.ani_count = 16
        self.point_bool = False

        self.hit_table = { # base table
            0: [67.55,  75.63,  80.7,   84.17,   89.51,   96.89,   106.52,  114.56,  122.89, 138.17], 
            1: [91.38,  97.86,  104.57, 113.86,  123.55,  131.07,  138.82,  152.23,  166.25, 189.97], 
            2: [141.25, 155.73, 167.05, 174.82,  186.8,   199.18, [220.7], [238.71], 262.21, 302.12], 
            3: [171.36, 184.12, 197.35,'211.03',[225.18],[239.78], 265.14,  291.70,  313.99, 366.97], 
            4: [182.76, 190.88, 199.18,'211.96',[220.7], [229.62],'243.32', 262.21,  276.85, 296.97], 
            5: [184.18, 191.47, 198.91, 202.68, '210.33','218.12',[226.05],[238.21], 250.69, 267.83], 
            6: [157.52, 163.41, 169.4,  175.51,  181.72,  188.04,  194.47,  204.31, '214.4', [231.75]]
        }

        self.pixmap = QPixmap(self.size())  # QPixmap 버퍼 생성
        self.pixmap.fill(Qt.transparent)  # 초기화

        self.widget_timer_33_150 = QTimer(self) # DURING RUN
        self.widget_timer_33_150.setInterval(150)
        self.widget_timer_33_150.timeout.connect(self.update)
        self.widget_timer_33_150.start()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # base painter
        painter.setPen(self.green_color)
        font = self.font()
        font.setPointSize(10)
        painter.setFont(font)
        # base
        self.draw_base_row_col(painter)
        
        # update values
        painter.drawPixmap(0, 0, self.pixmap)
        self.add_shortlows()
    
    def draw_base_row_col(self, painter):
        # baseline
        painter.drawLine(0, 30, 770, 30)
        painter.drawLine(70, 0, 70, 240)
        # row column
        for c in range(0, 10):
            painter.drawText(70*(c+1), 0, 70, 30, Qt.AlignCenter | Qt.AlignVCenter, f"{c*10}~{(c+1)*10}")
        for r in range(7):
            painter.drawText(0, 30*(r+1), 70, 30, Qt.AlignCenter | Qt.AlignVCenter, str(r))

    def add_shortlows(self):
        # text
        if self.ani_count == 16:
            painter = QPainter(self)
            font = self.font()
            font.setPointSize(10)
            painter.setFont(font)
            painter.setPen(self.green_color)
            if self.widget_timer_33_150.interval() == 33:
                self.widget_timer_33_150.setInterval(150)
            if self.point_bool:
                painter.drawText(750, 210, 20, 30, Qt.AlignRight | Qt.AlignVCenter, "_")
            self.point_bool = not self.point_bool
            return
        else:
            painter = QPainter(self.pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(self.green_color)
            font = self.font()
            font.setPointSize(10)
            painter.setFont(font)
            if self.ani_count == -1:
                self.pixmap.fill(Qt.transparent)
                self.widget_timer_33_150.setInterval(33)
            else:
                for angle, shortlow_list in self.hit_table.items():
                    power = self.ani_count - angle
                    if power > 9:
                        continue
                    level = type(shortlow_list[power])
                    if level == list:
                        painter.setPen(self.red_color)
                        draw_string = str(round(shortlow_list[power][0], 1))
                    elif level == str:
                        painter.setPen(self.yellow_color)
                        draw_string = str(round(float(shortlow_list[power]), 1))
                    else:
                        painter.setPen(self.green_color)
                        draw_string = str(round(shortlow_list[power], 1))
                    painter.drawText(70*(power+1), 30*(angle+1), 70, 30, Qt.AlignCenter | Qt.AlignVCenter, draw_string)
                    if power == 0:
                        break
            self.ani_count += 1
        painter.end()
