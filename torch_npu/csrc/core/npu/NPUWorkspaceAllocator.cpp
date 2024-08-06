#include <memory>
#include <vector>

#include <c10/util/flat_hash_map.h>
#include <c10/util/irange.h>

#include "third_party/acl/inc/acl/acl_base.h"
#include "third_party/acl/inc/acl/acl_rt.h"
#include "torch_npu/csrc/core/npu/interface/AsyncTaskQueueInterface.h"
#include "torch_npu/csrc/core/npu/register/OptionsManager.h"
#include "torch_npu/csrc/core/npu/NPUFunctions.h"
#include "torch_npu/csrc/core/npu/NPUCachingAllocator.h"
#include "torch_npu/csrc/core/npu/NPUWorkspaceAllocator.h"

namespace c10_npu {
namespace NPUWorkspaceAllocator {

namespace {
constexpr size_t kRoundLarge = 2097152; // Alloceted memory is aligned to 2 MiB.
} // namespace

struct WorkspaceBlock {
    void* data_ptr;
    size_t size;
    WorkspaceBlock() : data_ptr(nullptr), size(0) {}
};

class DeviceWorkspaceAllocator {
public:
    DeviceWorkspaceAllocator()
    {
        blocks.clear();
    }

    void* malloc(size_t size, aclrtStream stream)
    {
        size_t alloc_size = size + 32;

        auto it = blocks.find(stream);
        if (it == blocks.end()) {
            blocks.emplace(stream, new WorkspaceBlock());
        }

        WorkspaceBlock* block = blocks[stream];
        if (block->size < alloc_size) {
            if (block->data_ptr != nullptr) {
                ASCEND_LOGI("NPUWorkspaceAllocator free by aclrtFree: size=%zu", block->size);
                NPU_CHECK_ERROR(aclrtSynchronizeDevice());
                NPU_CHECK_ERROR(aclrtFree(block->data_ptr));
            }

            block->size = kRoundLarge * ((alloc_size + kRoundLarge - 1) / kRoundLarge);

            TORCH_CHECK(
                alloc_size <= block->size,
                "The allocated memory ", block->size, " bytes is smaller than the required memory ", alloc_size, " bytes.",
                PTA_ERROR(ErrCode::MEMORY));

            aclError err = c10_npu::acl::AclrtMallocAlign32(
                &block->data_ptr, block->size, aclrtMemMallocPolicy::ACL_MEM_MALLOC_HUGE_ONLY);
            if (err != ACL_ERROR_NONE) {
                return nullptr;
            }

            ASCEND_LOGD("NPUWorkspaceAllocator malloc by AclrtMallocAlign32: size=%zu", block->size);
        }
        return block->data_ptr;
    }

    // return to the system allocator
    void empty_cache(bool check_error)
    {
        auto acl_ret = aclrtSynchronizeDevice();
        if (check_error) {
            NPU_CHECK_ERROR(acl_ret, "aclrtSynchronizeDevice");
        } else {
            NPU_CHECK_WARN(acl_ret);
        }

        for (const auto& block_pair : blocks) {
            if (block_pair.second->data_ptr != nullptr) {
                ASCEND_LOGI("NPUWorkspaceAllocator free by aclrtFree: size=%zu", block_pair.second->size);
                NPU_CHECK_ERROR(aclrtFree(block_pair.second->data_ptr));
            }
            delete block_pair.second;
        }

        blocks.clear();
    }

private:
    ska::flat_hash_map<aclrtStream, WorkspaceBlock*> blocks;
}; // class DeviceworkspaceAllocator

static void uncached_delete(void* ptr)
{
    NPU_CHECK_ERROR(aclrtSynchronizeDevice());
    NPU_CHECK_ERROR(aclrtFree(ptr));
}

// Now we will reuse the allocated memory and not release immediately until
// memory is insufficient for NpuCachingAllocator or NpuWorkspaceAllocator.
// Then both will empty cache and the large memory will be released.
static void local_raw_delete(void* ptr)
{
}

class NpuWorkspaceAllocator : public c10::Allocator {
public:
    std::vector<std::unique_ptr<DeviceWorkspaceAllocator>> device_allocator;

