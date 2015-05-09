from django.conf import settings
import requests
import logging
import time

graphite_api = settings.GRAPHITE_API
user = settings.GRAPHITE_USER
password = settings.GRAPHITE_PASS
graphite_from = settings.GRAPHITE_FROM
auth = (user, password)


def get_data(target_pattern, mins_to_check):
    until_epoch = int(time.time())
    # calculate epoch time which is 59 seconds of last minutes
    until_epoch = until_epoch - (until_epoch % 60) - 1
    from_epoch = until_epoch - mins_to_check * 60
    resp = requests.get(
        graphite_api + 'render', auth=auth,
        params={
            'target': target_pattern,
            'format': 'json',
            'from': from_epoch,
            'until': until_epoch
        }
    )
    resp.raise_for_status()
    return resp.json


def get_matching_metrics(pattern):
    print 'Getting metrics matching %s' % pattern
    resp = requests.get(
        graphite_api + 'metrics/find/', auth=auth,
        params={
            'query': pattern,
            'format': 'completer'
        },
        headers={
            'accept': 'application/json'
        }
    )
    resp.raise_for_status()
    return resp.json


def get_all_metrics(limit=None):
    """Grabs all metrics by navigating find API recursively"""
    metrics = []

    def get_leafs_of_node(nodepath):
        for obj in get_matching_metrics(nodepath)['metrics']:
            if int(obj['is_leaf']) == 1:
                metrics.append(obj['path'])
            else:
                get_leafs_of_node(obj['path'])
    get_leafs_of_node('')
    return metrics


def parse_metric(metric, mins_to_check=5):
    """
    Returns dict with:
    - num_series_with_data: Number of series with data
    - num_series_no_data: Number of total series
    - max
    - min
    - average_value
    """
    ret = {
        'num_series_with_data': 0,
        'num_series_no_data': 0,
        'error': None,
        'all_values': [],
        'raw': ''
    }
    try:
        data = get_data(metric, mins_to_check)
    except requests.exceptions.RequestException, e:
        ret['error'] = 'Error getting data from Graphite: %s' % e
        ret['raw'] = ret['error']
        logging.error('Error getting data from Graphite: %s' % e)
        return ret
    all_values = []
    for target in data:
        values = [float(t[0])
                  for t in target['datapoints'] if t[0] is not None]
        if values:
            ret['num_series_with_data'] += 1
        else:
            ret['num_series_no_data'] += 1
        all_values.extend(values)
    if all_values:
        ret['max'] = max(all_values)
        ret['min'] = min(all_values)
        ret['average_value'] = sum(all_values) / len(all_values)
    ret['all_values'] = all_values
    ret['raw'] = data
    return ret

