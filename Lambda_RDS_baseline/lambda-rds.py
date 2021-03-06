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

# Read required RDS metric name from environment variables
# (In my sample configured CPUUtilization, DatabaseConnections, FreeableMemory, FreeStorageSpace)
# RDS_MetricName = os.environ['MetricName'].split(',')
RDS_MetricName = ['CPUUtilization','DatabaseConnections','FreeableMemory','FreeStorageSpace']
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
    CW_filteredIterator = CW_iterator.search("MetricAlarms[?Namespace==`AWS/RDS`]")

#   Prepare target RDS list
    RDS_client = boto3.client('rds')
    RDS_paginator = RDS_client.get_paginator('describe_db_instances')
    RDS_iterator = RDS_paginator.paginate(
        PaginationConfig={
            # ????????????RDS CloudWatch alarms?????????
            'MaxItems': MaxItems,
            # ?????????????????????20?????????100
            'PageSize': 100
        }
    )

#   Prepare RDS full list
    print('------')
    print('RDS full list:')
    RDS_rawList = []
    RDS_nameList = []
#    RDS_idList = []
    for RDS_response in RDS_iterator:
        RDS_rawList.extend(RDS_response['DBInstances'])
    for dict in RDS_rawList:
        for i in dict.items():
            if i[0] == "DBInstanceIdentifier":
                print(i[1])
                RDS_nameList.append(i[1])
#                RDS_idList.append(i[1].split('/',1)[1])


#   Prepare RDS ignore list: ??????????????????????????????????????????RDS???????????????
    print('------')
    print('RDS ignore list:')
    RDS_CPUUtilization_ignoreList = []
    RDS_DatabaseConnections_ignoreList = []
    RDS_FreeableMemory_ignoreList = []
    RDS_FreeStorageSpace_ignoreList = []
    for alarm in CW_filteredIterator:
#       ??????????????????????????????????????????????????????????????????
        for metric in RDS_MetricName:
            if alarm['MetricName'] == metric:
                for dimension in alarm["Dimensions"]:
                    if dimension["Name"] == "DBInstanceIdentifier":
                        if metric == 'CPUUtilization':
                            RDS_CPUUtilization_ignoreList.append(dimension["Value"])
                            print(metric+': '+dimension["Value"])
                        elif metric == 'DatabaseConnections':
                            RDS_DatabaseConnections_ignoreList.append(dimension["Value"])
                            print(metric+': '+dimension["Value"])
                        elif metric == 'FreeableMemory':
                            RDS_FreeableMemory_ignoreList.append(dimension["Value"])
                            print(metric+': '+dimension["Value"])
                        else:
                            RDS_FreeStorageSpace_ignoreList.append(dimension["Value"])
                            print(metric+': '+dimension["Value"])


#   Drop CloudWatch alarm cascade:
    print('------')
    for metric in RDS_MetricName:
        for cw in RDS_CPUUtilization_ignoreList:
            if is_existed_inList(cw, RDS_nameList) & (metric == 'CPUUtilization'):
                print('Dropping CloudWatch alarm "RDS_'+metric+'" for: '+cw)
                CWalarms = CW_client.delete_alarms(
                    AlarmNames=['RDS_'+metric+'-'+cw]
                )
                print('Dropped CloudWatch alarm "RDS_'+metric+'" for: '+cw)
        for cw in RDS_DatabaseConnections_ignoreList:
            if is_existed_inList(cw, RDS_nameList) & (metric == 'DatabaseConnections'):
                print('Dropping CloudWatch alarm "RDS_'+metric+'" for: '+cw)
                CWalarms = CW_client.delete_alarms(
                    AlarmNames=['RDS_'+metric+'-'+cw]
                )
                print('Dropped CloudWatch alarm "RDS_'+metric+'" for: '+cw)
        for cw in RDS_FreeableMemory_ignoreList:
            if is_existed_inList(cw, RDS_nameList) & (metric == 'FreeableMemory'):
                print('Dropping CloudWatch alarm "RDS_'+metric+'" for: '+cw)
                CWalarms = CW_client.delete_alarms(
                    AlarmNames=['RDS_'+metric+'-'+cw]
                )
                print('Dropped CloudWatch alarm "RDS_'+metric+'" for: '+cw)
        for cw in RDS_FreeStorageSpace_ignoreList:
            if is_existed_inList(cw, RDS_nameList) & (metric == 'FreeStorageSpace'):
                print('Dropping CloudWatch alarm "RDS_'+metric+'" for: '+cw)
                CWalarms = CW_client.delete_alarms(
                    AlarmNames=['RDS_'+metric+'-'+cw]
                )
                print('Dropped CloudWatch alarm "RDS_'+metric+'" for: '+cw)


