"""
Module with Skipper helper functions.
"""

import curses_helpers as chs
from pyfiglet import Figlet
from typing import List, Callable

def figlet_lines() -> List[str]:
	"""
	:return: List[str] ASCII bubble letter representation of "skipper"
	"""
	return Figlet(font="standard").renderText("skipper").split("\n")[:-1]


def loading_screen(stdscr, task: Callable) -> None:
	"""
	Draws the loading screen, runs the task function
	:return: result of task
	"""

	message_lines = ["", "Loading info from clusters found in kube-config..."]
	chs.print_center(stdscr, figlet_lines() + message_lines)
	return task()

def terminal_size_reminder(stdscr):
	"""
	Draws terminal sizer reminder screen, and waits for user to quit
	:param stdscr
	:return: None
	"""
	stdscr.erase()
	text_lines = ["Sorry, your terminal size does not meet Skipper's requirements.",
				  "Please resize your terminal to at least 180x40 and run Skipper again.",
				  "[q] quit"]
	chs.print_center(stdscr, text_lines)

	c = 0
	while c != ord('q'):
		c = stdscr.getch()
	return