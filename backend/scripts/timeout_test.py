import app as singleApp
from requests.packages import urllib3
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
import multiprocessing, time, json, io, sys
import numpy as np

def generate_json(name, dict):
	with io.open(name, 'w', encoding='utf-8') as f:
		f.write(json.dumps(dict, sort_keys=True, indent=4, separators=(',', ': '), ensure_ascii=False))

def get_apps(queue, client):
	ret = queue.get()
	dict = False
	try:
		dict = client.list_cluster_custom_object('app.k8s.io', 'v1beta1', 'applications')
	except (ApiException) as e:
		pass

	if dict:
		queue.put(dict)

def test(seconds, errorCount):
	try:
		view = Applications(seconds)
	except KeyError as e:
		pass

def testWait(seconds):
	errorCount = 0
	for i in range (20):
		p = multiprocessing.Process(target=test, args=(seconds, errorCount))
		p.start()
		time.sleep(3)
		if p.is_alive():
			p.terminate()
			p.join()
			print('process alive')
			continue
		else:
			errorCount += 1
	print("Final errorCount for", seconds, "seconds: ", errorCount)
	return errorCount

def testWaitTimes():
	seconds = np.arange(0.05, 2, 0.05)
	errors = {}
	for i in seconds:
		errors[i] = testWait(i)
	for key in errors:
		print('#', str(key)+':', errors[key])

def get_apps(contexts, seconds): # getting apps from current context
	apps_json = {}
	for context in contexts:
		cluster = context["context"]["cluster"]
		if cluster != "mycluster": # here we're making the assumption that the user is currently on the hub cluster
			continue
		api_client = config.new_client_from_config(context=context['name'])
		customs_client = client.CustomObjectsApi(api_client=api_client)
		queue = multiprocessing.Queue()
		ret = {}
		queue.put(ret)
		p = multiprocessing.Process(target=get_apps, args=(queue, customs_client))
		p.start()
		time.sleep(seconds)
		if p.is_alive():
			p.terminate()
			p.join()
			continue
		else:
			apps_json = queue.get()

	apps_dict = {}
	for app in apps_json['items']:
		apps_dict[app["metadata"]["name"]] = app
	return apps_dict

def getHierarchy(apps_dict):
	apps, uids, graph = {}, {}, {}
	for name in apps_dict:
		app = singleApp.Application(name, apps_dict[name], test_printing = True, graph = graph, uids = uids)
		app.getHierarchy()
		graph = app.graph
		uids = app.uids
		logs = app.logs
		apps["App_name: "+name] = app.generate_dicts()
	generate_json("test.json", apps)

if __name__ == "__main__":
	config.load_kube_config()
	urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
	contexts, active_context = config.list_kube_config_contexts()
	apps_dict = get_apps(contexts, 1.25)
	getHierarchy(apps_dict)

####### RESULTS OF ERROR COUNTS FROM TESTING WAIT TIMES FOR GETTING APPS #######
# wait time in seconds : error count out of 20
# 0.1: 20,
# 0.15000000000000002: 20,
# 0.20000000000000004: 4,
# 0.25000000000000006: 0,
# 0.30000000000000004: 3,
# 0.3500000000000001: 4,
# 0.40000000000000013: 0,
# 0.45000000000000007: 1,
# 0.5000000000000001: 0,
# 0.5500000000000002: 1,
# 0.6000000000000002: 0,
# 0.6500000000000001: 1,
# 0.7000000000000002: 0,
# 0.7500000000000002: 0,
# 0.8000000000000002: 0,
# 0.8500000000000002: 0,
# 0.9000000000000002: 1,
# 0.9500000000000003: 0
# 1.0: 0
# 1.05: 0
# 1.1: 0
# 1.1500000000000001: 0
# 1.2000000000000002: 0
# 1.2500000000000002: 0
# 1.3000000000000003: 0
# 1.3500000000000003: 0
# 1.4000000000000004: 0
# 1.4500000000000004: 0
# 1.5000000000000004: 0
# 1.5500000000000005: 0
# 1.6000000000000005: 0
# 1.6500000000000006: 0
# 1.7000000000000006: 0
# 1.7500000000000007: 0
# 1.8000000000000007: 0
# 1.8500000000000008: 0
# 1.9000000000000008: 0
# 1.9500000000000008: 0
####### END OF RESULTS #######
