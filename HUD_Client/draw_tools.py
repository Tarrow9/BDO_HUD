from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPen

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
