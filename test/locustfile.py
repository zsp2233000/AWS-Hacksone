import json
import random
import string
from locust import HttpUser, task, between

class LoadTestUser(HttpUser):
    # 設定請求之間的等待時間（秒）
    wait_time = between(1, 3)
    
    def on_start(self):
        """測試開始時執行的初始化"""
        self.headers = {
            'Content-Type': 'application/json'
        }
    
    def generate_random_transaction_id(self):
        """生成隨機的交易ID"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    
    def generate_test_data(self, count=100):
        """生成測試數據，預設100筆"""
        data = []
        for i in range(count):
            item = {
                "ap_id": "MID-LX-LNK-01",
                "transaction_id": self.generate_random_transaction_id(),
                "token": "fQ-zCXEvSTal059Zh_-jNt:APA91bF-DXII3eYbVOpfjdujd1kX9kj9zuO9LQF0wB8Rew_o0TFY4d6EvZi_0yp_KJ3lgyrepB7sxSWzoBtMUNajuS4cKnWd2jOMpu9vKcoX1ziDCBQVhl8",
                "payload": {
                    "notification": {
                        "title": "匯款",
                        "body": f"您在 2025/5/29 上午 10:47 匯款成功 (#{i+1})"
                    },
                    "link": "https://www.example.com/test/path"
                }            }
            data.append(item)
        return data
    
    # @task(1)
    # def send_notification_batch(self):
    #     """發送通知批次 - 10筆資料（主要測試）"""
    #     test_data = self.generate_test_data(10)
        
    #     with self.client.post(
    #         "/",
    #         json=test_data,
    #         headers=self.headers,
    #         catch_response=True
    #     ) as response:
    #         if response.status_code == 200:
    #             response.success()
    #         else:
    #             response.failure(f"請求失敗: {response.status_code} - {response.text}")
    
    # @task(1)
    # def send_notification_small_batch(self):
    #     """發送小批次通知 - 5筆資料"""
    #     test_data = self.generate_test_data(5)
        
    #     with self.client.post(
    #         "/",
    #         json=test_data,
    #         headers=self.headers,
    #         catch_response=True
    #     ) as response:
    #         if response.status_code == 200:
    #             response.success()
    #         else:
    #             response.failure(f"請求失敗: {response.status_code} - {response.text}")
    
    @task(3)
    def send_notification_single(self):
        """發送單筆通知"""
        test_data = self.generate_test_data(1)
        
        with self.client.post(
            "/",
            json=test_data,
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"請求失敗: {response.status_code} - {response.text}")
