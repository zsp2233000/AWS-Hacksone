import os
import json
import logging
import boto3
from botocore.exceptions import ClientError, BotoCoreError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb   = boto3.resource("dynamodb")
TABLE_NAME = os.getenv("TABLE_NAME")

def lambda_handler(event, context):
    """Lambda adaptor：將 SQS 傳來的 body 轉存至 DynamoDB。"""
    logger.info("event: %s", event)
    if not TABLE_NAME:
        logger.error("TABLE_NAME env 未設定")
        return {"statusCode": 500, "body": "Missing TABLE_NAME"}

    table = dynamodb.Table(TABLE_NAME)
    logger.info(event.get("Records", []))
    for rec in event.get("Records", []):
        body = rec.get("body")
        messageId = rec.get("messageId")
        logger.info("messageId: %s", messageId)
        if not body:
            logger.warning("Record 無 body，跳過")
            continue

        try:
            msg      = json.loads(body)
            payload  = msg.get("payload", {})
            notif = payload.get("notification", {}) if payload else {}

            item = {
                "messageId" :     messageId,
                "transaction_id": msg.get("transaction_id"),
                "sns_id":      msg.get("sns_id",""),
                "token":          msg.get("token",""),
                "platform":       msg.get("platform",""),
                "payload":        msg,
                "notification_title": notif.get("title",""),
                "notification_body":  notif.get("body",""),
                "status":         msg.get("status",""),
                "retry_cnt":      msg.get("retry_cnt", 0),
                "error_msg":      msg.get("error_msg",""),
                "send_ts":        msg.get("send_ts",""),
                "delivered_ts":   msg.get("delivered_ts",""),
                "failed_ts":      msg.get("failed_ts",""),
                "created_at":    msg.get("created_at",""),
                "ap_id":          msg.get("ap_id",""),
                "event_message":        msg.get("event_message","")
            }

            logger.info(item)
            table.put_item(Item=item)
            logger.info("寫入 DynamoDB 成功", extra={"transaction_id": item["transaction_id"]})
        except Exception as e:
            logger.exception(f"Adaptor 處理失敗: {e}")
            return {"statusCode": 500, "body": "Error"}

    return {"statusCode": 200, "body": "OK"}
