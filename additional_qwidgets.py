"""
Additional QWidgets, placed here to make the code in ./custom_ide.py cleaner.

Uses code from https://stackoverflow.com/questions/40386194/create-text-area-textedit-with-line-number-in-pyqt
QLineNumberArea and QCodeEditor courtesy of @ acbetter, @ Dan-Dev, and @ Axel Schneider

Uses code from https://stackoverflow.com/questions/7339685/how-to-rotate-a-qpushbutton
RotatedButton courtesy of @ Ulrich Dangel

Code has been modified to fit specific needs / wants.
- Allowed colors to be read in from ide_state.json for example
- made rotated buttons not look as bloated. May be an issue on some systems but it works great for me.
"""
import os
import re
import tempfile
from json import loads

from PyQt5.QtCore import Qt, QRect, QSize, pyqtBoundSignal, QEvent
from PyQt5.QtGui import QColor, QPainter, QTextFormat, QMouseEvent, QTextCursor, QStandardItemModel, QStandardItem, \
    QFont
from PyQt5.QtWidgets import (QWidget, QPlainTextEdit,
                             QTextEdit, QPushButton, QStylePainter, QStyle,
                             QStyleOptionButton, QTabWidget, QTreeView, QDialog, QDialogButtonBox, QVBoxLayout, QLabel,
                             QLineEdit, QCompleter)

import syntax


class RotatedButton(QPushButton):
    def __init__(self, text, parent=None):
        super(RotatedButton, self).__init__(text, parent)
        self.setMaximumWidth(20)

    def paintEvent(self, event):
        painter = QStylePainter(self)
        painter.rotate(90)
        painter.translate(0, -self.width())
        painter.drawControl(QStyle.CE_PushButton, self.get_style_options())

    def minimumSizeHint(self):
        size = super(RotatedButton, self).minimumSizeHint()
        size.transpose()
        return size

    def sizeHint(self):
        size = super(RotatedButton, self).sizeHint()
        size.transpose()
        return size

    def get_style_options(self):
        options = QStyleOptionButton()
        options.initFrom(self)
        size = options.rect.size()
        size.transpose()
        options.rect.setSize(size)
        options.features = QStyleOptionButton.None_
        if self.isFlat():
            options.features |= QStyleOptionButton.Flat
        if self.menu():
            options.features |= QStyleOptionButton.HasMenu
        if self.autoDefault() or self.isDefault():
            options.features |= QStyleOptionButton.AutoDefaultButton
        if self.isDefault():
            options.features |= QStyleOptionButton.DefaultButton
        if self.isDown() or (self.menu() and self.menu().isVisible()):
            options.state |= QStyle.State_Sunken
        if self.isChecked():
            options.state |= QStyle.State_On
        if not self.isFlat() and not self.isDown():
            options.state |= QStyle.State_Raised

        options.text = self.text()
        options.icon = self.icon()
        options.iconSize = self.iconSize()
        return options


class QLineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor
        self.setToolTip("tooltip")
        self.setMouseTracking(True)
        self.hovering = False

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.codeEditor.line_number_area_paint_event(event)

    def enterEvent(self, event):
        self.hovering = True

    def leaveEvent(self, event):
        self.hovering = False

    def mouseMoveEvent(self, a0: QMouseEvent):
        if self.hovering:
            y = a0.y()
            hovering_on = y // self.codeEditor.font_height + self.codeEditor.verticalScrollBar().value() + 1
            self.setToolTip(self.codeEditor.line_number_area_linting_tooltips.get(hovering_on, ''))


