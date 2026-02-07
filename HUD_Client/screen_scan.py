import math
import cv2
import numpy as np
import pyopencl as cl
from PyQt5.QtCore import QThread, pyqtSignal
from mss.windows import MSS as mss
from gpu_util import GPUUtils

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
        self.gpu_utils = GPUUtils()
        self.prev_pair = None
        self.middle_ema = None
        self.ema_alpha = 0.35

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
                shot = sct.grab(moniter)
                image = np.frombuffer(shot.raw, dtype=np.uint8).reshape(shot.height, shot.width, 4)
                calculated_angle = self.calculate_angle(image)

                if calculated_angle is not None:
                    self.angle_signal.emit(calculated_angle)

                self.msleep(33)

    def _candidates(self, lines, center):
        cx, cy = center
        cands = []
        for line in lines:
            x1, y1, x2, y2 = line[0]

            # 길이(긴 선 우선)
            length = math.hypot(x2 - x1, y2 - y1)

            # 중심 기준으로 "더 먼 끝점" 방향을 사용 (기존 의도 유지!)
            d1 = (x1 - cx)**2 + (y1 - cy)**2
            d2 = (x2 - cx)**2 + (y2 - cy)**2
            if d1 >= d2:
                dx, dy = x1 - cx, y1 - cy
            else:
                dx, dy = x2 - cx, y2 - cy

            azimuth = (math.degrees(math.atan2(dy, dx)) + 360) % 360

            # 중심 근처를 더 신뢰(선생님 기존 filter 의도 반영)
            mx = (x1 + x2) * 0.5
            my = (y1 + y2) * 0.5
            dist_center = math.hypot(mx - cx, my - cy)

            # 점수: 길이↑, 중심근접↑ (dist 스케일은 ROI에 맞게 조절)
            score = length * (1.0 / (1.0 + dist_center / 80.0))

            cands.append({"az": azimuth, "len": length, "dist": dist_center, "score": score})
        return cands

    def _cluster_angles(self, cands, merge_deg=6):
        # azimuth를 0~360로 정렬 후, 가까운 각도끼리 묶어서
        # 각 클러스터에서 score가 가장 높은 것만 대표로 남김
        cands = sorted(cands, key=lambda c: c["az"])
        clusters = []
        for c in cands:
            placed = False
            for cl in clusters:
                # 대표 각도와 원형 차이 비교
                d = abs(c["az"] - cl["rep"]["az"])
                d = min(d, 360 - d)
                if d <= merge_deg:
                    # 더 점수가 높은 후보를 대표로
                    if c["score"] > cl["rep"]["score"]:
                        cl["rep"] = c
                    placed = True
                    break
            if not placed:
                clusters.append({"rep": c})
        return [cl["rep"] for cl in clusters]

    def _ang_diff(self, a, b):
        d = abs(a - b) % 360
        return min(d, 360 - d)

    def _ang_ema(self, prev, new, alpha):
        if prev is None:
            return new
        delta = (new - prev + 540) % 360 - 180
        return (prev + alpha * delta) % 360

    def _pick_pair_120(self, reps, prev_pair=None, target=120, tol=6):
        best = None
        best_score = -1e18

        for i in range(len(reps)):
            for j in range(i+1, len(reps)):
                a, b = reps[i]["az"], reps[j]["az"]
                if abs(self._ang_diff(a, b) - target) > tol:
                    continue

                pair_score = reps[i]["score"] + reps[j]["score"]

                # 이전 프레임과의 연속성 가점(튀는 것 방지)
                if prev_pair is not None:
                    p1, p2 = prev_pair
                    dmatch = min(
                        self._ang_diff(a, p1) + self._ang_diff(b, p2),
                        self._ang_diff(a, p2) + self._ang_diff(b, p1),
                    )
                    pair_score += 200.0 / (1.0 + dmatch)  # 가중치는 상황에 따라 조절

                if pair_score > best_score:
                    best_score = pair_score
                    best = (a, b)

        return best

    def calculate_angle(self, image):
        edges = self.gpu_utils.gpu_canny(image)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=40, minLineLength=8, maxLineGap=10)
        if lines is None:
            return None

        h, w = image.shape[:2]
        center = (w // 2, h // 2)

        # 기존처럼 "중앙 주변만" 라인을 먼저 제한하고 싶으면 유지 가능
        filtered_lines = self._filter_lines(lines, center, margin=90)
        if len(filtered_lines) < 2:
            return None

        cands = self._candidates(filtered_lines, center)
        reps = self._cluster_angles(cands, merge_deg=self.azimuth_threshold)

        pair = self._pick_pair_120(reps, prev_pair=self.prev_pair, target=120, tol=6)
        if pair is None:
            return None

        middle = self._calculate_middle_azimuth(pair[0], pair[1])  # 기존 함수 유지
        self.middle_ema = self._ang_ema(self.middle_ema, middle, self.ema_alpha)
        self.prev_pair = pair

        return int(self.middle_ema)

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
