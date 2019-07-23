import cluster_mode_backend as cmb
import k8s_config
import k8s_api
import requests
import metrics
import json

# check what clusters we can access
k8s_config.update_available_clusters()

def get_unhealthy_pods():
    """
    (currently) gets unhealthy pods
    :return: list of unhealthy pods, where each item is (skipper_uid, rtype, name, reason, message)

    follows https://github.ibm.com/IBMPrivateCloud/search-collector/blob/master/pkg/transforms/pod.go
    """

    bad_pods = []
    pod_list = []

    # getting all pods
    clusters = k8s_config.all_cluster_names()
    for cluster in clusters:
        CoreV1Api_client = k8s_api.api_client(cluster, "CoreV1Api")
        namespaces = cmb.cluster_namespace_names(cluster)
        for ns in namespaces:
            pods = CoreV1Api_client.list_namespaced_pod(ns).items
            for pod in pods:
                pod_list.append((pod, ns, cluster))

    for pod, pod_ns, pod_cluster in pod_list:
        containers = []
        for ct in pod.spec.containers:
            containers.append(ct.name)

        reason = pod.status.phase
        if pod.status.reason is not None:
            reason = pod.status.reason

        initializing = False
        restarts = 0

        # loop through the containers
        if pod.status.init_container_statuses != None:
            for i,ct in enumerate(pod.status.init_container_statuses):
                restarts += ct.restart_count

                if ct.state.terminated != None and ct.state.terminated.exit_code == 0:
                    continue
                elif ct.state.terminated != None:
                    # initialization failed
                    if len(ct.state.terminated.reason) == 0:
                        if ct.state.terminated.signal != 0:
                            reason = "Init:Signal:{}".format(ct.state.terminated.signal)
                        else:
                            reason = "Init:ExitCode:{}".format(ct.state.terminated.exit_code)
                    else:
                        reason = "Init:" + ct.state.terminated.reason
                    initializing = True
                elif ct.state.waiting != None and len(ct.state.waiting.reason) > 0 and ct.state.waiting.reason != "PodInitializing":
                    reason = "Init:" + ct.state.waiting.reason
                else:
                    reason = "Init:{}/{}".format(i, len(pod.spec.init_containers))
                    initializing = True
                break

        if not initializing:
            # clear and sum the restarts
            restarts = 0
            hasRunning = False
            if pod.status.container_statuses != None:
                for ct in pod.status.container_statuses[::-1]:
                    restarts += ct.restart_count

                    if ct.state.waiting != None and ct.state.waiting.reason != None:
                        reason = ct.state.waiting.reason
                    elif ct.state.terminated != None and ct.state.terminated.reason != None:
                        reason = ct.state.terminated.reason
                    elif ct.state.terminated != None and ct.state.terminated.reason == None:
                        if ct.state.terminated.signal != 0:
                            reason = "Signal:{}".format(ct.state.terminated.signal)
                        else:
                            reason = "ExitCode:{}".format(ct.state.terminated.exit_code)
                    elif ct.ready and ct.state.running != None:
                        hasRunning = True

            # change pod status back to Running if there is at least one container still reporting as "Running" status
            if reason == "Completed" and hasRunning:
                reason = "Running"

        if pod.metadata.deletion_timestamp != None and pod.status.reason == "NodeLost":
            reason = "Unknown"
        elif pod.metadata.deletion_timestamp != None:
            reason = "Terminating"

        message = pod.status.message if pod.status.message != None else ''

        # TODO will need to test with more data
        if reason not in ['Running','Succeeded','Completed']:
            skipper_uid = pod_cluster + "_" + pod.metadata.uid
            bad_pods.append((skipper_uid, 'Pod', pod.metadata.name, reason, message))

            pod_metrics, container_metrics = metrics.aggregate_pod_metrics(pod_cluster, pod_ns, pod.metadata.name)
            info = {'pod_metrics': pod_metrics, 'container_metrics': container_metrics}

            created_at = pod.metadata.creation_timestamp
            # write pods to db
            resource_data = {'uid': skipper_uid, "created_at": created_at, "rtype": 'Pod',
                             "name": pod.metadata.name, "cluster": pod_cluster, "namespace": pod_ns, "info": json.dumps(info)}
            requests.post('http://127.0.0.1:5000/resource/{}'.format(skipper_uid), data=resource_data)

    return bad_pods

def get_resources_with_bad_events():
    """
    Goes through kubernetes events and gets resources with "bad" events, determined by me
    https://github.com/kubernetes/kubernetes/blob/master/pkg/kubelet/events/event.go

    :return: list of unhealthy resources, where each item is (skipper_uid, rtype, name, reason, message)
    """

    bad_resources = []
    clusters = k8s_config.all_cluster_names()
    for cluster in clusters:
        api_client = k8s_api.api_client(cluster, "CoreV1Api")
        namespaces = cmb.cluster_namespace_names(cluster)
        for ns in namespaces:
            events = api_client.list_namespaced_event(ns).items
            for ev in events:
                if ev.type == 'Warning' or ev.reason not in ['Created','Started',
                                                             'Pulling','Pulled',
                                                             'NodeReady','NodeSchedulable',
                                                             'Starting',
                                                             'VolumeResizeSuccessful','SuccessfulAttachVolume','SuccessfulMountVolume',
                                                             'Rebooted',
                                                             'Scheduled', 'Schedule',
                                                             'ScalingReplicaSet',
                                                             'SuccessfulCreate',
                                                             'SandboxChanged']:

                    message = ev.message if ev.message != None else ''

                    if ev.reason != None:
                        skipper_uid = cluster + "_" + ev.involved_object.uid
                        bad_resources.append((skipper_uid,ev.involved_object.kind,ev.involved_object.name, ev.reason, message))

                        info = {}
                        if ev.involved_object.kind == 'Pod':
                            pod_metrics, container_metrics = metrics.aggregate_pod_metrics(cluster, ns, ev.involved_object.name)
                            info['pod_metrics'] = pod_metrics
                            info['container_metrics'] = container_metrics

                        # write resources to db
                        resource_data = {'uid': skipper_uid, "rtype": ev.involved_object.kind,
                                         "name": ev.involved_object.name, "cluster": cluster, "namespace": ns, "info":json.dumps(info)}
                        requests.post('http://127.0.0.1:5000/resource/{}'.format(skipper_uid), data=resource_data)

    return bad_resources
