import cluster_mode_backend as cmb
import k8s_config

# check what clusters we can access
k8s_config.update_available_clusters()

# list deployment names for each namespace in each cluster
clusters = k8s_config.all_cluster_names()
for cluster in clusters:
	print("Cluster", cluster + ":")
	namespaces = cmb.cluster_namespace_names(cluster)
	for ns in namespaces:
		print("\tNamespace", ns + ":")
		deploys = cmb.namespace_deployment_names(ns, cluster)
		for deploy in deploys:
			print("\t\tDeployment:", deploy)