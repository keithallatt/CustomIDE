"""
Make an editor for themes.
"""
import os
import sys
from json import loads, dumps

from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (QWidget, QMainWindow, QPushButton, QComboBox, QVBoxLayout, QHBoxLayout,
                             QLabel, QColorDialog, QLineEdit, QSpinBox, QInputDialog, QDialog, QDialogButtonBox,
                             QApplication)

DEFAULT_SYNTAX_HIGHLIGHTER = {
    "keyword": ["#2f8eab"],
    "operator": ["#ffffff"],
    "brace": ["#ffffff"],
    "builtins": ["#a2eae0"],
    "defclass": ["#92d7ef"],
    "string": ["#bcb8ce"],
    "string2": ["#bcb8ce", "bold"],
    "comment": ["#808080", "italic"],
    "self": ["#917898"],
    "numbers": ["#a5cdef"],
    "dunder": ["#a2eae0"],
    "kwargs": ["#f9acbb"],
    "todo": ["#4790ba", "italic"],
    "todo_author": ["#44a0ff", "bold italic"]
}

DEFAULT_IDE_THEME = {
  "background_window_color": "#222233",
  "foreground_window_color": "#ffffff",
  "line_number_color": "#9999cc",
  "line_highlight_color": "#8888aa",
  "editor_font_family": "Courier New",
  "editor_font_size": 12
}


class ThemeEditor(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Theme Editor")
        self.resize(600, 500)

        self.application = parent

        central_widget = QWidget(self)

        layout = QVBoxLayout()

        self.theme_kind = QComboBox(central_widget)
        self.theme_kind.addItems(["IDE Themes", "Syntax Highlighters"])

        self.theme_list = QComboBox(central_widget)
        self.scroll_widget_inside = QWidget(self)
        self.scroll_widget_layout = QVBoxLayout()

        ide_themes = os.listdir("ide_themes")
        syntax_highlighters = os.listdir("syntax_highlighters")

        def theme_list_change(new_text):
            folder_name = self.theme_kind.currentText().replace(" ", "_").lower()
            filepath = os.sep.join([folder_name, new_text])
            if not os.path.isfile(filepath):
                return

            for widget_index in reversed(range(self.scroll_widget_layout.count())):
                widget_to_remove = self.scroll_widget_layout.itemAt(widget_index).widget()
                self.scroll_widget_layout.removeWidget(widget_to_remove)
                widget_to_remove.setParent(None)
                widget_to_remove.deleteLater()

            theme = loads(open(filepath, 'r').read())

            for k, v in theme.items():
                self.scroll_widget_layout.addWidget(ThemeOption(self.scroll_widget_inside, k, v))

        def theme_kind_change(new_text):
            while self.theme_list.count():
                self.theme_list.removeItem(0)
            if new_text == "IDE Themes":
                self.theme_list.addItems(ide_themes)
                self.theme_list.setCurrentText(parent.ide_state['ide_theme'])
                theme_list_change(parent.ide_state['ide_theme'])
            elif new_text == "Syntax Highlighters":
                self.theme_list.addItems(syntax_highlighters)
                self.theme_list.setCurrentText(parent.ide_state['syntax_highlighter'])
                theme_list_change(parent.ide_state['syntax_highlighter'])
            else:
                raise ValueError("Not a choice")

        self.theme_kind.currentTextChanged.connect(theme_kind_change)
        theme_kind_change(self.theme_kind.currentText())

        self.theme_list.currentTextChanged.connect(theme_list_change)
        self.scroll_widget_inside.setLayout(self.scroll_widget_layout)

        self.new_button = QPushButton("New...")
        self.new_button.clicked.connect(self.new_theme)

        self.set_button = QPushButton("Set theme")
        self.set_button.clicked.connect(self.set_theme)

        self.done_button = QPushButton("Save")
        self.done_button.clicked.connect(self.save_values)

        layout.addWidget(self.theme_kind)
        layout.addWidget(self.theme_list)
        layout.addWidget(self.scroll_widget_inside)
        layout.addWidget(self.new_button)
        layout.addWidget(self.set_button)
        layout.addWidget(self.done_button)

        self.theme_kind.setCurrentText("IDE Themes")
        theme_kind_change("IDE Themes")
        self.theme_list.setCurrentText(parent.ide_state['ide_theme'])
        theme_list_change(parent.ide_state['ide_theme'])

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def new_theme(self):
        kind = self.theme_kind.currentText()
        name, accept = QInputDialog.getText(self, f"New {kind} Name", "Theme Name:")
        kind = kind.replace(" ", "_").lower()

        if not accept:
            return

        if not name.endswith('.json'):
            name = name.replace(".", "_") + ".json"
        else:
            name = name[:-5].replace(".", "_") + ".json"

        filepath = os.sep.join([kind, name])

        if os.path.exists(filepath):
            print("filepath exists, cannot make theme")
            return

        default_contents = DEFAULT_IDE_THEME if kind == "ide_themes" else DEFAULT_SYNTAX_HIGHLIGHTER

        with open(filepath, 'w') as f:
            f.write(dumps(default_contents, indent=2))

        self.theme_list.addItem(name)
        self.theme_list.setCurrentText(name)

    def set_theme(self):
        kind = self.theme_kind.currentText().replace(" ", "_").lower()
        theme = self.theme_list.currentText()

        self.application.set_theme(kind, theme)

        dial = QDialog(self)
        dial.setWindowTitle("")

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Close)
        button_box.accepted.connect(lambda: QApplication.exit(0))
        button_box.rejected.connect(dial.accept)

        layout = QVBoxLayout()
        message = QLabel("Changes will take effect on restart. Quit now?")
        layout.addWidget(message)
        layout.addWidget(button_box)
        dial.setLayout(layout)
        dial.exec()

    def save_values(self):
        filename = self.theme_kind.currentText().replace(" ", "_").lower() + os.sep + self.theme_list.currentText()

        values = dict()
        for widget_index in range(self.scroll_widget_layout.count()):
            values.update(self.scroll_widget_layout.itemAt(widget_index).widget().get_value())

        file_contents = dumps(values, indent=2)

        with open(filename, 'w') as f:
            f.write(file_contents)


