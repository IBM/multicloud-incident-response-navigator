"""
Module with Skipper helper functions.
"""

import curses_helpers as chs
from pyfiglet import Figlet
from typing import List, Callable
import curses
import time
import requests


def figlet_lines() -> List[str]:
	"""
	Returns ASCII bubble letter representation of "skipper" as a list of strings.
	"""
	return Figlet(font="standard").renderText("skipper").split("\n")[:-1]


def loading_screen(stdscr, task: Callable) -> None:
	"""
	Draws the loading screen, runs the task function, and returns the result.
	"""

	chs.print_center(stdscr, figlet_lines() + ["", "Loading clusters from kube-config..."])
	cluster_names = requests.get('http://127.0.0.1:5000/cluster_names').json()["names"]
	stdscr.erase()
	message_lines = ["", "Loading info for the following clusters: " + ",".join(cluster_names) + ". This may take a while..."]
	chs.print_center(stdscr, figlet_lines() + message_lines)
	return task()