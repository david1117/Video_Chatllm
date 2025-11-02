"""
Veo3.1 視頻生成工具
使用 Google GenAI API 進行視頻生成
"""
import time
import logging
import os
from typing import Optional, Dict, Any
from config import settings
import base64
from io import BytesIO

# 嘗試導入 google.genai，如果失敗則使用替代方案
try:
    from google import genai
    from google.genai import types
    GOOGLE_GENAI_AVAILABLE = True
except ImportError:
    try:
        import google.generativeai as genai
        GOOGLE_GENAI_AVAILABLE = True
    except ImportError:
        GOOGLE_GENAI_AVAILABLE = False

logger = logging.getLogger(__name__)


class Veo3VideoGenerator:
    """Veo3.1 視頻生成器"""
    
    def __init__(self):
        """初始化 Veo3.1 API"""
        # 從 config 讀取 API key
        self.api_key = settings.veo_api_key
        
        self.client = None
        self.use_legacy_api = False
        
        if not self.api_key:
            logger.error("❌ API key 未配置！請在 .env 文件中設置 VEO_API_KEY 或 GEMINI_API_KEY")
            return
            
        if not GOOGLE_GENAI_AVAILABLE:
            logger.error("❌ google-genai 套件未安裝")
            return
            
        try:
            # 嘗試使用新版 API (google.genai)
            if hasattr(genai, 'Client'):
                self.client = genai.Client(api_key=self.api_key)
                self.use_legacy_api = False
                logger.info("✅ Veo3.1 客戶端初始化成功 (使用新版 google.genai API)")
            # 使用舊版 API (google.generativeai)
            elif hasattr(genai, 'configure'):
                genai.configure(api_key=self.api_key)
                # 對於舊版 API，使用 genai 模塊本身作為 client
                self.client = genai
                self.use_legacy_api = True
                logger.info("✅ Veo3.1 API 配置成功 (使用舊版 google.generativeai API)")
                logger.info("📝 注意: 舊版 API 可能不支援 Veo 視頻生成功能，建議升級到新版")
            else:
                logger.error("❌ 無法找到可用的 GenAI API 接口")
        except Exception as e:
            logger.error(f"❌ 初始化失敗: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def generate_video(self, prompt: str, duration: int = 10, timeout: int = 300) -> Dict[str, Any]:
        """
        使用 Veo3.1 生成視頻
        
        Args:
            prompt: 視頻描述文本
            duration: 視頻時長（秒）
            timeout: 超時時間（秒）
            
        Returns:
            包含視頻數據和元數據的字典
        """
        if not self.client:
            raise ValueError("Veo3.1 API key 未配置")
        
        try:
            logger.info(f"開始生成視頻: {prompt[:50]}...")
            
            # 創建生成視頻的操作
            operation = self.client.models.generate_videos(
                model="veo-3.1-generate-preview",
                prompt=prompt,
            )
            
            logger.info(f"視頻生成任務已創建，等待完成...")
            
            # 輪詢操作狀態直到完成
            start_time = time.time()
            while not operation.done:
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    raise TimeoutError(f"視頻生成超時（超過 {timeout} 秒）")
                
                logger.info(f"等待視頻生成完成... ({elapsed:.0f}s)")
                time.sleep(10)
                operation = self.client.operations.get(operation)
            
            elapsed = time.time() - start_time
            
            # 獲取生成的視頻
            if not operation.response or not operation.response.generated_videos:
                raise ValueError("視頻生成完成但未返回視頻數據")
            
            generated_video = operation.response.generated_videos[0]
            
            # 下載視頻
            video_file = generated_video.video
            self.client.files.download(file=video_file)
            
            # 確保 outputs 目錄存在
            os.makedirs('outputs', exist_ok=True)
            
            # 保存視頻到 outputs 目錄
            output_filename = f"generated_video_{int(time.time())}.mp4"
            output_path = os.path.join('outputs', output_filename)
            video_file.save(output_path)
            
            logger.info(f"視頻生成成功並保存到: {output_path}")
            
            return {
                "success": True,
                "video_file": output_filename,
                "video_object": video_file,
                "prompt": prompt,
                "duration": duration,
                "metadata": {
                    "operation_name": operation.name,
                    "generation_time": elapsed
                }
            }
            
        except Exception as e:
            logger.error(f"Veo3.1 視頻生成失敗: {e}")
            raise
    
    def image_to_video(self, image, prompt: str = "", duration: int = 5, timeout: int = 300) -> Dict[str, Any]:
        """
        圖生視頻
        
        Args:
            image: 輸入圖片 (PIL Image object)
            prompt: 視頻描述
            duration: 視頻時長
            timeout: 超時時間（秒）
            
        Returns:
            生成結果
        """
        if not self.client:
            raise ValueError("Veo3.1 API key 未配置")

        try:
            logger.info(f"開始從圖片生成視頻: {prompt[:50] if prompt else '(無提示詞)'}...")

            # 1. 將 PIL Image 轉換為 bytes
            buffered = BytesIO()
            image_format = image.format or 'PNG'
            image.save(buffered, format=image_format)
            img_bytes = buffered.getvalue()
            
            # 確定 MIME 類型
            mime_type = f"image/{image_format.lower()}"
            if image_format.upper() == 'JPEG' or image_format.upper() == 'JPG':
                mime_type = "image/jpeg"
            elif image_format.upper() == 'PNG':
                mime_type = "image/png"

            logger.info(f"圖片準備完成: {len(img_bytes)} 字節, MIME: {mime_type}")

            # 2. 構建參考圖片對象 - 直接使用 image_bytes (不需要上傳文件)
            # Gemini API 不支持 gcs_uri，只能用 image_bytes
            reference_image = types.VideoGenerationReferenceImage(
                image=types.Image(
                    image_bytes=img_bytes,
                    mime_type=mime_type
                ),
                reference_type=types.VideoGenerationReferenceType.ASSET  # 使用 ASSET 類型
            )
            
            logger.info("✅ 參考圖片對象創建成功")
            
            # 3. 創建生成視頻的操作
            operation = self.client.models.generate_videos(
                model="veo-3.1-generate-preview",
                prompt=prompt,
                config=types.GenerateVideosConfig(
                    reference_images=[reference_image],
                ),
            )

            logger.info(f"視頻生成任務已創建，等待完成...")

            # 輪詢操作狀態直到完成
            start_time = time.time()
            while not operation.done:
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    raise TimeoutError(f"視頻生成超時（超過 {timeout} 秒）")
                
                logger.info(f"等待視頻生成完成... ({elapsed:.0f}s)")
                time.sleep(10)
                operation = self.client.operations.get(operation)
            
            elapsed = time.time() - start_time
            
            # 獲取生成的視頻
            if not operation.response or not operation.response.generated_videos:
                raise ValueError("視頻生成完成但未返回視頻數據")
            
            generated_video = operation.response.generated_videos[0]
            
            # 下載視頻
            video_file = generated_video.video
            self.client.files.download(file=video_file)
            
            # 確保 outputs 目錄存在
            os.makedirs('outputs', exist_ok=True)
            
            # 保存視頻到 outputs 目錄
            output_filename = f"generated_video_{int(time.time())}.mp4"
            output_path = os.path.join('outputs', output_filename)
            video_file.save(output_path)
            
            logger.info(f"視頻生成成功並保存到: {output_path}")
            
            return {
                "success": True,
                "video_file": output_filename,
                "video_object": video_file,
                "prompt": prompt,
                "duration": duration,
                "metadata": {
                    "operation_name": operation.name,
                    "generation_time": elapsed
                }
            }

        except Exception as e:
            logger.error(f"Veo3.1 圖生視頻失敗: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    def first_to_last_frame(self, first_image, last_image, prompt: str = "", duration: int = 5, timeout: int = 300) -> Dict[str, Any]:
        """
        首尾幀插值生成視頻
        
        Args:
            first_image: 首幀圖片 (PIL Image object)
            last_image: 尾幀圖片 (PIL Image object)
            prompt: 視頻描述 (可選)
            duration: 視頻時長
            timeout: 超時時間（秒）
            
        Returns:
            生成結果
        """
        if not self.client:
            raise ValueError("Veo3.1 API key 未配置")

        try:
            logger.info(f"開始首尾幀插值生成視頻: {prompt[:50] if prompt else '(無提示詞)'}...")

            # 1. 轉換首幀圖片為 bytes
            buffered_first = BytesIO()
            first_format = first_image.format or 'PNG'
            first_image.save(buffered_first, format=first_format)
            first_img_bytes = buffered_first.getvalue()
            
            first_mime_type = f"image/{first_format.lower()}"
            if first_format.upper() in ['JPEG', 'JPG']:
                first_mime_type = "image/jpeg"
            elif first_format.upper() == 'PNG':
                first_mime_type = "image/png"

            # 2. 轉換尾幀圖片為 bytes
            buffered_last = BytesIO()
            last_format = last_image.format or 'PNG'
            last_image.save(buffered_last, format=last_format)
            last_img_bytes = buffered_last.getvalue()
            
            last_mime_type = f"image/{last_format.lower()}"
            if last_format.upper() in ['JPEG', 'JPG']:
                last_mime_type = "image/jpeg"
            elif last_format.upper() == 'PNG':
                last_mime_type = "image/png"

            logger.info(f"首幀準備完成: {len(first_img_bytes)} 字節, MIME: {first_mime_type}")
            logger.info(f"尾幀準備完成: {len(last_img_bytes)} 字節, MIME: {last_mime_type}")

            # 3. 構建首幀和尾幀的 Image 對象
            first_frame = types.Image(
                image_bytes=first_img_bytes,
                mime_type=first_mime_type
            )
            
            last_frame = types.Image(
                image_bytes=last_img_bytes,
                mime_type=last_mime_type
            )
            
            logger.info("✅ 首尾幀對象創建成功")
            
            # 4. 創建生成視頻的操作，使用首尾幀插值
            # 注意: image (首幀) 作為方法參數,last_frame (尾幀) 放在 config 中
            operation = self.client.models.generate_videos(
                model="veo-3.1-generate-preview",
                prompt=prompt,
                image=first_frame,  # 首幀作為方法參數
                config=types.GenerateVideosConfig(
                    last_frame=last_frame,  # 尾幀在 config 中
                ),
            )

            logger.info(f"視頻生成任務已創建，等待完成...")

            # 輪詢操作狀態直到完成
            start_time = time.time()
            while not operation.done:
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    raise TimeoutError(f"視頻生成超時（超過 {timeout} 秒）")
                
                logger.info(f"等待視頻生成完成... ({elapsed:.0f}s)")
                time.sleep(10)
                operation = self.client.operations.get(operation)
            
            elapsed = time.time() - start_time
            
            # 添加詳細的調試信息
            logger.info(f"✅ 首尾幀插值任務完成! 耗時: {elapsed:.2f}秒")
            logger.info(f"Operation 狀態: done={operation.done}")
            logger.info(f"Operation 名稱: {operation.name}")
            
            # 檢查 operation 是否有錯誤
            if hasattr(operation, 'error') and operation.error:
                logger.error(f"❌ 視頻生成失敗，API 返回錯誤: {operation.error}")
                raise ValueError(f"視頻生成失敗: {operation.error}")
            
            # 檢查響應結構
            logger.info(f"Operation response 類型: {type(operation.response)}")
            if operation.response:
                logger.info(f"Response 屬性: {dir(operation.response)}")
                if hasattr(operation.response, 'generated_videos'):
                    logger.info(f"Generated videos 長度: {len(operation.response.generated_videos) if operation.response.generated_videos else 0}")
            
            # 獲取生成的視頻
            if not operation.response or not operation.response.generated_videos:
                logger.error("❌ 未找到視頻數據")
                logger.error(f"Response 內容: {operation.response}")
                raise ValueError("視頻生成完成但未返回視頻數據")
            
            generated_video = operation.response.generated_videos[0]
            
            # 下載視頻
            video_file = generated_video.video
            self.client.files.download(file=video_file)
            
            # 確保 outputs 目錄存在
            os.makedirs('outputs', exist_ok=True)
            
            # 保存視頻到 outputs 目錄
            output_filename = f"generated_video_{int(time.time())}.mp4"
            output_path = os.path.join('outputs', output_filename)
            video_file.save(output_path)
            
            logger.info(f"首尾幀插值視頻生成成功並保存到: {output_path}")
            
            return {
                "success": True,
                "video_file": output_filename,
                "video_object": video_file,
                "prompt": prompt,
                "duration": duration,
                "metadata": {
                    "operation_name": operation.name,
                    "generation_time": elapsed
                }
            }

        except Exception as e:
            logger.error(f"Veo3.1 首尾幀插值失敗: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    def check_video_status(self, operation_name: str, timeout: int = 300) -> Dict[str, Any]:
        """
        檢查視頻狀態
        
        Args:
            operation_name: 視頻生成任務名稱
            timeout: 超時時間（秒）
            
        Returns:
            包含視頻數據和元數據的字典
        """
        if not self.client:
            raise ValueError("Veo3.1 API key 未配置")

        try:
            logger.info(f"檢查視頻狀態: {operation_name}")
            
            # 獲取操作狀態
            operation = self.client.operations.get(operation_name)
            
            logger.info(f"檢查任務狀態...")
            
            # 輪詢操作狀態直到完成
            start_time = time.time()
            while not operation.done:
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    raise TimeoutError(f"視頻生成超時（超過 {timeout} 秒）")
                
                logger.info(f"等待視頻生成完成... ({elapsed:.0f}s)")
                time.sleep(10)
                operation = self.client.operations.get(operation_name)
            
            elapsed = time.time() - start_time
            
            # 獲取生成的視頻
            if not operation.response or not operation.response.generated_videos:
                raise ValueError("視頻生成完成但未返回視頻數據")
            
            generated_video = operation.response.generated_videos[0]
            
            # 下載視頻
            video_file = generated_video.video
            self.client.files.download(file=video_file)
            
            # 確保 outputs 目錄存在
            os.makedirs('outputs', exist_ok=True)
            
            # 保存視頻到 outputs 目錄
            output_filename = f"generated_video_{int(time.time())}.mp4"
            output_path = os.path.join('outputs', output_filename)
            video_file.save(output_path)
            
            logger.info(f"視頻生成成功並保存到: {output_path}")
            
            return {
                "success": True,
                "video_file": output_filename,
                "video_object": video_file,
                "metadata": {
                    "operation_name": operation.name,
                    "generation_time": elapsed
                }
            }
            
        except Exception as e:
            logger.error(f"檢查視頻狀態失敗: {e}")
            raise