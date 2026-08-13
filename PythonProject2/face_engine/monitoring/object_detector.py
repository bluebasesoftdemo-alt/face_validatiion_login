from ultralytics import YOLO

CELL_PHONE_CLASS_ID = 67
BOOK_CLASS_ID = 73


class ObjectDetector:
    def __init__(self, confidence=0.30):
        self.model = YOLO("yolov8n.pt")
        self.confidence = confidence
        self.watch_classes = {"cell phone", "book"}

    def detect(self, frame):
        results = self.model(
            frame,
            verbose=False,
            imgsz=320,
            classes=[CELL_PHONE_CLASS_ID, BOOK_CLASS_ID],
        )[0]

        detections = []
        for box in results.boxes:
            cls_id = int(box.cls[0])
            label = self.model.names[cls_id]
            conf = float(box.conf[0])

            if label in self.watch_classes and conf >= self.confidence:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                detections.append({"label": label, "bbox": (x1, y1, x2, y2), "conf": conf})

        return detections