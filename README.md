# 小红书笔记二创工作流工具

这是一个本地可运行的 FastAPI 工具：

1. 输入小红书笔记链接（以及主题关键词）。
2. 自动抓取页面可读文本与图片链接。
3. 生成“二创”文案（重写标题、正文、标签）。
4. 对图片做二创处理：
   - 围绕主题进行智能中心裁剪（默认裁剪为 4:5）。
   - 轻微调色与锐化。
   - 添加 `二创` 水印。
5. 输出一个结果目录链接，里面包含：
   - `remix_note.md`（二创笔记）
   - `images/`（二创后的美食图）
   - `result.zip`（打包下载）

> 说明：小红书页面存在反爬限制，本工具采用“尽可能提取”的通用抓取策略。若页面防护较强，可改为：
> - 手工粘贴原文内容
> - 手工上传原图
> 再调用本工具完成二创。

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 启动

```bash
uvicorn app:app --reload --port 8000
```

## 调用示例

```bash
curl -X POST 'http://127.0.0.1:8000/remix' \
  -H 'Content-Type: application/json' \
  -d '{
    "note_url": "https://www.xiaohongshu.com/explore/xxxx",
    "theme": "家常下饭菜",
    "extra_edit_prompt": "整体更暖色，突出食物质感"
  }'
```

返回示例：

```json
{
  "job_id": "20260214_abc12345",
  "output_link": "/workspace/my-ai-project/outputs/20260214_abc12345",
  "zip_link": "/workspace/my-ai-project/outputs/20260214_abc12345/result.zip",
  "note_file": "/workspace/my-ai-project/outputs/20260214_abc12345/remix_note.md",
  "images": [
    "/workspace/my-ai-project/outputs/20260214_abc12345/images/remix_1.jpg"
  ]
}
```

## 目录结构

- `app.py`：API 入口
- `workflow.py`：抓取、改写、二创图片、打包的主流程
- `requirements.txt`：依赖
- `outputs/`：每次任务输出目录
