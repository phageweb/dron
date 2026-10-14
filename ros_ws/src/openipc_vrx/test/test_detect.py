import unittest

try:
    import numpy as np
    from openipc_vrx.detect import COCO, nms
except ImportError:          # numpy or Pillow missing: nothing to test here
    np = None


@unittest.skipIf(np is None, "numpy/Pillow not available")
class NmsTest(unittest.TestCase):
    def test_overlapping_boxes_keep_the_best(self):
        boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [50, 50, 60, 60]], dtype=float)
        scores = np.array([0.6, 0.9, 0.5])
        self.assertEqual(sorted(nms(boxes, scores, 0.5)), [1, 2])

    def test_separate_boxes_all_kept(self):
        boxes = np.array([[0, 0, 10, 10], [20, 0, 30, 10]], dtype=float)
        self.assertEqual(sorted(nms(boxes, np.array([0.5, 0.6]), 0.5)), [0, 1])

    def test_coco_has_80_classes_person_first(self):
        self.assertEqual(len(COCO), 80)
        self.assertEqual(COCO[0], "person")


if __name__ == "__main__":
    unittest.main()
