__all__ = []


import logging
from functools import reduce

import torch
import torch_npu
from torch_npu.utils._error_code import ErrCode, ops_error


logger = logging.getLogger(__name__)


class _PreGenDropoutTask:
    def __init__(self, device, p):
        self.device = device
        self.p = p
        self.mask = None
        self.idx = 0
        self.max_mb = 16


class NpuPreGenDropout(torch.nn.Dropout):
    r"""NpuPreGenDropout using on npu device
    .. note::
        pre-generate Dropout mask, all masks are generated once with a big tensor.
    Args:
        p (float): probability of an element to be zeroed.
        module_name (string): the name of the model
    """

    prob = set()
    task_dict = {}
    dropout_stream = None

    def __init__(self, p, module_name=None):
        super().__init__(p)
        self.module_name = module_name
        NpuPreGenDropout.prob.add(p)

    def forward(self, x):
        if isinstance(x, torch.Tensor):
            dtype = x.dtype
            device = x.device
            do_mask_flag = True
            return_obj = x
        elif isinstance(x, list):
            shape, dtype, device = x
            do_mask_flag = False
            return_obj = None
        else:
            raise RuntimeError("input type error!" + ops_error(ErrCode.TYPE))

        if self.p == 0:
            return return_obj

        if self.p not in NpuPreGenDropout.task_dict:
            raise RuntimeError(f"NpuPreGenDropout input prob error! "
                               "You Only Register prob:{NpuPreGenDropout.task_dict.keys()}" + ops_error(ErrCode.VALUE))

        tmp_len = reduce(lambda a, b: a * b, x.shape)
        mask_len = int(((tmp_len + 128 - 1) // 128 * 128) / 8)
        task = NpuPreGenDropout.task_dict[self.p]
        end_idx = task.idx + mask_len
        mask = task.mask[task.idx:end_idx]

        if do_mask_flag:
            task.idx = end_idx
            if task.idx > len(task.mask):
                task.max_mb = max((task.idx * 8 // 1048576) + 1, task.max_mb)
                mask = task.mask[0:mask_len]

            return torch_npu.npu_dropout_do_mask(x, mask, self.p)[0]
        else:
            return mask

    @classmethod
    def enable_dropout_ensemble(cls, model):
        if cls.dropout_stream is None:
            cls.dropout_stream = torch.npu.Stream()

        def wait_stream_hook_func():
            def hook_function(module, inputs):
                torch.npu.current_stream().wait_stream(cls.dropout_stream)

            return hook_function

        model.register_forward_pre_hook(wait_stream_hook_func())

        model_device = f"npu:{torch.npu.current_device()}"
        for p in cls.prob:
            init_task = _PreGenDropoutTask(model_device, p)

            init_task.mask = torch_npu.npu_dropout_gen_mask([init_task.max_mb, 1024, 1024], p=p, 
                                                            dtype=torch.float32, device=model_device)
            cls.task_dict[p] = init_task

        def mask_gen_hook_func():
            def hook_function(module, inputs, outputs):
                for task in cls.task_dict.values():
                    task.mask = torch_npu.npu_dropout_gen_mask([task.max_mb, 1024, 1024], p=task.p, 
                                                               dtype=torch.float32, device=task.device)
                    task.idx = 0

            return hook_function

        model.register_forward_hook(mask_gen_hook_func())
