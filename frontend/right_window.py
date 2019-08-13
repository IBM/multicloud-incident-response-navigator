import curses, requests, datetime, json, sys, math
from dateutil.parser import parse
import tabulate
tabulate.PRESERVE_WHITESPACE = True
from tabulate import tabulate

sys.path.insert(0,'./../backend')
import metrics

this = sys.modules[__name__]

INDENT_AMT = 5 # horizontal indent amount

status = ""

event_headers=["Type", "Reason", "Age", "From", "Message"]
metrics_headers=["","CPU (cores)","CPU Limit","MEM (bytes)","MEM Limit"]

def init(panel_height, panel_width, top_height):
	""" 
	Makes initial pad and top window of the right pane
	:param panel_height: height of pad
	:param panel_width: width of pad
	:param top_height: height of top panel (y where the top banner should start drawing)
	:return: None
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
	:param (str) ftype: yaml / logs / summary / events
	:param (Dict) resource data: all info relevant to resource
	:return: None
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
		get_yaml(resource_data)
		this.doc_height = max(this.panel_height, calc_height(this.yaml, this.panel_width-INDENT_AMT) + 5)
		this.doc_width = this.panel_width
		draw_pad(this.doc_height, this.doc_width)
		draw_yaml(this.yaml)

	elif ftype == "logs":
		this.logs = requests.get('http://127.0.0.1:5000/resource/{}/{}'.format(resource_data["cluster"]+'_'+resource_data["uid"].split('_')[-1], "logs")).json()["logs"].split('\n')
		this.doc_height = max(this.panel_height, calc_height(this.logs, this.panel_width-INDENT_AMT) + 5)
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
				short_table = [ event[:-1] for event in events_table ] # table w/o the last message column
				tabulated_short = tabulate(short_table, headers=event_headers[:-1],  tablefmt="github")
				short_width = len(tabulated_short.split('\n')[0]) # width of the shortened table
				width = (this.panel_width-short_width-INDENT_AMT) - 5 # calculating width of column

				messages = [ event[-1] for event in events_table ]
				for msg, event in zip(messages, short_table):
					if len(msg):
						msg = msg.replace('\n', '')
						msg = [ msg[i:i + width] for i in range(0, len(msg), width)]
						event.append(msg[0]) # appending first line  of message to row of events
					else:
						event.append(msg) # or if message is empty, append that
					new_table.append(event) # adding new event to constructed table

					if len(msg) > 1:
						for line in msg[1:]:
							new_table.append(["", "", "", "", line])

				new_table = tabulate(new_table, headers=event_headers, tablefmt="github").split('\n')

			else:
				new_table.append("No events found")
			this.doc_width = this.panel_width
			this.doc_height = max(len(new_table) + 5, this.panel_height)
			draw_pad(this.doc_height, this.doc_width)
			draw_events(new_table)

	elif ftype == "summary":
		get_yaml(resource_data)
		draw_pad(max(this.panel_height, calc_height(this.yaml, this.panel_width-INDENT_AMT) + 5), this.panel_width)
		this.doc_height = max(this.panel_height, draw_summary(resource_data))

	# INDENT_AMT+1 is to match the alignment of top (name) banner
	this.background_win.addstr(1, INDENT_AMT+1, file_types[ftype], curses.A_BOLD)
	this.background_win.border(curses.ACS_VLINE, " ", " ", " ", curses.ACS_VLINE, " ", " ", " ")
	this.background_win.refresh()
	this.win.refresh(this.scroll_y, this.scroll_x, top_height+2, panel_width+1, this.panel_height+this.top_height-1, 2*this.panel_width-2)

def draw_yaml(yaml):
	""" 
	Draws the resource yaml in right win
	:param (List[str]) yaml
	:return: None
	"""
	win, panel_height, panel_width, top_height = this.win, this.panel_height, this.panel_width, this.top_height
	y = 1
	for i in range (len(yaml)):
		y = draw_str(win, y, INDENT_AMT, yaml[i], panel_width-INDENT_AMT)

def draw_logs(resource_data, logs):
	""" 
	Draws logs, or tells user about the nonexistence of logs for resources other than pods
	:param (Dict) resource data: all info relevant to resource
	:return: None
	"""
	win, panel_height, panel_width, top_height = this.win, this.panel_height, this.panel_width, this.top_height
	if resource_data["rtype"] in ["Pod"]:
		for i in range (len(logs)):
			draw_str(win, 1, INDENT_AMT, this.logs[i], panel_width-INDENT_AMT)
	else:
		win.addstr(1, INDENT_AMT, "Logs only exist for pods")

def draw_events(events_table):
	"""
	Draw events table
	:param (List[str]) events_table
	:return: None
	"""
	win, panel_height, panel_width, top_height = this.win, this.panel_height, this.panel_width, this.top_height

	y = 1
	for line in events_table:
		y = draw_str(win, y, INDENT_AMT, line, panel_width-INDENT_AMT)

def draw_summary(resource_data):
	"""
	Refreshes and populates summary pane with info based on resource
	Creates top, left, and right derwins for top banner and columns
	:param (Dict) resource_data: all data related to the current resource to be displayed
	:return: None
	"""
	win, length, width, top_height = this.win, this.panel_height, this.panel_width, this.top_height

	if resource_data == None:
		this.win.refresh(0, 0, this.top_height+2, this.panel_width+1, this.panel_height+this.top_height-1, 2*this.panel_width-2)
		return

	rtype, rname, resource_data['status'] = resource_data['rtype'], resource_data['name'],  status

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

	return y

def get_yaml(resource_data):
	"""
	Get the resource yaml and set this.yaml
	:param (Dict) resource data: all info relevant to resource
	:return: None
	"""
	if resource_data["rtype"] != "Cluster":
		this.yaml = requests.get('http://127.0.0.1:5000/resource/{}/{}'.format(resource_data["cluster"]+'_'+resource_data["uid"].split('_')[-1], "yaml")).json()["yaml"].split('\n')
	else: # cluster yamls are stored instead of directly queried from the api
		if resource_data["info"] != "None":
			info = json.loads(resource_data["info"])
			yaml = info["yaml"]
			this.yaml = yaml.split('\n')
		else:
			this.yaml = ["Yaml not found"]

def draw_service(resource_data):
	"""
	Fills in left and right summary windows with info relevant to service
	:param (Dict) resource data: all info relevant to resource
	:return: end y coordinate
	"""
	win, left, right, length, width = this.win, this.left, this.right, this.panel_height, this.panel_width
	labels, selector, ports, status = None, None, None, None
	if resource_data["info"] != "None":
		info = json.loads(resource_data["info"])
		labels = info["metadata"]["labels"] if info["metadata"].get("labels") else None
		selector = info["spec"]["selector"] if info["spec"].get("selector") else None
		ports = info["spec"]["ports"] if info["spec"].get("ports") else None
		status = info["status"]

	lfields = ["Cluster: " + resource_data["cluster"], "Namespace: " + resource_data["namespace"], "UID: " + resource_data["uid"]]
	rfields = ["Age: " + resource_data["age"], "Created: " + resource_data["created_at"], "Last updated: "+resource_data["last_updated"]]

	if resource_data.get("application"):
		lfields.append("Application: " + resource_data["application"])

	y = iterate_info(left, right, lfields, rfields, width)

	lefty = righty = y
	if labels is not None:
		lefty = draw_pairs(left, lefty, "Labels:", width//2-INDENT_AMT, labels)
	if selector is not None:
		lefty = draw_pairs(left, lefty, "Selector:", width//2-INDENT_AMT, selector)
	if ports is not None:
		righty = draw_pairs(right, righty, "Ports: ", width//2-2*INDENT_AMT, ports[0])
	if status is not None:
		righty = draw_pairs(right, righty, "Status: ", width//2-2*INDENT_AMT, status)

	return max(lefty,righty)

def draw_work(resource_data):
	"""
	Fills in left and right summary windows with info relevant to Deployment / Deployable / StatefulSet / DaemonSet
	:param (Dict) resource data: all info relevant to resource
	:return: end y coordinate
	"""
	win, left, right, length, width = this.win, this.left, this.right, this.panel_height, this.panel_width
	labels, available, unavailable, updated, reps, ready = None, "None", "None", "None", 'None', 'None'
	if resource_data["info"] != "None":
		info = json.loads(resource_data["info"])
		labels = info["metadata"]["labels"] if info["metadata"].get("labels") else None
		status = info["status"] if info.get("status") else {}
		if (resource_data['rtype'] == 'Deployment'):
			updated = str(status["updated_replicas"]) if status.get("updated_replicas") else "0"
			available = str(status["available_replicas"]) if status.get("available_replicas") else "0"
			ready = str(status["ready_replicas"]) if status.get("ready_replicas") else "0"
			reps = str(status["replicas"]) if status.get("replicas")  else "0"

		elif (resource_data['rtype'] == 'DaemonSet'):
			updated = str(status["updated_number_scheduled"]) if status.get("updated_number_scheduled") else "0"
			available = str(status["number_available"]) if status.get("number_available")else "0"
			ready = str(status["number_ready"]) if status.get("number_ready") else "0"
			reps = str(status["desired_number_scheduled"]) if status.get("desired_number_scheduled")  else "0"

		elif (resource_data['rtype'] == 'StatefulSet'):
			reps = str(status["replicas"]) if status.get("replicas")  else "0"
			ready = str(status["ready_replicas"]) if status.get("ready_replicas")  else "0"

	ready_reps = ready + '/' + reps
	lfields = ["Cluster: " + resource_data["cluster"], "Namespace: " + resource_data["namespace"], "UID: " + resource_data["uid"]]
	rfields = ["Age: " + resource_data["age"], "Created: " + resource_data["created_at"], "Last updated: "+resource_data["last_updated"]]

	if resource_data.get("application"):
		lfields.append("Application: " + resource_data["application"])

	if resource_data['rtype'] == "Deployment":
		rfields.extend(["Ready: " + ready_reps, "Up-to-date: " + updated, "Available: " + available])

	elif resource_data['rtype'] == "DaemonSet":
		rfields.extend(["Up-to-date: " + updated, "Available: " + available, "Ready: " + ready])

	elif resource_data['rtype'] == "StatefulSet":
		rfields.append("Ready: " + ready_reps)
	y = iterate_info(left, right, lfields, rfields, width)

	lefty = righty = y

	if labels is not None:
		lefty = draw_pairs(left, y, "Labels:", width//2-INDENT_AMT, labels)

	if resource_data['rtype'] in ["StatefulSet", "DaemonSet"] and resource_data["info"] != "None":
		righty = draw_pairs(right, righty, "Status:", width//2-2*INDENT_AMT, info["status"])

	return max(lefty, righty)

def draw_ns(resource_data):
	"""
	Fills in left and right summary windows with info relevant to Namespace
	:param (Dict) resource data: all info relevant to resource
	:return: end y coordinate
	"""
	win, left, right, length, width = this.win, this.left, this.right, this.panel_height, this.panel_width
	k8s_uid = resource_data["uid"]
	status = "None"
	if resource_data["info"] != "None":
		info = json.loads(resource_data["info"])
		if info.get("status"):
			status = info["status"]["phase"] if isinstance(info["status"], dict) else str(info["status"])

	lfields = ["Cluster: " + resource_data["cluster"], "Namespace: " + resource_data["namespace"], "UID: " + k8s_uid]
	rfields = ["Age: " + resource_data["age"], "Created: " + resource_data["created_at"], "Last updated: "+resource_data["last_updated"], "Status: "  + str(status)]

	return iterate_info(left, right, lfields, rfields, width)

def draw_app(resource_data):
	"""
	Fills in left and right summary windows with info relevant to Application
	:param (Dict) resource data: all info relevant to resource
	:return: end y coordinate
	"""
	win, left, right, length, width = this.win, this.left, this.right, this.panel_height, this.panel_width
	if resource_data["info"] != "None":
		info = json.loads(resource_data["info"])
		labels = info["metadata"]["labels"] if info["metadata"].get("labels") else None
		status = info["status"]

	else:
		labels, status = None, None

	lfields = ["Cluster: " + resource_data["cluster"], "Namespace: " + resource_data["namespace"], "UID: " + resource_data["uid"]]
	rfields = ["Age: " + resource_data["age"], "Created: " + resource_data["created_at"], "Last updated: "+resource_data["last_updated"], "Status: "  + str(status)]

	if resource_data.get("application"):
		lfields.append("Application: " + resource_data["application"])

	lefty = iterate_info(left, right, lfields, rfields, width)
	righty = lefty

	if labels is not None:
		lefty = draw_pairs(left, lefty, "Labels:", width//2-2*INDENT_AMT, labels)

	return max(lefty,righty)

def draw_pod(resource_data):
	"""
	Fills in left and right summary windows with info relevant to Pod
	:param (Dict) resource data: all info relevant to resource
	:return: end y coordinate
	"""
	win, left, right, length, width = this.win, this.left, this.right, this.panel_height, this.panel_width
	host_ip, pod_ip, ready, restarts = parse_pod_status(resource_data)

	if resource_data["info"] != "None":
		info = json.loads(resource_data["info"])
		if info.get("metadata") is not None:
			labels = info["metadata"]["labels"] if info["metadata"].get("labels") else None
			owner_refs = info["metadata"]["owner_references"][0] if info["metadata"].get("owner_references") else None

	status = resource_data['sev_reason']
	lfields = ["Cluster: " + resource_data["cluster"], "Namespace: " + resource_data["namespace"], "UID: " + resource_data["uid"], "PodIP: " + pod_ip, "Node/HostIP: " + host_ip]
	rfields = ["Ready: " + ready, "Restarts: " + restarts, "Age: " + resource_data["age"], "Created: " + resource_data["created_at"], "Last updated: "+resource_data["last_updated"], "Status: "  + status]

	if resource_data.get("application"):
		lfields.append("Application: " + resource_data["application"])

	lefty = iterate_info(left, right, lfields, rfields, width)
	righty = lefty

	if labels is not None:
		lefty = draw_pairs(left, lefty, "Labels:", width//2-INDENT_AMT, labels)

	if owner_refs is not None:
		righty = draw_pairs(right, righty, "Owner References:", width//2-2*INDENT_AMT, owner_refs)

	y = max(lefty,righty) + 3
	win.addstr(y + 1, INDENT_AMT, "Compute Resources", curses.A_BOLD)
	y += 3

	pod_metrics, container_metrics = metrics.aggregate_pod_metrics(resource_data["cluster"], resource_data["namespace"], resource_data["name"])

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

	return y + 3

def parse_pod_status(pod_dict):
	"""
	Using dictionary with db data for a given pod, returns information about pod status
	:param (Dict) pod_dict: all pod info
	:return: (str) host_ip, (str) pod_ip, (str) ready, (str) restarts
	"""
	host_ip, pod_ip, ready, restarts= "None", "None", "None", "None"
	if pod_dict["info"] != "None":
		info = json.loads(pod_dict["info"])
		if info.get("status") is not None:
			status = info.get("status")
			host_ip = status["host_ip"] if status.get("host_ip") else "None"
			pod_ip = status["pod_ip"] if status.get("pod_ip") else "None"
			container_statuses = status.get("container_statuses")
			if container_statuses is not None:
				ready, restarts = 0, 0
				container_count = len(container_statuses)
				for c in container_statuses:
					ready += c["ready"]
					restarts += c["restart_count"]
				ready = str(ready)
				restarts = str(restarts)
				container_count = str(container_count)
				ready = ready + "/" + container_count
	return host_ip, pod_ip, ready, restarts

def draw_cluster(resource_data):
	"""
	Fills in left and right summary windows with info relevant to Cluster
	:param (Dict) resource data: all info relevant to resource
	:return: end y coordinate
	"""
	win, left, right, length, width = this.win, this.left, this.right, this.panel_height, this.panel_width
	if resource_data["info"] != "None":
		mcm_cluster = json.loads(resource_data["info"])
		status = mcm_cluster["status"] if mcm_cluster.get("status") else None
		labels = mcm_cluster["metadata"]["labels"] if mcm_cluster["metadata"].get("labels") else None
		remote_name = mcm_cluster["metadata"]["name"] if mcm_cluster["metadata"].get("name") else "None"
		remote_namespace = mcm_cluster["metadata"]["namespace"] if mcm_cluster["metadata"].get("namespace") else "None"
		k8s_uid = mcm_cluster["metadata"]["uid"] if mcm_cluster["metadata"].get("uid") else "None"

		lfields = ["Local Cluster Name: " + resource_data["cluster"], "UID: " + k8s_uid, "Remote Cluster Name: " + remote_name, "Namespace on Hub: " + remote_namespace]
		rfields = ["Age: " + resource_data["age"], "Created: " + resource_data["created_at"], "Last updated: "+resource_data["last_updated"] ]
		lefty = righty = iterate_info(left, right, lfields, rfields, width)

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
	Turns datetime or timedelta object into an age string
	:param (Datetime) time: date object
	:return: (str) age followed by 1 char unit of time
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
	"""
	Calculate height of lines of text with wrapping
	:param (List[str]) lines: original lines of text
	:param (int) width: max width before wrapping
	:return: (int) lines with wrapping taken into account
	"""
	y = 0
	for line in lines:
		y += math.ceil(len(line) / width)
	return y

def iterate_info(left, right, lfields, rfields, width):
	"""
	Draws lines of information for left and right columns
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
	Draws and wraps pairs of information, where pairs are indented one from title
	:param win: window to draw in
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
				win.addstr(start_y, start_x+(INDENT_AMT*indent), line)
				start_y += 1
		else:
			win.addstr(start_y, start_x+(INDENT_AMT*indent), pair)
			start_y += 1
	return start_y

def draw_str(win, y, x, string, maxw):
	"""
	Draws and wraps string
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
	Draws title and info (which are pairs)
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
