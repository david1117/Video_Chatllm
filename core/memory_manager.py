"""
記憶管理系統
維護對話歷史、任務狀態和用戶偏好
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class MemoryManager:
    """記憶管理器"""
    
    def __init__(self, memory_file: str = "memory.json"):
        """
        初始化記憶管理器
        
        Args:
            memory_file: 記憶持久化文件路徑
        """
        self.memory_file = Path(memory_file)
        self.memory: Dict[str, Any] = self._load_memory()
        
    def _load_memory(self) -> Dict[str, Any]:
        """從文件加載記憶"""
        if self.memory_file.exists():
            try:
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加載記憶失敗: {e}")
        
        # 返回默認結構
        return {
            "conversations": {},
            "tasks": {},
            "user_preferences": {},
            "last_updated": datetime.now().isoformat()
        }
    
    def _save_memory(self):
        """保存記憶到文件"""
        try:
            self.memory["last_updated"] = datetime.now().isoformat()
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.memory, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存記憶失敗: {e}")
    
    def add_conversation(self, session_id: str, user_input: str, response: str, metadata: Dict[str, Any] = None):
        """
        添加對話記錄
        
        Args:
            session_id: 會話ID
            user_input: 用戶輸入
            response: 系統回應
            metadata: 元數據
        """
        if session_id not in self.memory["conversations"]:
            self.memory["conversations"][session_id] = []
        
        self.memory["conversations"][session_id].append({
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input,
            "response": response,
            "metadata": metadata or {}
        })
        
        # 限制會話歷史長度（保留最近 100 條）
        if len(self.memory["conversations"][session_id]) > 100:
            self.memory["conversations"][session_id] = self.memory["conversations"][session_id][-100:]
        
        self._save_memory()
    
    def get_conversation_history(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        獲取對話歷史
        
        Args:
            session_id: 會話ID
            limit: 返回的記錄數
            
        Returns:
            對話歷史列表
        """
        if session_id not in self.memory["conversations"]:
            return []
        
        return self.memory["conversations"][session_id][-limit:]
    
    def add_task(self, task_id: str, task_info: Dict[str, Any]):
        """
        添加任務記錄
        
        Args:
            task_id: 任務ID
            task_info: 任務信息
        """
        self.memory["tasks"][task_id] = {
            **task_info,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        self._save_memory()
    
    def update_task_status(self, task_id: str, status: str, result: Any = None):
        """
        更新任務狀態
        
        Args:
            task_id: 任務ID
            status: 新狀態
            result: 任務結果（可選）
        """
        if task_id in self.memory["tasks"]:
            self.memory["tasks"][task_id]["status"] = status
            self.memory["tasks"][task_id]["updated_at"] = datetime.now().isoformat()
            
            if result is not None:
                self.memory["tasks"][task_id]["result"] = result
            
            self._save_memory()
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        獲取任務信息
        
        Args:
            task_id: 任務ID
            
        Returns:
            任務信息或 None
        """
        return self.memory["tasks"].get(task_id)
    
    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        獲取用戶偏好
        
        Args:
            user_id: 用戶ID
            
        Returns:
            用戶偏好設置
        """
        return self.memory["user_preferences"].get(user_id, {
            "image_size": "1024x1024",
            "image_style": "realistic",
            "video_duration": 5,
            "provider": "kling"
        })
    
    def update_user_preferences(self, user_id: str, preferences: Dict[str, Any]):
        """
        更新用戶偏好
        
        Args:
            user_id: 用戶ID
            preferences: 偏好設置
        """
        if user_id not in self.memory["user_preferences"]:
            self.memory["user_preferences"][user_id] = {}
        
        self.memory["user_preferences"][user_id].update(preferences)
        self._save_memory()
    
    def clear_session(self, session_id: str):
        """
        清除會話歷史
        
        Args:
            session_id: 會話ID
        """
        if session_id in self.memory["conversations"]:
            del self.memory["conversations"][session_id]
            self._save_memory()
    
    def get_statistics(self) -> Dict[str, Any]:
        """獲取統計信息"""
        return {
            "total_conversations": len(self.memory["conversations"]),
            "total_tasks": len(self.memory["tasks"]),
            "total_users": len(self.memory["user_preferences"]),
            "last_updated": self.memory["last_updated"]
        }

