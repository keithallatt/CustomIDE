"""
The main application.

Count lines with:
    cloc . --by-file --exclude-dir=venv,.idea

-- WARNING --
This program is only designed to work on Ubuntu 20.04, as this is a personal project to create a functional IDE.

TODO:
 - additional shortcuts
 - make file handing work with multiple files
 - check if file is saved before closing? maybe?
 - add venv to projects if desired (could be useful, and is recommended practice)

TO DEBUG:
 - add linting to code
"""
import os
import subprocess
import sys
import tempfile
from json import loads

from PyQt5.QtCore import Qt, QDir, QTimer, QModelIndex
from PyQt5.QtGui import QFont, QKeySequence, QFontInfo
from PyQt5.QtWidgets import (QApplication, QGridLayout, QWidget, QPushButton,
                             QShortcut, QFileSystemModel, QTreeView,
                             QColumnView, QFileDialog)

import syntax
from additional_qwidgets import QCodeEditor, RotatedButton
from linting import run_linter_on_code


class Application(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.resize(2200, 1800)
        self.move(200, 100)

        ide_state = loads(open("ide_state.json", 'r').read())
        shortcuts = loads(open("shortcuts.json", 'r').read())
        self.setWindowTitle(ide_state.get("ide_title", "ide"))

        self.python_bin = ide_state.get("python_bin_location", "/usr/bin/python3")

        self.linting_results = []

        # set global style sheet
        self.setStyleSheet(
            "QWidget {"
            f"  background-color: {ide_state['background_window_color']};"
            f"  color: {ide_state['foreground_window_color']};"
            "}"
            ""
            "QToolTip {"
            f"  background-color: {ide_state['background_window_color']};"
            f"  color: {ide_state['foreground_window_color']};"
            "}"
        )

        self.current_opened_file = None
        # background dealt with in QCodeEditor class
        self.code_window = QCodeEditor()  # QPlainTextEdit with Line Numbers and highlighting.

        font_name = ide_state.get('editor_font_family', "Courier New")
        font_size = ide_state.get('editor_font_size', 12)

        backup_font = QFont("Courier New", 12)
        q = QFont(font_name, font_size)
        qfi = QFontInfo(q)
        self.code_window.setFont(q if font_name == qfi.family() else backup_font)

        self.highlighter = syntax.PythonHighlighter(self.code_window.document())

        # SHORTCUTS

        # set Ctrl-Shift-R to be the run shortcut.
        self.run_shortcut = QShortcut(QKeySequence(shortcuts.get("run", "Ctrl+Shift+R")), self)
        self.run_shortcut.activated.connect(self.run_function)

        # set Ctrl-S to be the save shortcut.
        self.save_shortcut = QShortcut(QKeySequence(shortcuts.get("save", "Ctrl+S")), self)
        self.save_shortcut.activated.connect(self.save_file)

        # set Ctrl-W to be the close shortcut.
        self.close_shortcut = QShortcut(QKeySequence(shortcuts.get("close", "Ctrl+W")), self)
        self.close_shortcut.activated.connect(self.close_file)

        # set Ctrl-Shift-O to be the close shortcut.
        self.open_project_shortcut = QShortcut(QKeySequence(shortcuts.get("open_project", "Ctrl+Shift+O")), self)
        self.open_project_shortcut.activated.connect(self.open_project)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.perform_lint)
        # may need to adjust
        # self.timer.start(2000)

        self.hide_files_button = RotatedButton("Hide")
        self.hide_files_button: QPushButton  # gets rid of warning.
        self.hide_files_button.clicked.connect(self.show_hide_files_widget)

        self.button_widget = QWidget()
        button_widget_layout = QGridLayout()
        button_widget_layout.addWidget(self.hide_files_button, 0, 0, 1, 1)
        self.button_widget.setLayout(button_widget_layout)

        self.file_box = QWidget()
        self.model = QFileSystemModel()

        self.model.setRootPath('')
        self.tree = QTreeView()
        # Create the view in the splitter.
        view = QColumnView(self.tree)
        view.doubleClicked.connect(self.open_file)
        # Set the model of the view.
        view.setModel(self.model)
        # Set the root index of the view as the user's home directory.
        proj_dir = ide_state['project_dir']
        proj_dir = os.path.expanduser(proj_dir)

        if not os.path.exists(proj_dir):
            proj_dir = ide_state['default_project_dir']
            proj_dir = os.path.expanduser(proj_dir)

        assert os.path.exists(proj_dir), "Default Project Folder does not exist."

        view.setRootIndex(self.model.index(QDir.cleanPath(proj_dir)))
        self.current_project_root = proj_dir.split(os.sep)

        self.tree.setViewport(view)
        self.tree.setAnimated(False)
        self.tree.setIndentation(20)
        self.tree.setSortingEnabled(True)
        self.tree_view = view
        self.tree.setWindowTitle("Project Files")

        file_box_layout = QGridLayout()
        file_box_layout.addWidget(self.tree, 0, 0, 1, 1)
        file_box_layout.setColumnStretch(0, 1)
        file_box_layout.setRowStretch(0, 1)
        self.file_box.setLayout(file_box_layout)

        layout = QGridLayout()
        layout.addWidget(self.button_widget, 0, 0, 1, 1)
        layout.addWidget(self.file_box, 0, 1, 1, 1)
        layout.addWidget(self.code_window, 0, 2, 1, 1)

        self.file_window_show_column_info = 1, 2

        layout.setColumnStretch(0, 0)  # make button widget small
        layout.setColumnStretch(*self.file_window_show_column_info)  # make file window ok
        layout.setColumnStretch(2, 5)  # make code window larger

        self.grid_layout = layout
        self.setLayout(layout)

        # open up current opened files. (one until further notice)
        current_files = ide_state['current_opened_files']
        files = [
            os.sep.join([*self.current_project_root, current_file]) for current_file in current_files
        ]
        if files:
            self.open_file(files[0])

        # right at the end, grab focus to the code editor
        self.code_window.setFocus()

    def _load_code(self, text):
        self.code_window.setPlainText(text)

    def _get_code(self):
        return self.code_window.getPlainText()

    def open_file(self, filepath: str = None):
        # if used for shortcut
        if filepath is None:
            q_model_indices = self.tree_view.selectedIndexes()
            assert len(q_model_indices) <= 1, "Multiple selected."
            last_index = q_model_indices[-1]

            file_paths = []

            while last_index.data(Qt.DisplayRole) != os.sep:
                file_paths.append(last_index.data(Qt.DisplayRole))
                last_index = last_index.parent()

            file_paths.append("")
            filepath = os.sep.join(file_paths[::-1])

        # for double click
        if type(filepath) == QModelIndex:
            last_index = filepath
            file_paths = []

            while last_index.data(Qt.DisplayRole) != os.sep:
                file_paths.append(last_index.data(Qt.DisplayRole))
                last_index = last_index.parent()

            file_paths.append("")
            filepath = os.sep.join(file_paths[::-1])

        if os.path.isfile(filepath):
            self.code_window.setPlainText(open(filepath, 'r').read())

        self.current_opened_file = filepath

    def open_project(self):
        print("OPEN PROJECT")
        print(self)

    def save_file(self):
        if self.current_opened_file is None:
            # make new file:
            dial = QFileDialog()
            dial.setDirectory(os.sep.join(self.current_project_root))
            dial.setDefaultSuffix("*.py")
            filename, _ = dial.getSaveFileName(self, "Save file", "",
                                               "Python Files (*.py)", options=QFileDialog.DontUseNativeDialog)

            if filename:
                # actually write to the file.
                self.current_opened_file = filename
            else:
                return
        self.perform_lint()
        open(self.current_opened_file, 'w').write(self.code_window.toPlainText())

    def close_file(self):
        self.current_opened_file = None
        self.code_window.setPlainText("")

    def new_file(self):
        pass

    def run_function(self):
        # save file
        if self.current_opened_file is None:
            # need to create file:
            temporary = tempfile.mktemp(suffix='.py')
            open(temporary, 'w').write(self.code_window.toPlainText())
            file_to_run = temporary
        else:
            self.save_file()
            file_to_run = self.current_opened_file

        # call subprocess
        subprocess.call(['gnome-terminal', '--', self.python_bin, '-i', file_to_run])
        pass

    def perform_lint(self):
        if self.current_opened_file is None:
            lint_results = run_linter_on_code(code=self.code_window.toPlainText())
        else:
            lint_results = run_linter_on_code(code=self.code_window.toPlainText())

        self.linting_results = lint_results
        self.code_window.linting_results = lint_results

        # dlg = LintDialog(self, lint_results, 'tempfile' if self.current_opened_file is None
        #                  else self.current_opened_file)
        #
        # dlg.exec()

    def show_hide_files_widget(self):
        if self.file_box.isHidden():
            self.grid_layout.setColumnStretch(*self.file_window_show_column_info)
            self.file_box.show()
            self.hide_files_button.setText("Hide")
        else:
            self.file_box.hide()
            self.grid_layout.setColumnStretch(self.file_window_show_column_info[0], 0)
            self.hide_files_button.setText("Show")

    def __call__(self):
        exit_code = self.app.exec_()

        sys.exit(exit_code)


pt_default = """\"\"\"
default python script
\"\"\"


def arbitrary_function(var):
    \"\"\" arbitrary function \"\"\"
    return var + (var // 2)

if __name__ == "__main__":
    # get arbitrary function evaluated at 3
    print(arbitrary_function(var=3))
"""

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = Application()

    window.show()

    sys.exit(app.exec_())
