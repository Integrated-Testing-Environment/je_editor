import importlib.util
import sys
from pathlib import Path
from typing import Union, List

import jedi
from PySide6 import QtGui
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPainter, QTextCharFormat, QTextFormat, QKeyEvent, QAction, QTextDocument, QTextCursor, \
    QKeySequence
from PySide6.QtWidgets import QPlainTextEdit, QWidget, QTextEdit, QCompleter
from jedi.api.classes import Completion

from je_editor.pyside_ui.code.syntax.python_syntax import PythonHighlighter
from je_editor.pyside_ui.dialog.search_ui.search_text_box import SearchBox
from je_editor.pyside_ui.main_ui.save_settings.user_color_setting_file import actually_color_dict


def venv_check():
    venv_path = Path(str(Path.cwd()) + "/venv")
    return venv_path


class CodeEditor(QPlainTextEdit):
    """
    Extend QPlainTextEdit,
    Add line, edit tab distance, add highlighter, add search text
    """

    def __init__(self):
        super().__init__()
        self.env = None
        self.check_env()
        self.skip_popup_behavior_list = [
            Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Up, Qt.Key.Key_Down,
            Qt.Key.Key_Tab, Qt.Key.Key_Backtab, Qt.Key.Key_Space, Qt.Key.Key_Backspace
        ]
        self.need_complete_list = [
            Qt.Key.Key_A, Qt.Key.Key_B, Qt.Key.Key_C, Qt.Key.Key_D, Qt.Key.Key_E, Qt.Key.Key_F,
            Qt.Key.Key_G, Qt.Key.Key_H, Qt.Key.Key_I, Qt.Key.Key_J, Qt.Key.Key_K, Qt.Key.Key_L,
            Qt.Key.Key_M, Qt.Key.Key_N, Qt.Key.Key_O, Qt.Key.Key_P, Qt.Key.Key_Q, Qt.Key.Key_R,
            Qt.Key.Key_S, Qt.Key.Key_T, Qt.Key.Key_U, Qt.Key.Key_V, Qt.Key.Key_W, Qt.Key.Key_X,
            Qt.Key.Key_Y, Qt.Key.Key_Z
        ]
        self.search_box = None
        self.line_number: LineNumber = LineNumber(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.update_line_number_area_width(0)
        self.textChanged.connect(self.highlight_current_line)
        self.setTabStopDistance(
            QtGui.QFontMetricsF(self.font()).horizontalAdvance(' ') * 4
        )
        self.highlighter = PythonHighlighter(self.document())
        self.highlight_current_line()
        self.setLineWrapMode(self.LineWrapMode.NoWrap)
        # Search Text
        self.search_action = QAction("Search")
        self.search_action.setShortcut("Ctrl+f")
        self.search_action.triggered.connect(
            self.start_search_dialog
        )
        # Add actions
        self.addAction(self.search_action)
        # Complete
        self.completer: Union[None, QCompleter] = None
        self.set_complete([])

    def check_env(self):
        path = venv_check()
        try:
            if path.exists():
                self.env = jedi.create_environment(str(path))
        except Exception as error:
            pass

    def go_to_reference(self):
        if self.textCursor().selectedText() != "":
            if self.env is not None:
                script = jedi.Script(code=self.toPlainText(), environment=self.env)
            else:
                script = jedi.Script(code=self.toPlainText())
            find_ref_list = script.get_references(
                self.textCursor().blockNumber() + 1, self.textCursor().positionInBlock())
            # try:
            #     importlib.util.find_spec()
            # except ValueError as not_found:
            #     pass

    def set_complete(self, list_to_complete: list) -> None:
        """
        Set complete and bind.
        :param list_to_complete: keyword list to complete.
        :return: None
        """
        completer = QCompleter(list_to_complete)
        completer.activated.connect(self.insert_completion)
        completer.setWidget(self)
        completer.setWrapAround(False)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer = completer

    def insert_completion(self, completion) -> None:
        """
        insert complete keyword to editor.
        :param completion: completion text
        :return: None
        """
        if self.completer.widget() != self:
            return
        text_cursor = self.textCursor()
        extra = len(completion) - len(self.completer.completionPrefix())
        text_cursor.movePosition(QTextCursor.MoveOperation.Left)
        text_cursor.movePosition(QTextCursor.MoveOperation.EndOfWord)
        text_cursor.insertText(completion[-extra:])
        self.setTextCursor(text_cursor)

    @property
    def text_under_cursor(self):
        # Find text under cursor
        text_cursor = self.textCursor()
        text_cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        return text_cursor.selectedText()

    def focusInEvent(self, e) -> None:
        if self.completer:
            self.completer.setWidget(self)
        QPlainTextEdit.focusInEvent(self, e)

    def complete(self) -> None:
        """
        Keyword autocomplete
        :return:  None
        """
        prefix = self.text_under_cursor
        if self.env is not None:
            script = jedi.Script(code=self.toPlainText(), environment=self.env)
        else:
            script = jedi.Script(code=self.toPlainText())
        jedi_complete_list: List[Completion] = script.complete(
            self.textCursor().blockNumber() + 1, self.textCursor().positionInBlock())
        if len(jedi_complete_list) > 0:
            new_complete_list = list()
            for complete_text in jedi_complete_list:
                new_complete_list.append(complete_text.name)
            self.set_complete(new_complete_list)
        self.completer.setCompletionPrefix(prefix)
        popup = self.completer.popup()
        cursor_rect = self.cursorRect()
        popup.setCurrentIndex(self.completer.completionModel().index(0, 0))
        cursor_rect.setWidth(self.completer.popup().rect().size().width())
        self.completer.complete(cursor_rect)

    def start_search_dialog(self) -> None:
        """
        Show search box ui and bind.
        :return: None
        """
        # Search box connect to function
        self.search_box = SearchBox()
        self.search_box.search_back_button.clicked.connect(
            self.find_back_text
        )
        self.search_box.search_next_button.clicked.connect(
            self.find_next_text
        )
        self.search_box.show()

    def find_next_text(self) -> None:
        """
        Find next match text.
        :return: None
        """
        if self.search_box.isVisible():
            text = self.search_box.search_input.text()
            self.find(text)

    def find_back_text(self) -> None:
        """
        Find back match text.
        :return: None
        """
        if self.search_box.isVisible():
            text = self.search_box.search_input.text()
            self.find(text, QTextDocument.FindFlag.FindBackward)

    def line_number_paint(self, event) -> None:
        painter = QPainter(self.line_number)
        painter.fillRect(event.rect(), actually_color_dict.get("line_number_background_color"))
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(actually_color_dict.get("line_number_color"))
                painter.drawText(
                    0,
                    top,
                    self.line_number.width(),
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignCenter,
                    number,
                )
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    def line_number_width(self) -> int:
        digits = len(str(self.blockCount()))
        space = 12 * digits
        return space

    def update_line_number_area_width(self, value) -> None:
        self.setViewportMargins(self.line_number_width(), 0, 0, 0)

    def resizeEvent(self, event) -> None:
        """
        Resize line number paint.
        :param event: QT event.
        :return: None
        """
        QPlainTextEdit.resizeEvent(self, event)
        cr = self.contentsRect()
        self.line_number.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_width(), cr.height()),
        )

    def update_line_number_area(self, rect, dy) -> None:
        """
        Set line number.
        :param rect: line number rect.
        :param dy: update or not.
        :return: None
        """
        if dy:
            self.line_number.scroll(0, dy)
        else:
            self.line_number.update(
                0,
                rect.y(),
                self.line_number.width(),
                rect.height(),
            )
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def highlight_current_line(self) -> None:
        """
        Change current line color.
        :return: None
        """
        selections = []
        if not self.isReadOnly():
            formats = QTextCharFormat()
            selection = QTextEdit.ExtraSelection()
            selection.format = formats
            color_of_the_line = actually_color_dict.get("current_line_color")
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            selections.append(selection)
            selection.format.setBackground(color_of_the_line)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
        self.setExtraSelections(selections)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """
        Catch Soft new line (key, shift + enter)
        :param event: keypress event
        :return: None
        """
        # Catch soft wrap shift + return (line nuber not working on soft warp)
        if self.completer.popup().isVisible() and event.key() in self.skip_popup_behavior_list:
            self.completer.popup().close()
            event.ignore()
            return
        if event.modifiers() and Qt.Modifier.SHIFT:
            key = event.key()
            if key == Qt.Key.Key_Enter or key == Qt.Key.Key_Return:
                event.ignore()
                return
        if event.modifiers() and Qt.Modifier.CTRL:
            if event.key() == Qt.Key.Key_B:
                self.go_to_reference()
                event.ignore()
                return
        super().keyPressEvent(event)
        self.highlight_current_line()
        if event.key() in self.need_complete_list and self.completer is not None:
            if self.completer.popup().isVisible():
                self.completer.popup().close()
            self.complete()

    def mousePressEvent(self, event) -> None:
        # Highlight mouse click line
        super().mousePressEvent(event)
        self.highlight_current_line()


class LineNumber(QWidget):
    """
    Used to paint line number.
    """

    def __init__(self, editor):
        QWidget.__init__(self, parent=editor)
        self.editor = editor

    def paintEvent(self, event) -> None:
        self.editor.line_number_paint(event)