class QCodeEditor(QPlainTextEdit):
    ProgrammingMode = 0
    RawTextInput = 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineNumberArea = QLineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.update_line_number_area_width(0)

        self.linting_results = []
        self.line_number_area_linting_tooltips = {}

        self.application = parent
        self.font_height = 10  # approximate until starts drawing

        self.text_input_mode = QCodeEditor.RawTextInput

    def keyPressEvent(self, event):
        if self.text_input_mode == QCodeEditor.RawTextInput:
            return QPlainTextEdit.keyPressEvent(self, event)

        # make sure the text input mode was not changed to anything else.
        assert self.text_input_mode == QCodeEditor.ProgrammingMode, \
            "Mode is neither raw text input nor programming mode."

        tc = self.textCursor()

        if event.key() == Qt.Key_1 and event.modifiers() == Qt.AltModifier:
            self.application.focus_file_explorer()
            return

        # for navigating (up and down on top and bottom lines)
        if event.key() == Qt.Key_Down and self.blockCount() - 1 == tc.blockNumber():
            # last number
            tc.setPosition(len(self.toPlainText()))
            self.setTextCursor(tc)
            return
        if event.key() == Qt.Key_Up and tc.blockNumber() == 0:
            # right the beginning
            tc.setPosition(0)
            self.setTextCursor(tc)
            return
        # prevent shift-return from making extra newlines in a block (block = line in this case)
        if event.key() == Qt.Key_Return:
            current_line = self.toPlainText().split("\n")[tc.blockNumber()]

            m = re.match(r"\s*", current_line)
            whitespace = m.group(0)
            whitespace = whitespace.replace("\t", "    ")  # 4 spaces per tab if they somehow get in there.

            if current_line[:tc.positionInBlock()].endswith(":"):
                whitespace += "    "

            tc.insertText("\n" + whitespace)
            self.setTextCursor(tc)
            return
        # for indentation
        if event.key() == Qt.Key_Tab:
            if tc.selectionStart() == tc.selectionEnd():
                tc.insertText(" " * (4 - (tc.positionInBlock() % 4)))
            else:
                tc.beginEditBlock()
                sel_start, sel_end = tc.selectionStart(), tc.selectionEnd()

                tc.setPosition(sel_start)
                sel_start = tc.position() - tc.positionInBlock()

                tc.setPosition(sel_end)
                sel_end = tc.position() - tc.positionInBlock()

                original_start = sel_start
                position_after = sel_end

                while sel_end != sel_start:
                    tc.setPosition(sel_end)
                    tc.insertText("    ")
                    tc.setPosition(sel_end - 1)
                    position_after += 4
                    sel_end = tc.position() - tc.positionInBlock()
                tc.setPosition(sel_end)
                tc.insertText("    ")

                tc.setPosition(original_start)
                tc.setPosition(position_after, QTextCursor.KeepAnchor)

                last_line_len = len(self.toPlainText().split("\n")[tc.blockNumber()])
                tc.setPosition(tc.position() + last_line_len, QTextCursor.KeepAnchor)

                tc.endEditBlock()

                self.setTextCursor(tc)
            return
        # for un-indenting
        if event.key() == Qt.Key_Backtab:
            if tc.selectionStart() == tc.selectionEnd():
                line_number = tc.blockNumber()
                line = self.toPlainText().split("\n")[line_number]

                m = re.match(r"^(\s*)", line)
                num_removing = min(m.end(), 4)
                if num_removing:
                    tc.beginEditBlock()
                    new_position = tc.position() - num_removing
                    sel_start = tc.position() - tc.positionInBlock()
                    tc.setPosition(sel_start)
                    for i in range(num_removing):
                        tc.deleteChar()
                    tc.setPosition(new_position)
                    tc.endEditBlock()
                    self.setTextCursor(tc)
            else:
                tc.beginEditBlock()
                sel_start, sel_end = tc.selectionStart(), tc.selectionEnd()

                tc.setPosition(sel_start)
                sel_start = tc.position() - tc.positionInBlock()

                tc.setPosition(sel_end)
                sel_end = tc.position() - tc.positionInBlock()

                original_start = sel_start
                position_after = sel_end + len(self.toPlainText().split("\n")[tc.blockNumber()])

                while sel_end >= sel_start:
                    tc.setPosition(sel_end)
                    line_number = tc.blockNumber()
                    line = self.toPlainText().split("\n")[line_number]

                    m = re.match(r"^(\s*)", line)
                    num_removing = min(m.end(), 4)

                    if num_removing:
                        line_start = tc.position() - tc.positionInBlock()
                        tc.setPosition(line_start)
                        for i in range(num_removing):
                            tc.deleteChar()

                    if sel_end == 0:
                        break

                    position_after -= num_removing
                    tc.setPosition(sel_end - 1)
                    sel_end = tc.position() - tc.positionInBlock()

                tc.setPosition(sel_end)

                if original_start < 0:
                    original_start = 0

                tc.setPosition(original_start)
                tc.setPosition(position_after, QTextCursor.KeepAnchor)
                tc.endEditBlock()

                self.setTextCursor(tc)
            return

        # need to do the bracket matching and quote matching for single and triple
        need_to_match = {
            Qt.Key_ParenLeft: "()",
            Qt.Key_BraceLeft: "{}",
            Qt.Key_BracketLeft: "[]",
        }

        matching_closing = {
            Qt.Key_ParenRight, Qt.Key_BraceRight, Qt.Key_BracketRight
        }

        need_to_match_strings = {
            Qt.Key_QuoteDbl: "\"\"",
            Qt.Key_Apostrophe: "\'\'"
        }

        if event.key() in need_to_match.keys():
            if tc.selectionStart() == tc.selectionEnd():
                matching_str = need_to_match[event.key()]

                tc.insertText(matching_str[0])
                pos = tc.position()
                tc.insertText(matching_str[1])
                tc.setPosition(pos)
                self.setTextCursor(tc)
                return
            else:
                matching_str = need_to_match[event.key()]
                s, e = tc.selectionStart(), tc.selectionEnd()

                tc.setPosition(s)
                tc.insertText(matching_str[0])
                tc.setPosition(e+1)
                tc.insertText(matching_str[1])

                tc.setPosition(s+1)
                tc.setPosition(e+1, QTextCursor.KeepAnchor)
                self.setTextCursor(tc)

                return

        # for matching close ), ], }
        if event.key() in matching_closing:
            pos = tc.position()
            next_1 = self.toPlainText()[pos:pos + 1]
            if ord(next_1) == event.key():
                tc.setPosition(pos+1)
                self.setTextCursor(tc)
                return

        if event.key() in need_to_match_strings.keys():
            matching_str = need_to_match_strings[event.key()]

            if tc.selectionStart() == tc.selectionEnd():

                tc.insertText(matching_str[0])
                self.setTextCursor(tc)
                pos = tc.position()

                last_3 = self.toPlainText()[max(0, pos-3):pos]
                last_3_1_before = self.toPlainText()[max(0, pos-4):pos-1]

                if last_3 in ["'''", '"""'] and last_3_1_before not in ["'''", '"""']:
                    tc.insertText(last_3)
                    tc.setPosition(pos)
                else:
                    next_1 = self.toPlainText()[pos:pos+1]
                    if next_1 == matching_str[1]:
                        tc.deleteChar()
                        tc.setPosition(pos)
                    else:
                        tc.insertText(matching_str[1])
                        tc.setPosition(pos)
                self.setTextCursor(tc)
                return
            else:
                s, e = tc.selectionStart(), tc.selectionEnd()

                tc.setPosition(s)
                tc.insertText(matching_str[0])
                tc.setPosition(e+1)
                tc.insertText(matching_str[1])

                tc.setPosition(s+1)
                tc.setPosition(e+1, QTextCursor.KeepAnchor)
                self.setTextCursor(tc)

                return

        # if the delete key is pressed, then check for "|" or like (|)
        if event.key() == Qt.Key_Backspace:
            pos = tc.position()
            prev_and_next = self.toPlainText()[max(0, pos-1):pos+1]
            matching_pairs = list(need_to_match.values()) + list(need_to_match_strings.values())
            if prev_and_next in matching_pairs:
                tc.deleteChar()
                tc.deletePreviousChar()
                self.setTextCursor(tc)
                return

            # if delete isn't for the matching pairs part, check for indentation parts.
            current_line = self.toPlainText()[tc.position() - tc.positionInBlock(): tc.position()]
            m = re.match(r"^\s*$", current_line)
            if m is not None:
                l = len(current_line)
                if l:
                    for i in range((l-1) % 4 + 1):
                        tc.deletePreviousChar()
                    self.setTextCursor(tc)
                    return

        return QPlainTextEdit.keyPressEvent(self, event)

    def line_number_area_width(self):
        digits = 1
        max_value = max(1, self.blockCount())
        while max_value >= 10:
            max_value /= 10
            digits += 1
        space = 3 + self.fontMetrics().width('9') * digits
        return space

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def highlight_current_line(self):
        ide_state = loads(open("ide_state.json", 'r').read())
        extra_selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            line_color = QColor()
            line_color.setNamedColor(ide_state["line_highlight_color"])
            line_color = line_color.lighter(85)
            line_color.setAlpha(25)
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        self.setExtraSelections(extra_selections)

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.lineNumberArea)
        ide_state = self.application.ide_state
        window_color = QColor(ide_state['background_window_color'])
        line_color = QColor(ide_state['line_number_color'])

        painter.fillRect(event.rect(), window_color)
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        # Just to make sure I use the right font
        height = int(self.fontMetrics().height())
        self.font_height = height
        while block.isValid() and (top <= event.rect().bottom()):
            if block.isVisible() and (bottom >= event.rect().top()):
                number = str(block_number + 1)

                painter.fillRect(0, int(top), int(self.lineNumberArea.width()), int(height), window_color)

                painter.setPen(line_color)
                painter.drawText(0, int(top), int(self.lineNumberArea.width()), int(height), Qt.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1


class QCodeFileTabs(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tabs = {}
        self.temp_files = {}
        self.application = parent

        # which was the last tab swapped to
        self.last_tab_index = None
        self._last_file_selected = None

        # allow tabs to be rearranged.
        self.setMovable(True)

        # connect function to signal made by tab clicking.
        self.currentChanged: pyqtBoundSignal
        self.currentChanged.connect(self.file_selected_by_index)
        # connect function to signal made by tab rearranging
        self.tabBar().tabMoved: pyqtBoundSignal
        self.tabBar().tabMoved.connect(self.tabs_rearranged)

        self.setTabsClosable(True)
        self.tabCloseRequested: pyqtBoundSignal
        self.tabCloseRequested.connect(self.close_tab)

    @property
    def current_file_selected(self):
        return self._last_file_selected

    def open_tab(self, name):
        if name in self.tabs.keys():
            # select tab
            tab = self.tabs[name]
            tab_index = self.indexOf(tab)
        else:
            tab = QWidget()
            self.tabs.update({name: tab})
            self.addTab(tab, name)
            tab_index = self.indexOf(tab)

            self.style().styleHint(
                QStyle.SH_TabBar_CloseButtonPosition, None, self.tabBar()
            )

        self.setCurrentIndex(tab_index)

    def close_tab(self, index: int = None):
        if index is None:
            index = self.currentIndex()

        self.save_to_temp(index)

        # possible fix for file not updating on tab close.
        if index == self.last_tab_index:
            self.last_tab_index = None

        name = self.tabText(index)
        self.tabs.pop(name)
        self.removeTab(index)

        # moved here so closing tab whether from button or shortcut still removes files.
        filepath = os.sep.join([self.application.current_project_root_str, name])
        self.application.current_opened_files.remove(filepath)

        return self.currentIndex(), name

    def next_tab(self):
        next_index = (self.currentIndex() + 1) % self.count()
        self.setCurrentIndex(next_index)

    def previous_tab(self):
        next_index = (self.currentIndex() - 1) % self.count()
        self.setCurrentIndex(next_index)

    def reset_tabs(self):
        self.tabs = {}
        self.temp_files = {}
        self.last_tab_index = None
        self._last_file_selected = None

    def tabs_rearranged(self):
        self.last_tab_index = self.indexOf(self.tabs[self._last_file_selected])

    def save_to_temp(self, index: int = None):
        """
        Save a tab's contents to a temp file when needed.
        :param index: The index of the tab to save.
        """
        if index is None:
            index = self.currentIndex()

        last_tab = self.tabText(index)
        if last_tab not in self.temp_files.keys():
            # keep until program quits.
            self.temp_files.update({last_tab: tempfile.mkstemp()[1]})
        last_temp_file = self.temp_files[last_tab]
        code_to_save = self.application.code_window.toPlainText()
        open(last_temp_file, 'w').write(code_to_save)

    def file_selected_by_index(self, index: int) -> None:
        """
        When a tab is selected, save the old tab to a temp file before
        :param index: The index of the tab corresponding to the file selected.
        """
        if index == -1:
            return

        if self.last_tab_index is not None:
            self.save_to_temp(self.last_tab_index)

        next_tab = self.tabText(index)
        next_temp_file = self.temp_files.get(next_tab,
                                             self.application.current_project_root_str + os.sep + next_tab)

        self.set_syntax_highlighter(next_tab)

        self.application.code_window.setPlainText(open(next_temp_file, 'r').read())

        self.last_tab_index = index
        self._last_file_selected = next_tab

    def set_syntax_highlighter(self, filename = None):
        if filename is None:
            current_widget = self.currentWidget()
            for k, v in self.tabs.items():
                if v == current_widget:
                    filename = k
                    break
            else:
                print("No file open or other issue")
                return

        # set appropriate syntax highlighter
        self.application.highlighter = {
            ".py": syntax.PythonHighlighter,
            ".json": syntax.JSONHighlighter
        }.get(
            "unspecified" if '.' not in filename else filename[filename.index('.'):], lambda _: None
        )(self.application.code_window.document())

        if self.application.highlighter is None:
            self.application.code_window.text_input_mode = QCodeEditor.RawTextInput
        else:
            self.application.code_window.text_input_mode = QCodeEditor.ProgrammingMode


class CTreeView(QTreeView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.application = parent

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return:
            self.application.open_file()

        self.get_files_as_strings()

        return QTreeView.keyPressEvent(self, event)

    def get_files_as_strings(self):
        def get_files(directory_path):
            files_in_directory = []
            if not directory_path.endswith(os.sep):
                directory_path += os.sep
            for f in os.listdir(directory_path):
                if os.path.isdir(directory_path + f):
                    files_in_directory += get_files(directory_path + f)
                elif os.path.isfile(directory_path + f):
                    files_in_directory.append(directory_path + f)
                else:
                    print(f"WTF is '{directory_path+f}'")
            return files_in_directory
        if self.application.current_project_root is None:
            return []

        files = get_files(self.application.current_project_root_str)
        cprs_len = len(self.application.current_project_root_str) + 1
        return [f[cprs_len:] for f in files]


class SearchBar(QLineEdit):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.application = parent

        self.autocomplete_model = QStandardItemModel()
        self.completer = QCompleter()
        self.completer.setMaxVisibleItems(5)
        self.completer.setModel(self.autocomplete_model)

        ide_state_completion_mode = self.application.ide_state.get("search_completion", "popup")

        completion_mode = {
            'popup': QCompleter.PopupCompletion,
            'inline': QCompleter.InlineCompletion
        }.get(ide_state_completion_mode, QCompleter.PopupCompletion)
        self.completer.setCompletionMode(completion_mode)

        if completion_mode == QCompleter.PopupCompletion:
            bgc = self.application.ide_state.get("background_window_color", "#333333")
            fgc = self.application.ide_state.get("foreground_window_color", "#aaaaaa")

            self.completer.popup().setStyleSheet(
                f"background-color: {bgc};"
                f"color: {fgc};"
            )

        self.setCompleter(self.completer)
        self.set_data()

        self.returnPressed: pyqtBoundSignal
        self.returnPressed.connect(self.entered)
        self.completer.activated.connect(self.activated)

    def set_data(self):
        if self.application.current_project_root is None:
            return

        files = self.application.tree.get_files_as_strings()

        while self.autocomplete_model.rowCount() > 0:
            self.autocomplete_model.takeRow(0)

        for f in files:
            self.autocomplete_model.appendRow(QStandardItem(f))

    def activated(self):
        fp = self.application.current_project_root_str
        if not fp.endswith(os.sep):
            fp += os.sep
        fp_l = self.text()
        if os.path.exists(fp + fp_l) and os.path.isfile(fp + fp_l):
            self.application.open_file(filepath=fp + fp_l)

        self.setText("")
        self.application.code_window.setFocus()

    def entered(self):
        self.setText(self.completer.currentCompletion())
        self.activated()

    def next_completion(self):
        index = self.completer.currentIndex()
        self.completer.popup().setCurrentIndex(index)
        start = self.completer.currentRow()
        if not self.completer.setCurrentRow(start + 1):
            self.completer.setCurrentRow(0)

    def event(self, event):
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Tab:
            self.next_completion()
            return True

        return super().event(event)


class SaveFilesOnCloseDialog(QDialog):
    def __init__(self, parent=None, files=None):
        super().__init__(parent)

        self.setWindowTitle("Save Before Quitting?")

        q_btn = QDialogButtonBox.Yes | QDialogButtonBox.No | QDialogButtonBox.Cancel

        self.buttonBox = QDialogButtonBox(q_btn)
        self.buttonBox.clicked.connect(self.button_clicked)

        self.layout = QVBoxLayout()

        label_string = "The following file(s) have not been saved: \n\n"
        label_string += "\n\t".join(files)
        label_string += "\n\nSave before quitting?"

        message = QLabel(label_string)

        self.layout.addWidget(message)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)

        self.response = None

    def button_clicked(self, button: QPushButton):
        self.response = button.text().replace("&", "")  # remove mnemonic part
        self.accept()


class CLOCDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("External Command 'cloc' Output")

        q_btn = QDialogButtonBox.Ok

        self.buttonBox = QDialogButtonBox(q_btn)
        self.buttonBox.accepted.connect(self.accept)

        self.layout = QVBoxLayout()
        self.message_header = QLabel("Line counting for " + parent.current_project_root_str)
        self.message = QLabel()
        self.message.setFont(QFont("Courier New", 10))
        self.layout.addWidget(self.message_header)
        self.layout.addWidget(self.message)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)

    def set_content(self, content):
        content = content.split("\n")
        content = "\n".join(content)

        self.message.setText(content)
