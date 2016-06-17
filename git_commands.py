import os
import sublime
import sublime_plugin

from .git_plugin import GitWindowCommand

class GitOpenExcludeFileCommand(GitWindowCommand):
    def run(self):
        working_dir = git_root(self.get_working_dir())
        exclude_file = os.path.join(working_dir, '.git/info/exclude')
        if os.path.exists(exclude_file):
            self.window.open_file(exclude_file)
        else:
            sublime.status_message(".git/info/exclude not found")

# Based on GitBranchCommand, GitNewBranchCommand
# https://help.github.com/articles/checking-out-pull-requests-locally/
class GitCheckoutPullRequestCommand(GitWindowCommand):
    may_change_files = True

    def run(self):
        self.window.show_input_panel("Pull Request #", "", self.on_input, None, None)

    def on_input(self, s):
        if s.strip() == "":
            self.panel("Invalid PR#")
            return
        self.pull_request_id = int(s)
        self.picked_remote = 'origin'
        self.remote_ref = 'pull/{}/head'.format(self.pull_request_id)
        self.local_branch = '{}-pr{}'.format(self.picked_remote, self.pull_request_id)
        self.run_command(['git', 'fetch', self.picked_remote, '{}:{}'.format(self.remote_ref, self.local_branch)], callback=self.fetch_done)

    def fetch_done(self, result):
        self.run_command(['git', 'checkout', self.local_branch])