class ThemeOption(QWidget):
    def __init__(self, parent, label_str, args):
        super().__init__(parent)

        default_color = None
        style_option = None
        string_option = None
        int_option = None

        if type(args) == str and args.startswith("#"):
            default_color = args
            option_type = "color"
        elif type(args) == list and len(args) == 1 and args[0].startswith("#"):
            default_color = args[0]
            style_option = ''
            option_type = "styled color"
        elif type(args) == list and len(args) == 2:
            default_color, style_option = args
            option_type = "styled color"
        elif type(args) == str:
            string_option = args
            option_type = "string"
        elif type(args) == int:
            int_option = args
            option_type = "int"
        else:
            return

        layout = QHBoxLayout()
        label = QLabel(label_str.replace("_", " ").capitalize())
        layout.addWidget(label)

        if default_color is not None:
            button = QPushButton(default_color)

            def button_push(color_name=None):
                if color_name is None or type(color_name) == bool:
                    color = QColorDialog.getColor()
                    color_name = color.name()
                else:
                    color = QColor()
                    color.setNamedColor(color_name)
                lightness = color.lightness()
                text_color = "f" if lightness < 128 else "0"
                text_color = "#" + (text_color * 6)
                button.setStyleSheet("QPushButton {"
                                     f"background-color: {color_name};"
                                     f"color: {text_color}; "
                                     "}")
                self.color_name = color_name
                button.setText(color_name)

            button_push(default_color)
            button.clicked.connect(button_push)
            layout.addWidget(button)

        if style_option is not None:
            self.style_line = QLineEdit()
            self.style_line.setText(style_option)
            self.style_line.setMaximumWidth(150)
            layout.addWidget(self.style_line)

        if string_option is not None:
            self.string_line = QLineEdit()
            self.string_line.setText(string_option)
            self.string_line.setMaximumWidth(150)
            layout.addWidget(self.string_line)

        if int_option is not None:
            self.int_spin = QSpinBox()
            self.int_spin.setValue(int_option)
            self.int_spin.setMaximumWidth(150)
            layout.addWidget(self.int_spin)

        self.setLayout(layout)
        self.label_name = label_str
        self.option_type = option_type

    def get_value(self):
        if self.option_type == "color":
            return {self.label_name: self.color_name}
        if self.option_type == "styled color":
            return {self.label_name: [self.color_name] if self.style_line.text().strip() == ''
                    else [self.color_name, self.style_line.text()]}
        if self.option_type == "string":
            return {self.label_name: self.string_line.text()}
        if self.option_type == "int":
            return {self.label_name: self.int_spin.value()}
        return {self.label_name: None}