    void init(int device_count)
    {
        int size = static_cast<int>(device_allocator.size());
        if (size < device_count) {
            device_allocator.resize(device_count);
            for (const auto i : c10::irange(size, device_count)) {
                device_allocator[i] = std::make_unique<DeviceWorkspaceAllocator>();
            }
        }
    }

    void malloc(void** new_ptr, int device, size_t size, aclrtStream stream)
    {
        *new_ptr = static_cast<void*>(device_allocator[device]->malloc(size, stream));

        // Free all cached blocks and try again.
        if ((*new_ptr) == nullptr) {
            empty_cache(true);
            c10_npu::NPUCachingAllocator::emptyCache(true);
            *new_ptr = static_cast<void*>(device_allocator[device]->malloc(size, stream));
        }

        if ((*new_ptr) == nullptr) {
            size_t device_free;
            size_t device_total;
            NPU_CHECK_ERROR(aclrtGetMemInfo(ACL_HBM_MEM, &device_free, &device_total));

            TORCH_CHECK(false,
                "NPU out of memory. NPUWorkspaceAllocator tried to allocate ",
                format_size(size),
                "(NPU ", device, "; ",
                format_size(device_total),
                " total capacity; ",
                format_size(device_free),
                " free)",
                PTA_ERROR(ErrCode::MEMORY));
        }
    }

    void empty_cache(bool check_error)
    {
        int count = static_cast<int>(device_allocator.size());
        for (int i = 0; i < count; i++) {
            device_allocator[i]->empty_cache(check_error);
        }
    }

    c10::DataPtr allocate(size_t size) override
    {
        int device = 0;
        NPU_CHECK_ERROR(c10_npu::GetDevice(&device));
        void* dev_ptr = nullptr;
        void (*delete_func)(void*) = &local_raw_delete;
        return {dev_ptr, dev_ptr, delete_func, c10::Device(c10::DeviceType::PrivateUse1, device)};
    }

    c10::DataPtr allocate_with_stream(size_t size, aclrtStream stream)
    {
        int device = 0;
        NPU_CHECK_ERROR(c10_npu::GetDevice(&device));
        void* dev_ptr = nullptr;
        void (*delete_func)(void*) = &local_raw_delete;

        if (c10_npu::option::OptionsManager::CheckForceUncached()) {
            delete_func = &uncached_delete;
            if (size != 0) {
                size_t alloc_size = size + 32;
                NPU_CHECK_ERROR(
                    c10_npu::acl::AclrtMallocAlign32(&dev_ptr, alloc_size, aclrtMemMallocPolicy::ACL_MEM_MALLOC_HUGE_ONLY));
            }
        } else {
            if (size != 0) {
                this->malloc(&dev_ptr, device, size, stream);
            }
        }
        return {dev_ptr, dev_ptr, delete_func, c10::Device(c10::DeviceType::PrivateUse1, device)};
    }

    c10::DeleterFnPtr raw_deleter() const override
    {
        if (c10_npu::option::OptionsManager::CheckForceUncached()) {
            return &uncached_delete;
        } else {
            return &local_raw_delete;
        }
    }

    // Note [COW/lazy_clone is not supported yet]
    void copy_data(void* dest, const void* src, std::size_t count) const final
    {
        default_copy_data(dest, src, count);
    }
}; // class NpuWorkspaceAllocator

NpuWorkspaceAllocator workspace_allocator;

c10::Allocator* get()
{
    return &workspace_allocator;
}

void init()
{
    uint32_t device_count = 0;
    NPU_CHECK_ERROR(aclrtGetDeviceCount(&device_count));
    workspace_allocator.init(device_count);
}

c10::DataPtr malloc_with_stream(size_t size, aclrtStream stream)
{
    return workspace_allocator.allocate_with_stream(size, stream);
}

void emptyCache(bool check_error)
{
    workspace_allocator.empty_cache(check_error);
}

} // namespace NPUWorkspaceAllocator
} // namespace c10_npu