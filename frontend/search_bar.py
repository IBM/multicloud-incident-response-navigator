"""
Module that holds the logic for the query mode search bar.
"""

import sys

this = sys.modules[__name__]	# used to reference module variables

window = None					# _curses.window obj that represents the search bar
instruction_window = None
bar_window = None
width, height = 0,0				# width and height of the window
start_x, start_y = 0,0			# x,y coordinates of the upper left corner of the window

LEFT_PADDING = 5

query_chars = []				# list of characters that represents the user's query so far
max_len = 0 					# maximum of length of a query, as dictated by space constraints


def set_window(sb_window) -> None:
	"""
	Initializes module variables based on the given curses window.

	Arguments: 	(_curses.window) sb_window, search bar window
	Returns:	None
	"""
	this.window = sb_window
	this.height, this.width = sb_window.getmaxyx()
	this.max_len = this.width - 2 * LEFT_PADDING
	this.start_y, this.start_x = 1, LEFT_PADDING


def draw() -> None:
	"""
	Draws the search bar, shows the outstanding query, moves the cursor to end of query.
	"""
	this.instruction_window = this.window.derwin(4, this.width, 0, 0)
	this.instruction_window.addstr(0, LEFT_PADDING, "Filter by application/cluster/namespace:\tEx: \"app:bookinfo\", \"cluster:iks\", \"ns:default\"")
	this.instruction_window.addstr(1, LEFT_PADDING, "Filter by resource kind:\t\t\tEx: \"kind:pod\"")
	this.instruction_window.addstr(2, LEFT_PADDING, "Search by keyword:\t\t\t\tEx: \"redis\"")
	this.instruction_window.addstr(3, LEFT_PADDING, "All together:\t\t\t\tEx: \"app:bookinfo kind:pod cluster:iks redis\"")
	this.instruction_window.refresh()

	this.bar_window = this.window.derwin(3, this.width, 4, 0)
	this.bar_window.box()
	this.bar_window.addstr(1, LEFT_PADDING, "".join(this.query_chars))
	this.bar_window.move(1, LEFT_PADDING + len(this.query_chars))
	this.bar_window.refresh()


def get_query() -> str:
	"""
	Returns the current query.
	"""
	return "".join(this.query_chars)

def addch(char: chr) -> None:
	"""
	Writes the given char at the current cursor position.

	Acts like window.addch(), except that it inserts instead of overwriting characters.
	Arguments:	(chr) char, the character to write
	Returns:	None
	"""
	y,x = this.bar_window.getyx()
	if len(this.query_chars) < this.max_len:
		ins_idx = x - LEFT_PADDING
		this.query_chars.insert(ins_idx, char)
		query_str = "".join(query_chars)
		this.bar_window.erase()
		this.bar_window.addstr(1, LEFT_PADDING, query_str)
		this.bar_window.box()
		this.bar_window.move(y, x+1)
	else:
		this.bar_window.move(y, x)
	this.bar_window.refresh()


def backspace() -> None:
	"""
	Deletes the character preceding the cursor.

	Also shifts the portion of the query to the right of the cursor left one character.
	"""
	y,x = this.bar_window.getyx()
	if x > LEFT_PADDING:
		del_idx = x - LEFT_PADDING - 1
		del this.query_chars[del_idx]
		query_str = "".join(query_chars)
		this.bar_window.erase()
		this.bar_window.addstr(1, LEFT_PADDING, query_str)
		this.bar_window.box()
		this.bar_window.move(y, x-1)
	this.bar_window.refresh()


def move_left() -> None:
	"""
	Moves the cursor left, if possible.
	"""
	y,x = this.bar_window.getyx()
	if x > LEFT_PADDING:
		this.bar_window.move(y, x-1)
	this.bar_window.refresh()


def move_right() -> None:
	"""
	Moves the cursor right, if possible.
	"""
	y,x = this.bar_window.getyx()
	if x < this.max_len and x < len(this.query_chars) + LEFT_PADDING:	# space
		this.bar_window.move(y, x+1)
	else:
		this.bar_window.move(y,x)
	this.bar_window.refresh()


def move_to_start() -> None:
	"""
	Moves the cursor to the start of the query.
	"""
	this.bar_window.move(1, LEFT_PADDING)
	this.bar_window.refresh()


def move_to_end() -> None:
	"""
	Moves the cursor to the end of the query.
	"""
	this.bar_window.move(1, LEFT_PADDING + len(this.query_chars))
	this.bar_window.refresh()

def show_cursor() -> None:
	"""
	Displays cursor where it previously was in search bar window.
	"""
	y,x = this.bar_window.getyx()
	this.bar_window.move(y, x)
	this.bar_window.refresh()
