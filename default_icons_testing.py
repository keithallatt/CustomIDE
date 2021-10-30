import sys

import inspect

from PyQt5.QtWidgets import QApplication, QGridLayout, QPushButton, QStyle, QWidget


class Window(QWidget):
    def __init__(self):
        super(Window, self).__init__()

        inspect_list = []
        for x in inspect.getmembers(QStyle):
            if x[0].startswith("SP_"):
                inspect_list.append(x[0])

        layout = QGridLayout()

        for n, name in enumerate(inspect_list):
            btn = QPushButton(name)
            pixmapi = getattr(QStyle, name)

            icon = self.style().standardIcon(pixmapi)

            btn.setIcon(icon)
            layout.addWidget(btn, n // 4, n % 4)

        self.setLayout(layout)


app = QApplication(sys.argv)

w = Window()
w.show()

app.exec_()