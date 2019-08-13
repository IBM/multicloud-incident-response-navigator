import sys, requests, datetime, json
import sqlalchemy, yaml
from dateutil.parser import parse
from flask import request, jsonify
from app import app, db
from app.models import Resource, Edge

sys.path.insert(0,'../../backend')
import resource_files, metrics
import clients_resources, k8s_config
import cluster_mode_backend as cmb
import app_mode_backend as amb
import errors_backend as eb

# loads the user's kube-config
# gets exception info if something went wrong in the process
running, e = k8s_config.load_kube_config()
info_handler = resource_files.ResourceFiles()

def to_json(k8s_obj) -> str:
	"""
	Turn object to json using json.dumps() on object dictionary, defaulting to __str__
	"""
	to_s = lambda dt: dt.__str__()
	return json.dumps(k8s_obj.to_dict(), default=to_s)

# check if user has a db
try:
	db.session.query(Resource).first()
except sqlalchemy.exc.OperationalError as e:
	db.create_all()

def row_to_dict(row) -> dict:
	"""
	Helper function that converts a Resource or Edge into a dictionary
	"""
	d = {}
	for column in row.__table__.columns:
		d[column.name] = str(getattr(row, column.name))
	return d

def has_children(table):
	"""
	Returns List[bool] for whether each item in table has children or not.
	"""
	has_children = []
	for t_item in table:
		has_children.append(False if db.session.query(Edge).filter(Edge.start_uid == t_item.uid).first() is None else True)
	return has_children

@app.route('/')
@app.route('/index')
def index():
	return "Hello, World!"

@app.route('/running')
def status():
	"""
	Returns info regarding any exceptions encountered when loading the user's kube-config.
	"""
	exc_str = str(type(e)) + "\n" + str(e)
	return jsonify(running=running, exception=exc_str)

@app.route('/start/<mode>')
def start(mode):
	"""
	Retrieves and stores clusters+namespaces, and applications+deployables, and returns starting table
	:param mode: 'app' or 'cluster'
	:return: json response including path_names (List[str], list of names of resources in the path),
									path_rtypes (List[str], list of rtypes of resources in the path),
									path_uids (List[str], list of skipper uids of resources in the path),
									table_items (List[Dict], list of dictionaries for resources to be displayed),
									index (int, row to be selected),
									has_children (List[bool]), whether each resource in table has children),
									has_apps (bool, if MCM applications are found)
	"""

	cluster_rows = db.session.query(Resource).filter(Resource.rtype=="Cluster").all()
	if len(cluster_rows) == 0:
		# lazy load clusters
		clusters = k8s_config.all_cluster_names()
		mcm_clusters = cmb.mcm_clusters(clusters)
		for cluster in clusters:
			if cluster in mcm_clusters:
				mcm_cluster  = mcm_clusters[cluster]
				mcm_cluster["yaml"] = yaml.dump(mcm_cluster, sort_keys=False)
				resource_data = {'uid': cluster, "rtype": 'Cluster', "name": cluster,
								 "cluster": cluster, "cluster_path": "/root/",
								 "info" : json.dumps(mcm_cluster)}
			else:
				resource_data = {"uid": cluster, "rtype": "Cluster", "name": cluster,
								 "cluster": cluster, "cluster_path": "/root/"}
			edge_data = {'start_uid': 'root', 'end_uid': cluster, 'relation': "Root<-Cluster"}
			requests.post('http://127.0.0.1:5000/resource/{}'.format(cluster), data=resource_data)
			requests.post('http://127.0.0.1:5000/edge/{}/{}'.format('root', cluster), data=edge_data)

			# lazy load namespaces
			namespaces = cmb.cluster_namespaces(cluster)
			for ns in namespaces:
				ns_uid = cluster + "_" + ns.metadata.uid
				ns_name = ns.metadata.name
				created_at = ns.metadata.creation_timestamp
				resource_data = {"uid": ns_uid, "created_at": created_at, "rtype": "Namespace",
							"name": ns_name, "cluster": cluster, "namespace": ns_name,
							"cluster_path": "/root/{}/".format(cluster),
							"info": to_json(ns)}
				edge_data = {'start_uid': cluster, 'end_uid': ns_uid, 'relation': "Cluster<-Namespace"}
				requests.post('http://127.0.0.1:5000/resource/{}'.format(ns_uid), data=resource_data)
				requests.post('http://127.0.0.1:5000/edge/{}/{}'.format(cluster, ns_uid), data=edge_data)

	# lazy load applications
	app_rows = db.session.query(Resource).filter(Resource.rtype=="Application").all()
	has_apps = True
	if len(app_rows) == 0:
		apps = amb.all_applications()
		has_apps = True if len(apps) > 0 else False
		for app in apps:
			md = app["metadata"]
			app_name, app_cluster, app_ns, k8s_uid = md["name"], md["cluster_name"], md["namespace"], md["uid"]
			app_uid = app_cluster + "_" + k8s_uid
			created_at = parse(md["creationTimestamp"])

			data = { "uid": app_uid, "created_at": created_at, "rtype": "Application",
							"name": app_name, "cluster": app_cluster, "namespace": app_ns, "application": app_name,
								"app_path": "/root/", "info": json.dumps(app)}

			requests.post('http://127.0.0.1:5000/resource/{}'.format(app_uid), data=data)
			edge_data = {'start_uid': 'root', 'end_uid': app_uid, 'relation': "Root<-Application"}
			requests.post('http://127.0.0.1:5000/edge/{}/{}'.format('root', app_uid), data=edge_data)

			# lazy load deployables
			dpbs = amb.application_deployables(app_cluster, app_ns, app_name)
			for dpb in dpbs:
				md = dpb["metadata"]
				dpb_name, k8s_uid, cname, ns = md["name"], md["uid"], md["cluster_name"], md["namespace"]
				dpb_uid = cname + "_" + k8s_uid
				created_at = parse(dpb["metadata"]["creationTimestamp"])

				resource_data = {"uid": dpb_uid, "created_at": created_at, "rtype": "Deployable",
								 "name": dpb_name, "cluster": cname, "namespace": ns, "application": app_name,
								 "app_path": "/root/{}/".format(app_uid), "info": json.dumps(dpb)}

				edge_data = {'start_uid': app_uid, 'end_uid': dpb_uid, 'relation': "Application<-Deployable"}
				requests.post('http://127.0.0.1:5000/resource/{}'.format(dpb_uid), data=resource_data)
				requests.post('http://127.0.0.1:5000/edge/{}/{}'.format(app_uid, dpb_uid), data=edge_data)

	# get the starting apps or clusters
	if mode == 'app':
		table = db.session.query(Resource).filter(Resource.rtype == "Application").all()
	elif mode == 'cluster':
		table = db.session.query(Resource).filter(Resource.rtype == "Cluster").all()
	table_dicts = [row_to_dict(table_item) for table_item in table]

	return jsonify(path_names=[], path_rtypes=[], path_uids=[], table_items=table_dicts, index=0, has_children=has_children(table), has_apps=has_apps)

