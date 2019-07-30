import curses, requests, datetime, json, sys, math
from dateutil.parser import parse
import tabulate
tabulate.PRESERVE_WHITESPACE = True
from tabulate import tabulate

this = sys.modules[__name__]

INDENT_AMT = 4 # horizontal indent amount

status = ""

event_headers=["Type", "Reason", "Age", "From", "Message"]
metrics_headers=["","CPU (cores)","CPU Limit","MEM (bytes)","MEM Limit"]

def init(stdscr, panel_height, panel_width, top_height):
	""" 
	makes initial pad and top window
	:param stdscr: window to draw within
	:param panel_height: height of pad
	:param panel_width: width of pad
	:param top_height: height of top panel (y where the top banner should start drawing)
	:return:
	"""
	this.panel_height, this.panel_width, this.top_height = panel_height, panel_width, top_height
	this.scroll_y, this.scroll_x = 0, 0
	draw_pad(panel_height, panel_width)
	this.background_win = curses.newwin(panel_height, panel_width, top_height, panel_width)

def draw_pad(panel_height, panel_width):
	this.win = curses.newpad(panel_height, panel_width)

def draw(ftype, resource_data):
	""" 
	chooses whether to draw summary, yaml, or logs based on keybinding
	:param ftype: yaml / logs / summary
	:resource data: all info relevant to resource
	:return:
	"""
	this.win.erase()
	this.background_win.erase()
	if resource_data == None:
		this.background_win.border(curses.ACS_VLINE, " ", " ", " ", curses.ACS_VLINE, " ", " ", " ")
		this.background_win.refresh()
		this.win.refresh(0, 0, this.top_height+2, this.panel_width+1, this.panel_height+this.top_height-1, 2*this.panel_width-2)
		return

	this.rtype, this.rname = resource_data['rtype'], resource_data['name']

	file_types = { "yaml" : "Yaml: "+ this.rname, "summary" :  this.rtype + ": " + this.rname, "logs" : "Logs: "+ this.rname, "events" : "Events: "+ this.rname}

	if ftype == "yaml":
		if resource_data["rtype"] != "Cluster":
			this.yaml = requests.get('http://127.0.0.1:5000/resource/{}/{}'.format(resource_data["cluster"]+'_'+resource_data["uid"].split('_')[-1], "yaml")).json()["yaml"].split('\n')
		else:
			if resource_data["info"] != "None":
				info = json.loads(resource_data["info"])
				this.yaml = info["yaml"].split('\n')
			else:
				this.yaml = ["Yaml not found"]
		this.doc_height = max(this.panel_height, calc_height(this.yaml, this.panel_width-INDENT_AMT) + 3)
		this.doc_width = this.panel_width
		draw_pad(this.doc_height, this.doc_width)
		draw_yaml(resource_data, this.yaml)

	elif ftype == "logs":
		this.logs = requests.get('http://127.0.0.1:5000/resource/{}/{}'.format(resource_data["cluster"]+'_'+resource_data["uid"].split('_')[-1], "logs")).json()["logs"].split('\n')
		this.doc_height = max(this.panel_height, calc_height(this.logs, this.panel_width-INDENT_AMT) + 3)
		this.doc_width = this.panel_width
		draw_pad(this.doc_height, this.doc_width)
		draw_logs(resource_data, this.logs)

	elif ftype == "events":
		events_table = requests.get('http://127.0.0.1:5000/resource/{}/{}'.format(resource_data["cluster"]+'_'+resource_data["uid"].split('_')[-1], "events")).json()["events"]
		""" 
		when events not found for a resource, message with notification is printed
		when events do exist for the resource, overflow lines of the message column gets wrapped by breaking up the lines and adding them as individual rows
		"""
		if events_table == "Events not found":
			this.doc_height = this.panel_height
			this.doc_width = this.panel_width
			draw_str(this.win, 1, INDENT_AMT, events_table, this.panel_width-2*INDENT_AMT)
		else:
			new_table = []
			if len(events_table):
				short_table = [ event[:-1] for event in events_table ]
				tabulated_short = tabulate(short_table, headers=event_headers[:-1],  tablefmt="github")
				short_width = len(tabulated_short.split('\n')[0])
				width = (this.panel_width-short_width-INDENT_AMT) - 5 # calculating width of column

				messages = [ event[-1] for event in events_table ]
				for msg, event in zip(messages, short_table):
					if len(msg):
						msg = [ msg[i:i + width] for i in range(0, len(msg), width)]
						event.append(msg[0])
					else:
						event.append(msg)
					new_table.append(event)
					if len(msg) > 1:
						for line in msg[1:]:
							new_table.append(["", "", "", "", line])


				new_table = tabulate(new_table, headers=event_headers, tablefmt="github").split('\n')

			else:
				new_table.append("No events found")

			this.doc_width = this.panel_width
			this.doc_height = max(this.panel_height, len(events_table) + 3)
			draw_pad(this.doc_height, this.doc_width)
			draw_events(resource_data, new_table)


	elif ftype == "summary":
		this.doc_height = this.panel_height
		draw_summary(resource_data)
	"""
	INDENT_AMT+1 is to match the alignment of top (name) banner
	"""
	this.background_win.addstr(1, INDENT_AMT+1, file_types[ftype], curses.A_BOLD)
	this.background_win.border(curses.ACS_VLINE, " ", " ", " ", curses.ACS_VLINE, " ", " ", " ")
	this.background_win.refresh()
	# this.win.border(curses.ACS_VLINE, " ", " ", " ", curses.ACS_VLINE, " ", " ", " ")
	this.win.refresh(this.scroll_y, this.scroll_x, top_height+2, panel_width+1, this.panel_height+this.top_height-1, 2*this.panel_width-2)

