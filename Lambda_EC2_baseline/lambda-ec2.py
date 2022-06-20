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

# Read required EC2 metric name from environment variables
# (In my sample configured CPUUtilization, DatabaseConnections, FreeableMemory, FreeStorageSpace)
EC2_MetricName = os.environ['MetricName'].split(',')
MaxItems = os.environ['MaxItems']
SNS_topic_ARN = os.environ['SNS_topic_ARN']

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def is_existed_inList(target, list):
    if target in list:
        return False
    else:
        return True


def map_maxConnections(instanceSize):
    if instanceSize == 'large':
        return 1000
    if instanceSize == 'xlarge':
        return 2000
    if instanceSize == '2xlarge':
        return 3000
    if instanceSize == '4xlarge':
        return 5000
    if instanceSize == '8xlarge':
        return 10000
    if instanceSize == '12xlarge':
        return 15000
    if instanceSize == '16xlarge':
        return 20000
    if instanceSize == '24xlarge':
        return 30000
    if instanceSize == 'small':
        return 45
    if instanceSize == 'medium':
        return 90
    else:
        return 999

# def map_instanceMemory(instanceFamily, instanceSize):
#     if instanceFamily[0] == 'r':
#         if instanceSize == 'large':
#             return 16000
#         if instanceSize == 'xlarge':
#             return 32000
#         if instanceSize == '2xlarge':
#             return 64000
#         if instanceSize == '4xlarge':
#             return 128000
#         if instanceSize == '8xlarge':
#             return 256000
#         if instanceSize == '12xlarge':
#             return 384000
#         if instanceSize == '16xlarge':
#             return 512000
#         if instanceSize == '24xlarge':
#             return 768000
#         else:
#             return 999
#     elif instanceFamily[0] == 'm':
#         if instanceSize == 'large':
#             return 8000
#         if instanceSize == 'xlarge':
#             return 16000
#         if instanceSize == '2xlarge':
#             return 32000
#         if instanceSize == '4xlarge':
#             return 64000
#         if instanceSize == '8xlarge':
#             return 128000
#         if instanceSize == '12xlarge':
#             return 192000
#         if instanceSize == '16xlarge':
#             return 256000
#         if instanceSize == '24xlarge':
#             return 384000
#         else:
#             return 999
#     else:
#         return 8000


# def get_instanceFamily(instanceFamily):
#     if instanceFamily == 't2':
#         return False
#     if instanceFamily == 't3':
#         return False
#     else:
#         return True


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
    CW_filteredIterator = CW_iterator.search("MetricAlarms[?Namespace==`AWS/EC2`]")

#   Prepare target EC2 list
    EC2_client = boto3.client('ec2')
    EC2_paginator = EC2_client.get_paginator('describe_instances')
    EC2_iterator = EC2_paginator.paginate(
        PaginationConfig={
            # 最大创建EC2 CloudWatch alarms的数量
            'MaxItems': MaxItems,
            # 演示分页，最小20，最大100
            'PageSize': 100
        }
    )

#   Prepare EC2 full list
    print('------')
    print('EC2 full list:')
    EC2_rawList = []
    EC2_nameList = []
#    EC2_idList = []
    for EC2_response in EC2_iterator:
        for i in EC2_response['Reservations']:
            EC2_rawList.extend(i['Instances'])
    for dict in EC2_rawList:
        for i in dict.items():
            if i[0] == "InstanceId":
                print(i[1])
                EC2_nameList.append(i[1])
#                EC2_idList.append(i[1].split('/',1)[1])


#   Prepare EC2 ignore list: 筛选出已经创建对应监控告警的EC2数据库实例
    print('------')
    print('EC2 ignore list:')
    EC2_CPUUtilization_ignoreList = []

    for alarm in CW_filteredIterator:
