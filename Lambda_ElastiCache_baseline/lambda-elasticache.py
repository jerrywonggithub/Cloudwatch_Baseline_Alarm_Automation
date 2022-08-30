from __future__ import print_function
from botocore.exceptions import ClientError
from base64 import b64decode
import subprocess
import logging
import json
import os
import requests
import json
import boto3


# Read required ElastiCache metric name from environment variables
# (In my sample configured EngineCPUUtilization, DatabaseMemoryUsagePercentage)
EC_MetricName = os.environ['MetricName'].split(',')
MaxItems = os.environ['MaxItems']
SNS_topic_ARN = os.environ['SNS_topic_ARN']

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def is_existed_inList(target, list):
    if target in list:
        return False
    else:
        return True


#def map_maxVal(instanceSize): 
#    if instanceSize == 'large':
#        return 1000
#    if instanceSize == 'xlarge':
#        return 2000
#    if instanceSize == '2xlarge':
#        return 3000
#    if instanceSize == '4xlarge':
#        return 5000
#    if instanceSize == '8xlarge':
#        return 10000
#    if instanceSize == '12xlarge':
#        return 15000
#    if instanceSize == '16xlarge':
#        return 20000
#    if instanceSize == '24xlarge':
#        return 30000
#    if instanceSize == 'small':
#        return 45
#    if instanceSize == 'medium':
#        return 90
#    else:
#        return 999


def get_instanceFamily(instanceFamily):
    if instanceFamily == 't2':
        return False
    if instanceFamily == 't3':
        return False
    else:
        return True


# The 'handler' Python function is the entry point for AWS Lambda function invocations.
def lambda_handler(event, context):


    stsClient = boto3.client('sts')
    accountId = stsClient.get_caller_identity().get('Account')
    print('------')
    print('Account: '+accountId)


#   List metrics through the pagination interface
    CW_client = boto3.client('cloudwatch')
    CW_paginator = CW_client.get_paginator('describe_alarms')
    CW_iterator = CW_paginator.paginate()
    CW_filteredIterator = CW_iterator.search("MetricAlarms[?Namespace==`AWS/ElastiCache`]")
    

#   Prepare target ElastiCache list
    EC_client = boto3.client('elasticache')
    EC_paginator = EC_client.get_paginator('describe_cache_clusters')
    EC_iterator = EC_paginator.paginate(
        PaginationConfig={
            # 最大创建ElastiCache的CloudWatch alarms数量
            'MaxItems': MaxItems,
            # 演示分页，最小20，最大100
            'PageSize': 100
        }
    )
    EC_replicaGroup_paginator = EC_client.get_paginator('describe_replication_groups')
    EC_replicaGroup_iterator = EC_replicaGroup_paginator.paginate(
        PaginationConfig={
            # 最大创建ElastiCache的CloudWatch alarms数量
            'MaxItems': 10000,
            # 演示分页，最小20，最大100
            'PageSize': 100
        }
    )


#   Prepare ElastiCache Replication Group status list
    EC_replicaGroup_List = []
    for EC_replicaGroup_resp in EC_replicaGroup_iterator:
        EC_replicaGroup_List.append(EC_replicaGroup_resp['ReplicationGroups'])


    def is_cluster_enabled(cluster):
        for d in EC_replicaGroup_List:
            for i in d:
                for c in i['NodeGroups']:
                    for m in c['NodeGroupMembers']:
                        if m['CacheClusterId'] == cluster:
                            return i['ClusterEnabled']


#   Prepare ElastiCache clusters full list
    print('------')
    print('ElastiCache full list:')
    EC_rawList = []
    EC_nameList = []
    EC_idList = []
    for EC_response in EC_iterator:
        EC_rawList.extend(EC_response['CacheClusters'])
        for EC_node in EC_response['CacheClusters']:
            EC_nameList.append(EC_node['CacheClusterId'])
            EC_idList.append(EC_node['ARN'])
    print(EC_nameList)
    print(EC_idList)


#   Prepare ElastiCache ignore list: 筛选出已经创建对应监控告警的ElastiCache集群
    print('------')
    print('ElastiCache ignore list:')
#    alarm = cloudwatch.Alarm('name')
    EC_EngineCPUUtilization_ignoreList = []
    EC_DatabaseMemoryUsagePercentage_ignoreList = []
    for alarm in CW_filteredIterator:
