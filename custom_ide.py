"""
The main application.

Count lines with:
    cloc . --by-file --exclude-dir=venv,.idea --include-ext=py

-- NOTICE --
This program is only designed to work on Ubuntu 20.04, as this is a personal project to create a functional IDE.

next steps:
 - add q-thread or something for linting and other slow processes.
 - add multi-cursors like in VSCode, like control click to add multiple cursors, insert text at all of them until
     another click
 - git stuff maybe?
 - rename files.

"""
import os
import re
import subprocess
import sys
import time
from colorsys import rgb_to_hsv, hsv_to_rgb
from json import loads, dumps

from PyQt5.QtCore import Qt, QDir, QModelIndex, QEvent, QItemSelectionModel, QStringListModel, QTimer, QThread
from PyQt5.QtGui import QFont, QFontInfo
from PyQt5.QtWidgets import (QApplication, QGridLayout, QWidget, QFileSystemModel, QFileDialog, QMainWindow, QToolBar,
                             QAction, QPushButton, QStyle, QInputDialog, QDialog, QDialogButtonBox, QVBoxLayout, QLabel,
                             QCompleter)

import syntax
from additional_qwidgets import (QCodeEditor, QCodeFileTabs, ProjectViewer, SaveFilesOnCloseDialog,
                                 SearchBar, CommandLineCallDialog, FindAndReplaceWidget)

from new_project_wizard import NewProjectWizard
from linting import LintingWorker
from webbrowser import open_new_tab as open_in_browser
import datetime
import logging
from send2trash import send2trash

from theme_editor import ThemeEditor

logging.basicConfig(filename='debug_logger.log', level=logging.DEBUG)


