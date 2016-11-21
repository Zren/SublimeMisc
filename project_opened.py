import os
import sys
import sublime
import sublime_plugin

def openMain():
	window = sublime.active_window()
	print(window.project_file_name())
	if window.project_file_name():
		projectMain = window.project_data().get('project_main')
		if projectMain:
			windowVars = window.extract_variables()
			mainFilepath = os.path.join(windowVars['project_path'], projectMain)
			window.run_command('open_file', {
				'file': mainFilepath,
			})
			window.run_command('reveal_in_side_bar')

sublime.set_timeout(openMain, 50)

