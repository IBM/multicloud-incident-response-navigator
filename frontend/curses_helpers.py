"""
Module with curses helper functions.
"""

import curses
from typing import List


def initialize_curses():
	"""
	Initializes curses and returns a _curses.window object for the entire screen.

	Arguments:	None
	Returns:	(_curses.window) stdscr
	"""

	stdscr = curses.initscr()

	curses.start_color()
	curses.use_default_colors()
	curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
	if curses.can_change_color() == 1:
		curses.init_color(240,500,500,500)
		curses.init_pair(2, 240, -1)
		curses.init_color(255, 0, 0, 0)
		curses.init_pair(3, 255, 240)

	curses.noecho()
	curses.cbreak()
	stdscr.keypad(True)
	curses.curs_set(0)

	return stdscr


def print_center(stdscr, text_lines: List[str]) -> None:
	"""
	Draws the given lines of text in the center of the screen.

	Arguments:	(_curses.window) stdscr
				(List[str]) text_lines
	"""

	stdscr.erase()
	h, w = stdscr.getmaxyx()
	for i, line in enumerate(text_lines):
		x = w // 2 - len(line) // 2
		y = h // 2 - len(text_lines) // 2 + i
		stdscr.addstr(y, x, line)
	stdscr.refresh()


def highlight_window(window, grey=False) -> None:
	"""
	Makes the given window's background white and text black.

	Arguments:	(_curses.window) window
	Returns:	None
	"""
	if not grey:
		window.bkgd(" ", curses.A_STANDOUT)
	else:
		window.bkgd(" ", curses.color_pair(3))


def bottom_border(window) -> None:
	"""
	Draws a border on the bottom edge of the given window.

	Arguments:	(_curses.window) window
	Returns:	None
	"""

	nochar = curses.A_INVIS
	hline = curses.ACS_HLINE

	# l,r,t,b,tl,tr,bl,br
	window.border(nochar,nochar,nochar,0,nochar,nochar,hline,hline)