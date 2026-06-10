# 儲存路徑: 路由開發/app/utils/notifier.py
import os
import requests

class LineNotifier:
    @staticmethod
    def send_notification(message):
        """
        發送 LINE Notify 提醒
        :param message: 提醒文字內容
        :return: Boolean 是否成功
        """
        # 從環境變數讀取 LINE Notify Access Token
        token = os.environ.get('LINE_NOTIFY_TOKEN')
        if not token:
            # 未設定 Token 時，進行終端機模擬 Log 記錄，並防範 Windows 控制台 CP950 編碼不支援 Emoji 的問題
            try:
                print(f"[LINE Notify Simulated] {message}")
            except UnicodeEncodeError:
                import sys
                enc = sys.stdout.encoding or 'utf-8'
                safe_message = message.encode(enc, errors='replace').decode(enc)
                print(f"[LINE Notify Simulated] {safe_message}")
            return False
            
        url = 'https://notify-api.line.me/api/notify'
        headers = {
            'Authorization': f'Bearer {token}'
        }
        payload = {
            'message': message
        }
        
        try:
            response = requests.post(url, headers=headers, data=payload, timeout=5)
            if response.status_code == 200:
                print(f"[LINE Notify Success] {message}")
                return True
            else:
                print(f"[LINE Notify Error] Status {response.status_code}: {response.text}")
                return False
        except Exception as e:
            print(f"[LINE Notify Failed] Exception: {str(e)}")
            return False
