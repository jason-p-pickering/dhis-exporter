from prometheus_client import start_http_server, Metric, REGISTRY
import json
import sys
import time
import urllib3
import configparser
import base64


class JsonCollector(object):

    def __init__(self, params):
        self._config = params

    def collect(self):
        # Fetch the JSON
        http = urllib3.PoolManager()

        userpass = self._config['server']['username'] + ":" + self._config['server']['password']
        encoded_u = base64.b64encode(userpass.encode()).decode()

        url =  self._config['server']['base_url'] + 'api/dataSummary'
        request = http.request("GET", url, headers={"Authorization": "Basic %s" % encoded_u})

        response = json.loads(request.data.decode('utf-8'))

        # Metrics for various object types
        metric = Metric('dhis_object_counts', 'Object counts', 'gauge')
        for k, v in response['objectCounts'].items():
            metric.add_sample('dhis_object_counts', value=v, labels={'object': k})
        yield metric

        #Metrics for active users by day
        metric = Metric('dhis_active_users', 'Active users', 'gauge')
        for k, v in response['activeUsers'].items():
            metric.add_sample('activeUsers', value=v, labels={'days': k})
        yield metric


        #Metrics for count of data values by day
        metric = Metric('dhis_datavalues_count', 'Count of data values', 'gauge')
        for k, v in response['dataValueCount'].items():
            metric.add_sample('dataValueCount', value=v, labels={'days': k})
        yield metric


        #Metrics for count of data values by day
        metric = Metric('dhis_event_count', 'Count of events', 'gauge')
        for k, v in response['eventCount'].items():
            metric.add_sample('eventCount', value=v, labels={'days': k})
        yield metric

if __name__ == '__main__':

    # Usage: json_exporter.py port endpoint
    config = configparser.ConfigParser()
    config.read(sys.argv[1])
    start_http_server(int(config['server']['server_port']))
    REGISTRY.register(JsonCollector(config))
    while True: time.sleep(1)
