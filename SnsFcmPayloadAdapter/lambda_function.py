import json
import os
import boto3
import logging

# 配置日誌
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# 從環境變數獲取目標 SNS 資源 ARN (用於直接推播)
SNS_DIRECT_PUSH_TARGET_ARN = os.environ.get('SNS_DIRECT_PUSH_TARGET_ARN')

# 初始化 SNS 客戶端
sns_client = boto3.client('sns')

def validate_input_event(event_data):
    """
    驗證傳入 Lambda 的事件資料結構。
    Args:
        event_data (dict): Lambda 接收到的事件。
    Returns:
        tuple: (bool, str) 驗證結果 (is_valid, message)。
    """
    required_keys = ["transaction_id", "token", "payload"]
    for key in required_keys:
        if key not in event_data:
            return False, f"必要欄位缺失: '{key}'。"
        
        if key == "payload" and not isinstance(event_data[key], dict):
            return False, f"欄位 '{key}' 必須是字典。"
        elif key != "payload" and not isinstance(event_data[key], str): 
            return False, f"欄位 '{key}' 必須是字串。"

    payload = event_data["payload"]
    if "notification" not in payload or not isinstance(payload["notification"], dict):
        return False, "欄位 'payload.notification' 缺失或必須是字典。"
    
    notification = payload["notification"]
    if "title" not in notification or not isinstance(notification["title"], str):
        return False, "欄位 'payload.notification.title' 缺失或必須是字串。"
    if "body" not in notification or not isinstance(notification["body"], str):
        return False, "欄位 'payload.notification.body' 缺失或必須是字串。"
        
    if "link" not in payload or not isinstance(payload["link"], str):
        return False, "欄位 'payload.link' 缺失或必須是字串。"

    platform_config_keys = ["android_config", "apns_config", "webpush_config"]
    for config_key in platform_config_keys:
        if config_key in payload and not isinstance(payload[config_key], dict):
            return False, f"欄位 'payload.{config_key}' 如果存在，必須是字典。"

    business_data_keys_to_check_type = ["amount", "recipient_name", "credited_amount", "sender_name", "error_message", "order_id", "alert_level", "article_id"]
    for key in business_data_keys_to_check_type:
        if key in payload and not isinstance(payload[key], (str, int, float, bool)):
             logger.warning(f"欄位 'payload.{key}' 的類型為 {type(payload[key])}，預期為可轉換為字串的類型。")

    return True, "事件資料有效。"

def build_fcm_v1_message_object(event_data):
    """
    根據輸入事件建構 FCM HTTP v1 API 的 message 物件。
    Args:
        event_data (dict): 經過驗證的 Lambda 事件資料。
    Returns:
        dict: FCM message 物件。
    """
    payload = event_data["payload"]
    
    message = {
        "token": event_data["token"], 
        "notification": {
            "title": payload["notification"]["title"],
            "body": payload["notification"]["body"]
        },
        "data": {
            "deepLink": payload["link"] 
        }
    }
    
    known_payload_keys_for_structure = ["notification", "link", "android_config", "apns_config", "webpush_config"]
    
    for key, value in payload.items():
        if key not in known_payload_keys_for_structure: 
            if isinstance(value, (str, int, float, bool)):
                message["data"][key] = str(value)
            else:
                logger.warning(f"欄位 'payload.{key}' (值: {value}) 的類型 ({type(value)}) 不適合放入 FCM data payload，將被忽略。")

    if "android_config" in payload and isinstance(payload["android_config"], dict):
        message["android"] = payload["android_config"]

    if "apns_config" in payload and isinstance(payload["apns_config"], dict):
        message["apns"] = payload["apns_config"]

    if "webpush_config" in payload and isinstance(payload["webpush_config"], dict):
        message["webpush"] = payload["webpush_config"]

    return message

def lambda_handler(event, context):
    """
    Lambda 處理函數：
    1. 驗證輸入事件。
    2. 根據事件內容建構 FCM v1 message 物件。
    3. 將 message 物件包裝成 SNS 直接推播 FCM 所需的 GCM payload 格式。
    4. 發佈 GCM payload 到指定的 SNS 目標 ARN。
    """
    # 從 context 物件中取得 AWS 為這次執行所產生的 Request ID
    aws_request_id = context.aws_request_id
    
    logger.info(f"Request ID: {aws_request_id} - SnsFcmPayloadAdapter Lambda 接收到原始事件: {json.dumps(event)}") 

    if not SNS_DIRECT_PUSH_TARGET_ARN:
        logger.error(f"Request ID: {aws_request_id} - 環境變數 SNS_DIRECT_PUSH_TARGET_ARN 未設定。") 
        return {
            'statusCode': 500, 
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Lambda configuration error: SNS_DIRECT_PUSH_TARGET_ARN is not set.', 'lambda_request_id': aws_request_id})
        }

    try:
        if 'body' in event and isinstance(event['body'], str):
            request_body = json.loads(event['body'])
        else:
            request_body = event
    except json.JSONDecodeError:
        logger.error(f"Request ID: {aws_request_id} - 解析 event['body'] 的 JSON 格式失敗。")
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Invalid JSON format in request body.', 'lambda_request_id': aws_request_id})
        }
    
    is_valid, validation_msg = validate_input_event(request_body)
    if not is_valid:
        logger.error(f"Request ID: {aws_request_id} - 輸入事件驗證失敗: {validation_msg}") 
        return {
            'statusCode': 400, 
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': f"Invalid input: {validation_msg}", 'lambda_request_id': aws_request_id})
        }
    
    transaction_id = request_body.get("transaction_id", "N/A")
    logger.info(f"Request ID: {aws_request_id} - Transaction ID: {transaction_id} - 輸入事件驗證成功。")

    fcm_v1_message_object = build_fcm_v1_message_object(request_body)
    
    gcm_payload_inner_object = {
        "fcmV1Message": { 
            "validate_only": False,
            "message": fcm_v1_message_object
        }
    }
    gcm_payload_inner_json_string = json.dumps(gcm_payload_inner_object, ensure_ascii=False) 
    
    sns_message_payload_for_publish = {
        "default": f"交易 {transaction_id}: {request_body['payload']['notification']['title']}", 
        "GCM": gcm_payload_inner_json_string 
    }
    final_sns_message_to_publish = json.dumps(sns_message_payload_for_publish, ensure_ascii=False) 

    try:
        publish_response = sns_client.publish(
            TargetArn=SNS_DIRECT_PUSH_TARGET_ARN, 
            Message=final_sns_message_to_publish,
            MessageStructure='json',
            # Subscription Filter
            MessageAttributes={
                "token": {
                    "DataType": "String", 
                    "StringValue": fcm_v1_message_object.get("token", "unknown")
                 }
            }
        )
        sns_message_id = publish_response.get('MessageId')
        
        logger.info(f"Request ID: {aws_request_id} - Transaction ID: {transaction_id} - Payload 成功發佈到 SNS。Message ID: {sns_message_id}") 
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'message': 'Payload successfully prepared and published to SNS for direct FCM push.',
                'transaction_id': transaction_id,
                'sns_message_id': sns_message_id,
                'lambda_request_id': aws_request_id
            })
        }
    except Exception as e:
        logger.error(f"Request ID: {aws_request_id} - Transaction ID: {transaction_id} - 發佈 payload 到 SNS 失敗: {str(e)}", exc_info=True) 
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': f"Failed to publish payload to SNS: {str(e)}",
                'transaction_id': transaction_id,
                'lambda_request_id': aws_request_id
            })
        }