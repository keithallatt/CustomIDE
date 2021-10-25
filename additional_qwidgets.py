"""
Additional QWidgets, placed here to make application.py more clean.

Uses code from https://stackoverflow.com/questions/40386194/create-text-area-textedit-with-line-number-in-pyqt
QLineNumberArea and QCodeEditor courtesy of @ acbetter, @ Dan-Dev, and @ Axel Schneider

Uses code from https://stackoverflow.com/questions/7339685/how-to-rotate-a-qpushbutton
RotatedButton courtesy of @ Ulrich Dangel

Code has been modified to fit specific needs / wants.
- Allowed colors to be read in from ide_state.json for example
- made rotated buttons not look as bloated. May be an issue on some systems but it works great for me.
"""

from PyQt5.QtCore import Qt, QRect, QSize, QEvent
from PyQt5.QtGui import QColor, QPainter, QTextFormat, QMouseEvent
from PyQt5.QtWidgets import (QWidget, QPlainTextEdit,
                             QTextEdit, QPushButton, QStylePainter, QStyle,
                             QStyleOptionButton, QScrollBar)
from json import loads


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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineNumberArea = QLineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.update_line_number_area_width(0)

        self.linting_results = []
        self.line_number_area_linting_tooltips = {}

        self.font_height = 10  # approximate until starts drawwing

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Tab:
            tc = self.textCursor()
            tc.insertText("    ")
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
        ide_state = loads(open("ide_state.json", 'r').read())
        window_color = QColor(ide_state['background_window_color'])
        line_color = QColor(ide_state['line_number_color'])

        lint_colors = {
            "error": (QColor("#800000"), 3),
            "warning": (QColor("#808000"), 2),
            "convention": (QColor("#006010"), 1)
        }

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

                _color = window_color
                _severity = -1
                for result in self.linting_results:
                    if str(result['line_number']) == number:
                        color, severity = lint_colors.get(result['kind'], (line_color, 0))
                        if severity > _severity:
                            _color, _severity = color, severity
                            self.line_number_area_linting_tooltips.update({int(number): result['message']})

                painter.fillRect(0, int(top), int(self.lineNumberArea.width()), int(height), _color)

                painter.setPen(line_color)
                painter.drawText(0, int(top), int(self.lineNumberArea.width()), int(height), Qt.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1