def draw_yaml(resource_data, yaml):
	""" 
	draws the first lines of yaml that fits, TODO: also get them for custom resources and namespaces
	:resource data: all info relevant to resource
	:return:
	"""
	win, panel_height, panel_width, top_height = this.win, this.panel_height, this.panel_width, this.top_height
	y = 1
	for i in range (len(yaml)):
		y = draw_str(win, y, INDENT_AMT, yaml[i], panel_width-INDENT_AMT-1)

def draw_logs(resource_data, logs):
	""" 
	draws the first lines of logs that fit, also tells user about the nonexistence of logs for resources other than pods"
	:resource data: all info relevant to resource
	:return:
	"""
	win, panel_height, panel_width, top_height = this.win, this.panel_height, this.panel_width, this.top_height
	if resource_data["rtype"] in ["Pod"]:
		for i in range (len(logs)):
			draw_str(win, 1, INDENT_AMT, logs[i], panel_width-INDENT_AMT)
	else:
		win.addstr(1, INDENT_AMT, "Logs only exist for pods")

def draw_events(resource_data, events_table):
	"""
	queries database, formats events with tabulate and then draws it
	:return:
	"""
	win, panel_height, panel_width, top_height = this.win, this.panel_height, this.panel_width, this.top_height

	y = 1
	for line in events_table:
		y = draw_str(win, y, INDENT_AMT, line, panel_width-INDENT_AMT)

