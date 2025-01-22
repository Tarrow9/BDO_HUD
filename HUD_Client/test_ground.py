from PyQt5.QtWidgets import QApplication, QWidget
from pynput.keyboard import Listener, Key
from PyQt5.QtCore import Qt, QTimer
import sys
import ctypes
import threading
from PyQt5.QtGui import *
import math

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Main Window")
        self.setGeometry(100, 100, 300, 200)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setWindowOpacity(0.8)  # 반투명
        self.setClickThrough()
    
    def setClickThrough(self):
        hwnd = int(self.winId())  # PyQt 창의 핸들 ID 가져오기
        # Windows API 호출을 위한 설정
        GWL_EXSTYLE = -20  # Extended window style
        WS_EX_LAYERED = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020

        # 기존 창 스타일에 투명 및 클릭 무시 옵션 추가
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT)

class SubWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sub Window")
        self.setGeometry(200, 100, 400, 200)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setWindowOpacity(0.5)  # 불투명
        
        self.pixmap = QPixmap(self.size())  # QPixmap 버퍼 생성
        self.pixmap.fill(Qt.transparent)  # 초기화
        
        self.past_x = None
        self.past_y = None
        self.present_x = None
        self.present_y = None
        self.return_angle = (0, 0, 0, 0)

        # 새로운 윈도우 상태 초기화
        self.new_window = None
        self.is_new_window_visible = False
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor(0, 255, 0, 255))
        painter.drawPixmap(0, 0, self.pixmap)
        self.update()
    
    def mouseMoveEvent(self,event):
        self.draw_Line(event.x(),event.y())
        dx, dy = abs(event.x() - self.past_x), event.y() - self.past_y
        angle = round(math.degrees(math.atan2(dy, dx)), 3)
        print(angle)
    def mouseReleaseEvent(self,event):  
        self.draw_Line(event.x(),event.y())
        self.return_angle = (self.past_x, self.past_y, self.present_x, self.present_y)
        dx = abs(self.present_x - self.past_x)
        dy = self.present_y - self.past_y
        angle = round(math.degrees(math.atan2(dy, dx)), 3)
        print(angle)
        self.past_x = None
        self.past_y = None
    def draw_Line(self,x,y):
        if self.past_x is None:
            self.past_x = x
            self.past_y = y
        else:
            self.present_x = x
            self.present_y = y
            self.pixmap.fill(Qt.transparent)
            painter = QPainter(self.pixmap)
            painter.setPen(QPen(Qt.black, 2, Qt.SolidLine))
            painter.drawLine(self.past_x,self.past_y,self.present_x,self.present_y)
            painter.end()
            

    def toggle_window(self):
        if self.is_new_window_visible:
            print('hide')
            self.pixmap.fill(Qt.transparent)
            QTimer.singleShot(0, self.hide)
        else:
            print('show')
            QTimer.singleShot(0, self.show)
        print('this')
        self.is_new_window_visible = not self.is_new_window_visible
        return None

    def create_new_window(self):
        # 일반 윈도우로 생성
        new_win = QWidget()
        new_win.setWindowTitle("New Window")
        new_win.setGeometry(0, 0, 0, 0)
        new_win.setWindowFlags(Qt.Window)  # 일반 윈도우
        new_win.setStyleSheet("background-color: lightblue;")
        return new_win

class KeyboardListener:
    def __init__(self, sub_window):
        self.sub_window = sub_window

    def on_press(self, key):
        try:
            if key == Key.f9:
                self.sub_window.toggle_window()
        except AttributeError:
            pass

    def start(self):
        with Listener(on_press=self.on_press) as listener:
            listener.join()

def main():
    app = QApplication(sys.argv)

    main_window = MainWindow()
    main_window.show()
    sub_window = SubWindow()
    sub_window.hide()

    # 키보드 이벤트 리스너 시작
    key = KeyboardListener(sub_window)
    listener_thread = threading.Thread(target=key.start)
    listener_thread.daemon = True  # 프로그램 종료 시 스레드 종료
    listener_thread.start()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
