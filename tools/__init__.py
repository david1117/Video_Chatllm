def __init__(self):
    """初始化 Veo3.1 API"""
    self.api_key = settings.veo_api_key
    if not self.api_key:
        logger.info("Veo API key not set, falling back to Gemini API key.")
        self.api_key = settings.gemini_api_key

    self.client = None
    
    # 檢查 API key 是否存在
    if not self.api_key:
        logger.error("❌ API key 未配置！請設置 VEO_API_KEY 或 GEMINI_API_KEY 環境變數")
        return
    
    # 檢查 google-genai 套件是否可用
    if not GOOGLE_GENAI_AVAILABLE:
        logger.error("❌ google-genai 套件未安裝，請執行: pip install google-genai")
        return
    
    try:
        if hasattr(genai, 'Client'):
            # Preferred new-style client
            self.client = genai.Client(api_key=self.api_key)
            logger.info("✅ Veo3.1 客戶端初始化成功 (new-style)")
        else:
            # If the installed package exposes a configure-style API
            if hasattr(genai, 'configure'):
                try:
                    genai.configure(api_key=self.api_key)
                    logger.warning("⚠️ 已配置 google generative API（configure），但未創建統一 client 對象 — Veo 功能將被禁用")
                except Exception as e:
                    logger.error(f"❌ 嘗試使用 genai.configure 設置 API key 失敗: {e}")
            else:
                logger.error("❌ 已安裝的 google.genai 模組缺少可用的 Client/配置接口")
    except Exception as e:
        logger.error(f"❌ 建立 Veo 客戶端時出現異常: {e}")
        import traceback
        logger.error(traceback.format_exc())