"""
Gemini API 对话核心引擎
提供自然语言理解、上下文管理和多轮对话功能
"""
import os
from typing import List, Dict, Optional, Any

# 显式加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed, using system environment variables only")

from typing import List, Dict, Optional, Any
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """系统配置类别"""
    
    # Gemini API
    gemini_api_key: Optional[str] = Field(default=None, env="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.0-flash-exp", env="GEMINI_MODEL")
    
    # VEO API (视频生成)
    veo_api_key: Optional[str] = Field(default=None, env="VEO_API_KEY")
    
    # System Settings
    max_retry_attempts: int = Field(default=3, env="MAX_RETRY_ATTEMPTS")
    timeout_seconds: int = Field(default=30, env="TIMEOUT_SECONDS")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# 使用新版 google.genai API
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None

class GeminiEngine:
    """Gemini 对话引擎"""
    
    def __init__(self):
        """初始化 Gemini API"""
        if not GENAI_AVAILABLE or genai is None:
            logger.error("❌ google-genai 套件未安装，对话功能不可用")
            logger.info("💡 请执行: pip install google-genai>=1.47.0")
            raise ImportError("google-genai 套件未安装，请执行: pip install google-genai>=1.47.0")
        
        # 初始化配置
        self.settings = Settings()
        
        # 获取API key - 按优先级从多个来源获取
        api_key = None
        if self.settings.gemini_api_key:
            api_key = self.settings.gemini_api_key
        else:
            # 直接从环境变量获取
            api_key = os.getenv('GEMINI_API_KEY')
        
        if not api_key:
            raise ValueError("❌ 未找到 GEMINI_API_KEY，请检查.env文件或环境变量")
        
        # 打印调试信息（隐藏API key）
        logger.info(f"✅ 找到API Key: {api_key[:8]}...{api_key[-4:]}")
        
        # 使用新版 API Client
        try:
            self.client = genai.Client(api_key=api_key)
            self.model_name = self.settings.gemini_model
            self.conversation_history: List[Dict[str, str]] = []
            logger.info("✅ Gemini 对话引擎初始化成功 (使用新版 google.genai API)")
        except Exception as e:
            logger.error(f"❌ Gemini客户端初始化失败: {e}")
            raise ValueError(f"Gemini API 初始化失败: {e}")
        
    def chat(self, user_input: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        处理用户输入并返回回应
        
        Args:
            user_input: 用户输入
            system_prompt: 系统提示词（可选）
            
        Returns:
            包含回应和元数据的字典
        """
        try:
            # 构建对话内容
            contents = []
            
            if system_prompt:
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part(text=system_prompt)]
                ))
                contents.append(types.Content(
                    role="model",
                    parts=[types.Part(text="理解，我会协助您完成各种创作任务。")]
                ))
            
            # 添加历史对话
            for msg in self.conversation_history[-10:]:  # 保留最近10轮对话
                contents.append(types.Content(
                    role=msg["role"],
                    parts=[types.Part(text=msg["parts"])]
                ))
            
            # 添加当前输入
            contents.append(types.Content(
                role="user",
                parts=[types.Part(text=user_input)]
            ))
            
            # 调用 Gemini API (新版)
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents
            )
            
            # 提取回应
            response_text = response.text
            
            # 更新对话历史
            self.conversation_history.append({"role": "user", "parts": user_input})
            self.conversation_history.append({"role": "model", "parts": response_text})
            
            # 处理 metadata
            metadata = {}
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                try:
                    metadata = {
                        "prompt_token_count": getattr(response.usage_metadata, 'prompt_token_count', 0),
                        "candidates_token_count": getattr(response.usage_metadata, 'candidates_token_count', 0),
                        "total_token_count": getattr(response.usage_metadata, 'total_token_count', 0)
                    }
                except:
                    metadata = {}
            
            return {
                "response": response_text,
                "task_type": self._detect_task_type(user_input, response_text),
                "confidence": self._calculate_confidence(response),
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Gemini API 调用失败: {e}")
            raise
    
    def _detect_task_type(self, user_input: str, response: str) -> str:
        """
        检测任务类型
        
        Returns:
            任务类型: 'text_gen' | 'image_gen' | 'video_gen' | 'speech2video' | 'multimodal'
        """
        input_lower = user_input.lower()
        response_lower = response.lower()
        
        # 图像生成关键词
        if any(word in input_lower for word in ['画', '生成图片', 'image', '图', '图片', '插图']):
            return 'image_gen'
        
        # 视频生成关键词
        if any(word in input_lower for word in ['视频', '短片', '动画', 'video', '影片']):
            if any(word in input_lower for word in ['语音', '声音', 'speech', 'audio', '配音']):
                return 'speech2video'
            elif any(word in input_lower for word in ['图片', 'image', '图']):
                return 'video_gen'
        
        # 多模态任务
        if any(word in input_lower for word in ['完整', '全套', '整体', '流程']):
            return 'multimodal'
        
        # 默认为文本生成
        return 'text_gen'
    
    def _calculate_confidence(self, response: Any) -> float:
        """
        计算回应的信心度
        
        Returns:
            0.0 到 1.0 之间的信度值
        """
        # 基于回应长度和内容质量计算信度
        text = response.text if hasattr(response, 'text') else ""
        if len(text) < 10:
            return 0.3
        elif len(text) > 100:
            return 0.9
        else:
            return 0.5 + (len(text) / 100) * 0.4
    
    def clear_history(self):
        """清除对话历史"""
        self.conversation_history = []
        logger.info("对话历史已清除")
    
    def get_history_summary(self) -> str:
        """获取对话历史摘要"""
        if not self.conversation_history:
            return "没有对话历史"
        
        summary = f"共 {len(self.conversation_history)} 轮对话\n"
        summary += f"最后一轮: {self.conversation_history[-2]['parts'][:50]}..."
        return summary