class CustomIDE(QMainWindow):
    """
    The main IDE application window. Contains everything from the code editor window
    to the file window, to the file tabs.
    """

    NO_FILES_OPEN_TEXT = "\n\n\n\n\tNo files are currently opened.\n\t" \
                         "Double-click on a file in the side window to start editing.\n\n\n\n"

    def __init__(self, parent=None):
        """ Create the widget """
        super().__init__(parent)
        self.ide_state = loads(open("ide_state.json", 'r').read())
        self.ide_theme = loads(open("ide_themes" + os.sep + self.ide_state['ide_theme'], 'r').read())

        shortcuts = loads(open("shortcuts.json", 'r').read())
        self.setWindowTitle(self.ide_state.get("ide_title", "ide"))

        x, y, w, h = self.ide_state.get('window_geometry', [100, 100, 1000, 1000])
        self.resize(w, h)
        self.move(x, y)

        self.linting_results = []
        self.current_opened_files = set()
        self.completer_style_sheet = ""
        self.set_style_sheet()

        self.file_tabs = QCodeFileTabs(self)
        self.code_window = QCodeEditor(self)
        self.completer = None
        self.completer_model = None
        self.code_window_find = FindAndReplaceWidget(self)
        self.highlighter = None
        self.set_up_file_editor()

        self.file_box = QWidget()
        self.model = QFileSystemModel()
        self.tree = ProjectViewer(self)
        self.current_project_root = None
        self.current_project_root_str = None
        self.set_up_project_viewer()

        self.file_window_show_column_info = 1, 2
        self.grid_layout = None

        self.button_widget = QWidget()
        self.set_up_layout()

        self.set_up_from_save_state()

        # QMainWindow
        self.toolbar = None
        self.set_up_toolbar()

        self.menu_bar = self.menuBar()
        self.search_bar = None
        self.set_up_menu_bar(shortcuts)

        self.statusBar().showMessage('Ready', 3000)
        # right at the end, grab focus to the code editor
        self.file_tabs.set_syntax_highlighter()
        self.code_window.setFocus()

        self.timer = QTimer(self)
        self.linting_thread = None
        self.linting_worker = None
        self.is_linting_currently = False
        self.set_up_linting()

    # Setup Functions

    def set_style_sheet(self):
        # set global style sheet
        bwc = self.ide_theme['background_window_color']
        fwc = self.ide_theme['foreground_window_color']

        lighter_factor = 2
        darker_factor = 0.8
        l_bg_w_c = "#313131"
        d_bg_w_c = "#1e1e1e"

        m = re.match("#(..)(..)(..)", bwc)

        if m is not None:
            r, g, b = m.groups()
            r = int(r, 16) / 255
            g = int(g, 16) / 255
            b = int(b, 16) / 255
            h, s, v = rgb_to_hsv(r, g, b)

            vl = min(1.0, lighter_factor * v)
            vd = min(1.0, darker_factor * v)

            r, g, b = hsv_to_rgb(h, s, vl)
            r = hex(int(r * 255))[2:].zfill(2)
            g = hex(int(g * 255))[2:].zfill(2)
            b = hex(int(b * 255))[2:].zfill(2)
            l_bg_w_c = f"#{r}{g}{b}"

            r, g, b = hsv_to_rgb(h, s, vd)
            r = hex(int(r * 255))[2:].zfill(2)
            g = hex(int(g * 255))[2:].zfill(2)
            b = hex(int(b * 255))[2:].zfill(2)
            d_bg_w_c = f"#{r}{g}{b}"

        self.setStyleSheet(
            "QWidget {"f"background-color: {bwc};  color: {fwc};""}"
            "QToolTip {"f"background-color: {bwc};  color: {fwc};""}"
            "QMainWindow {"f"background-color: {bwc};  color: {fwc};""}"
            "QMenuBar {"f"background-color: {d_bg_w_c};  color: {fwc};""}"
            "QMenuBar::item {"f"background-color: {d_bg_w_c};  color: {fwc}; ""}"
            "QMenuBar::item::selected {"f"background-color: {l_bg_w_c}; ""}"
            "QMenu {"f"background-color: {d_bg_w_c};  color: {fwc}; border: 1px solid {l_bg_w_c};""}"
            "QMenu::item::selected {"f"background-color: {l_bg_w_c}; ""}"
        )

        self.completer_style_sheet = f"background-color: {d_bg_w_c};  color: {fwc}; border: 1px solid {l_bg_w_c};"

        logging.info("Set up style sheet")

    def set_up_file_editor(self):
        autocomplete_prompts = syntax.PythonHighlighter.built_ins
        autocomplete_dict = {
            "main": "if __name__ == \"__main__\":"
        }
        autocomplete_prompts += list(autocomplete_dict.keys())

        autocomplete_prompts.sort(key=len)

        self.completer = QCompleter(self)
        self.completer_model = QStringListModel(autocomplete_prompts, self.completer)
        self.completer.setModel(self.completer_model)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setWrapAround(False)
        self.completer.popup().setStyleSheet(self.completer_style_sheet)

        self.code_window = QCodeEditor(self)

        self.code_window.all_autocomplete = autocomplete_prompts
        self.code_window.auto_complete_dict = autocomplete_dict

        self.code_window.set_completer(self.completer)

        self.code_window.installEventFilter(self)
        # try to get from theme, but fall back on state, and finally to Courier New 12pt
        font_name = self.ide_theme.get('editor_font_family', self.ide_state.get('editor_font_family', "Courier New"))
        font_size = self.ide_theme.get('editor_font_size', self.ide_state.get('editor_font_size', 12))
        backup_font = QFont("Courier New", 12)
        q = QFont(font_name, font_size)
        qfi = QFontInfo(q)
        logging.debug(f"Font match? {font_name} v.s. {qfi.family()}: {font_name == qfi.family()}")
        self.code_window.setFont(q if font_name == qfi.family() else backup_font)

        logging.info("Set up file editor / code editor")

    def set_up_project_viewer(self):
        self.model.setRootPath('')
        self.tree.doubleClicked.connect(self.open_file)

        # Set the model of the view.
        self.tree.setModel(self.model)
        for i in range(1, self.tree.model().columnCount()):
            self.tree.header().hideSection(i)

        # Set the root index of the view as the user's home directory.
        proj_dir = self.ide_state['project_dir']
        self.tree.setEnabled(False)
        if proj_dir is not None:
            proj_dir = os.path.expanduser(proj_dir)
            if not os.path.exists(proj_dir):
                return

            self.tree.setRootIndex(self.model.index(QDir.cleanPath(proj_dir)))
            self.current_project_root = proj_dir.split(os.sep)
            self.current_project_root_str = proj_dir
            self.tree.setEnabled(True)

        self.tree.setAnimated(False)
        self.tree.setIndentation(20)
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)

        logging.info("Set up project viewer")

    def set_up_layout(self):
        file_box_layout = QGridLayout()
        file_box_layout.addWidget(self.tree, 0, 0, 1, 1)
        file_box_layout.setColumnStretch(0, 1)
        file_box_layout.setRowStretch(0, 1)
        self.file_box.setLayout(file_box_layout)
        layout = QGridLayout()
        layout.addWidget(self.button_widget, 0, 0, 3, 1)
        layout.addWidget(self.file_box, 0, 1, 3, 1)
        layout.addWidget(self.code_window_find, 1, 2, 1, 1)
        layout.addWidget(self.file_tabs, 0, 2, 1, 1)
        layout.addWidget(self.code_window, 2, 2, 1, 1)
        layout.setColumnStretch(0, 0)  # make button widget small
        layout.setColumnStretch(*self.file_window_show_column_info)  # make file window ok
        layout.setColumnStretch(2, 5)  # make code window larger
        layout.setRowStretch(2, 1)
        self.grid_layout = layout
        central_widget_holder = QWidget()
        central_widget_holder.setLayout(layout)
        self.setCentralWidget(central_widget_holder)

        logging.info("Set up layout")

    def set_up_from_save_state(self):
        # put default before opening files
        self.code_window.setPlainText(CustomIDE.NO_FILES_OPEN_TEXT)
        self.code_window.setEnabled(False)
        # open up current opened files. (one until further notice)

        if self.current_project_root is None:
            return

        current_files = self.ide_state['current_opened_files']
        files = [
            os.sep.join([self.current_project_root_str, current_file]) for current_file in current_files
        ]
        current_index = self.ide_state['selected_tab']
        number_before_missing = 0
        for i, f in enumerate(files):
            if os.path.exists(f):
                self.open_file(f)
            elif i <= current_index:
                # counts number missing before the 'selected' so we can more closely find which tab to open to.
                number_before_missing += 1
        current_index -= number_before_missing
        # makes sure current index is in range 0 <= index < number of tabs
        current_index = max(0, min(current_index, len(self.file_tabs.tabs.keys()) - 1))
        self.file_tabs.setCurrentIndex(current_index)
        if len(self.file_tabs.tabs) == 1:
            # no swapping took place so after this file opens, save to temp
            self.file_tabs.save_to_temp(0)

        logging.info("Restored save state")

    def set_up_toolbar(self):
        self.toolbar = QToolBar("Custom IDE Toolbar", self)

        run_button = QPushButton("Run")
        run_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        run_button.clicked.connect(self.run_function)

        save_button = QPushButton("Save")
        save_button.setIcon(self.style().standardIcon(QStyle.SP_DriveFDIcon))
        save_button.clicked.connect(self.save_file)

        cloc_button = QPushButton("CLOC")
        cloc_button.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        cloc_button.clicked.connect(self.perform_cloc)

        self.toolbar.addWidget(run_button)
        self.toolbar.addWidget(save_button)
        self.toolbar.addWidget(cloc_button)

        tool_bar_area = {
            "top": Qt.TopToolBarArea,
            "bottom": Qt.BottomToolBarArea,
            "left": Qt.LeftToolBarArea,
            "right": Qt.RightToolBarArea,
        }[self.ide_state.get('tool_bar_position', "top")]

        self.addToolBar(tool_bar_area, self.toolbar)
        logging.info("Set up tool bar")

    def set_up_menu_bar(self, shortcuts):
        """ Set up the menu bar with all the options. """
        # FILE MENU
        file_menu = self.menu_bar.addMenu('&File')

        # set Ctrl-N to be the new file shortcut.
        new_file_action = QAction("New File", self)
        new_file_action.setShortcut(shortcuts.get("new", "Ctrl+N"))
        new_file_action.triggered.connect(self.new_file)

        # set Ctrl-W to be the close shortcut.
        close_file_action = QAction("Close", self)
        close_file_action.setShortcut(shortcuts.get("close", "Ctrl+W"))
        close_file_action.triggered.connect(self.close_file)

        # set Ctrl-S to be the save shortcut.
        save_file_action = QAction("Save", self)
        save_file_action.setShortcut(shortcuts.get("save", "Ctrl+S"))
        save_file_action.triggered.connect(self.save_file)

        # set Ctrl-Shift-N to be the new project shortcut.
        new_project_action = QAction("New Project", self)
        new_project_action.setShortcut(shortcuts.get("new_project", "Ctrl+Shift+N"))
        new_project_action.triggered.connect(self.new_project)

        # set Ctrl-Shift-O to be the open project shortcut.
        open_project_action = QAction("Open Project", self)
        open_project_action.setShortcut(shortcuts.get("open_project", "Ctrl+Shift+O"))
        open_project_action.triggered.connect(self.open_project)

        # set Ctrl-Shift-W to be the close project shortcut.
        close_project_action = QAction("Close Project", self)
        close_project_action.setShortcut(shortcuts.get("close_project", "Ctrl+Shift+W"))
        close_project_action.triggered.connect(self.close_project)

        focus_search_bar_action = QAction("Search Files", self)

        def focus_search_bar():
            self.search_bar.setFocus()

        focus_search_bar_action.setShortcut(shortcuts.get("search_files", "Ctrl+Shift+L"))
        focus_search_bar_action.triggered.connect(focus_search_bar)

        file_menu.addActions([
            new_file_action,
            close_file_action,
            save_file_action,
        ])
        file_menu.addSeparator()
        file_menu.addActions([
            new_project_action,
            open_project_action,
            close_project_action
        ])
        file_menu.addSeparator()
        file_menu.addActions([
            focus_search_bar_action
        ])

        # EDIT MENU

        edit_menu = self.menu_bar.addMenu('&Edit')

        cut_action = QAction("Cut", self)
        cut_action.setShortcut("Ctrl+X")
        cut_action.triggered.connect(self.code_window.cut)

        copy_action = QAction("Copy", self)
        copy_action.setShortcut("Ctrl+C")
        copy_action.triggered.connect(self.code_window.copy)

        paste_action = QAction("Paste", self)
        paste_action.setShortcut("Ctrl+V")
        paste_action.triggered.connect(self.code_window.paste)

        undo_action = QAction("Undo", self)
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(self.code_window.undo)

        redo_action = QAction("Redo", self)
        redo_action.setShortcut("Ctrl+Shift+Z")
        redo_action.triggered.connect(self.code_window.redo)

        def find_action_connection():
            self.code_window_find.show()
            self.code_window_find.find_line.setFocus()

        find_action = QAction("Find", self)
        find_action.setShortcut("Ctrl+F")
        find_action.triggered.connect(find_action_connection)

        def replace_action_connection():
            self.code_window_find.show()
            self.code_window_find.replace_line.setFocus()

        replace_action = QAction("Replace", self)
        replace_action.setShortcut("Ctrl+R")
        replace_action.triggered.connect(replace_action_connection)

        edit_menu.addActions([
            cut_action,
            copy_action,
            paste_action,
            undo_action,
            redo_action
        ])
        edit_menu.addSeparator()
        edit_menu.addActions([
            find_action,
            replace_action
        ])

        # VIEW MENU

        view_menu = self.menu_bar.addMenu('&View')

        show_tool_bar_action = QAction("Show Toolbar", self)
        show_tool_bar_action.setShortcut(shortcuts.get("show_toolbar", "Ctrl+Alt+Shift+T"))
        show_tool_bar_action.setCheckable(True)

        def show_hide_toolbar():
            if self.toolbar.isHidden():
                self.toolbar.show()
                show_tool_bar_action.setChecked(True)
            else:
                self.toolbar.hide()
                show_tool_bar_action.setChecked(False)

        show_tool_bar_action.triggered.connect(show_hide_toolbar)

        if self.ide_state.get('tool_bar_hidden', False):
            show_hide_toolbar()
        else:
            show_tool_bar_action.setChecked(True)

        show_files_action = QAction("Show Files", self)
        show_files_action.setShortcut(shortcuts.get("show_files", "Ctrl+Alt+Shift+F"))
        show_files_action.setCheckable(True)

        def show_hide_files_widget():
            if self.file_box.isHidden():
                self.grid_layout.setColumnStretch(*self.file_window_show_column_info)
                self.file_box.show()
                show_files_action.setChecked(True)
            else:
                self.file_box.hide()
                self.grid_layout.setColumnStretch(self.file_window_show_column_info[0], 0)
                show_files_action.setChecked(False)

        show_files_action.triggered.connect(show_hide_files_widget)

        if self.ide_state.get('file_box_hidden', False):
            show_hide_files_widget()
        else:
            show_files_action.setChecked(True)

        show_theme_editor_action = QAction("Show Theme Editor", self)
        show_theme_editor_action.triggered.connect(self.show_theme_editor)

        view_menu.addActions([
            show_tool_bar_action,
            show_files_action,
            show_theme_editor_action
        ])

        # RUN MENU

        run_menu = self.menu_bar.addMenu('&Run')

        # set Ctrl-R to be the run shortcut
        run_action = QAction("Run", self)
        run_action.setShortcut(shortcuts.get("run", "Ctrl+Shift+R"))
        run_action.triggered.connect(self.run_function)

        run_menu.addAction(run_action)

        # PIP MENU

        pip_menu = self.menu_bar.addMenu("&Pip")

        installed_packages_action = QAction("Installed Packages List", self)
        installed_packages_action.triggered.connect(lambda: self.pip_function("list"))

        install_pip_action = QAction(f"Install Package...", self)
        install_pip_action.triggered.connect(lambda: self.pip_function("install"))

        pip_help_action = QAction(f"Pip Help", self)
        pip_help_action.triggered.connect(lambda: self.pip_function("help"))

        pip_menu.addActions([
            installed_packages_action,
            install_pip_action,
            pip_help_action
        ])

        # HELP MENU

        help_menu = self.menu_bar.addMenu("&Help")

        github_repo_url = "https://github.com/keithallatt/CustomIDE"
        # using web browser module's open_new_tab causes Gtk-Message and libGL errors, but still works (?)

        def open_github_repo():
            open_in_browser(github_repo_url)

        def open_github_issues():
            open_in_browser(github_repo_url + "/issues")

        github_repo_action = QAction("GitHub Repo", self)
        github_repo_action.triggered.connect(open_github_repo)

        github_issues_action = QAction("Report a problem", self)
        github_issues_action.triggered.connect(open_github_issues)

        help_menu.addActions([
            github_repo_action,
            github_issues_action
        ])

        # SEARCH BAR
        # set up search bar on right hand side.

        self.search_bar = SearchBar(self)
        self.menu_bar.setCornerWidget(self.search_bar, Qt.TopRightCorner)

        logging.info("Set up menu bar")

    def set_up_linting(self):
        self.timer.timeout.connect(self.perform_lint)
        self.timer.start(500)

    # Utility functions

    def _load_code(self, text):
        self.code_window.setPlainText(text)

    def _get_code(self):
        return self.code_window.getPlainText()

    def focus_file_explorer(self):
        self.tree.setFocus()
        i = self.tree.selectionModel().currentIndex()
        self.tree.selectionModel().select(i, QItemSelectionModel.SelectionFlag.Select)

    def perform_lint(self):
        if self.is_linting_currently:
            print("Is already linting")
            return

        self.is_linting_currently = True

        if self.current_project_root is None:
            self.statusBar().showMessage("No project open", 3000)
            return

        self.linting_thread = QThread()
        self.linting_worker = LintingWorker(self)

        self.linting_worker.moveToThread(self.linting_thread)

        def worker_finished():
            self.is_linting_currently = False
            self.code_window.linting_results = self.linting_worker.linting_results
            self.code_window.repaint()

        self.linting_thread.started.connect(self.linting_worker.run)
        self.linting_worker.finished.connect(self.linting_thread.quit)
        self.linting_worker.finished.connect(self.linting_worker.deleteLater)
        self.linting_thread.finished.connect(self.linting_thread.deleteLater)
        self.linting_worker.finished.connect(worker_finished)

        self.linting_thread.start()

    def perform_cloc(self):
        """ run 'cloc' on the project """
        if self.current_project_root is None:
            self.statusBar().showMessage("No project open", 3000)
            return

        folder = self.current_project_root_str
        command = f"cloc {folder} --by-file --exclude-dir=venv,.idea".split(" ")
        out = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = out.communicate()

        # fixing bytes output (weird stuff that doesn't show up
        # when printing, but is still there nonetheless
        stdout = stdout.replace(b'\r', b'.\n')
        stdout = stdout.replace(b'classified', b'       Classified')

        stdout = stdout.decode("utf-8")
        dial = CommandLineCallDialog("cloc", "Line counting for " + self.current_project_root_str, self)
        dial.set_content(stdout)
        dial.exec()

        logging.info("Performed `cloc` on project")

    def pip_function(self, function, *args):
        """ Execute a command line call in the form 'pip3 function arg1 arg2 ...' """
        if self.current_project_root is None:
            # make sure we're working only when the project root is set.
            return

        pip_filepath = self.ide_state.get("pip_path", "/usr/bin/pip3")

        venv_path = self.current_project_root_str
        if not venv_path.endswith(os.sep):
            venv_path += os.sep

        venv_path += os.sep.join(['venv', 'bin', 'pip3'])

        if os.path.exists(venv_path):
            pip_filepath = venv_path

        valid_functions = [
            'install', 'download', 'uninstall', 'freeze', 'list', 'show', 'check', 'config',
            'search', 'wheel', 'hash', 'completion', 'debug', 'help'
        ]

        assert function in valid_functions, f"Invalid pip function {function}."

        needs_package_name = [
            'install', 'download', 'uninstall'
        ]

        if function in needs_package_name and not args:
            # get package name
            text, ok = QInputDialog.getText(self, f'{function.capitalize()} pip package', 'Package name:')
            if ok:
                args = (text,)
            else:
                return

            self.statusBar().showMessage(f"{function.capitalize()}ing module '{text}'")

        command = [pip_filepath, function, *args]
        out = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = out.communicate()

        self.statusBar().showMessage(" ".join(command))

        stdout = stdout.decode('utf-8')

        dial = CommandLineCallDialog(f"pip {function}", "", self)
        dial.set_content(stdout)
        dial.exec()

        logging.info(f"Performed `pip {function}`")

    def before_close(self):
        if self.current_project_root is not None:
            files_to_reopen = []
            current_root_len = len(self.current_project_root_str)
            if not self.current_project_root_str.endswith(os.sep):
                current_root_len += 1
            for file in self.current_opened_files:
                # should be unnecessary, but for now
                assert file.startswith(self.current_project_root_str)
                file_header = file[current_root_len:]
                files_to_reopen.append(file_header)

            files_to_reopen.sort(key=lambda name: self.file_tabs.indexOf(self.file_tabs.tabs[name]))

            self.ide_state['current_opened_files'] = files_to_reopen
            self.ide_state['project_dir'] = self.current_project_root_str.replace(os.path.expanduser('~'), '~', 1)
        else:
            self.ide_state['current_opened_files'] = []
            self.ide_state['project_dir'] = None

        self.ide_state['selected_tab'] = self.file_tabs.currentIndex()
        self.ide_state['file_box_hidden'] = self.file_box.isHidden()
        self.ide_state['tool_bar_hidden'] = self.toolbar.isHidden()

        tool_bar_position = {
            Qt.TopToolBarArea: "top",
            Qt.BottomToolBarArea: "bottom",
            Qt.LeftToolBarArea: "left",
            Qt.RightToolBarArea: "right",
        }[self.toolBarArea(self.toolbar)]

        self.ide_state['tool_bar_position'] = tool_bar_position

        size = self.size()
        position = self.pos()

        geometry = [position.x(), position.y(), size.width(), size.height()]
        self.ide_state['window_geometry'] = geometry

        json_str = dumps(self.ide_state, indent=2)
        open("ide_state.json", 'w').write(json_str)
        logging.info("Saved save state to file")

    def get_file_from_viewer(self):
        q_model_indices = self.tree.selectedIndexes()
        assert len(q_model_indices) <= 1, "Multiple selected."
        last_index = q_model_indices[-1]
        file_paths = []
        while last_index.data(Qt.DisplayRole) != os.sep:
            file_paths.append(last_index.data(Qt.DisplayRole))
            last_index = last_index.parent()
        file_paths.append("")
        filepath = os.sep.join(file_paths[::-1])
        return filepath

    def save_before_closing(self):
        if self.current_project_root is None:
            return

        # save the file currently looking at first.
        if self.file_tabs.tabs:
            self.file_tabs.save_to_temp(self.file_tabs.currentIndex())

        proj_root = self.current_project_root_str + os.sep
        unsaved_files = []
        save_from = dict()
        for k, v in self.file_tabs.temp_files.items():
            file = proj_root + k
            if not os.path.exists(file):
                print("File missing, probably deleted:", file)
                continue
            if open(file, 'r').read() != open(v, 'r').read():
                unsaved_files.append(k)
                save_from[file] = v

        if unsaved_files:
            save_files_dialog = SaveFilesOnCloseDialog(self, unsaved_files)
            save_files_dialog.exec()

            if save_files_dialog.response == "Cancel" or save_files_dialog.response is None:
                return False

            if save_files_dialog.response == "Yes":
                for s_to, s_from in save_from.items():
                    file_contents = open(s_from, 'r').read()
                    open(s_to, 'w').write(file_contents)

        return True

    def set_theme(self, k, v):
        assert k.endswith('s')
        k = k[:-1]
        assert k in self.ide_state.keys(), f"{k}"
        self.ide_state[k] = v

    def show_theme_editor(self):
        window = ThemeEditor(self)
        window.show()

    # File functions

    def new_file(self):
        # make new file:
        options_ = QFileDialog.Options()
        options_ |= QFileDialog.DontUseNativeDialog
        options_ |= QFileDialog.ShowDirsOnly
        dial = QFileDialog()
        dial.setDirectory(self.current_project_root_str)
        dial.setDefaultSuffix("*.py")

        filename, _ = dial.getSaveFileName(self, "Save file", "", "Python Files (*.py)", options=options_)

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
            self.search_bar.set_data()
        else:
            return

    def open_file(self, filepath: str = None):
        # if used for shortcut
        if filepath is None:
            filepath = self.get_file_from_viewer()
            self.open_file(filepath)
            return

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

        if os.path.isdir(filepath):
            return

        if root_full.endswith(os.sep):
            filename = filepath[len(root_full):]
        else:
            filename = filepath[len(root_full)+1:]

        self.current_opened_files.add(filepath)
        self.file_tabs.open_tab(filename)
        self.code_window.setEnabled(True)

    def save_file(self):
        if not self.current_opened_files:
            self.statusBar().showMessage("No files open", 3000)
            return

        try:
            file_path_to_save = self.current_project_root_str, self.file_tabs.current_file_selected
            file_path_to_save = os.sep.join(file_path_to_save)
            open(file_path_to_save, 'w').write(self.code_window.toPlainText())
            self.statusBar().showMessage(f"Saved file to \"{file_path_to_save}\"", 3000)
        except (OSError, FileNotFoundError, IsADirectoryError):
            self.statusBar().showMessage("Could not save file.", 5000)

    def close_file(self):
        next_selected, old_name = self.file_tabs.close_tab()
        self.file_tabs.setCurrentIndex(next_selected)
        if next_selected == -1 or not self.current_opened_files:
            self.highlighter = None
            self.code_window.text_input_mode = QCodeEditor.RawTextInput
            self.code_window.setPlainText(CustomIDE.NO_FILES_OPEN_TEXT)
            self.code_window.setEnabled(False)

    def delete_file(self):
        filepath = self.get_file_from_viewer()

        dial = QDialog(self)
        dial.setWindowTitle("Delete File")

        button_box = QDialogButtonBox(QDialogButtonBox.Yes | QDialogButtonBox.No)

        def delete_file_inner():
            fp = filepath[len(self.current_project_root_str):]
            fp = fp.lstrip(os.sep)

            self.file_tabs.close_tab(self.file_tabs.indexOf(self.file_tabs.tabs[fp]))

            send2trash(filepath)
            dial.accept()

        button_box.accepted.connect(delete_file_inner)
        button_box.rejected.connect(dial.reject)

        layout = QVBoxLayout()
        message = QLabel("Delete File? This action will move the file to the trash folder.")
        layout.addWidget(message)
        layout.addWidget(button_box)
        dial.setLayout(layout)
        dial.exec()

    # Project functions

    def new_project(self):
        wizard = NewProjectWizard(self)
        wizard.show()

    def open_project(self, *_, project_to_open: str = None):
        if project_to_open is None:
            options_ = QFileDialog.Options()
            options_ |= QFileDialog.DontUseNativeDialog
            options_ |= QFileDialog.ShowDirsOnly
            dial = QFileDialog(self)
            dial.setFileMode(QFileDialog.Directory)

            directory_to_start = self.ide_state.get("projects_folder", "~")
            directory_to_start = os.path.expanduser(directory_to_start)
            if not directory_to_start.endswith(os.sep):
                directory_to_start += os.sep

            project_to_open = dial.getExistingDirectory(self,
                                                        "Open Project",
                                                        directory=directory_to_start,
                                                        options=options_)

            if not project_to_open:
                return

        if not project_to_open.endswith(os.sep):
            project_to_open += os.sep

        if self.ide_state['project_dir'] is not None and \
                project_to_open == os.path.expanduser(self.ide_state['project_dir']):
            self.statusBar().showMessage("Project already open")
        else:
            # save the files before closing.
            self.save_before_closing()
            while self.file_tabs.tabs.keys():
                self.close_file()

            project_dir = project_to_open.replace(os.path.expanduser("~"), "~", 1)
            if project_dir.endswith(os.sep):
                project_dir = project_dir[:-1]
            self.ide_state['project_dir'] = project_dir
            self.set_up_project_viewer()
            self.file_tabs.reset_tabs()
            self.search_bar.set_data()

            self.tree.setEnabled(True)

    def close_project(self):
        if self.current_project_root is None:
            return

        while self.file_tabs.tabs:
            self.close_file()

        # set project to none
        self.current_project_root = None
        self.current_project_root_str = None
        self.ide_state['project_dir'] = None

        self.model.setRootPath('')
        self.tree.setRootIndex(self.model.index(QDir.cleanPath(os.sep)))

        self.tree.setEnabled(False)

    # Run functions

    def run_function(self):
        if not self.current_opened_files:
            self.statusBar().showMessage("No files open", 3000)
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

        if file_path_to_run is None:
            logging.warning("File path is None: function run_function(self)")
            return

        if not os.path.exists(file_path_to_run):
            logging.warning("File specified does not exist: function run_function(self)")
            return

        if file_path_to_run.endswith(".py"):
            # running python
            python_bin = self.ide_state.get("python_bin_location", "/usr/bin/python3")

            # look for venv
            venv_file_path = self.current_project_root_str
            if not venv_file_path.endswith(os.sep):
                venv_file_path += os.sep

            venv_file_path += os.sep.join(['venv', 'bin', 'python3'])

            if os.path.exists(venv_file_path):
                python_bin = venv_file_path

            process_call = ['gnome-terminal', '--', python_bin, '-i', file_path_to_run]
            self.statusBar().showMessage(f"Running '{' '.join(process_call)}'")
            subprocess.call(process_call)
        elif file_path_to_run.endswith(".json"):
            self.statusBar().showMessage(f"Cannot run JSON File.")
        else:
            filename = file_path_to_run.split(os.sep)[-1]
            if '.' in filename:
                extension = '.'.join(filename.split(".")[1:])
                self.statusBar().showMessage(f"Unable to run files of type '*.{extension}'")
            else:
                self.statusBar().showMessage(f"File {filename} has no extension")

    # Overridden functions (From QMain Window)

    def focusNextPrevChild(self, _: bool) -> bool:
        """ Filter for focusing other widgets. Prevents this. """
        # should prevent focus switching
        # parameter 'next' renamed to '_' as 'next' shadows a builtin.
        if self.code_window.hasFocus() or self.search_bar.hasFocus():
            return False

        QMainWindow.focusNextPrevChild(self, _)

        if self.code_window.hasFocus() or self.search_bar.hasFocus():
            QMainWindow.focusNextPrevChild(self, _)
        return True

    def eventFilter(self, q_object, event):
        """
        Prevents tab and back-tab from changing focus and also allows for control tab and control back-tab
        (ctrl-shift-tab) to switch open tabs.
        """
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

    def closeEvent(self, a0):
        if self.current_project_root is None:
            return

        close_after = self.save_before_closing()
        if not close_after:
            a0.ignore()


def main():
    """
    Create the QApplication window and add the Custom IDE to it.
    """

    output = subprocess.Popen("cloc . --by-file --exclude-dir=venv,.idea --include-ext=py".split(" "),
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    stdout, stderr = output.communicate()
    stdout = stdout.decode('utf-8')

    header_line = stdout.split("\n")[6].upper()
    sum_line = stdout.split("\n")[-3]
    while "  " in sum_line or "  " in header_line:
        sum_line = sum_line.replace("  ", " ")
        header_line = header_line.replace("  ", " ")

    cloc_results = dict()
    for k, v in zip(header_line.split(" "), sum_line.split(" ")):
        if v.isnumeric():
            cloc_results[k] = int(v)
    cloc_results["TOTAL"] = sum(cloc_results.values())
    print(*[f"{k}: {v}" for k, v in cloc_results.items()], sep="\n")

    logging.info(f"Application started running: {datetime.datetime.now()}")
    app = QApplication(sys.argv)
    window = CustomIDE()
    window.show()
    exit_code = app.exec_()
    window.before_close()
    logging.info(f"Application finished running: {datetime.datetime.now()}")

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
