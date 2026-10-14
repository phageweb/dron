"""People and things in a picture, with a YOLO model in ONNX on the CPU.

The model is YOLO11n trained on COCO (80 classes: person, car, chair,
bottle, backpack, ...), exported once to ONNX by export_model.sh; running
it needs only onnxruntime, numpy and Pillow, no PyTorch. Kept free of rclpy
so it can be tested without ROS.

The VRX picture has its own overlay and the OSD drawn over the camera
image; `mask` rectangles (fractions of the picture) are blacked out before
the model sees them, so a voltage readout is not taken for a thing.
"""

import io

import numpy as np
from PIL import Image

COCO = (
    "person bicycle car motorcycle airplane bus train truck boat traffic_light "
    "fire_hydrant stop_sign parking_meter bench bird cat dog horse sheep cow "
    "elephant bear zebra giraffe backpack umbrella handbag tie suitcase frisbee "
    "skis snowboard sports_ball kite baseball_bat baseball_glove skateboard "
    "surfboard tennis_racket bottle wine_glass cup fork knife spoon bowl banana "
    "apple sandwich orange broccoli carrot hot_dog pizza donut cake chair couch "
    "potted_plant bed dining_table toilet tv laptop mouse remote keyboard "
    "cell_phone microwave oven toaster sink refrigerator book clock vase "
    "scissors teddy_bear hair_drier toothbrush"
).split()

# The VRX's own readouts along the bottom and the SD card in the corner,
# and the bottom OSD rows the lidar scan is written into.
VRX_MASK = ((0.0, 0.85, 1.0, 1.0), (0.84, 0.07, 1.0, 0.15))


def nms(boxes, scores, iou):
    """Indices kept by greedy non-maximum suppression; boxes are x1 y1 x2 y2."""
    order = scores.argsort()[::-1]
    keep = []
    area = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    while order.size:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(boxes[i, 0], boxes[order[1:], 0])
        yy1 = np.maximum(boxes[i, 1], boxes[order[1:], 1])
        xx2 = np.minimum(boxes[i, 2], boxes[order[1:], 2])
        yy2 = np.minimum(boxes[i, 3], boxes[order[1:], 3])
        inter = np.clip(xx2 - xx1, 0, None) * np.clip(yy2 - yy1, 0, None)
        overlap = inter / (area[i] + area[order[1:]] - inter + 1e-9)
        order = order[1:][overlap < iou]
    return keep


class Detector:
    def __init__(self, model_path, conf=0.4, iou=0.5, classes=None, mask=VRX_MASK, threads=0):
        import onnxruntime as ort

        opts = ort.SessionOptions()
        if threads:
            opts.intra_op_num_threads = threads
        self.session = ort.InferenceSession(str(model_path), opts, providers=["CPUExecutionProvider"])
        inp = self.session.get_inputs()[0]
        self.input_name = inp.name
        self.size = inp.shape[2]           # square input, 640
        self.conf, self.iou = conf, iou
        self.classes = None if not classes else {COCO.index(c) for c in classes}
        self.mask = mask

    def prepare(self, image):
        """Letterbox to the model's square input; returns tensor, scale, padding."""
        w, h = image.size
        s = self.size / max(w, h)
        nw, nh = round(w * s), round(h * s)
        canvas = Image.new("RGB", (self.size, self.size), (114, 114, 114))
        px, py = (self.size - nw) // 2, (self.size - nh) // 2
        canvas.paste(image.resize((nw, nh), Image.BILINEAR), (px, py))
        x = np.asarray(canvas, dtype=np.float32).transpose(2, 0, 1)[None] / 255.0
        return x, s, px, py

    def masked(self, image):
        if not self.mask:
            return image
        image = image.copy()
        w, h = image.size
        for x1, y1, x2, y2 in self.mask:
            image.paste((0, 0, 0), (int(x1 * w), int(y1 * h), int(x2 * w), int(y2 * h)))
        return image

    def __call__(self, image):
        """[(class name, score, x1, y1, x2, y2)] in pixels of `image`, best first."""
        if isinstance(image, (bytes, bytearray)):
            image = Image.open(io.BytesIO(image))
        image = image.convert("RGB")
        self.last_size = image.size
        x, s, px, py = self.prepare(self.masked(image))
        out = self.session.run(None, {self.input_name: x})[0][0]   # (84, 8400)
        scores_all = out[4:]
        cls = scores_all.argmax(0)
        score = scores_all[cls, np.arange(scores_all.shape[1])]
        ok = score >= self.conf
        if self.classes is not None:
            ok &= np.isin(cls, list(self.classes))
        if not ok.any():
            return []
        cx, cy, bw, bh = out[0, ok], out[1, ok], out[2, ok], out[3, ok]
        boxes = np.stack([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2], 1)
        boxes = (boxes - [px, py, px, py]) / s
        w, h = image.size
        boxes = np.clip(boxes, 0, [w, h, w, h])
        cls, score = cls[ok], score[ok]
        result = []
        for c in np.unique(cls):
            sel = np.where(cls == c)[0]
            for k in nms(boxes[sel], score[sel], self.iou):
                i = sel[k]
                result.append((COCO[c], float(score[i]), *map(float, boxes[i])))
        return sorted(result, key=lambda r: -r[1])
