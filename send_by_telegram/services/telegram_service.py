# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging
import requests

from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/{method}"


class TelegramService:
    """Service class for Telegram Bot API interactions."""

    def __init__(self, token):
        """Initialize the Telegram service with bot token.
        
        Args:
            token (str): Telegram bot token from @BotFather
        """
        self.token = token
        if not self.token:
            raise UserError(_("Telegram bot token is not configured. "
                            "Please configure it in Settings."))

    def _make_request(self, method, data=None, files=None):
        """Make a request to Telegram Bot API.
        
        Args:
            method (str): API method name (e.g., 'sendMessage', 'sendDocument')
            data (dict): Request parameters
            files (dict): Files to upload
            
        Returns:
            dict: API response
            
        Raises:
            UserError: If API request fails
        """
        url = TELEGRAM_API_URL.format(token=self.token, method=method)
        
        try:
            if files:
                response = requests.post(url, data=data, files=files, timeout=30)
            else:
                response = requests.post(url, json=data, timeout=30)
            
            result = response.json()
            
            if not result.get('ok'):
                error_description = result.get('description', 'Unknown error')
                _logger.error("Telegram API error: %s", error_description)
                raise UserError(_("Telegram API error: %s") % error_description)
            
            return result
            
        except requests.exceptions.Timeout:
            _logger.error("Telegram API timeout")
            raise UserError(_("Telegram API request timed out. Please try again."))
        except requests.exceptions.ConnectionError:
            _logger.error("Telegram API connection error")
            raise UserError(_("Could not connect to Telegram API. "
                            "Please check your internet connection."))
        except json.JSONDecodeError:
            _logger.error("Invalid response from Telegram API")
            raise UserError(_("Invalid response from Telegram API."))

    def test_connection(self):
        """Test the bot token by calling getMe.
        
        Returns:
            dict: Bot information including username
            
        Raises:
            UserError: If token is invalid
        """
        result = self._make_request('getMe')
        return result.get('result', {})

    def send_message(self, chat_id, text, parse_mode='HTML'):
        """Send a text message to a chat/group.
        
        Args:
            chat_id (str|int): Telegram chat/group ID
            text (str): Message text
            parse_mode (str): Text formatting mode ('HTML' or 'Markdown')
            
        Returns:
            dict: Sent message info
        """
        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode,
        }
        result = self._make_request('sendMessage', data)
        return result.get('result', {})

    def send_document(self, chat_id, document_content, filename, caption=None, mimetype=None):
        """Send a document (PDF, etc.) to a chat/group.
        
        Args:
            chat_id (str|int): Telegram chat/group ID
            document_content (bytes): File content
            filename (str): File name
            caption (str): Optional caption text
            mimetype (str): File MIME type
            
        Returns:
            dict: Sent message info
        """
        data = {
            'chat_id': chat_id,
        }
        if caption:
            data['caption'] = caption
            data['parse_mode'] = 'HTML'
        
        content_type = mimetype or 'application/octet-stream'
        files = {
            'document': (filename, document_content, content_type),
        }
        
        result = self._make_request('sendDocument', data, files)
        return result.get('result', {})

    def send_photo(self, chat_id, photo_content, filename, caption=None):
        """Send a photo with preview to a chat/group.
        
        Args:
            chat_id (str|int): Telegram chat/group ID
            photo_content (bytes): Image file content
            filename (str): File name
            caption (str): Optional caption text
            
        Returns:
            dict: Sent message info
        """
        data = {
            'chat_id': chat_id,
        }
        if caption:
            data['caption'] = caption
            data['parse_mode'] = 'HTML'
        
        files = {
            'photo': (filename, photo_content, 'image/jpeg'),
        }
        
        result = self._make_request('sendPhoto', data, files)
        return result.get('result', {})
