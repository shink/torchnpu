// Copyright (c) 2020, Huawei Technologies.All rights reserved.
//
// Licensed under the BSD 3-Clause License  (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// https://opensource.org/licenses/BSD-3-Clause
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include "torch_npu/csrc/profiler/cann_profiling.h"
#include <c10/npu/NPUStream.h>
#include <c10/npu/NPUException.h>

namespace torch_npu {
namespace profiler {

NpuProfiling& NpuProfiling::Instance() {
  static NpuProfiling npuProfiling;
  return npuProfiling;
}

void NpuProfiling::Init(const std::string &path) {
  TORCH_CHECK(status == PROFILING_FINALIZE, "init current profile status is: ", status, " error!");
  c10::npu::npuSynchronizeDevice();
  auto ret = c10::npu::acl::AclProfilingInit(path.c_str(), path.length());
  if (ret && (ret != ACL_ERROR_PROF_ALREADY_RUN)) {
    NPU_LOGE("npu AclProfInit fail, error code: %d", ret);
    C10_NPU_SHOW_ERR_MSG();
    return;
  }
  status = PROFILING_INIT;
}

void NpuProfiling::Start(uint64_t npu_event, uint64_t aicore_metrics) {
  TORCH_CHECK(status == PROFILING_INIT || status == PROFILING_STOP, 
      "start current profile status is: ", status, " error!");
  int deviceIndex = 0;
  aclError ret = aclrtGetDevice(&deviceIndex);
  if(ret){
    NPU_LOGE("npu profiling aclrtGetDevice fail, error code: %d", ret);
    C10_NPU_SHOW_ERR_MSG();
    (void)c10::npu::acl::AclProfilingFinalize();
    status = PROFILING_FINALIZE;
    return;
  }
  const uint32_t deviceNum = 1;
  uint32_t deviceIdList[deviceNum] = {deviceIndex};
  profCfg = c10::npu::acl::AclProfilingCreateConfig(
      deviceIdList,
      deviceNum,
      (aclprofAicoreMetrics)aicore_metrics,
      nullptr,
      npu_event);
  if (profCfg == nullptr) {
    NPU_LOGE("npu profiling profiling_create_config fail, error  profCfg is null.");
    C10_NPU_SHOW_ERR_MSG();
    (void)c10::npu::acl::AclProfilingFinalize();
    status = PROFILING_FINALIZE;
    return;
  }
  c10::npu::npuSynchronizeDevice();
  ret = c10::npu::acl::AclProfilingStart(profCfg);
  if(ret && (ret != ACL_ERROR_PROF_ALREADY_RUN)){
    NPU_LOGE("npu profiling AclProfStart fail, error code: %d", ret);
    C10_NPU_SHOW_ERR_MSG();
  }
  status = PROFILING_START;
}

void NpuProfiling::Stop() {
  TORCH_CHECK(status == PROFILING_START, "stop current profile status is: ", status, " error!");
  c10::npu::npuSynchronizeDevice();
  auto ret = c10::npu::acl::AclProfilingStop(profCfg);
  if (ret && (ret != ACL_ERROR_PROF_ALREADY_RUN)) {
    NPU_LOGE("npu AclProfStop fail, error code: %d", ret);
    C10_NPU_SHOW_ERR_MSG();
  }
  status = PROFILING_STOP;
}

void NpuProfiling::Finalize() {
  if (profCfg != nullptr) {
    if (status != PROFILING_STOP) {
      NPU_LOGW("finalize current profile status ( %u ) is not stopped, and call stop now.", status);
      auto ret = c10::npu::acl::AclProfilingStop(profCfg);
      if (ret && (ret != ACL_ERROR_PROF_ALREADY_RUN)) {
        NPU_LOGE("npu AclProfStop fail, error code: %d", ret);
        C10_NPU_SHOW_ERR_MSG();
      }
    }
    auto ret = c10::npu::acl::AclProfilingDestroyConfig(profCfg);
    if (ret && (ret != ACL_ERROR_PROF_ALREADY_RUN)) {
      NPU_LOGE("npu AclProfDestoryConfig fail, error code: %d", ret);
      C10_NPU_SHOW_ERR_MSG();
    }
    profCfg = nullptr;
  }
  auto ret = c10::npu::acl::AclProfilingFinalize();
  if (ret && (ret != ACL_ERROR_PROF_ALREADY_RUN)) {
    NPU_LOGE("npu AclProfFinalize fail, error code: %d", ret);
    C10_NPU_SHOW_ERR_MSG();
  }
  status = PROFILING_FINALIZE;
}


NpuProfilingDispatch& NpuProfilingDispatch::Instance(){
  static NpuProfilingDispatch npuProfilingDispatch;
  return npuProfilingDispatch;
}

void NpuProfilingDispatch::init(){
    profStepInfo = c10::npu::acl::init_stepinfo();
}

void NpuProfilingDispatch::start(){
  this->init();
  auto stream = c10::npu::getCurrentNPUStream();
  auto ret = c10::npu::acl::start_deliver_op(
      profStepInfo,
      aclprofStepTag::ACL_STEP_START,
      stream);
  if(ret != ACL_ERROR_NONE){
      NPU_LOGE("npu profiling start fail, error code: %d", ret);
      C10_NPU_SHOW_ERR_MSG();
  }
}

void NpuProfilingDispatch::stop(){
  auto stream = c10::npu::getCurrentNPUStream();
  auto ret = c10::npu::acl::stop_deliver_op(
      profStepInfo,
      aclprofStepTag::ACL_STEP_END,
      stream);
  if(ret != ACL_ERROR_NONE){
      NPU_LOGE("npu profiling stop fail, error code: %d", ret);
      C10_NPU_SHOW_ERR_MSG();
  }
  this->destroy();
}

void NpuProfilingDispatch::destroy(){
  if(profStepInfo != nullptr){
    c10::npu::acl::destroy_stepinfo(profStepInfo);
  }
}

}
}