@app.route('/resource/<uid>', methods = ["GET", "POST", "PUT", "DELETE"])
def resource(uid):
	"""
	Get, add, update, or delete a specific resource based on request method. Modifies database.
	:param uid: skipper_uid of the resource
	:return: (str) brief message of action taken
	"""

	if request.method == "GET":
		resource = db.session.query(Resource).filter(Resource.uid == uid).first()
		return jsonify(data=row_to_dict(resource))
	elif request.method == 'DELETE':

		# Removes resource with given uid, all descendants, and associated edges
		to_delete = [ uid ]
		while len(to_delete) > 0:
			# delete the resource in question
			curr_uid = to_delete.pop()
			db.session.query(Resource).filter(Resource.uid == curr_uid).delete()

			# find all children
			outgoing_edges = db.session.query(Edge).filter(Edge.start_uid == curr_uid).all()
			child_uids = [ edge.end_uid for edge in outgoing_edges ]
			to_delete += child_uids

			# removes edges associated with this resource
			db.session.query(Edge).filter(Edge.start_uid == curr_uid or Edge.end_uid == curr_uid).delete()
		db.session.commit()
		return "Resource, descendants, and associated edges deleted"
	else:
		data = request.form.to_dict()

		# make sure all dates are datetimes
		if 'created_at' in data.keys() and not isinstance(data['created_at'], datetime.datetime):
			data['created_at'] = parse(data['created_at'])

		if request.method == 'POST': # add to db
			try:
				r1 = Resource(**data)
				db.session.add(r1)
				db.session.commit()
			except sqlalchemy.exc.IntegrityError: # unique uid already in db
				requests.put('http://127.0.0.1:5000/resource/{}'.format(uid), data=data) # redirect as put request with same data
			return "Resource saved"

		if request.method == 'PUT': # update db
			db.session.query(Resource).filter(Resource.uid == uid).update(data)
			db.session.commit()
			return "Resource updated"