#   Create customized CloudWatch alarms auto:
    print ('')
    for rds_record in RDS_rawList:
        #       ????????????SNS topic ARN????????????CloudWatch?????????????????????????????????SNS topic
        rds_name = rds_record['DBInstanceArn'].split(':', 6)[6]
        print('------')
        #       ???????????????MySQL????????????????????????CPU????????????
        if is_existed_inList(rds_name, RDS_CPUUtilization_ignoreList) & (RDS_rawList[0]['Engine'] == 'mysql'):
            print('------')
            print('RDS name: ' + rds_name)
            print('Creating CloudWatch alarm "RDS_CPUUtilization" for: ' + rds_name)
            #           ??????????????????
            CWalarms = CW_client.put_metric_alarm(
                AlarmName='RDS_CPUUtilization-' + rds_name,
                AlarmDescription='Auto-created customized CloudWatch Alarm <RDS_CPUUtilization>',
                ActionsEnabled=True,
                #                OKActions=[
                #                    'string',
                #                ],
                AlarmActions=[
                    # ??????????????????SNS
                    SNS_topic_ARN
                ],
                #                InsufficientDataActions=[
                #                    'string',
                #                ],
                MetricName='CPUUtilization',
                Namespace="AWS/RDS",
                Statistic='Maximum',
                # 'SampleCount'|'Average'|'Sum'|'Minimum'|'Maximum'
                #                ExtendedStatistic='p100',
                Dimensions=[
                    {
                        'Name': 'DBInstanceIdentifier',
                        'Value': rds_name
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
                        'Key': 'RDS_CPUUtilization',
                        'Value': 'autocreated'
                    },
                ],
                #                ThresholdMetricId='string'
            )

            #           ??????RDS???????????????CWalarm-CPUUtilization??????
            RDS_tags = RDS_client.add_tags_to_resource(
                ResourceName=rds_record['DBInstanceArn'],
                Tags=[
                    {
                        'Key': 'CWalarm-CPUUtilization',
                        'Value': 'enabled'
                    },
                ]
            )
            print('Added tag "CWalarm-CPUUtilization" to: ' + rds_name)

            print('Created CloudWatch alarm "RDS_CPUUtilization" for: ' + rds_name)
            print()
        else:
            print('No CloudWatch cpu alarm created for: ' + rds_name)

    for rds_record in RDS_rawList:
#       ????????????SNS topic ARN????????????CloudWatch?????????????????????????????????SNS topic
        rds_name = rds_record['DBInstanceArn'].split(':', 6)[6]
        print('------')
#       ???????????????MySQL?????????????????????????????????????????????
        if is_existed_inList(rds_name, RDS_DatabaseConnections_ignoreList) & (RDS_rawList[0]['Engine'] == 'mysql'):
            print('------')
            print('RDS name: '+rds_name)
            print('Creating CloudWatch alarm "RDS_DatabaseConnections" for: '+rds_name)
#           ?????????RDS???????????????????????????????????????map_maxConnections mapping????????????max_connections
            for dict in RDS_rawList:
                if dict["DBInstanceIdentifier"] == rds_name:
                    max_connections = map_maxConnections(dict["DBInstanceClass"].split('.',2)[2])
                    print('max_connections = '+str(max_connections))
