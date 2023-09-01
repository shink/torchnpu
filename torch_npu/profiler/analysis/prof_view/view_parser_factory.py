import datetime
import os
import threading
import time

from ..prof_common_func.constant import Constant
from ..prof_common_func.file_manager import FileManager
from ..prof_common_func.global_var import GlobalVar
from ..prof_common_func.path_manager import PathManager
from ..prof_config.view_parser_config import ViewParserConfig
from ..prof_parse.cann_file_parser import CANNFileParser
from ..level_config import LevelConfig


class ViewParserFactory:
    @classmethod
    def create_view_parser_and_run(cls, profiler_path: str, analysis_type: str, output_path: str):
        print(f"[INFO] [{os.getpid()}] profiler.py: Start parsing profiling data.")
        cann_file_parser = CANNFileParser(profiler_path)
        cann_file_parser.check_prof_data_size()
        start_time = datetime.datetime.now()
        CANNFileParser(profiler_path).export_cann_profiling()
        end_time = datetime.datetime.now()
        print(
            f"[INFO] [{os.getpid()}] profiler.py: CANN profiling data parsed in a total time of {end_time - start_time}")
        GlobalVar.init(profiler_path)
        LevelConfig().load_info(profiler_path)
        if analysis_type == Constant.TENSORBOARD_TRACE_HANDLER:
            output_path = os.path.join(profiler_path, Constant.OUTPUT_DIR)
            FileManager.remove_and_make_output_dir(output_path)
        for parser in ViewParserConfig.CONFIG_DICT.get(analysis_type):
            parser(profiler_path).generate_view(output_path)
        end_time = datetime.datetime.now()
        print(f"[INFO] [{os.getpid()}] profiler.py: All profiling data parsed in a total time of {end_time - start_time}")
