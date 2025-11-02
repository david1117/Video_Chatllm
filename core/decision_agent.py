"""
決策智能體
根據用戶輸入和文件，智能調度各模態工具的執行順序和組合
"""
import logging
from typing import Dict, List, Any, Optional
from enum import Enum
import re

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """任務類型枚舉"""
    TEXT_TO_IMAGE = "text_to_image"
    IMAGE_TO_IMAGE = "image_to_image"
    IMAGE_TO_VIDEO = "image_to_video"
    TEXT_TO_VIDEO = "text_to_video"
    FIRST_TO_LAST_FRAME = "first_to_last_frame"
    MULTIMODAL = "multimodal"
    BATCH_IMAGE_GENERATION = "batch_image_generation"


class DecisionAgent:
    """決策智能體類別"""
    
    def __init__(self):
        """初始化決策智能體"""
        self.task_queue: List[Dict[str, Any]] = []
        
        # 關鍵詞映射
        self.keywords = {
            'image_gen': ['生成圖片', '畫', '繪製', '創建圖像', '圖片', '插畫', 'image', 'picture', 'photo'],
            'image_transform': ['修改', '轉換', '改變', '調整', '編輯', 'transform', 'modify', 'edit', 'change'],
            'video_gen': ['視頻', '影片', '動畫', '動態', 'video', 'animation', 'motion'],
            'interpolation': ['首尾', '插值', '過渡', '中間幀', 'interpolate', 'transition', 'morph'],
        }
        
    def analyze_intent(self, message: str, file_count: int = 0, file_types: List[str] = None) -> Dict[str, Any]:
        """
        智能分析用戶意圖
        
        Args:
            message: 用戶消息
            file_count: 上傳文件數量
            file_types: 文件類型列表
            
        Returns:
            分析結果字典
        """
        logger.info(f"意圖分析開始: message='{message[:100]}...', file_count={file_count}")
        message_lower = message.lower()
        logger.info(f"轉換小寫後: message_lower='{message_lower[:100]}...'")
        
        # 基於規則的意圖識別
        task_type = self._determine_task_type(message_lower, file_count)
        logger.info(f"意圖識別結果: {task_type.value}")
        
        # 提取提示詞
        prompt = self._extract_prompt(message)
        logger.info(f"提示詞提取結果: '{prompt[:100]}...'")
        
        # 生成推理說明
        reasoning = self._generate_reasoning(task_type, message, file_count)
        logger.info(f"推理說明: {reasoning}")
        
        # 提取參數
        parameters = self._extract_parameters(message)
        logger.info(f"參數提取結果: {parameters}")
        
        result = {
            'taskType': task_type.value,
            'prompt': prompt,
            'fileCount': file_count,
            'reasoning': reasoning,
            'parameters': parameters,
            'confidence': self._calculate_confidence(message, file_count, task_type)
        }
        
        logger.info(f"最終意圖分析結果: {result}")
        return result
    
    def _determine_task_type(self, message: str, file_count: int) -> TaskType:
        """確定任務類型"""
        
        # 檢查是否包含批量生成關鍵詞（四張、四個等）
        batch_keywords = ['四張', '四個', '4張', '4個', 'four', '4', '多張', '多個', 'batch', '生成四', 'create four']
        has_batch_keyword = any(kw in message.lower() for kw in batch_keywords)
        
        # 檢查是否包含場景分割關鍵詞
        scene_keywords = ['場景一', '場景二', '場景三', '場景四', '第一張', '第二張', '第三張', '第四張']
        has_scene_keywords = any(kw in message for kw in scene_keywords)
        
        # 檢查是否包含視頻相關關鍵詞
        has_video_keyword = any(kw in message for kw in self.keywords['video_gen'])
        
        # 檢查是否包含插值關鍵詞
        has_interpolation_keyword = any(kw in message for kw in self.keywords['interpolation'])
        
        # 檢查是否包含圖片生成關鍵詞
        has_image_gen_keyword = any(kw in message for kw in self.keywords['image_gen'])
        
        # 檢查是否包含圖片轉換關鍵詞
        has_transform_keyword = any(kw in message for kw in self.keywords['image_transform'])
        
        # 添加調試輸出
        logger.info(f"意圖識別調試: file_count={file_count}, has_batch_keyword={has_batch_keyword}, has_scene_keywords={has_scene_keywords}")
        logger.info(f"批 量關鍵詞檢查: {[kw for kw in batch_keywords if kw.lower() in message.lower()]}")
        logger.info(f"場景關鍵詞檢查: {[kw for kw in scene_keywords if kw in message]}")
        
        # 決策邏輯 - 優先檢查批量生成
        if file_count == 1 and (has_batch_keyword or has_scene_keywords):
            # 上傳了1個文件且包含批量生成關鍵詞
            logger.info("識別為批量圖生圖任務")
            return TaskType.BATCH_IMAGE_GENERATION
                
        elif file_count == 0:
            # 沒有上傳文件
            if has_video_keyword:
                return TaskType.TEXT_TO_VIDEO
            else:
                return TaskType.TEXT_TO_IMAGE
                
        elif file_count == 1:
            # 上傳了1個文件
            if has_video_keyword:
                return TaskType.IMAGE_TO_VIDEO
            elif has_transform_keyword or has_image_gen_keyword:
                return TaskType.IMAGE_TO_IMAGE
            else:
                # 默認：如果有圖片就生成視頻，否則轉換圖片
                return TaskType.IMAGE_TO_VIDEO if has_video_keyword else TaskType.IMAGE_TO_IMAGE
                
        elif file_count == 2:
            # 上傳了2個文件
            if has_interpolation_keyword or '首' in message or '尾' in message:
                return TaskType.FIRST_TO_LAST_FRAME
            else:
                return TaskType.IMAGE_TO_IMAGE
                
        else:
            # 上傳了多個文件
            return TaskType.IMAGE_TO_IMAGE
    
    def _extract_prompt(self, message: str) -> str:
        """從消息中提取提示詞"""
        # 移除常見的指令詞
        instruction_words = [
            '幫我', '請', '生成', '創建', '製作', '畫', '繪製',
            'help', 'create', 'generate', 'make', 'draw'
        ]
        
        prompt = message
        for word in instruction_words:
            prompt = prompt.replace(word, '')
        
        # 清理多餘空格
        prompt = ' '.join(prompt.split())
        
        return prompt.strip()
    
    def _extract_parameters(self, message: str) -> Dict[str, Any]:
        """提取額外參數"""
        params = {}
        
        # 提取時長
        duration_match = re.search(r'(\d+)\s*秒|(\d+)\s*seconds?', message, re.IGNORECASE)
        if duration_match:
            duration = int(duration_match.group(1) or duration_match.group(2))
            params['duration'] = min(max(duration, 1), 10)  # 限制在1-10秒
        else:
            params['duration'] = 5  # 默認5秒
        
        # 提取尺寸 - 支持16:9、1920x1080等格式
        size_patterns = [
            r'(\d+)\s*[x×]\s*(\d+)',  # 1920x1080
            r'(\d+)\s*:\s*(\d+)',     # 16:9
            r'(\d+)\s*by\s*(\d+)'     # 16 by 9
        ]
        
        for pattern in size_patterns:
            size_match = re.search(pattern, message)
            if size_match:
                width, height = int(size_match.group(1)), int(size_match.group(2))
                params['size'] = f"{width}x{height}"
                break
        
        # 提取風格
        style_keywords = {
            'realistic': ['真實', '寫實', 'realistic', 'photorealistic'],
            'anime': ['動漫', '卡通', 'anime', 'cartoon'],
            'artistic': ['藝術', '繪畫', 'artistic', 'painting'],
            'cinematic': ['電影', '影視', 'cinematic', 'film']
        }
        
        for style, keywords in style_keywords.items():
            if any(kw in message.lower() for kw in keywords):
                params['style'] = style
                break
        
        return params
    
    def _generate_reasoning(self, task_type: TaskType, message: str, file_count: int) -> str:
        """生成推理說明"""
        reasons = []
        
        if file_count == 0:
            reasons.append("未上傳文件")
        else:
            reasons.append(f"上傳了 {file_count} 個文件")
        
        if task_type == TaskType.BATCH_IMAGE_GENERATION:
            reasons.append("包含批量生成關鍵詞（四張/四個/場景等）")
            reasons.append("需要參考圖片生成多個不同場景")
        
        if '視頻' in message or 'video' in message.lower():
            reasons.append("消息中包含視頻相關詞彙")
        
        if '圖片' in message or 'image' in message.lower():
            reasons.append("消息中包含圖片相關詞彙")
        
        if '首尾' in message or '插值' in message:
            reasons.append("消息中包含插值相關詞彙")
        
        reasoning = f"判斷為 {task_type.value}，因為: " + "、".join(reasons)
        
        return reasoning
    
    def _calculate_confidence(self, message: str, file_count: int, task_type: TaskType) -> float:
        """計算置信度"""
        confidence = 0.5  # 基礎置信度
        
        # 批量生成的置信度計算
        if task_type == TaskType.BATCH_IMAGE_GENERATION:
            batch_keywords = ['四張', '四個', '4張', '4個', 'four', '4', '多張', '多個', 'batch']
            if any(kw in message.lower() for kw in batch_keywords):
                confidence += 0.4
            
            scene_keywords = ['場景一', '場景二', '場景三', '場景四', '第一張', '第二張', '第三張', '第四張']
            if any(kw in message for kw in scene_keywords):
                confidence += 0.3
            
            if file_count == 1:
                confidence += 0.2
        
        # 如果有明確的關鍵詞，增加置信度
        elif task_type == TaskType.TEXT_TO_IMAGE:
            if any(kw in message for kw in self.keywords['image_gen']):
                confidence += 0.3
        
        elif task_type == TaskType.IMAGE_TO_VIDEO:
            if any(kw in message for kw in self.keywords['video_gen']):
                confidence += 0.3
        
        elif task_type == TaskType.FIRST_TO_LAST_FRAME:
            if any(kw in message for kw in self.keywords['interpolation']):
                confidence += 0.4
        
        # 如果文件數量匹配，增加置信度
        if task_type == TaskType.FIRST_TO_LAST_FRAME and file_count == 2:
            confidence += 0.2
        
        return min(confidence, 1.0)
    
    def plan_execution(self, intent_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        根據意圖數據規劃執行計劃
        
        Args:
            intent_data: 意圖分析結果
            
        Returns:
            執行計劃列表
        """
        task_type = intent_data.get('taskType')
        
        # 處理批量圖生圖任務
        if task_type == 'batch_image_generation':
            return self._plan_batch_generation(intent_data)
        
        execution_plan = [{
            'step': 1,
            'action': task_type,
            'parameters': {
                'prompt': intent_data.get('prompt'),
                'filePaths': intent_data.get('filePaths', []),
                **intent_data.get('parameters', {})
            },
            'description': self._get_action_description(task_type)
        }]
        
        return execution_plan
    
    def _plan_batch_generation(self, intent_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """規劃批量生成任務"""
        original_prompt = intent_data.get('prompt', '')
        file_paths = intent_data.get('filePaths', [])
        
        # 解析多個場景描述
        scenes = self._parse_scenes(original_prompt)
        
        execution_plan = []
        for i, scene_desc in enumerate(scenes, 1):
            execution_plan.append({
                'step': i,
                'action': 'image_to_image',
                'parameters': {
                    'prompt': scene_desc,
                    'filePaths': file_paths,
                    'is_batch': True,
                    'batch_index': i,
                    'total_batches': len(scenes)
                },
                'description': f'生成第{i}張場景圖：{scene_desc[:50]}...'
            })
        
        return execution_plan
    
    def _parse_scenes(self, prompt: str) -> List[str]:
        """解析場景描述"""
        scenes = []
        
        # 嘗試按場景分割
        scene_patterns = [
            r'場景[一二三四]：(.*?)(?=場景[一二三四]：|$)',
            r'場景(\d+)：(.*?)(?=場景\d+：|$)',
            r'第[一二三四]張：(.*?)(?=第[一二三四]張：|$)',
            r'第(\d+)張：(.*?)(?=第\d+張：|$)'
        ]
        
        for pattern in scene_patterns:
            matches = re.findall(pattern, prompt, re.DOTALL)
            if matches:
                for match in matches:
                    scene_text = match[1] if len(match) > 1 else match[0]
                    scene_text = scene_text.strip()
                    if scene_text:
                        scenes.append(scene_text)
                break
        
        # 如果沒有找到場景分割，嘗試按段落分割
        if not scenes:
            paragraphs = [p.strip() for p in prompt.split('\n') if p.strip()]
            if len(paragraphs) >= 2:
                # 假設第一段是參考描述，後面是各場景
                scenes = paragraphs[1:]
        
        return scenes[:4]  # 最多4個場景
    
    def _get_action_description(self, task_type: str) -> str:
        """獲取動作描述"""
        descriptions = {
            'text_to_image': '根據文字描述生成圖片',
            'image_to_image': '轉換/編輯上傳的圖片',
            'image_to_video': '將圖片轉換為動態視頻',
            'text_to_video': '根據文字描述生成視頻',
            'first_to_last_frame': '使用首尾兩幀生成完整視頻（插值）',
            'batch_image_generation': '參考圖片批量生成多張場景圖片'
        }
        
        return descriptions.get(task_type, '執行未知任務')
    
    def validate_input(self, task_type: str, message: str, file_count: int) -> Dict[str, Any]:
        """
        驗證輸入是否滿足任務要求
        
        Returns:
            {'valid': bool, 'errors': List[str]}
        """
        errors = []
        
        if task_type == 'batch_image_generation':
            if file_count == 0:
                errors.append('批量圖生圖需要上傳1張參考圖片')
            if not message or len(message.strip()) < 10:
                errors.append('請提供詳細的場景描述（至少10個字符）')
            
            # 檢查是否包含場景分割
            scene_keywords = ['場景一', '場景二', '場景三', '場景四', '第一張', '第二張', '第三張', '第四張']
            if not any(kw in message for kw in scene_keywords):
                errors.append('請用"場景一"、"場景二"等格式描述各個場景')
        
        elif task_type == 'text_to_image':
            if not message or len(message.strip()) < 3:
                errors.append('請提供有效的圖片描述（至少3個字符）')
        
        elif task_type == 'image_to_image':
            if file_count == 0:
                errors.append('圖生圖需要上傳至少1張圖片')
            if not message:
                errors.append('請說明要如何處理圖片')
        
        elif task_type == 'image_to_video':
            if file_count == 0:
                errors.append('圖生視頻需要上傳1張圖片')
        
        elif task_type == 'first_to_last_frame':
            if file_count < 2:
                errors.append('首尾幀插值需要上傳2張圖片')
        
        elif task_type == 'text_to_video':
            if not message or len(message.strip()) < 5:
                errors.append('請提供有效的視頻描述（至少5個字符）')
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }

