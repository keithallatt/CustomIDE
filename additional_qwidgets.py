"""
Additional QWidgets, placed here to make the code in ./custom_ide.py cleaner.

Uses code from https://stackoverflow.com/questions/40386194/create-text-area-textedit-with-line-number-in-pyqt
QLineNumberArea and QCodeEditor courtesy of @ acbetter, @ Dan-Dev, and @ Axel Schneider

Uses code from https://stackoverflow.com/questions/7339685/how-to-rotate-a-qpushbutton
RotatedButton courtesy of @ Ulrich Dangel

Code has been modified to fit specific needs / wants.
- Allowed colors to be read in from files specified in ide_state.json for example
- made rotated buttons not look as bloated. May be an issue on some systems but it works great for me.
"""
from __future__ import annotations
import inspect
import logging
import os
import re
import tempfile
import warnings

from PyQt5.QtCore import Qt, QRect, QSize, pyqtBoundSignal, QEvent, QStringListModel
from PyQt5.QtGui import (QColor, QPainter, QTextFormat, QMouseEvent, QTextCursor, QStandardItemModel,
                         QStandardItem, QFont, QCursor, QKeySequence)
from PyQt5.QtWidgets import (QWidget, QPlainTextEdit, QTextEdit, QPushButton, QStyle, QTabWidget, QTreeView, QDialog,
                             QDialogButtonBox, QVBoxLayout, QLabel, QLineEdit, QCompleter, QScrollArea, QMenu,
                             QApplication, QGridLayout)

import syntax
from linting import LintingHelper

logging.basicConfig(filename='debug_logger.log', level=logging.DEBUG)


class FindAndReplaceWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.application = parent

        layout = QGridLayout()

        self.find_label = QLabel("Find:")
        self.replace_label = QLabel("Replace:")

        self.find_line = QLineEdit(self)
        self.replace_line = QLineEdit(self)

        self.find_line.textChanged.connect(self.find_edit_changed)

        self.find_next_button = QPushButton("Find", self)
        self.replace_button = QPushButton("Replace", self)
        self.replace_all_button = QPushButton("Replace All", self)

        self.hide_this = QPushButton("x", self)

        self.find_next_button.clicked.connect(self.find_button_pushed)
        self.replace_button.clicked.connect(self.replace_button_pushed)
        self.replace_all_button.clicked.connect(self.replace_all_button_pushed)

        def hide_this_function():
            self.hide()
            self.application.code_window.setFocus()

        self.hide_this.clicked.connect(hide_this_function)

        self.hide_this.setShortcut(QKeySequence("Esc"))

        self.info_label = QLabel("0/0")

        layout.addWidget(self.find_label, 0, 0, 1, 1)
        layout.addWidget(self.replace_label, 1, 0, 1, 1)

        layout.addWidget(self.find_line, 0, 1, 1, 1)
        layout.addWidget(self.replace_line, 1, 1, 1, 1)

        layout.addWidget(self.find_line, 0, 1, 1, 1)
        layout.addWidget(self.replace_line, 1, 1, 1, 1)

        layout.addWidget(self.info_label, 0, 2, 1, 2)
        layout.addWidget(self.find_next_button, 1, 2, 1, 1)
        layout.addWidget(self.replace_button, 1, 3, 1, 1)
        layout.addWidget(self.replace_all_button, 1, 4, 1, 1)
        layout.addWidget(self.hide_this, 0, 4, 1, 1)

        self.setLayout(layout)

        self.occurrence_index = 0
        self.num_occurrences = 0

        self.hide()

    @staticmethod
    def find_nth(haystack, needle, n):
        start = haystack.find(needle)
        while start >= 0 and n > 1:
            start = haystack.find(needle, start + len(needle))
            n -= 1
        return start

    def find_edit_changed(self, new_text):
        if new_text:
            self.occurrence_index = 0
            self.num_occurrences = self.application.code_window.toPlainText().count(new_text)
        else:
            self.occurrence_index = 0
            self.num_occurrences = 0

        self.find_button_pushed()
        self.info_label.setText(f"{self.occurrence_index}/{self.num_occurrences}")

    def find_button_pushed(self):
        if not self.num_occurrences:
            return

        self.occurrence_index += 1
        if self.occurrence_index > self.num_occurrences:
            self.occurrence_index = 1

        document_text = self.application.code_window.toPlainText()
        to_find = self.find_line.text()
        nth = self.occurrence_index
        string_index = FindAndReplaceWidget.find_nth(document_text, to_find, nth)

        tc = self.application.code_window.textCursor()
        tc.setPosition(string_index)
        tc.setPosition(string_index + len(to_find), QTextCursor.KeepAnchor)
        self.application.code_window.setTextCursor(tc)

        self.info_label.setText(f"{self.occurrence_index}/{self.num_occurrences}")

    def replace_button_pushed(self):
        if not self.num_occurrences:
            return

        to_find_text = self.find_line.text()
        tc = self.application.code_window.textCursor()

        selected_text = self.application.code_window.toPlainText()[tc.selectionStart():tc.selectionEnd()]

        if to_find_text != selected_text:
            self.occurrence_index -= 1
            self.find_button_pushed()

        tc = self.application.code_window.textCursor()
        to_replace_text = self.replace_line.text()

        tc.insertText(to_replace_text)
        self.application.code_window.setTextCursor(tc)
        self.num_occurrences = self.application.code_window.toPlainText().count(to_find_text)
        self.occurrence_index -= 1

        if self.num_occurrences:
            self.find_button_pushed()
        else:
            self.info_label.setText("0/0")
        pass

    def replace_all_button_pushed(self):
        tc = self.application.code_window.textCursor()
        tc.beginEditBlock()

        all_text = self.application.code_window.toPlainText()
        to_find_text = self.find_line.text()
        current_selection_index = FindAndReplaceWidget.find_nth(all_text, to_find_text, self.occurrence_index)

        all_before, all_after = all_text[:current_selection_index], all_text[current_selection_index:]

        to_replace_text = self.replace_line.text()

        tc.setPosition(len(all_before))
        tc.setPosition(len(all_before) + len(all_after), QTextCursor.KeepAnchor)

        all_after = all_after.replace(to_find_text, to_replace_text)

        self.num_occurrences = all_before.count(to_find_text)
        self.occurrence_index = 1 if self.num_occurrences else 0

        self.info_label.setText(f"{self.occurrence_index}/{self.num_occurrences}")

        tc.insertText(all_after)
        self.application.code_window.setTextCursor(tc)

        if to_find_text in all_before:
            dial = QDialog(self)
            dial.setWindowTitle("Replace All")

            button_box = QDialogButtonBox(QDialogButtonBox.Yes | QDialogButtonBox.No)

            def replace_again_and_accept(before):
                self.occurrence_index -= 1

                tc.setPosition(0)
                tc.setPosition(len(before), QTextCursor.KeepAnchor)

                _all_before = before.replace(to_find_text, to_replace_text)

                self.num_occurrences = _all_before.count(to_find_text)
                self.occurrence_index = 1 if self.num_occurrences else 0

                self.info_label.setText(f"{self.occurrence_index}/{self.num_occurrences}")

                tc.insertText(_all_before)

                dial.accept()

            def dont_replace_and_reject():
                self.find_button_pushed()
                dial.reject()

            button_box.accepted.connect(lambda: replace_again_and_accept(all_before))
            button_box.rejected.connect(dont_replace_and_reject)

            layout = QVBoxLayout()
            message = QLabel("Continue replacing from the beginning?")
            layout.addWidget(message)
            layout.addWidget(button_box)
            dial.setLayout(layout)
            dial.exec()

        tc.endEditBlock()
        self.application.code_window.setTextCursor(tc)


class QLineNumberArea(QWidget):
    """ The line numbers that accompany the QCodeEditor class. """

    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor
        self.setToolTip("tooltip")
        self.setMouseTracking(True)
        self.hovering = False
        self.current_code = None
        self.current_message = None

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.code_editor.line_number_area_paint_event(event)

    def enterEvent(self, event):
        self.hovering = True

    def leaveEvent(self, event):
        self.hovering = False

    def mouseMoveEvent(self, a0: QMouseEvent):
        if not self.hovering:
            return

        y = a0.y()
        hovering_on = y // self.code_editor.font_height + self.code_editor.verticalScrollBar().value() + 1
        tooltip = self.code_editor.line_number_area_linting_tooltips.get(hovering_on, '')
        self.setToolTip(tooltip)

        self.current_code = None
        self.current_message = None

        if not tooltip:
            return

        m = re.search(r"(C|R|W|E|F)\d{4}", tooltip)
        if m is None:
            return

        # If any error, then consider putting in a try-catch, setting both to None again.
        self.current_code = m.group(0)
        self.current_message = tooltip.split(self.current_code)[0][:-1].strip()

    def mousePressEvent(self, a0: QMouseEvent):
        if self.current_code is None:
            return

        application = self.code_editor.application
        linting_worker = application.linting_worker

        linting_helper = LintingHelper(application, linting_worker, self.current_message, self.current_code)
        linting_helper.exec()


