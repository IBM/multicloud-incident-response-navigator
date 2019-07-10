

def get_application_summary(json):
	name = json["metadata"]["name"]
	uid = json["metadata"]["uid"]
	creationTimeStamp = str(json["metadata"]["creationTimestamp"])
	namespace = json["metadata"]["namespace"]
	labels = json["metadata"]["labels"]
	summary = { "Resource Type" : "Deployable", "Name":name, \
	"UID": uid, "Created": creationTimeStamp, "Namespace":namespace, "Labels":labels}
	return summary

def get_deployable_summary(json):
	name = json["metadata"]["name"]
	uid = json["metadata"]["uid"]
	creationTimeStamp = str(json["metadata"]["creationTimestamp"])
	namespace = json["metadata"]["namespace"]
	labels = json["metadata"]["labels"]
	annotations = json["metadata"]["annotations"]
	summary = { "Resource Type" : "Deployable", "Name":name, \
	"UID": uid, "Created": creationTimeStamp, "Namespace":namespace, "Labels":labels, \
	"Annotations" : annotations }
	return summary

def get_deployment_summary(json):
	name = json["metadata"]["name"]
	uid = json["metadata"]["uid"]
	date = str(json["metadata"]["creation_timestamp"])
	namespace = json["metadata"]["namespace"]
	summary = { "Resource Type" : "Deployment", "Name":name, \
	"UID": uid, "Created": date, "Namespace":namespace}
	return summary

def get_service_summary(json):
	creationTimeStamp = str(json["metadata"]["creation_timestamp"])
	labels = json["metadata"]["labels"]
	name = json["metadata"]["name"]
	namespace = json["metadata"]["namespace"]
	uid = json["metadata"]["uid"]
	clusterIP = json["spec"]["cluster_ip"]
	selector = json["spec"]["selector"]
	summary = { "Resource Type" : "Deployment", "Name":name, \
	"UID": uid, "Created": creationTimeStamp, "Namespace":namespace,\
	"Labels":labels, "ClusterIP":clusterIP, "Selector": selector}
	return summary

def get_rs_summary(json):
	creationTimeStamp = str(json["metadata"])
	labels = json["metadata"]["labels"]
	name = json["metadata"]["name"]
	namespace = json["metadata"]["namespace"]
	ownerRefs = json["metadata"]["owner_references"]
	uid = json["metadata"]["uid"]
	matchLabels = json["spec"]["selector"]["match_labels"]
	status = json["status"]
	summary = { "Resource Type" : "Deployment", "Name":name,  "Status":status, \
	"UID": uid, "Created": creationTimeStamp, "Namespace":namespace,\
	"Labels":labels, "MatchLabels":matchLabels, "Owner References":ownerRefs}
	return summary

def get_pod_summary(pod, cluster):
	ready, restarts = 0, 0
	containers, summary = { }, {} # rest of the pairs are (names:images)
	statuses = pod["status"].get("container_statuses")
	if statuses:
		for container in statuses:
			ready += container["ready"]
			restarts += container["restart_count"]
			containers[container["name"]] = container["image"]
		hostIP = pod["status"]["host_ip"]
		podIP = pod["status"]["pod_ip"]
		status = pod["status"]["phase"]
		startTime = pod["status"]["start_time"]
		name = pod["metadata"]["name"]
		namespace = pod["metadata"]["namespace"]
		uid = pod["metadata"]["uid"]
        # # # keeping this for possible calculation of resource ages in the future

        # diff = datetime.datetime.strptime(now, nowtimeFormat) - datetime.datetime.strptime(startTime, starttimeFormat)
		# days, seconds = diff.days, diff.seconds
		# [hours, minutes, seconds] = str(datetime.timedelta(seconds=seconds)).split(":")
		# hours, minutes, seconds = int(hours), int(minutes), int(seconds)
		# if not days:
		# 	if not hours:
		# 		age = str(minutes) +"m" + str(seconds) + "s"
		# 	else:
		# 		age = str(hours) +"h"
		# else:
		# 	age = str(days) +"d"
		# ready = str(ready)+"/"+str(len(pod["status"]["containerStatuses"]))

		summary = { "Resource Type": "Pod", "Ready": ready, "Status": status, "Restarts": restarts, \
		"hostIP": hostIP, "podIP": podIP, "container_Names:Images" : containers, \
		"namespace": namespace, "Cluster": cluster, "UID" : uid}
	return summary
