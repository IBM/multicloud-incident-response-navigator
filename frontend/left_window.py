"""
Module that represents the left panel of the Skipper interactive terminal tool.

 window________________________
|  __________________________  |
| | bc_window (breadcrumbs)  | |
| |__________________________| |
|  __________________________  |
| | th_window (table headers)| |
| |__________________________| |
|  __________________________  |
| | table_window             | |
| |  ______________________  | |
| | |tr_window (table row) | | |
| | |______________________| | |
| |  ______________________  | |
| | |tr_window (table row) | | |
| | |______________________| | |
| | ...                      | |
| |                          | |
| |                          | |
| |                          | |
| |                          | |
| |__________________________| |
|______________________________|
"""

import sys, curses
from typing import List
import curses_helpers as chs

this = sys.modules[__name__]	# used to reference module variables

mode = "app"
path = []				# path to display in breadcrumbs window
rtypes = []				# resource types of items in the path
col_names = []			# column header names
col_widths = []			# width of each column
table = [[]]			# rows of data to be displayed in table window (curses.pad)
row_selector = 0		# which row of the table should be highlighted

bc_height = 4			# height of the breadcrumbs window
th_height = 3			# height of the table headers window
tr_height = 3			# height of a table row window
table_height = 0		# height of the table window

x,y = 0,0				# absolute x,y of upper-left corner of left_window
width,height = 0,0		# width and height of left_window
end_x,end_y = 0,0		# absolute x,y of lower-right corner of left_window

bcx, bcy = 0,0			# relative x,y of upper-left corner of breadcrumbs window
thx, thy = 0,0			# relative x,y of upper-left corner of table headers window
table_x, table_y = 0,0	# absolute x,y of upper-left corner of table window (curses.pad)

window = None			# _curses.window object that represents the left window
bc_window = None		# _curses.window object that represents the breadcrumbs window
th_window = None		# _curses.window object that represents that table headers window
table_window = None		# _curses.pad object that represents that table window

LEFT_PADDING = 5


def init_win(stdscr, height: int, width: int, y: int, x: int) -> None:
	"""
	Initializes the left window and sets relevant position variables.

	Arguments: 	(_curses.window) stdscr
				(int) height
					Desired height of the left window.
				(int) width
					Desired width of the left window.
				(int) y
					Y-coordinate of upper-left corner of window.
				(int) x
					X-coordinate of upper-left corner of window.
	Returns: 	None
	"""

	this.window = curses.newwin(height, width, y, x)

	h,w = stdscr.getmaxyx()
	this.x, this.y = x,y 						# set x,y of upper-left corner of the left window
	this.width, this.height = width, height 	# set width, height of the left window
	this.end_x, this.end_y = x + width, h - 1	# set x,y of lower-right corner of the left window
	this.bcx, this.bcy = 0,0					# set x,y of upper-left corner of breadcrumbs window


def set_contents(mode: str,
					col_names: List[str],
					col_widths: List[int],
					table: List[ List[str] ],
					row_selector: int,
					path: List[str] = [],
					rtypes: List[str] = []) -> None:
	"""
	Sets relevant content variables based on given arguments.

	Arguments:	(str) mode
				(List[str]) col_names
					Names of the table column headers.
				(List[int]) col_widths
					Widths of the table columns.
				(List[List[str]]) table
					Rows of information to display in the table.
				(int) row_selector
					Index of which row should be highlighted.
				(List[str]) path
					For app and cluster mode.
					List of resource names to display in breadcrumb window.
				(List[str]) rtypes
					For app and cluster mode.
					List of resource types corresponding to the above resource names.
	Returns: 	None
	"""

	this.window = window
	this.mode = mode
	this.col_names = col_names
	this.col_widths = col_widths
	this.table = table
	this.row_selector = row_selector
	this.path = path
	this.rtypes = rtypes

	if mode in ["app", "cluster"]:
		this.thx, this.thy = 0,this.bc_height	# relative x,y inside left_window
		this.table_x, this.table_y = 0, y + this.bc_height + this.th_height # absolute x,y
		this.table_height = this.height - this.bc_height - this.th_height
	else:
		this.thx, this.thy = 0,0	# relative x,y inside left_window
		this.table_x, this.table_y = 0, y + this.th_height # absolute x,y
		this.table_height = this.height - this.th_height


