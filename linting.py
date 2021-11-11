"""
# -*- coding: utf-8 -*-
linting.py:

Use the pylint module to run on arbitrary code or files and get a list of warnings etc.
"""
import tempfile
import time
import os

from json import loads, dumps
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QDialog, QPushButton, QVBoxLayout, QLabel
from pylint import epylint as lint


class LintingWorker(QObject):
    finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__()
        self.application = parent
        self.linting_results = None
        self.linting_debug_messages = False

        self.linting_exclusions = []
        if os.path.exists("linting_exclusions.json"):
            self.linting_exclusions = loads(open("linting_exclusions.json", 'r').read()).get('linting_exclusions', [])

    def save_exclusions(self):
        with open("linting_exclusions.json", 'w') as f:
            json_exclusions = dumps({"linting_exclusions": self.linting_exclusions}, indent=2)
            f.write(json_exclusions)

    def add_exclusion(self, exclusion_code: str):
        if exclusion_code not in self.linting_exclusions:
            self.linting_exclusions.append(exclusion_code)

    def remove_exclusion(self, exclusion_code: str):
        if exclusion_code in self.linting_exclusions:
            self.linting_exclusions.remove(exclusion_code)

    def run_linter_on_code(self, code: str = None, filename: str = None):
        """
        Run linter on arbitrary code. This saves it to a temp file so we can call python linter.

        :param code: The arbitrary code to lint.
        :param filename: Run the linter on a file instead.
        """
        assert (code is None) ^ (filename is None), \
            "Cannot have both code and filename specified nor neither."
        if code is not None:
            filename = tempfile.mktemp(suffix='.py')
            with open(filename, 'w', encoding="utf-8") as file_obj:
                file_obj.write(code)

        (pylint_stdout, pylint_stderr) = lint.py_run(filename, return_std=True)

        # get warnings from pylint object_
        all_results = []

        for line in pylint_stdout.read().split("\n"):
            parts_of_line = line.strip().split(":")
            if len(parts_of_line) != 3:
                # make sure this is correct first
                continue

            error = parts_of_line[2].strip()
            kind = error.split(" ")[0]

            error = error[len(kind) + 1:]
            error_code_type = error[:error.index(")") + 1]
            message = error[len(error_code_type) + 1:]

            linting_code = error_code_type.replace("(", "").split(", ")[0]

            if linting_code in self.linting_exclusions:
                continue

            all_results.append({
                'filename': parts_of_line[0],
                'line_number': int(parts_of_line[1].strip()),
                'kind': kind,
                'lint_code': error_code_type,
                'message': message
            })

        self.linting_results = all_results
        try:
            self.finished.emit()
        except RuntimeError as e:
            if self.linting_debug_messages:
                print("Runtime error", str(e))

    def run(self):
        while True:
            if self.application.current_project_root is None:
                if self.linting_debug_messages:
                    print("no project: ", time.time())
                continue

            current_file = self.application.file_tabs.current_file_selected

            if current_file is None:
                if self.linting_debug_messages:
                    print("no file: ", time.time())
                continue

            if not current_file.endswith(".py"):
                # not viewing a python file
                self.application.code_window.linting_results = []  # remove linting results.
                self.application.code_window.line_number_area_linting_tooltips = dict()
                if self.linting_debug_messages:
                    print("non-python file: ", time.time())
                continue

            if self.linting_debug_messages:
                print("Run iter at time: ", time.time())

            try:
                self.run_linter_on_code(code=self.application.code_window.toPlainText())
            except RuntimeError:
                if self.linting_debug_messages:
                    print("Runtime error")
                break  # maybe don't use break, but if code editor was deleted, then we should be done


class LintingHelper(QDialog):
    """ Reference for certain codes and auto-fixing them with one click, or adding them to the exclusion list """
    def __init__(self, parent=None, linting_worker: LintingWorker = None, linting_message=None, linting_code=None):
        super().__init__(parent)

        assert linting_worker is not None
        assert linting_message is not None
        assert linting_code is not None

        self.linting_worker = linting_worker

        self.setWindowTitle("PyLint Helper")

        self.layout = QVBoxLayout()
        message = QLabel("Lint Result: " + linting_message)

        def ignore_lint_result_action():
            self.linting_worker.add_exclusion(linting_code)
            self.linting_worker.save_exclusions()
            self.accept()

        ignore_lint_result = QPushButton("Ignore this type of warning", self)
        ignore_lint_result.clicked.connect(ignore_lint_result_action)

        def exit_dialog_action():
            self.reject()

        exit_dialog = QPushButton("Close", self)
        exit_dialog.clicked.connect(exit_dialog_action)

        self.layout.addWidget(message)
        self.layout.addWidget(ignore_lint_result)
        self.layout.addWidget(exit_dialog)
        self.setLayout(self.layout)

        self.response = None