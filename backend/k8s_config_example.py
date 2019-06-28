import k8s_config

# Example script that prints out the name and corresponding context for 
# all clusters listed in the user's kube-config.

k8s_config.update_available_clusters()
clusters = k8s_config.all_cluster_names()

for cluster in clusters:
	context = k8s_config.context_for_cluster(cluster)
	print("The cluster", cluster, "is pointed to by context", context)