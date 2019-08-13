import os, sys
import requests, json, time, yaml
import kubernetes as k8s
from dateutil.parser import parse

print("Loading backend functions...")
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))
import k8s_config
import cluster_mode_backend as cmb
import app_mode_backend as amb
import errors_backend as eb

print("Getting access to db...")
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'controller', 'webserver'))
from app.models import Resource, Edge

print("Loading kube config...")
k8s_config.load_kube_config()
k8s_config.update_available_clusters()

# For reference
# {"uid", "created_at", "rtype", "name", "cluster", "namespace", "application", "app_path", "cluster_path", "sev_measure", "sev_reason", "info"}

def load_all() -> None:
	"""
	Loads all Resources and Edges into the database.
	"""

	def to_json(k8s_obj: k8s.client.models) -> str:
		to_s = lambda dt: dt.__str__()
		return json.dumps(k8s_obj.to_dict(), default=to_s)

	all_nss = []                # all namespaces
	all_deploys = []            # all deployments
	all_svcs = []               # all services
	all_dsets = []              # all daemonsets
	all_ssets = []              # all statefulsets
	all_pods = []               # all pods

	all_dpbs = []               # all deployables

	start = time.time()         # time how long one round of load-all takes
	split_start = time.time()   # time how long each portion takes

	print("\nStarting a round of load-all. Strap yourself in, astronaut.")

	# insert all clusters into the database
	stale_clusters = Resource.query.filter(Resource.rtype=="Cluster").all()
	stale_cdict = { c.name: c for c in stale_clusters }
	cluster_names = k8s_config.all_cluster_names()
	mcm_clusters = cmb.mcm_clusters(cluster_names)
	for cname in cluster_names:
		if cname in mcm_clusters:
			mcm_cluster = mcm_clusters[cname]
			mcm_cluster["yaml"] = yaml.dump(mcm_cluster, sort_keys=False)
			cluster_data = {'uid': cname, "rtype": 'Cluster', "name": cname , "cluster": cname ,
						 "cluster_path": "/root/", "created_at" : mcm_cluster["metadata"].get("creationTimestamp"),
						 "info" : json.dumps(mcm_cluster)}
		else:
			cluster_data = {"uid": cname, "rtype": "Cluster", "name": cname,
							"cluster": cname, "cluster_path": "/root/"}

		# remove cluster from running list of stale clusters
		if cname in stale_cdict.keys():
			stale_cdict.pop(cname)

		requests.post('http://127.0.0.1:5000/resource/{}'.format(cname), data=cluster_data)

		# find all namespaces under this cluster and add it
		# to the running list of namespaces (all_nss)
		nss = cmb.cluster_namespaces(cluster_name=cname)
		for ns in nss:
			ns.metadata.cluster_name = cname
		all_nss += nss

	# remove all stale clusters, descendants, and associated edges
	# i.e. clusters that were in the db but that we didn't find
	for cname in stale_cdict.keys():
		requests.delete('http://127.0.0.1:5000/resource/{}'.format(cname))

		# remove any apps that were defined in the cluster
		cluster_apps = Resource.query.filter(Resource.rtype=="Application" and Resource.uid.like(cname + "%")).all()
		for capp in cluster_apps:
			requests.delete('http://127.0.0.1:5000/resource/{}'.format(capp.uid))

	print("Wrote %d clusters and found all child namespaces in %d seconds." % (len(cluster_names), time.time() - split_start))

	# insert all applications into the database
	split_start = time.time()
	stale_apps = Resource.query.filter(Resource.rtype == "Application").all()
	stale_adict = { app.uid: app for app in stale_apps }
	apps = amb.all_applications()
	for app in apps:	
		md = app["metadata"]
		name, cname, ns, k8s_uid = md["name"], md["cluster_name"], md["namespace"], md["uid"]
		app_uid = cname + "_" + k8s_uid
		created_at = parse(app["metadata"]["creationTimestamp"])
		app_data = { "uid": app_uid, "created_at": created_at, "rtype": "Application",
						"name": name, "cluster": cname, "namespace": ns, "application": name,
							"app_path": "/root/", "info": json.dumps(app)}
		requests.post('http://127.0.0.1:5000/resource/{}'.format(app_uid), data=app_data)

		# find all deployables under this application and add it to the running
		# list of all deployables (all_dpbs)
		deployables = amb.application_deployables(cluster_name=cname, namespace=ns, app_name=name)
		for dpb in deployables:
			dpb["metadata"]["app_name"] = name
			dpb["metadata"]["app_uid"] = app_uid
		all_dpbs += deployables

		# remove this app from running list of stale apps
		if app_uid in stale_adict.keys():
			stale_adict.pop(app_uid)

	# remove all stale apps, descendants, and associated edges
	for app_uid in stale_adict:
		requests.delete('http://127.0.0.1:5000/resource/{}'.format(app_uid))

	print("Wrote %d applications and found all child deployables in %d seconds." % (len(apps), time.time() - split_start))

	# insert all namespaces and corresponding edges into the database
	split_start = time.time()
	stale_nss = Resource.query.filter(Resource.rtype == "Namespace").all()
	stale_nsdict = { ns.uid: ns for ns in stale_nss }
	for ns in all_nss:
		cname = ns.metadata.cluster_name
		ns_uid = cname + "_" + ns.metadata.uid
		ns_name = ns.metadata.name
		created_at = ns.metadata.creation_timestamp
		ns_resource = {"uid": ns_uid, "created_at": created_at, "rtype": "Namespace",
					"name": ns_name, "cluster": cname, "namespace": ns_name,
					"cluster_path": "/root/{}/".format(cname), "info": to_json(ns)}
		ns_edge = {"start_uid": cname, "end_uid": ns_uid, "relation": "Cluster<-Namespace"}
		requests.post('http://127.0.0.1:5000/resource/{}'.format(ns_uid), data=ns_resource)
		requests.post('http://127.0.0.1:5000/edge/{}/{}'.format(cname, ns_uid), data=ns_edge)

		# remove this ns from list of stale namespaces
		if ns_uid in stale_nsdict.keys():
			stale_nsdict.pop(ns_uid)

		# find all deployments under this namespace and add it to the running
		# list of all deployments (all_deploys)
		deploys = cmb.namespace_deployments(cluster_name=cname, namespace=ns_name)
		for deploy in deploys:
			deploy.metadata.cluster_name = cname
			deploy.metadata.ns_uid = ns_uid
		all_deploys += deploys

		# find all services under this namespace and add it to the running
		# list of all services (all_svcs)
		svcs = cmb.namespace_services(cluster_name=cname, namespace=ns_name)
		for svc in svcs:
			svc.metadata.cluster_name = cname
			svc.metadata.ns_uid = ns_uid
		all_svcs += svcs

		# find all daemonsets under this namespace and add it to the running
		# list of all daemonsets (all_dsets)
		dsets = cmb.namespace_daemon_sets(cluster_name=cname, namespace=ns_name)
		for dset in dsets:
			dset.metadata.cluster_name = cname
			dset.metadata.ns_uid = ns_uid
		all_dsets += dsets

		# find all statefulsets under this namespace and add it to the running
		# list of all statefulsets (all_ssets)
		ssets = cmb.namespace_stateful_sets(cluster_name=cname, namespace=ns_name)
		for sset in ssets:
			sset.metadata.cluster_name = cname
			sset.metadata.ns_uid = ns_uid
		all_ssets += ssets

	# remove all stale namespaces, their descendants and associated edges
	for sns_uid in stale_nsdict.keys():
		requests.delete('http://127.0.0.1:5000/resource/{}'.format(sns_uid))

	print("Wrote %d namespaces and found child deployments, services, daemonsets and statefulsets in %d seconds." % (len(all_nss), time.time() - split_start))

	# insert all deployables and corresponding edges into the database
	split_start = time.time()
	stale_dpbs = Resource.query.filter(Resource.rtype == "Deployable").all()
	stale_dpb_dict = { dpb.uid: dpb for dpb in stale_dpbs }
	for dpb in all_dpbs:
		md = dpb["metadata"]
		app_name, app_uid = md["app_name"], md["app_uid"]
		dpb_name, k8s_uid, cname, ns = md["name"], md["uid"], md["cluster_name"], md["namespace"]
		dpb_uid = cname + "_" + k8s_uid
		created_at = parse(dpb["metadata"]["creationTimestamp"])
		dpb_resource = {"uid": dpb_uid, "created_at": created_at, "rtype": "Deployable",
					"name": dpb_name, "cluster": cname, "namespace": ns, "application": app_name,
					"app_path": "/root/{}/".format(app_uid), "info": json.dumps(dpb)}
		dpb_edge = {"start_uid": app_uid, "end_uid": dpb_uid, "relation": "Application<-Deployable"}
		requests.post('http://127.0.0.1:5000/resource/{}'.format(dpb_uid), data=dpb_resource)
		requests.post('http://127.0.0.1:5000/edge/{}/{}'.format(app_uid, dpb_uid), data=dpb_edge)

		# remove this deployable from the list of stale deployables
		if dpb_uid in stale_dpb_dict.keys():
			stale_dpb_dict.pop(dpb_uid)

	# remove all stale deployables, their descendants and associated edges
	for dpb_uid in stale_dpb_dict.keys():
		requests.delete('http://127.0.0.1:5000/resource/{}'.format(dpb_uid))

	print("Wrote %d deployables in %d seconds." % (len(all_dpbs), time.time() - split_start ))

	# insert all deployments and corresponding edges into the database
	split_start = time.time()
	stale_deploys = Resource.query.filter(Resource.rtype == "Deployment").all()
	stale_deploy_dict = { deploy.uid: deploy for deploy in stale_deploys }
	for deploy in all_deploys:
		cname = deploy.metadata.cluster_name
		ns_uid = deploy.metadata.ns_uid
		deploy_uid = cname + "_" + deploy.metadata.uid
		deploy_path = "/root/{}/{}/".format(cname, ns_uid)
		created_at = deploy.metadata.creation_timestamp
		deploy_resource = {"uid": deploy_uid, "created_at": created_at, "rtype": "Deployment",
						"name": deploy.metadata.name, "cluster": cname, "namespace": deploy.metadata.namespace,
						"cluster_path": deploy_path, "info": to_json(deploy)}
		deploy_edge = {"start_uid": ns_uid, "end_uid": deploy_uid, "relation": "Namespace<-Deployment"}
		requests.post('http://127.0.0.1:5000/resource/{}'.format(deploy_uid), data=deploy_resource)
		requests.post('http://127.0.0.1:5000/edge/{}/{}'.format(ns_uid, deploy_uid), data=deploy_edge)	

		# find all pods being managed by this deployment and add them to the list of all pods (all_pods)
		pods = cmb.deployment_pods(cluster_name=cname, namespace=deploy.metadata.namespace, deploy_name=deploy.metadata.name)
		for pod in pods:
			pod.metadata.cluster_name = cname
			pod.metadata.ns_uid = ns_uid
			pod.metadata.parent_uid = deploy_uid
			pod.metadata.parent_type = "Deployment"
		all_pods += pods

		# remove this deployment from the list of stale deployments
		if deploy_uid in stale_deploy_dict.keys():
			stale_deploy_dict.pop(deploy_uid)

	# remove all stale deployments, their descendants and associated edges
	for deploy_uid in stale_deploy_dict.keys():
		requests.delete('http://127.0.0.1:5000/resource/{}'.format(deploy_uid))

	print("Wrote %d deployments and found managed pods in %d seconds." % (len(all_deploys), time.time() - split_start))

	# insert all services and corresponding edges into the database
	split_start = time.time()
	stale_svcs = Resource.query.filter(Resource.rtype == "Service").all()
	stale_svc_dict = { svc.uid: svc for svc in stale_svcs }
	for svc in all_svcs:
		cname = svc.metadata.cluster_name
		ns_uid = svc.metadata.ns_uid
		svc_uid = cname + "_" + svc.metadata.uid
		svc_path = "/root/{}/{}/".format(cname, ns_uid)
		created_at = svc.metadata.creation_timestamp
		svc_resource = {"uid": svc_uid, "created_at": created_at, "rtype": "Service",
						"name": svc.metadata.name, "cluster": cname, "namespace": svc.metadata.namespace,
						"cluster_path": svc_path, "info": to_json(svc)}
		svc_edge = {"start_uid": ns_uid, "end_uid": svc_uid, "relation": "Namespace<-Service"}
		requests.post('http://127.0.0.1:5000/resource/{}'.format(svc_uid), data=svc_resource)
		requests.post('http://127.0.0.1:5000/edge/{}/{}'.format(ns_uid, svc_uid), data=svc_edge)

		# find all pods selected by this service and add them to the list of all pods (all_pods)
		pods = cmb.service_pods(cluster_name=cname, namespace=svc.metadata.namespace, svc_name=svc.metadata.name)
		for pod in pods:
			pod.metadata.cluster_name = cname
			pod.metadata.ns_uid = ns_uid
			pod.metadata.parent_uid = svc_uid
			pod.metadata.parent_type = "Service"
		all_pods += pods

		# remove this service from the list of stale services
		if svc_uid in stale_svc_dict.keys():
			stale_svc_dict.pop(svc_uid)

	# remove all stale services, their descendants and associated edges
	for svc_uid in stale_svc_dict.keys():
		requests.delete('http://127.0.0.1:5000/resource/{}'.format(svc_uid))

	print("Wrote %d services and found selected pods in %d seconds." % (len(all_svcs), time.time() - split_start))

	# insert all daemonsets and corresponding edges into the database
	split_start = time.time()
	stale_dsets = Resource.query.filter(Resource.rtype == "DaemonSet").all()
	stale_dset_dict = { dset.uid: dset for dset in stale_dsets }
	for dset in all_dsets:
		cname = dset.metadata.cluster_name
		ns_uid = dset.metadata.ns_uid
		dset_uid = cname + "_" + dset.metadata.uid
		dset_path = "/root/{}/{}/".format(cname, ns_uid)
		created_at = dset.metadata.creation_timestamp
		dset_resource = {"uid": dset_uid, "created_at": created_at, "rtype": "DaemonSet",
					"name": dset.metadata.name, "cluster": cname, "namespace": dset.metadata.namespace,
					"cluster_path": dset_path, "info": to_json(dset)}
		dset_edge = {"start_uid": ns_uid, "end_uid": dset_uid, "relation": "Namespace<-DaemonSet"}
		requests.post('http://127.0.0.1:5000/resource/{}'.format(dset_uid), data=dset_resource)
		requests.post('http://127.0.0.1:5000/edge/{}/{}'.format(ns_uid, dset_uid), data=dset_edge)

		# find all pods managed by this daemonset and add them to the list of all pods (all_pods)
		pods = cmb.daemon_set_pods(cluster_name=cname, namespace=dset.metadata.namespace, dset_name=dset.metadata.name)
		for pod in pods:
			pod.metadata.cluster_name = cname
			pod.metadata.ns_uid = ns_uid
			pod.metadata.parent_uid = dset_uid
			pod.metadata.parent_type = "DaemonSet"
		all_pods += pods

		# remove this daemonset from the list of stale daemonsets
		if dset_uid in stale_dset_dict.keys():
			stale_dset_dict.pop(dset_uid)

	# remove all stale daemonsets, their descendants and associated edges
	for dset_uid in stale_dset_dict.keys():
		requests.delete('http://127.0.0.1:5000/resource/{}'.format(dset_uid))

	print("Wrote %d daemonsets and found managed pods in %d seconds." % (len(all_dsets), time.time() - split_start))

	# insert all stateful sets and corresponding edges into the database
	split_start = time.time()
	stale_ssets = Resource.query.filter(Resource.rtype == "StatefulSet").all()
	stale_sset_dict = { sset.uid: sset for sset in stale_ssets }
	for sset in all_ssets:
		cname = sset.metadata.cluster_name
		ns_uid = sset.metadata.ns_uid
		sset_uid = cname + "_" + sset.metadata.uid
		sset_path = "/root/{}/{}/".format(cname, ns_uid)
		created_at = sset.metadata.creation_timestamp
		sset_resource = {"uid": sset_uid, "created_at": created_at, "rtype": "StatefulSet",
							"name": sset.metadata.name, "cluster": cname, "namespace": sset.metadata.namespace,
							"cluster_path": sset_path, "info": to_json(sset)}
		sset_edge = {"start_uid": ns_uid, "end_uid": sset_uid, "relation": "Namespace<-StatefulSet"}
		requests.post('http://127.0.0.1:5000/resource/{}'.format(sset_uid), data=sset_resource)
		requests.post('http://127.0.0.1:5000/edge/{}/{}'.format(ns_uid, sset_uid), data=sset_edge)

		# find all pods managed by this statefulset and add them to the list of all pods (all_pods)
		pods = cmb.stateful_set_pods(cluster_name=cname, namespace=sset.metadata.namespace, sset_name=sset.metadata.name)
		for pod in pods:
			pod.metadata.cluster_name = cname
			pod.metadata.ns_uid = ns_uid
			pod.metadata.parent_uid = sset_uid
			pod.metadata.parent_type = "StatefulSet"
		all_pods += pods

		# remove this stateful set from the list of stale statefulsets
		if sset_uid in stale_sset_dict.keys():
			stale_sset_dict.pop(sset_uid)

	# remove all stale statefulsets, their descendants and associated edges
	for sset_uid in stale_sset_dict.keys():
		requests.delete('http://127.0.0.1:5000/resource/{}'.format(sset_uid))

	print("Wrote %d statefulsets and found managed pods in %d seconds." % (len(all_ssets), time.time() - split_start))

	# insert all pods and corresponding edges into the database
	split_start = time.time()
	stale_pods = Resource.query.filter(Resource.rtype == "Pod").all()
	stale_pod_dict = { pod.uid: pod for pod in stale_pods }
	for pod in all_pods:
		cname = pod.metadata.cluster_name
		ns_uid = pod.metadata.ns_uid
		parent_uid = pod.metadata.parent_uid
		parent_type = pod.metadata.parent_type
		pod_uid = cname + "_" + pod.metadata.uid
		pod_path = "/root/{}/{}/{}/".format(cname, ns_uid, parent_uid)
		sev_measure, sev_reason = eb.pod_state(pod)
		created_at = pod.metadata.creation_timestamp

		# don't write this pod to db w/ a cluster_path that goes through a service
		if parent_type != "Service":
			pod_resource = {"uid": pod_uid, "created_at": created_at, "rtype": "Pod",
							"name": pod.metadata.name, "cluster": cname, "namespace": pod.metadata.namespace,
							"cluster_path": pod_path, "sev_measure": sev_measure, "sev_reason": sev_reason, "info": to_json(pod)}
			requests.post('http://127.0.0.1:5000/resource/{}'.format(pod_uid), data=pod_resource)

		pod_edge = {"start_uid": parent_uid, "end_uid": pod_uid, "relation": parent_type + "<-Pod"}
		requests.post('http://127.0.0.1:5000/edge/{}/{}'.format(parent_uid, pod_uid), data=pod_edge)

		# remove this pod from the list of stale pods
		if pod_uid in stale_pod_dict.keys():
			stale_pod_dict.pop(pod_uid)

	# remove all stale pods and associated edges
	for pod_uid in stale_pod_dict.keys():
		requests.delete('http://127.0.0.1:5000/resource/{}'.format(pod_uid))

	print("Wrote %d pods in %d seconds." % (len(all_pods), time.time() - split_start))

	# create edges between deployables and their resources
	split_start = time.time()
	for dpb in all_dpbs:
		cname = dpb["metadata"]["cluster_name"]
		ns_name = dpb["metadata"]["namespace"]
		app_name = dpb["metadata"]["app_name"]
		app_uid = dpb["metadata"]["app_uid"]
		dpb_name = dpb["metadata"]["name"]
		dpb_uid = cname + "_" + dpb["metadata"]["uid"]
		resource = amb.deployable_resource(cluster_name=cname, namespace=ns_name, deployable_name=dpb_name)

		# case: helm charts
		if resource == {}:
			continue

		resource_uid = resource["metadata"]["cluster_name"] + "_" + resource["metadata"]["uid"]
		resource_edge = {"start_uid": dpb_uid, "end_uid": resource_uid, "relation": "Deployable<-" + resource["kind"]}
		requests.post('http://127.0.0.1:5000/edge/{}/{}'.format(dpb_uid, resource_uid), data=resource_edge)

		# update app_path of resource
		update_info = {"uid": resource_uid, "app_path": "/root/{}/{}/".format(app_uid, dpb_uid), "application" : app_name}
		requests.post('http://127.0.0.1:5000/resource/{}'.format(resource_uid), data=update_info)

		# update app_path of the resource's pods
		pods = []
		if resource["kind"] == "Deployment":
			pods = cmb.deployment_pods(cluster_name=resource["metadata"]["cluster_name"],
											namespace=resource["metadata"]["namespace"],
											deploy_name=resource["metadata"]["name"])
		elif resource["kind"] == "DaemonSet":
			pods = cmb.daemon_set_pods(cluster_name=resource["metadata"]["cluster_name"],
											namespace=resource["metadata"]["namespace"],
											dset_name=resource["metadata"]["name"])
		elif resource["kind"] == "StatefulSet":
			pods = cmb.stateful_set_pods(cluster_name=resource["metadata"]["cluster_name"],
											namespace=resource["metadata"]["namespace"],
											sset_name=resource["metadata"]["name"])
		for pod in pods:
			pod_uid = resource["metadata"]["cluster_name"] + "_" + pod.metadata.uid
			update_info = {"uid": pod_uid, "application": app_name, "app_path": "/root/{}/{}/{}/".format(app_uid, dpb_uid, resource_uid)}
			requests.post('http://127.0.0.1:5000/resource/{}'.format(pod_uid), data=update_info)

	print("Updated app_paths and created app mode edges in %d seconds." % (time.time() - split_start))

	print("Total time elapsed: {} secs".format(time.time()-start))

if __name__ == "__main__":

	# wait for the webserver to come up
	while True:
		try:
			requests.get("http://127.0.0.1:5000/")
		except requests.exceptions.ConnectionError as e:
			print("Waiting for webserver to start...\r")
			time.sleep(1)
		else:
			break

	try:
		# crawl continuously
		while True:
			load_all()
	except KeyboardInterrupt as e:
		sys.exit(0)
