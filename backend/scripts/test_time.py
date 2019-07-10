import cluster_mode_backend as cm
import apps, time
import clients_resources as cr

if __name__ == "__main__":
	start_time = time.time()
	app_dicts, active_cluster, k8clients, jsons = apps.get_apps()
	apps.get_application_objects(app_dicts, active_cluster, k8clients, jsons)
	elapsed_time = time.time() - start_time
	print("app mode", elapsed_time)

	start_time = time.time()
	clusters, clients, active_cluster= cr.get_clients()
	jsons  = cr.get_resources(clusters, clients, active_cluster)
	elapsed_time = time.time() - start_time
	print("fetching resources from api", elapsed_time)