#       判断已有的监控告警是否为正准备创建的监控告警
        for metric in EC_MetricName:
            if alarm['MetricName'] == metric:
                for dimension in alarm["Dimensions"]:
                    if dimension["Name"] == "CacheClusterId":
                        if metric == 'EngineCPUUtilization':
                            EC_EngineCPUUtilization_ignoreList.append(dimension["Value"])
                            print(metric + ': ' + dimension["Value"])
                        elif metric == 'DatabaseMemoryUsagePercentage':
                            EC_DatabaseMemoryUsagePercentage_ignoreList.append(dimension["Value"])
                            print(metric + ': ' + dimension["Value"])


#   Drop CloudWatch alarm cascade: 
    print('------')
    for metric in EC_MetricName:
        for cw in EC_EngineCPUUtilization_ignoreList:
            if is_existed_inList(cw, EC_nameList) & (metric == 'EngineCPUUtilization'):
                print('Dropping CloudWatch alarm "EC_'+metric+'" for: '+cw)
                CWalarms = CW_client.delete_alarms(
                    AlarmNames=['EC_'+metric+'-'+cw]
                )
                print('Dropped CloudWatch alarm "ES_'+metric+'" for: '+cw)
        for cw in EC_DatabaseMemoryUsagePercentage_ignoreList:
            if is_existed_inList(cw, EC_nameList) & (metric == 'DatabaseMemoryUsagePercentage'):
                print('Dropping CloudWatch alarm "EC_'+metric+'" for: '+cw)
                CWalarms = CW_client.delete_alarms(
                    AlarmNames=['EC_'+metric+'-'+cw]
                )
                print('Dropped CloudWatch alarm "ES_'+metric+'" for: '+cw)


#   Create customized CloudWatch alarms auto: 
    print ('')
#   预先定义SNS topic ARN，不同的CloudWatch告警通知会发送到不同的SNS topic
    for ec_id in EC_idList:
        ec_name = ec_id.split(':',6)[6]
        print('------')
#       判断是否并未创建对应的监控告警
        if is_existed_inList(ec_name, EC_EngineCPUUtilization_ignoreList) & (EC_rawList[0]['Engine'] == 'redis'):