def draw_summary(resource_data):
	"""
	refreshes and populates summary pane with info based on resource
	creates top, left, and right derwins for top banner and columns
	:param resource_data: all data related to the current resource to be displayed
	:return:
	"""
	win, length, width, top_height = this.win, this.panel_height, this.panel_width, this.top_height

	if resource_data == None:
		this.win.refresh(0, 0, this.top_height+2, this.panel_width+1, this.panel_height+this.top_height-1, 2*this.panel_width-2)
		return

	rtype, rname = resource_data['rtype'], resource_data['name']
	resource_data["status"] = status

	if resource_data["created_at"] != "None":
		resource_data["age"] = calc_age(datetime.datetime.utcnow() - parse(resource_data["created_at"]))
	else:
		resource_data["age"] = "None"

	resource_data["uid"]  = resource_data["uid"].split("_")[-1]

	info_length = length - 3
	this.left = win.derwin(info_length, width//2-INDENT_AMT, 1, INDENT_AMT)
	this.right = win.derwin(info_length, width//2-2*INDENT_AMT, 1, width//2+INDENT_AMT)

	if rtype == "Application":
		y = draw_app(resource_data)
	elif rtype == "Cluster":
		y = draw_cluster(resource_data)
	elif rtype == "Namespace":
		y = draw_ns(resource_data)
	elif rtype in ["Deployment", "Deployable", "StatefulSet", "ReplicaSet", "DaemonSet"]:
		y = draw_work(resource_data)
	elif rtype == "Pod":
		y = draw_pod(resource_data)
	elif rtype == "Service":
		y = draw_service(resource_data)
	else:
		y = 0

def draw_service(resource_data):
	"""
	fills in left and right windows will info relevant to service
	:resource data: all info relevant to service
	:return: y coordinate to start drawing related resources on
	"""
	win, left, right, length, width = this.win, this.left, this.right, this.panel_height, this.panel_width
	if resource_data["info"] != "None":
		info = json.loads(resource_data["info"])
		labels = info["labels"] if info.get("labels") and (info.get("labels") != "None") else None
		selector = info["selector"] if info.get("selector") and (info.get("selector") != "None") else None
		ports = info["ports"] if info.get("ports") and (info.get("ports") != "None") else None
		# labels, selector, ports = info.get("labels"), info.get("selector"), info.get("ports")
	else:
		labels, selector, ports = None, None, None

	lfields = ["Cluster: " + resource_data["cluster"], "Namespace: " + resource_data["namespace"], "UID: " + resource_data["uid"]]
	rfields = ["Age: " + resource_data["age"], "Created: " + resource_data["created_at"], "Last updated: "+resource_data["last_updated"], "Status: "  + resource_data["status"]]
	y = iterate_info(win, left, right, lfields, rfields, width)

	lefty = righty = y
	if labels is not None:
		lefty = draw_pairs(left, lefty, "Labels:", width//2-INDENT_AMT, labels)
	if selector is not None:
		lefty = draw_pairs(left, lefty, "Selector:", width//2-INDENT_AMT, selector)

	if ports is not None:
		# draw_str(right, righty, INDENT_AMT, str(ports[0]), width//2-2*INDENT_AMT)
		righty = draw_pairs(right, righty, "Ports: ", width//2-2*INDENT_AMT, ports[0])

	return max(lefty,righty)

def draw_work(resource_data):
	""" 
	fills in left and right windows will info relevant to Deployment / Deployable / StatefulSet / ReplicaSet / DaemonSet
	:resource data: all info relevant to Deployment / Deployable / StatefulSet / ReplicaSet / DaemonSet
	:return: y coordinate to start drawing related resources on
	"""
	win, left, right, length, width = this.win, this.left, this.right, this.panel_height, this.panel_width
	if resource_data["info"] != "None":
		info = json.loads(resource_data["info"])
		labels = info["labels"] if info.get("labels") and (info.get("labels") != "None") else None
		status = info["status"] if info.get("status") and (info.get("status") != "None") else None
		available = info["available"] if info.get("available") and (info.get("available") != "None") else "0"
		updated = info["updated" ] if info.get("updated") and (info.get("updated") != "None") else "0"
		ready_reps = info["ready_reps"] if info.get("ready_reps") and (info.get("ready_reps") != "None") else "0"
	else:
		labels, status, available, updated, ready_reps = "None", "None", "None", "None", "None"

	lfields = ["Cluster: " + resource_data["cluster"], "Namespace: " + resource_data["namespace"], "UID: " + resource_data["uid"]]
	rfields = ["Age: " + resource_data["age"], "Created: " + resource_data["created_at"], "Last updated: "+resource_data["last_updated"]]
	if resource_data['rtype'] not in ["Deployable", "StatefulSet"]:
		rfields.extend(["Ready: " + ready_reps, "Available: " + available, "Up-to-date: " + updated])
	y = iterate_info(win, left, right, lfields, rfields, width)

	if labels is not None:
		y = draw_pairs(left, y, "Labels:", width//2-INDENT_AMT, labels)
	if status is not None:
		y = draw_pairs(left, y, "Status:", width//2-INDENT_AMT, status)
	return y

def draw_ns(resource_data):
	"""
	fills in left and right windows will info relevant to namespace
	:resource data: all info relevant to namespace
	:return: y coordinate to start drawing related resources on
	"""
	win, left, right, length, width = this.win, this.left, this.right, this.panel_height, this.panel_width
	if resource_data["info"] != "None":
		info = json.loads(resource_data["info"])
		status = info["status"] if info.get("status") and (info.get("status") != "None") else "None"
		k8s_uid = info["k8s_uid"] if info.get("k8s_uid") and (info.get("k8s_uid") != "None") else "None"
	else:
		status = "None"

	lfields = ["Cluster: " + resource_data["cluster"], "Namespace: " + resource_data["namespace"], "UID: " + k8s_uid]
	rfields = ["Age: " + resource_data["age"], "Created: " + resource_data["created_at"], "Last updated: "+resource_data["last_updated"], "Status: "  + status]

	return iterate_info(win, left, right, lfields, rfields, width)

def draw_app(resource_data):
	"""
	fills in left and right windows will info relevant to app
	:resource data: all info relevant to app
	:return: y coordinate to start drawing related resources on
	"""
	win, left, right, length, width = this.win, this.left, this.right, this.panel_height, this.panel_width
	if resource_data["info"] != "None":
		info = json.loads(resource_data["info"])
		labels = info["labels"] if info.get("labels") and (info.get("labels") != "None") else None
		status = info["status"] if info.get("status") and (info.get("status") != "None") else None
	else:
		labels, status = None, None

	lfields = ["Cluster: " + resource_data["cluster"], "Namespace: " + resource_data["namespace"], "UID: " + resource_data["uid"]]
	rfields = ["Age: " + resource_data["age"], "Created: " + resource_data["created_at"], "Last updated: "+resource_data["last_updated"], "Status: "  + str(status)]

	lefty = iterate_info(win, left, right, lfields, rfields, width)
	righty = lefty

	if labels is not None:
		lefty = draw_pairs(left, lefty, "Labels:", width//2-2*INDENT_AMT, labels)

	# righty = draw_pairs(right, righty, "Deployables: ", width//2-2*INDENT_AMT, info["deployables"].split(","))

	return max(lefty,righty)

def draw_pod(resource_data):
	"""
	fills in left and right windows will info relevant to pod
	:resource data: all info relevant to pod
	:return: y coordinate to start drawing related resources on
	"""
	win, left, right, length, width = this.win, this.left, this.right, this.panel_height, this.panel_width
	if resource_data["info"] != "None":
		info = json.loads(resource_data["info"])
		labels = info["labels"] if info.get("labels") and (info.get("labels") != "None") else None
		owner_refs = info["owner_refs"][0] if info.get("owner_refs") and (info.get("owner_refs") != "None") else None
		host_ip = info["host_ip"] if info.get("host_ip") and (info.get("host_ip") != None) else "None"
		phase = info["phase"] if info.get("phase") and (info.get("phase") != None) else "None"
		pod_ip = info["pod_ip"] if info.get("pod_ip") and (info.get("pod_ip") != None) else "None"
		ready = info["ready"] if info.get("ready") and (info.get("ready") != None) else "None"
		restarts = info["restarts"] if info.get("restarts") and (info.get("restarts") != None) else "None"
		container_count = info["container_count"] if info.get("container_count") and (info.get("container_count") != None) else "None"
		pod_metrics = info["pod_metrics"]
		container_metrics = info["container_metrics"]
	else:
		labels, owner_refs, host_ip, phase, pod_ip, ready, restarts, container_count = None, None, "None", "None", "None", "None", "None", "None"

	lfields = ["Cluster: " + resource_data["cluster"], "Namespace: " + resource_data["namespace"], "UID: " + resource_data["uid"], "PodIP: " + pod_ip, "Node/HostIP: " + host_ip]
	rfields = ["Ready: " + ready, "Restarts: " + restarts, "Age: " + resource_data["age"], "Created: " + resource_data["created_at"], "Last updated: "+resource_data["last_updated"], "Status: "  + phase]

	lefty = iterate_info(win, left, right, lfields, rfields, width)
	righty = lefty

	if labels is not None:
		lefty = draw_pairs(left, lefty, "Labels:", width//2-INDENT_AMT, labels)

	if owner_refs is not None:
		righty = draw_pairs(right, righty, "Owner References:", width//2-2*INDENT_AMT, owner_refs)

	y = max(lefty,righty) + 3
	win.addstr(y + 1, INDENT_AMT, "Compute Resources", curses.A_BOLD)
	y += 3

	if container_metrics is None:
		win.addstr(y, INDENT_AMT, "Could not retrieve pod/container data")
		y += 1
	else:
		metrics_table = [['Pod', pod_metrics['cpu'], pod_metrics['cpu_limit'], pod_metrics['mem'], pod_metrics['mem_limit']]]
		metrics_table.append(["", "", "", "", ""])
		metrics_table.append(["Containers:", "", "", "", ""])

		for ct in container_metrics['containers']:
			ct_dict = container_metrics['containers'][ct]
			metrics_table.append([" "*INDENT_AMT + ct, ct_dict['cpu'], ct_dict['cpu_limit'], ct_dict['mem'], ct_dict['mem_limit']])
		if container_metrics['init_containers']:
			metrics_table.append(["", "", "", "", ""])
			metrics_table.append(["Init Containers:", "", "", "", ""])
			for ct in container_metrics['init_containers']:
				ct_dict = container_metrics['init_containers'][ct]
				metrics_table.append([" "*INDENT_AMT + ct, ct_dict['cpu'], ct_dict['cpu_limit'], ct_dict['mem'], ct_dict['mem_limit']])
		lines = tabulate(metrics_table, headers=metrics_headers).split('\n')
		for line in lines:
			y = draw_str(win, y, INDENT_AMT, line, width-2*INDENT_AMT)

	return y

def draw_cluster(resource_data):
	"""
	fills in left and right windows will info relevant to cluster
	:resource data: all info relevant to cluster
	:return: y coordinate to start drawing related resources on
	"""
	win, left, right, length, width = this.win, this.left, this.right, this.panel_height, this.panel_width
	if resource_data["info"] != "None":
		info = json.loads(resource_data["info"])
		status = info["status"] if info.get("status") and (info.get("status") != "None") else None
		labels = info["labels"] if info.get("labels") and (info.get("labels") != "None") else None
		remote_name = info["remote_name"]
		remote_namespace = info["remote_namespace"]
		k8s_uid = info["k8s_uid"]

		lfields = ["Local Cluster Name: " + resource_data["cluster"], "UID: " + k8s_uid, "Remote Cluster Name: " + remote_name, "Namespace on Hub: " + remote_namespace]
		rfields = ["Age: " + resource_data["age"], "Created: " + resource_data["created_at"], "Last updated: "+resource_data["last_updated"] ]
		lefty = righty = iterate_info(win, left, right, lfields, rfields, width)

		if labels is not None:
			lefty = draw_pairs(left, lefty, "Labels:", width//2-INDENT_AMT, labels)
		if status is not None:
			righty = draw_pairs(right, righty, "Conditions:", width//2-2*INDENT_AMT, status['conditions'][0])
	else:
		lines = [ "Welcome to Skipper, a cross-cluster terminal application", \
				  "Looks like the cluster \"" + this.rname + "\" is not an MCM cluster", \
				  "More info about your cluster can be loaded when using IBM's Multicloud Manager"
					]
		righty = lefty = 1
		for line in lines:
			lefty = draw_str(win, lefty, INDENT_AMT, line, width-2*INDENT_AMT)+1
	return max(lefty, righty)

def calc_age(time):
	"""
	turns datetime or timedelta object into an age string
	:param time: date object
	:return: string of age followed by 1 char unit of time
	"""
	if time.days == 0:
		hours = time.seconds // 3600
		if hours == 0:
			minutes = time.seconds // 60
			if minutes == 0:
				return str(time.seconds)
			return str(minutes)+"m"
		return str(hours)+"h"
	return str(time.days)+"d"

def calc_height(lines, width):
	y = 0
	for line in lines:
		y += math.ceil(len(line) / width)
	return y


def iterate_info(win, left, right, lfields, rfields, width):
	"""
	draws lines of information for left and right columns
	:param win: window to draw in
	:param left: left column window
	:param right: right column window
	:param lfields: list of fields/ info to fill in for left column
	:param rfields: list of fields/ info to fill in for right column
	:param width: width of entire right panel
	:return: y coordinate that the columns end on (whichever ends later)
	"""
	lefty, righty = 0, 0
	for string in lfields:
	   lefty = draw_str(left, lefty, 0, string, width//2-2*INDENT_AMT)

	for string in rfields:
	   righty = draw_str(right, righty, 0, string, width//2-2*INDENT_AMT)

	return max(lefty, righty)

def iterate_indented_pairs(win, start_y, start_x, pairs, alloted_width, indent = False):
	"""
	draws and wraps pairs of information, where pairs are indented one from title
	:param start_y: y coord to start in
	:param start_x: x coord to start in
	:param pairs: dict of information to draw
	:param alloted_width: width of allowed  before wrapping
	:param indent (optional): whether to indent the pairs
	:return: y coordinate that the pairs end on
	"""
	for pair in pairs:
		pair = pair+"="+str(pairs[pair])
		if (len(pair) > alloted_width-(INDENT_AMT*indent)):
			lines = [ pair[i:i + alloted_width-INDENT_AMT*indent] for i in range(0, len(pair), alloted_width-INDENT_AMT*indent) ]
			win.addstr(start_y, start_x+(INDENT_AMT*indent), lines[0])
			lines = lines[1:]
			start_y += 1
			for line in lines:
				# win.addstr(start_y, start_x+(INDENT_AMT*indent), line)
				win.addstr(start_y, start_x+(INDENT_AMT*indent), line)
				start_y += 1
		else:
			win.addstr(start_y, start_x+(INDENT_AMT*indent), pair)
			start_y += 1
	return start_y

def draw_str(win, y, x, string, maxw):
	"""
	draws and wraps string
	:param win: window to draw in
	:param y: y coord to start in
	:param x: x coord to start in
	:param string: string to be drawn
	:param maxw: width of allowed before wrapping
	:return: y coordinate that the string ends on
	"""
	if (len(string) > maxw):
		lines = [ string[i:i + maxw] for i in range(0, len(string), maxw) ]
		win.addstr(y, x, lines[0])
		lines = lines[1:]
		y += 1
		for line in lines:
			win.addstr(y, x, line)
			y += 1
	else:
		win.addstr(y, x, string)
		y += 1
	return y

def draw_pairs(win, y, name, width, pairs):
	"""
	draws title and info (which are pairs)
	:param win: window to draw in
	:param y: y coord to start in
	:param name: type/name/title of pairs to be drawn
	:param width: width allowed before wrapping
	:param pairs: dict of pairs to be drawn
	:return: y coordinate that the string ends on
	"""
	y = draw_str(win, y+1, 0, name, width)
	y = iterate_indented_pairs(win, y, 0, pairs, width, indent = True)
	return y
