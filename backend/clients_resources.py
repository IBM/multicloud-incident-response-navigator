import k8s_config, json
from kubernetes import client, config
from pprint import pprint
import cluster_mode_backend as cm
import application as app
import clients_resources as cr
import app_mode_backend as amb

def get_resources(clusters, clients, active_cluster):
	jsons = {}
	for cluster in clusters:
	# fetching resources for all clusters
		jsons[cluster] = {}
		jsons[cluster]["Deployment"] = clients[cluster]["ext_client"].list_deployment_for_all_namespaces().items
		jsons[cluster]["Service"] = clients[cluster]["core_client"].list_service_for_all_namespaces().items
		jsons[cluster]["Pod"] = clients[cluster]["core_client"].list_pod_for_all_namespaces().items
		jsons[cluster]["ReplicaSet"] = clients[cluster]["apps_client"].list_replica_set_for_all_namespaces().items
		jsons[cluster]["DaemonSet"] = clients[cluster]["apps_client"].list_daemon_set_for_all_namespaces().items
		jsons[cluster]["StatefulSet"] = clients[cluster]["apps_client"].list_stateful_set_for_all_namespaces().items
		jsons[cluster]["Job"] = clients[cluster]["batch_client"].list_job_for_all_namespaces().items
		jsons[cluster]["Application"] = amb.cluster_applications(cluster)
		jsons[cluster]["Deployable"] = amb.cluster_deployables(cluster)
	return jsons

def get_clients(): # returns clients (6 types) for each cluster, active cluster name, and jsons of resources
	clusters = k8s_config.update_available_clusters()
	contexts, active_context = config.list_kube_config_contexts() # assuming current active cluster is the hub
	active_cluster = active_context["context"]["cluster"]
	api_client = config.new_client_from_config(context=active_context['name'])
	clients = {}
	for cluster in clusters:
		context = clusters[cluster]
	# building all clients all clusters
		clients[cluster] = {}
		clients[cluster]["apps_client"] = client.AppsV1Api(api_client=config.new_client_from_config(context=context))
		clients[cluster]["batch_client"] = client.BatchV1Api(api_client=config.new_client_from_config(context=context))
		clients[cluster]["core_client"] = client.CoreV1Api(api_client=config.new_client_from_config(context=context))
		clients[cluster]["ext_client"] = client.ExtensionsV1beta1Api(api_client=config.new_client_from_config(context=context))
		clients[cluster]["api_client"] = client.ApiextensionsV1beta1Api(api_client=config.new_client_from_config(context=context))
		clients[cluster]["customs_client"] = client.CustomObjectsApi(api_client=config.new_client_from_config(context=context))

	return clusters, clients, active_cluster

def order_resources(jsons):
	uids = {}
	initial_path = "/root/"
	for cluster in jsons:
		# add cluster as resource
		uids[cluster] = {'uid': cluster, "rtype": 'Cluster', "name": cluster, "cluster": cluster}
		cluster_path = initial_path + cluster + "/"
		namespaces = cm.cluster_namespace_names(cluster)
		# add namespace as resource
		for ns in namespaces:
			skipper_uid = cluster + "_" + ns
			uids[skipper_uid] = {'uid': skipper_uid, "rtype": 'Namespace', "name": ns, \
			"cluster": cluster, "namespace": ns}
		# add all other resources
		for rtype in jsons[cluster]:
			if rtype == 'ReplicaSet':
				continue
			for resource in jsons[cluster][rtype]:
				if rtype not in ["Deployable", "Application"]:
					resource = resource.to_dict()
				# print(resource)
				# if rtype == "Application":
				# 	uids[skipper_uid]["deployables"] = resource["metadata"]["annotations"]["apps.ibm.com/deployables"]
				uid = resource["metadata"]['uid']
				skipper_uid = cluster+'_'+uid
				name = resource["metadata"]["name"]
				namespace = resource["metadata"]["namespace"]
				created_at = resource["metadata"].get("creationTimestamp")
				if not created_at:
					created_at = resource["metadata"]["creation_timestamp"]
				uids[skipper_uid] = { 'uid': skipper_uid, "created_at": created_at, \
									  "rtype": rtype, "name" : name, \
									  "cluster" : cluster, "namespace" : namespace, \
									  }

				# other info to include:
				# application
				# app_path
				# cluster_path
				# sev_measure
				# info
	print(len(uids))
	return uids

