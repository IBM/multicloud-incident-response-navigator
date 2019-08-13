import k8s_config
from kubernetes import client, config

def get_clients():
	"""
	Get clusters, clients for each cluster, and the active cluster
	:return: ((Dict) {cluster : context}
			  (Dict) {cluster : {client_type : client}}
			  (str) name of active cluster)
	"""
	clusters = k8s_config.update_available_clusters()
	contexts, active_context = config.list_kube_config_contexts() # assuming current active cluster is the hub
	active_cluster = active_context["context"]["cluster"]
	clients = {}
	for cluster in clusters:
		context = clusters[cluster]
		# building all clients for all clusters
		clients[cluster] = {}
		clients[cluster]["apps_client"] = client.AppsV1Api(api_client=config.new_client_from_config(context=context))
		clients[cluster]["batch_client"] = client.BatchV1Api(api_client=config.new_client_from_config(context=context))
		clients[cluster]["core_client"] = client.CoreV1Api(api_client=config.new_client_from_config(context=context))
		clients[cluster]["ext_client"] = client.ExtensionsV1beta1Api(api_client=config.new_client_from_config(context=context))
		clients[cluster]["api_client"] = client.ApiextensionsV1beta1Api(api_client=config.new_client_from_config(context=context))
		clients[cluster]["customs_client"] = client.CustomObjectsApi(api_client=config.new_client_from_config(context=context))

	return clusters, clients, active_cluster