#       支持使用is_cluster_enabled()函数，判断该ElastiCache集群是否启用集群模式
#       该函数的返回值有3种：True / False / None分别表示已启用集群模式、未启用集群模式、未启用Replication Group(单节点实例)
#       if is_existed_inList(ec_name, EC_ignoreList):  #  & (str(is_cluster_enabled(ec_name))=='True')
#            print('EC name: '+ec_name)
#            print('------')
#            获取该EC集群节点对应的实例规格，查询map_maxVal mapping所对应的该项阈值指定的最大允许值
#            for dict in EC_rawList:
#                for i in dict:
#                    print('CacheClusterId: '+i['CacheClusterId'])
#                    if i['CacheClusterId'] == ec_name:
#                        maxVal = map_maxVal(i['CacheNodeType'].split('.',2)[2])
#                        print('maxVal = '+str(maxVal))
#           创建监控告警
            CWalarms = CW_client.put_metric_alarm(
                AlarmName='EC_EngineCPUUtilization-' + ec_name,
                AlarmDescription='Auto-created customized CloudWatch Alarm <EC_EngineCPUUtilization>',
                ActionsEnabled=True,
#                OKActions=[
#                    'string',
#                ],
                AlarmActions=[
                    # 示例，发送到SNS
                    SNS_topic_ARN
                ], 
#                InsufficientDataActions=[
#                    'string',
#                ],
                MetricName='EngineCPUUtilization',
                Namespace="AWS/ElastiCache",
                Statistic='Maximum',
                # 'SampleCount'|'Average'|'Sum'|'Minimum'|'Maximum'
#                ExtendedStatistic='p100',
#                ElastiCache支持cluster级别的监控:
               Dimensions = [
                  {
                       'Name': 'DomainName',
                       'Value': ec_name
                   },{
                       'Name': 'ClientId',
                       'Value': accountId,
                      }
               ],
#               ElastiCache支持cache nodes级别的监控:
#                Dimensions = node_record,
#                print(ec_name['LoadBalancerArn'].split('/',1)[1])
                Period=60,
#                Unit='Seconds',
                # 'Seconds'|'Microseconds'|'Milliseconds'|'Bytes'|'Kilobytes'|'Megabytes'|'Gigabytes'|'Terabytes'|'Bits'|'Kilobits'|'Megabits'|'Gigabits'|'Terabits'|'Percent'|'Count'|'Bytes/Second'|'Kilobytes/Second'|'Megabytes/Second'|'Gigabytes/Second'|'Terabytes/Second'|'Bits/Second'|'Kilobits/Second'|'Megabits/Second'|'Gigabits/Second'|'Terabits/Second'|'Count/Second'|'None'
                EvaluationPeriods=60,
                DatapointsToAlarm=20,
                Threshold=75,
                ComparisonOperator='GreaterThanThreshold',
                # 'GreaterThanOrEqualToThreshold'|'GreaterThanThreshold'|'LessThanThreshold'|'LessThanOrEqualToThreshold'|'LessThanLowerOrGreaterThanUpperThreshold'|'LessThanLowerThreshold'|'GreaterThanUpperThreshold'
                TreatMissingData='ignore',
#                EvaluateLowSampleCountPercentile='ignore',
#                Metrics=[
#                    {
#                        'Id': 'string',
#                        'MetricStat': {
#                            'Metric': {
#                                'Namespace': 'string',
#                                'MetricName': 'string',
#                                'Dimensions': [
#                                    {
#                                        'Name': 'string',
#                                        'Value': 'string'
#                                    },
#                                ]
#                            },
#                            'Period': 123,
#                            'Stat': 'string',
#                            'Unit': 'Seconds'|'Microseconds'|'Milliseconds'|'Bytes'|'Kilobytes'|'Megabytes'|'Gigabytes'|'Terabytes'|'Bits'|'Kilobits'|'Megabits'|'Gigabits'|'Terabits'|'Percent'|'Count'|'Bytes/Second'|'Kilobytes/Second'|'Megabytes/Second'|'Gigabytes/Second'|'Terabytes/Second'|'Bits/Second'|'Kilobits/Second'|'Megabits/Second'|'Gigabits/Second'|'Terabits/Second'|'Count/Second'|'None'
#                        },
#                        'Expression': 'string',
#                        'Label': 'string',
#                        'ReturnData': True|False,
#                        'Period': 123
#                    },
#                ],
                Tags=[
                    {
                        'Key': 'EC_EngineCPUUtilization',
                        'Value': 'autocreated'
                    },
                ],
#                ThresholdMetricId='string'
            )