def get_resource(cluster, uid, jsons):
	skipper_uid = cluster+','+uid
	return jsons[skipper_uid]

def order_edges_and_paths(jsons):
	edges = set()
	cluster_paths = {}
	app_paths = {}
	k8s_config.update_available_clusters()
	clusters, k8clients , active_cluster = cr.get_clients()
	app_dicts = { "items": amb.all_applications() }

	# pass in cluster paths dict to app, build it as resources are being fetched, then return
	for app_dict in app_dicts["items"]:
		single_app = app.Application(k8clients, jsons, app_dict, active_cluster)
		single_app.load_hierarchy()
		edges = edges.union(single_app.edges)
		app_paths = {**app_paths, **single_app.paths}

	initial_path = "/root/"
	for cluster in clusters:
		edges.add(('root', cluster, "Root<-Cluster"))
		path_to_cluster = initial_path + cluster + "/"
		cluster_paths[cluster] = initial_path
		namespaces = cm.cluster_namespace_names(cluster)
		for ns in namespaces:
			ns_uid = cluster+'_'+ns
			path_to_ns = path_to_cluster + ns_uid + "/"
			cluster_paths[ns_uid] = path_to_cluster
			edges.add((cluster, ns_uid, "Cluster<-Namespace"))
			deploys = cm.namespace_deployment_names(ns, cluster)
			for deploy in deploys:
				deploy_uid =  cluster+'_'+deploy[1]
				path_to_deploy = path_to_ns + deploy_uid + "/"
				cluster_paths[deploy_uid] = path_to_ns
				edges.add((ns_uid, deploy_uid, "Namespace<-Deployment"))
				pods = cm.deployment_pod_names(deploy[0], ns, cluster)
				for pod in pods:
					pod_uid = cluster+'_'+pod[1]
					cluster_paths[pod_uid] = path_to_deploy
					edges.add(( deploy_uid, pod_uid, "Deployment<-Pod"))

			dsets = cm.namespace_daemon_set_names(ns, cluster)
			for dset in dsets:
				dset_uid = cluster + "_" + dset[1]
				path_to_dset = path_to_ns + dset_uid + "/"
				cluster_paths[dset_uid] = path_to_ns
				edges.add((ns_uid, dset_uid, "Namespace<-DaemonSet"))
				pods = cm.daemon_set_pod_names(dset[0], ns, cluster)
				for pod in pods:
					pod_uid = cluster + "_" + pod[1]
					cluster_paths[pod_uid] = path_to_dset
					edges.add((dset_uid, pod_uid, "DaemonSet<-Pod"))

			ssets = cm.namespace_stateful_set_names(ns, cluster)
			for sset in ssets:
				sset_uid = cluster + "_" + sset[1]
				path_to_sset = path_to_ns + sset_uid + "/"
				cluster_paths[sset_uid] = path_to_ns
				edges.add((ns_uid, sset_uid, "Namespace<-StatefulSet"))
				pods = cm.stateful_set_pod_names(sset[0], ns, cluster)
				for pod in pods:
					pod_uid = cluster + "_" + pod[1]
					cluster_paths[pod_uid] = path_to_sset
					edges.add((sset_uid, pod_uid, "StatefulSet<-Pod"))

			svcs = cm.namespace_service_names(ns, cluster)
			for svc in svcs:
				svc_uid = cluster + "_" + svc[1]
				cluster_paths[svc_uid] = path_to_ns
				edges.add((ns_uid, svc_uid, "Namespace<-Service"))
				pods = cm.service_pod_names(svc[0], ns, cluster)
				for pod in pods:
					pod_uid = cluster + "_" + pod[1]
					edges.add((svc_uid, pod_uid, "Service<-Pod"))

			### end of cluster mode edges
	return edges, cluster_paths, app_paths


if __name__ == "__main__":
	clusters, clients, active_cluster= get_clients()
	jsons = get_resources(clusters, clients, active_cluster)
	# order_edges_and_paths(jsons)
	order_resources(jsons)
	# print(get_resource('iks-extremeblue', 'b4d69756-7bf0-11e9-9468-4687af9546f9', order_resources(jsons)))
