# Generates C++ autograd functions for the derivatives of ATen operations
#
# This writes two files:
#  python_functions.h/cpp: Python bindings for subclasses of autograd::Node

from typing import Dict
from torchgen.api.autograd import DifferentiabilityInfo
from torchgen.model import FunctionSchema
from torchgen.utils import FileManager
from torchgen.gen import FileManager
from torchgen.packaged.autograd.gen_autograd_functions import (
    process_function,
    get_infos_with_derivatives_list,
    PY_FUNCTION_DEFINITION,
    PY_FUNCTION_PROPS_AND_GETTERS
)


def gen_autograd_functions_python(
    out: str,
    differentiability_infos: Dict[FunctionSchema, Dict[str, DifferentiabilityInfo]],
    template_path: str,
) -> None:
    fm = FileManager(install_dir=out, template_dir=template_path, dry_run=False)
    num_shards = 2
    fm.write(
        "python_functions.h",
        lambda: {
            "generated_comment":
            f"@ generated from {fm.template_dir_for_comments()}/python_functions.h",
            "shard_forward_declare": [
                f"void initialize_autogenerated_functions_{i}(PyObject* module);"
                for i in range(num_shards)
            ],
            "shard_call": [
                f"initialize_autogenerated_functions_{i}(module);"
                for i in range(num_shards)
            ],
        },
    )

    # get a 1D list of diffinfos, we do not need them to be per FunctionSchema/DispatchKey here
    # infos with the diff dispatchkeys but the same name will still be in the same shard.
    infos = get_infos_with_derivatives_list(differentiability_infos)
    fm.write_sharded(
        "python_functions.cpp",
        infos,
        key_fn=lambda info: info.name,
        base_env={
            "generated_comment": 
            f"@ generated from {fm.template_dir_for_comments()}/python_functions.cpp",
        },
        env_callable=lambda info: {
            "py_function_initializers": [
                process_function(info, PY_FUNCTION_DEFINITION)
            ],
            "py_function_props_and_getters": [
                process_function(info, PY_FUNCTION_PROPS_AND_GETTERS)
            ],
        },
        num_shards=num_shards,
        sharded_keys={"py_function_initializers", "py_function_props_and_getters"},
    )