@app.route('/resource/<uid>/<info_type>')
def get_resource_info(uid, info_type):
	"""
	Get info for a specific resource
	:param uid: uid of resource of interest
	:param info_type: "yaml", "events", or "logs"
	:return: json response with resource info
	"""
	resource = db.session.query(Resource).filter(Resource.uid == uid).first()
	uid = uid.split("_")[-1]

	if info_type == 'yaml':
		if resource == None:
			return jsonify(yaml="Yaml not found")
		return jsonify(yaml=info_handler.get_yaml(resource.rtype, resource.name, resource.namespace, resource.cluster))
	elif info_type == 'events':
		if resource == None:
			return jsonify(events="Events not found")
		return jsonify(events=info_handler.get_events(resource.cluster, resource.namespace, uid))
	elif info_type == 'logs':
		if resource == None:
			return jsonify(logs="Logs not found")
		return jsonify(logs=info_handler.get_logs(resource.cluster, resource.namespace, resource.name))

@app.route('/mode/<mode>/<uid>')
def get_table_by_resource(mode, uid):
	"""
	Get the table and relevant info for navigating INTO a resource (aka the table lists resource's children)
	:param mode: 'app' or 'cluster'
	:param uid: skipper uid of resource
	:return: json response including path_names (List[str], list of names of resources in the path),
									path_rtypes (List[str], list of rtypes of resources in the path),
									path_uids (List[str], list of skipper uids of resources in the path),
									table_items (List[Dict], list of dictionaries for resources to be displayed),
									index (int, row to be selected),
									has_children (List[bool]), whether each resource in table has children)
	"""

	resource = db.session.query(Resource).filter_by(uid=uid).first()
	outgoing_edges = db.session.query(Edge).filter_by(start_uid=uid).all()

	if len(outgoing_edges) == 0:
		children = []
		# lazy load depending on current resource type
		if resource.rtype == 'Cluster':
			namespaces = cmb.cluster_namespaces(resource.cluster)
			for ns in namespaces:
				cname = ns.metadata.cluster_name
				ns_uid = cname + "_" + ns.metadata.uid
				ns_name = ns.metadata.name
				created_at = ns.metadata.creation_timestamp
				resource_data = {"uid": ns_uid, "created_at": created_at, "rtype": "Namespace",
								 "name": ns_name, "cluster": cname, "namespace": ns_name,
								 "cluster_path": "/root/{}/".format(cname), "info": to_json(ns)}
				edge_data = {'start_uid': cname, 'end_uid': ns_uid, 'relation': "Cluster<-Namespace"}
				requests.post('http://127.0.0.1:5000/resource/{}'.format(ns_uid), data=resource_data)
				requests.post('http://127.0.0.1:5000/edge/{}/{}'.format(cname, ns_uid), data=edge_data)

		# for all other resources, storing(child, child_type) into the children list
		elif resource.rtype == 'Namespace':
			children.extend([(res, "Deployment") for res in cmb.namespace_deployments(resource.name, resource.cluster)])
			children.extend([(res, "Service") for res in cmb.namespace_services(resource.name, resource.cluster)])
			children.extend([(res, "StatefulSet") for res in cmb.namespace_stateful_sets(resource.name, resource.cluster)])
			children.extend([(res, "DaemonSet") for res in cmb.namespace_daemon_sets(resource.name, resource.cluster)])
		elif resource.rtype == 'Application':
			children.extend([(res, "Deployable") for res in amb.application_deployables(resource.cluster, resource.namespace, resource.name)])
		elif resource.rtype == 'Deployable':
			deployer_dict = amb.deployable_resource(resource.cluster, resource.namespace, resource.name)
			if deployer_dict != {}:
				children.extend([(deployer_dict, deployer_dict["kind"])])
		elif resource.rtype == 'Deployment':
			children.extend([(res, "Pod") for res in cmb.deployment_pods(resource.name, resource.namespace, resource.cluster)])
		elif resource.rtype == 'Service':
			children.extend([(res, "Pod") for res in cmb.service_pods(resource.name, resource.namespace, resource.cluster)])
		elif resource.rtype == 'StatefulSet':
			children.extend([(res, "Pod") for res in cmb.stateful_set_pods(resource.name, resource.namespace, resource.cluster)])
		elif resource.rtype == 'DaemonSet':
			children.extend([(res, "Pod") for res in cmb.daemon_set_pods(resource.name, resource.namespace, resource.cluster)])

		# loop through children and add to db
		for child, rtype in children:
			child_obj = child.to_dict() if not isinstance(child, dict) else child
			# get cluster, falls back to parent resource's cluster (maybe risky)
			cluster = child_obj["metadata"]["cluster_name"] if child_obj["metadata"]["cluster_name"] is not None else resource.cluster
			namespace = child_obj["metadata"]["namespace"]
			skipper_uid = cluster + "_" + child_obj["metadata"]["uid"]
			created_at = child_obj["metadata"]["creation_timestamp"] if not child_obj["metadata"].get("creationTimestamp") else child_obj["metadata"].get("creationTimestamp")
			# build dict
			resource_data = {'uid': skipper_uid, "created_at": created_at, \
							 "rtype": rtype, "name" : child_obj["metadata"]["name"], \
							 "cluster" : cluster, "namespace" : namespace, "info": json.dumps(child_obj, default=str)}

			# fill in sev_measure and sev_reason fields if we are looking at a pod
			if rtype == "Pod":
				sm, sr = eb.pod_state(child)
				resource_data["sev_measure"] = sm
				resource_data["sev_reason"] = sr

			# update paths
			if resource.app_path != None:
				resource_data['app_path'] = resource.app_path + resource.uid + "/"
				app_uid = resource.app_path.split("/")[2]
				resource_data["application"] = requests.get('http://127.0.0.1:5000/resource/{}'.format(app_uid)).json()['data']['name']

			if resource.cluster_path != None:
				resource_data['cluster_path'] = resource.cluster_path + resource.uid + "/"

			requests.post('http://127.0.0.1:5000/resource/{}'.format(skipper_uid), data=resource_data)
			edge_data = {'start_uid': resource.uid, 'end_uid': skipper_uid, 'relation': resource.rtype + "<-" + rtype}
			requests.post('http://127.0.0.1:5000/edge/{}/{}'.format(resource.uid, skipper_uid), data=edge_data)

	table_items = db.session.query(Resource).join(Edge, Resource.uid == Edge.end_uid).filter(Edge.start_uid == uid).all()

	# get path info for frontend
	if mode == 'app':
		full_path = resource.app_path
	elif mode == 'cluster':
		full_path = resource.cluster_path
	full_path += "{}/".format(resource.uid)

	# convert path using uids to breadcrumbs of resource names and types
	path_uids = full_path.split("/")[2:-1]
	path_names = []
	path_rtypes = []
	for res_uid in path_uids:
		path_names.append(db.session.query(Resource.name).filter(Resource.uid == res_uid).first()[0])
		path_rtypes.append(db.session.query(Resource.rtype).filter(Resource.uid == res_uid).first()[0])

	return jsonify(path_names=path_names, path_rtypes=path_rtypes, path_uids=path_uids, table_items=[row_to_dict(t_item) for t_item in table_items], index=0, has_children=has_children(table_items))

