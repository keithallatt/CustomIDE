"""
syntax.py -> https://wiki.python.org/moin/PyQt/Python%20syntax%20highlighting

Modified the syntax.py from the python wiki to recognize keywords, read colors from
a JSON file, and generally make it more readable.

Also updated as the original looked like it did not handle things such as:
- highlighting keyword arguments
- highlighting the b/f/r/u string prefixes for bytes, f-strings, raw strings and unicode.
- highlighting builtin operators such as 'str' and 'int'
- handling todo's and todo authors.
"""
from PyQt5 import QtCore, QtGui
from json import loads
from re import escape
import builtins
import inspect
import os


def format_color(color, style=''):
    """ Return a QTextCharFormat with the given attributes. """
    _color = QtGui.QColor()
    _color.setNamedColor(color)

    _format = QtGui.QTextCharFormat()
    _format.setForeground(_color)
    if 'bold' in style:
        _format.setFontWeight(QtGui.QFont.Bold)
    if 'italic' in style:
        _format.setFontItalic(True)

    return _format


# syntax styles like for keywords or for operators / built-ins.
STYLES = {
    k: format_color(*v) for k, v in loads(
        open("syntax_highlighters" + os.sep +
             loads(open("ide_state.json", 'r').read())['syntax_highlighter_theme'], 'r').read()
    ).items()
}


class PythonHighlighter(QtGui.QSyntaxHighlighter):
    """Syntax highlighter for the Python language. """

    # Python keywords
    keywords = [
        'and', 'assert', 'break', 'class', 'continue', 'def',
        'del', 'elif', 'else', 'except', 'exec', 'finally',
        'for', 'from', 'global', 'if', 'import', 'in',
        'is', 'lambda', 'not', 'or', 'pass', 'print',
        'raise', 'return', 'try', 'while', 'yield',
        'None', 'True', 'False',
    ]

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

    # Python braces
    braces = list(map(escape, list("()[]{}")))

    # Python builtins
    built_ins = list(map(lambda x: x[0], inspect.getmembers(builtins)))

    def __init__(self, parent: QtGui.QTextDocument) -> None:
        super().__init__(parent)

        # things for like f"thing {var}" or r"raw string"
        string_prefix_regex = r"(r|u|R|U|f|F|fr|Fr|fR|FR|rf|rF|Rf|RF|b|B|br|Br|bR|BR|rb|rB|Rb|RB)?"
        fstring_prefix_regex = r"(f|F|fr|Fr|fR|FR|rf|rF|Rf|RF)"

        # Multi-line strings (expression, flag, style)
        self.tri_single = (QtCore.QRegExp(string_prefix_regex + "'''"), 1, STYLES['string2'])
        self.tri_double = (QtCore.QRegExp(string_prefix_regex + '"""'), 2, STYLES['string2'])

        self.triple_quotes_within_strings = []

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
            # kwargs-> needs testing
            (r'\(.*([a-zA-Z_][a-zA-Z_0-9]*)\s*=[^=].*\)', 1, STYLES['kwargs']),

            # gets rid of them in function definitions (returns to default editor color.)
            (r'\bdef\b\s*[a-zA-Z_][a-zA-Z_0-9]*\s*\(.*([a-zA-Z_][a-zA-Z_0-9]*)\s*=[^=].*\)', 1,
             format_color(loads(open("ide_state.json", 'r').read())['editor_font_color']))
        ]

        rules += [(rf'\b{b}\b', 0, STYLES['builtins'])
                  for b in PythonHighlighter.built_ins]

        # All other rules
        rules += [
            # 'self'
            (r'\bself\b', 0, STYLES['self']),

            # 'def' followed by an identifier
            (r'\bdef\b\s*(\w+)', 1, STYLES['defclass']),
            # 'class' followed by an identifier
            (r'\bclass\b\s*(\w+)', 1, STYLES['defclass']),

            # dunder methods. place earlier so it gets overridden by other rules.
            (r'__[a-zA-z](\w)*__', 0, STYLES['dunder']),

            # Numeric literals
            (r'\b[+-]?[0-9]+[lL]?\b', 0, STYLES['numbers']),
            (r'\b[+-]?0[xX][0-9A-Fa-f]+[lL]?\b', 0, STYLES['numbers']),
            (r'\b[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\b', 0, STYLES['numbers']),

            # Double-quoted string, possibly containing escape sequences
            (string_prefix_regex + r'"[^"\\]*(\\.[^"\\]*)*"', 0, STYLES['string']),
            # Single-quoted string, possibly containing escape sequences
            (string_prefix_regex + r"'[^'\\]*(\\.[^'\\]*)*'", 0, STYLES['string']),

            # From '#' until a newline
            (r'#[^\n]*', 0, STYLES['comment']),

            # handling todos
            (r'# *todo *(\([^\n]+\))?\b[^\n]*', 0, STYLES['todo']),
            # handling todos
            (r'# *todo *\(([^\n]+)\)', 1, STYLES['todo_author']),

            # f-string insides. (with { and } )
            # (fstring_prefix_regex + r'"[^\"]*(\{[^\}]*\})[^\"]*\"', 2, STYLES['keyword']),
            # (fstring_prefix_regex + r"'[^\']*(\{[^\}]*\})[^\']*\'", 2, STYLES['keyword']),

            # f-string insides. (inside { and } )
            # (fstring_prefix_regex + r'"[^\"]*\{([^\}]*)\}[^\"]*\"', 2, STYLES['operator']),
            # (fstring_prefix_regex + r"'[^\']*\{([^\}]*)\}[^\']*\'", 2, STYLES['operator']),
        ]

        # Build a QRegExp for each pattern
        self.rules = [(QtCore.QRegExp(pat), index, fmt)
                      for (pat, index, fmt) in rules]

    def highlightBlock(self, text):
        """Apply syntax highlighting to the given block of text. """
        self.triple_quotes_within_strings = []
        # Do other syntax formatting
        for expression, nth, format_ in self.rules:
            index = expression.indexIn(text, 0)
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
                    expression.indexIn(text, index)
                    continue

                # We actually want the index of the nth match
                index = expression.pos(nth)
                length = len(expression.cap(nth))
                self.setFormat(index, length, format_)
                index = expression.indexIn(text, index + length)

        self.setCurrentBlockState(0)

        # Do multi-line strings
        in_multiline = self.match_multiline(text, *self.tri_single)
        if not in_multiline:
            # in_multiline = self.match_multiline(text, *self.tri_double)
            self.match_multiline(text, *self.tri_double)

    def match_multiline(self, text, delimiter, in_state, style):
        """Do highlighting of multi-line strings. ``delimiter`` should be a
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
            # Apply formatting
            self.setFormat(start, length, style)
            # Look for the next match
            start = delimiter.indexIn(text, start + length)

        # Return whether we're still inside a multi-line string
        return self.currentBlockState() == in_state


class JSONHighlighter(QtGui.QSyntaxHighlighter):
    """Syntax highlighter for the JSON language. """

    def __init__(self, parent: QtGui.QTextDocument) -> None:
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

