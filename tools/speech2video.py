"""
Wan2.2 S2V / Kling AI 語音生視頻工具
支持語音輸入轉換為視頻
"""
import requests
import logging
import base64
from typing import Optional, Dict, Any, BinaryIO
from config import settings
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class SpeechToVideoGenerator:
    """語音生視頻生成器"""
    
    def __init__(self, provider: str = "kling"):
        """
        初始化語音生視頻生成器
        
        Args:
            provider: 提供商 ('wan2' 或 'kling')
        """
        self.provider = provider
        
        if provider == "kling":
            self.api_key = settings.kling_api_key
            self.endpoint = settings.kling_endpoint
        else:
            self.api_key = settings.wan2_api_key
            self.endpoint = settings.wan2_endpoint
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def speech_to_video(self, audio_file: BinaryIO, prompt: str = "") -> Dict[str, Any]:
        """
        語音生視頻
        
        Args:
            audio_file: 音頻文件（二進制流）
            prompt: 額外描述（可選）
            
        Returns:
            包含任務信息和元數據的字典
        """
        if not self.api_key:
            raise ValueError(f"{self.provider} API key 未配置")
        
        try:
            # 讀取音頻數據
            audio_data = audio_file.read()
            audio_b64 = base64.b64encode(audio_data).decode()
            
            url = f"{self.endpoint}/v1/speech-to-video"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            # Kling AI 使用 JSON 格式
            if self.provider == "kling":
                payload = {
                    "audio": audio_b64,
                    "prompt": prompt,
                    "duration": 10  # 預設 10 秒
                }
                response = requests.post(url, headers=headers, json=payload, timeout=settings.timeout_seconds)
            
            # Wan2.2 使用 multipart/form-data
            else:
                files = {"audio": audio_file}
                data = {"prompt": prompt}
                response = requests.post(url, headers=headers, files=files, data=data, timeout=settings.timeout_seconds)
            
            response.raise_for_status()
            data = response.json()
            
            return {
                "task_id": data.get("task_id"),
                "status": "processing",
                "prompt": prompt,
                "provider": self.provider,
                "metadata": data.get("metadata", {})
            }
            
        except Exception as e:
            logger.error(f"{self.provider} 語音生視頻失敗: {e}")
            raise
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def text_to_video(self, text_prompt: str, audio_file: Optional[BinaryIO] = None) -> Dict[str, Any]:
        """
        文本生視頻（可選配語音）
        
        Args:
            text_prompt: 文本描述
            audio_file: 同步音頻（可選）
            
        Returns:
            任務信息
        """
        if not self.api_key:
            raise ValueError(f"{self.provider} API key 未配置")
        
        try:
            url = f"{self.endpoint}/v1/text-to-video"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            payload = {"prompt": text_prompt, "duration": 10}
            
            # 如果有音頻，添加到請求中
            if audio_file:
                audio_data = audio_file.read()
                audio_b64 = base64.b64encode(audio_data).decode()
                payload["audio"] = audio_b64
            
            response = requests.post(url, headers=headers, json=payload, timeout=settings.timeout_seconds)
            response.raise_for_status()
            
            data = response.json()
            
            return {
                "task_id": data.get("task_id"),
                "status": "processing",
                "prompt": text_prompt,
                "provider": self.provider,
                "metadata": data.get("metadata", {})
            }
            
        except Exception as e:
            logger.error(f"{self.provider} 文本生視頻失敗: {e}")
            raise
    
    def check_status(self, task_id: str) -> Dict[str, Any]:
        """
        檢查任務狀態
        
        Args:
            task_id: 任務ID
            
        Returns:
            狀態和結果數據
        """
        try:
            url = f"{self.endpoint}/v1/status/{task_id}"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            response = requests.get(url, headers=headers, timeout=settings.timeout_seconds)
            response.raise_for_status()
            
            data = response.json()
            
            result = {
                "task_id": task_id,
                "status": data.get("status"),
                "progress": data.get("progress", 0)
            }
            
            if data.get("status") == "completed":
                video_url = data.get("video_url")
                video_response = requests.get(video_url, timeout=settings.timeout_seconds)
                video_response.raise_for_status()
                
                result["video_data"] = video_response.content
                result["video_url"] = video_url
            
            return result
            
        except Exception as e:
            logger.error(f"檢查任務狀態失敗: {e}")
            raise

