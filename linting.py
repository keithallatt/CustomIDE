# -*- coding: utf-8 -*-
"""
linting.py: Use the pylint module to run on arbitrary code or files and get a list of warnings etc.
"""
import logging
import tempfile
import time
import os
import subprocess

from json import loads, dumps
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QDialog, QPushButton, QVBoxLayout, QLabel, QMainWindow
from pylint import epylint as lint


class LintingWorker(QObject):
    """
    Worker object to work continuously linting the current file.
    Continuously runs pylint on the currently opened file to
    provide the IDE with linting options.
    """
    finished = pyqtSignal()

    def __init__(self, parent: QMainWindow = None) -> None:
        """
        Create the linting object with a parent object,
        but not linked as parent so this can be moved
        to a new thread.
        """
        super().__init__()
        # self.pylint_installed_in_venv = False
        self.application = parent
        self.linting_results = None
        self.was_fatal = False
        self.linting_debug_messages = False
        self.linting_sleep = 0
        self.linting_exclusions = []
        self.temp_files = []
        if os.path.exists("linting_exclusions.json"):
            self.linting_exclusions = loads(open("linting_exclusions.json", 'r').read()).get('linting_exclusions', [])
            print(self.linting_exclusions)

    def reset_exclusions(self) -> None:
        """ Reset the list of linting exclusions  """
        self.linting_exclusions = []
        with open("linting_exclusions.json", 'w') as f:
            json_exclusions = dumps({"linting_exclusions": []}, indent=2)
            f.write(json_exclusions)

    def save_exclusions(self) -> None:
        """ Save the current selection of linting exclusions to file. """
        with open("linting_exclusions.json", 'w') as f:
            json_exclusions = dumps({"linting_exclusions": self.linting_exclusions}, indent=2)
            f.write(json_exclusions)

    def add_exclusion(self, exclusion_code: str) -> None:
        """ Add a linting code to the current selection of linting exclusions. """
        if exclusion_code not in self.linting_exclusions:
            self.linting_exclusions.append(exclusion_code)

    def remove_exclusion(self, exclusion_code: str) -> None:
        """ Remove a linting code to the current selection of linting exclusions. """
        if exclusion_code in self.linting_exclusions:
            self.linting_exclusions.remove(exclusion_code)

    def run_linter_on_code(self, code: str = None, filename: str = None) -> None:
        """
        Run linter on arbitrary code. This saves it to a temp file so we can call python linter,
        if no file is specified.

        :param code: The arbitrary code to lint.
        :param filename: Run the linter on a file instead.
        """
        assert (code is None) ^ (filename is None), \
            "Cannot have both code and filename specified nor neither."
        remove_after = False
        if code is not None:
            remove_after = True
            filename = tempfile.mkstemp(prefix="linting_", suffix='.py')[1]
            self.temp_files.append(filename)
            with open(filename, 'w', encoding="utf-8") as file_obj:
                file_obj.write(code)

        # look for venv
        venv_file_path = self.application.current_project_root_str
        if not venv_file_path.endswith(os.sep):
            venv_file_path += os.sep

        venv_file_path += os.sep.join(['venv', 'bin'])

        if os.path.exists(venv_file_path):
            python_bin = venv_file_path

            # if errors start popping up, uncomment.

            # pip_bin = os.sep.join([python_bin, 'pip3'])
            pylint_bin = os.sep.join([python_bin, 'pylint'])

            # installs pylint to venv (necessary for linting, not best practices though)
            # subprocess.call([pip_bin, '-q', '-q', 'install', 'pylint'])

            command = [pylint_bin, filename, "-f", "json"]

            proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            (pylint_stdout, pylint_stderr) = proc.communicate()

            stdout = pylint_stdout.decode('utf-8')
            stderr = pylint_stderr.decode('utf-8')

            if stderr.strip():
                print(stderr)

            self.linting_results = loads(stdout)
        else:
            (pylint_stdout, pylint_stderr) = lint.py_run(f"{filename} --output-format='json'",
                                                         return_std=True)
            stdout = pylint_stdout.read()

            # set the results for the code editor to use for line highlights
            self.linting_results = loads(stdout)

        self.linting_results = list(filter(
            lambda x: x['message-id'] not in self.linting_exclusions, self.linting_results))

        fatal_linting = list(filter(
            lambda x: x['message-id'].startswith("F"), self.linting_results))

        self.linting_results = list(filter(
            lambda x: not x['message-id'].startswith("F"), self.linting_results))

        self.was_fatal = False
        if fatal_linting:
            self.was_fatal = True
            for lm in fatal_linting:
                logging.error(f"Fatal Linting Error: {lm.get('message', '')}, {lm.get('message-id', '')}")

        if remove_after:
            if os.path.exists(filename):
                os.remove(filename)
            if filename in self.temp_files:
                self.temp_files.remove(filename)

        # emit a finishing signal
        try:
            if hasattr(self.finished, 'emit'):
                self.finished.emit()
            else:
                logging.error("PyQt Signal Emit not performed (linting.py)")
        except RuntimeError as e:
            if self.linting_debug_messages:
                print("Runtime error", str(e))

    def run(self) -> None:
        """ Continually run the pylint linter on the current file. """

        def clear_linting() -> None:
            """ Clear the linter results and tooltips, so that no stale results remain. """
            # not viewing a python file / no file open / project is closed
            print("clearing in linting.py:run")

            self.application.code_window.linting_results = []  # remove linting results.
            self.application.code_window.line_number_area_linting_tooltips = dict()
            if self.application.highlighter:
                self.application.highlighter.linting_results = []

        while True:
            # try sleeping first, if we run into a guard statement,
            # then we want to sleep if the sleep amount is specified.
            if self.linting_sleep:
                time.sleep(self.linting_sleep)

            # if no project is open, continue
            if self.application.current_project_root is None:
                if self.linting_debug_messages:
                    print("no project: ", time.time())
                print("clearing in linting.py:run: current project root is none")
                clear_linting()
                continue

            current_file = self.application.file_tabs.current_file_selected

            # if a project is open, but no files open, also continue
            if current_file is None:
                if self.linting_debug_messages:
                    print("no file: ", time.time())
                print("clearing in linting.py:run: current file is none")
                clear_linting()
                continue

            # if the file isn't a python file, and thus linting results don't matter
            if not current_file.endswith(".py"):
                if self.linting_debug_messages:
                    print("non-python file: ", time.time())
                print("clearing in linting.py:run: non python file")
                clear_linting()
                continue

            if self.linting_debug_messages:
                print("Run iter at time: ", time.time())

            try:
                # run the linter, may run into runtime error around the time the application closes
                # but in that case, just stop linting.
                self.run_linter_on_code(code=self.application.code_window.toPlainText())
            except RuntimeError:
                if self.linting_debug_messages:
                    print("Runtime error")
                # maybe don't use break, but if code editor was deleted, then we should be done
                break


