# QThread 사용
# pyqtSignal을 이용해서 데이터 통신

from PyQt5.QtCore import QThread, pyqtSignal
from pynput import keyboard
import sys
import time
from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

# 작업을 처리할 QThread
class WorkerThread(QThread):
    update_signal = pyqtSignal(str)  # UI 업데이트용 Signal

    def __init__(self):
        super().__init__()
        self.running = False  # 작업 실행 여부

    def run(self):
        while True:
            if self.running:
                self.update_signal.emit("Running...")  # UI에 전달
                time.sleep(0.1)  # 작업 반복
            else:
                self.update_signal.emit("")  # UI에 전달
                time.sleep(0.1)  # 잠시 대기

    def start_work(self):
        self.running = True  # 작업 시작

    def stop_work(self):
        self.running = False  # 작업 중지

# 메인 윈도우
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.label = QLabel("Press F4 to Start/Stop the Worker Thread")
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)

        # QThread 초기화
        self.worker = WorkerThread()
        self.worker.update_signal.connect(self.update_label)
        self.worker.start()  # 스레드 시작

    def update_label(self, text):
        self.label.setText(text)

# 키보드 입력 처리
class KeyListener:
    def __init__(self, worker_thread):
        self.worker_thread = worker_thread
        self.toggle = False  # 작업 상태

    def on_press(self, key):
        try:
            if key == keyboard.Key.f4:  # F4 키 감지
                self.toggle = not self.toggle
                if self.toggle:
                    print("Starting Worker Thread")
                    self.worker_thread.start_work()
                else:
                    print("Stopping Worker Thread")
                    self.worker_thread.stop_work()
        except Exception as e:
            print(f"Error: {e}")

    def start_listener(self):
        with keyboard.Listener(on_press=self.on_press) as listener:
            listener.join()

# 메인 실행
def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    # QThread와 키 리스너 연결
    key_listener = KeyListener(window.worker)

    # 키 리스너를 별도의 스레드로 실행
    from threading import Thread
    listener_thread = Thread(target=key_listener.start_listener, daemon=True)
    listener_thread.start()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()