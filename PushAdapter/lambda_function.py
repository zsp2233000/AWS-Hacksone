import json
import os
import uuid
import sys
import boto3

# 建立 SQS 客戶端
sqs = boto3.client('sqs')
QUEUE_URL = os.environ.get('SQS_URL')  # 從環境變數取得 SQS URL
MAX_SQS_MESSAGE_SIZE = 262144  # SQS 最大訊息大小為 256 KB

def lambda_handler(event, context):
    try:
        # 檢查 event 的結構
        if isinstance(event, list):
            # 如果 event 是列表（例如直接測試的情況），直接使用
            body = event
        elif isinstance(event, dict) and 'body' in event:
            # 如果 event 是字典（API Gateway 格式），處理 body
            if isinstance(event['body'], str):
                body = json.loads(event['body'])
            else:
                body = event['body']   

        # 確保 body 是陣列格式
        if not isinstance(body, list):
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'body must be an array'})
            }
        
        # 驗證陣列不為空
        if len(body) == 0:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'body array cannot be empty'})
            }
        
        successful_messages = []
        failed_messages = []
        
        # 處理陣列中的每個項目
        for index, item in enumerate(body):
            try:
                # 驗證必要的欄位
                if not item.get('token'):
                    failed_messages.append({
                        'index': index,
                        'error': 'token is required'
                    })
                    continue
                    
                # 動態生成 transaction_id
                transaction_id = str(uuid.uuid4())

                # 準備 SQS 訊息
                message = {
                    "ap_id": item.get('ap_id', ''),
                    "transaction_id": transaction_id,
                    "token": item.get('token', ''),
                    "payload": {
                        "notification": item.get('payload', {}).get('notification', {}),
                        "link": item.get('payload', {}).get('link', '')
                        }
                    }
                
                successful_messages.append(message)
                
            except Exception as item_error:
                print(json.dumps({
                    'level': 'ERROR',
                    'message': f"Error processing item {index}: {str(item_error)}",
                    'timestamp': context.get_remaining_time_in_millis(),
                    'function_name': context.function_name
                }))
                failed_messages.append({
                    'index': index,
                    'error': str(item_error)
                })

        send_message_to_sqs(successful_messages, failed_messages, context)

        # 回傳批次處理結果給 API Gateway
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Processed {len(body)} messages',
                'total': len(body),
                'successful': len(successful_messages),
                'failed': len(failed_messages),
                'successful_messages': successful_messages,
                'failed_messages': failed_messages
            })
        }
        
    except Exception as e:
        print(json.dumps({
            'level': 'ERROR',
            'message': str(e),
            'timestamp': context.get_remaining_time_in_millis(),
            'function_name': context.function_name
        }))
        # 錯誤處理
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
    
def send_message_to_sqs(successful_messages, failed_messages, context):
    """發送訊息到 SQS"""
    # 分批處理訊息
    batches = []
    current_batch = []
    current_size = 0
    
    for message in successful_messages:
        # 估計單一訊息的大小
        message_size = sys.getsizeof(json.dumps([message]))
        if current_size + message_size > MAX_SQS_MESSAGE_SIZE and current_batch:
            # 當前批次已滿，加入 batches
            batches.append(current_batch)
            current_batch = [message]
            current_size = message_size
        else:
            # 添加到當前批次
            current_batch.append(message)
            current_size += message_size
    
    # 加入最後一批
    if current_batch:
        batches.append(current_batch)
    
    # 發送每批訊息
    for batch_index, batch in enumerate(batches):
        try:
            message_body = json.dumps(batch)
            print(f"Sending batch {batch_index + 1}/{len(batches)} to SQS: {message_body}")
            
            # 發送單一 SQS 訊息
            response = sqs.send_message(
                QueueUrl=QUEUE_URL,
                MessageBody=message_body
            )
            # test
            # 模擬 SQS 響應，包含 MessageId
            # response = {'MessageId': f"test-message-id-{batch_index}-{uuid.uuid4()}"}
            
            # 更新 successful_messages，加入 messageId
            for success in successful_messages:
                if any(msg['transaction_id'] == success['transaction_id'] for msg in batch):
                    success['messageId'] = response['MessageId']
            
        except Exception as sqs_error:
            print(json.dumps({
                'level': 'ERROR',
                'message': f"Failed to send batch {batch_index + 1} to SQS: {str(sqs_error)}",
                'timestamp': context.get_remaining_time_in_millis(),
                'function_name': context.function_name
            }))
            # 將該批次的訊息標記為失敗
            for success in successful_messages[:]:
                if any(msg['transaction_id'] == success['transaction_id'] for msg in batch):
                    failed_messages.append({
                        'index': success['index'],
                        'error': f"SQS send failed: {str(sqs_error)}"
                    })
                    successful_messages.remove(success)