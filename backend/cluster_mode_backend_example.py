import cluster_mode_backend as cmb
import k8s_config

# check what clusters we can access
k8s_config.update_available_clusters()
clusters = k8s_config.all_cluster_names()

# list deployment names for each namespace in each cluster
for cluster in clusters:
	print("Cluster", cluster + ":")
	namespaces = cmb.cluster_namespaces(cluster)
	for ns in namespaces:
		print("\tNamespace", ns.metadata.name + ":")
		deploys = cmb.namespace_deployments(ns.metadata.name, cluster)
		for deploy in deploys:
			print("\t\tDeployment:", deploy.metadata.name)

# getting cluster objects from mcm
print(cmb.mcm_clusters(clusters))
