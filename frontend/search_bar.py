"""
Module that holds the logic for the query mode search bar.
"""

import sys

this = sys.modules[__name__]	# used to reference module variables

window = None					# _curses.window obj that represents the search bar
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
	this.window.box()
	this.window.addstr(1, LEFT_PADDING, "".join(this.query_chars))
	this.window.move(1, LEFT_PADDING + len(this.query_chars))
	this.window.refresh()


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
	y,x = this.window.getyx()
	if len(this.query_chars) < this.max_len:
		ins_idx = x - LEFT_PADDING
		this.query_chars.insert(ins_idx, char)
		query_str = "".join(query_chars)
		this.window.erase()
		this.window.addstr(1, LEFT_PADDING, query_str)
		this.window.box()
		this.window.move(y, x+1)
	else:
		this.window.move(y, x)
	this.window.refresh()


def backspace() -> None:
	"""
	Deletes the character preceding the cursor.

	Also shifts the portion of the query to the right of the cursor left one character.
	"""
	y,x = this.window.getyx()
	if x > LEFT_PADDING:
		del_idx = x - LEFT_PADDING - 1
		del this.query_chars[del_idx]
		query_str = "".join(query_chars)
		this.window.erase()
		this.window.addstr(1, LEFT_PADDING, query_str)
		this.window.box()
		this.window.move(y, x-1)
	this.window.refresh()


def move_left() -> None:
	"""
	Moves the cursor left, if possible.
	"""
	y,x = this.window.getyx()
	if x > LEFT_PADDING:
		this.window.move(y, x-1)
	this.window.refresh()


def move_right() -> None:
	"""
	Moves the cursor right, if possible.
	"""
	y,x = this.window.getyx()
	if x < this.max_len and x < len(this.query_chars) + LEFT_PADDING:	# space
		this.window.move(y, x+1)
	else:
		this.window.move(y,x)
	this.window.refresh()


def move_to_start() -> None:
	"""
	Moves the cursor to the start of the query.
	"""
	this.window.move(1, LEFT_PADDING)
	this.window.refresh()


def move_to_end() -> None:
	"""
	Moves the cursor to the end of the query.
	"""
	this.window.move(1, LEFT_PADDING + len(this.query_chars))
	this.window.refresh()

def show_cursor() -> None:
	"""
	Displays cursor where it previously was in search bar window.
	"""
	y,x = this.window.getyx()
	this.window.move(y, x)
	this.window.refresh()