#       判断已有的监控告警是否为正准备创建的监控告警
        for metric in EC2_MetricName:
            if alarm['MetricName'] == metric:
                for dimension in alarm["Dimensions"]:
                    if dimension["Name"] == "InstanceId":
                        if metric == 'CPUUtilization':
                            EC2_CPUUtilization_ignoreList.append(dimension["Value"])
                            print(metric+': '+dimension["Value"])
                        # elif metric == 'DatabaseConnections':
                        #     EC2_DatabaseConnections_ignoreList.append(dimension["Value"])
                        #     print(metric+': '+dimension["Value"])
                        # elif metric == 'FreeableMemory':
                        #     EC2_FreeableMemory_ignoreList.append(dimension["Value"])
                        #     print(metric+': '+dimension["Value"])
                        # else:
                        #     EC2_FreeStorageSpace_ignoreList.append(dimension["Value"])
                        #     print(metric+': '+dimension["Value"])


#   Drop CloudWatch alarm cascade:
    print('------')
    for metric in EC2_MetricName:
        for cw in EC2_CPUUtilization_ignoreList:
            if is_existed_inList(cw, EC2_nameList) & (metric == 'CPUUtilization'):
                print('Dropping CloudWatch alarm "EC2_'+metric+'" for: '+cw)
                CWalarms = CW_client.delete_alarms(
                    AlarmNames=['EC2_'+metric+'-'+cw]
                )
                print('Dropped CloudWatch alarm "EC2_'+metric+'" for: '+cw)



#   Create customized CloudWatch alarms auto:
    print ('')
    for ec2_record in EC2_rawList:
        #       预先定义SNS topic ARN，不同的CloudWatch告警通知会发送到不同的SNS topic
        ec2_name = ec2_record['InstanceId']
        print('------')
        #       判断是否为EC2，且未创建CPU监控告警
        if is_existed_inList(ec2_name, EC2_CPUUtilization_ignoreList):
            print('------')
            print('EC2 name: ' + ec2_name)
            print('Creating CloudWatch alarm "EC2_CPUUtilization" for: ' + ec2_name)
            #           创建监控告警
            CWalarms = CW_client.put_metric_alarm(
                AlarmName='EC2_CPUUtilization-' + ec2_name,
                AlarmDescription='Auto-created customized CloudWatch Alarm <EC2_CPUUtilization>',
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
                MetricName='CPUUtilization',
                Namespace="AWS/EC2",
                Statistic='Maximum',
                # 'SampleCount'|'Average'|'Sum'|'Minimum'|'Maximum'
                #                ExtendedStatistic='p100',
                Dimensions=[
                    {
                        'Name': 'InstanceId',
                        'Value': ec2_name
                    },
                ],
                Period=60,
                #                Unit='Seconds',
                # 'Seconds'|'Microseconds'|'Milliseconds'|'Bytes'|'Kilobytes'|'Megabytes'|'Gigabytes'|'Terabytes'|'Bits'|'Kilobits'|'Megabits'|'Gigabits'|'Terabits'|'Percent'|'Count'|'Bytes/Second'|'Kilobytes/Second'|'Megabytes/Second'|'Gigabytes/Second'|'Terabytes/Second'|'Bits/Second'|'Kilobits/Second'|'Megabits/Second'|'Gigabits/Second'|'Terabits/Second'|'Count/Second'|'None'
                EvaluationPeriods=3,
                DatapointsToAlarm=2,
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
                #                               ]
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
                        'Key': 'EC2_CPUUtilization',
                        'Value': 'autocreated'
                    },
                ],
                #                ThresholdMetricId='string'
            )

            #           为该EC2数据库标记CWalarm-CPUUtilization标签
            EC2_tags = EC2_client.create_tags(
                #DryRun=True,
                ResourceName=ec2_record['InstanceId'],
                Tags=[
                    {
                        'Key': 'CWalarm-CPUUtilization',
                        'Value': 'enabled'
                    },
                ]
            )
            print('Added tag "CWalarm-CPUUtilization" to: ' + ec2_name)

            print('Created CloudWatch alarm "EC2_CPUUtilization" for: ' + ec2_name)
            print()
        else:
            print('No CloudWatch cpu alarm created for: ' + ec2_name)



    return {
        'statusCode': 200,
        'body': json.dumps('Mission Complete!')
    }


#run_command('/var/task/aws --version')
#run_command('ls -l')

