"""Simple Telegram notifier using Bot API HTTP endpoint.

Sends Markdown-formatted messages to a chat_id.
"""
import os
import requests

class TelegramNotifier:
    def __init__(self, token: str = None, chat_id: str = None):
        # Use provided token/chat_id or read from environment variables BOT_TOKEN/CHAT_ID (fallback TELEGRAM_*)
        self.token = token or os.getenv('BOT_TOKEN') or os.getenv('TELEGRAM_TOKEN')
        self.chat_id = chat_id or os.getenv('CHAT_ID') or os.getenv('TELEGRAM_CHAT_ID')
        if not self.token:
            print('Warning: TELEGRAM token not set; messages will not be sent to Telegram.')

    async def send_message(self, chat_id_param: str, text: str = None):
        """Send a message to Telegram.

        Args:
            chat_id_param: Target chat ID (can be first or second param for compatibility)
            text: Message text (if None, assumes chat_id_param is the message and uses default chat_id)
        """
        # Handle both call styles: send_message(chat_id, text) and send_message(text)
        if text is None:
            text = chat_id_param
            target_chat = self.chat_id
        else:
            target_chat = chat_id_param

        if not self.token or not target_chat:
            print('--- Mensaje (no Telegram configurado) ---')
            print(text)
            print('----------------------------------------')
            return False

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            'chat_id': target_chat,
            'text': text,
            'parse_mode': 'Markdown'
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                return True
            else:
                print(f"Telegram send failed: {response.status_code} {response.text}")
                return False
        except Exception as e:
            print(f"Telegram exception: {e}")
            return False
