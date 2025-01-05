from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QGraphicsDropShadowEffect
from PyQt5.QtGui import QColor, QPen, QFont

def draw_neon_line(painter, x1, y1, x2, y2, width, alpha):
    # 외곽 빛나는 효과 (Glow Effect)
    for i, glow_width in enumerate(range(width*3, 0, -width)):  # 점점 좁아지는 외곽선
        glow_pen = QPen(QColor(0, 255, 0, 75*i))  # 청록색 + 투명도
        glow_pen.setWidth(glow_width)
        glow_pen.setCapStyle(Qt.RoundCap)  # 둥근 끝 모양
        painter.setPen(glow_pen)
        painter.drawLine(x1, y1, x2, y2)  # 선 그리기
    # 중심 선 (Main Neon Line)
    main_pen = QPen(QColor(0, 255, 0, alpha))  # 밝은 청록색
    main_pen.setWidth(width)
    main_pen.setCapStyle(Qt.RoundCap)
    painter.setPen(main_pen)
    painter.drawLine(x1, y1, x2, y2)  # 선 그리기

class NeonLabel(QLabel):
    def __init__(self, text, *args, **kwargs):
        super().__init__(text)

        # 네온 텍스트 스타일
        font = QFont("Arial", 20, QFont.Bold)
        self.setFont(font)
        self.setAlignment(Qt.AlignCenter)

        # 텍스트 색상 (16진수)
        self.setStyleSheet("color: #FFFFFF;")  # 흰색 텍스트

        # 네온 효과 (빛 번짐)
        neon_effect = QGraphicsDropShadowEffect()
        neon_effect.setOffset(0, 0)  # 그림자 위치
        neon_effect.setBlurRadius(50)  # 더 강한 번짐 효과
        neon_effect.setColor(QColor(0, 255, 0))  # 네온 초록색
        self.setGraphicsEffect(neon_effect)