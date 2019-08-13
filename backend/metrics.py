import requests
from kubernetes import client, config
from hurry.filesize import size, iec
from si_prefix import si_format
import k8s_api, k8s_config

k8s_config.update_available_clusters()

def get_value_and_unit(value_string):
    """
    Takes a string and splits it up, returning the number part and the unit part

    :param (str) value_string: examples: "100Mi", "8", "500n" (does not need to include unit)
    :return: ((int) numerical value, (str) unit, which is empty string for no unit)
    """
    i = 0
    while i < len(value_string) and (value_string[i].isdigit() or value_string[i] == 'e'): # e for scientific notation
        i += 1
    first_nondigit_index = i

    value = int(float(value_string[:first_nondigit_index]))
    unit = value_string[first_nondigit_index:]
    return (value, unit)

def convert_to_base_unit(value, unit):
    """
    Convert value from current unit to base unit
    :param (int) value: Numerical value
    :param (str) unit: unit, where empty string denotes base unit
    :return: (int) the value in base unit
    """
    POWERS_BY_UNIT = {'n': -3,
                        'u': -2,
                        'm': -1,
                        '': 0,
                        'K': 1, 'Ki': 1,
                        'M': 2, 'Mi': 2,
                        'G': 3, 'Gi': 3,
                        'T': 4, 'Ti': 4,
                        'P': 5, 'Pi': 5,
                        'E': 6, 'Ei': 6}

    if unit in ['n','u','m','','K','M','G','T','P','E']: # normal si system prefixes
        base = 1000
    else: # iec system
        base = 1024
    return value * (base ** POWERS_BY_UNIT[unit])

