# Ignore "file hasn't been saved" prompt when closing a temp file.

import sublime
import sublime_plugin
import os

def expandpath(path):
    return os.path.abspath(os.path.expanduser(path))

class FileOpenListener(sublime_plugin.EventListener):
    def on_activated(self, view):
        if view.file_name() is None:
            return

        filepath = os.path.abspath(view.file_name())
        read_only_dirs = ['~/.cache']
        for path in read_only_dirs:
            if filepath.startswith(expandpath(path)):
                view.set_read_only(True)
                view.set_scratch(True) # Ignore "unsaved" on close.
