from app import app, db
from app.models import Resource, Edge
from flask import request, jsonify, redirect, url_for
import sys
import requests
import datetime
from dateutil.parser import parse

sys.path.insert(0,'../../backend')
# sys.path.insert(0,'../crawler')
import apps, clients_resources

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
	Retrieves and stores all resources and edges, for both app and cluster mode, and returns starting table
	:param mode: 'app' or 'cluster'
	:return: json response including path (List[str], list of names of resources in the path),
									rtypes (List[str], list of rtypes of resources in the path),
									index (int, row to be selected),
									table (List[Dict], list of dictionaries for resources to be displayed),
									current_resource (Resource)
	"""
	db.drop_all()
	db.create_all()

	# get all resources (app and cluster)
	clusters, clients, active_clusters = clients_resources.get_clients()
	big_json = clients_resources.get_resources(clusters, clients, active_clusters)
	resources = clients_resources.order_resources(big_json)
	for res in resources.keys():
		requests.post('http://127.0.0.1:5000/resource/{}', data=resources[res])

	# get all edges (app and cluster) and update resource paths (breadcrumbs built while getting edges)
	edges, cluster_paths, app_paths = clients_resources.order_edges_and_paths(big_json)
	for edge in edges:
		edge_dict = {'start_uid': edge[0], 'end_uid': edge[1], 'relation': edge[2]}
		requests.post('http://127.0.0.1:5000/edge/{}/{}'.format(edge[0],edge[1]), data=edge_dict)
	for res in cluster_paths.keys():
		cpath_dict = {'cluster_path': cluster_paths[res]}
		requests.put('http://127.0.0.1:5000/resource/{}'.format(res), data=cpath_dict)
	for res in app_paths.keys():
		apath_dict = {'app_path': app_paths[res]}
		requests.put('http://127.0.0.1:5000/resource/{}'.format(res), data=apath_dict)

	# get the starting apps or clusters
	if mode == 'app':
		table = db.session.query(Resource).filter(Resource.rtype == "Application").all()
	elif mode == 'cluster':
		table = db.session.query(Resource).filter(Resource.rtype == "Cluster").all()
	table_dicts = [row_to_dict(table_item) for table_item in table]

	return jsonify(path=[], rtypes= [], table_items=table_dicts, index=0)


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
			r1 = Resource(**data)
			db.session.add(r1)
			db.session.commit()
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

@app.route('/mode/<new_mode>/switch/<uid>') # TODO end with slash or no slash?
def switch_mode(new_mode, uid):
	"""
    Get the hierarchy info for switching into a different mode from a resource
    (Difference between this and get_table_by_resource is that this one takes you to siblings, not children)
    :param new_mode: new mode to switch to, one of ['cluster', 'app']
    :param uid: uid of resource to switch modes on
    :return: json response including path (List[str], list of names of resources in the path),
    								rtypes (List[str], list of rtypes of resources in the path),
									index (int, row to be selected),
									table (List[Dict], list of dictionaries for resources to be displayed),
									current_resource (Resource)
	"""

	if new_mode == 'app':
		full_path = db.session.query(Resource.app_path).filter_by(uid=uid).first()[0]
	elif new_mode == 'cluster':
		full_path = db.session.query(Resource.cluster_path).filter_by(uid=uid).first()[0]
	print(full_path)
	if full_path == None: # TODO cannot switch to new_mode from the current resource, currently leaves frontend to deal with this
		return jsonify(path=[], rtypes=[], table_items=[], index=0)

	parent = full_path.split("/")[-2]

	if parent == 'root':
		if new_mode == 'app':
			siblings = db.session.query(Resource).join(Edge, Resource.uid == Edge.end_uid).filter(Edge.start_uid == parent).filter(Edge.relation == 'Root<-Application').all()
		elif new_mode == 'cluster':
			siblings = db.session.query(Resource).join(Edge, Resource.uid == Edge.end_uid).filter(Edge.start_uid == parent).filter(Edge.relation == 'Root<-Cluster').all()
	else:
		siblings = db.session.query(Resource).join(Edge, Resource.uid == Edge.end_uid).filter(Edge.start_uid == parent).all()

	# get index of resource within siblings
	index = 0
	for i, sib in enumerate(siblings):
		if sib.uid == uid:
			index = i
			break

	# convert path using uids to breadcrumbs of resource names and types
	path = []
	rtypes = []
	for res_uid in full_path.split("/")[2:-1]:
		path.append(db.session.query(Resource.name).filter(Resource.uid == res_uid).first()[0])
		rtypes.append(db.session.query(Resource.rtype).filter(Resource.uid == res_uid).first()[0])

	return jsonify(path=path, rtypes=rtypes, table_items=[row_to_dict(sib) for sib in siblings], index=index)

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

	if mode == 'app':
		full_path = db.session.query(Resource.app_path).filter_by(uid=uid).first()[0]
	elif mode == 'cluster':
		full_path = db.session.query(Resource.cluster_path).filter_by(uid=uid).first()[0]
	print(full_path)
	full_path += "{}/".format(uid)

	# convert path using uids to breadcrumbs of resource names and types
	path = []
	rtypes = []
	for res_uid in full_path.split("/")[2:-1]:
		path.append(db.session.query(Resource.name).filter(Resource.uid == res_uid).first()[0])
		rtypes.append(db.session.query(Resource.rtype).filter(Resource.uid == res_uid).first()[0])

	children = db.session.query(Resource).join(Edge, Resource.uid == Edge.end_uid).filter(Edge.start_uid == uid).all()

	return jsonify(path=path, rtypes=rtypes, table_items=[row_to_dict(child) for child in children], index=0)

# @app.route('/errors')
# def get_errors():
# 	pods = errors_backend.get_unhealthy_pods()
# 	resources = errors_backend.get_resources_with_bad_events()
# 	all = pods + resources
# 	return jsonify(resources=all)

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