def draw_bc_window(bc_window) -> None:
	"""
	Draws this.path and this.rtypes in the given breadcrumb window.

	Arguments: 	(_curses.window) bc_window
					_curses.window object that represents the breadcrumb window
	Returns:  	None
	"""

	# edge case: name is shorter than resource type
	# edge case: path is longer than bc window width
	# edge case: path and rtypes are of different lengths
	
	# calculate and apply padding for resource labels that go below path
	padded_rtypes = []
	for name, rtype in zip(path, rtypes):
		nlen, rtlen = len(name), len(rtype)
		left_padding = (nlen-rtlen) - (nlen-rtlen)//2
		right_padding = (nlen-rtlen)//2 + 3
		padded_str = left_padding * " " + rtype + right_padding * " "
		padded_rtypes.append(padded_str)

	# create strings to be displayed
	path_str = "/ " + " / ".join(path)
	type_str = 2 * " " + "".join(padded_rtypes)

	bc_window.addstr(1, this.LEFT_PADDING, path_str)
	bc_window.addstr(2, this.LEFT_PADDING, type_str)


def draw_tr_window(tr_window, row: List[str]) -> None:
	"""
	Formats and draws row in the given window.

	Arguments: 	(_curses.window)	tr_window
					_curses.window object that represents the table row
	Returns: 	None
	"""

	# edge case: start positions are too close together for the col_names
	# edge case: start positions are too large for width of window
	# edge case: col_names and start_postions have different lengths

	if len(row) == 0 or len(row) != len(this.col_widths):
		print("Please check that you are passing in valid arguments to the draw_tr_window function.")
		return

	# generate a python format string based on col widths (this.col_widths)
	format_strs = []
	for i,width in enumerate(this.col_widths):
		format_str = "{" + str(i) + ":<" + str(width) + "}"
		format_strs.append(format_str)
	str_format = "".join(format_strs)

	# draw the string inside the table row window
	row_str = str_format.format(*row)
	tr_window.addstr(1, this.LEFT_PADDING, row_str)


def draw_table_window(table_window) -> None:
	"""
	Draws this.table inside the given curses.pad window.

	Arguments:	(_curses.pad)	table_window
					_curses.pad object that represents the table.
	Returns:	None
	"""

	# create a (derived) window for each row in this.table
	yloc = 0
	row_windows = []
	for row in this.table:
		tr_window = table_window.derwin(this.tr_height,this.width, yloc,0)
		row_windows.append( (row, tr_window) )
		yloc += this.tr_height

	# Draw the row windows
	for entries, rowwin in row_windows:
		draw_tr_window(rowwin, entries)

	# Highlight the row at index this.row_selector
	chs.highlight_window(row_windows[this.row_selector][1])


def draw() -> None:
	"""
	Populates this.window with content given by the most recent call to set_contents(...)

	Arguments:	None
	Returns:	None
	"""

	this.window.erase()

	# initialize and draw breadcrumbs derived window
	# only if Skipper is in app or cluster mode
	if this.mode == "app" or this.mode == "cluster":
		bc_window = window.derwin(this.bc_height,this.width, this.bcy,this.bcx)	# nlines, ncols, rel_y, rel_x
		draw_bc_window(bc_window)

	# initialize and draw table header window
	th_window = window.derwin(this.th_height,this.width, this.thy,this.thx)	# nlines, ncols, rel_y, rel_x
	draw_tr_window(th_window, this.col_names)

	# initialize and draw table window (of type _curses.pad)
	pad_height = max(this.table_height, this.tr_height * len(this.table))
	table_window = curses.newpad( pad_height, this.width )	# nlines, ncols, start_y, start_x
	draw_table_window(table_window)

	# refresh the window before the table, o/w window will cover the table
	window.refresh()

	# calculate appropriate position in table to display based on this.row_selector
	pad_start_y = max(0, this.tr_height + row_selector * this.tr_height - this.table_height)
	table_window.refresh(pad_start_y,0, this.table_y,this.table_x, this.end_y,this.end_x)


def move_up():
	# decrements this.row_selector and redraws window, if necessary
	if this.row_selector > 0:
		this.row_selector -= 1
		this.draw()


def move_down():
	# increments this.row_selector and redraws window, if necessary
	if this.row_selector < len(table)-1:
		this.row_selector += 1
		this.draw()


def get_selected_row():
	return this.table[this.row_selector]