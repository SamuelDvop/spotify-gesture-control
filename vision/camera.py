import cv2
from config import CAM_ID, FRAME_W, FRAME_H


class Camera:
    def __init__(self):
        self.cap = cv2.VideoCapture(CAM_ID)
        if not self.cap.isOpened():
            raise RuntimeError("No se pudo abrir la cámara")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)

    def read(self):
        ok, frame = self.cap.read()
        if not ok:
            return None
        frame = cv2.flip(frame, 1)
        return frame

    def release(self):
        self.cap.release()