def aggregate_pod_metrics(cluster_name, namespace, pod_name):
    """
    Get the pod and container compute resources
    :param (str) cluster_name: cluster the pod is in
    :param (str) namespace: namespace the pod is in
    :param (str) pod_name
    :return: ((Dict) pod_final, (Dict) containers_final)
                where if resource_metric_dict = {'cpu': (str) current_cpu, 'cpu_limit': (str) cpu_limit or 'N/A',
                                                'mem': (str) current_mem, 'mem_limit': (str) mem_limit or 'N/A'},
                then pod_final = resource_metric_dict (for pod),
                and containers_final = Dict('init_containers': Dict(<container_name>, resource_metric_dict),
                                            'containers': Dict(<container_name>, resource_metric_dict)), or None if no container info
    """

    def get_pod_container_usage(cluster_name, namespace, pod_name):
        """
        Helper method for getting current usage for containers in a pod
        :return: Dict(container_name : (cpu, mem)), or None if http request failed
        """
        # load configuration for the desired context to get host and api key
        myconfig = client.Configuration()
        desired_context = k8s_config.context_for_cluster(cluster_name)
        config.load_kube_config(context=desired_context, client_configuration=myconfig)

        # request to get pod
        server = myconfig.host
        headers = myconfig.api_key
        url = server + "/apis/metrics.k8s.io/v1beta1/namespaces/{}/pods/{}".format(namespace, pod_name)
        response = requests.get(url, headers=headers, verify=False)

        if response.status_code == 200:
            pod_metrics = response.json()
            usage_by_container = {}
            if pod_metrics.get('containers'):
                for ct in pod_metrics['containers']:
                    usage_by_container[ct['name']] = (ct['usage']['cpu'], ct['usage']['memory'])
            return usage_by_container
        else:
            return None

    def get_pod_container_limits(cluster_name, namespace, pod_name):
        """
        Helper method for getting limits for containers in a pod
        :return: Dict(container_name : (cpu, mem, (bool) is_init_container))), where None for cpu and mem mean no limits specified
        """
        api_client = k8s_api.api_client(cluster_name=cluster_name, api_class="CoreV1Api")
        pod_object = api_client.read_namespaced_pod(pod_name, namespace)

        limits_by_container = {}
        containers = pod_object.spec.containers
        for ct in containers:
            name = ct.name

            try:
                ct_cpu_limit = ct.resources.limits.get('cpu')
            except:
                ct_cpu_limit = None
            try:
                ct_mem_limit = ct.resources.limits.get('memory')
            except:
                ct_mem_limit = None
            limits_by_container[name] = (ct_cpu_limit, ct_mem_limit, False)

        if pod_object.spec.init_containers is not None:
            for ct in pod_object.spec.init_containers:
                name = ct.name

                try:
                    ct_cpu_limit = ct.resources.limits.get('cpu')
                except:
                    ct_cpu_limit = None
                try:
                    ct_mem_limit = ct.resources.limits.get('memory')
                except:
                    ct_mem_limit = None
                limits_by_container[name] = (ct_cpu_limit, ct_mem_limit, True)

        return limits_by_container

    # get current container usage and limits
    container_limits = get_pod_container_limits(cluster_name,namespace,pod_name)
    container_usage = get_pod_container_usage(cluster_name,namespace,pod_name)
    if container_usage is None: # no container usage info
        return {'cpu': None, 'memory': None}, None

    # initialize variables used to keep cumulative sum
    pod_cpu_usage = 0
    pod_mem_usage = 0

    # check if a pod limit makes sense to calculate - all (non-init) containers have to have a limit
    pod_cpu_limit, pod_mem_limit = 0, 0
    for ct in container_limits:
        if container_limits[ct][2]: # is init container
            continue
        if container_limits[ct][0] is None:
            pod_cpu_limit = None
        if container_limits[ct][1] is None:
            pod_mem_limit = None

    containers_final = {'init_containers': {}, 'containers': {}}
    for ct_name in container_usage.keys():
        ct_cpu_usage, ct_mem_usage = container_usage[ct_name]
        ct_cpu_limit, ct_mem_limit, is_init_container = container_limits[ct_name]

        ct_cpu_pct = ""
        ct_mem_pct = ""

        # get container cpu usage value and add onto pod cpu usage
        value, unit = get_value_and_unit(ct_cpu_usage)
        ct_cpu_usage_value = convert_to_base_unit(value, unit)
        pod_cpu_usage += ct_cpu_usage_value

        if ct_cpu_limit is not None:
            # calculate percentage (current/limit) and return the formatted string
            value, unit = get_value_and_unit(ct_cpu_limit)
            ct_cpu_limit_value = convert_to_base_unit(value, unit)
            if pod_cpu_limit is not None and not is_init_container:
                pod_cpu_limit += ct_cpu_limit_value

            ct_cpu_pct = "(" + str(round(ct_cpu_usage_value / ct_cpu_limit_value * 100)) + "%)"

        # same process for memory
        value, unit = get_value_and_unit(ct_mem_usage)
        ct_mem_usage_value = convert_to_base_unit(value, unit)
        pod_mem_usage += ct_mem_usage_value

        if ct_mem_limit is not None:
            value, unit = get_value_and_unit(ct_mem_limit)
            ct_mem_limit_value = convert_to_base_unit(value, unit)
            if pod_mem_limit is not None and not is_init_container:
                pod_mem_limit += ct_mem_limit_value

            ct_mem_pct = "(" + str(round(ct_mem_usage_value / ct_mem_limit_value * 100)) + "%)"

        ct_dict = {'cpu': si_format(ct_cpu_usage_value, precision=0, format_str='{value}{prefix}') + " " + ct_cpu_pct,
                    'cpu_limit': si_format(ct_cpu_limit_value, precision=0, format_str='{value}{prefix}') if ct_cpu_limit is not None else "N/A",
                    'mem': size(ct_mem_usage_value, system=iec) + " " + ct_mem_pct,
                    'mem_limit': size(ct_mem_limit_value, system=iec) if ct_mem_limit is not None else "N/A"}
        if is_init_container:
            containers_final['init_containers'][ct_name] = ct_dict
        else:
            containers_final['containers'][ct_name] = ct_dict

    # calculate pod percentages
    pod_cpu_pct = ""
    pod_mem_pct = ""
    if pod_cpu_limit is not None:
        pod_cpu_pct = "(" + str(round(pod_cpu_usage / pod_cpu_limit * 100)) + "%)"
    if pod_mem_limit is not None:
        pod_mem_pct = "(" + str(round(pod_mem_usage / pod_mem_limit * 100)) + "%)"

    pod_final = {'cpu': si_format(pod_cpu_usage, precision=0, format_str='{value}{prefix}') + " " + pod_cpu_pct,
                 'cpu_limit': si_format(pod_cpu_limit, precision=0,format_str='{value}{prefix}') if pod_cpu_limit is not None else "N/A",
                 'mem': size(pod_mem_usage, system=iec) + " " + pod_mem_pct,
                 'mem_limit': size(pod_mem_limit, system=iec) if pod_mem_limit is not None else "N/A",}

    return pod_final, containers_final

if __name__ == "__main__":
    print(aggregate_pod_metrics('iks-extremeblue','kube-system','public-cr8a6558242f3d4cb18af6703d10b27910-alb1-b6f9688dc-dbb8q'))
    print(aggregate_pod_metrics('iks-extremeblue', 'default','binging-whale-gbapp-redismaster-76994bf95d-lkl8k'))
    # print(get_value_and_unit('100'))