@app.route('/edge/<start_uid>/<end_uid>', methods=['POST', 'DELETE'])
def edge(start_uid, end_uid):
	"""
	Add an edge to the database.
	:param start_uid: skipper_uid of the parent resource
	:param end_uid: skipper_uid of the child resource
	:return: (str) brief message of action taken
	"""
	data = request.form
	if request.method == 'POST':
		e1 = Edge(**data)
		db.session.add(e1)
		db.session.commit()
		return "Edge saved"

@app.route('/mode/app/switch/<uid>')
def switch_app_mode(uid):
	"""
	Get the hierarchy info for switching into app mode from a resource
	(Difference between this and get_table_by_resource is that this one includes resource's siblings, not children, in table)
	:param uid: uid of resource to switch modes on
	:return: json response including path_names (List[str], list of names of resources in the path),
									path_rtypes (List[str], list of rtypes of resources in the path),
									path_uids (List[str], list of skipper uids of resources in the path),
									table_items (List[Dict], list of dictionaries for resources to be displayed),
									index (int, row to be selected),
									has_children (List[bool]), whether each resource in table has children)
	"""

	# if we're switching from nothing, go to top of the Application hierarchy
	if uid == "empty":
		table = db.session.query(Resource).filter(Resource.rtype == 'Application').all()
		table_dicts = [row_to_dict(table_item) for table_item in table]
		return jsonify(path_names=[], path_rtypes=[], path_uids=[], table_items=table_dicts, index=0, has_children=has_children(table))

	resource = db.session.query(Resource).filter_by(uid=uid).first()

	full_path = resource.app_path

	if full_path == None: # either doesn't exist in app mode or hasn't been lazy-loaded yet

		# get the resource that would correspond to a deployable (e.g. for pods, it's the pod's parent)
		resource_to_match = None
		if resource.rtype == 'Pod':
			if resource.cluster_path != None:
				parent_uid = resource.cluster_path.split("/")[-2]
				resource_to_match = db.session.query(Resource).filter_by(uid=parent_uid).first()
		elif resource.rtype in ['Deployment', 'Service', 'DaemonSet', 'StatefulSet']:
			resource_to_match = resource

		# search for deployable that has same deployer_name as resource_to_match
		if resource_to_match is not None:
			dpbs = db.session.query(Resource).filter_by(rtype="Deployable").all()
			for dpb in dpbs:
				deployer_name = amb.deployable_resource_name(dpb.cluster, dpb.namespace, dpb.name)
				if deployer_name == resource_to_match.name:
					# if match, update the app paths of the resources
					full_path = dpb.app_path + dpb.uid +  "/"
					requests.put('http://127.0.0.1:5000/resource/{}'.format(resource_to_match.uid),data={'app_path': full_path})
					if resource.rtype == 'Pod':
						full_path += '{}/'.format(parent_uid)
						requests.put('http://127.0.0.1:5000/resource/{}'.format(resource.uid), data={'app_path': full_path})

	if full_path == None or full_path.split("/")[-2] == 'root': # cannot switch from the current resource, go to top of hierarchy
		table = db.session.query(Resource).filter(Resource.rtype == 'Application').all()
		table_dicts = [row_to_dict(table_item) for table_item in table]
		return jsonify(path_names=[], path_rtypes=[], path_uids=[], table_items=table_dicts, index=0, has_children=has_children(table))

	# got the new path, now get the resource's siblings (aka the parent's children) and other data
	parent = full_path.split("/")[-2]

	data = requests.get('http://127.0.0.1:5000/mode/app/{}'.format(parent)).json()
	siblings = data['table_items']

	# get index of resource within siblings
	for i, sib in enumerate(siblings):
		if sib["uid"] == uid:
			index = i
			break

	return jsonify(path_names=data['path_names'], path_rtypes=data['path_rtypes'], path_uids=data['path_uids'], table_items=siblings, index=index, has_children=data['has_children'])

