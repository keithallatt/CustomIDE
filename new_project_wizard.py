"""
For settings, new project, and various other things. Making use of Wizards in PyQt5 will make code a lot cleaner in
other files
"""
import os.path
import subprocess
from json import loads

from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import (QWizard, QWizardPage, QComboBox, QVBoxLayout, QHBoxLayout,
                             QWidget, QLabel, QLineEdit, QCheckBox, QDialog, QListWidget, QAbstractItemView)

import logging

logging.basicConfig(filename='debug_logger.log', level=logging.DEBUG)

MAIN_PY_DEFAULT = """# This is a sample Python script.

# Press Ctrl-Shift-R to execute it or replace it with your code.

def primes_under(limit):
    primes = [2, 3]
    for i in range(5, limit + 1, 6):
        # all primes p > 3 are in the form 6n +/- 1
        for p in primes:
            if i % p == 0:
                break
        else:
            primes.append(i)
        for p in primes:
            if (i + 2) % p == 0:
                break
        else:
            primes.append(i + 2)
    return primes


# Press the Run Button in the toolbar to run.
# If the toolbar is not visible, press Ctrl-Alt-Shift-T to show the toolbar.
if __name__ == '__main__':
    for x in primes_under(100):
        print(x)

# For more help, visit the GitHub Repository at https://github.com/keithallatt/CustomIDE
"""


class NewProjectWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.new_project_page = NewProjectPage(self)
        self.addPage(self.new_project_page)
        self.setWindowTitle("New Project")
        self.resize(800, 600)

        self.button(QWizard.FinishButton).clicked.connect(self.finish_up)

    def validateCurrentPage(self) -> bool:
        return self.new_project_page.validatePage()

    def finish_up(self):
        self.new_project_page.finish_up(self.parent())


class NewProjectPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)

        new_project_title_label = QLabel("New Project")

        projects_folder = loads(open('ide_state.json', 'r').read()).get('projects_folder', '~')
        if not projects_folder.endswith(os.sep):
            projects_folder += os.sep
        project_name = "pythonProject"
        projects_folder += project_name

        fp_box, self.fp_line_edit = NewProjectPage.labelled_q_widget(
            "Project Path:", (QLineEdit, os.path.expanduser(projects_folder)))
        env_box, self.env_combo_box = NewProjectPage.labelled_q_widget(
            "Environment:", (QComboBox, ['Virtual Environment (venv)', 'System Python Interpreter']))
        env_location_box, self.env_location_line_edit = NewProjectPage.labelled_q_widget(
            "Environment Location:", (QLineEdit, os.sep.join([os.path.expanduser(projects_folder), "venv"])))
        system_site_packages, self.system_site_packages = NewProjectPage.labelled_q_widget(
            "System Site Packages:", (QCheckBox, "Give the venv access to the system site-packages dir?"))
        main_script_box, self.main_script_check = NewProjectPage.labelled_q_widget(
            "Main Script:", (QCheckBox, "Initialize with main.py?"))

        self.main_script_check.setChecked(True)

        # set selection of project name
        self.fp_line_edit.setSelection(len(projects_folder)-1, len(project_name))

        self.fp_line_edit.textEdited.connect(lambda: self.env_location_line_edit.setText(
            os.sep.join([self.fp_line_edit.text(), "venv"])))

        layout = QVBoxLayout()
        layout.addWidget(new_project_title_label)
        layout.addWidget(fp_box)
        layout.addWidget(env_box)
        layout.addWidget(env_location_box)
        layout.addWidget(system_site_packages)
        layout.addWidget(main_script_box)
        self.setLayout(layout)
        self.setFocus()

    @staticmethod
    def labelled_q_widget(label_text: str, *widget_type_and_args):
        box = QWidget()
        box_layout = QHBoxLayout()

        label = QLabel(label_text)
        box_layout.addWidget(label)
        widgets = []

        num_widgets = len(widget_type_and_args)

        for tup in widget_type_and_args:
            widget_type = tup[0]
            if widget_type == QComboBox:
                widget = QComboBox()
                widget.addItems(tup[1])
            else:
                widget = widget_type(*tup[1:])

            widget.setFixedWidth(500 // num_widgets)

            box_layout.addWidget(widget)
            widgets.append(widget)
        box.setLayout(box_layout)
        return box, *widgets

    def validatePage(self) -> bool:
        fp = self.fp_line_edit.text()

        if os.path.exists(fp) or " " in fp:
            self.fp_line_edit.setStyleSheet("border: 1px solid red;")
            return False

        self.fp_line_edit.setStyleSheet("border: 1px solid black;")

        return True

    def finish_up(self, custom_ide_object):
        if not self.validatePage():
            return

        fp = self.fp_line_edit.text()

        env_choice = self.env_combo_box.currentText()
        chose_venv = "(venv)" in env_choice
        include_main = self.main_script_check.isChecked()
        ssp = self.system_site_packages.isChecked()

        assert not os.path.exists(fp), "Filepath already exists"
        assert " " not in fp, "Cannot use spaces (for time being)"

        logging.info(f"Making project at {fp}, using {env_choice}. " +
                     ("Includes" if include_main else "Does not include") + "main script")

        try:
            # make dir at file path
            os.mkdir(fp)
            if not fp.endswith(os.sep):
                fp += os.sep

            if chose_venv:
                python_fp = loads(open('ide_state.json', 'r').read()).get('python_bin_location', '/usr/bin/python3')
                command = [python_fp, "-m", "venv", fp + "venv"]

                if ssp:
                    command.insert(3, "--system-site-packages")

                subprocess.call(command)
            if include_main:
                main_fp = fp + "main.py"

                with open(main_fp, 'w') as main_file:
                    main_file.write(MAIN_PY_DEFAULT)

            custom_ide_object.statusBar().showMessage('Successfully made new project: ' + fp, 3000)
            custom_ide_object.open_project(project_to_open=fp)

            return True, fp
        except (FileExistsError, FileNotFoundError) as e:
            logging.error(f"Exception of type {type(e)}.")

        custom_ide_object.statusBar().showMessage('Error making new project', 3000)


class GetNewNameDialog(QDialog):
    def __init__(self, parent=None, dialog_title=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.FramelessWindowHint)

        assert hasattr(parent, 'current_project_root')
        assert dialog_title is not None

        self.root_file_path = parent.current_project_root
        self._accepted = False

        layout = QVBoxLayout()

        title_label = QLabel(dialog_title, self)
        menu_background = parent.special_color_dict['lighter-bg-color']
        border_color = parent.special_color_dict['darker-bg-color']
        title_label.setMinimumWidth(250)
        title_label.setAlignment(Qt.AlignCenter)

        title_label.setStyleSheet("background-color: " + menu_background + "; padding: 2px;")

        layout.addWidget(title_label)

        self.line_edit = QLineEdit(self)
        self.line_edit.setMinimumWidth(250)
        self.line_edit.setStyleSheet("QLineEdit:focus { border: 0px solid black; }")

        layout.addWidget(self.line_edit)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        self.setStyleSheet("QDialog { border: 3px solid " + border_color + "; }")
        self.setLayout(layout)

    def get_file_name(self):
        self.exec()
        filename = self.line_edit.text()
        filename = os.sep.join(self.root_file_path + [filename])
        if self._accepted:
            return filename

    def get_raw_text(self):
        self.exec()
        if self._accepted:
            return self.line_edit.text()

    def keyPressEvent(self, a0: QKeyEvent) -> None:
        # do things like with enter and all

        if a0.key() == Qt.Key_Enter or a0.key() == Qt.Key_Return:
            self._accepted = True
            self.accept()

        if a0.key() == Qt.Key_Escape:
            self._accepted = False
            self.reject()

        super().keyPressEvent(a0)


class GetOptionDialog(QDialog):
    def __init__(self, parent=None, dialog_title=None, options=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.FramelessWindowHint)

        assert hasattr(parent, 'current_project_root')
        assert dialog_title is not None
        assert options is not None

        self.root_file_path = parent.current_project_root
        self._accepted = False

        layout = QVBoxLayout()

        title_label = QLabel(dialog_title, self)
        menu_background = parent.special_color_dict['lighter-bg-color']
        border_color = parent.special_color_dict['darker-bg-color']
        title_label.setMinimumWidth(250)
        title_label.setAlignment(Qt.AlignCenter)

        title_label.setStyleSheet("background-color: " + menu_background + "; padding: 2px;")

        layout.addWidget(title_label)

        self.list_widget = QListWidget(self)
        self.list_widget.setMinimumWidth(250)
        self.list_widget.addItems(options)

        title_height = title_label.height()

        item_height = self.list_widget.rectForIndex(self.list_widget.indexFromItem(self.list_widget.item(0))).height()
        self.list_widget.setMaximumHeight(len(options) * item_height + 4)
        self.setMaximumHeight(title_height + len(options) * item_height)

        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.viewport().installEventFilter(self)
        self.list_widget.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

        layout.addWidget(self.list_widget)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        self.setStyleSheet("QDialog { border: 3px solid " + border_color + "; }")
        self.setLayout(layout)

    def eventFilter(self, source, event):
        if event.type() == QEvent.Wheel and source is self.list_widget.viewport():
            return True
        return super().eventFilter(source, event)

    def get_raw_text(self):
        self.exec()
        if self._accepted:
            index = self.list_widget.currentIndex().row()
            text = self.list_widget.item(index).text()
            return text

    def keyPressEvent(self, a0: QKeyEvent) -> None:
        # do things like with enter and all
        if a0.key() == Qt.Key_Enter or a0.key() == Qt.Key_Return:
            self._accepted = True
            self.accept()

        if a0.key() == Qt.Key_Escape:
            self._accepted = False
            self.reject()

        super().keyPressEvent(a0)