class LintingHelper(QDialog):
    """ Reference for certain codes and auto-fixing them with one click, or adding them to the exclusion list """
    def __init__(self, parent: QMainWindow = None, linting_worker: LintingWorker = None,
                 linting_message: str = None, linting_code: str = None) -> None:
        super().__init__(parent)

        assert linting_worker is not None
        assert linting_message is not None
        assert linting_code is not None

        self.linting_worker = linting_worker

        self.setWindowTitle("PyLint Helper")

        self.layout = QVBoxLayout()
        message = QLabel("Lint Result: " + linting_message)

        def ignore_lint_result_action() -> None:
            """ Action when the 'Ignore this type of warning' button is pushed"""
            self.linting_worker.add_exclusion(linting_code)
            self.linting_worker.save_exclusions()
            self.accept()

        ignore_lint_result = QPushButton("Ignore this type of warning", self)
        ignore_lint_result.clicked.connect(ignore_lint_result_action)

        def exit_dialog_action() -> None:
            """ Action when the 'Close' button is pushed """
            self.reject()

        exit_dialog = QPushButton("Close", self)
        exit_dialog.clicked.connect(exit_dialog_action)

        self.layout.addWidget(message)
        self.layout.addWidget(ignore_lint_result)
        self.layout.addWidget(exit_dialog)
        self.setLayout(self.layout)

        self.response = None
