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
        self.http = urllib3.PoolManager()

        auth_header = "Basic " + base64.b64encode(
            (self._config['server']['username'] + ":" + self._config['server']['password']).encode()).decode()

        self.request_headers = {
            "Content-Type": "application/json",
            "Authorization": auth_header
        }

    def fetch_data_summary(self):
        url = self._config['server']['base_url'] + 'api/dataSummary'
        response = self.http.request('GET', url, headers=self.request_headers)
        return json.loads(response.data.decode('utf-8'))

    @staticmethod
    def collect_object_counts(response):
        metric = Metric('dhis_object_counts', 'Object counts', 'gauge')
        for k, v in response['objectCounts'].items():
            metric.add_sample('dhis_object_counts', value=v, labels={'object': k})
        return metric

    @staticmethod
    def collect_active_users(response):
        metric = Metric('dhis_active_users', 'Active users', 'gauge')
        for k, v in response['activeUsers'].items():
            metric.add_sample('activeUsers', value=v, labels={'days': k})
        return metric

    @staticmethod
    def collect_data_values_count(response):
        metric = Metric('dhis_datavalues_count', 'Count of data values', 'gauge')
        for k, v in response['dataValueCount'].items():
            metric.add_sample('dataValueCount', value=v, labels={'days': k})
        return metric

    @staticmethod
    def collect_event_count(response):
        metric = Metric('dhis_event_count', 'Count of events', 'gauge')
        for k, v in response['eventCount'].items():
            metric.add_sample('eventCount', value=v, labels={'days': k})
        return metric

    @staticmethod
    def transform_summaries_to_metrics(summaries):
        metric = Metric('dhis_metadata_integrity_checks', 'Metadata integrity checks', 'gauge')
        for k, v in summaries.items():
            metric.add_sample('dhis_metadata_integrity_checks', value=v['count'], labels={'count': k})
        return metric

    def fetch_metadata_integrity_checks(self):
        # GET /api/dataIntegrity
        try:
            url = self._config['server']['base_url'] + 'api/dataIntegrity/summary'
            response = self.http.request("GET", url, headers=self.request_headers)
            summaries =  json.loads(response.data.decode("utf-8"))
            transformed_metrics = self.transform_summaries_to_metrics(summaries)
            return transformed_metrics
        except Exception as e:
            print("Error: " + str(e))
            return None

    def collect(self):
        #Metrics from the data summary
        response = self.fetch_data_summary()
        yield self.collect_object_counts(response)
        yield self.collect_active_users(response)
        yield self.collect_data_values_count(response)
        yield self.collect_event_count(response)
        yield self.fetch_metadata_integrity_checks()

if __name__ == '__main__':

    # Usage: json_exporter.py port endpoint
    config = configparser.ConfigParser()
    config.read(sys.argv[1])
    start_http_server(int(config['server']['server_port']))
    REGISTRY.register(JsonCollector(config))
    while True: time.sleep(1)
