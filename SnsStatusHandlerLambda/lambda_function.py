import json
import os
import boto3
import logging

# 配置日誌
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# 從環境變數獲取目標 SQS 佇列 URL
STATUS_UPDATE_QUEUE_URL = os.environ.get('STATUS_UPDATE_QUEUE_URL')

# 初始化 SQS 客戶端
sqs_client = boto3.client('sqs')

def lambda_handler(event, context):
    """
    Lambda 處理函數主體：
    1. 遍歷收到的所有 SNS 記錄。
    2. 解析每條記錄中的交付狀態訊息。
    3. 組裝標準化的內部事件。
    4. 將內部事件發送到 SQS 佇列。
    """
    aws_request_id = context.aws_request_id
    logger.info(f"Request ID: {aws_request_id} - Lambda 接收到事件: {json.dumps(event)}")

    if not STATUS_UPDATE_QUEUE_URL:
        logger.error(f"Request ID: {aws_request_id} - 環境變數 STATUS_UPDATE_QUEUE_URL 未設定。")
        # 拋出錯誤以便觸發 Lambda 的重試機制和 DLQ
        raise ValueError("Lambda configuration error: STATUS_UPDATE_QUEUE_URL is not set.")

    # SNS 事件可能包含多條記錄
    for record in event.get('Records', []):
        try:
            # SNS 交付狀態被包裝在 Sns.Message 這個 JSON 字串中
            sns_message_str = record['Sns']['Message']
            status_event = json.loads(sns_message_str)

            # 提取關鍵資訊
            sns_message_id = status_event.get('notification', {}).get('messageId')
            delivery_status = status_event.get('status')
            provider_response = status_event.get('delivery', {}).get('providerResponse', '')

            if not sns_message_id or not delivery_status:
                logger.warning(f"Request ID: {aws_request_id} - 收到的狀態事件缺少必要欄位: {sns_message_str}")
                continue # 繼續處理下一條記錄

            # 組裝要發送到下游的內部事件訊息
            internal_event = {
                'snsMessageId': sns_message_id,
                'deliveryStatus': delivery_status,
                'providerResponse': provider_response,
                'timestamp': record['Sns']['Timestamp']
            }
            
            # 將內部事件發送到 StatusUpdateQueue
            sqs_client.send_message(
                QueueUrl=STATUS_UPDATE_QUEUE_URL,
                MessageBody=json.dumps(internal_event)
            )
            
            logger.info(f"Request ID: {aws_request_id} - 成功處理並轉發狀態事件。snsMessageId: {sns_message_id}, Status: {delivery_status}")

        except Exception as e:
            logger.error(f"Request ID: {aws_request_id} - 處理單條記錄時發生錯誤: {str(e)}", exc_info=True)
            # 即使單條記錄處理失敗，也繼續嘗試處理批次中的其他記錄
            # 失敗的記錄可以依賴 Lambda 的重試和 DLQ 機制
            continue
            
    return {
        'statusCode': 200,
        'body': json.dumps('Successfully processed event records.')
    }