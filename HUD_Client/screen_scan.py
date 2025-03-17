import math
from PyQt5.QtCore import QThread, pyqtSignal
import cv2
import numpy as np
from mss.windows import MSS as mss

class AzimuthCaptureThread(QThread):
    """
    미니맵캡처, 시야각 인식 및 방위각 측정
    (x1, y1, x2, y2)
    """
    angle_signal = pyqtSignal(int)
    
    def __init__(self, capture_rect, parent=None):
        super().__init__(parent)
        self.capture_rect = capture_rect
        self.running = True
        self.azimuth_threshold = 7
        
    def run(self):
        #(3122, 30, 3420, 290)
        moniter = {
            'top': self.capture_rect[1],
            'left': self.capture_rect[0],
            'width': self.capture_rect[2]-self.capture_rect[0],
            'height': self.capture_rect[3]-self.capture_rect[1],
        }
        with mss() as sct:
            while self.running:
                screenshot = sct.grab(moniter)
                image = np.array(screenshot)
                calculated_angle = self.calculate_angle(image)

                if calculated_angle is not None:
                    self.angle_signal.emit(calculated_angle)

                self.msleep(16)
    
    def calculate_angle(self, image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 490, 500)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=40, minLineLength=8, maxLineGap=10)
        if lines is None:
            return None
        
        height, width = image.shape[:2]
        center = (width // 2, height // 2)
        filtered_lines = self._filter_lines(lines, center, margin=90)
        
        if len(filtered_lines) < 2:
            return None
        
        azimuths = self._calculate_azimuths(filtered_lines, center)
        filterd_azimuths = self._pick_duo_lines(azimuths, 110, 130)
        middle_angle = self._calculate_middle_azimuth(*filterd_azimuths) if len(filterd_azimuths) == 2 else None
        
        return middle_angle

    def _filter_lines(self, lines, center, margin):
        # 중앙+margin만큼의 범위에 직선의 중심이 존재하는 직선만
        cx, cy = center
        filtered = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            line_center_x = (x1 + x2) // 2
            line_center_y = (y1 + y2) // 2
            
            if (cx - margin <= line_center_x <= cx + margin and
                cy - margin <= line_center_y <= cy + margin):
                filtered.append(line)
        return filtered
    
    def _calculate_azimuths(self, lines, center):
        azimuths = []
        cx, cy = center
        
        for line in lines:
            x1, y1, x2, y2 = line[0]
            
            # 시작점을 중심점 기준으로 벡터 계산
            dx = x1 - cx if abs(x1 - cx) > abs(x2 - cx) else x2 - cx
            dy = y1 - cy if abs(y1 - cy) > abs(y2 - cy) else y2 - cy
            angle = math.degrees(math.atan2(dy, dx))
            azimuth = (angle + 360) % 360
            
            # 리스트의 모든 값과 비교하여 차이가 threshold 이상인 경우만 추가
            # 중요한 건 all([])는 True 라는거!!!!!!
            if all(abs(azimuth - a) >= self.azimuth_threshold for a in azimuths):
                azimuths.append(azimuth)
        return azimuths
    
    def _pick_duo_lines(self, filterd_lines, min_diff=110, max_diff=130):
        def angle_difference(angle1, angle2):
            diff = abs(angle1 - angle2)
            return min(diff, 360 - diff)  # 양방향 차이 중 최소값

        filtered_azimuths = []
        for i in range(len(filterd_lines)):
            for j in range(i + 1, len(filterd_lines)):
                if min_diff <= angle_difference(filterd_lines[i], filterd_lines[j]) <= max_diff:
                    filtered_azimuths.append(filterd_lines[i])
                    filtered_azimuths.append(filterd_lines[j])
                    break
        return filtered_azimuths
    
    def _calculate_middle_azimuth(self, azimuth1, azimuth2):
        azimuth1 %= 360
        azimuth2 %= 360
        diff = (azimuth2 - azimuth1 + 360) % 360
        
        # 중간값 계산
        middle = (azimuth1 + diff / 2) % 360 if diff <= 180 else (azimuth1 - (360 - diff) / 2 + 360) % 360
        
        # x축 기준 각도이므로 90도 더해서 정규화
        return int((middle + 90) % 360)
    
    def stop(self):
        self.running = False
        self.wait()
