"""
# -*- coding: utf-8 -*-
linting.py:

Use the pylint module to run on arbitrary code or files and get a list of warnings etc.
"""
import tempfile

from PyQt5.QtWidgets import (QDialog, QDialogButtonBox, QVBoxLayout, QLabel)
from pylint import epylint as lint


def run_linter_on_code(code: str = None, filename: str = None):
    """
    Run linter on arbitrary code. This saves it to a temp file so we can call pylinter.

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

    # get warnings from pylint object
    all_results = []

    for line in pylint_stdout.read().split("\n"):
        parts_of_line = line.strip().split(":")
        if len(parts_of_line) != 3:
            # make sure this is correct first
            continue

        error = parts_of_line[2].strip()
        kind = error.split(" ")[0]

        error = error[len(kind)+1:]
        error_code_type = error[:error.index(")")+1]
        message = error[len(error_code_type)+1:]

        all_results.append({
            'filename': parts_of_line[0],
            'line_number': int(parts_of_line[1].strip()),
            'kind': kind,
            'lint_code': error_code_type,
            'message': message
        })

    return all_results


class LintDialog(QDialog):
    def __init__(self, parent, lint_results, filename):
        super().__init__(parent)

        self.setWindowTitle(f"Linting results on {filename}")

        q_btn = QDialogButtonBox.Ok

        self.buttonBox = QDialogButtonBox(q_btn)
        self.buttonBox.accepted.connect(self.accept)

        current_lint_format = "\n".join([f"Line {lint_line['line_number']}: {lint_line['message']}"
                                         for lint_line in lint_results])

        self.layout = QVBoxLayout()
        message = QLabel(current_lint_format)
        self.layout.addWidget(message)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)


if __name__ == '__main__':
    run_linter_on_code(filename="./syntax.py")
