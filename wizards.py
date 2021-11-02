"""
For settings, new project, and various other things. Making use of Wizards in PyQt5 will make code a lot cleaner in
other files
"""
import os.path
import subprocess
from json import loads

from PyQt5.QtWidgets import (QWizard, QWizardPage, QComboBox, QVBoxLayout, QHBoxLayout,
                             QWidget, QLabel, QLineEdit, QCheckBox)

import logging
logging.basicConfig(filename='debug_logger.log', level=logging.DEBUG)

WIZARD_DEBUG = True

MAIN_PY_DEFAULT = """# This is a sample Python script.

# Press Ctrl-Shift-R to execute it or replace it with your code.

def primes_under(limit):
    primes = [2, 3]
    for i in range(5, limit + 1, 6):
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
            "Project Path:", (QLineEdit, os.path.expanduser(projects_folder))
        )

        env_box, self.env_combo_box = NewProjectPage.labelled_q_widget(
            "Environment:", (QComboBox, ['Virtual Environment (venv)', 'System Python Interpreter'])
        )

        env_location_box, self.env_location_line_edit = NewProjectPage.labelled_q_widget(
            "Environment Location:", (QLineEdit, os.sep.join([os.path.expanduser(projects_folder), "venv"]))
        )

        main_script_box, self.main_script_check = NewProjectPage.labelled_q_widget(
            "Main Script:", (QCheckBox, "Initialize with main.py?")
        )

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
                subprocess.call([python_fp, "-m", "venv", fp + "venv"])
            if include_main:
                main_fp = fp + "main.py"

                with open(main_fp, 'w') as main_file:
                    main_file.write(MAIN_PY_DEFAULT)

            # TODO: test this after figuring out the issue with the last one.
            custom_ide_object.statusBar().showMessage('Successfully made new project: ' + fp, 3000)
            custom_ide_object.open_project(project_to_open=fp)

            return True, fp
        except (FileExistsError, FileNotFoundError) as e:
            logging.error(f"Exception of type {type(e)}.")

        custom_ide_object.statusBar().showMessage('Error making new project', 3000)
