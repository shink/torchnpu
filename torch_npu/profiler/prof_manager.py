import os
import socket
from datetime import datetime

from ..utils.path_manager import PathManager
from .analysis.prof_common_func.constant import Constant
from .analysis.prof_common_func.singleton import Singleton
from .analysis.prof_common_func.constant import print_warn_msg
from .analysis.prof_common_func.path_manager import ProfilerPathManager


@Singleton
class ProfManager:

    def __init__(self):
        self._prof_path = None
        self._worker_name = None
        self._dir_path = None
        self.is_prof_inited = False

    def init(self, worker_name: str = None, dir_name: str = None) -> None:
        valid_wk_name = worker_name and isinstance(worker_name, str)
        valid_wk_len = isinstance(worker_name, str) and len(worker_name) < Constant.MAX_WORKER_NAME_LENGTH
        if (valid_wk_name and valid_wk_len) or worker_name is None:
            self._worker_name = worker_name
        else:
            print_warn_msg("Invalid parameter worker_name, reset it to default.")
            self._worker_name = None

        valid_dir_name = dir_name and isinstance(dir_name, str)
        if valid_dir_name:
            dir_path = ProfilerPathManager.get_realpath(dir_name)
            PathManager.check_input_directory_path(dir_path)
            self._dir_path = dir_name
        elif dir_name is None:
            self._dir_path = dir_name  
        else:
            print_warn_msg("Invalid parameter dir_name, reset it to default.")
            self._dir_path = None

    def create_prof_dir(self):
        if not self._dir_path:
            dir_path = os.getenv(Constant.ASCEND_WORK_PATH, default=None)
            dir_path = os.path.join(os.path.abspath(dir_path), Constant.PROFILING_WORK_PATH) if dir_path else os.getcwd()
        else:
            dir_path = self._dir_path
        if not self._worker_name:
            worker_name = "{}_{}".format(socket.gethostname(), str(os.getpid()))
        else:
            worker_name = self._worker_name
        span_name = "{}_{}_ascend_pt".format(worker_name, datetime.utcnow().strftime("%Y%m%d%H%M%S%f")[:-3])
        self._prof_path = os.path.join(dir_path, span_name)
        PathManager.check_input_directory_path(self._prof_path)
        PathManager.make_dir_safety(self._prof_path)
        PathManager.check_directory_path_writeable(self._prof_path)
        self.is_prof_inited = True

    def get_prof_dir(self) -> str:
        return self._prof_path
