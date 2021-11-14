from typing import Optional

from PyQt5.QtWidgets import QMenu, QToolBar, QPushButton, QAction
from abc import ABC, abstractmethod


class Plugin(ABC):
    """
    A plugin for the Custom IDE.

    If one wishes to not include it in the menu or the toolbar, override
    the make_menu_item or make_toolbar_item methods and make them no-op methods.
    """
    def __init__(self, parent, plugin_name: str = None, shortcut: Optional[str] = None):
        assert plugin_name is not None

        self.parent = parent
        self.plugin_name = plugin_name
        self.shortcut = shortcut

    def make_menu_item(self, menu: QMenu):
        menu_action = QAction(self.plugin_name, self.parent)
        if self.shortcut:
            menu_action.setShortcut(self.shortcut)

        def internal():
            self.run_on_triggered()

        menu_action.triggered.connect(internal)
        menu.addAction(menu_action)

    def make_toolbar_item(self, toolbar: QToolBar):
        toolbar_button = QPushButton(self.plugin_name)
        toolbar_button.clicked.connect(self.run_on_triggered)
        toolbar.addWidget(toolbar_button)

    @abstractmethod
    def run_on_triggered(self):
        pass
