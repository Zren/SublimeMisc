# Open a .sublime-project file in the current window when clicked from the sidebar / opened.

import sublime
import sublime_plugin
import subprocess
import os

# https://github.com/randy3k/ProjectManager/blob/master/pm.py#L71
def subl(args=[]):
    # learnt from SideBarEnhancements
    executable_path = sublime.executable_path()
    if sublime.platform() == 'osx':
        app_path = executable_path[:executable_path.rfind(".app/") + 5]
        executable_path = app_path + "Contents/SharedSupport/bin/subl"
    subprocess.Popen([executable_path] + args)
    if sublime.platform() == "windows":
        def fix_focus():
            window = sublime.active_window()
            view = window.active_view()
            window.run_command('focus_neighboring_group')
            window.focus_view(view)
        sublime.set_timeout(fix_focus, 300)

# Based on: https://github.com/randy3k/ProjectManager/blob/master/pm.py#L332
def switch_project(project_file_name):
    window = sublime.active_window()
    window.run_command('close_project')
    window.run_command('close_workspace')
    subl([project_file_name])

class OpenProjectListener(sublime_plugin.EventListener):
    def on_activated(self, view):
        if view.file_name() is None:
            return

        _, ext = os.path.splitext(view.file_name())
        if ext != '.sublime-project':
            return

        window = sublime.active_window()
        project_file_name = view.file_name()
        if window.project_file_name() == project_file_name:
            return

        window.run_command('close') # Close .sublime-project tab
        switch_project(project_file_name)

