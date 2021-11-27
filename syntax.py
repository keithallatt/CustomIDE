"""
syntax.py -> https://wiki.python.org/moin/PyQt/Python%20syntax%20highlighting

Modified the syntax.py from the python wiki to recognize keywords, read colors from
a JSON file, and generally make it more readable.

Also updated as the original looked like it did not handle things such as:
- highlighting keyword arguments
- highlighting the b/f/r/u string prefixes for bytes, f-strings, raw strings and unicode.
- highlighting builtin operators such as 'str' and 'int'
- escape sequences
- a few other small features
"""
import re

from PyQt5 import QtCore, QtGui
from json import loads, dumps
from re import escape
import builtins
import inspect
import os
import keyword

from PyQt5.QtGui import QColor


def format_color(color, style=''):
    """ Return a QTextCharFormat with the given attributes. """
    _color = QColor()
    _color.setNamedColor(color)

    _format = QtGui.QTextCharFormat()
    _format.setForeground(_color)

    if 'bold' in style:
        _format.setFontWeight(QtGui.QFont.Bold)
    if 'italic' in style:
        _format.setFontItalic(True)

    return _format


# syntax styles like for keywords or for operators / built-ins.
STYLES = dict()


def reset_styles(ide_state: dict = None):
    global STYLES

    if ide_state is None:
        ide_state = loads(open("ide_state.json", 'r').read())

    syntax_highlighter_filepath = f"syntax_highlighters{os.sep}{ide_state['syntax_highlighter']}"

    if not os.path.exists(syntax_highlighter_filepath):
        for file in os.listdir("./syntax_highlighters"):
            ide_state['ide_theme'] = file
            syntax_highlighter_filepath = f"ide_themes{os.sep}{file}"
            break
        else:
            from theme_editor import DEFAULT_SYNTAX_HIGHLIGHTER
            default_theme = dumps(DEFAULT_SYNTAX_HIGHLIGHTER, indent=2)
            syntax_highlighter_filepath = f"syntax_highlighters{os.sep}default.json"
            with open(syntax_highlighter_filepath, 'w') as f:
                f.write(default_theme)
            ide_state['ide_theme'] = "default.json"
            STYLES = {k: format_color(*v) for k, v in DEFAULT_SYNTAX_HIGHLIGHTER.items()}
            return

    STYLES = {
        k: format_color(*v) for k, v in loads(
            open(syntax_highlighter_filepath, 'r').read()
        ).items()
    }


reset_styles()


