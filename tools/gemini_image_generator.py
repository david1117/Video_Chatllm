"""
使用 Gemini 2.5 Flash Image Preview 進行圖像生成
直接使用 Gemini Board API 進行文生圖
"""
from typing import Optional, Dict, Any
from PIL import Image
import io
from config import settings
import logging

# 使用新版 google.genai API
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None

logger = logging.getLogger(__name__)


def generate_image(text, images=None, api_key=None, model="gemini-2.5-flash-image-preview"):
    """
    使用 Gemini API 生成圖像
    
    Args:
        text: 文本描述
        images: 可選的參考圖片列表
        api_key: API 密鑰（可選，使用配置中的默認值）
        model: 使用的模型名稱
        
    Returns:
        生成的圖像對象
    """
    try:
        if not GENAI_AVAILABLE or genai is None:
            raise ImportError("google-genai 套件未安裝，請執行: pip install google-genai>=1.47.0")
        
        # 使用提供的 API Key 或配置中的默認值
        key = api_key or settings.gemini_api_key
        if not key or key == "demo_key":
            raise ValueError("請提供有效的 Gemini API Key")
        
        # 創建客戶端
        client = genai.Client(api_key=key)
        
        # 準備配置
        config = types.GenerateContentConfig(
            temperature=1,
            top_p=0.95,
            top_k=40,
            max_output_tokens=8192,
        )
        
        # 準備輸入內容
        contents = []
        if images:
            for img in images:
                if isinstance(img, Image.Image):
                    # PIL Image 轉換為 bytes
                    img_bytes = io.BytesIO()
                    img.save(img_bytes, format='PNG')
                    # 使用關鍵字參數
                    contents.append(types.Part.from_bytes(
                        data=img_bytes.getvalue(),
                        mime_type='image/png'
                    ))
                else:
                    contents.append(img)
        
        # 使用關鍵字參數
        contents.append(types.Part.from_text(text=text))
        
        # 生成內容
        logger.info(f"使用 {model} 生成內容: {text[:50]}...")
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=config
        )
        
        # 檢查候選內容是否存在
        if not response.candidates:
            error_message = "模型未返回任何候選內容。"
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                error_message += f" 原因: {response.prompt_feedback}"
            raise ValueError(error_message)

        # 調試：檢查響應內容
        logger.info(f"候選內容數量: {len(response.candidates)}")
        candidate = response.candidates[0]
        logger.info(f"Parts 數量: {len(candidate.content.parts)}")
        
        # 從候選內容中提取圖像數據
        image_data = None
        text_response = []
        
        for idx, part in enumerate(candidate.content.parts):
            logger.info(f"Part {idx}: has_inline_data={hasattr(part, 'inline_data')}, has_text={hasattr(part, 'text')}")
            
            if hasattr(part, 'inline_data') and part.inline_data:
                image_data = part.inline_data.data
                logger.info(f"✅ 找到圖像數據，大小: {len(image_data)} bytes")
                break
            elif hasattr(part, 'text') and part.text:
                text_response.append(part.text)
                logger.info(f"📝 找到文本: {part.text[:100]}")

        if image_data is None:
            error_msg = "模型回應中不包含有效的圖像數據。"
            if text_response:
                error_msg += f"\n模型返回的文本: {' '.join(text_response)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # 增加日誌記錄，檢查數據類型和內容
        logger.debug(f"Image data type: {type(image_data)}")
        logger.debug(f"Image data (first 50 bytes): {image_data[:50]}")

        # 轉換為 PIL Image
        image = Image.open(io.BytesIO(image_data))
        
        logger.info(f"圖像生成成功: {image.size}")
        
        return {
            "image": image,
            "image_data": image_data,
            "prompt": text,
            "width": image.width,
            "height": image.height,
            "format": "PNG",
            "model": model
        }
        
    except Exception as e:
        logger.error(f"Gemini 圖像生成失敗: {e}")
        raise


class GeminiImageGenerator:
    """Gemini 圖像生成器類別"""
    
    def __init__(self, model="gemini-2.5-flash-image-preview"):
        """
        初始化 Gemini 圖像生成器
        
        Args:
            model: 使用的模型名稱
        """
        if not GENAI_AVAILABLE or genai is None:
            logger.error("❌ google-genai 套件未安裝，圖像生成功能不可用")
            logger.info("💡 請執行: pip install google-genai>=1.47.0")
            raise ImportError("google-genai 套件未安裝")
        
        self.model = model
        self.api_key = settings.gemini_api_key
        
        if self.api_key and self.api_key != "demo_key":
            self.client = genai.Client(api_key=self.api_key)
            logger.info("✅ Gemini 圖像生成器初始化成功 (使用新版 google.genai API)")
        else:
            self.client = None
            logger.warning("⚠️ Gemini API Key 未配置，圖像生成功能將無法使用")
    
    def text_to_image(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        文本生成圖像
        
        Args:
            prompt: 圖像描述文本
            **kwargs: 其他參數
            
        Returns:
            包含圖像數據的字典
        """
        return generate_image(
            text=prompt,
            api_key=self.api_key,
            model=self.model
        )
    
    def image_with_reference(self, text: str, reference_images: list, **kwargs) -> Dict[str, Any]:
        """
        基於參考圖像生成新圖像
        
        Args:
            text: 描述文本
            reference_images: 參考圖片列表
            **kwargs: 其他參數
            
        Returns:
            包含圖像數據的字典
        """
        # 增強提示詞，明確告訴模型要生成圖像
        enhanced_prompt = f"請根據以下參考圖片生成一張新圖片。\n要求：{text}\n請直接生成圖片，不要返回文字描述。"
        
        logger.info(f"圖生圖任務 - 參考圖片數: {len(reference_images)}")
        logger.info(f"增強提示詞: {enhanced_prompt}")
        
        return generate_image(
            text=enhanced_prompt,
            images=reference_images,
            api_key=self.api_key,
            model=self.model
        )

