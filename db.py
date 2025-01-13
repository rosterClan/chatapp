'''
db
database file, containing all the logic to interface with the sql database
'''

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from models import *
import datetime
import random #Should probably select something more secure
import sys
import os
import datetime
import json
import common

from pathlib import Path

# creates the database directory
Path("database").mkdir(exist_ok=True)

# "database/main.db" specifies the database file
# change it if you wish
# turn echo = True to display the sql output
engine = create_engine("sqlite:///database/main.db", echo=False)

# initializes the database
Base.metadata.create_all(engine)

# inserts a user to the database
def insert_user(username: str, password: str):
    with Session(engine) as session:
        user = User(username=username, password=password)
        session.add(user)
        session.commit()

# gets a user from the database
def get_user(username: str):
    with Session(engine) as session:
        return session.get(User, username)
    
def get_user_refactored(user_hash: str):
    with Session(engine) as session:
        return session.get(user_refactored,user_hash)
    
def get_user_by_username(user_name: str):
    with Session(engine) as session:
        return session.query(user_refactored_salted).filter(user_refactored_salted.user_name == user_name).first()
    
def get_user_by_username_array(user_name: str):
    with Session(engine) as session:
        user = session.query(user_refactored_salted).filter(user_refactored_salted.user_name == user_name).first()
        
        array_list = []
        array_list.append(user.user_name)
        array_list.append(user.user_role)
        array_list.append(user.muted)
        
        return array_list

def get_user_role(user_name: str):
    with Session(engine) as session:
        user = session.query(user_refactored).filter(user_refactored_salted.user_name == user_name).first()
        if user:
            return user.user_role
        else:
            return 1
        
def get_muted_state(user_name: str):
    with Session(engine) as session:
        user = session.query(user_refactored).filter(user_refactored_salted.user_name == user_name).first()
        if user:
            return user.muted
        else:
            return 0

def insert_user_refactored(user_hash,user_name):
    salt = int.from_bytes(os.urandom(8), byteorder="big") & ((1 << 63) - 1)
    salted_hash = common.salt_hash(user_hash,salt)

    with Session(engine) as session:
        user = user_refactored_salted(user_hash=salted_hash, user_name=user_name, salt=salt)
        session.add(user)
        session.commit()

def duplicate_friend_request_check(sender_user_name,receiver_user_name):
    with Session(engine) as session:
        sender_to_reciever = session.query(friend_request).filter(friend_request.sender == sender_user_name).filter(friend_request.receiver == receiver_user_name).first()
        reciever_to_sender = session.query(friend_request).filter(friend_request.sender == receiver_user_name).filter(friend_request.receiver == sender_user_name).first()
        
        return not (sender_to_reciever == reciever_to_sender == None)
    
def get_friend_requests(user_name):
    with Session(engine) as session:
        requests = session.query(friend_request).filter(friend_request.receiver == user_name).all()
        sent_requests = session.query(friend_request).filter(friend_request.sender == user_name).all()
        just_names = []
        for request in requests:
            just_names.append([get_user_by_username_array(request.sender),'request'])
        for request in sent_requests:
            just_names.append([get_user_by_username_array(request.sender),'pending'])
        return just_names
    
def get_friend_sent_requests(user_name):
    with Session(engine) as session:
        requests = session.query(friend_request).filter(friend_request.receiver == user_name).all()
        sent_requests = session.query(friend_request).filter(friend_request.sender == user_name).all()
        just_names = []
        for request in requests:
            just_names.append(request.receiver)
        for request in sent_requests:
            just_names.append(request.receiver)
        return just_names
    
def delete_friend_request(sender_user_name,receiver_user_name):
    with Session(engine) as session:
        sender_to_reciever = session.query(friend_request).filter(friend_request.sender == sender_user_name).filter(friend_request.receiver == receiver_user_name).first()
        reciever_to_sender = session.query(friend_request).filter(friend_request.sender == receiver_user_name).filter(friend_request.receiver == sender_user_name).first()
        
        if not (sender_to_reciever == None):
            session.delete(sender_to_reciever)
        if not (reciever_to_sender == None):
            session.delete(reciever_to_sender)
        session.commit()
    
def is_valid_username(user_name):
    return not get_user_by_username(user_name) == None

def send_friend_request(sender_user_name,receiver_user_name):
    if (duplicate_friend_request_check(sender_user_name,receiver_user_name) == False):
        request = friend_request(sender=sender_user_name,receiver=receiver_user_name)
        with Session(engine) as session:
            session.add(request)
            session.commit()
            
