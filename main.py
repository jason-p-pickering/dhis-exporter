from datetime import datetime

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
        metric = Metric('dhis_summary_object_count_total', 'Object counts', 'gauge')
        for k, v in response['objectCounts'].items():
            metric.add_sample('dhis_summary_object_count_total', value=v, labels={'object': k})
        return metric

    @staticmethod
    def collect_active_users(response):
        metric = Metric('dhis_summary_active_users_count_total', 'Active users', 'gauge')
        for k, v in response['activeUsers'].items():
            metric.add_sample('dhis_summary_active_users_count_total', value=v, labels={'days': k})
        print(f"Collected active users metric: {metric}")
        return metric

    @staticmethod
    def collect_data_values_count(response):
        metric = Metric('dhis_summary_data_value_count_total', 'Count of data values', 'gauge')
        for k, v in response['dataValueCount'].items():
            metric.add_sample('dhis_summary_data_value_count', value=v, labels={'days': k})
        return metric

    @staticmethod
    def collect_event_count(response):
        metric = Metric('dhis_summary_event_count_total', 'Count of events', 'gauge')
        for k, v in response['eventCount'].items():
            metric.add_sample('dhis_summary_event_count', value=v, labels={'days': k})
        return metric

    @staticmethod
    def collect_build_info(response):
        metric = Metric('dhis_sysinfo_build_info', 'Build information', 'gauge')
        build_time = int(time.mktime(time.strptime(response['buildTime'], "%Y-%m-%dT%H:%M:%S.%f")))
        metric.add_sample('dhis_sysinfo_build_info', value=build_time,
                          labels={'version': response['version'], 'commit': response['revision']})
        print(f"Collected build info metric: {metric}")
        return metric

    @staticmethod
    def collect_analytics_partition_runtime(response):
        # lastAnalyticsTablePartitionRuntime : "00:00:42.260"
        metric = Metric('dhis_summary_analytics_partition_runtime', 'Analytics partition runtime', 'gauge')
        try:
            runtime = response['lastAnalyticsTablePartitionRuntime']
            hours, minutes, seconds = map(float, runtime.split(':'))
            total_seconds = hours * 3600 + minutes * 60 + seconds
            metric.add_sample('dhis_sysinfo_analytics_partition_runtime', value=total_seconds, labels={})
        except ValueError:
            print("Error parsing analytics partition runtime")
        return metric

    @staticmethod
    def collect_analytics_table_runtime(response):
        metric = Metric('dhis_summary_analytics_table_runtime', 'Analytics table runtime', 'gauge')
        try:
            runtime = response['lastAnalyticsTableRuntime']
            hours, minutes, seconds = map(float, runtime.split(':'))
            total_seconds = hours * 3600 + minutes * 60 + seconds
            metric.add_sample('dhis_sysinfo_analytics_table_runtime', value=total_seconds, labels={})
        except ValueError:
            print("Error parsing analytics table runtime")
        return metric

    @staticmethod
    def transform_count_to_metrics(summaries):
        count_metric = Metric('dhis_data_integrity_issues_count_total', 'Data integrity check counts', 'gauge')
        for k, v in summaries.items():
            count_metric.add_sample('dhis_data_integrity_issues_count_total', value=v['count'], labels={'check': k, 'severity': v['severity'], 'object_type': v['issuesIdType']})
        return count_metric

    @staticmethod
    def transform_percentage_to_metrics(summaries):
        metric = Metric('dhis_data_integrity_issues_percentage', 'Data integrity check percentages', 'gauge')
        for k, v in summaries.items():
                #percentage can be missing entirely, so check for this
            if 'percentage' in v:
                metric.add_sample('dhis_data_integrity_issues_percentage', value=v['percentage'], labels={'check': k, 'severity': v['severity'], 'object_type': v['issuesIdType']} )
        return metric

    @staticmethod
    def transform_duration_to_metrics(summaries):
        metric = Metric('dhis_data_integrity_issues_duration_total', 'Data integrity check durations', 'gauge')
        for k, v in summaries.items():
            start_time = datetime.fromisoformat(v['startTime'])
            end_time = datetime.fromisoformat(v['finishedTime'])
            duration = (end_time - start_time).total_seconds()
            metric.add_sample('dhis_data_integrity_issues_duration_total', value=duration,
                               labels={'check': k, 'severity': v['severity'], 'object_type': v['issuesIdType']})
        return metric

    def fetch_metadata_integrity_checks(self):
        # GET /api/dataIntegrity
        try:
            url = self._config['server']['base_url'] + 'api/dataIntegrity/summary'
            response = self.http.request("GET", url, headers=self.request_headers)
            summaries =  json.loads(response.data.decode("utf-8"))
            return summaries
        except Exception as e:
            print("Error: " + str(e))
            return None

    def fetch_system_info(self):
        # GET /api/systemSettings
        url = self._config['server']['base_url'] + 'api/system/info'
        response = self.http.request('GET', url, headers=self.request_headers)
        return json.loads(response.data.decode('utf-8'))


    def collect(self):
        #Metrics from the data summary
        response = self.fetch_data_summary()
        yield self.collect_object_counts(response)
        yield self.collect_active_users(response)
        yield self.collect_data_values_count(response)
        yield self.collect_event_count(response)
        #Get the system settings
        sys_info = self.fetch_system_info()
        print(sys_info)
        yield self.collect_build_info(sys_info)
        yield self.collect_analytics_partition_runtime(sys_info)
        yield self.collect_analytics_table_runtime(sys_info)
        #Metrics from the data integrity checks
        di_checks = self.fetch_metadata_integrity_checks()
        if di_checks:
            yield self.transform_count_to_metrics(di_checks)
            yield self.transform_percentage_to_metrics(di_checks)
            yield self.transform_duration_to_metrics(di_checks)

if __name__ == '__main__':

    # Usage: json_exporter.py port endpoint
    config = configparser.ConfigParser()
    config.read(sys.argv[1])
    start_http_server(int(config['server']['server_port']))
    REGISTRY.register(JsonCollector(config))
    while True: time.sleep(1)
