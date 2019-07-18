from app import app, db
from app.models import Resource, Edge
from flask import request, jsonify, redirect, url_for
import sys
import requests
import datetime
import inspect
from dateutil.parser import parse
import sqlalchemy

sys.path.insert(0,'../../backend')
# sys.path.insert(0,'../crawler')
import apps, clients_resources, k8s_config, cluster_mode_backend as cmb, app_mode_backend as amb, errors_backend

def row_to_dict(row):
	d = {}
	for column in row.__table__.columns:
		d[column.name] = str(getattr(row, column.name))
	return d

@app.route('/')
@app.route('/index')
def index():
	return "Hello, World!"


@app.route('/start/<mode>')
def start(mode):
	"""
	Retrieves and stores clusters+namespaces, and applications+deployables, and returns starting table
	:param mode: 'app' or 'cluster'
	:return: json response including path (List[str], list of names of resources in the path),
									rtypes (List[str], list of rtypes of resources in the path),
									index (int, row to be selected),
									table (List[Dict], list of dictionaries for resources to be displayed),
									current_resource (Resource)
	"""

	db.drop_all()
	db.create_all()

	k8s_config.update_available_clusters()

	# lazy load clusters
	clusters = k8s_config.all_cluster_names()
	for cluster in clusters:
		resource_data = {'uid': cluster, "rtype": 'Cluster', "name": cluster, "cluster": cluster,
						 "cluster_path": "/root/"}
		requests.post('http://127.0.0.1:5000/resource/{}'.format(cluster), data=resource_data)
		edge_data = {'start_uid': 'root', 'end_uid': cluster, 'relation': "Root<-Cluster"}
		requests.post('http://127.0.0.1:5000/edge/{}/{}'.format('root', cluster), data=edge_data)

		# lazy load namespaces
		namespaces = cmb.cluster_namespaces(cluster)
		for ns in namespaces:
			ns = ns.to_dict()
			skipper_uid = cluster + "_" + ns["metadata"]["name"]
			resource_data = {'uid': skipper_uid, "rtype": 'Namespace', "name": ns["metadata"]["name"],
							 "cluster": cluster, "namespace": ns["metadata"]["name"],
							 "cluster_path": "/root/{}/".format(cluster)}
			requests.post('http://127.0.0.1:5000/resource/{}'.format(skipper_uid), data=resource_data)
			edge_data = {'start_uid': cluster, 'end_uid': skipper_uid, 'relation': "Cluster<-Namespace"}
			requests.post('http://127.0.0.1:5000/edge/{}/{}'.format(cluster, skipper_uid), data=edge_data)

	# lazy load applications
	apps = amb.all_applications()
	for app in apps:
		app_cluster = app["metadata"]["cluster_name"]
		app_name = app["metadata"]["name"]
		app_uid = app_cluster + "_" + app["metadata"]["uid"]
		app_ns = app["metadata"]["namespace"]
		data = {'uid': app_uid, "created_at": app["metadata"].get("creationTimestamp"), "rtype": "Application",
				"name": app_name, "cluster": app_cluster, "namespace": app_ns, "app_path": "/root/"}
		requests.post('http://127.0.0.1:5000/resource/{}'.format(app_uid), data=data)
		edge_data = {'start_uid': 'root', 'end_uid': app_uid, 'relation': "Root<-Application"}
		requests.post('http://127.0.0.1:5000/edge/{}/{}'.format('root', app_uid), data=edge_data)

		# lazy load deployables
		dpbs = amb.application_deployables(app_cluster, app_ns, app_name)
		for dpb in dpbs:
			cluster = dpb["metadata"]["cluster_name"]
			namespace = dpb["metadata"]["namespace"]
			dpb_uid = cluster + "_" + dpb["metadata"]["uid"]
			created_at = dpb["metadata"].get("creationTimestamp")
			if not created_at:
				created_at = dpb["metadata"]["creation_timestamp"]
			resource_data = {'uid': dpb_uid, "created_at": created_at, "rtype": "Deployable",
							 "name": dpb["metadata"]["name"], "cluster": cluster, "namespace": namespace,
							 "app_path": "/root/{}/".format(app_uid)}
			requests.post('http://127.0.0.1:5000/resource/{}'.format(dpb_uid), data=resource_data)
			edge_data = {'start_uid': app_uid, 'end_uid': dpb_uid, 'relation': "Application<-Deployable"}
			requests.post('http://127.0.0.1:5000/edge/{}/{}'.format(app_uid, dpb_uid), data=edge_data)

	# # load all
	#
	# # get all resources (app and cluster)
	# clusters, clients, active_clusters = clients_resources.get_clients()
	# big_json = clients_resources.get_resources(clusters, clients, active_clusters)
	# resources = clients_resources.order_resources(big_json)
	# for res in resources.keys():
	# 	requests.post('http://127.0.0.1:5000/resource/{}', data=resources[res])
	#
	# # get all edges (app and cluster) and update resource paths (breadcrumbs built while getting edges)
	# edges, cluster_paths, app_paths = clients_resources.order_edges_and_paths(big_json)
	# for edge in edges:
	# 	edge_dict = {'start_uid': edge[0], 'end_uid': edge[1], 'relation': edge[2]}
	# 	requests.post('http://127.0.0.1:5000/edge/{}/{}'.format(edge[0],edge[1]), data=edge_dict)
	# for res in cluster_paths.keys():
	# 	cpath_dict = {'cluster_path': cluster_paths[res]}
	# 	requests.put('http://127.0.0.1:5000/resource/{}'.format(res), data=cpath_dict)
	# for res in app_paths.keys():
	# 	apath_dict = {'app_path': app_paths[res]}
	# 	requests.put('http://127.0.0.1:5000/resource/{}'.format(res), data=apath_dict)

	# get the starting apps or clusters
	if mode == 'app':
		table = db.session.query(Resource).filter(Resource.rtype == "Application").all()
	elif mode == 'cluster':
		table = db.session.query(Resource).filter(Resource.rtype == "Cluster").all()
	table_dicts = [row_to_dict(table_item) for table_item in table]

	return jsonify(path_names=[], path_rtypes=[], path_uids=[], table_items=table_dicts, index=0)


