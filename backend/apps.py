import io, json
import application as app
from kubernetes import client, config, watch
import clients_resources as cr
import app_mode_backend as amb

def get_application_objects(app_dicts, active_cluster, k8clients, jsons):
	apps, uids, graph = {}, {}, {}
	for app_dict in app_dicts["items"]:
		name = app_dict["metadata"]["name"]
		singleApp = app.Application(k8clients, jsons, app_dict)
		singleApp.getHierarchy()
		graph = singleApp.graph
		apps["App_name: "+name] = singleApp.generate_dicts()

	for app_dict in app_dicts["items"]:
		name = app_dict["metadata"]["name"]

def get_app_uids(app_dicts, active_cluster):
	return [ active_cluster+","+app['metadata']['uid'] for app in app_dicts['items']]

if __name__ == "__main__":
	app_dicts, active_cluster, k8clients = get_apps()
	print(get_app_uids(app_dicts, active_cluster))
