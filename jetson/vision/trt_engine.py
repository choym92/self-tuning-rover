#!/usr/bin/env python3
"""Run a TensorRT engine on NumPy arrays (Jetson). CUDA buffers come from torch, which the
Ultralytics container already has. Dynamic input dimensions are fixed to the engine's optimisation
profile (trtexec --shapes builds one profile with min = opt = max). Outputs are returned in the
engine's tensor order, which follows the ONNX graph's output order.
"""
import numpy as np
import tensorrt as trt
import torch


class TRTEngine:
    def __init__(self, path):
        with open(path, "rb") as f:
            self.engine = trt.Runtime(trt.Logger(trt.Logger.WARNING)).deserialize_cuda_engine(f.read())
        self.ctx = self.engine.create_execution_context()
        names = [self.engine.get_tensor_name(i) for i in range(self.engine.num_io_tensors)]
        self.inputs = [n for n in names if self.engine.get_tensor_mode(n) == trt.TensorIOMode.INPUT]
        self.outputs = [n for n in names if n not in self.inputs]
        for n in self.inputs:
            shape = tuple(self.engine.get_tensor_shape(n))
            if -1 in shape:
                shape = tuple(self.engine.get_tensor_profile_shape(n, 0)[2])
            self.ctx.set_input_shape(n, shape)
        self.buf = {}
        for n in names:
            dtype = torch.from_numpy(np.empty(0, trt.nptype(self.engine.get_tensor_dtype(n)))).dtype
            self.buf[n] = torch.empty(tuple(self.ctx.get_tensor_shape(n)), dtype=dtype, device="cuda")
            self.ctx.set_tensor_address(n, self.buf[n].data_ptr())

    def __call__(self, *arrays):
        for n, a in zip(self.inputs, arrays):
            self.buf[n].copy_(torch.from_numpy(np.ascontiguousarray(a)))
        stream = torch.cuda.current_stream()
        self.ctx.execute_async_v3(stream.cuda_stream)
        stream.synchronize()
        return [self.buf[n].cpu().numpy() for n in self.outputs]
