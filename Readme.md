# 项目介绍

本项目基于wxauto代码库实现了大模型接入自动聊天，代码参考[deepseek_project项目](https://github.com/1692775560/deepseek_project/tree/main)，主要解决了itchat库的使用风险问题，主要功能（参考[deepseek_project项目](https://github.com/1692775560/deepseek_project/tree/main)）：

1. 微信消息监听
2. 基于上下文的多轮对话

## 安装指南

1. 克隆仓库
2. 安装依赖
   ```bash
   pip install -r requirements.txt
   ```

### 文件说明

- `models.py`: 定义了数据库模型，使用 SQLAlchemy ORM 管理聊天记录
- `wxAutoBot.py`: 主程序文件，包含微信机器人核心逻辑和 Flask Web 服务
- `requirements.txt`: 项目依赖列表
- `templates/index.html`: 实时监控面板的前端界面

### 代码说明

本项目测试时使用本地部署的[ChatGLM3大模型](https://github.com/THUDM/ChatGLM3/tree/main/)实现自动回复，相关代码为：

```python
'''some code'''
from openai import OpenAI

# Local ChatGlm3 配置
LOCAL_API_URL = "xxxxx"  
LOCAL_API_KEY = 'EMPTY'
client = OpenAI(api_key=LOCAL_API_KEY, base_url=LOCAL_API_URL)

'''some code'''
def get_LOCALGLM_response(NewMessageList):
   '''some code'''
                data = [
                        {"role": "system", 
                         "content": f"你是xxxxx，一个聪明、热情、善良的人，后面的对话来自你的朋友{user_id}，你要认真地回答他"
                        },
                        *chat_contexts[user_id]
                ]
                
                # 添加详细的请求日志
                logger.info(f"发送请求到 ChatGLM API, 用户: {user_id}")
                logger.debug(f"请求数据: {json.dumps(data, ensure_ascii=False)}")
                
                response = client.chat.completions.create(
                    model="chatglm3-6b",
                    messages=data,
                    stream=False,
                    max_tokens=512,
                    temperature=0.8,
                    presence_penalty=1.1,
                    top_p=0.8
                )
                
                if not response:
                    raise ValueError("API 返回空响应")
                
                reply = response.choices[0].message.content
                logger.info(f"成功获取回复 - 用户: {user_id}, 回复长度: {len(reply)}")
```

ChatGLM3是个可本地部署的大模型，具有部署简单、操作友好的特性，如无本地部署条件，可参考原始版本代码[deepseek_project项目](https://github.com/1692775560/deepseek_project/tree/main)，使用deepseek接口实现上下文回复

## 致谢

- 感谢开源仓库[deepseek_project项目](https://github.com/1692775560/deepseek_project/tree/main)
- 感谢开源项目[wxauto](https://wxauto.loux.cc/docs/intro)