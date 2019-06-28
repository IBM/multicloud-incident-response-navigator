import k8s_api
import k8s_config

# example script that print all namespaces for each cluster
# the user has access to

k8s_config.update_available_clusters()
clusters = k8s_config.all_cluster_names()

for cluster in clusters:
	api_client = k8s_api.api_client(cluster_name = cluster, api_class = "CoreV1Api")
	namespaces = api_client.list_namespace()
	ns_names = [ ns.metadata.name for ns in namespaces.items ]
	print("The cluster", cluster, "has the following namespaces:", ns_names)