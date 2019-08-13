import yaml, datetime, pytz, kubernetes
import app_mode_backend as amb
import clients_resources as cr

class ResourceFiles:
	def __init__(self):
		self.clusters, self.clients, self.active_cluster= cr.get_clients()

		# preload app and deployable information (for yaml)
		apps = amb.all_applications()
		self.apps = { app["metadata"]["name"] : app for app in apps}
		self.dpbs = {}
		for app in self.apps.values():
			app_name = app["metadata"]["name"]
			app_ns = app["metadata"]["namespace"]
			app_cluster = app["metadata"]["cluster_name"]
			deployables = amb.application_deployables(cluster_name=app_cluster, namespace=app_ns, app_name=app_name)
			for dpb in deployables:
				dpb_name = dpb["metadata"]["name"]
				self.dpbs[dpb_name] = dpb

	def get_yaml(self, type, name, namespace, cluster):
		"""
		Helper to get resource yaml
		:param (str) type: resource type
		:param (str) name: resource name
		:param (str) namespace
		:param (str) cluster
		:return: (str) yaml, or "Yaml not found" if we don't cover that resource type
		"""
		if type in ["DaemonSet", "Deployment", "ReplicaSet", "StatefulSet"]:
			client = self.clients[cluster]["apps_client"]
		elif type in ["Pod", "Service", "Event", "Namespace"]:
			client = self.clients[cluster]["core_client"]
		elif type == "Application":
			doc = self.apps[name]
		elif type == "Deployable":
			doc = self.dpbs[name]
		else:
			return "Yaml not found"

		if type == "DaemonSet":
			doc = client.read_namespaced_daemon_set(name, namespace).to_dict()
		elif type == "Deployment":
			doc = client.read_namespaced_deployment(name, namespace).to_dict()
		elif type == "ReplicaSet":
			doc =  client.read_namespaced_replica_set(name, namespace).to_dict()
		elif type == "StatefulSet":
			doc =  client.read_namespaced_stateful_set(name, namespace).to_dict()
		elif type == "Service":
			doc = client.read_namespaced_service(name, namespace).to_dict()
		elif type == "Pod":
			doc =  client.read_namespaced_pod(name, namespace).to_dict()
		elif type == "Namespace":
			doc = client.read_namespace(name).to_dict()

		return yaml.dump(doc, sort_keys=False)

	def parse_time(self, time):
		if time.days == 0:
			hours = time.seconds // 3600
			if hours == 0:
				minutes = time.seconds // 60
				if minutes == 0:
					return str(time.seconds)
				return str(minutes)+"m"
			return str(hours)+"h"
		return str(time.days)+"d"

	def get_events(self, cluster, namespace, uid):
		"""
		Helper to get events for a resource
		:param (str) cluster
		:param (str) namespace
		:param (str) uid: k8s uid for the resource of interest
		:return: (List[
					List[
						(str) event type, "Normal" or "Warning",
						(str) event reason,
						(str) event age,
						(str) event source,
						(str) event message]
		"""
		events = self.clients[cluster]["core_client"].list_namespaced_event(namespace).items
		events_list = [ e  for e in events if e.involved_object.uid == uid ]
		table = []
		for e in events_list:
			e = e.to_dict()
			source = e["source"] if e.get("source") else ""
			# type, reason, created, count, source component, source host, message
			last_timestamp = e["last_timestamp"] if e.get("last_timestamp") else ""
			now = datetime.datetime.now(pytz.utc)
			current_age = self.parse_time(now - last_timestamp)
			if e.get("creation_timestamp"):
				creation_timestamp = e["metadata"]["creation_timestamp"]
				total_age = self.parse_time(now - creation_timestamp)
				count = str(e["count"])
				age = current_age+ " (x"+count+" over "+total_age+")"
			else:
				age = current_age

			source_output = ""
			if source.get("component"):
				source_output = source["component"]

			if source.get("host"):
				source_output += ", " + source["host"]

			table.append([e["type"], e["reason"], age, source_output, e["message"]])
		return table

	def get_logs(self, cluster, namespace, pod_name):
		"""
		Helper to get pod logs
		:param (str) cluster
		:param (str) namespace
		:param (str) pod_name
		:return: (str) pod logs, or "Logs unavailable" if ApiException
		"""
		try:
			doc = self.clients[cluster]["core_client"].read_namespaced_pod_log(pod_name, namespace)
		except kubernetes.client.rest.ApiException:
			doc = "Logs unavailable"
		return doc