######################################################################
# Advanced Python & Practical Applications
# SQLite, SQLAlchemy, LINE, Flask
#
# [專案]
# 資料庫記錄心情留言
# 問題：請詳閱附件 ReadMe_Linebot-Secret.pdf 說明
#       請依照本週課程專題所述，撰寫程式並佈署伺服器至帶有資料庫的
#       雲端平台 (PythonAnywhere 及 Heroku)，於串聯LINE頻道後測試。
#
# 輸出：
#   1)使用者加入好友後於LINE第一次輸入 "悄悄話"，機器人回應 
#     "大膽說出心裡話吧~"，並準備儲存。
#   2)使用者接著輸入的文字會被儲存，機器人回應：
#     "我會好好保護這個秘密~"。
#   3)下回使用者再輸入 "悄悄話" 時，機器人會取出並回應所存的文字。
#######################################################################

# import random
from flask import Flask, request, abort
from flask_sqlalchemy import SQLAlchemy
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    StickerMessage, StickerSendMessage,
    FollowEvent
)
import os, psycopg2

## Using config vars through Heroku
acc_code = os.environ['LINE_ACC_TOKEN']
secr = os.environ['LINE_SECRET']
line_bot_api = LineBotApi(acc_code)
handler = WebhookHandler(secr)

app = Flask(__name__)
app.config["DEBUG"] = True

## Connect to PostgreSQL of Heroku
# SQLAlchemy 1.4 removed the deprecated postgres dialect name,
# the name postgresql must be used instead now. 
# SQLALCHEMY_DATABASE_URI = os.environ['DATABASE_URL']
uri = os.getenv("DATABASE_URL")
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

SQLALCHEMY_DATABASE_URI = uri
app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

class User(db.Model):  # 使用者資料表

    __tablename__ = "users"

    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    words = db.Column(db.String(100), nullable=False, default='')
    save = db.Column(db.Boolean, nullable=False, default=False)

    def __repr__(self):
        return f'name:{self.name},secret:{self.words}'

def check_user(id, name):
    exists = User.query.filter_by(id=id).first()

    if not exists:
        new = User(id=id, name=name,    # 初始化此使用者物件
              words='', save=False)
        db.session.add(new)
        db.session.commit()
        print('新增一名用戶：', id)
    else:
        print('用戶已經存在，id：', id)
        users = User.query.all()
        print('目前用戶數：', len(users))

@app.route('/')
def index():
    db.create_all()
    return 'Welcome to Line Bot!'

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

# 處理回應文字
def reply_text(token, id, txt):
    me = User.query.filter_by(id=id).first()

    if (txt=='Hi') or (txt=="你好"):
        reply = f'{txt} {me.name}！'
    elif '悄悄話' in txt:
        words = me.words
        if words:
            reply = f'你的悄悄話是：\n\n{words}'
        else:
            reply = '放膽說出心裡的話吧～'
            me.save = True  # 準備儲存祕密
            db.session.commit()
    elif me.save:
        me.words = txt      # 儲存祕密
        me.save = False     # 停止儲存祕密
        db.session.commit()
        reply = '我會好好保護這個祕密～'
    else:
        reply = txt  #學你說話

    msg = TextSendMessage(reply)
    # line_bot_api.reply_message(token, msg)
    stk = StickerSendMessage(
        package_id=3,
        sticker_id=233)
    line_bot_api.reply_message(token, [msg, stk])

@handler.default()
def default(event):
    print('捕捉到事件：', event)

# 接收文字訊息的事件處理程式
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    profile = line_bot_api.get_profile(event.source.user_id)
    # 紀錄用戶資料
    _id = event.source.user_id
    _name = profile.display_name
    _txt = event.message.text

    check_user(_id, _name)
    reply_text(event.reply_token, _id, _txt)


@handler.add(MessageEvent, message=StickerMessage)
def handle_sticker_message(event):
    line_bot_api.reply_message(
        event.reply_token,
        StickerSendMessage(
            package_id=event.message.package_id,
            sticker_id=event.message.sticker_id)
    )

@handler.add(FollowEvent)
def followed(event):
    _id = event.source.user_id
    profile = line_bot_api.get_profile(_id)
    _name = profile.display_name
    print('歡迎新好友，ID：', _id)
    print('名字：', _name)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=80)

