import functools
import os
import subprocess
import threading
import sublime
import sublime_plugin


# Copied from Git.sublime-package/git/__init__.py
def main_thread(callback, *args, **kwargs):
    # sublime.set_timeout gets used to send things onto the main thread
    # most sublime.[something] calls need to be on the main thread
    sublime.set_timeout(functools.partial(callback, *args, **kwargs), 0)

# Modified version from Git.sublime-package/git/__init__.py
def git_root(directory):
    retval = False
    while directory:
        if os.path.exists(os.path.join(directory, '.git')):
            retval = directory
            break
        parent = os.path.realpath(os.path.join(directory, os.path.pardir))
        if parent == directory:
            # /.. == /
            retval = False
            break
        directory = parent

    return retval

def do_when(conditional, command, *args, **kwargs):
    if conditional():
        return command(*args, **kwargs)
    sublime.set_timeout(functools.partial(do_when, conditional, command, *args, **kwargs), 50)

# Copied from Git.sublime-package/git/__init__.py
def _make_text_safeish(text, fallback_encoding, method='decode'):
    # The unicode decode here is because sublime converts to unicode inside
    # insert in such a way that unknown characters will cause errors, which is
    # distinctly non-ideal... and there's no way to tell what's coming out of
    # git in output. So...
    try:
        unitext = getattr(text, method)('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        unitext = getattr(text, method)(fallback_encoding)
    except AttributeError:
        # strongly implies we're already unicode, but just in case let's cast
        # to string
        unitext = str(text)
    return unitext


def _test_paths_for_executable(paths, test_file):
    for directory in paths:
        file_path = os.path.join(directory, test_file)
        if os.path.exists(file_path) and os.access(file_path, os.X_OK):
            return file_path


def find_binary(cmd):
    # It turns out to be difficult to reliably run git, with varying paths
    # and subprocess environments across different platforms. So. Let's hack
    # this a bit.
    # (Yes, I could fall back on a hardline "set your system path properly"
    # attitude. But that involves a lot more arguing with people.)
    path = os.environ.get('PATH', '').split(os.pathsep)
    if os.name == 'nt':
        cmd = cmd + '.exe'

    path = _test_paths_for_executable(path, cmd)

    if not path:
        # /usr/local/bin:/usr/local/git/bin
        if os.name == 'nt':
            extra_paths = (
                os.path.join(os.environ.get("ProgramFiles", ""), "Git", "bin"),
                os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Git", "bin"),
            )
        else:
            extra_paths = (
                '/usr/local/bin',
                '/usr/local/git/bin',
            )
        path = _test_paths_for_executable(extra_paths, cmd)
    return path
GIT = find_binary('git')
GITK = find_binary('gitk')

# Copied from Git.sublime-package/git/__init__.py
class CommandThread(threading.Thread):
    command_lock = threading.Lock()

    def __init__(self, command, on_done, working_dir="", fallback_encoding="", **kwargs):
        threading.Thread.__init__(self)
        self.command = command
        self.on_done = on_done
        self.working_dir = working_dir
        if "stdin" in kwargs:
            self.stdin = kwargs["stdin"].encode()
        else:
            self.stdin = None
        if "stdout" in kwargs:
            self.stdout = kwargs["stdout"]
        else:
            self.stdout = subprocess.PIPE
        self.fallback_encoding = fallback_encoding
        self.kwargs = kwargs

    def run(self):
        # Ignore directories that no longer exist
        if not os.path.isdir(self.working_dir):
            return

        self.command_lock.acquire()
        output = ''
        callback = self.on_done
        try:
            if self.working_dir != "":
                os.chdir(self.working_dir)
            # Windows needs startupinfo in order to start process in background
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            env = os.environ.copy()

            shell = False
            if sublime.platform() == 'windows':
                shell = True
                if 'HOME' not in env:
                    env[str('HOME')] = str(env['USERPROFILE'])

            # universal_newlines seems to break `log` in python3
            print(self.command)
            proc = subprocess.Popen(self.command,
                stdout=self.stdout, stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE, startupinfo=startupinfo,
                shell=shell, universal_newlines=False,
                env=env)
            output = proc.communicate(self.stdin)[0]
            if not output:
                output = ''
            output = _make_text_safeish(output, self.fallback_encoding)
        except subprocess.CalledProcessError as e:
            output = e.returncode
        except OSError as e:
            callback = sublime.error_message
            if e.errno == 2:
                global _has_warned
                if not _has_warned:
                    _has_warned = True
                    output = "{cmd} binary could not be found in PATH\n\nConsider using the {cmd_setting}_command setting for the Git plugin\n\nPATH is: {path}".format(cmd=self.command[0], cmd_setting=self.command[0].replace('-', '_'), path=os.environ['PATH'])
            else:
                output = e.strerror
        finally:
            self.command_lock.release()
            main_thread(callback, output, **self.kwargs)


# Modified version from Git.sublime-package/git/__init__.py
class GitWindowCommand(sublime_plugin.WindowCommand):
    may_change_files = False

    def active_view(self):
        return self.window.active_view()

    def _active_file_name(self):
        view = self.active_view()
        if view and view.file_name() and len(view.file_name()) > 0:
            return view.file_name()

    # If there is a file in the active view use that file's directory to
    # search for the Git root.  Otherwise, use the only folder that is
    # open.
    def get_working_dir(self):
        file_name = self._active_file_name()
        if file_name:
            return os.path.realpath(os.path.dirname(file_name))
        try:  # handle case with no open folder
            return self.window.folders()[0]
        except IndexError:
            return ''

    # If there's no active view or the active view is not a file on the
    # filesystem (e.g. a search results view), we can infer the folder
    # that the user intends Git commands to run against when there's only
    # only one.
    def is_enabled(self):
        if self._active_file_name() or len(self.window.folders()) == 1:
            return bool(git_root(self.get_working_dir()))
        return False

    # Modified version from Git.sublime-package/git/__init__.py
    def run_command(self, command, callback=None, show_status=True,
            filter_empty_args=True, no_save=False, **kwargs):

        if filter_empty_args:
            command = [arg for arg in command if arg]
        if 'working_dir' not in kwargs:
            kwargs['working_dir'] = self.get_working_dir()
        if 'fallback_encoding' not in kwargs and self.active_view() and self.active_view().settings().get('fallback_encoding'):
            kwargs['fallback_encoding'] = self.active_view().settings().get('fallback_encoding').rpartition('(')[2].rpartition(')')[0]

        s = sublime.load_settings("Git.sublime-settings")
        if s.get('save_first') and self.active_view() and self.active_view().is_dirty() and not no_save:
            self.active_view().run_command('save')
        if command[0] == 'git':
            us = sublime.load_settings('Preferences.sublime-settings')
            if s.get('git_command') or us.get('git_binary'):
                command[0] = s.get('git_command') or us.get('git_binary')
            elif GIT:
                command[0] = GIT
        if command[0] == 'gitk' and s.get('gitk_command'):
            if s.get('gitk_command'):
                command[0] = s.get('gitk_command')
            elif GITK:
                command[0] = GITK
        if command[0] == 'git' and command[1] == 'flow' and s.get('git_flow_command'):
            command[0] = s.get('git_flow_command')
            del(command[1])
        if not callback:
            callback = self.generic_done

        print(command)
        thread = CommandThread(command, callback, **kwargs)
        thread.start()

    def generic_done(self, result, **kw):
        if self.may_change_files and self.active_view() and self.active_view().file_name():
            if self.active_view().is_dirty():
                result = "WARNING: Current view is dirty.\n\n"
            else:
                # just asking the current file to be re-opened doesn't do anything
                print("reverting")
                position = self.active_view().viewport_position()
                self.active_view().run_command('revert')
                do_when(lambda: not self.active_view().is_loading(), lambda: self.active_view().set_viewport_position(position, False))
                # self.active_view().show(position)

        view = self.active_view()
        if view and view.settings().get('live_git_annotations'):
            view.run_command('git_annotate')

        if not result.strip():
            return
        self.panel(result)

    def _output_to_view(self, output_file, output, clear=False,
            syntax="Packages/Diff/Diff.tmLanguage", **kwargs):
        output_file.set_syntax_file(syntax)
        args = {
            'output': output,
            'clear': clear
        }
        output_file.run_command('git_scratch_output', args)

    def panel(self, output, **kwargs):
        if not hasattr(self, 'output_view'):
            self.output_view = self.get_window().get_output_panel("git")
        self.output_view.set_read_only(False)
        self._output_to_view(self.output_view, output, clear=True, **kwargs)
        self.output_view.set_read_only(True)
        self.record_git_root_to_view(self.output_view)
        self.get_window().run_command("show_panel", {"panel": "output.git"})

    def record_git_root_to_view(self, view):
        # Store the git root directory in the view so we can resolve relative paths
        # when the user wants to navigate to the source file.
        if self.get_working_dir():
            root = git_root(self.get_working_dir())
        else:
            root = self.active_view().settings().get("git_root_dir")
        view.settings().set("git_root_dir", root)
