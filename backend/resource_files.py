import clients_resources as cr
import yaml, datetime, pytz, kubernetes
import app_mode_backend as amb

class ResourceFiles:
	def __init__(self):
		self.clusters, self.clients, self.active_cluster= cr.get_clients()
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


	# both yaml and describe information lives in read, so it may make more sense ot output them as the same yaml file
	def get_yaml(self, type, name, namespace, cluster):
		if type in ["DaemonSet", "Deployment", "ReplicaSet", "StatefulSet"]:
			client = self.clients[cluster]["apps_client"]
		elif type in ["Pod", "Service", "Event", "Namespace"]:
			client = self.clients[cluster]["core_client"]
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
		elif type == "Application":
			doc = self.apps[name]
		elif type == "Deployable":
			doc = self.dpbs[name]
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
		event_list = []
		events = self.clients[cluster]["core_client"].list_namespaced_event(namespace).items
		events_list = [ e  for e in events if e.involved_object.uid == uid]
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
				total_age = ""
				age = current_age
			if source.get("host") and source.get("component"):
				source= source["component"] + ", " + source["host"]
			else:
				source = ""
			table.append([e["type"], e["reason"], age, source, e["message"]])
			# https://stackoverflow.com/questions/34752611/tabulate-according-to-terminal-width-in-python
		return table

	def get_logs(self, cluster, namespace, pod_name):
		try:
			doc = self.clients[cluster]["core_client"].read_namespaced_pod_log(pod_name, namespace)
		except kubernetes.client.rest.ApiException as e:
			doc = "Logs unavailable"
		return doc

def main():
	rf = ResourceFiles()
	# doc = rf.get_describe("Service", "ratings", "default", "mycluster")
	# doc = rf.get_yaml("Pod", "boisterous-shark-gbapp-frontend-8b5cc67bf-wctkb", "default","mycluster")
	doc = rf.get_logs("mycluster", "default", "boisterous-shark-gbapp-frontend-8b5cc67bf-wctkb")
	print(doc)

if __name__ == "__main__":
	main()