#           为该EC集群标记CWalarm-DatabaseMemoryUsagePercentage标签
            EC_tags = EC_client.add_tags_to_resource(
                ResourceName = ec_id,
                Tags = [
                    {
                        'Key': 'CWalarm-EngineCPUUtilization',
                        'Value': 'enabled'
                    },
                ]
            )
            print('Added tag "CWalarm-EngineCPUUtilization" to: ' + ec_id)
                    
            print('Created CloudWatch alarm "EC_EngineCPUUtilization" for Cluster <'+ec_name+'>')
            print()
        else: 
            print('No CloudWatch alarm created for: '+ec_name)

    for ec_id in EC_idList:
        ec_name = ec_id.split(':', 6)[6]
        print('------')
    #       判断是否并未创建对应的监控告警
        if is_existed_inList(ec_name, EC_DatabaseMemoryUsagePercentage_ignoreList) & (EC_rawList[0]['Engine'] == 'redis'):
            #       支持使用is_cluster_enabled()函数，判断该ElastiCache集群是否启用集群模式
            #       该函数的返回值有3种：True / False / None分别表示已启用集群模式、未启用集群模式、未启用Replication Group(单节点实例)
            #       if is_existed_inList(ec_name, EC_ignoreList):  #  & (str(is_cluster_enabled(ec_name))=='True')
            #            print('EC name: '+ec_name)
            #            print('------')
            #            获取该EC集群节点对应的实例规格，查询map_maxVal mapping所对应的该项阈值指定的最大允许值
            #            for dict in EC_rawList:
            #                for i in dict:
            #                    print('CacheClusterId: '+i['CacheClusterId'])
            #                    if i['CacheClusterId'] == ec_name:
            #                        maxVal = map_maxVal(i['CacheNodeType'].split('.',2)[2])
            #                        print('maxVal = '+str(maxVal))
            #           创建监控告警
            CWalarms = CW_client.put_metric_alarm(
                AlarmName='EC_DatabaseMemoryUsagePercentage-' + ec_name,
                AlarmDescription='Auto-created customized CloudWatch Alarm <EC_DatabaseMemoryUsagePercentage>',
                ActionsEnabled=True,
                #                OKActions=[
                #                    'string',
                #                ],
                AlarmActions=[
                    # 示例，发送到SNS
                    SNS_topic_ARN
                ],
                #                InsufficientDataActions=[
                #                    'string',
                #                ],
                MetricName='DatabaseMemoryUsagePercentage',
                Namespace="AWS/ElastiCache",
                Statistic='Maximum',
                # 'SampleCount'|'Average'|'Sum'|'Minimum'|'Maximum'
                #                ExtendedStatistic='p100',
                #                ElastiCache支持cluster级别的监控:
                               Dimensions = [
                                  {
                                       'Name': 'DomainName',
                                       'Value': ec_name
                                   },{
                                       'Name': 'ClientId',
                                       'Value': accountId,
                                      }
                               ],
                #               ElastiCache支持cache nodes级别的监控:
                #                Dimensions = node_record,
                #                print(ec_name['LoadBalancerArn'].split('/',1)[1])
                Period=60,
                #                Unit='Seconds',
                # 'Seconds'|'Microseconds'|'Milliseconds'|'Bytes'|'Kilobytes'|'Megabytes'|'Gigabytes'|'Terabytes'|'Bits'|'Kilobits'|'Megabits'|'Gigabits'|'Terabits'|'Percent'|'Count'|'Bytes/Second'|'Kilobytes/Second'|'Megabytes/Second'|'Gigabytes/Second'|'Terabytes/Second'|'Bits/Second'|'Kilobits/Second'|'Megabits/Second'|'Gigabits/Second'|'Terabits/Second'|'Count/Second'|'None'
                EvaluationPeriods=60,
                DatapointsToAlarm=20,
                Threshold=80,
                ComparisonOperator='GreaterThanThreshold',
                # 'GreaterThanOrEqualToThreshold'|'GreaterThanThreshold'|'LessThanThreshold'|'LessThanOrEqualToThreshold'|'LessThanLowerOrGreaterThanUpperThreshold'|'LessThanLowerThreshold'|'GreaterThanUpperThreshold'
                TreatMissingData='ignore',
                #                EvaluateLowSampleCountPercentile='ignore',
                #                Metrics=[
                #                    {
                #                        'Id': 'string',
                #                        'MetricStat': {
                #                            'Metric': {
                #                                'Namespace': 'string',
                #                                'MetricName': 'string',
                #                                'Dimensions': [
                #                                    {
                #                                        'Name': 'string',
                #                                        'Value': 'string'
                #                                    },
                #                                ]
                #                            },
                #                            'Period': 123,
                #                            'Stat': 'string',
                #                            'Unit': 'Seconds'|'Microseconds'|'Milliseconds'|'Bytes'|'Kilobytes'|'Megabytes'|'Gigabytes'|'Terabytes'|'Bits'|'Kilobits'|'Megabits'|'Gigabits'|'Terabits'|'Percent'|'Count'|'Bytes/Second'|'Kilobytes/Second'|'Megabytes/Second'|'Gigabytes/Second'|'Terabytes/Second'|'Bits/Second'|'Kilobits/Second'|'Megabits/Second'|'Gigabits/Second'|'Terabits/Second'|'Count/Second'|'None'
                #                        },
                #                        'Expression': 'string',
                #                        'Label': 'string',
                #                        'ReturnData': True|False,
                #                        'Period': 123
                #                    },
                #                ],
                Tags=[
                    {
                        'Key': 'EC_DatabaseMemoryUsagePercentage',
                        'Value': 'autocreated'
                    },
                ],
                #                ThresholdMetricId='string'
            )

            #           为该EC集群标记CWalarm-DatabaseMemoryUsagePercentage标签
            EC_tags = EC_client.add_tags_to_resource(
                ResourceName=ec_id,
                Tags=[
                    {
                        'Key': 'CWalarm-DatabaseMemoryUsagePercentage',
                        'Value': 'enabled'
                    },
                ]
            )
            print('Added tag "CWalarm-DatabaseMemoryUsagePercentage" to: ' + ec_name)

            print('Created CloudWatch alarm "EC_DatabaseMemoryUsagePercentage" for Cluster <' + ec_name + '>')
            print()


    return {
        'statusCode': 200,
        'body': json.dumps('Mission Complete!')
    }


#run_command('/var/task/aws --version')
#run_command('ls -l')