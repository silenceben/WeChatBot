import json
import logging
import sys
import threading
import time
import webbrowser
from logging.handlers import RotatingFileHandler

from flask import Flask, render_template
from flask_cors import CORS
from wxauto import WeChat
from openai import OpenAI
from models import Session, ChatMessage

# 自定义日志重定向类
class StreamToLogger(object):
    def __init__(self, logger, log_level=logging.INFO):
        self.logger = logger
        self.log_level = log_level

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())

    def flush(self):
        pass

# 日志配置函数
def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)


    logging.getLogger('comtypes').setLevel(logging.WARNING)
    # 文件处理器（带轮转）
    file_handler = RotatingFileHandler(
        'wxbot.log',
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    file_handler.setFormatter(file_formatter)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # 重定向标准输出
    sys.stdout = StreamToLogger(logger, logging.INFO)
    sys.stderr = StreamToLogger(logger, logging.ERROR)

# 初始化日志
setup_logging()
logger = logging.getLogger(__name__)

# 其他配置
LOCAL_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
LOCAL_API_KEY = 'sk-fexx27'
client = OpenAI(api_key=LOCAL_API_KEY, base_url=LOCAL_API_URL)
listen_list = ["xx"]

app = Flask(__name__, static_folder='static')
CORS(app)
chat_contexts = {}
context_lock = threading.Lock()

# 核心功能函数保持不变...
def login_wechat():
    """微信登录函数"""
    try:
        wx = WeChat()
        if wx.GetSessionList():
            logger.info("微信连接成功")
            open_dashboard()
            return wx
        logger.error("微信连接失败")
        return None
    except Exception as e:
        logger.error(f"登录出错: {str(e)}", exc_info=True)
        return None

def save_message(sender_id, sender_name, message, reply):
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
    except Exception as e:
        logger.error(f"保存消息失败: {str(e)}")
    finally:
        session.close()

def get_LOCALGLM_response(NewMessageList):
    with context_lock:
        try:
            AllspecificUser = list(set([msg['sender_name'] for msg in NewMessageList]))
            AllReply = []

            for newmessage in NewMessageList:
                user_id = newmessage['sender_name']
                message = newmessage['content']
                msgtype = newmessage['type']

                if user_id not in chat_contexts:
                    chat_contexts[user_id] = []

                if len(chat_contexts[user_id]) > 5:
                    chat_contexts[user_id] = chat_contexts[user_id][-5:]

                chat_contexts[user_id].append({
                    "role": "user" if msgtype == 'friend' else "assistant",
                    "content": message
                })

            for user_id in AllspecificUser:
                try:
                    data = [
                        {"role": "system", "content": f"你是{user_id}的助手"},
                        *chat_contexts[user_id][-5:]
                    ]

                    response = client.chat.completions.create(
                        model="deepseek-v3",
                        messages=data,
                        stream=False,
                        max_tokens=5000,
                        presence_penalty=1.1,
                        top_p=0.8,
                        temperature=0.8
                    )

                    reply = response.choices[0].message.content
                    chat_contexts[user_id].append({"role": "assistant", "content": reply})
                    
                    AllReply.append({
                        "sender_name": user_id,
                        "newmessage": chat_contexts[user_id][-2],
                        "reply": reply
                    })

                except Exception as api_error:
                    logger.error(f"API请求失败: {str(api_error)}")
                    AllReply.append({
                        "sender_name": user_id,
                        "newmessage": chat_contexts[user_id][-1],
                        "reply": "服务暂时不可用，请稍后再试"
                    })

            return AllReply
        except Exception as e:
            logger.error(f"处理消息失败: {str(e)}", exc_info=True)
            return []

# Flask路由保持不变...
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/messages')
def get_messages():
    session = Session()
    try:
        messages = session.query(ChatMessage).order_by(ChatMessage.created_at.desc()).all()
        return {'messages': [{
            'id': msg.id,
            'sender_name': msg.sender_name,
            'message': msg.message,
            'reply': msg.reply,
            'created_at': msg.created_at.strftime('%Y-%m-%d %H:%M:%S')
        } for msg in messages]}
    finally:
        session.close()

def run_flask():
    app.run(host='127.0.0.1', port=5000, debug=False, threaded=True)

def open_dashboard():
    time.sleep(2)
    webbrowser.open('http://127.0.0.1:5000')

def get_NewMessage(wx):
    try:
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
                        if msg.type.lower() == 'sys' and msg.content == '以下为新消息':
                            send_name_getnewmsg[sender_name] = True
                        elif msg.type.lower() != 'sys' and send_name_getnewmsg[sender_name]:
                            NEW_MESSAGE_LIST.append({
                                "sender_name": sender_name,
                                "content": msg.content,
                                "type": msg.type
                            })
        return NEW_MESSAGE_LIST if NEW_MESSAGE_LIST else None
    except Exception as e:
        logger.error(f"获取消息异常: {str(e)}")
        return None

def handle_message(wx):
    try:
        while True:
            NewMessageList = get_NewMessage(wx)
            if NewMessageList:
                Allreply = get_LOCALGLM_response(NewMessageList)
                for reply in Allreply:
                    try:
                        sender_name = reply['sender_name']
                        wx.SendMsg(reply['reply'], sender_name)
                        save_message(sender_name, sender_name, 
                                   reply['newmessage']['content'], reply['reply'])
                    except Exception as send_error:
                        logger.error(f"发送消息失败: {str(send_error)}")
            time.sleep(1)
    except Exception as e:
        logger.error(f"消息处理循环异常: {str(e)}", exc_info=True)

def main():
    """新版主函数"""
    try:
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        logger.info("监控服务器启动成功")

        while True:
            try:
                retry_count = 0
                wx = None
                
                while retry_count < 3 and wx is None:
                    wx = login_wechat()
                    if wx:
                        logger.info("微信登录成功")
                        for listener in listen_list:
                            wx.AddListenChat(who=listener)
                        handle_message(wx)
                    else:
                        retry_count += 1
                        logger.warning(f"登录尝试 {retry_count}/3")
                        time.sleep(5)
                
                if not wx:
                    logger.error("连续登录失败，等待5分钟重试")
                    time.sleep(300)

            except Exception as main_error:
                logger.error(f"主循环异常: {str(main_error)}", exc_info=True)
                logger.info("10秒后恢复运行...")
                time.sleep(10)

    except KeyboardInterrupt:
        logger.info("用户中断程序")
    finally:
        logger.info("程序终止")

if __name__ == '__main__':
    main()