class PythonHighlighter(QtGui.QSyntaxHighlighter):
    """Syntax highlighter for the Python language. """

    # Python keywords
    keywords = keyword.kwlist

    # Python operators
    operators = list(map(escape, [
        '=',
        # Comparison
        '==', '!=', '<', '<=', '>', '>=',
        # Arithmetic
        '+', '-', '*', '/', '//', '%', '**',
        # In-place
        '+=', '-=', '*=', '/=', '%=',
        # Bitwise
        '^', '|', '&', '~', '>>', '<<',
        # In-place bitwise
        '^=', '|=', '&=', '~=', '>>=', '<<='
    ]))

    escape_sequences = list(map(escape, [
        r"\\", r"\'", r"\"", r"\n", r"\r", r"\t", r"\b", r"\f"
    ])) + [  # more general ones.
        r"\\[0-7]{3}",  # octal escape
        r"\\h[0-9A-Fa-f]{2}",  # hex escape
        r"\\u[0-9A-Fa-f]{4}",  # unicode escape
    ]

    # Python braces
    braces = list(map(escape, list("()[]{}")))

    # Python builtins
    built_ins = list(filter(lambda x: x not in ["True", "False", "None"],
                            map(lambda x: x[0], inspect.getmembers(builtins))))

    def __init__(self, parent: QtGui.QTextDocument, ide_object) -> None:
        super().__init__(parent)
        # things for like f"thing {var}" or r"raw string"
        self.string_prefix_regex = r"(r|u|R|U|f|F|fr|Fr|fR|FR|rf|rF|Rf|RF|b|B|br|Br|bR|BR|rb|rB|Rb|RB)?"

        # Multi-line strings (expression, flag, style)
        self.tri_single = (QtCore.QRegExp(self.string_prefix_regex + "'''"), 1, STYLES['string2'])
        self.tri_double = (QtCore.QRegExp(self.string_prefix_regex + '"""'), 2, STYLES['string2'])

        self.triple_quotes_within_strings = []

        self.linting_results = []
        # should be same as in additional_qwidgets.py but yk easy solution for now,
        # maybe a little brighter on some
        self.linting_colors = {
            'refactor': QColor("#765432"),
            'convention': QColor("#555599"),
            'warning': QColor("#99aa22"),
            'error': QColor("#ee3322"),
        }

        self.string_locations = []
        self._string_locations = []

        rules = []

        # Keyword, operator, and brace rules
        rules += [(rf'\b{w}\b', 0, STYLES['keyword'])
                  for w in PythonHighlighter.keywords]
        rules += [(f'{o}', 0, STYLES['operator'])
                  for o in PythonHighlighter.operators]
        rules += [(f'{b}', 0, STYLES['brace'])
                  for b in PythonHighlighter.braces]

        # kwargs needs to be before builtins. This way
        # for things like def 'foo(x: str = 3):', the type hint will still appear highlighted
        rules += [
            # kwargs -> need to figure out properly once and for all.

            # gets rid of them in function definitions (returns to default editor color.)
            (r'\bdef\b\s*[a-zA-Z_][a-zA-Z_0-9]*\s*\(.*([a-zA-Z_][a-zA-Z_0-9]*)\s*=[^=].*\)', 1,
             format_color(ide_object.ide_theme['foreground_window_color']))
        ]

        rules += [(rf'\b{b}\b', 0, STYLES['builtins'])
                  for b in PythonHighlighter.built_ins]

        # All other rules
        rules += [
            # 'self'
            (r'\bself\b', 0, STYLES['self']),

            # double underscore methods. place earlier so it gets overridden by other rules.
            (r'__[a-zA-z](\w)*__', 0, STYLES['double_under']),

            # 'def' followed by an identifier
            (r'\bdef\b\s*(\w+)', 1, STYLES['def_class']),
            # 'class' followed by an identifier
            (r'\bclass\b\s*(\w+)', 1, STYLES['def_class']),

            # Numeric literals
            (r'\b[+-]?[0-9]+[lLj]?\b', 0, STYLES['numbers']),
            (r'\b[+-]?0[xX][0-9A-Fa-f]+[lLj]?\b', 0, STYLES['numbers']),
            (r'\b[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\b', 0, STYLES['numbers']),

            # strings, possibly containing escape sequences
            (self.string_prefix_regex + r'"[^"\\]*(\\.[^"\\]*)*"', 0, STYLES['string']),

            # From '#' until a newline
            (r'#[^\n]*', 0, STYLES['comment']),

            # handling todos
            (r'# *todo *(\([^\n]+\))?\b[^\n]*', 0, STYLES['todo']),
            # handling todos
            (r'# *todo *\(([^\n]+)\)', 1, STYLES['todo_author']),
        ]

        rules += [(f'{b}', 0, STYLES['keyword'])
                  for b in PythonHighlighter.escape_sequences]

        # Build a QRegExp for each pattern
        self.rules = [(QtCore.QRegExp(pat), index, fmt)
                      for (pat, index, fmt) in rules]

    def highlightBlock(self, text):
        """Apply syntax highlighting to the given block of text. """
        self.triple_quotes_within_strings = []
        self._string_locations = []

        # Do other syntax formatting
        for expression, nth, format_ in self.rules:
            def get_index(input_text, start_at, ex=expression):
                if ex.pattern().startswith(self.string_prefix_regex):
                    second_pattern = ex.pattern().replace("\"", "'")
                    second_pattern = QtCore.QRegExp(second_pattern)

                    ind1 = ex.indexIn(input_text, start_at)
                    ind2 = second_pattern.indexIn(input_text, start_at)

                    if ind1 == -1:
                        return ind2, second_pattern
                    if ind2 == -1:
                        return ind1, ex

                    ex_to_return = ex if ind1 < ind2 else second_pattern

                    return min(ind1, ind2), ex_to_return
                else:
                    return ex.indexIn(input_text, start_at), ex

            index, exp_to_consider = get_index(text, 0)
            if index >= 0:
                # if there is a string we check if there are some triple quotes
                # within the string they will be ignored if they are matched again
                if expression.pattern() in [r'"[^"\\]*(\\.[^"\\]*)*"', r"'[^'\\]*(\\.[^'\\]*)*'"]:
                    inner_index = self.tri_single[0].indexIn(text, index + 1)
                    if inner_index == -1:
                        inner_index = self.tri_double[0].indexIn(text, index + 1)

                    if inner_index != -1:
                        triple_quote_indexes = range(inner_index, inner_index + 3)
                        self.triple_quotes_within_strings.extend(triple_quote_indexes)

            while index >= 0:
                # skipping triple quotes within strings
                if index in self.triple_quotes_within_strings:
                    index += 1
                    index, exp_to_consider = get_index(text, index)
                    continue

                # We actually want the index of the nth match
                index = exp_to_consider.pos(nth)
                length = len(exp_to_consider.cap(nth))

                format_after = True
                # string matching, if before the 'f' if statement, then for any string
                if exp_to_consider.pattern().startswith(self.string_prefix_regex):
                    # lhs bound and  rhs bound0
                    self._string_locations.append((self.currentBlock().position() + index,
                                                   self.currentBlock().position() + index + length))

                    f_string_line = text[index:index+length]
                    capture_group = exp_to_consider.cap(1)
                    if 'f' in capture_group.lower():
                        to_format = [0]

                        open_index = f_string_line.find("{")
                        close_index = f_string_line.find("}", open_index)
                        while open_index != -1 and close_index != -1:
                            inside_indices = f_string_line[open_index+1:close_index]

                            while inside_indices.count("{") - inside_indices.count("}"):
                                close_index = f_string_line.find("}", close_index + 1)
                                inside_indices = f_string_line[open_index+1:close_index]

                            to_format += [open_index, close_index+1]
                            open_index = f_string_line.find("{", close_index)
                            close_index = f_string_line.find("}", open_index)
                        to_format.append(len(f_string_line))
                        to_format = [(to_format[i], to_format[i + 1]) for i in range(0, len(to_format), 2)]

                        for tup in to_format:
                            self.setFormat(index + tup[0], tup[1] - tup[0], format_)
                            if tup[0]:
                                self.setFormat(index + tup[0] - 1, 1, STYLES['keyword'])
                            if tup[1] - len(f_string_line):
                                self.setFormat(index + tup[1], 1, STYLES['keyword'])
                        format_after = False

                if format_after:
                    self.setFormat(index, length, format_)
                index, exp_to_consider = get_index(text, index + length)

        self.setCurrentBlockState(0)
        # Do multi-line strings
        in_multiline = self.match_multiline(text, *self.tri_single)
        if not in_multiline:
            # in_multiline = self.match_multiline(text, *self.tri_double)
            self.match_multiline(text, *self.tri_double)

        # only resets after the entire highlighting process.
        # should prevent polling of string locations giving partial results.
        self.string_locations = self._string_locations

        line_number = self.currentBlock().blockNumber() + 1

        linting_results_for_line = list(filter(lambda x: x['line'] == line_number, self.linting_results))
        # print(line_number, linting_results_for_line)

        _color = QtGui.QColor()
        _color.setNamedColor("gray")
        line_text = self.currentBlock().text()

        for result in linting_results_for_line:
            position = result['column']
            # get line of text after index
            line_after_index = line_text[result['column']:].lstrip()  # remove whitespace for whole line ones,
            search_result = re.findall(r".+\b", line_after_index)
            if search_result:
                search_result = search_result[0]
                sr_len = len(search_result)
            else:
                sr_len = len(line_after_index)
                if not len(line_after_index) or position >= len(line_text):
                    position = len(line_text) - 1
                    sr_len = 1

            lint_color = self.linting_colors.get(result['type'], _color)

            for position_index in range(position, position + sr_len):
                _format = self.format(position_index)
                _format.setFontUnderline(True)
                _format.setUnderlineColor(lint_color)
                _format.setUnderlineStyle(QtGui.QTextCharFormat.UnderlineStyle.WaveUnderline)

                self.setFormat(position_index, 1, _format)

    def match_multiline(self, text, delimiter, in_state, style):
        """
        Do highlighting of multi-line strings. ``delimiter`` should be a
        ``QRegExp`` for triple-single-quotes or triple-double-quotes, and
        ``in_state`` should be a unique integer to represent the corresponding
        state changes when inside those strings. Returns True if we're still
        inside a multi-line string when this function is finished.
        """
        # If inside triple-single quotes, start at 0
        if self.previousBlockState() == in_state:
            start = 0
            add = 0
        # Otherwise, look for the delimiter on this line
        else:
            start = delimiter.indexIn(text)
            # skipping triple quotes within strings
            if start in self.triple_quotes_within_strings:
                return False
            # Move past this match
            add = delimiter.matchedLength()

        # As long as there's a delimiter match on this line...
        while start >= 0:
            # Look for the ending delimiter
            end = delimiter.indexIn(text, start + add)
            # Ending delimiter on this line?
            if end >= add:
                length = end - start + add + delimiter.matchedLength()
                self.setCurrentBlockState(0)
            # No; multi-line string
            else:
                self.setCurrentBlockState(in_state)
                length = len(text) - start + add

            # Apply formatting and set interval for docstrings
            self._string_locations.append((self.currentBlock().position() + start,
                                           self.currentBlock().position() + start + length))

            self.setFormat(start, length, style)
            # Look for the next match
            start = delimiter.indexIn(text, start + length)
        # Return whether we're still inside a multi-line string
        return self.currentBlockState() == in_state


class JSONHighlighter(QtGui.QSyntaxHighlighter):
    """Syntax highlighter for the JSON language. """

    def __init__(self, parent: QtGui.QTextDocument, _) -> None:
        super().__init__(parent)

        rules = [
            (r"\b[1-9][0-9]+\b", 0, STYLES['numbers']),
            (r"(\"[^\"]*\")\s*:", 1, STYLES['builtins']),
            (r":\s*(\"[^\"]*\")", 1, STYLES['string']),
            (r"(,|:)", 0, STYLES['keyword'])

        ]

        # Build a QRegExp for each pattern
        self.rules = [(QtCore.QRegExp(pat), index, fmt)
                      for (pat, index, fmt) in rules]

    def highlightBlock(self, text):
        """Apply syntax highlighting to the given block of text. """
        # Do other syntax formatting
        for expression, nth, format_ in self.rules:
            index = expression.indexIn(text, 0)

            while index >= 0:
                # We actually want the index of the nth match
                index = expression.pos(nth)
                length = len(expression.cap(nth))
                self.setFormat(index, length, format_)
                index = expression.indexIn(text, index + length)

        self.setCurrentBlockState(0)
