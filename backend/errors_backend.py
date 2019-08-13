from typing import Tuple
import kubernetes as k8s
import k8s_config, k8s_api, cluster_mode_backend as cmb

# used for type suggestions
V1Pod = k8s.client.models.v1_pod.V1Pod

def pod_state(pod: V1Pod) -> Tuple[int, str]:
    """
    Returns pod sev_measure and pod status

    :param (V1Pod) pod: pod object
    :return: ((int) sev_measure, 0 for good status, 1 for bad status,
              (str) pod status, as shown in status column in kubectl get pods)
    """
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

    if reason not in ['Running','Succeeded','Completed']:
        return (1, reason)
    return (0, reason)

def get_unhealthy_pods():
    """
    Gets unhealthy pods
    (follows same logic as https://github.ibm.com/IBMPrivateCloud/search-collector/blob/master/pkg/transforms/pod.go)

    :return: ((List(tuple)) skipper_uid, rtype, name, reason, message,
              (List(V1Pod)) pod object)
    """
    bad_pods = []
    table_rows = []
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

        if reason not in ['Running','Succeeded','Completed']:
            skipper_uid = pod_cluster + "_" + pod.metadata.uid
            pod.metadata.cluster_name = pod_cluster
            pod.metadata.sev_reason = reason
            bad_pods.append(pod)
            table_rows.append((skipper_uid, 'Pod', pod.metadata.name, reason, message))

    return (table_rows, bad_pods)