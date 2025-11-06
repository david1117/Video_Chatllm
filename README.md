# VideoChatLLM - 多模態 ChatLLM 創作系統

一個基於 Gemini API 的智能多模態 ChatLLM 創作助手，整合圖文生成、視頻製作、語音轉換等多種創作工具。

**現在支援 Spec-Kit 架構！** 見 [Spec-Kit 文檔](./README_SPECKIT.md)

## 🎯 核心特性

- **智能對話核心**: 使用 Gemini API 提供強大的自然語言理解和上下文管理
- **多模態創作**: 整合文生圖、圖生圖、圖生視頻、語音生視頻等完整創作流程
- **決策智能體**: 自動分析用戶需求，智能調度各模態工具
- **工作流管理**: 基於 LangGraph 實現任務編排和依賴管理
- **記憶系統**: 持久化對話歷史、任務狀態和用戶偏好
- **錯誤處理**: 完善的異常處理、重試機制和任務回溯功能

## 🏗️ 架構設計

```
┌─────────────────────────────────────────────────────────┐
│                   VideoChatLLM                          │
├─────────────────────────────────────────────────────────┤
│  Gemini 對話引擎 → 決策智能體 → 執行計劃                      │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐     │
│  │ 文生圖/圖生圖   │  │  圖生視頻      │  │ 語音生視頻  │      │
│  │ NanoBanana   │  │   Veo3.1     │  │ TTS+Lipsync│      │
│  └──────────────┘  └──────────────┘  └────────────┘      │
│                                                         │
│  ├─ LangGraph 工作流                                     │
│  ├─ 記憶管理系統                                          │
│  └─ 錯誤處理與回溯                                         │
└─────────────────────────────────────────────────────────┘
```

## 📦 安裝與配置

### 1. 安裝依賴

```bash
pip install -r requirements.txt
```

### 2. 配置環境變數

複製 `.env.example` 並命名為 `.env`，填入相應的 API 密鑰：

```bash
cp .env.example .env
```

編輯 `.env` 文件：

```env
# Gemini API
GEMINI_API_KEY=your_gemini_api_key_here

# NanoBanana API
NANOBANANA_API_KEY=your_nanobanana_api_key_here

# Veo3.1 API
VEO_API_KEY=your_veo_api_key_here

# Wan2.2 / Kling AI
WAN2_API_KEY=your_wan2_api_key_here
KLING_API_KEY=your_kling_api_key_here
```

## 🚀 快速開始


### 運行主程序

```bash
python app.py
```

## 📚 功能模組

### 1. Gemini 對話引擎 (`core/gemini_engine.py`)

提供自然語言對話功能：
- 多輪對話支持
- 任務類型檢測
- 上下文管理

### 2. 決策智能體 (`core/decision_agent.py`)

智能任務調度：
- 自動識別創作需求
- 生成執行計劃
- 管理任務依賴

### 3. 記憶管理系統 (`core/memory_manager.py`)

持久化狀態管理：
- 對話歷史記錄
- 任務狀態跟蹤
- 用戶偏好設置

### 4. 圖像生成工具 (`tools/image_generator.py`)

NanoBanana 文生圖/圖生圖：
- 文生圖
- 圖生圖（風格轉換）

### 5. 視頻生成工具 (`tools/video_generator.py`)

Veo3.1 圖生視頻：
- 靜態圖片轉動態視頻
- 異步任務處理

### 6. 語音生視頻工具 (`tools/speech2video.py`)

Wan2.2 / Kling AI：
- 語音轉視頻
- 文本+語音混合生成

## 📊 使用場景

### 場景 1: 文生圖

```
用戶: "幫我生成一張夕陽下的海灘風景圖"
系統: [調用 NanoBanana] → 生成圖片
```

### 場景 2: 圖生視頻

```
用戶: "把剛才的圖片做成動態視頻"
系統: [調用 Veo3.1] → 生成視頻
```

### 場景 3: 完整創作流程

```
用戶: "我想創建一個完整作品：一隻可愛的小貓在花園裡"
系統: [文生圖] → [圖生視頻] → [組合輸出]
```

### 場景 4: 語音生視頻

```
用戶: [上傳音頻]
系統: [調用 Kling AI] → [生成視頻]
```

## 🛠️ 開發與擴展

### 添加新的模態工具

1. 在 `tools/` 目錄創建新的工具類
2. 實現統一的接口規範
3. 在 `DecisionAgent` 中添加調度邏輯
4. 更新 `app.py` 中的執行邏輯

### 自定義工作流


## 📝 配置選項

在 `config.py` 或 `.env` 中可以配置：

- `MAX_RETRY_ATTEMPTS`: 最大重試次數
- `TIMEOUT_SECONDS`: API 調用超時時間
- `ENABLE_MEMORY`: 是否啟用記憶功能
- `DEFAULT_TEMPERATURE`: Gemini API 溫度參數

## 🤝 貢獻

歡迎提交 Issue 和 Pull Request！

## 📄 許可

MIT License

## 🙏 致謝

- Google Gemini API
- NanoBanana
- Veo3.1
  


