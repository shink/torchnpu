#ifndef __TORCH_NPU_MSTXINTERFACE__
#define __TORCH_NPU_MSTXINTERFACE__

#include <third_party/mstx/ms_tools_ext.h>

namespace at_npu {
namespace native {

int MstxRangeStartA(const char* message, aclrtStream stream, int ptRangeId);

void MstxRangeEnd(int ptRangeId);

bool IsRangeIdWithStream(int ptRangeId);
}
}

#endif