#           ??????????????????
            CWalarms = CW_client.put_metric_alarm(
                AlarmName='RDS_DatabaseConnections-'+rds_name,
                AlarmDescription='Auto-created customized CloudWatch Alarm <RDS_DatabaseConnections>',
                ActionsEnabled=True,
#                OKActions=[
#                    'string',
#                ],
                AlarmActions=[
                    # ??????????????????SNS
                    SNS_topic_ARN
                ],
#                InsufficientDataActions=[
#                    'string',
#                ],
                MetricName='DatabaseConnections',
                Namespace="AWS/RDS",
                Statistic='Maximum',
                # 'SampleCount'|'Average'|'Sum'|'Minimum'|'Maximum'
#                ExtendedStatistic='p100',
                Dimensions=[
                    {
                        'Name': 'DBInstanceIdentifier',
                        'Value': rds_name
                    },
                ],
                Period=60,
#                Unit='Seconds',
                # 'Seconds'|'Microseconds'|'Milliseconds'|'Bytes'|'Kilobytes'|'Megabytes'|'Gigabytes'|'Terabytes'|'Bits'|'Kilobits'|'Megabits'|'Gigabits'|'Terabits'|'Percent'|'Count'|'Bytes/Second'|'Kilobytes/Second'|'Megabytes/Second'|'Gigabytes/Second'|'Terabytes/Second'|'Bits/Second'|'Kilobits/Second'|'Megabits/Second'|'Gigabits/Second'|'Terabits/Second'|'Count/Second'|'None'
                EvaluationPeriods=3,
                DatapointsToAlarm=2,
                Threshold=max_connections,
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
                        'Key': 'RDS_DatabaseConnections',
                        'Value': 'autocreated'
                    },
                ],
#                ThresholdMetricId='string'
            )

