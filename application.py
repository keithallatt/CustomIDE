"""
The main application.

Count lines with:
    cloc . --by-file --exclude-dir=venv,.idea

-- WARNING --
This program is only designed to work on Ubuntu 20.04, as this is a personal project to create a functional IDE.

TODO:
 - additional shortcuts
 - check if file is saved before closing? maybe?
 - add venv to projects if desired (could be useful, and is recommended practice)
 - select file to be the designated run file

TO DEBUG:
 - add linting to code
 - tab /shift-tab behaviour
"""
import os
import subprocess
import sys
import tempfile
from json import loads, dumps

from PyQt5.QtCore import Qt, QDir, QTimer, QModelIndex, QEvent
from PyQt5.QtGui import QFont, QKeySequence, QFontInfo, QKeyEvent
from PyQt5.QtWidgets import (QApplication, QGridLayout, QWidget, QPushButton, QShortcut, QFileSystemModel, QTreeView,
                             QColumnView, QFileDialog)

import syntax
from additional_qwidgets import QCodeEditor, RotatedButton, QCodeFileTabs
from linting import run_linter_on_code


class Application(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.resize(2200, 1800)
        self.move(200, 100)

        self.ide_state = loads(open("ide_state.json", 'r').read())
        shortcuts = loads(open("shortcuts.json", 'r').read())
        self.setWindowTitle(self.ide_state.get("ide_title", "ide"))

        self.python_bin = self.ide_state.get("python_bin_location", "/usr/bin/python3")

        self.linting_results = []

        # set global style sheet
        self.setStyleSheet(
            "QWidget {"
            f"  background-color: {self.ide_state['background_window_color']};"
            f"  color: {self.ide_state['foreground_window_color']};"
            "}"
            ""
            "QToolTip {"
            f"  background-color: {self.ide_state['background_window_color']};"
            f"  color: {self.ide_state['foreground_window_color']};"
            "}"
        )

        self.current_opened_files = set()

        # need file tabs.
        self.file_tabs = QCodeFileTabs(self)

        # background dealt with in QCodeEditor class
        self.code_window = QCodeEditor()  # QPlainTextEdit with Line Numbers and highlighting.
        self.code_window.installEventFilter(self)

        font_name = self.ide_state.get('editor_font_family', "Courier New")
        font_size = self.ide_state.get('editor_font_size', 12)

        backup_font = QFont("Courier New", 12)
        q = QFont(font_name, font_size)
        qfi = QFontInfo(q)
        self.code_window.setFont(q if font_name == qfi.family() else backup_font)
        self.highlighter = syntax.PythonHighlighter(self.code_window.document())

        # SHORTCUTS

        # set Ctrl-Shift-R to be the run shortcut.
        self.run_shortcut = QShortcut(QKeySequence(shortcuts.get("run", "Ctrl+Shift+R")), self)
        self.run_shortcut.activated.connect(self.run_function)

        # set Ctrl-N to be the new file shortcut.
        self.new_file_shortcut = QShortcut(QKeySequence(shortcuts.get("new", "Ctrl+N")), self)
        self.new_file_shortcut.activated.connect(self.new_file)

        # set Ctrl-S to be the save shortcut.
        self.save_shortcut = QShortcut(QKeySequence(shortcuts.get("save", "Ctrl+S")), self)
        self.save_shortcut.activated.connect(self.save_file)

        # set Ctrl-W to be the close shortcut.
        self.close_shortcut = QShortcut(QKeySequence(shortcuts.get("close", "Ctrl+W")), self)
        self.close_shortcut.activated.connect(self.close_file)

        # set Ctrl-Shift-O to be the close shortcut.
        self.open_project_shortcut = QShortcut(QKeySequence(shortcuts.get("open_project", "Ctrl+Shift+O")), self)
        self.open_project_shortcut.activated.connect(self.open_project)

        # not currently using, but would like to do something like this in the future
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.perform_lint)

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
        proj_dir = self.ide_state['project_dir']
        proj_dir = os.path.expanduser(proj_dir)

        if not os.path.exists(proj_dir):
            proj_dir = self.ide_state['default_project_dir']
            proj_dir = os.path.expanduser(proj_dir)

        assert os.path.exists(proj_dir), "Default Project Folder does not exist."

        view.setRootIndex(self.model.index(QDir.cleanPath(proj_dir)))
        self.current_project_root = proj_dir.split(os.sep)
        self.current_project_root_str = proj_dir

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
        layout.addWidget(self.button_widget, 0, 0, 2, 1)
        layout.addWidget(self.file_box, 0, 1, 2, 1)
        layout.addWidget(self.file_tabs, 0, 2, 1, 1)
        layout.addWidget(self.code_window, 1, 2, 1, 1)

        self.file_window_show_column_info = 1, 2

        layout.setColumnStretch(0, 0)  # make button widget small
        layout.setColumnStretch(*self.file_window_show_column_info)  # make file window ok
        layout.setColumnStretch(2, 5)  # make code window larger
        layout.setRowStretch(1, 1)

        self.grid_layout = layout
        self.setLayout(layout)

        # open up current opened files. (one until further notice)
        current_files = self.ide_state['current_opened_files']
        files = [
            os.sep.join([self.current_project_root_str, current_file]) for current_file in current_files
        ]
        for f in files:
            self.open_file(f)

        self.file_tabs.setCurrentIndex(self.ide_state['selected_tab'])

        # right at the end, grab focus to the code editor
        self.code_window.setFocus()

    def focusNextPrevChild(self, _: bool) -> bool:
        # should prevent focus switching
        # parameter 'next' renamed to '_' as 'next' shadows a builtin.
        return False

    def eventFilter(self, q_object, event):
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Tab and event.modifiers() == Qt.ControlModifier:
                # for tab / ctrl tab
                self.file_tabs.next_tab()
                return True

            if event.key() == Qt.Key_Backtab and event.modifiers() == Qt.ControlModifier | Qt.ShiftModifier:
                # for ctrl shift tab
                self.file_tabs.previous_tab()
                return True

        return QWidget.eventFilter(self, q_object, event)

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

        root_full = os.sep.join(self.current_project_root)
        assert filepath.startswith(root_full), "Opening non-project file."

        filename = filepath[len(root_full)+1:]

        self.file_tabs.open_tab(filename)
        self.current_opened_files.add(filepath)
        self.code_window.setEnabled(True)

    def open_project(self):
        print("OPEN PROJECT")
        print(self)

    def save_file(self):
        if not self.current_opened_files:
            return

        file_path_to_save = self.current_project_root_str, self.file_tabs.current_file_selected
        file_path_to_save = os.sep.join(file_path_to_save)
        open(file_path_to_save, 'w').write(self.code_window.toPlainText())

    def close_file(self):
        next_selected, old_name = self.file_tabs.close_tab()
        filepath = os.sep.join([self.current_project_root_str, old_name])
        self.current_opened_files.remove(filepath)

        if next_selected == -1:
            self.code_window.setPlainText("""\n\n\n
            No files are currently opened.
            Double-click on a file to start editing.\n\n\n\n""")
            self.code_window.setEnabled(False)

    def new_file(self):
        # make new file:
        options_ = QFileDialog.Options()
        options_ |= QFileDialog.DontUseNativeDialog
        options_ |= QFileDialog.ShowDirsOnly
        dial = QFileDialog()
        dial.setDirectory(self.current_project_root_str)
        dial.setDefaultSuffix("*.py")
        filename, _ = dial.getSaveFileName(self, "Save file", "",
                                           "Python Files (*.py)", options=options_)
        if filename:
            filename: str
            last_part = filename.split(os.sep)[-1]
            if '.' in last_part:
                # ensure extension is '.py' so all files are python files.
                pass
            else:
                filename += ".py"
            # actually write to the file.
            open(filename, 'a').close()
            self.open_file(filename)
        else:
            return

    def run_function(self):
        if not self.current_opened_files:
            return

        file_path_to_run = self.current_project_root_str, self.file_tabs.current_file_selected
        file_path_to_run = os.sep.join(file_path_to_run)

        contents_in_file = open(file_path_to_run, 'r').read()

        if contents_in_file != self.code_window.toPlainText():
            save_on_run = self.ide_state.get('save_on_run', False)

            if save_on_run:
                self.save_file()
            else:
                file_path_to_run = self.file_tabs.save_to_temp()

        subprocess.call(['gnome-terminal', '--', self.python_bin, '-i', file_path_to_run])

    def perform_lint(self):
        if self.current_opened_file is None:
            lint_results = run_linter_on_code(code=self.code_window.toPlainText())
        else:
            lint_results = run_linter_on_code(code=self.code_window.toPlainText())

        self.linting_results = lint_results
        self.code_window.linting_results = lint_results

    def show_hide_files_widget(self):
        if self.file_box.isHidden():
            self.grid_layout.setColumnStretch(*self.file_window_show_column_info)
            self.file_box.show()
            self.hide_files_button.setText("Hide")
        else:
            self.file_box.hide()
            self.grid_layout.setColumnStretch(self.file_window_show_column_info[0], 0)
            self.hide_files_button.setText("Show")

    def before_close(self):
        files_to_reopen = []
        current_root_len = len(self.current_project_root_str) + 1
        for file in self.current_opened_files:
            # should be unnecessary, but for now
            assert file.startswith(self.current_project_root_str)
            file_header = file[current_root_len:]
            files_to_reopen.append(file_header)

        files_to_reopen.sort(key=lambda name: self.file_tabs.indexOf(self.file_tabs.tabs[name]))

        self.ide_state['current_opened_files'] = files_to_reopen
        self.ide_state['project_dir'] = self.current_project_root_str
        self.ide_state['selected_tab'] = self.file_tabs.currentIndex()

        open("ide_state.json", 'w').write(dumps(self.ide_state, indent=2))


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = Application()
    window.show()
    exit_code = app.exec_()
    window.before_close()
    sys.exit(exit_code)
