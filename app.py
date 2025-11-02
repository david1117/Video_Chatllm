"""
VideoChatLLM Web 應用服務器
提供文生圖、圖生圖、Veo 視頻生成功能
"""
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import os
import logging
from datetime import datetime
from typing import Dict, Any
import base64
from io import BytesIO
from PIL import Image

from core import GeminiEngine, MemoryManager
from tools.gemini_image_generator import GeminiImageGenerator
from tools.video_generator import Veo3VideoGenerator

# 配置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# 上傳文件配置
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB 最大文件大小

# 初始化工具
gemini_engine = GeminiEngine()
memory = MemoryManager()
image_gen = GeminiImageGenerator()
video_gen = Veo3VideoGenerator()


@app.route('/')
def index():
    """主頁面"""
    return render_template('index.html')


@app.route('/outputs/<path:filename>')
def serve_output(filename):
    """提供輸出文件的訪問"""
    return send_file(os.path.join(OUTPUT_FOLDER, filename))


@app.route('/api/generate_image', methods=['POST'])
def generate_image():
    """文生圖 API"""
    try:
        data = request.json
        prompt = data.get('prompt', '')
        
        if not prompt:
            return jsonify({'error': '請提供提示詞'}), 400
        
        logger.info(f"文生圖請求: {prompt}")
        
        # 生成圖像
        result = image_gen.text_to_image(prompt)
        
        # 保存圖像
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"image_{timestamp}.png"
        filepath = os.path.join(app.config['OUTPUT_FOLDER'], filename)
        result['image'].save(filepath)
        
        # 轉換為 base64
        buffer = BytesIO()
        result['image'].save(buffer, format='PNG')
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        # 記錄到記憶
        memory.add_conversation("web", prompt, f"已經完成 {filename}")
        
        return jsonify({
            'success': True,
            'image': f'data:image/png;base64,{img_base64}',
            'filename': filename,
            'width': result['width'],
            'height': result['height'],
            'format': result['format']
        })
        
    except Exception as e:
        logger.error(f"文生圖錯誤: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/transform_image', methods=['POST'])
def transform_image():
    """圖生圖 API - 支持多張圖片"""
    try:
        data = request.json
        prompt = data.get('prompt', '')
        images_data = data.get('images', [])
        
        # 兼容舊版本單張圖片
        if not images_data:
            image_data = data.get('image', '')
            if image_data:
                images_data = [image_data]
        
        if not prompt or not images_data:
            return jsonify({'error': '請提供提示詞和圖片'}), 400
        
        # 解析所有圖片
        images = []
        for img_data in images_data:
            if ',' in img_data:
                img_data = img_data.split(',')[1]
            image_bytes = base64.b64decode(img_data)
            image = Image.open(BytesIO(image_bytes))
            images.append(image)
        
        logger.info(f"圖生圖請求: {prompt}，共 {len(images)} 張圖片")
        
        results = []
        results_base64 = []
        
        # 使用 Gemini 基於參考圖生成新圖片
        result = image_gen.image_with_reference(
            text=prompt,
            reference_images=images
        )
        
        # 保存結果
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"transformed_{timestamp}.png"
        filepath = os.path.join(app.config['OUTPUT_FOLDER'], filename)
        result['image'].save(filepath)
        
        # 轉換為 base64
        buffer = BytesIO()
        result['image'].save(buffer, format='PNG')
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return jsonify({
            'success': True,
            'images': [f'data:image/png;base64,{img_base64}'],
            'count': 1,
            'filenames': [filename]
        })
        
    except Exception as e:
        logger.error(f"圖生圖錯誤: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/generate_video', methods=['POST'])
def generate_video():
    """Veo 視頻生成 API，支持文生視頻、圖生視頻和首尾幀插值"""
    try:
        prompt = request.form.get('prompt', '')
        duration = int(request.form.get('duration', 10))
        mode = request.form.get('mode', 'text_to_video')  # 新增模式參數
        
        if not prompt and mode != 'first_to_last':
            return jsonify({'error': '請提供提示詞'}), 400

        if mode == 'first_to_last':
            # 首尾幀插值
            if 'first_frame' not in request.files or 'last_frame' not in request.files:
                return jsonify({'error': '請上傳首幀和尾幀圖片'}), 400
            
            first_file = request.files['first_frame']
            last_file = request.files['last_frame']
            
            if first_file.filename == '' or last_file.filename == '':
                return jsonify({'error': '請選擇首幀和尾幀圖片'}), 400
            
            first_image = Image.open(first_file.stream)
            last_image = Image.open(last_file.stream)
            
            logger.info(f"收到首尾幀插值請求: {prompt}")
            result = video_gen.first_to_last_frame(
                first_image=first_image,
                last_image=last_image,
                prompt=prompt,
                duration=duration
            )
            
        elif mode == 'image_to_video' and 'image' in request.files and request.files['image'].filename != '':
            # 圖生視頻
            file = request.files['image']
            image = Image.open(file.stream)
            logger.info(f"收到圖生視頻請求: {prompt}")
            result = video_gen.image_to_video(image=image, prompt=prompt, duration=duration)
        else:
            # 文生視頻
            logger.info(f"視頻生成請求: {prompt}")
            result = video_gen.generate_video(
                prompt=prompt,
                duration=duration,
                timeout=600
            )
        
        # 返回文件路徑
        return jsonify({
            'success': True,
            'filename': result['video_file'],
            'prompt': prompt,
            'duration': duration,
            'generation_time': result['metadata']['generation_time']
        })
        
    except Exception as e:
        logger.error(f"視頻生成錯誤: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/download/<filename>')
def download_file(filename):
    """文件下載"""
    try:
        filepath = os.path.join(app.config['OUTPUT_FOLDER'], filename)
        
        if not os.path.exists(filepath):
            return jsonify({'error': '文件不存在'}), 404
        
        # 判斷文件類型
        if filename.endswith('.mp4'):
            mimetype = 'video/mp4'
        elif filename.endswith('.png') or filename.endswith('.jpg'):
            mimetype = 'image/png'
        else:
            mimetype = 'application/octet-stream'
        
        return send_file(filepath, mimetype=mimetype, as_attachment=True)
        
    except Exception as e:
        logger.error(f"下載錯誤: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/chat', methods=['POST'])
def chat():
    """對話 API"""
    try:
        data = request.json
        user_input = data.get('message', '')
        
        if not user_input:
            return jsonify({'error': '請提供訊息'}), 400
        
        # 使用 Gemini 進行對話
        response = gemini_engine.chat(user_input)
        
        return jsonify({
            'success': True,
            'response': response['response'],
            'task_type': response['task_type']
        })
        
    except Exception as e:
        logger.error(f"對話錯誤: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/generate_video_from_image', methods=['POST'])
def generate_video_from_image():
    if 'image' not in request.files or 'prompt' not in request.form:
        return jsonify({"error": "請求中缺少圖片或提示"}), 400

    file = request.files['image']
    prompt = request.form['prompt']

    if file.filename == '':
        return jsonify({"error": "未選擇文件"}), 400

    try:
        image = Image.open(file.stream)
        
        logger.info(f"收到圖生視頻請求: {prompt}")
        result = video_gen.image_to_video(image=image, prompt=prompt)
        
        video_path = result.get("video_file")
        if video_path and os.path.exists(video_path):
            return send_file(video_path, as_attachment=True)
        else:
            return jsonify({"error": "視頻文件生成失敗或未找到"}), 500

    except Exception as e:
        logger.error(f"圖生視頻錯誤: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/analyze_intent', methods=['POST'])
def analyze_intent():
    """
    智能意圖分析 API
    分析用戶消息和上傳的文件，返回任務類型和參數
    """
    try:
        message = request.form.get('message', '')
        files = request.files.getlist('files')
        
        logger.info(f"收到意圖分析請求: {message}, 文件數: {len(files)}")
        
        # 構建分析提示詞
        analysis_prompt = f"""
分析以下用戶請求，判斷任務類型並提取關鍵參數。

用戶消息: {message}
上傳文件數量: {len(files)}

請分析並以JSON格式返回以下信息：
{{
    "taskType": "任務類型（text_to_image/image_to_image/image_to_video/text_to_video/first_to_last_frame）",
    "prompt": "提取的提示詞",
    "fileCount": {len(files)},
    "reasoning": "判斷理由"
}}

判斷規則：
1. 如果沒有上傳文件且用戶描述要生成圖片 -> text_to_image
2. 如果上傳了1張圖片且用戶要求修改/轉換 -> image_to_image
3. 如果上傳了1張圖片且用戶要求生成視頻/動畫 -> image_to_video
4. 如果上傳了2張圖片且用戶提到首尾/插值/過渡 -> first_to_last_frame
5. 如果沒有上傳文件且用戶描述要生成視頻 -> text_to_video
6. 如果上傳了多張圖片（>2）-> image_to_image

只返回JSON，不要有其他文字。
"""
        
        # 調用 Gemini 分析
        response = gemini_engine.chat(analysis_prompt)
        
        # 解析 Gemini 的回應
        import json
        import re
        
        # 嘗試從回應中提取JSON
        response_text = response['response']
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        
        if json_match:
            intent_data = json.loads(json_match.group())
        else:
            # 如果無法解析，使用簡單規則
            intent_data = simple_intent_analysis(message, len(files))
        
        # 保存上傳的文件
        file_paths = []
        for file in files:
            if file and file.filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"chat_{timestamp}_{file.filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                file_paths.append(filepath)
        
        intent_data['filePaths'] = file_paths
        intent_data['originalMessage'] = message
        
        logger.info(f"意圖分析結果: {intent_data}")
        
        return jsonify(intent_data)
        
    except Exception as e:
        logger.error(f"意圖分析錯誤: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def simple_intent_analysis(message: str, file_count: int) -> Dict[str, Any]:
    """簡單的意圖分析邏輯（作為後備方案）"""
    message_lower = message.lower()
    
    # 判斷任務類型
    if file_count == 0:
        if any(word in message_lower for word in ['視頻', '视频', 'video', '動畫', '动画']):
            task_type = 'text_to_video'
        else:
            task_type = 'text_to_image'
    elif file_count == 1:
        if any(word in message_lower for word in ['視頻', '视频', 'video', '動畫', '动画']):
            task_type = 'image_to_video'
        else:
            task_type = 'image_to_image'
    elif file_count == 2:
        if any(word in message_lower for word in ['首尾', '插值', '過渡', '转换']):
            task_type = 'first_to_last_frame'
        else:
            task_type = 'image_to_image'
    else:
        task_type = 'image_to_image'
    
    return {
        'taskType': task_type,
        'prompt': message,
        'fileCount': file_count,
        'reasoning': '基於簡單規則分析'
    }


@app.route('/api/execute_task', methods=['POST'])
def execute_task():
    """
    智能任務執行 API
    根據意圖分析結果執行相應的生成任務
    """
    try:
        data = request.json
        task_type = data.get('taskType')
        prompt = data.get('prompt', '')
        file_paths = data.get('filePaths', [])
        
        logger.info(f"執行任務: {task_type}, 提示詞: {prompt}")
        
        result = {
            'success': True,
            'taskType': task_type,
            'message': ''
        }
        
        # 根據任務類型執行
        if task_type == 'text_to_image':
            # 文生圖
            img_result = image_gen.text_to_image(prompt)
            
            # 保存圖片
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"image_{timestamp}.png"
            filepath = os.path.join(app.config['OUTPUT_FOLDER'], filename)
            img_result['image'].save(filepath)
            
            # 轉換為 base64
            buffer = BytesIO()
            img_result['image'].save(buffer, format='PNG')
            img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            result['message'] = f'✅ 已成功生成圖片！'
            result['images'] = [f'data:image/png;base64,{img_base64}']
            
        elif task_type == 'batch_image_generation':
            # 批量圖生圖（參考一張圖片生成多個場景）
            from decision_agent import DecisionAgent
            decision_agent = DecisionAgent()
            
            # 解析執行計劃
            execution_plan = decision_agent.plan_execution({
                'taskType': task_type,
                'prompt': prompt,
                'filePaths': file_paths,
                'fileCount': len(file_paths)
            })
            
            results = []
            for step in execution_plan:
                step_prompt = step['parameters']['prompt']
                
                # 加載參考圖片
                images = []
                for file_path in file_paths:
                    images.append(Image.open(file_path))
                
                # 準備參數
                gen_params = {}
                if 'size' in step['parameters']:
                    gen_params['size'] = step['parameters']['size']
                
                # 生成圖片
                img_result = image_gen.image_with_reference(step_prompt, images, **gen_params)
                
                # 保存圖片
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"batch_scene_{step['step']}_{timestamp}.png"
                filepath = os.path.join(app.config['OUTPUT_FOLDER'], filename)
                img_result['image'].save(filepath)
                
                # 轉換為 base64
                buffer = BytesIO()
                img_result['image'].save(buffer, format='PNG')
                img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                
                results.append({
                    'step': step['step'],
                    'prompt': step_prompt,
                    'image': f'data:image/png;base64,{img_base64}',
                    'filename': filename
                })
            
            result['message'] = f'✅ 已成功生成 {len(results)} 張場景圖片！'
            result['images'] = [r['image'] for r in results]
            result['batch_details'] = results
            
        elif task_type == 'image_to_image':
            # 圖生圖（基於參考圖像生成）
            images = []
            for file_path in file_paths:
                images.append(Image.open(file_path))
            
            # 使用正確的方法名和參數順序
            img_result = image_gen.image_with_reference(prompt, images)
            
            # 保存圖片
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"transformed_{timestamp}.png"
            filepath = os.path.join(app.config['OUTPUT_FOLDER'], filename)
            img_result['image'].save(filepath)
            
            # 轉換為 base64
            buffer = BytesIO()
            img_result['image'].save(buffer, format='PNG')
            img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            result['message'] = f'✅ 已成功生成圖片！'
            result['images'] = [f'data:image/png;base64,{img_base64}']
            
        elif task_type == 'image_to_video':
            # 圖生視頻
            if not file_paths:
                raise ValueError('圖生視頻需要上傳圖片')
            
            image = Image.open(file_paths[0])
            video_result = video_gen.image_to_video(image, prompt, duration=5)
            
            if video_result['success']:
                video_filename = video_result['video_file']
                result['message'] = f'✅ 視頻已生成！時長: 5秒'
                result['video'] = f'/outputs/{video_filename}'
            else:
                raise ValueError('視頻生成失敗')
                
        elif task_type == 'first_to_last_frame':
            # 首尾幀插值
            if len(file_paths) < 2:
                raise ValueError('首尾幀插值需要上傳2張圖片')
            
            first_image = Image.open(file_paths[0])
            last_image = Image.open(file_paths[1])
            
            video_result = video_gen.first_to_last_frame(
                first_image, 
                last_image, 
                prompt, 
                duration=5
            )
            
            if video_result['success']:
                video_filename = video_result['video_file']
                result['message'] = f'✅ 首尾幀插值視頻已生成！'
                result['video'] = f'/outputs/{video_filename}'
            else:
                raise ValueError('首尾幀插值失敗')
                
        elif task_type == 'text_to_video':
            # 文生視頻
            video_result = video_gen.generate_video(prompt, duration=5)
            
            if video_result['success']:
                video_filename = video_result['video_file']
                result['message'] = f'✅ 視頻已生成！時長: 5秒'
                result['video'] = f'/outputs/{video_filename}'
            else:
                raise ValueError('視頻生成失敗')
        else:
            raise ValueError(f'未知的任務類型: {task_type}')
        
        logger.info(f"任務執行成功: {task_type}")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"任務執行錯誤: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'❌ 執行失敗: {str(e)}'
        }), 500


if __name__ == '__main__':
    # Avoid printing non-encodable emoji on some Windows consoles
    print("=" * 60)
    print("VideoChatLLM Web 應用啟動")
    print("=" * 60)
    print("訪問地址: http://localhost:5000")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)

