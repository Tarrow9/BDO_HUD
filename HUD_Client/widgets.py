import math

from PyQt5.QtCore import Qt, QPoint, pyqtProperty
from PyQt5.QtGui import QColor, QPainter, QPen, QFont, QTransform
from PyQt5.QtWidgets import QWidget, QLabel

INF_LEFT = 1000  # 좌측 세로선 상단 x
INF_RIGHT = 1800  # 우측 세로선 상단 x
INF_HIGH = 60  # 좌측 세로선 상단 y
LINE_LEN = 30  # 가로선 길이

class LeftLineWidget(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setFont(QFont("Arial", 14))
        self.resize(100, 2400)  # 위젯 크기 설정
        self.line_color = QColor(0, 255, 0, 192)  # 50% 투명한 초록색

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
                painter.drawLine(50, target_y, 100, target_y)
                # 텍스트 그리기
                painter.setPen(self.line_color)
                font = self.font()
                painter.setFont(font)
                painter.drawText(0, target_y-15, 50, 30, Qt.AlignLeft | Qt.AlignVCenter, str(line_number))
            else:
                painter.drawLine(70, target_y, 90, target_y)
    
    def change_color(self, color):
        color.setAlpha(192)
        if self.line_color != color:
            self.line_color = color
            self.update()

class RightLineWidget(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setFont(QFont("Arial", 14))
        self.resize(100, 2100)  # 위젯 크기 설정
        self.line_color = QColor(0, 255, 0, 192)  # 50% 투명한 초록색

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
                # 텍스트 그리기
                painter.setPen(self.line_color)
                font = self.font()
                painter.setFont(font)
                painter.drawText(45, target_y-15, 45, 30, Qt.AlignRight | Qt.AlignVCenter, str(line_number//10))
            else:
                # 짧은 선 그리기
                painter.drawLine(10, target_y, 30, target_y)
    
    def change_color(self, color):
        color.setAlpha(192)
        if self.line_color != color:
            self.line_color = color
            self.update()

class ShortLowWidget(QWidget):
    def __init__(self, center_shortlow, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.center_shortlow = center_shortlow
        self.line_color = QColor(0, 255, 0, 192)  # 50% 투명한 초록색
        
    def paintEvent(self, event):
        self.line_color.setAlpha(192)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 텍스트 그리기
        painter.setPen(self.line_color)
        font = self.font()
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignLeft | Qt.AlignVCenter, str(self.center_shortlow))
    
    def change_color(self, color):
        color.setAlpha(192)
        if self.line_color != color:
            self.line_color = color
            self.update()
    
    @pyqtProperty(int)
    def value(self):
        return self.center_shortlow
    @value.setter
    def value(self, new_value):
        self.center_shortlow = new_value
        self.update()  # 숫자가 변경될 때 화면 갱신

class HeightWidget(QWidget):
    def __init__(self, height, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._height = height
        self.line_color = QColor(0, 255, 0, 192)  # 50% 투명한 초록색
        
    def paintEvent(self, event):
        self.line_color.setAlpha(192)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 텍스트 그리기
        painter.setPen(self.line_color)
        font = self.font()
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignRight | Qt.AlignVCenter, str(self._height/10))
    
    def change_color(self, color):
        color.setAlpha(192)
        if self.line_color != color:
            self.line_color = color
            self.update()
    
    @pyqtProperty(int)
    def value(self):
        return self._height
    @value.setter
    def value(self, new_value):
        self._height = new_value
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
        self._rotation = self._rotation % 360

        # 폰트 정의
        mini_text = QFont("Arial", 8)
        bold_text = QFont("Arial", 11)
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
                self.line_color.setAlpha(255)
                painter.setPen(QPen(self.line_color, 4))
                text_radius = radius * 0.65
                outer_point = QPoint(
                    int(radius * math.cos(angle_rad)),
                    int(radius * math.sin(angle_rad))
                )
            else:
                painter.setFont(mini_text)
                self.line_color.setAlpha(127)
                painter.setPen(QPen(self.line_color, 2))
                text_radius = radius * 0.6
                outer_point = QPoint(
                    int(radius * 0.95 * math.cos(angle_rad)),
                    int(radius * 0.95 * math.sin(angle_rad))
                )
            painter.drawLine(inner_point, outer_point)

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

    # 회전을 위한 프로퍼티
    @pyqtProperty(float)
    def rotation(self):
        return self._rotation
    @rotation.setter
    def rotation(self, rotation):
        self._rotation = rotation
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
        font = self.font()
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignCenter | Qt.AlignVCenter, str(round(self._azimuth)))

    def change_color(self, color):
        color.setAlpha(255)
        if self.line_color != color:
            self.line_color = color
            self.update()

    @pyqtProperty(float)
    def value(self):
        return round(self._azimuth, 1)
    @value.setter
    def value(self, new_value):
        self._azimuth = round(new_value, 1)
        self.update()  # 숫자가 변경될 때 화면 갱신 