@app.route('/resource/<uid>', methods=['POST', 'PUT', 'GET', 'DELETE'])
def resource(uid):
	"""
	All things related to a specific resource, based on request method
	:param uid: skipper_uid of the resource
	:return:
	"""
	if request.method == 'GET': # return the row for the resource as a dict
		resource = db.session.query(Resource).filter(Resource.uid == uid).first()
		return jsonify(data=row_to_dict(resource))
	elif request.method == 'DELETE':
		db.session.query(Resource).filter(Resource.uid == uid).delete()
		db.session.query(Edge).filter(Edge.start_uid == uid or Edge.end_uid == uid).delete()
		db.session.commit()
		return "Resource and respective edges deleted"
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

			return "Resource saved" # TODO what is the proper thing to return?
		if request.method == 'PUT': # update db
			db.session.query(Resource).filter(Resource.uid == uid).update(data)
			db.session.commit()
			return "Resource updated"

# # TODO unfinished
# @app.route('/resource/<uid>/<info_type>')
# def get_resource_info(uid, info_type):
# 	resource = db.session.query(Resource).filter(Resource.uid == uid).first()
# 	info_handler = resource_files.resource_files()
# 	if info_type == 'yaml':
# 		info = info_handler.getYaml(resource.type, resource.name, resource.cluster)
# 	elif info_type == 'describe':
# 		### TODO this is not going to work for all resources
# 		info = info_handler.getDescribe(resource.type, resource.name, resource.namespace, resource.cluster)
# 	elif info_type == 'events':
# 		info = info_handler.getEvents()
# 	elif info_type == 'logs':
# 		info = info_handler.getLogs()


@app.route('/edge/<start_uid>/<end_uid>', methods=['POST', 'PUT'])
def edge(start_uid, end_uid):
	"""
	All things related to a specific edge, based on request method
	:param start_uid: uid of parent
	:param end_uid: uid of child
	:return:
	"""
	data = request.form
	if request.method == 'POST':
		e1 = Edge(**data)
		db.session.add(e1)
		db.session.commit()
		return "Edge saved"
	elif request.method == 'PUT':
		db.session.query(Resource).filter(Edge.start_uid == start_uid and Edge.end_uid == end_uid).update(data)
		return "Edge updated"

@app.route('/mode/app/switch/<uid>')
def switch_app_mode(uid):
	"""
	Get the hierarchy info for switching into app mode from a resource
	(Difference between this and get_table_by_resource is that this one takes you to siblings, not children)
	:param uid: uid of resource to switch modes on
	:return: json response including path (List[str], list of names of resources in the path),
									rtypes (List[str], list of rtypes of resources in the path),
									index (int, row to be selected),
									table (List[Dict], list of dictionaries for resources to be displayed),
									current_resource (Resource)
	"""
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
		return jsonify(path_names=[], path_rtypes=[], path_uids=[], table_items=table_dicts, index=0)

	# got the new path, now get the resource's siblings (aka the parent's children) and other data
	parent = full_path.split("/")[-2]

	data = requests.get('http://127.0.0.1:5000/mode/app/{}'.format(parent)).json()
	siblings = data['table_items']

	# get index of resource within siblings
	for i, sib in enumerate(siblings):
		if sib["uid"] == uid:
			index = i
			break

	return jsonify(path_names=data['path_names'], path_rtypes=data['path_rtypes'], path_uids=data['path_uids'], table_items=siblings, index=index)

