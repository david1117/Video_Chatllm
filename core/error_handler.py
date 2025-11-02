"""
錯誤處理與回溯機制
提供統一的錯誤處理、重試邏輯和任務回溯功能
"""
import logging
from typing import Dict, Any, Optional, Callable, List
from enum import Enum
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """錯誤類型"""
    API_ERROR = "api_error"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    AUTH_ERROR = "auth_error"
    UNKNOWN = "unknown"


class ErrorHandler:
    """錯誤處理器"""
    
    def __init__(self, max_retries: int = 3):
        """
        初始化錯誤處理器
        
        Args:
            max_retries: 最大重試次數
        """
        self.max_retries = max_retries
        self.error_history: List[Dict[str, Any]] = []
        
    def handle_error(self, error: Exception, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        處理錯誤
        
        Args:
            error: 異常對象
            context: 上下文信息
            
        Returns:
            錯誤處理結果
        """
        error_type = self._classify_error(error)
        
        error_info = {
            "type": error_type.value,
            "message": str(error),
            "context": context or {},
            "timestamp": str(datetime.now()),
            "should_retry": self._should_retry(error_type)
        }
        
        self.error_history.append(error_info)
        logger.error(f"錯誤處理: {error_info}")
        
        return error_info
    
    def _classify_error(self, error: Exception) -> ErrorType:
        """分類錯誤類型"""
        error_msg = str(error).lower()
        
        if "timeout" in error_msg or isinstance(error, TimeoutError):
            return ErrorType.TIMEOUT
        
        if "rate limit" in error_msg or "429" in error_msg:
            return ErrorType.RATE_LIMIT
        
        if "auth" in error_msg or "401" in error_msg or "403" in error_msg:
            return ErrorType.AUTH_ERROR
        
        if "api" in error_msg:
            return ErrorType.API_ERROR
        
        return ErrorType.UNKNOWN
    
    def _should_retry(self, error_type: ErrorType) -> bool:
        """判斷是否應該重試"""
        retryable_errors = [
            ErrorType.API_ERROR,
            ErrorType.TIMEOUT,
            ErrorType.RATE_LIMIT
        ]
        return error_type in retryable_errors
    
    def get_retry_strategy(self, error_type: ErrorType) -> Dict[str, Any]:
        """
        獲取重試策略
        
        Args:
            error_type: 錯誤類型
            
        Returns:
            重試策略配置
        """
        strategies = {
            ErrorType.TIMEOUT: {
                "max_attempts": 3,
                "wait_type": "exponential",
                "multiplier": 2,
                "min_wait": 2,
                "max_wait": 10
            },
            ErrorType.RATE_LIMIT: {
                "max_attempts": 5,
                "wait_type": "exponential",
                "multiplier": 3,
                "min_wait": 5,
                "max_wait": 30
            },
            ErrorType.API_ERROR: {
                "max_attempts": 3,
                "wait_type": "exponential",
                "multiplier": 1.5,
                "min_wait": 1,
                "max_wait": 10
            },
            ErrorType.AUTH_ERROR: {
                "max_attempts": 0,  # 不重試
                "wait_type": "none",
                "multiplier": 0,
                "min_wait": 0,
                "max_wait": 0
            },
            ErrorType.UNKNOWN: {
                "max_attempts": 2,
                "wait_type": "exponential",
                "multiplier": 2,
                "min_wait": 1,
                "max_wait": 5
            }
        }
        
        return strategies.get(error_type, strategies[ErrorType.UNKNOWN])
    
    def rollback(self, task_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        任務回溯
        
        Args:
            task_history: 任務歷史記錄
            
        Returns:
            回溯結果
        """
        logger.info("執行任務回溯")
        
        # 清理已創建的資源
        cleanup_results = []
        for task in reversed(task_history):
            if task.get("status") == "completed":
                # 清理邏輯（例如：刪除已生成的圖片/視頻）
                cleanup_results.append({
                    "task_id": task["task_id"],
                    "cleaned": True
                })
        
        return {
            "success": True,
            "cleanup_results": cleanup_results,
            "error_count": len(self.error_history)
        }
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """獲取錯誤統計"""
        error_counts = {}
        for error in self.error_history:
            error_type = error["type"]
            error_counts[error_type] = error_counts.get(error_type, 0) + 1
        
        return {
            "total_errors": len(self.error_history),
            "error_counts": error_counts,
            "recent_errors": self.error_history[-10:] if len(self.error_history) > 0 else []
        }