#           ??????RDS???????????????CWalarm-DatabaseConnections??????
            RDS_tags = RDS_client.add_tags_to_resource(
                ResourceName=rds_record['DBInstanceArn'],
                Tags=[
                    {
                        'Key': 'CWalarm-DatabaseConnections',
                        'Value': 'enabled'
                    },
                ]
            )
            print('Added tag "CWalarm-DatabaseConnections" to: '+rds_name)

            print('Created CloudWatch alarm "RDS_DatabaseConnections" for: '+rds_name)
            print()
        else:
            print('No CloudWatch db connection alarm created for: '+rds_name)

    for rds_record in RDS_rawList:
                #       ????????????SNS topic ARN????????????CloudWatch?????????????????????????????????SNS topic
                rds_name = rds_record['DBInstanceArn'].split(':', 6)[6]
                print('------')
                #       ???????????????MySQL??????????????????????????????????????????
                if is_existed_inList(rds_name, RDS_FreeableMemory_ignoreList) & (
                        RDS_rawList[0]['Engine'] == 'mysql'):
                    print('------')
                    print('RDS name: ' + rds_name)
                    print('Creating CloudWatch alarm "RDS_FreeableMemory" for: ' + rds_name)
                    #           ??????????????????
                    CWalarms = CW_client.put_metric_alarm(
                        AlarmName='RDS_FreeableMemory-' + rds_name,
                        AlarmDescription='Auto-created customized CloudWatch Alarm <RDS_FreeableMemory>',
                        ActionsEnabled=True,
                        #                OKActions=[
                        #                    'string',
                        #                ],
                        AlarmActions=[
                            # ??????????????????SNS
                            SNS_topic_ARN
                        ],
                        #                InsufficientDataActions=[
                        #                    'string',
                        #                ],
                        MetricName='FreeableMemory',
                        Namespace="AWS/RDS",
                        Statistic='Maximum',
                        # 'SampleCount'|'Average'|'Sum'|'Minimum'|'Maximum'
                        #                ExtendedStatistic='p100',
                        Dimensions=[
                            {
                                'Name': 'DBInstanceIdentifier',
                                'Value': rds_name
                            },
                        ],
                        Period=60,
                        #                Unit='Seconds',
                        # 'Seconds'|'Microseconds'|'Milliseconds'|'Bytes'|'Kilobytes'|'Megabytes'|'Gigabytes'|'Terabytes'|'Bits'|'Kilobits'|'Megabits'|'Gigabits'|'Terabits'|'Percent'|'Count'|'Bytes/Second'|'Kilobytes/Second'|'Megabytes/Second'|'Gigabytes/Second'|'Terabytes/Second'|'Bits/Second'|'Kilobits/Second'|'Megabits/Second'|'Gigabits/Second'|'Terabits/Second'|'Count/Second'|'None'
                        EvaluationPeriods=3,
                        DatapointsToAlarm=2,
                        Threshold=1000000000,
                        ComparisonOperator='LessThanOrEqualToThreshold',
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
                                'Key': 'RDS_FreeableMemory',
                                'Value': 'autocreated'
                            },
                        ],
                        #                ThresholdMetricId='string'
                    )

                    #           ??????RDS???????????????CWalarm-FreeableMemory??????
                    RDS_tags = RDS_client.add_tags_to_resource(
                        ResourceName=rds_record['DBInstanceArn'],
                        Tags=[
                            {
                                'Key': 'CWalarm-FreeableMemory',
                                'Value': 'enabled'
                            },
                        ]
                    )
                    print('Added tag "CWalarm-FreeableMemory" to: ' + rds_name)

                    print('Created CloudWatch alarm "RDS_FreeableMemory" for: ' + rds_name)
                    print()
                else:
                    print('No CloudWatch memory alarm created for: ' + rds_name)

    for rds_record in RDS_rawList:
                #       ????????????SNS topic ARN????????????CloudWatch?????????????????????????????????SNS topic
                rds_name = rds_record['DBInstanceArn'].split(':', 6)[6]
                print('------')
                #       ???????????????MySQL??????????????????????????????????????????
                if is_existed_inList(rds_name, RDS_FreeStorageSpace_ignoreList) & (
                        RDS_rawList[0]['Engine'] == 'mysql'):
                    print('------')
                    print('RDS name: ' + rds_name)
                    print('Creating CloudWatch alarm "RDS_FreeStorageSpace" for: ' + rds_name)
                    #           ??????????????????
                    CWalarms = CW_client.put_metric_alarm(
                        AlarmName='RDS_FreeStorageSpace-' + rds_name,
                        AlarmDescription='Auto-created customized CloudWatch Alarm <RDS_FreeStorageSpace>',
                        ActionsEnabled=True,
                        #                OKActions=[
                        #                    'string',
                        #                ],
                        AlarmActions=[
                            # ??????????????????SNS
                            SNS_topic_ARN
                        ],
                        #                InsufficientDataActions=[
                        #                    'string',
                        #                ],
                        MetricName='FreeStorageSpace',
                        Namespace="AWS/RDS",
                        Statistic='Maximum',
                        # 'SampleCount'|'Average'|'Sum'|'Minimum'|'Maximum'
                        #                ExtendedStatistic='p100',
                        Dimensions=[
                            {
                                'Name': 'DBInstanceIdentifier',
                                'Value': rds_name
                            },
                        ],
                        Period=60,
                        #                Unit='Seconds',
                        # 'Seconds'|'Microseconds'|'Milliseconds'|'Bytes'|'Kilobytes'|'Megabytes'|'Gigabytes'|'Terabytes'|'Bits'|'Kilobits'|'Megabits'|'Gigabits'|'Terabits'|'Percent'|'Count'|'Bytes/Second'|'Kilobytes/Second'|'Megabytes/Second'|'Gigabytes/Second'|'Terabytes/Second'|'Bits/Second'|'Kilobits/Second'|'Megabits/Second'|'Gigabits/Second'|'Terabits/Second'|'Count/Second'|'None'
                        EvaluationPeriods=3,
                        DatapointsToAlarm=2,
                        Threshold=10000000000,
                        ComparisonOperator='LessThanOrEqualToThreshold',
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
                                'Key': 'RDS_FreeStorageSpace',
                                'Value': 'autocreated'
                            },
                        ],
                        #                ThresholdMetricId='string'
                    )

                    #           ??????RDS???????????????CWalarm-FreeStorageSpace??????
                    RDS_tags = RDS_client.add_tags_to_resource(
                        ResourceName=rds_record['DBInstanceArn'],
                        Tags=[
                            {
                                'Key': 'CWalarm-FreeStorageSpace',
                                'Value': 'enabled'
                            },
                        ]
                    )
                    print('Added tag "CWalarm-FreeStorageSpace" to: ' + rds_name)

                    print('Created CloudWatch alarm "RDS_FreeStorageSpace" for: ' + rds_name)
                    print()
                else:
                    print('No CloudWatch FreeStorageSpace alarm created for: ' + rds_name)


    return {
        'statusCode': 200,
        'body': json.dumps('Mission Complete!')
    }


#run_command('/var/task/aws --version')
#run_command('ls -l')