def existing_friend_relationship(user_name_one,user_name_two):
    with Session(engine) as session:
        one_to_two = session.query(friends_list).filter(friends_list.user_one == user_name_one).filter(friends_list.user_two == user_name_two).first()
        two_to_one = session.query(friends_list).filter(friends_list.user_two == user_name_one).filter(friends_list.user_one == user_name_two).first()
        return one_to_two == two_to_one == None
            
def append_friends_relationship(user_name_one,user_name_two):
    if (is_valid_username(user_name_one) and is_valid_username(user_name_two)):
        if (existing_friend_relationship(user_name_one,user_name_two)):
            with Session(engine) as session:
                friend_relationship = friends_list(user_one=user_name_one,user_two=user_name_two)
                session.add(friend_relationship)
                session.commit()
                
def get_all_users():
    with Session(engine) as session:
        all_users = session.query(user_refactored).all()
        user_dicts = []
        for user in all_users:
            temp = []
            temp.append(user.user_name)
            temp.append(user.user_role)
            temp.append(user.muted)
            user_dicts.append(temp)
        return user_dicts
    
def get_friends_by_username(user_name:str):
    if (is_valid_username(user_name)):
        with Session(engine) as session:
            left_column_detection = session.query(friends_list).filter(friends_list.user_one == user_name).all()
            right_column_detection = session.query(friends_list).filter(friends_list.user_two == user_name).all()

            just_names = []
            for relationship in left_column_detection:
                just_names.append(relationship.user_two)
            for relationship in right_column_detection:
                just_names.append(relationship.user_one)
            return just_names
        
def create_new_chatroom(user_name:str):
    try:
        with Session(engine) as session:
            chat_room = chat_room_obj(chat_name=f'{user_name}s chat room')
            session.add(chat_room)
            session.commit()
            
            user_chat = user_chat_obj(chat_id=chat_room.chat_id,user_name=user_name)
            session.add(user_chat)
            session.commit()
            
            return user_chat.chat_id
    except Exception as e:
        return None
        
def get_chat_room_by_id(chat_room_id: int):
    with Session(engine) as session:
        chat_room = session.query(chat_room_obj).filter(chat_room_obj.chat_id == chat_room_id).first()
        if not (chat_room == None):
            chat_room_json_obj = {"chat_name":None,"chat_id":None,"members":[],"messages":[]}
            chat_room_json_obj['chat_name'] = chat_room.chat_name
            chat_room_json_obj['chat_id'] = chat_room_id
            
            users_in_chat = session.query(user_chat_obj).filter(user_chat_obj.chat_id == chat_room_id).all()
            for user in users_in_chat:
                chat_room_json_obj['members'].append(user.user_name)
            
            chat_room_messages = []
            chat_room_message_obj = session.query(message_obj).filter(message_obj.chat_id == chat_room_id).all()
            for message_instance in chat_room_message_obj:
                chat_room_messages.append({
                    'from' : get_user_by_username_array(message_instance.user_name),
                    'Time' : message_instance.time_sent,
                    'message' : message_instance.message,
                    'article_id' : chat_room_id
                })
                
            chat_room_json_obj['messages'] = chat_room_messages
            return chat_room_json_obj
    return None
        
def add_message_to_chat(user_name,message,chat_id):
    with Session(engine) as session:
        message_instance = message_obj(user_name=user_name,chat_id=chat_id,time_sent=datetime.datetime.now().isoformat(),message=message)
        session.add(message_instance)
        session.commit()

def is_valid_chatroomid(chatroom_id):
    return not get_chat_room_by_id(chatroom_id) == None

def get_chats_by_username(user_name):
    with Session(engine) as session:
        chat_room_objs = session.query(user_chat_obj).filter(user_chat_obj.user_name == user_name).all()
        
        chat_room_json = []
        for chat_room in chat_room_objs:
            chat_room_name = session.query(chat_room_obj).filter(chat_room_obj.chat_id == chat_room.chat_id).first()
            chat_room_json.append({
                'chat_name' : chat_room_name.chat_name,
                'chat_id' : chat_room.chat_id
            })
        return chat_room_json
    
def set_chat_name(chat_id, new_name):
    with Session(engine) as session:
        chat_room = session.query(chat_room_obj).filter(chat_room_obj.chat_id == chat_id).first()
        chat_room.chat_name = new_name
        session.commit()
        
def get_random_chatroom_for_user(username):
    try: 
        with Session(engine) as session:
            chat_room = session.query(user_chat_obj).filter(user_chat_obj.user_name == username).first()
            return chat_room.chat_id
    except:
        return None
        
