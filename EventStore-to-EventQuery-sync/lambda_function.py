import boto3
import json
from decimal import Decimal
from aws_lambda_powertools import Logger
logger = Logger(service="EventStore-to-EventQuery-sync")
dynamodb = boto3.resource('dynamodb')
query_table = dynamodb.Table('EventQuery')

def lambda_handler(event, context):
    logger.info("Lambda 開始處理 DynamoDB Stream")
    for record in event['Records']:
        if record['eventName'] not in ['INSERT', 'MODIFY']:
            continue

        new_image = record['dynamodb']['NewImage']
        item = {
            'transaction_id': new_image['transaction_id']['S'],
            'messageId':  new_image['messageId']['S'],
            'token': new_image.get('token', {}).get('S'),
            'platform': new_image.get('platform', {}).get('S'),
            'notification_title': new_image.get('notification_title', {}).get('S'),
            'notification_body': new_image.get('notification_body', {}).get('S'),
            'status': new_image.get('status', {}).get('S'),
            'send_ts': new_image.get('send_ts', {}).get('N'),
            'delivered_ts': new_image.get('delivered_ts', {}).get('N'),
            'failed_ts': new_image.get('failed_ts', {}).get('N'),
            'created_at': new_image.get('created_at', {}).get('N'),
            'ap_id': new_image.get('ap_id', {}).get('S')
        }
        logger.info("DynamoDB Stream NewImage: ")
        logger.info(item)
        query_table.put_item(Item=item)
        logger.info("DynamoDB Query Table 更新成功")
