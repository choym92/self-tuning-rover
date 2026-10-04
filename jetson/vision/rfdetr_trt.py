#!/usr/bin/env python3
"""Run an RF-DETR TensorRT engine (built by rfdetr_bench.py) without the rfdetr package.

Pre- and post-processing copy rfdetr 1.11.1 `RFDETR.predict` and `PostProcess` (box-only models):
RGB in [0, 1], plain bilinear resize to the square model resolution (no letterbox, no antialias),
ImageNet mean/std; then sigmoid over the (300 queries x 91 classes) logits, top 300 query/class
pairs, boxes from normalised cx, cy, w, h to pixels, clamped to the image. Labels are COCO
category ids (person = 1), as in rfdetr.assets.coco_classes.COCO_CLASSES.

Engine I/O: input (1, 3, R, R) float; dets (1, 300, 4) float; labels (1, 300, 91) float.
"""
import numpy as np
import tensorrt as trt
import torch
import torch.nn.functional as F

MEAN = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
STD = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)


class RFDETRTRT:
    def __init__(self, engine_path, num_select=300):
        with open(engine_path, "rb") as f:
            self.engine = trt.Runtime(trt.Logger(trt.Logger.WARNING)).deserialize_cuda_engine(f.read())
        self.ctx = self.engine.create_execution_context()
        self.buf = {}
        for i in range(self.engine.num_io_tensors):
            name = self.engine.get_tensor_name(i)
            self.buf[name] = torch.empty(tuple(self.engine.get_tensor_shape(name)), dtype=torch.float32, device="cuda")
            self.ctx.set_tensor_address(name, self.buf[name].data_ptr())
        self.res = self.buf["input"].shape[-1]
        self.num_select = num_select
        self.mean, self.std = MEAN.cuda(), STD.cuda()

    @torch.no_grad()
    def predict(self, bgr, threshold=0.5):
        """bgr: HxWx3 uint8. Returns (boxes xyxy px, scores, COCO category ids) as numpy arrays."""
        h, w = bgr.shape[:2]
        x = torch.from_numpy(np.ascontiguousarray(bgr[:, :, ::-1])).cuda().permute(2, 0, 1)[None].float() / 255
        x = F.interpolate(x, size=(self.res, self.res), mode="bilinear", align_corners=False, antialias=False)
        self.buf["input"].copy_((x - self.mean) / self.std)
        stream = torch.cuda.current_stream()
        self.ctx.execute_async_v3(stream.cuda_stream)
        stream.synchronize()
        prob = self.buf["labels"][0].sigmoid()                      # (300, 91)
        n_cls = prob.shape[1]
        scores, idx = prob.flatten().topk(min(self.num_select, prob.numel()))
        query, labels = idx // n_cls, idx % n_cls
        cx, cy, bw, bh = self.buf["dets"][0, query].unbind(-1)
        scale = torch.tensor([w, h, w, h], device="cuda", dtype=torch.float32)
        boxes = torch.stack([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2], -1) * scale
        boxes = boxes.clamp_min(0).clamp(max=scale)
        keep = scores > threshold
        return boxes[keep].cpu().numpy(), scores[keep].cpu().numpy(), labels[keep].cpu().numpy()
