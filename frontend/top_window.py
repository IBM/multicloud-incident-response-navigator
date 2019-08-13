"""
Module that represents that top banner window of Skipper interactive terminal tool.

window__________________________________
|                                       |
|_______________________________________|
"""

import curses, emojis
import sys, time
import skipper_helpers as shs

# used to reference module variables
this = sys.modules[__name__]

mode = "cluster"
window = None		# _curses.window object that represents that top banner
height, width = 0,0

LEFT_PADDING = 5
TOP_PADDING = 1

def init_win(height: int, width: int, y: int, x: int, has_apps: bool) -> None:
	"""
	Initializes the top banner window based on the given parameters.
	Also initializes top  right window for loading icon

	:param (int) height: Desired height of the top window.
	:param (int) width: Desired width of the top window.
	:param (int) y: Y-coordinate of upper-left corner of top window.
	:param (int) x: X-coordiante of upper-left corner of top window.
	:param (bool) has_apps: True if the user manages applications
	:return: None
	"""

	this.window = curses.newwin(height,width, y,x)
	this.height, this.width = height, width
	this.has_apps = has_apps

def init_load(mode) -> None:
	"""
	Create loading icon win to the right of the text of current mode
	"""
	offset = len("> " + mode + " mode ")
	this.loading_icon_win = curses.newwin(2, 2, this.loading_y, this.loading_x + offset)

def draw(mode: str, ftype : str, panel : str) -> None:
	"""
	Draws the top banner based on the given mode.

	:param (str) mode
	:param (str) resource file type for right window
	:return: None
	"""

	this.window.erase()

	nav_keybinds = { 'left' : '[shift+l] left pane',
					 'right' : '[shift+r] right pane',
					 'quit' : '[q] quit'
	}

	mode_keybinds = {'cluster' : '[1] cluster mode',
					'app' : '[2] app mode',
					'anomaly' : '[3] anomaly mode',
					'query' : '[4] query mode'
					}

	resource_keybinds = {'summary' : '[s] summary',
					'yaml' : '[y] yaml',
					'logs' : '[l] logs',
					'events' : '[e] k8s events'
						}

	skipper_figlet_lines = shs.figlet_lines()

	# draw figlet
	y = this.TOP_PADDING
	x = this.LEFT_PADDING
	for line in skipper_figlet_lines:
		this.window.addstr(y, x, line)	# y, x, str
		y += 1
	this.loading_y = y
	this.loading_x = x

	# write the current mode under the figlet
	if mode in ["app", "cluster", "query", "anomaly"]:
		this.window.addstr(y, x, "> " + mode + " mode")
	else:
		print("No valid mode could be found with name", mode + ".")
		return

	# calculate starting position for nav keybinds
	keybinds_x = max(len(line) for line in skipper_figlet_lines) + this.LEFT_PADDING * 3
	keybinds_y = this.TOP_PADDING + 2

	# draw nav keybinds
	y = keybinds_y
	x = keybinds_x
	for kb in nav_keybinds.values():
		if nav_keybinds[panel] == kb:
			this.window.addstr(y, x, kb,  curses.A_STANDOUT) 	# y, x, str
		else:
			this.window.addstr(y, x, kb) 	# y, x, str
		y += 1

	# draw mode keybinds
	# if mode drawn matches current mode, highlight it (stand out markup)
	y = keybinds_y
	x += max(len(kb) for kb in nav_keybinds.values()) + this.LEFT_PADDING
	for kb in mode_keybinds.values():
		if mode_keybinds[mode] == kb:
			this.window.addstr(y, x, kb, curses.A_STANDOUT)	# y, x, str
		else:
			if kb == '[2] app mode' and not this.has_apps:
				this.window.addstr(y, x, kb, curses.color_pair(2))
			else:
				this.window.addstr(y, x, kb)	# y, x, str
		y += 1

	# calculate starting position for resource keybinds
	# draw the phrase "resource key binds"
	y = keybinds_y
	x = this.width // 2 + this.LEFT_PADDING
	this.window.addstr(y, x, "resource key binds")

	# draw resource keybinds
	y = keybinds_y
	x += len("resource key binds") + this.LEFT_PADDING
	for kb in resource_keybinds.values():
		if resource_keybinds[ftype] == kb:
			this.window.addstr(y, x, kb, curses.A_STANDOUT)	# y, x, str
		else:
			this.window.addstr(y, x, kb)	# y, x, str
		y += 1
	this.window.refresh()

def start_loading() -> None:
	"""
	Draw loading icon
	"""
	this.loading_icon_win.erase()
	# refer to cheatsheet for more emojis https://www.webfx.com/tools/emoji-cheat-sheet/
	this.loading_icon_win.addstr(0, 0, emojis.encode(':hourglass:'), curses.A_BLINK)
	this.loading_icon_win.refresh()

def stop_loading() -> None:
	"""
	Erase loading icon
	"""
	this.loading_icon_win.erase()
	this.loading_icon_win.refresh()
