import os.path
import queue
import shutil
import subprocess
from pathlib import Path
from threading import Thread

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMainWindow, QTextEdit

from je_editor.utils.exception.exception_tags import compiler_not_found_error
from je_editor.utils.exception.exception_tags import file_not_fond_error
from je_editor.utils.exception.exceptions import JEditorExecException


class ExecManager(object):

    def __init__(
            self,
            main_window=None,
            program_language="python",
            program_encoding="utf-8",
            program_buffer=10240000,
    ):
        """
        :param main_window: tkinter main window
        :param program_language: which program language
        :param program_encoding: which encoding
        """
        self.read_program_error_output_from_thread = None
        self.read_program_output_from_thread = None
        self.main_window: QMainWindow = main_window
        self.code_result: [QTextEdit, None] = None
        self.timer: [QTimer, None] = None
        self.still_run_program = True
        self.process = None
        self.run_output_queue = queue.Queue()
        self.run_error_queue = queue.Queue()
        self.program_language = program_language
        self.program_encoding = program_encoding
        self.program_buffer = program_buffer

    def later_init(self):
        if self.main_window is not None:
            self.code_result: QTextEdit = self.main_window.code_result
            self.timer = QTimer(self.main_window)
        else:
            # TODO Exception
            raise Exception

    def exec_code(self, exec_file_name):
        """
        :param exec_file_name: string file will open to run
        :return: if error return result and True else return result and False
        """
        try:
            self.exit_program()
            self.code_result.setPlainText("")
            reformat_os_file_path = os.path.abspath(exec_file_name)
            # detect file is exist
            try:
                if not Path(exec_file_name).exists():
                    raise JEditorExecException(file_not_fond_error)
            except OSError as error:
                raise JEditorExecException(error)
            compiler_path = shutil.which(self.program_language)
            if compiler_path is None and self.program_language == "python":
                compiler_path = shutil.which("python3")
            elif compiler_path is None and self.program_language == "python3":
                compiler_path = shutil.which("python")
            if compiler_path is None:
                raise JEditorExecException(compiler_not_found_error)
            exec_file = reformat_os_file_path
            # run program
            execute_program_list = [compiler_path, exec_file]
            self.process = subprocess.Popen(
                execute_program_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False
            )
            self.still_run_program = True
            # program output message queue thread
            self.read_program_output_from_thread = Thread(
                target=self.read_program_output_from_process,
                daemon=True
            ).start()
            # program error message queue thread
            self.read_program_error_output_from_thread = Thread(
                target=self.read_program_error_output_from_process,
                daemon=True
            ).start()
            # show which file execute
            self.code_result.append(compiler_path + " " + reformat_os_file_path)
            # start tkinter_ui update
            # start timer
            self.timer = QTimer(self.main_window)
            self.timer.setInterval(1)
            self.timer.timeout.connect(self.pull_text)
            self.timer.start()
        except Exception as error:
            self.code_result.setTextColor(self.main_window.red_color)
            self.code_result.append(str(error))
            self.code_result.setTextColor(self.main_window.black_color)

    # tkinter_ui update method
    def pull_text(self):
        try:
            self.code_result.setTextColor(self.main_window.red_color)
            if not self.run_error_queue.empty():
                error_message = self.run_error_queue.get_nowait()
                error_message = str(error_message).strip()
                if error_message:
                    self.code_result.append(error_message)
            self.code_result.setTextColor(self.main_window.black_color)
            if not self.run_output_queue.empty():
                output_message = self.run_output_queue.get_nowait()
                output_message = str(output_message).strip()
                if output_message:
                    self.code_result.append(output_message)
        except queue.Empty:
            pass
        if self.process.returncode == 0:
            self.exit_program()
        elif self.process.returncode is not None:
            self.exit_program()
            self.timer.stop()
        if self.still_run_program:
            # poll return code
            self.process.poll()

    # exit program change run flag to false and clean read thread and queue and process
    def exit_program(self):
        self.still_run_program = False
        if self.read_program_output_from_thread is not None:
            self.read_program_output_from_thread = None
        if self.read_program_error_output_from_thread is not None:
            self.read_program_error_output_from_thread = None
        self.print_and_clear_queue()
        if self.process is not None:
            self.process.terminate()

    def print_and_clear_queue(self):
        try:
            for std_output in iter(self.run_output_queue.get_nowait, None):
                std_output = str(std_output).strip()
                if std_output:
                    self.code_result.append(std_output)
            self.code_result.setTextColor(self.main_window.red_color)
            for std_err in iter(self.run_error_queue.get_nowait, None):
                std_err = str(std_err).strip()
                if std_err:
                    self.code_result.append(std_err)
            self.code_result.setTextColor(self.main_window.black_color)
        except queue.Empty:
            pass
        self.run_output_queue = queue.Queue()
        self.run_error_queue = queue.Queue()

    def read_program_output_from_process(self):
        while self.still_run_program:
            program_output_data = self.process.stdout.raw.read(self.program_buffer).decode(self.program_encoding)
            self.run_output_queue.put_nowait(program_output_data)

    def read_program_error_output_from_process(self):
        while self.still_run_program:
            program_error_output_data = self.process.stderr.raw.read(self.program_buffer).decode(self.program_encoding)
            self.run_error_queue.put_nowait(program_error_output_data)


exec_manage = ExecManager()