class QCodeEditor(QPlainTextEdit):
    """ The main text editor of the IDE """
    ProgrammingMode = 0
    RawTextInput = 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lint_width = 5

        self.lineNumberArea = QLineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.update_line_number_area_width(0)

        self.linting_results = []
        self.line_number_area_linting_tooltips = {}

        self.linting_colors = {
            'refactor': QColor("#765432"),
            'convention': QColor("#222266"),
            'warning': QColor("#99aa22"),
            'error': QColor("#ee3322"),
        }

        self.linting_severities = [
            'convention', 'refactor', 'warning', 'error'
        ]

        self.application = parent
        self.font_height = 10  # approximate until starts drawing

        self.text_input_mode = QCodeEditor.RawTextInput

        self._completer = None
        self.auto_complete_dict = dict()
        self.all_autocomplete = []
        # Class Instances
        self.completion_prefix = ''

        self.string_locations = []

    def keyPressEvent(self, event):
        if self.text_input_mode == QCodeEditor.RawTextInput:
            return QPlainTextEdit.keyPressEvent(self, event)

        if type(self.application.highlighter) == syntax.JSONHighlighter:
            return self.non_auto_complete_key_event(event)

        # if deleting, preserve old locations, updates more in non_auto_complete_key_event
        if event.key() == Qt.Key_Backspace:
            self.string_locations += self.application.highlighter.string_locations
        else:
            self.string_locations = self.application.highlighter.string_locations

        is_shortcut = False

        if self._completer is not None and self._completer.popup().isVisible():
            # The following keys are forwarded by the completer to the widget.
            if event.key() in [Qt.Key_Enter, Qt.Key_Return, Qt.Key_Escape, Qt.Key_Tab, Qt.Key_Backtab]:
                # Let the completer do default behavior.
                event.ignore()
                return

        if self._completer is None or not is_shortcut:
            self.non_auto_complete_key_event(event)

        ctrl_or_shift = event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier)

        if self._completer is None or (ctrl_or_shift and len(event.text()) == 0):
            return

        if self._completer.popup().isVisible():
            if event.key() == Qt.Key_Q and event.modifiers() == Qt.ControlModifier:
                # was weird sigsev at one point, if happens again, look into it.
                QApplication.exit(0)

        eow = "~!@#$%^&*()_+{}|:\"<>?,./;'[]\\-="
        has_modifier = (event.modifiers() != Qt.NoModifier) and not ctrl_or_shift

        completion_prefix = self.text_under_cursor()
        self.completion_prefix = completion_prefix

        if not is_shortcut and (has_modifier or len(event.text()) == 0 or
                                len(completion_prefix) < 1 or event.text()[-1] in eow):
            self._completer.popup().hide()
            return

        if completion_prefix != self._completer.completionPrefix():
            # Puts the Prefix of the word you're typing into the Prefix
            # print("setting prefix: ", repr(completion_prefix))
            self._completer.setCompletionPrefix(completion_prefix)
            self._completer.popup().setCurrentIndex(
                self._completer.completionModel().index(0, 0))

        cr = self.cursorRect()
        cr.setWidth(self._completer.popup().sizeHintForColumn(0) +
                    self._completer.popup().verticalScrollBar().sizeHint().width())

        tc = self.textCursor()
        inside_string = False
        tc_pos = tc.position()

        self.string_locations += self.application.highlighter.string_locations

        for tup in self.string_locations:
            if tup[0] <= tc_pos <= tup[1]:
                inside_string = True
                break

        if inside_string:
            self._completer.popup().hide()
        else:
            self._completer.complete(cr)

    def non_auto_complete_key_event(self, event):
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
            if event.modifiers() == Qt.ShiftModifier:
                tc.setPosition(len(self.toPlainText()), QTextCursor.KeepAnchor)
            else:
                tc.setPosition(len(self.toPlainText()))
            self.setTextCursor(tc)
            return
        if event.key() == Qt.Key_Up and tc.blockNumber() == 0:
            # right the beginning
            if event.modifiers() == Qt.ShiftModifier:
                tc.setPosition(0, QTextCursor.KeepAnchor)
            else:
                tc.setPosition(0)
            self.setTextCursor(tc)
            return

        # prevent shift-return from making extra newlines in a block (block = line in this case)
        if event.key() == Qt.Key_Return:
            current_line = self.toPlainText().split("\n")[tc.blockNumber()][:tc.positionInBlock()]

            m = re.match(r"\s*", current_line)
            whitespace = m.group(0)
            whitespace = whitespace.replace("\t", "    ")  # 4 spaces per tab if they somehow get in there.

            if current_line[:tc.positionInBlock()].endswith(":"):
                whitespace += "    "
            elif current_line.lstrip().startswith('return') and whitespace:
                whitespace = whitespace[:-4]

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
                tc.setPosition(e + 1)
                tc.insertText(matching_str[1])

                tc.setPosition(s + 1)
                tc.setPosition(e + 1, QTextCursor.KeepAnchor)
                self.setTextCursor(tc)

                return

        # for matching close ), ], }
        if event.key() in matching_closing:
            pos = tc.position()
            next_1 = self.toPlainText()[pos:pos + 1]

            if next_1 and ord(next_1) == event.key():
                tc.setPosition(pos + 1)
                self.setTextCursor(tc)
                return

        if event.key() in need_to_match_strings.keys():
            matching_str = need_to_match_strings[event.key()]

            if tc.selectionStart() == tc.selectionEnd():

                tc.insertText(matching_str[0])
                self.setTextCursor(tc)
                pos = tc.position()

                last_3 = self.toPlainText()[max(0, pos - 3):pos]
                last_3_1_before = self.toPlainText()[max(0, pos - 4):pos - 1]

                if last_3 in ["'''", '"""'] and last_3_1_before not in ["'''", '"""']:
                    tc.insertText(last_3)
                    tc.setPosition(pos)
                else:
                    next_1 = self.toPlainText()[pos:pos + 1]
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
                tc.setPosition(e + 1)
                tc.insertText(matching_str[1])

                tc.setPosition(s + 1)
                tc.setPosition(e + 1, QTextCursor.KeepAnchor)
                self.setTextCursor(tc)

                return

        # if the delete key is pressed, then check for "|" or like (|)
        if event.key() == Qt.Key_Backspace:
            self.application.highlighter.rehighlightBlock(tc.block())
            pos = tc.position()
            prev_and_next = self.toPlainText()[max(0, pos - 1):pos + 1]
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
                line_len = len(current_line)
                if line_len:
                    for i in range((line_len - 1) % 4 + 1):
                        tc.deletePreviousChar()
                    self.setTextCursor(tc)
                    return

        if event.key() == Qt.Key_Slash and event.modifiers() == Qt.ControlModifier:
            start_pos = tc.selectionStart()
            end_pos = tc.selectionEnd()

            tc.setPosition(start_pos)
            start_line = tc.blockNumber()
            start_line_pos = start_pos - tc.positionInBlock()
            tc.setPosition(end_pos)
            end_line = tc.blockNumber()

            tc.setPosition(start_pos)
            lines_to_comment = self.document().toPlainText().split("\n")[start_line: end_line + 1]

            # length of all lines + (len(lines_to_comment) - 1) which is number of newlines
            length_of_text = sum(map(len, lines_to_comment)) + len(lines_to_comment) - 1

            tc.setPosition(start_line_pos)
            tc.setPosition(start_line_pos + length_of_text, QTextCursor.KeepAnchor)

            min_indent = min(map(lambda x: len(x) - len(x.lstrip(' ')), lines_to_comment))
            is_currently_commented = all(len(x) > min_indent and x.lstrip(' ')[0] == "#" for x in lines_to_comment)

            if is_currently_commented:
                lines_uncommented = []
                for line in lines_to_comment:
                    if line.lstrip(' ').startswith("# "):
                        lines_uncommented.append(line.replace('# ', '', 1))
                    elif line.lstrip(' ').startswith("#"):
                        lines_uncommented.append(line.replace('#', '', 1))
                    else:
                        warnings.warn(f"Line was meant to be commented but wasn't: {line}")

                to_replace_with = "\n".join(lines_uncommented)
            else:
                def insert_into(wrapper, to_insert, index):
                    return wrapper[:index] + to_insert + wrapper[index:]

                to_replace_with = "\n".join(map(lambda x: insert_into(x, "# ", min_indent), lines_to_comment))

            tc.insertText(to_replace_with)
            tc.setPosition(start_line_pos)
            tc.setPosition(start_line_pos + len(to_replace_with), QTextCursor.KeepAnchor)

            self.setTextCursor(tc)
            return

        # for debug purposes. Will be removed in the final version
        print_possible_keys = False
        if print_possible_keys:
            possible_keys = []
            for member, value in inspect.getmembers(Qt):
                if member.startswith("Key_"):
                    if value == event.key():
                        possible_keys.append(member)
            print(possible_keys)

        return QPlainTextEdit.keyPressEvent(self, event)

    def line_number_area_width(self):
        digits = len(str(self.blockCount()))  # get number of characters in the last value.
        space = 3 + self.fontMetrics().width('9') * digits
        return space + self.lint_width

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
        extra_selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            line_color = QColor()
            line_color.setNamedColor(self.application.ide_theme["line_highlight_color"])
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
        ide_theme = self.application.ide_theme
        window_color = QColor(ide_theme['background_window_color'])
        line_color = QColor(ide_theme['line_number_color'])

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

                severity = -3
                for lint_result in self.linting_results:
                    if lint_result['line_number'] == block_number + 1:
                        lint_kind_severity = -1
                        if lint_result['kind'] in self.linting_severities:
                            lint_kind_severity = self.linting_severities.index(lint_result['kind'])

                        lint_message = lint_result['message'] + " " + lint_result['lint_code']

                        if lint_kind_severity >= severity:
                            self.line_number_area_linting_tooltips[block_number + 1] = lint_message
                            severity = lint_kind_severity

                if severity < 0:
                    lint_kind = ""
                    self.line_number_area_linting_tooltips[block_number + 1] = ''
                else:
                    lint_kind = self.linting_severities[severity]

                lint_color = self.linting_colors.get(lint_kind, window_color)

                painter.fillRect(0, int(top), self.lint_width, int(height), lint_color)
                painter.fillRect(self.lint_width, int(top), int(self.lineNumberArea.width()) - self.lint_width,
                                 int(height), window_color)

                painter.setPen(line_color)
                painter.drawText(0, int(top), int(self.lineNumberArea.width()), int(height), Qt.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    # Auto complete part.

    def set_completer(self, c):
        self._completer = c
        c.setWidget(self)
        c.setCompletionMode(QCompleter.PopupCompletion)
        c.setCaseSensitivity(Qt.CaseSensitive)
        c.activated.connect(self.insert_completion)

    def insert_completion(self, completion):
        if self._completer.widget() is not self:
            return

        tc = self.textCursor()
        extra = len(completion) - len(self._completer.completionPrefix())
        tc.movePosition(QTextCursor.Left)
        tc.movePosition(QTextCursor.EndOfWord)

        if completion in self.auto_complete_dict.keys():
            tc.setPosition(tc.position() - len(self._completer.completionPrefix()), QTextCursor.KeepAnchor)
            tc.insertText(self.auto_complete_dict[completion])
        elif self.completion_prefix.lower() != completion[-extra:].lower():
            tc.insertText(completion[-extra:])
            self.setTextCursor(tc)
            self._completer.setModel(QStringListModel(self.all_autocomplete, self._completer))

    def text_under_cursor(self):
        tc = self.textCursor()

        # inside_string = False
        # tc_pos = tc.position()
        #
        # for tup in self.application.highlighter.string_locations:
        #     if tup[0] <= tc_pos <= tup[1]:
        #         inside_string = True
        #         break
        # if inside_string:
        #     return ""

        tc.movePosition(QTextCursor.Left)
        tc_pos = tc.position()

        tc.select(QTextCursor.WordUnderCursor)
        s, e = tc.selectionStart(), tc.selectionEnd()

        if s <= tc_pos < e:
            return tc.selectedText()
        else:
            return ""

    def focusInEvent(self, e):
        # Open the widget where you are at in the edit
        if self._completer is not None:
            self._completer.setWidget(self)
        super(QCodeEditor, self).focusInEvent(e)


class QCodeFileTabs(QTabWidget):
    """ The tabbed view at the top of the code editor. """

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

        # self.setTabShape(QTabWidget.TabShape.Triangular)

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
            self.temp_files.update({last_tab: tempfile.mkstemp(suffix=last_tab[last_tab.index('.'):])[1]})
        last_temp_file = self.temp_files[last_tab]
        code_to_save = self.application.code_window.toPlainText()
        open(last_temp_file, 'w').write(code_to_save)
        return last_temp_file

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
        self.application.code_window.linting_results = []  # remove linting results
        self.application.code_window.line_number_area_linting_tooltips = dict()
        self.application.code_window.lineNumberArea.setToolTip('')
        self.application.code_window.repaint()

        self.application.code_window.setPlainText(open(next_temp_file, 'r').read())

        self.last_tab_index = index
        self._last_file_selected = next_tab

    def set_syntax_highlighter(self, filename: str = None):
        if filename is None:
            current_widget = self.currentWidget()
            for k, v in self.tabs.items():
                if v == current_widget:
                    filename = k
                    break
            else:
                # should then go on to set the highlighter to None and then set the raw text input mode.
                filename = "unspecified"

        # set appropriate syntax highlighter
        self.application.highlighter = {
            ".py": syntax.PythonHighlighter,
            ".json": syntax.JSONHighlighter
        }.get(
            "unspecified" if '.' not in filename else filename[filename.index('.'):], lambda *_: None
        )(self.application.code_window.document(), self.application)

        if self.application.highlighter is None:
            self.application.code_window.text_input_mode = QCodeEditor.RawTextInput
        else:
            self.application.code_window.text_input_mode = QCodeEditor.ProgrammingMode


class ProjectViewer(QTreeView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.application = parent

    def mousePressEvent(self, event):
        QTreeView.mousePressEvent(self, event)
        if event.button() == Qt.RightButton:
            top_menu = QMenu(self.application)

            menu = top_menu.addMenu("Menu")

            open_action = menu.addAction("Open File")
            copy_filepath_action = menu.addAction("Copy Filepath")
            rename_action = menu.addAction("Rename File")
            delete_action = menu.addAction("Delete File")

            action = menu.exec_(QCursor.pos())

            if action == open_action:
                self.application.open_file()
            elif action == delete_action:
                self.application.delete_file()
            elif action == rename_action:
                self.application.rename_file()
            elif action == copy_filepath_action:
                QApplication.clipboard().setText(self.application.get_file_from_viewer())

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return:
            self.application.open_file()

        # self.get_files_as_strings()

        return QTreeView.keyPressEvent(self, event)

    def get_files_as_strings(self):
        def get_files(directory_path):
            if directory_path.split(os.sep)[-1] == "venv":
                return []

            files_in_directory = []
            if not directory_path.endswith(os.sep):
                directory_path += os.sep
            for f in os.listdir(directory_path):
                if os.path.isdir(directory_path + f):
                    files_in_directory += get_files(directory_path + f)
                elif os.path.isfile(directory_path + f):
                    files_in_directory.append(directory_path + f)
                else:
                    logging.info(f"File {directory_path + f} is not dir nor file? Called with root "
                                 f"directory {self.application.current_project_root_str}")

            return files_in_directory

        if self.application.current_project_root is None:
            return []

        files = get_files(self.application.current_project_root_str)
        project_root_str_len = len(self.application.current_project_root_str)
        if not self.application.current_project_root_str.endswith(os.sep):
            project_root_str_len += 1
        return [f[project_root_str_len:] for f in files]


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

        def button_clicked(button: QPushButton):
            self.response = button.text().replace("&", "")  # remove mnemonic part
            self.accept()

        self.buttonBox.clicked.connect(button_clicked)

        self.layout = QVBoxLayout()

        label_string = "The following file(s) have not been saved: \n\n"
        label_string += "\n\t".join(files)
        label_string += "\n\nSave before quitting?"

        message = QLabel(label_string)

        self.layout.addWidget(message)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)

        self.response = None


class CommandLineCallDialog(QDialog):
    def __init__(self, command_line_function: str, header_str: str, parent=None):
        super().__init__(parent)

        self.setWindowTitle(f"{command_line_function}")

        q_btn = QDialogButtonBox.Ok

        self.buttonBox = QDialogButtonBox(q_btn)
        self.buttonBox.accepted.connect(self.accept)

        self.layout = QVBoxLayout()
        self.message_header = QLabel(header_str)
        self.message = QLabel()
        self.message.setFont(QFont("Courier New", 10))

        self.scrollArea = QScrollArea(self)
        self.scrollArea.setWidgetResizable(True)
        content = QWidget(self)
        self.scrollArea.setWidget(content)
        lay = QVBoxLayout(content)
        self.message.setWordWrap(True)
        lay.addWidget(self.message)

        self.layout.addWidget(self.message_header)
        self.layout.addWidget(self.scrollArea)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)
        self.resize(900, 400)

        self.set_content = self.message.setText