@app.route('/mode/cluster/switch/<uid>')
def switch_cluster_mode(uid):
	"""
	Get the hierarchy info for switching into cluster mode from a resource
	(Difference between this and get_table_by_resource is that this one includes resource's siblings, not children, in table)
	:param uid: uid of resource to switch modes on
	:return: json response including path_names (List[str], list of names of resources in the path),
									path_rtypes (List[str], list of rtypes of resources in the path),
									path_uids (List[str], list of skipper uids of resources in the path),
									table_items (List[Dict], list of dictionaries for resources to be displayed),
									index (int, row to be selected),
									has_children (List[bool]), whether each resource in table has children)
	"""

	# if we're switching from nothing, go to top of the Application hierarchy
	if uid == "empty":
		table = db.session.query(Resource).filter(Resource.rtype == 'Cluster').all()
		table_dicts = [row_to_dict(table_item) for table_item in table]
		return jsonify(path_names=[], path_rtypes=[], path_uids=[], table_items=table_dicts, index=0, has_children=has_children(table))

	resource = db.session.query(Resource).filter_by(uid=uid).first()

	full_path = resource.cluster_path

	if full_path == None: # either doesn't exist in cluster mode or hasn't been lazy-loaded yet

		# get the resource that you would find under a namespace (e.g. for pods, it's the pod's parent)
		resource_to_match = None
		if resource.rtype == 'Pod':
			if resource.app_path != None:
				parent_uid = resource.app_path.split("/")[-2]
				resource_to_match = db.session.query(Resource).filter_by(uid=parent_uid).first()
		elif resource.rtype in ['Deployment', 'Service', 'DaemonSet', 'StatefulSet']:
			resource_to_match = resource

		# check that cluster and namespace are accessible
		if resource_to_match is not None:
			clusters = k8s_config.all_cluster_names()
			if resource_to_match.cluster in clusters:
				namespaces = cmb.cluster_namespace_names(resource_to_match.cluster)
				if resource_to_match.namespace in namespaces:
					# found in cluster mode, so update the app paths of the resources
					ns_uid = resource_to_match.cluster + "_" + resource_to_match.namespace
					full_path = "/root/{}/{}/".format(resource_to_match.cluster, ns_uid)
					requests.put('http://127.0.0.1:5000/resource/{}'.format(resource_to_match.uid), data={'cluster_path': full_path})
					if resource.rtype == 'Pod':
						full_path += '{}/'.format(parent_uid)
						requests.put('http://127.0.0.1:5000/resource/{}'.format(resource.uid), data={'cluster_path': full_path})

	if full_path == None or full_path.split("/")[-2] == 'root': # cannot switch from the current resource, go to top of hierarchy
		table = db.session.query(Resource).filter(Resource.rtype == 'Cluster').all()
		table_dicts = [row_to_dict(table_item) for table_item in table]
		return jsonify(path_names=[], path_rtypes=[], path_uids=[], table_items=table_dicts, index=0, has_children=has_children(table))

	parent = full_path.split("/")[-2]

	data = requests.get('http://127.0.0.1:5000/mode/cluster/{}'.format(parent)).json()
	siblings = data['table_items']

	# get index of resource within siblings
	for i, sib in enumerate(siblings):
		if sib["uid"] == uid:
			index = i
			break

	return jsonify(path_names=data['path_names'], path_rtypes=data['path_rtypes'], path_uids=data['path_uids'], table_items=siblings, index=index, has_children=data['has_children'])

