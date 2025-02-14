import json
import logging
from flask import Flask, render_template
from models import Session, ChatMessage
import threading
import time
import webbrowser
from flask_cors import CORS
from wxauto import WeChat
from openai import OpenAI

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s- %(filename)s:%(lineno)d - %(message)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Local ChatGlm3 配置
LOCAL_API_URL = "xxxxx"  
LOCAL_API_KEY = 'EMPTY'
client = OpenAI(api_key=LOCAL_API_KEY, base_url=LOCAL_API_URL)

listen_list = [
    "Wechat nick name you want to listen"
]

# 创建Flask应用
app = Flask(__name__, static_folder='static')
CORS(app)

# 全局变量存储上下文
chat_contexts = {}

def login_wechat():
    """微信登录函数"""
    try:
        # 初始化微信实例
        wx = WeChat()
        # 验证微信是否成功连接
        if wx.GetSessionList():
            logger.info("微信连接成功")
            # 登录成功后打开监控页面
            open_dashboard()
            return wx
        else:
            logger.error("微信连接失败")
            return None
    except Exception as e:
        logger.error(f"登录过程出错: {str(e)}")
        return None

def save_message(sender_id, sender_name, message, reply):
    """保存聊天记录到数据库"""
    try:
        session = Session()
        chat_message = ChatMessage(
            sender_id=sender_id,
            sender_name=sender_name,
            message=message,
            reply=reply
        )
        session.add(chat_message)
        session.commit()
        session.close()
    except Exception as e:
        logger.error(f"保存消息失败: {str(e)}")

def get_LOCALGLM_response(NewMessageList):
    """调用 LOCAL CHATGLM API 获取回复"""
    try:
        # 获取用户上下文
        AllspecificUser = [newmessage['sender_name'] for newmessage in NewMessageList]
        AllspecificUser = list(set(AllspecificUser))
        print(f"用户列表: {AllspecificUser}")
        
        for newmessage in NewMessageList:
            user_id = newmessage['sender_name']
            message = newmessage['content']
            msgtype = newmessage['type']
            if user_id not in chat_contexts:
                chat_contexts[user_id] = []
            
            # 添加新消息到上下文
            if msgtype == 'friend':
                chat_contexts[user_id].append({"role": "user", "content": message})
            elif msgtype == 'self':
                chat_contexts[user_id].append({"role": "assistant", "content": message})
            else:
                raise ValueError("未知消息类型")
            
        AllReply = []
        
        for user_id in AllspecificUser:
            try:
                # 保持上下文长度不超过20条消息
                if len(chat_contexts[user_id]) > 10:
                    chat_contexts[user_id] = chat_contexts[user_id][-10:]
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
                
                chat_contexts[user_id].append({"role": "assistant", "content": reply})
                AllReply.append({
                    "sender_name": user_id,
                    "newmessage": chat_contexts[user_id][-2],
                    "reply": reply
                })
                
            except Exception as api_error:
                logger.error(f"处理用户 {user_id} 的消息时出错: {str(api_error)}")
                # 返回一个友好的错误消息
                error_reply = "抱歉，我现在遇到了一些问题，请稍后再试。"
                AllReply.append({
                    "sender_name": user_id,
                    "newmessage": chat_contexts[user_id][-1],
                    "reply": error_reply
                })
                
        return AllReply
    
    except Exception as e:
        logger.error(f"调用 LOCALGLM API 失败: {str(e)}")
        raise e
    
# Flask路由
@app.route('/')
def index():
    """渲染监控页面"""
    return render_template('index.html')

@app.route('/messages')
def get_messages():
    """获取所有聊天记录"""
    # 添加跨域访问头
    session = Session()
    messages = session.query(ChatMessage).order_by(ChatMessage.created_at.desc()).all()
    result = [{
        'id': msg.id,
        'sender_name': msg.sender_name,
        'message': msg.message,
        'reply': msg.reply,
        'created_at': msg.created_at.strftime('%Y-%m-%d %H:%M:%S')
    } for msg in messages]
    session.close()
    return {'messages': result}

def run_flask():
    """运行Flask应用"""
    app.config['SECRET_KEY'] = 'your-secret-key-here'  # 添加密钥
    app.config['TEMPLATES_AUTO_RELOAD'] = True  # 启用模板自动重载
    app.run(
        host='127.0.0.1',  # 改为本地地址
        port=5000,
        debug=False,  # 关闭调试模式
        threaded=True
    )

def open_dashboard():
    """打开监控面板"""
    time.sleep(2)  # 等待Flask服务器启动
    webbrowser.open('http://127.0.0.1:5000')

def get_NewMessage(wx):
    """获取最新消息"""
    new_msg = wx.GetListenMessage()
    NEW_MESSAGE_LIST = []
    send_name_getnewmsg = {}
    if new_msg:
        for chatmsg in new_msg:
            sender_name = chatmsg.who
            one_content = new_msg.get(chatmsg)
            if sender_name not in send_name_getnewmsg:
                send_name_getnewmsg[sender_name] = False
            if one_content:
                for msg in one_content:
                    logger.debug(f'Parsing : {sender_name} : {msg.content}; type : {msg.type}')
                    if msg.type.lower() == 'sys' and msg.content == '以下为新消息':
                        send_name_getnewmsg[sender_name] = True
                    elif msg.type.lower() != 'sys' and send_name_getnewmsg[sender_name]:
                        NEW_MESSAGE_LIST.append({
                            "sender_name": sender_name,
                            "content": msg.content,
                            "type": msg.type
                        })
                        
    return NEW_MESSAGE_LIST if len (NEW_MESSAGE_LIST) > 0 else None


def handle_message(wx):
    """处理微信消息"""
    try:
        while True:
            NewMessageList = get_NewMessage(wx)
            if NewMessageList:
                # 获取回复
                Allreply = get_LOCALGLM_response(NewMessageList)
                for reply in Allreply:
                    sender_name = reply['sender_name']
                    newmessage = reply['newmessage']
                    reply = reply['reply']
                    # 保存消息记录
                    save_message(sender_name, sender_name, newmessage['content'], reply)
                    # 回复消息
                    wx.SendMsg(reply, sender_name)
                    logger.info(f"回复 {sender_name}: {reply}")
            
            time.sleep(1)  # 降低CPU占用
            
    except Exception as e:
        logger.error(f"处理消息失败: {str(e)}")

def main():
    """主函数"""
    try:
        # 启动Flask线程
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        logger.info("监控服务器已启动")
        
        # 删除之前的浏览器线程启动代码
        # 尝试登录微信
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            try:
                wx = login_wechat()
                for listener in listen_list:
                    wx.AddListenChat(who = listener)
                if wx:  # 登录成功
                    logger.info("开始运行微信机器人...")
                    handle_message(wx)
                    break
                else:
                    retry_count += 1
                    if retry_count < max_retries:
                        logger.info(f"等待 5 秒后进行第 {retry_count + 1} 次重试")
                        time.sleep(5)
            except Exception as e:
                logger.error(f"运行出错: {str(e)}")
                retry_count += 1
                if retry_count < max_retries:
                    logger.info(f"等待 10 秒后进行第 {retry_count + 1} 次重试")
                    time.sleep(10)
        
        if retry_count >= max_retries:
            logger.error("多次尝试登录失败，程序退出")
            
    except Exception as e:
        logger.error(f"程序运行错误: {str(e)}")
    finally:
        logger.info("程序退出")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"程序异常退出: {str(e)}")