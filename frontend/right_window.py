import curses

INDENT_AMT = 4 # horizontal indent amount

labels = [ "app=gbapp", "chart=gbapp-0.1.0", "heritage=Tiller", "name=boisterous-shark-gbapp", "release=boisterous-shark" ]
ownerRefs = ["apiVersion: apps/v1", "blockOwnerDeletion: true", "controller: true", "kind: ReplicaSet", "name: boisterous-shark-gbapp-frontend-8b5cc67bf" ,"uid: 3a24c572-990e-11e9-b68f-0e70a6ce6d3a"]
deployables = "boisterous-shark-gbapp-frontend,boisterous-shark-gbapp-service,boisterous-shark-gbapp-redismaster,boisterous-shark-gbapp-redismasterservice,boisterous-shark-gbapp-redisslave,boisterous-shark-gbapp-redisslaveservice"
age = "12 days" # need to calculate from Createdstamp
events_list = ["this can be a very long line of events and this super long string is just to demonstrate"]
hostIP = "10.1.15.230"
podIP = "10.0.0.89"
status = ""
# pod specific info
ready = '1/1'
restarts = "0"

# service-specific info
ports = ["nodePort=30323", "port=80", "protocol=TCP", "targetPort=80" ]
pod_selector = ["app=gbapp", "release=boisterous-shark","tier=frontend" ]

def iterate_indented_pairs(win, start_y, start_x, pairs, alloted_width, indent = False):
	for pair in pairs:
		win.addstr(start_y, start_x+(INDENT_AMT*indent), pair)
		if (len(pair) + start_x + (INDENT_AMT*indent)) > alloted_width:
			start_y += 1 # need to take of multi-line wrapping
		start_y += 1
	return start_y

def draw_str(win, y, x, string, maxw):
	win.addstr(y, x, string)
	if len(string) > maxw: # need to take of multi-line wrapping
		y += 1
	return y + 1

def draw_pairs(win, y, name, width, pairs):
	y = draw_str(win, y+1, 0, name, width)
	y = iterate_indented_pairs(win, y, 0, pairs, width, indent = True)
	return y

