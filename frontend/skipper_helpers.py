"""
Module with Skipper helper functions.
"""

import curses_helpers as chs
from pyfiglet import Figlet
from typing import List
import curses
import time


def figlet_lines() -> List[str]:
	"""
	Returns ASCII bubble letter representation of "skipper" as a list of strings.
	"""
	return Figlet(font="standard").renderText("skipper").split("\n")[:-1]


def loading_screen(stdscr) -> None:
	"""
	Draws the loading screen and keeps it for 0.5 secs.
	"""

	kube_config_line = ["Loading cluster info from kube-config..."]
	chs.print_center(stdscr, figlet_lines() + kube_config_line)
	time.sleep(0.5)
	stdscr.erase()
	stdscr.refresh()