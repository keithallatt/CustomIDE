import subprocess

import plugins
from additional_qwidgets import CommandLineCallDialog


class ClocPlugin(plugins.Plugin):
    def __init__(self, parent):
        super().__init__(parent, "CLOC")

    def run_on_triggered(self):
        """ run 'cloc' on the project """
        if self.parent.current_project_root is None:
            self.parent.statusBar().showMessage("No project open", 3000)
            return

        folder = self.parent.current_project_root_str
        command = f"cloc {folder} --by-file --exclude-dir=venv,.idea".split(" ")
        out = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = out.communicate()

        # fixing bytes output (weird stuff that doesn't show up
        # when printing, but is still there nonetheless
        stdout = stdout.replace(b'\r', b'.\n')
        stdout = stdout.replace(b'classified', b'       Classified')

        stdout = stdout.decode("utf-8")
        dial = CommandLineCallDialog("cloc", "Line counting for " + self.parent.current_project_root_str, self.parent)
        dial.set_content(stdout)
        dial.exec()
