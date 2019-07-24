import requests
import k8s_api, k8s_config
from kubernetes import client, config
from hurry.filesize import size, iec
from si_prefix import si_format

k8s_config.update_available_clusters()

def get_value_and_unit(value_string):
    """
    Takes a string and splits it up, returning the number part and the unit part
    :param value_string: examples: "100Mi", "8", "500n" (does not need to include unit)
    :return: (int) numerical value, (str) unit, which is empty string for no unit
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
    :param value: (int) Numerical value
    :param unit: (str) unit, where empty string denotes base unit
    :return: (int) the value in base unit
    """
    POWERS_BY_UNIT = {'n': -3,
                        'm': -1,
                        '': 0,
                        'K': 1, 'Ki': 1,
                        'M': 2, 'Mi': 2,
                        'G': 3, 'Gi': 3,
                        'T': 4, 'Ti': 4,
                        'P': 5, 'Pi': 5,
                        'E': 6, 'Ei': 6}

    if unit in ['n','m','','K','M','G','T','P','E']: # normal si system prefixes
        base = 1000
    else: # iec system
        base = 1024
    return value * (base ** POWERS_BY_UNIT[unit])

def aggregate_pod_metrics(cluster_name, namespace, pod_name):
    """
    Get the pod and container compute resources
    :param cluster_name: (str) pod cluster
    :param namespace: (str) pod namespace
    :param pod_name: (str) pod name
    :return: ((Dict) pod_final, (Dict) containers_final)
                where pod_final = {'cpu': <value>, 'memory': <value>},
                and containers_final is Dict(<container_name>, {'cpu': <value>, 'memory': <value>}), or None if no container info
    """

    def get_pod_container_usage(cluster_name, namespace, pod_name):
        """
        Returns Dict(container_name, (cpu, mem)) for current container resource usage, or None if http request failed
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
        Returns Dict(container_name, (cpu, mem)) for container resource limits
            - None values for cpu and mem mean no limits were specified
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
            limits_by_container[name] = (ct_cpu_limit, ct_mem_limit)

        return limits_by_container

    # get current container usage and limits
    container_limits = get_pod_container_limits(cluster_name,namespace,pod_name)
    container_usage = get_pod_container_usage(cluster_name,namespace,pod_name)
    if container_usage is None: # no container usage info
        return {'cpu': None, 'memory': None}, None

    # initialize variables used to keep cumulative sum
    pod_cpu_usage = 0
    pod_mem_usage = 0
    pod_cpu_limit = None if None in [container_limits[ct][0] for ct in container_limits] else 0
    pod_mem_limit = None if None in [container_limits[ct][1] for ct in container_limits] else 0

    containers_final = {}
    for ct_name in container_usage.keys():
        ct_cpu_usage, ct_mem_usage = container_usage[ct_name]
        ct_cpu_limit, ct_mem_limit = container_limits[ct_name]

        ct_cpu_pct = ""
        ct_mem_pct = ""

        # get container cpu usage value and add onto pod cpu usage
        value, unit = get_value_and_unit(ct_cpu_usage)
        ct_cpu_usage_value = convert_to_base_unit(value, unit)
        pod_cpu_usage += ct_cpu_usage_value

        if ct_cpu_limit is not None:
            # calculate percentage (current/limit) and return the formatted string
            value, unit = get_value_and_unit(ct_cpu_limit)
            limit_value = convert_to_base_unit(value, unit)
            if pod_cpu_limit is not None:
                pod_cpu_limit += limit_value

            ct_cpu_pct = "(" + str(round(ct_cpu_usage_value / limit_value * 100)) + "%)"

        # same process for memory
        value, unit = get_value_and_unit(ct_mem_usage)
        ct_mem_usage_value = convert_to_base_unit(value, unit)
        pod_mem_usage += ct_mem_usage_value

        if ct_mem_limit is not None:
            value, unit = get_value_and_unit(ct_mem_limit)
            limit_value = convert_to_base_unit(value, unit)
            if pod_mem_limit is not None:
                pod_mem_limit += limit_value

            ct_mem_pct = "(" + str(round(ct_mem_usage_value / limit_value * 100)) + "%)"

        containers_final[ct_name] = {'cpu': ct_cpu_usage + " " + ct_cpu_pct, 'memory': ct_mem_usage + " " + ct_mem_pct}

    # calculate pod percentages
    pod_cpu_pct = ""
    pod_mem_pct = ""
    if pod_cpu_limit is not None:
        pod_cpu_pct = "(" + str(round(pod_cpu_usage / pod_cpu_limit * 100)) + "%)"
    if pod_mem_limit is not None:
        pod_mem_pct = "(" + str(round(pod_mem_usage / pod_mem_limit * 100)) + "%)"

    pod_final = {'cpu': si_format(pod_cpu_usage, precision=0, format_str='{value}{prefix}') + " " + pod_cpu_pct,
                 'memory': size(pod_mem_usage, system=iec) + " " + pod_mem_pct}

    return pod_final, containers_final

if __name__ == "__main__":
    # print(aggregate_pod_metrics('c2-e-us-east-containers-cloud-ibm-com:31140','ibm-system','ibm-cloud-provider-ip-169-47-179-226-777f4fbc8-mjwl5'))
    print(aggregate_pod_metrics('mycluster','default','busybox'))
    # print(get_value_and_unit('100'))