@app.route('/errors')
def get_errors():
	"""
	Get all the unhealthy pods to display in anomaly mode table
	:return: json response of (List[Dict]) of unhealthy pods
	"""
	# each item in table_items list is (skipper_uid, type, name, status, reason)

	anomalies = db.session.query(Resource).filter(Resource.sev_measure==1).all()
	if len(anomalies) > 0:
		return jsonify(table_items=[row_to_dict(a) for a in anomalies])

	# resources = errors_backend.get_resources_with_bad_events()
	table_rows, pods = eb.get_unhealthy_pods()

	# write anomalous pods the db
	for pod in pods:
		pod_cluster = pod.metadata.cluster_name
		pod_ns = pod.metadata.namespace
		skipper_uid = pod_cluster + "_" + pod.metadata.uid
		created_at = pod.metadata.creation_timestamp
		# write pods to db
		resource_data = {'uid': skipper_uid, "created_at": created_at, "rtype": 'Pod',
						 "name": pod.metadata.name, "cluster": pod_cluster, "namespace": pod_ns,
						 "sev_measure": 1, "sev_reason": pod.metadata.sev_reason, "info": to_json(pod)}
		requests.post('http://127.0.0.1:5000/resource/{}'.format(skipper_uid), data=resource_data)

	anomalies = db.session.query(Resource).filter(Resource.sev_measure == 1).all()
	return jsonify(table_items=[row_to_dict(a) for a in anomalies])

@app.route('/search/<query>')
def search(query: str):
	"""
	Searches over all resource names and returns the results as json.
	:param (str) query: the text the user typed into search bar
	:return: json response of (List[Dict]) the results to be displayed in table
	"""
	if query.isspace():
		return jsonify(results=[])

	query_list = query.split(" ")
	results = db.session.query(Resource)

	# for each component of query, filter as needed
	for query_part in query_list:
		if ':' in query_part:
			field = query_part.split(':')[0].lower()
			value = ":".join(query_part.split(':')[1:])
			if field == 'app':
				results = results.filter(Resource.application.ilike(value))
			elif field == 'kind':
				results = results.filter(Resource.rtype.ilike(value))
			elif field == 'cluster':
				results = results.filter(Resource.cluster.ilike(value))
			elif field == 'ns':
				results = results.filter(Resource.namespace.ilike(value))
			else:
				results = results.filter(Resource.name.ilike("%" + query_part + "%"))
		else: # regular fuzzy search
			results = results.filter(Resource.name.ilike("%" + query_part + "%"))

	# sort by sev measure
	results = results.order_by(Resource.sev_measure.desc())
	return jsonify(results=[row_to_dict(r) for r in results])

@app.route('/search/')
def empty_search():
	"""
	:return: json response of empty list, meaning empty search result
	"""
	return jsonify(results=[])

@app.route('/view_resources')
def view_resources():
	"""
	Helper to view all resources in db
	"""
	result = Resource.query.all()
	return jsonify(resources=[row_to_dict(res) for res in result])

@app.route('/view_edges')
def view_edges():
	"""
	Helper to view all edges in db
	"""
	result = Edge.query.all()
	return jsonify(edges=[row_to_dict(res) for res in result])