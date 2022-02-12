# Copyright (c) 2020 Huawei Technologies Co., Ltd
# Copyright (c) 2019, Facebook CORPORATION. 
# All rights reserved.
#
# Licensed under the BSD 3-Clause License  (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://opensource.org/licenses/BSD-3-Clause
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from logging import exception
import os
import torch_npu._C
# this file is used to enhance the npu frontend API by set_option or other.

__all__ = ["set_option", "global_step_inc", "set_start_fuzz_compile_step", "set_aoe", "profile", "prof_init",  
            "prof_start", "prof_stop", "prof_finalize", "profileConfig"]

def set_option(option):
    if not isinstance(option, dict):
        raise TypeError("npu option must be a dict.")

    for option_name, option_value in option.items():
        option[option_name] = str(option_value)
    torch_npu._C._npu_setOption(option)

def init_dump():
    option = {"mdldumpswitch":"enable"}
    torch_npu._C._npu_setOption(option)

def set_dump(cfg_file):
    if not os.path.exists(cfg_file):
        raise AssertionError("cfg_file %s path does not exists."%(cfg_file))
    cfg_file = os.path.abspath(cfg_file)
    option = {"mdldumpconfigpath": cfg_file}
    torch_npu._C._npu_setOption(option)

def finalize_dump():
    option = {"mdldumpswitch": "disable"}
    torch_npu._C._npu_setOption(option)

_GLOBAL_STEP = 0
_START_FUZZ_COMPILE_STEP = 1
def global_step_inc():
    global _GLOBAL_STEP
    _GLOBAL_STEP += 1

    option = {"fuzzycompileswitch": "enable" if _GLOBAL_STEP >= _START_FUZZ_COMPILE_STEP \
        else "disable"}
    torch_npu._C._npu_setOption(option)

def set_start_fuzz_compile_step(step):
    if not isinstance(step, int):
        raise TypeError("step must be a int, but got ", type(step))
    
    global _START_FUZZ_COMPILE_STEP
    _START_FUZZ_COMPILE_STEP = step
    option = {"fuzzycompileswitch": "disable"}
    torch_npu._C._npu_setOption(option)

def set_aoe(dump_path):
    if os.path.exists(dump_path):
        option = {"autotune": "enable", "autotunegraphdumppath": dump_path}
        torch_npu._C._npu_setOption(option)
    else:
        try:
            os.makedirs(dump_path)
        except Exception:
            raise ValueError("the path of '%s' is invaild."%(dump_path))

def prof_init(path):
    if not os.path.exists(path):
        raise AssertionError("profiler_result_path: %s not exists."%(path))
    profiler_result_path = os.path.abspath(path)
    option = {"profilerResultPath": profiler_result_path}
    torch_npu._C._npu_setOption(option)

def prof_start(npu_event, aicore_metrics):
    torch_npu._C._prof_start(npu_event, aicore_metrics)

def prof_stop():
    option = {"profiling": "stop"}
    torch_npu._C._npu_setOption(option)

def prof_finalize():
    option = {"profiling": "finalize"}
    torch_npu._C._npu_setOption(option)

class npuEvent(object):
    def __init__(self):    
        self.ACL_PROF_ACL_API            = 0x0001
        self.ACL_PROF_TASK_TIME          = 0x0002
        self.ACL_PROF_AICORE_METRICS     = 0x0004
        self.ACL_PROF_AICPU              = 0x0008
        self.ACL_PROF_L2CACHE            = 0x0010
        self.ACL_PROF_HCCL_TRACE         = 0x0020
        self.ACL_PROF_TRAINING_TRACE     = 0x0040
        self.ACL_PROF_MSPROFTX           = 0x0080
        self.ACL_PROF_RUNTIME_API        = 0x0100

    def update(self, ACL_PROF_ACL_API=True, ACL_PROF_TASK_TIME=True,
                ACL_PROF_AICORE_METRICS=True, ACL_PROF_AICPU=True,
                ACL_PROF_L2CACHE=False, ACL_PROF_HCCL_TRACE=True,
                ACL_PROF_TRAINING_TRACE=True):
        if not ACL_PROF_ACL_API:
            self.ACL_PROF_ACL_API = 0x00
        if not ACL_PROF_TASK_TIME:
            self.ACL_PROF_TASK_TIME = 0x00
        if not ACL_PROF_AICORE_METRICS:
            self.ACL_PROF_AICORE_METRICS = 0x00
        if not ACL_PROF_AICPU:
            self.ACL_PROF_AICPU = 0x00
        if not ACL_PROF_L2CACHE:
            self.ACL_PROF_L2CACHE = 0x00
        if not ACL_PROF_HCCL_TRACE:
            self.ACL_PROF_HCCL_TRACE = 0x00
        if not ACL_PROF_TRAINING_TRACE:
            self.ACL_PROF_TRAINING_TRACE = 0x00
        return self.getConfig()

    def getConfig(self):
        return self.ACL_PROF_ACL_API | self.ACL_PROF_TASK_TIME | self.ACL_PROF_AICORE_METRICS  \
                | self.ACL_PROF_AICPU | self.ACL_PROF_L2CACHE | self.ACL_PROF_HCCL_TRACE \
                | self.ACL_PROF_TRAINING_TRACE | self.ACL_PROF_RUNTIME_API

class aiCoreMetrics(object):
    ACL_AICORE_ARITHMETIC_UTILIZATION = 0
    ACL_AICORE_PIPE_UTILIZATION = 1
    ACL_AICORE_MEMORY_BANDWIDTH = 2
    ACL_AICORE_L0B_AND_WIDTH = 3
    ACL_AICORE_RESOURCE_CONFLICT_RATIO = 4
    ACL_AICORE_NONE = 0xFF

class profileConfig(object):
    def __init__(self, ACL_PROF_ACL_API=True, ACL_PROF_TASK_TIME=True, ACL_PROF_AICORE_METRICS=True,
                ACL_PROF_AICPU=True, ACL_PROF_L2CACHE=False, ACL_PROF_HCCL_TRACE=True,
                ACL_PROF_TRAINING_TRACE=True, aiCoreMetricsType=0):                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 
        self.NpuEventConfig = npuEvent().update(ACL_PROF_ACL_API, ACL_PROF_TASK_TIME, ACL_PROF_AICORE_METRICS,
                                                ACL_PROF_AICPU, ACL_PROF_L2CACHE, ACL_PROF_HCCL_TRACE,
                                                ACL_PROF_TRAINING_TRACE)
        self.AiCoreMetricsConfig = aiCoreMetricsType


class profile(object):
    def __init__(self, profiler_result_path="./", use_e2e_profiler=False, 
        config=profileConfig()):
        self.result_path = profiler_result_path
        self.use_e2e_profiler = use_e2e_profiler
        self.npu_event = config.NpuEventConfig
        self.aicore_metrics = config.AiCoreMetricsConfig
        self.entered = False
        if self.use_e2e_profiler:
            raise ValueError("This version dose not support E2E profiling now!")

    def __enter__(self):
        if self.entered:
            raise RuntimeError("npu profiler traces are not reentrant")
        self.entered = True
        prof_init(self.result_path)
        prof_start(self.npu_event, self.aicore_metrics)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        prof_stop()
        prof_finalize()
        return False
  