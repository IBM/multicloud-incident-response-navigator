"""
Module that represents that top banner window of Skipper interactive terminal tool.

window__________________________________
|                                       |
|_______________________________________|
"""

import curses
import sys
import curses_helpers as chs
import skipper_helpers as shs


# used to reference module variables
this = sys.modules[__name__]

mode = "app"
window = None		# _curses.window object that represents that top banner

LEFT_PADDING = 5
TOP_PADDING = 1


def init_win(stdscr, height: int, width: int, y: int, x: int) -> None:
	"""
	Initializes the top banner window based on the given parameters.

	Arguments:	(_curses.window) stdscr
				(int) height
					Desired height of the top window.
				(int) width
					Desired width of the top window.
				(int) y
					Y-coordinate of upper-left corner of top window.
				(int) x
					X-coordiante of upper-left corner of top window.
	Returns:	None
	"""

	this.window = curses.newwin(height,width, y,x)


def draw(mode: str) -> None:
	"""
	Draws the top banner based on the given mode.

	Arguments:	(str) mode
	Returns:	None
	"""

	this.window.erase()

	nav_keybinds = ['[esc] command mode',
					'[shift-l] left pane',
					'[shift-r] right pane',
					'[shift-b] back',
					'[q] quit']
	mode_keybinds = ['[1] cluster mode',
					'[2] app mode',
					'[3] anomaly mode',
					'[4] query mode']
	resource_keybinds = ['[shift-s] summary',
					'[shift-d] describe',
					'[shift-y] yaml',
					'[shift-l] logs',
					'[shift-e] k8s events']

	skipper_figlet_lines = shs.figlet_lines()

	# draw figlet
	y = this.TOP_PADDING
	x = this.LEFT_PADDING
	for line in skipper_figlet_lines:
		this.window.addstr(y, x, line)	# y, x, str
		y += 1

	# write the current mode under the figlet
	if mode in ["app", "cluster", "query", "anomaly"]:
		this.window.addstr(y, x, "> " + mode + " mode")
	else:
		print("No valid mode could be found with name", mode + ".")
		return

	# calculate starting position for nav keybinds
	keybinds_x = max(len(line) for line in skipper_figlet_lines) + this.LEFT_PADDING * 4
	keybinds_y = this.TOP_PADDING + 1

	# draw nav keybinds
	y = keybinds_y
	x = keybinds_x
	for kb in nav_keybinds:
		this.window.addstr(y, x, kb) 	# y, x, str
		y += 1

	# draw mode keybinds
	y = keybinds_y
	x += max(len(kb) for kb in nav_keybinds) + this.LEFT_PADDING
	for kb in mode_keybinds:
		this.window.addstr(y, x, kb)	# y, x, str
		y += 1

	# calculate starting position for resource keybinds
	# draw the phrase "resource key binds"
	y = keybinds_y
	x += max(len(kb) for kb in mode_keybinds) + 2 * this.LEFT_PADDING
	this.window.addstr(y, x, "resource key binds")

	# draw resource keybinds
	y = keybinds_y
	x += len("resource key binds") + this.LEFT_PADDING
	for kb in resource_keybinds:
		this.window.addstr(y, x, kb)	# y, x, str
		y += 1

	this.window.refresh()