"""
The main application.

Count lines with:
    cloc . --by-file --exclude-dir=venv,.idea

-- WARNING --
This program is only designed to work on Ubuntu 20.04, as this is a personal project to create a functional IDE.

next steps:
 - add venv to projects if desired (could be useful, and is recommended practice)
 - add option for extensibility modules (like a folder of 'mods' that are auto integrated)
 - add q-thread or something for linting
 - add multi-cursors like in VSCode, like control click to add multiple cursors, insert text at all of them until
     another click
 - New project button

"""
import os
import re
import subprocess
import sys
from colorsys import rgb_to_hsv, hsv_to_rgb
from json import loads, dumps

from PyQt5.QtCore import Qt, QDir, QModelIndex, QEvent, QItemSelectionModel
from PyQt5.QtGui import QFont, QFontInfo
from PyQt5.QtWidgets import (QApplication, QGridLayout, QWidget, QFileSystemModel, QFileDialog, QMainWindow, QToolBar,
                             QAction, QPushButton, QStyle)

from additional_qwidgets import QCodeEditor, QCodeFileTabs, CTreeView, SaveFilesOnCloseDialog, SearchBar, CLOCDialog
from linting import run_linter_on_code
from webbrowser import open_new_tab as open_in_browser


class CustomIntegratedDevelopmentEnvironment(QMainWindow):
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
        shortcuts = loads(open("shortcuts.json", 'r').read())
        self.setWindowTitle(self.ide_state.get("ide_title", "ide"))

        x, y, w, h = self.ide_state.get('window_geometry', [100, 100, 1000, 1000])
        self.resize(w, h)
        self.move(x, y)

        self.linting_results = []
        self.current_opened_files = set()
        self.set_style_sheet()

        self.file_tabs = QCodeFileTabs(self)
        self.code_window = QCodeEditor(self)
        self.highlighter = None
        self.set_up_file_editor()

        self.file_box = QWidget()
        self.model = QFileSystemModel()
        self.tree = CTreeView(self)
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

    # Setup Functions

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

        # set Ctrl-Shift-O to be the close shortcut.
        open_project_action = QAction("Open Project", self)
        open_project_action.setShortcut(shortcuts.get("open_project", "Ctrl+Shift+O"))
        open_project_action.triggered.connect(self.open_project)

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
            open_project_action
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

        edit_menu.addActions([
            cut_action,
            copy_action,
            paste_action,
            undo_action,
            redo_action
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
        show_files_action.setShortcut(shortcuts.get("show_toolbar", "Ctrl+Alt+Shift+F"))
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

        view_menu.addAction(show_tool_bar_action)
        view_menu.addAction(show_files_action)

        # RUN MENU

        run_menu = self.menu_bar.addMenu('&Run')

        # set Ctrl-R to be the run shortcut
        run_action = QAction("Run", self)
        run_action.setShortcut(shortcuts.get("run", "Ctrl+Shift+R"))
        run_action.triggered.connect(self.run_function)

        run_menu.addAction(run_action)

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

    def set_up_project_viewer(self):
        self.model.setRootPath('')
        self.tree.doubleClicked.connect(self.open_file)

        # Set the model of the view.
        self.tree.setModel(self.model)
        for i in range(1, self.tree.model().columnCount()):
            self.tree.header().hideSection(i)

        # Set the root index of the view as the user's home directory.
        proj_dir = self.ide_state['project_dir']
        proj_dir = os.path.expanduser(proj_dir)
        if not os.path.exists(proj_dir):
            proj_dir = self.ide_state['default_project_dir']
            proj_dir = os.path.expanduser(proj_dir)
        assert os.path.exists(proj_dir), "Default Project Folder does not exist."

        self.tree.setRootIndex(self.model.index(QDir.cleanPath(proj_dir)))
        self.current_project_root = proj_dir.split(os.sep)
        self.current_project_root_str = proj_dir
        self.tree.setAnimated(False)
        self.tree.setIndentation(20)
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)

    def set_up_layout(self):
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
        layout.setColumnStretch(0, 0)  # make button widget small
        layout.setColumnStretch(*self.file_window_show_column_info)  # make file window ok
        layout.setColumnStretch(2, 5)  # make code window larger
        layout.setRowStretch(1, 1)
        self.grid_layout = layout
        central_widget_holder = QWidget()
        central_widget_holder.setLayout(layout)
        self.setCentralWidget(central_widget_holder)

    def set_up_from_save_state(self):
        # put default before opening files
        self.code_window.setPlainText(CustomIntegratedDevelopmentEnvironment.NO_FILES_OPEN_TEXT)
        self.code_window.setEnabled(False)
        # open up current opened files. (one until further notice)
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

    def set_style_sheet(self):
        # set global style sheet
        bwc = self.ide_state['background_window_color']
        fwc = self.ide_state['foreground_window_color']

        lighter_factor = 1.2
        darker_factor = 2
        lbwc = "#313131"
        dbwc = "#1e1e1e"

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
            lbwc = f"#{r}{g}{b}"

            r, g, b = hsv_to_rgb(h, s, vd)
            r = hex(int(r * 255))[2:].zfill(2)
            g = hex(int(g * 255))[2:].zfill(2)
            b = hex(int(b * 255))[2:].zfill(2)
            dbwc = f"#{r}{g}{b}"

        self.setStyleSheet(
            "QWidget {"
            f"  background-color: {bwc};  color: {fwc};"
            "}"
            ""
            "QToolTip {"
            f"  background-color: {bwc};  color: {fwc};"
            "}"
            "QMainWindow {"
            f"  background-color: {bwc};  color: {fwc};"
            "}"
            "QMenuBar {"
            f"  background-color: {lbwc};  color: {fwc};"
            "}"
            "QMenuBar::item {"
            f"   background-color: {lbwc};  color: {fwc}; "
            "}"
            "QMenuBar::item::selected { "
            f"   background-color: {dbwc}; "
            "}"
            "QMenu { "
            f"   background-color: {lbwc};  color: {fwc}; border: 1px solid {dbwc};"
            "}"
            "QMenu::item::selected { "
            f"   background-color: {dbwc}; "
            "}"
        )

    def set_up_file_editor(self):
        self.code_window.installEventFilter(self)
        font_name = self.ide_state.get('editor_font_family', "Courier New")
        font_size = self.ide_state.get('editor_font_size', 12)
        backup_font = QFont("Courier New", 12)
        q = QFont(font_name, font_size)
        qfi = QFontInfo(q)
        self.code_window.setFont(q if font_name == qfi.family() else backup_font)

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
        if self.current_opened_file is None:
            lint_results = run_linter_on_code(code=self.code_window.toPlainText())
        else:
            lint_results = run_linter_on_code(code=self.code_window.toPlainText())

        self.linting_results = lint_results
        self.code_window.linting_results = lint_results

    def perform_cloc(self):
        folder = self.current_project_root_str
        command = f"cloc {folder} --by-file --exclude-dir=venv,.idea".split(" ")
        out = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = out.communicate()

        # fixing bytes output (weird stuff that doesn't show up
        # when printing, but is still there nonetheless
        stdout = stdout.replace(b'\r', b'.\n')
        stdout = stdout.replace(b'classified', b'       Classified')

        stdout = stdout.decode("utf-8")
        dial = CLOCDialog(self)
        dial.set_content(stdout)
        dial.exec()

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
        self.ide_state['project_dir'] = self.current_project_root_str.replace(os.path.expanduser('~'), '~', 1)
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

    def save_before_closing(self):
        # save the file currently looking at first.
        if self.file_tabs.tabs:
            self.file_tabs.save_to_temp(self.file_tabs.currentIndex())

        proj_root = self.current_project_root_str + os.sep
        unsaved_files = []
        save_from = dict()
        for k, v in self.file_tabs.temp_files.items():
            file = proj_root + k
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

    # File functions

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
            self.search_bar.set_data()
        else:
            return

    def open_file(self, filepath: str = None):
        # if used for shortcut
        if filepath is None:
            q_model_indices = self.tree.selectedIndexes()
            assert len(q_model_indices) <= 1, "Multiple selected."
            last_index = q_model_indices[-1]

            file_paths = []

            while last_index.data(Qt.DisplayRole) != os.sep:
                file_paths.append(last_index.data(Qt.DisplayRole))
                last_index = last_index.parent()

            file_paths.append("")
            filepath = os.sep.join(file_paths[::-1])

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

        filename = filepath[len(root_full)+1:]

        self.current_opened_files.add(filepath)
        self.file_tabs.open_tab(filename)
        self.code_window.setEnabled(True)

    def save_file(self):
        if not self.current_opened_files:
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
            self.code_window.setPlainText(CustomIntegratedDevelopmentEnvironment.NO_FILES_OPEN_TEXT)
            self.code_window.setEnabled(False)

    # Project functions

    def new_project(self):
        pass

    def open_project(self):
        options_ = QFileDialog.Options()
        options_ |= QFileDialog.DontUseNativeDialog
        options_ |= QFileDialog.ShowDirsOnly
        dial = QFileDialog()
        dial.setDirectory(self.ide_state.get("projects_folder", os.path.expanduser("~")))

        project_to_open = dial.getExistingDirectory(self, "Open Project", "", options=options_)

        if project_to_open == os.path.expanduser(self.ide_state['project_dir']):
            self.statusBar().showMessage("Project already open")
        else:
            # save the files before closing.
            self.save_before_closing()
            while self.file_tabs.tabs.keys():
                self.close_file()

            self.ide_state['project_dir'] = project_to_open.replace(os.path.expanduser("~"), "~", 1)
            self.set_up_project_viewer()
            self.file_tabs.reset_tabs()
            self.search_bar.set_data()

    # Run functions

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

        if file_path_to_run is None:
            print("File path is None... issue")
            return

        if not os.path.exists(file_path_to_run):
            print("File path not a file... potential issue.")
            return

        if file_path_to_run.endswith(".py"):
            # running python
            python_bin = self.ide_state.get("python_bin_location", "/usr/bin/python3")
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
        return False

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
        close_after = self.save_before_closing()
        if close_after:
            QMainWindow.closeEvent(self, a0)
        else:
            a0.ignore()


def main():
    """
    Create the QApplication window and add the Custom IDE to it.
    """
    app = QApplication(sys.argv)
    window = CustomIntegratedDevelopmentEnvironment()
    window.show()
    exit_code = app.exec_()
    window.before_close()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