def delete_chat_by_id(chat_id):
    with Session(engine) as session:
        chat_room = session.query(chat_room_obj).filter(chat_room_obj.chat_id == chat_id).first()
        session.delete(chat_room)

        users_to_update = []
        user_chat_associations = session.query(user_chat_obj).filter(user_chat_obj.chat_id == chat_id).all()
        for chat_user in user_chat_associations:
            users_to_update.append(chat_user.user_name)
            session.delete(chat_user)
        
        messages = session.query(message_obj).filter(message_obj.chat_id == chat_id).all()
        for message in messages:
            session.delete(message)
        
        session.commit()
        
        return users_to_update
    
def get_user_suggestion(entered_text,user_name):
    try:
        with Session(engine) as session:
            #input = f'{entered_text}%'
            #user = session.query(user_refactored).filter(user_refactored.user_name.like(input)).first()
            friends = get_friends_by_username(user_name)
            users = []
            for friend in friends:
                if friend.startswith(entered_text):
                    users.append(friend)
            return users
    except:
        return None

def add_user_to_chat(user_name, chat_id):
    with Session(engine) as session:
        existing_user = session.query(user_chat_obj).filter(user_chat_obj.user_name == user_name).filter(user_chat_obj.chat_id == chat_id).first()
        if (existing_user == None):
            message_instance = user_chat_obj(user_name=user_name,chat_id=chat_id)
            session.add(message_instance)
            session.commit()
        
        
##### Article Functions ######
def get_all_articles():
    with Session(engine) as session:
        articles = session.query(articles_obj).all()
        articles_json_array = []
        
        for article in articles:
            articles_json_array.append({
                'title' : article.title,
                'content' : article.content,
                'author' : article.author,
                'article_id' : article.article_id
            })
            
        return articles_json_array
    
def get_article_by_id(article_id):
    with Session(engine) as session:
        article = session.query(articles_obj).filter(articles_obj.article_id == int(article_id)).first()
        article_json = {
                'title' : article.title,
                'content' : article.content,
                'author' : article.author,
                'article_id' : article.article_id
            }
        return article_json
    
def post_article(article):
    with Session(engine) as session:
        article = articles_obj(title=article['title'], content=article['content'], author=article['author'])
        session.add(article)
        session.commit()
        return article.article_id

def delete_article_by_id(article_id):
    with Session(engine) as session:
        article = session.query(articles_obj).filter(articles_obj.article_id == article_id).first()
        if not (article == None):
            comment_objs = session.query(article_comment_obj).filter(article_comment_obj.article_id == article_id).all()
            for comment_obj in comment_objs:
                session.delete(comment_obj)
            session.delete(article)
            session.commit()
            
def edit_an_article(article_json):
    with Session(engine) as session:
        article = session.query(articles_obj).filter(articles_obj.article_id == article_json['article_id']).first()
        article.title = article_json['title']
        article.content = article_json['content']
        session.commit()
        
        
def post_comment_to_article(comment_json):
    with Session(engine) as session:
        comment_obj = article_comment_obj(article_id=comment_json['article_id'],
                                          comment_msg=comment_json['content'],
                                          user_name=comment_json['sender'],
                                          time_posted=datetime.datetime.now().timestamp())
        session.add(comment_obj)
        session.commit()

def get_comments_by_article_id(article_id):
    with Session(engine) as session:
        comment_objs = session.query(article_comment_obj).filter(article_comment_obj.article_id == article_id).all()
        comments_json =[]
        for comment in comment_objs:
            comments_json.append({
                'article_id':comment.article_id,
                'comment_msg':comment.comment_msg,
                'user_name':get_user_by_username_array(comment.user_name),
                'time_posted':comment.time_posted,
                'comment_id':comment.comment_id
            })
        return comments_json
    
def delete_comment_by_id(comment_id):
    with Session(engine) as session:
        comment_obj = session.query(article_comment_obj).filter(article_comment_obj.comment_id == comment_id).first()
        session.delete(comment_obj)
        session.commit()
    
def update_user_role(user_name,user_role):
    with Session(engine) as session:
        user = session.query(user_refactored).filter(user_refactored.user_name == user_name).first()
        user.user_role = user_role
        session.commit()
        
def update_user_mute(user_name,mute_status):
    with Session(engine) as session:
        user = session.query(user_refactored).filter(user_refactored.user_name == user_name).first()
        user.muted = mute_status
        session.commit()
        
def is_not_mute(user_name):
    with Session(engine) as session:
        user = session.query(user_refactored).filter(user_refactored.user_name == user_name).first()
        if (user.muted):
            return False
        return True
    
def get_user_status(user_name):
    with Session(engine) as session:
        if (user_name != None):
            user = session.query(user_refactored).filter(user_refactored.user_name == user_name).first()
            return user.user_role