def draw_summary(win, length, width, resource_data):
	win.erase()
	# win.box()
	win.border(curses.ACS_VLINE, " ", " ", " ", " ", " ", " ")
	rtype, rname = resource_data['rtype'], resource_data['name']
	resource_data["labels"] = labels
	resource_data["status"] = status
	resource_data["age"] = age
	if rtype != "cluster":
		resource_data["uid"]  = resource_data["uid"].split("_")[-1]

	# top banner displaying resource type and name
	top_banner = win.derwin(3, width, 0, 0) # window.derwin(nlines (optional), ncols (optional), begin_y, begin_x)
	top_banner.addstr(1, INDENT_AMT, rtype  + ": " + rname, curses.A_BOLD )
	# top_banner.hline(4, 1, curses.ACS_HLINE, 2*width-2)

	info_length = length-3
	left = win.derwin(info_length//2, width//2-INDENT_AMT, 3, INDENT_AMT)
	right = win.derwin(info_length//2, width//2-2*INDENT_AMT, 3, width//2+INDENT_AMT)

	if rtype == "Application":
		y = draw_app(win, left, right, length, width, resource_data)
	elif rtype == "Cluster":
		resource_data["status"] = ""
		y = draw_cluster(win, left, right, length, width, resource_data)
	elif rtype == "Namespace":
		resource_data["status"] = ""
		y = draw_ns(win, left, right, length, width, resource_data)
	elif rtype in ["Deployment", "Deployable", "StatefulSet", "ReplicaSet", "DaemonSet"]:
		resource_data["status"] = ""
		y = draw_work(win, left, right, length, width, resource_data)
	elif rtype == "Pod":
		y = draw_pod(win, left, right, length, width, resource_data)
	elif rtype == "Service":
		y = draw_service(win, left, right, length, width, resource_data)
	else:
		y = 0

	y += 3 # to account for top banner length
	draw_related_resources(win, y + 5, {})
	win.refresh()

def draw_related_resources(win, y, resources):
	win.addstr(y, INDENT_AMT, "Related Resources", curses.A_BOLD)

def draw_service(win, left, right, length, width, resource_data):
	lefty, righty = 0, 0
	for string in ["Cluster: " + resource_data["cluster"], "Namespace: " + resource_data["namespace"], "UID: " + resource_data["uid"]]:
	   lefty = draw_str(left, lefty, 0, string, width)+1

	for string in ["Created: " + resource_data["created_at"], "Last updated: "+resource_data["last_updated"], "Status: "  + resource_data["status"]]:
	   righty = draw_str(right, righty, 0, string, width)+1

	lefty = righty = max(lefty, righty)
	lefty = draw_pairs(left, lefty, "Labels:", width//2-INDENT_AMT, labels)
	lefty = draw_pairs(left, lefty, "Selector:", width//2-INDENT_AMT, pod_selector)

	righty = draw_pairs(right, righty, "Ports: ", width//2-2*INDENT_AMT, ports)

	return max(lefty, righty)

def draw_work(win, left, right, length, width, resource_data):
	lefty, righty = 0, 0
	for string in ["Cluster: " + resource_data["cluster"], "Namespace: " + resource_data["namespace"], "UID: " + resource_data["uid"]]:
	   lefty = draw_str(left, lefty, 0, string, width)+1

	for string in ["Created: " + resource_data["created_at"], "Last updated: "+resource_data["last_updated"], "Status: "  + resource_data["status"]]:
	   righty = draw_str(right, righty, 0, string, width)+1

	return max(lefty, righty)

def draw_ns(win, left, right, length, width, resource_data):
	lefty, righty = 0, 0
	for string in ["Cluster: " + resource_data["cluster"], "Namespace: " + resource_data["namespace"], "UID: " + resource_data["uid"]]:
	   lefty = draw_str(left, lefty, 0, string, width)+1

	for string in ["Created: " + resource_data["created_at"], "Last updated: "+resource_data["last_updated"], "Status: "  + resource_data["status"]]:
	   righty = draw_str(right, righty, 0, string, width)+1

	return max(lefty, righty)

# Further needed info: labels, status, age, deployables, events)
def draw_app(win, left, right, length, width, resource_data):
	lefty, righty = 0, 0
	for string in ["Cluster: " + resource_data["cluster"], "Namespace: " + resource_data["namespace"], "UID: " + resource_data["uid"]]:
	   lefty = draw_str(left, lefty, 0, string, width//2-2*INDENT_AMT)

	for string in ["Age: " + resource_data["age"], "Created: " + resource_data["created_at"], "Last updated: "+resource_data["last_updated"], "Status: "  + resource_data["status"]]:
	   righty = draw_str(right, righty, 0, string, width)

	lefty = righty = max(lefty, righty)

	lefty = draw_pairs(left, lefty, "Labels:", width//2-INDENT_AMT, labels)
	righty = draw_pairs(right, righty, "Deployables: ", width//2-2*INDENT_AMT, deployables.split(","))
	righty = draw_pairs(right, righty, "Status:", width//2-2*INDENT_AMT, resource_data["status"])

	bottom = win.derwin(3+max(lefty, righty), INDENT_AMT)

	y = draw_str(bottom, 0, 0, "Events:", width-2*INDENT_AMT) + max(lefty,righty)

	return y

def draw_pod(win, left, right, length, width, resource_data):
	lefty, righty = 0, 0
	for string in ["Cluster: " + resource_data["cluster"], "Namespace: " + resource_data["namespace"], "UID: " + resource_data["uid"], "PodIP: " + podIP, "Node/HostIP: " + hostIP]:
	   lefty = draw_str(left, lefty, 0, string, width)

	for string in ["Ready: " + ready, "Restarts: " + restarts, "Age: " + age, "Created: " + resource_data["created_at"], "Last updated: "+resource_data["last_updated"], "Status: "  + resource_data["status"]]:
	   righty = draw_str(right, righty, 0, string, width)

	lefty = righty = max(lefty, righty)

	lefty = draw_pairs(left, lefty, "Labels:", width//2-INDENT_AMT, labels)

	righty = draw_pairs(right, righty, "OwnerReferences", width//2-2*INDENT_AMT, ownerRefs)

	return max(lefty, righty)

def draw_cluster(win, left, right , length, width, resource_data):
	lines = [ "Welcome to Skipper, a cross-cluster terminal application", \
			  "We will be loading in more info about your cluster in the future", \
			  "But for now please scroll and arrow right to view more resources"
				]
	lefty = 3
	for line in lines:
		lefty = draw_str(win, lefty, INDENT_AMT, line, width)+1
	return lefty
