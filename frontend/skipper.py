import curses
import skipper_helpers as shs
import curses_helpers as chs
import left_window as lwin
import top_window as twin
import requests


def run_skipper(stdscr):
	"""
	Runs the Skipper interactive terminal application.

	Arguments: (_curses.window) stdscr
					Automatically passed in by curses.wrapper function.
					A _curses.window obj that represents the entire screen.
	Returns:	None
	"""

	START_MODE = "cluster"	# possible modes include app, cluster, query, anomaly


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

	# get the data for the initial cluster mode screen that lists all clusters
	data = requests.get('http://127.0.0.1:5000/start/{}'.format(START_MODE)).json() # load everything, which involves creating the db tables, takes a LONG time
	# data = requests.get('http://127.0.0.1:5000/mode/app/switch/mycluster_537676e1-9201-11e9-b68f-0e70a6ce6d3a').json() # for debugging, when db is already populated
	# data = requests.get('http://127.0.0.1:5000/mode/cluster/switch/mycluster').json()  # for debugging, when db is already populated

	if len(data['table_items']) > 0:
		table_data = {	"mode": START_MODE,
						"col_names": ["type", "name"],
						"col_widths": [20,20],
						"table": [[t_item['rtype'], t_item['name']] for t_item in data['table_items']],
						"row_selector": data['index'],
						"path_names": data['path_names'],
						"path_rtypes": data['path_rtypes'],
						"path_uids": data['path_uids'],
						"table_uids": [t_item['uid'] for t_item in data['table_items']]}
		current_uid = table_data['table_uids'][table_data['row_selector']]
		lwin.set_contents(*table_data.values())

	lwin.draw()


	# state that needs to be tracked
	mode = START_MODE
	c = 0


	# start listening for keystrokes, and act accordingly
	while c != ord('q'):

		c = stdscr.getch()

		if c == ord('1'):		# cluster mode
			data = requests.get('http://127.0.0.1:5000/mode/cluster/switch/{}'.format(current_uid)).json()
			if len(data['table_items']) > 0:
				mode = "cluster"
				twin.draw(mode=mode)
				table_data["mode"] = mode
				table_data['table'] = [[t_item['rtype'], t_item['name']] for t_item in data['table_items']]
				table_data['row_selector'] = data['index']
				table_data['path_names'] = data['path_names']
				table_data['path_rtypes'] = data['path_rtypes']
				table_data['path_uids'] = data['path_uids']
				table_data["table_uids"] = [t_item['uid'] for t_item in data['table_items']]
				current_uid = table_data['table_uids'][table_data['row_selector']]
				lwin.set_contents(*table_data.values())
				lwin.draw()
		elif c == ord('2'):		# app mode
			data = requests.get('http://127.0.0.1:5000/mode/app/switch/{}'.format(current_uid)).json()
			if len(data['table_items']) > 0:
				mode = "app"
				twin.draw(mode=mode)
				table_data["mode"] = mode
				table_data['table'] = [[t_item['rtype'], t_item['name']] for t_item in data['table_items']]
				table_data['row_selector'] = data['index']
				table_data['path_names'] = data['path_names']
				table_data['path_rtypes'] = data['path_rtypes']
				table_data['path_uids'] = data['path_uids']
				table_data["table_uids"] = [t_item['uid'] for t_item in data['table_items']]
				current_uid = table_data['table_uids'][table_data['row_selector']]
				lwin.set_contents(*table_data.values())
				lwin.draw()
		elif c == ord('3'):		# anomaly mode
			mode = "anomaly"
			twin.draw(mode="anomaly")
			table_data["mode"] = mode
			# TODO update the data with list of anomalous resources
			lwin.set_contents(*table_data.values())
			lwin.draw()
		elif c == ord('4'):		# query mode
			mode = "query"
			twin.draw(mode="query")
			table_data["mode"] = mode
			lwin.set_contents(*table_data.values())
			lwin.draw()
		elif c == curses.KEY_UP:
			current_uid = lwin.move_up()
		elif c == curses.KEY_DOWN:
			current_uid = lwin.move_down()
		elif c == curses.KEY_RIGHT:
			parent_uid = current_uid
			# gets the children of the current resource and other relevant info
			data = requests.get('http://127.0.0.1:5000/mode/{}/{}'.format(mode,current_uid)).json()
			if len(data['table_items']) > 0:
				# update and redraw
				table_data['table'] = [[t_item['rtype'], t_item['name']] for t_item in data['table_items']]
				table_data['row_selector'] = data['index']
				table_data['path_names'] = data['path_names']
				table_data['path_rtypes'] = data['path_rtypes']
				table_data['path_uids'] = data['path_uids']
				table_data["table_uids"] = [t_item['uid'] for t_item in data['table_items']]
				current_uid = table_data['table_uids'][table_data['row_selector']]
				lwin.set_contents(*table_data.values())
				lwin.draw()
		elif c == curses.KEY_LEFT:
			current_resource = requests.get('http://127.0.0.1:5000/resource/{}'.format(current_uid)).json()['data']
			if current_resource['rtype'] not in ['Application', 'Cluster']:
				# gets the siblings of the parent resource (including parent) and other relevant info
				parent_uid = table_data['path_uids'][-1]
				data = requests.get('http://127.0.0.1:5000/mode/{}/switch/{}'.format(mode, parent_uid)).json()
				table_data['table'] = [[t_item['rtype'], t_item['name']] for t_item in data['table_items']]
				table_data['row_selector'] = data['index']
				table_data['path_names'] = data['path_names']
				table_data['path_rtypes'] = data['path_rtypes']
				table_data['path_uids'] = data['path_uids']
				table_data["table_uids"] = [t_item['uid'] for t_item in data['table_items']]
				current_uid = table_data['table_uids'][table_data['row_selector']]
				lwin.set_contents(*table_data.values())
				lwin.draw()


def main():
	curses.wrapper(run_skipper)

if __name__ == "__main__":
	main()