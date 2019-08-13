import k8s_config
import app_mode_backend as amb

# Example script that prints out all Clusters, their Namespaces,
# and the Deployments under each namespace.

k8s_config.update_available_clusters()

names = lambda ls: [ l["metadata"]["name"] for l in ls ]

# find all Applications defined across your clusters
apps = amb.all_applications()

for app in apps:
	app_name = app["metadata"]["name"]
	app_ns = app["metadata"]["namespace"]
	app_cluster = app["metadata"]["cluster_name"]
	print("Application:", app_name)

	# find all Deployables that belong to this Application
	deployables = amb.application_deployables(cluster_name=app_cluster, namespace=app_ns, app_name=app_name)
	for dpb in deployables:
		dpb_name = dpb["metadata"]["name"]
		dpb_ns = dpb["metadata"]["namespace"]
		dpb_cluster = dpb["metadata"]["cluster_name"]
		print("\tDeployable:", dpb_name)

		# find the resource that belongs to this Deployable
		resource = amb.deployable_resource(cluster_name=dpb_cluster, namespace=dpb_ns, deployable_name=dpb_name)
		try:
			resource_name = resource["metadata"]["name"]
		except:
			resource_name = "Deployer name not found"
		print("\t\tResource:", resource_name)