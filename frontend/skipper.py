import curses
import skipper_helpers as shs
import curses_helpers as chs
import left_window as lwin
import top_window as twin


def run_skipper(stdscr):
	"""
	Runs the Skipper interactive terminal application.

	Arguments: (_curses.window) stdscr
					Automatically passed in by curses.wrapper function.
					A _curses.window obj that represents the entire screen.
	Returns:	None
	"""

	START_MODE = "app"	# possible modes include app, cluster, query, anomaly


	# initialize stdscr (standard screen)
	stdscr = chs.initialize_curses()

	# on startup, show loading screen
	shs.loading_screen(stdscr)

	# initialize and draw top window
	height, width = stdscr.getmaxyx()
	twin.init_win(stdscr, len(shs.figlet_lines()) + 3, width, 0,0)	# height, width, y, x
	twin.draw(mode=START_MODE)

	# initialize and draw left window
	top_height, top_width = twin.window.getmaxyx()
	lwin.init_win(stdscr, height=height-top_height, width=width//2, y=top_height, x=0)
	sample_data = {	"mode": START_MODE,
					"col_names": ["type", "name"],
					"col_widths": [20,20],
					"table": [
						["Application", "gbapp-gbapp"],
						["Application", "bookinfo"],
						["Application", "stock-trader"] ]*10,
					"row_selector": 0,
					"path": ["mycluster", "default", "Deployments", "boisterous-shark-gbapp-frontend"],
					"rtypes": ["cluster", "ns", "rtype", "deployment"] }
	lwin.set_contents(*sample_data.values())
	lwin.draw()


	# state that needs to be tracked
	mode = "app"
	c = 0


	# start listening for keystrokes, and act accordingly
	while c != ord('q'):

		c = stdscr.getch()

		if c == ord('1'):		# cluster mode
			mode = "cluster"
			twin.draw(mode="cluster")
			sample_data["mode"] = "cluster"
			lwin.set_contents(*sample_data.values())
			lwin.draw()
		elif c == ord('2'):		# app mode
			mode = "app"
			twin.draw(mode="app")
			sample_data["mode"] = "app"
			lwin.set_contents(*sample_data.values())
			lwin.draw()
		elif c == ord('3'):		# anomaly mode
			mode = "anomaly"
			twin.draw(mode="anomaly")
			sample_data["mode"] = "anomaly"
			lwin.set_contents(*sample_data.values())
			lwin.draw()
		elif c == ord('4'):		# query mode
			mode = "query"
			twin.draw(mode="query")
			sample_data["mode"] = "query"
			lwin.set_contents(*sample_data.values())
			lwin.draw()
		elif c == curses.KEY_UP:
			lwin.move_up()
		elif c == curses.KEY_DOWN:
			lwin.move_down()


def main():
	curses.wrapper(run_skipper)

if __name__ == "__main__":
	main()