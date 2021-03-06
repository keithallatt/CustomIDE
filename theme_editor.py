"""
Make an editor for themes.
"""
import os
from json import loads, dumps
from typing import Union

from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (QWidget, QMainWindow, QPushButton, QComboBox, QVBoxLayout, QHBoxLayout,
                             QLabel, QColorDialog, QLineEdit, QSpinBox, QInputDialog)

DEFAULT_SYNTAX_HIGHLIGHTER = {
    "keyword": ["#cc7832"],
    "operator": ["#ffffff"],
    "brace": ["#ffffff"],
    "builtins": ["#8888c6"],
    "def_class": ["#ffc66d"],
    "string": ["#6a8759"],
    "string2": ["#629755", "bold"],
    "comment": ["#808080", "italic"],
    "self": ["#94558d"],
    "numbers": ["#6897bb"],
    "double_under": ["#b200b2"],
    "kwargs": ["#aa4926"],
    "todo": ["#bbb529", "italic"],
    "todo_author": ["#bbbb99", "bold italic"]
}

DEFAULT_IDE_THEME = {
  "background_window_color": "#222222",
  "foreground_window_color": "#ffffff",
  "line_number_color": "#999999",
  "line_highlight_color": "#888888",
  "editor_font_family": "Courier New",
  "editor_font_size": 12
}


class ThemeEditor(QMainWindow):
    """
    Menu for theme editing, whether that involves editing the colors or making new themes.
    """
    def __init__(self, parent: QMainWindow = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Theme Editor")
        self.resize(800, 500)

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

        def theme_list_change(new_text: str) -> None:
            """ When the Theme QComboBox's value changes, reset the contents of the panel. """
            folder_name = self.theme_kind.currentText().replace(" ", "_").lower()
            filepath = os.sep.join([folder_name, new_text])
            if not os.path.isfile(filepath):
                return

            for widget_index in reversed(range(self.scroll_widget_layout.count())):
                widget_to_remove = self.scroll_widget_layout.itemAt(widget_index).widget()
                self.scroll_widget_layout.removeWidget(widget_to_remove)
                widget_to_remove.deleteLater()

            theme = loads(open(filepath, 'r').read())

            for k, v in theme.items():
                # must be done in place, if a local variable is used, it will overwrite some behaviour
                # of each options.
                self.scroll_widget_layout.addWidget(ThemeOption(self.scroll_widget_inside, k, v))

        def theme_kind_change(new_text: str) -> None:
            """ When the Theme Kind QComboBox's value changes, change the Theme QComboBox's options """
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

        # buttons that appear at the bottom of the window.
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

    def new_theme(self) -> None:
        """ Create a new theme, with the default values. """
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

    def set_theme(self) -> None:
        """ Set the theme, and apply it visually immediately """
        kind = self.theme_kind.currentText().replace(" ", "_").lower()
        theme = self.theme_list.currentText()

        self.application.set_theme(kind, theme)

    def save_values(self) -> None:
        """ Save the theme values to file """
        filename = self.theme_kind.currentText().replace(" ", "_").lower() + os.sep + self.theme_list.currentText()

        values = dict()
        for widget_index in range(self.scroll_widget_layout.count()):
            values.update(self.scroll_widget_layout.itemAt(widget_index).widget().get_value())

        file_contents = dumps(values, indent=2)

        with open(filename, 'w') as f:
            f.write(file_contents)


class ThemeOption(QWidget):
    """ Represents a single row of the theme editor, such as  """
    def __init__(self, parent: QWidget, label_str: str, args: Union[str, list, int]):
        super().__init__(parent)

        default_color = None
        style_option = None
        string_option = None
        int_option = None

        # determine type of option purely from option arguments.
        # done so no checking has to be done before creation.
        if isinstance(args, str):
            args: str
            if args.startswith("#"):
                default_color = args
                option_type = "color"
            else:
                string_option = args
                option_type = "string"
        elif isinstance(args, list):
            args: list
            if len(args) == 1 and args[0].startswith("#"):
                default_color = args[0]
                style_option = ''
                option_type = "styled color"
            elif len(args) == 2:
                default_color, style_option = args
                option_type = "styled color"
            else:
                return
        elif isinstance(args, int):
            args: int
            int_option = args
            option_type = "int"
        else:
            return

        layout = QHBoxLayout()
        label = QLabel(label_str.replace("_", " ").capitalize())
        layout.addWidget(label)

        # add editable blocks depending on options set.
        if default_color is not None:
            button = QPushButton(default_color)

            def button_push(color_name: Union[str, bool] = None) -> None:
                """ On button push, allow user to select a color """
                if color_name is None or isinstance(color_name, bool):
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

    def get_value(self) -> dict:
        """ Return the value of this theme option as a dictionary. """
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