@app.route('/mode/cluster/switch/<uid>')
def switch_cluster_mode(uid):
	"""
	Get the hierarchy info for switching into cluster mode from a resource
	(Difference between this and get_table_by_resource is that this one takes you to siblings, not children)
	:param uid: uid of resource to switch modes on
	:return: json response including path (List[str], list of names of resources in the path),
									rtypes (List[str], list of rtypes of resources in the path),
									index (int, row to be selected),
									table (List[Dict], list of dictionaries for resources to be displayed),
									current_resource (Resource)
	"""

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
		return jsonify(path_names=[], path_rtypes=[], path_uids=[], table_items=table_dicts, index=0)

	parent = full_path.split("/")[-2]

	data = requests.get('http://127.0.0.1:5000/mode/cluster/{}'.format(parent)).json()
	siblings = data['table_items']

	# get index of resource within siblings
	for i, sib in enumerate(siblings):
		if sib["uid"] == uid:
			index = i
			break

	return jsonify(path_names=data['path_names'], path_rtypes=data['path_rtypes'], path_uids=data['path_uids'], table_items=siblings, index=index)

@app.route('/mode/<mode>/<uid>')
def get_table_by_resource(mode, uid):
	"""
	Get the table and relevant info for navigating INTO a resource (aka the table lists children)
    :param mode: 'app' or 'cluster'
    :param uid: skipper uid of resource
    :return: json response including path (List[str], list of names of resources in the path),
    								rtypes (List[str], list of rtypes of resources in the path),
									index (int, row to be selected),
									table (List[Dict], list of dictionaries for resources to be displayed),
									current_resource (Resource)
    """

	# TODO needs to be broken up into smaller functions

	children = []

	resource = db.session.query(Resource).filter_by(uid=uid).first()

	# lazy load depending on current resource type
	if resource.rtype == 'Cluster':
		namespaces = cmb.cluster_namespaces(resource.cluster)
		for ns in namespaces:
			ns = ns.to_dict()
			skipper_uid = resource.cluster + "_" + ns["metadata"]["name"]
			resource_data = {'uid': skipper_uid, "rtype": 'Namespace', "name": ns["metadata"]["name"], "cluster": resource.cluster, "namespace": ns["metadata"]["name"], "cluster_path": resource.cluster_path + resource.uid + "/"}
			requests.post('http://127.0.0.1:5000/resource/{}'.format(skipper_uid), data=resource_data)
			edge_data = {'start_uid': resource.uid, 'end_uid': skipper_uid, 'relation': "Cluster<-Namespace"}
			requests.post('http://127.0.0.1:5000/edge/{}/{}'.format(resource.uid, skipper_uid), data=edge_data)
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
	for child_obj, rtype in children:

		if not isinstance(child_obj, dict):
			child_obj = child_obj.to_dict()

		# get cluster, falls back to parent resource's cluster (maybe risky)
		cluster = child_obj["metadata"]["cluster_name"] if child_obj["metadata"]["cluster_name"] is not None else resource.cluster
		namespace = child_obj["metadata"]["namespace"]
		skipper_uid = cluster + "_" + child_obj["metadata"]["uid"]
		created_at = child_obj["metadata"].get("creationTimestamp")
		if not created_at:
			created_at = child_obj["metadata"]["creation_timestamp"]

		# build dict
		resource_data = {'uid': skipper_uid, "created_at": created_at, "rtype": rtype, "name" : child_obj["metadata"]["name"], "cluster" : cluster, "namespace" : namespace}

		# update paths
		if resource.app_path != None:
			resource_data['app_path'] = resource.app_path + resource.uid + "/"
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
	print("HIIII", resource.name)
	full_path += "{}/".format(resource.uid)

	# convert path using uids to breadcrumbs of resource names and types
	path_uids = full_path.split("/")[2:-1]
	path_names = []
	path_rtypes = []
	for res_uid in path_uids:
		path_names.append(db.session.query(Resource.name).filter(Resource.uid == res_uid).first()[0])
		path_rtypes.append(db.session.query(Resource.rtype).filter(Resource.uid == res_uid).first()[0])

	return jsonify(path_names=path_names, path_rtypes=path_rtypes, path_uids=path_uids, table_items=[row_to_dict(t_item) for t_item in table_items], index=0)

@app.route('/errors')
def get_errors():
	# each item in table_items list is (skipper_uid, type, name, status, reason)

	pods = errors_backend.get_unhealthy_pods()
	resources = errors_backend.get_resources_with_bad_events()
	all = pods + resources
	return jsonify(table_items=all)

# @app.route('/viewqueue')
# def view_queue():
# 	queue = crawler.update_queue()
# 	return jsonify(queue=queue)

@app.route('/view_resources')
def view_resources():
	result = Resource.query.all()
	return jsonify(resources=[row_to_dict(res) for res in result])

@app.route('/view_edges')
def view_edges():
	result = Edge.query.all()
	return jsonify(edges=[row_to_dict(res) for res in result])

# @app.route('/redirectme')
# def redirectme():
# 	result = redirect(url_for('view_db'))
# 	return result