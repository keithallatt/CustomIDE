# CustomIDE

Custom IDE built in Python 3 and the PyQt5 module. Designed to work on Ubuntu 20.04 LTS with GNOME, 
but could potentially be modified to work on other operating systems / desktop environments.

---

Currently, the IDE only has a dark mode (a programmer favourite), but also currently comes with 2 themes.

![current_ide](readme_assets/current_sample_main.png?)

As this project is still in it's early stages, a lot of the themes, color schemes, and general layout 
are likely to change.

---

Current Feature List
 - The ability to open, edit, and save files.
 - Python and JSON syntax highlighting.
 - A toolbar and menu bar
   - Some basic operations, but also integration with tools like `pip` and `cloc`
 - Basic navigation using the keyboard
 - Customizable keybinds
 - Linting (still a WIP)
 - Theme picker and editor
---

There are a lot of plans for the future, but until then, this project is still very much a work in progress.

---

Installation Requirements:
- Python3.8+
- Ubuntu /w Gnome DE
  - Only tested with Ubuntu 20.04 LTS
- `pip` and `venv`

To Install:
1. Download the repository
2. Move `custom_ide.desktop` to `~/.local/share/applications/`
3. Create the virtual environment and use `pip` to install various dependencies
   - A dependency list will be available soon, but a setup wizard is also in the plan for the future.
4. Edit the `Exec` and `Path` file paths in `custom_ide.desktop` to point to the `custom_ide.py` script and the parent folder respectively.
