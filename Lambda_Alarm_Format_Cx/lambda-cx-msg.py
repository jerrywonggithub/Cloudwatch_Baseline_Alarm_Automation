import boto3
import os
import json
import datetime
import urllib
# from changeAlarmToLocalTimeZone import *

#Get SNS Topic ARN from Environment variables
NotificationSNSTopicARN = os.environ['NotificationSNSTopicARN']

# #Get timezone corresponding to your localTimezone from Environment variables
# timezoneCode = os.environ['TimeZoneCode']
#
# #Get Your local timezone Initials, E.g UTC+2, IST, AEST...etc from Environment variables
# localTimezoneInitial=os.environ['TimezoneInitial']

#Get SNS resource using boto3
SNS = boto3.resource('sns')

#Specify the SNS topic to push message to by ARN
platform_endpoint = SNS.PlatformEndpoint(NotificationSNSTopicARN)

def lambda_handler(event, context):

    #Call Main function
    # changeAlarmToLocalTimeZone(event,timezoneCode,localTimezoneInitial,platform_endpoint)
    
    #Print All Available timezones
    #getAllAvailableTimezones()
    
    #search if Timezone/Country exist
    #searchAvailableTimezones('sy')
    AlarmEvent = json.loads(event['Records'][0]['Sns']['Message'])
    # extract event data like alarm name, region, state, timestamp
    alarmName = AlarmEvent['AlarmName']
    descriptionexist = 0
    if "AlarmDescription" in AlarmEvent:
        description = AlarmEvent['AlarmDescription']
        descriptionexist = 1
    reason = AlarmEvent['NewStateReason']
    region = AlarmEvent['Region']
    state = AlarmEvent['NewStateValue']
    previousState = AlarmEvent['OldStateValue']
    timestamp = AlarmEvent['StateChangeTime']
    Subject = event['Records'][0]['Sns']['Subject']
    alarmARN = AlarmEvent['AlarmArn']
    RegionID = alarmARN.split(":")[3]
    AccountID = AlarmEvent['AWSAccountId']

    # create Custom message and change timestamps

    customMessage = 'You are receiving this email because your Amazon CloudWatch Alarm "' + alarmName + '" in the ' + region + ' region has entered the ' + state + ' state, because "' + reason + '" at "' + timestamp + ' UTC'  + '.'

    # Add Console link
    customMessage = customMessage + '\n\n View this alarm in the AWS Management Console: \n' + 'https://' + RegionID + '.console.aws.amazon.com/cloudwatch/home?region=' + RegionID + '#s=Alarms&alarm=' + urllib.parse.quote(
        alarmName)

    # Add Alarm Name
    customMessage = customMessage + '\n\n Alarm Details:\n- Name:\t\t\t\t\t\t' + alarmName

    # Add alarm description if exist
    if (descriptionexist == 1): customMessage = customMessage + '\n- Description:\t\t\t\t\t' + description
    customMessage = customMessage + '\n- State Change:\t\t\t\t' + previousState + ' -> ' + state

    # Add alarm reason for changes
    customMessage = customMessage + '\n- Reason for State Change:\t\t' + reason

    # Add alarm evaluation timeStamp
    customMessage = customMessage + '\n- Timestamp:\t\t\t\t\t' + timestamp + ' UTC'

    # Add AccountID
    customMessage = customMessage + '\n- AWS Account: \t\t\t\t' + AccountID

    # Add Alarm ARN
    customMessage = customMessage + '\n- Alarm Arn:\t\t\t\t\t' + alarmARN

    # push message to SNS topic
    response = platform_endpoint.publish(
        Message=customMessage,
        Subject=Subject,
        MessageStructure='string'
    )
