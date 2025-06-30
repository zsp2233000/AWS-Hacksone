#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Message Status Task for ECS
處理 StatusUpdateQueue 和 DLQ 的訊息，並轉發到 EventQueue
"""

import json
import os
import time
import logging
import signal
import sys
import asyncio
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from datetime import datetime
import aiohttp

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class MessageStatusProcessor:
    def __init__(self):
        """初始化 SQS 客戶端和配置"""
        try:
            self.sqs = boto3.client('sqs')
            
            # 從環境變數獲取 SQS URL
            self.status_queue_url = os.environ.get('STATUS_UPDATE_QUEUE_URL')
            self.dlq_url = os.environ.get('DLQ_URL')
            self.event_queue_url = os.environ.get('EVENT_QUEUE_URL')
            self.push_queue_url = os.environ.get('PUSH_QUEUE_URL')  # 推播佇列
            self.query_url = os.environ.get('QUERY_DB_URL')

            # 驗證環境變數
            if not all([self.status_queue_url, self.dlq_url, self.event_queue_url, self.push_queue_url, self.query_url]):
                raise ValueError("Missing required environment variables: STATUS_UPDATE_QUEUE_URL, DLQ_URL, EVENT_QUEUE_URL, PUSH_QUEUE_URL, QUERY_DB_URL")

            logger.info(f"初始化完成 - Status Queue: {self.status_queue_url}")
            logger.info(f"DLQ: {self.dlq_url}")
            logger.info(f"Event Queue: {self.event_queue_url}")
            if self.push_queue_url:
                logger.info(f"Push Queue: {self.push_queue_url}")
            
            self.running = True
            self.max_messages = int(os.environ.get('MAX_MESSAGES', '10'))  # 預設一次處理 10 個訊息
            self.max_retry_cnt = int(os.environ.get('MAX_RETRY_COUNT', '3'))  # 最大重試次數
            
        except Exception as e:
            logger.error(f"初始化失敗: {str(e)}")
            raise

    def process_message(self, message_body: str, source_queue: str, original_message: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        處理單一訊息並轉換為 EventQueue 格式
        
        Args:
            message_body: SQS 訊息內容
            source_queue: 來源佇列名稱
            original_message: 原始推播訊息

        Returns:
            處理後的訊息或 None (如果處理失敗)
        """
        try:
            # 解析訊息
            if isinstance(message_body, str):
                message_data = json.loads(message_body)
            else:
                message_data = message_body
                
            # 驗證必要欄位
            required_fields = ['sns_id', 'delivery_status', 'provider_response', 'timestamp']
            for field in required_fields:
                if field not in message_data:
                    logger.warning(f"訊息缺少必要欄位 {field}: {message_body}")
                    return None
            
            # 準備要發送到 Queue 的訊息 - 合併原始訊息和狀態資料
            event_message = original_message.copy()
            
            event_message.update({
                'sns_id': message_data['sns_id'],
                'status': message_data['delivery_status'],
                'delivered_ts': int(time.time() * 1000),
                'created_at': int(time.time() * 1000),
                'apid': original_message.get('ap_id', ''),
            })

            logger.info(f"成功處理訊息 ID: {message_data['sns_id']}, Transaction_id: {original_message.get('transaction_id')}, 狀態: {message_data['delivery_status']}")
            return event_message
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析錯誤: {str(e)}, 訊息: {message_body}")
            return None
        except Exception as e:
            logger.error(f"處理訊息時發生錯誤: {str(e)}, 訊息: {message_body}")
            return None

    async def query_original_message(self, sns_id: str, sqs_message_id: str = None) -> Optional[Dict[str, Any]]:
        """
        透過 SNS ID 查詢原始推播訊息，並於失敗時記錄 SQS MessageId
        
        Args:
            sns_id: SNS 訊息 ID
            sqs_message_id: SQS 訊息的 MessageId (for logging)
        Returns:
            原始推播訊息或 None
        """
        try:
            api_url = self.query_url + sns_id
            # await asyncio.sleep(5)
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        # 檢查 API 回應格式
                        if result.get('success') and result.get('data'):
                            data_list = result['data']
                            if data_list and len(data_list) > 0:
                                # 取第一筆資料作為原始訊息
                                original_message = data_list[0]
                                logger.info(f"成功查詢原始訊息，SNS ID: {sns_id}, Transaction ID: {original_message.get('transaction_id')}")
                                return original_message
                            else:
                                logger.warning(f"查詢 API 回應成功但 data 為空，SNS ID: {sns_id}, SQS MessageId: {sqs_message_id}")
                                return None
                        else:
                            logger.warning(f"查詢 API 回應失敗或 success 為 false，SNS ID: {sns_id}, SQS MessageId: {sqs_message_id}, Response: {result}")
                            return None
                    else:
                        logger.error(f"查詢原始訊息失敗，SNS ID: {sns_id}, SQS MessageId: {sqs_message_id}, Status: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"查詢原始訊息時發生錯誤，SNS ID: {sns_id}, SQS MessageId: {sqs_message_id}, 錯誤: {str(e)}")
            return None

    async def send_retry_message(self, original_message: Dict[str, Any], retry_count: int) -> bool:
        """
        發送重試訊息到推播佇列
        
        Args:
            original_message: 原始推播訊息
            retry_count: 重試次數
            
        Returns:
            bool: 成功發送返回 True，否則返回 False
        """
        if not self.push_queue_url:
            logger.warning("未設定 PUSH_QUEUE_URL，無法發送重試訊息")
            return False
            
        try:
            # 組成重試訊息格式
            retry_message = {
                "apid": original_message.get("ap_id", ""),
                "transaction_id": original_message.get("transaction_id", ""),
                "token": original_message.get("token", ""),
                "payload": original_message.get("payload", {}),
                "retry_cnt": retry_count
            }
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.sqs.send_message(
                    QueueUrl=self.push_queue_url,
                    MessageBody=json.dumps(retry_message)
                )
            )
            
            logger.info(f"成功發送重試訊息到推播佇列，MessageId: {response['MessageId']}, 重試次數: {retry_count}")
            return True
            
        except Exception as e:
            logger.error(f"發送重試訊息失敗: {str(e)}")
            return False

    def send_to_event_queue(self, messages: list) -> bool:
        """
        將處理後的訊息發送到 EventQueue
        
        Args:
            messages: 要發送的訊息列表
            
        Returns:
            bool: 成功發送返回 True，否則返回 False
        """
        if not messages:
            return True
            
        try:
            # 批次發送訊息到 EventQueue
            for message in messages:
                response = self.sqs.send_message(
                    QueueUrl=self.event_queue_url,
                    MessageBody=json.dumps(message)
                )
                logger.info(f"成功發送訊息到 EventQueue，MessageId: {response['MessageId']}")
                
            return True
            
        except ClientError as e:
            logger.error(f"發送訊息到 EventQueue 失敗: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"發送訊息時發生未預期錯誤: {str(e)}")
            return False

    async def send_to_event_queue_async(self, messages: list) -> bool:
        """
        非同步將處理後的訊息發送到 EventQueue
        
        Args:
            messages: 要發送的訊息列表
            
        Returns:
            bool: 成功發送返回 True，否則返回 False
        """
        if not messages:
            return True
            
        try:
            loop = asyncio.get_event_loop()
            # 批次發送訊息到 EventQueue
            for message in messages:
                response = await loop.run_in_executor(
                    None,
                    lambda msg=message: self.sqs.send_message(
                        QueueUrl=self.event_queue_url,
                        MessageBody=json.dumps(msg)
                    )
                )
                logger.info(f"成功發送訊息到 EventQueue，MessageId: {response['MessageId']}")
                
            return True
            
        except ClientError as e:
            logger.error(f"發送訊息到 EventQueue 失敗: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"發送訊息時發生未預期錯誤: {str(e)}")
            return False

    async def poll_queue(self, queue_url: str, queue_name: str) -> None:
        """
        非同步輪詢指定的 SQS 佇列，並行查詢原始訊息以提升效能
        Args:
            queue_url: SQS 佇列 URL
            queue_name: 佇列名稱 (用於日誌)
        """
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.sqs.receive_message(
                    QueueUrl=queue_url,
                    MaxNumberOfMessages=self.max_messages,
                    WaitTimeSeconds=20,  # 長輪詢
                    VisibilityTimeout=300  # 5 分鐘
                )
            )
            messages = response.get('Messages', [])
            if not messages:
                logger.debug(f"從 {queue_name} 沒有接收到訊息")
                return
            logger.info(f"從 {queue_name} 接收到 {len(messages)} 個訊息")

            # 1. 收集所有 sns_id 與 MessageId
            sns_id_list = []
            message_id_list = []
            for message in messages:
                message_data = json.loads(message['Body']) if isinstance(message['Body'], str) else message['Body']
                sns_id_list.append(message_data.get('sns_id'))
                message_id_list.append(message.get('MessageId'))

            # 2. 批次並行查詢原始訊息
            query_tasks = [
                asyncio.create_task(self.query_original_message(sns_id, sqs_message_id))
                for sns_id, sqs_message_id in zip(sns_id_list, message_id_list)
            ]
            original_message_list = await asyncio.gather(*query_tasks)

            processed_messages = []
            receipt_handles = []

            # 3. 處理每個訊息，與查詢結果一一對應
            for idx, message in enumerate(messages):
                message_data = json.loads(message['Body']) if isinstance(message['Body'], str) else message['Body']
                original_message = original_message_list[idx]
                should_retry = (
                    message_data.get('delivery_status') == 'FAILURE' or 
                    queue_name == 'DLQ'
                )
                sns_id = message_data.get('sns_id')
                # 如果原始訊息不存在，則記錄警告並跳過，並且不刪除訊息
                if not original_message:
                    logger.warning(f"無法查詢到原始訊息，SNS ID: {sns_id}，跳過處理此訊息")
                    continue
                if should_retry:
                    current_retry_cnt = original_message.get('retry_cnt')
                    if current_retry_cnt < self.max_retry_cnt:
                        if sns_id:
                            if original_message:
                                retry_success = await self.send_retry_message(
                                    original_message, 
                                    current_retry_cnt + 1
                                )
                                if retry_success:
                                    logger.info(f"已發送重試訊息到 PushQueue，Transaction ID: {original_message.get('transaction_id')}, 重試次數: {current_retry_cnt + 1}")
                                else:
                                    logger.error(f"重試訊息發送失敗，SNS ID: {sns_id}")
                    else:
                        logger.warning(f"訊息已達最大重試次數 {self.max_retry_cnt}，SNS ID: {message_data.get('sns_id')} ; Transaction ID: {original_message.get('transaction_id')}")
                processed_message = self.process_message(message['Body'], queue_name, original_message)
                if processed_message:
                    processed_messages.append(processed_message)
                    receipt_handles.append(message['ReceiptHandle'])
                else:
                    receipt_handles.append(message['ReceiptHandle'])
            # 發送到 EventQueue
            if processed_messages:
                success = await self.send_to_event_queue_async(processed_messages)
                if success:
                    await self.delete_messages_async(queue_url, receipt_handles, queue_name)
                else:
                    logger.error(f"無法發送訊息到 EventQueue，保留 {queue_name} 中的訊息")
            else:
                await self.delete_messages_async(queue_url, receipt_handles, queue_name)
        except ClientError as e:
            logger.error(f"輪詢 {queue_name} 時發生 AWS 錯誤: {str(e)}")
        except Exception as e:
            logger.error(f"輪詢 {queue_name} 時發生未預期錯誤: {str(e)}")

    def delete_messages(self, queue_url: str, receipt_handles: list, queue_name: str) -> None:
        """
        刪除已處理的訊息
        
        Args:
            queue_url: SQS 佇列 URL
            receipt_handles: 要刪除的訊息的 receipt handles
            queue_name: 佇列名稱 (用於日誌)
        """
        for receipt_handle in receipt_handles:
            try:
                self.sqs.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=receipt_handle
                )
                logger.debug(f"成功刪除 {queue_name} 中的訊息")
            except ClientError as e:
                logger.error(f"刪除 {queue_name} 中的訊息失敗: {str(e)}")

    async def delete_messages_async(self, queue_url: str, receipt_handles: list, queue_name: str) -> None:
        """
        非同步刪除已處理的訊息
        
        Args:
            queue_url: SQS 佇列 URL
            receipt_handles: 要刪除的訊息的 receipt handles
            queue_name: 佇列名稱 (用於日誌)
        """
        loop = asyncio.get_event_loop()
        
        for receipt_handle in receipt_handles:
            try:
                await loop.run_in_executor(
                    None,
                    lambda rh=receipt_handle: self.sqs.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=rh
                    )
                )
                logger.debug(f"成功刪除 {queue_name} 中的訊息")
            except ClientError as e:
                logger.error(f"刪除 {queue_name} 中的訊息失敗: {str(e)}")

    async def run_async(self) -> None:
        """主要的非同步運行循環"""
        logger.info("Message Status Processor 開始運行...")
        
        while self.running:
            try:
                # 同時輪詢 StatusUpdateQueue 和 DLQ
                await asyncio.gather(
                    self.poll_queue(self.status_queue_url, "StatusUpdateQueue"),
                    self.poll_queue(self.dlq_url, "DLQ")
                )
                
            except KeyboardInterrupt:
                logger.info("接收到中斷信號，正在停止...")
                self.stop()
            except Exception as e:
                logger.error(f"運行循環中發生錯誤: {str(e)}")

    def run(self) -> None:
        """主要的運行循環 - 包裝非同步版本"""
        asyncio.run(self.run_async())

    def stop(self) -> None:
        """停止處理器"""
        logger.info("正在停止 Message Status Processor...")
        self.running = False

# 信號處理器
def signal_handler(signum, frame):
    """處理系統信號"""
    logger.info(f"接收到信號 {signum}，正在優雅停止...")
    processor.stop()
    sys.exit(0)

# 全域處理器實例
processor = None

def main():
    """主函數"""
    global processor
    
    # 註冊信號處理器
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        processor = MessageStatusProcessor()
        processor.run()
    except NoCredentialsError:
        logger.error("AWS 認證失敗，請檢查 AWS credentials")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"配置錯誤: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"應用程式啟動失敗: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
