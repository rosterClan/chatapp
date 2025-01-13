'''
socket_routes
file containing all the routes related to socket.io
'''

from flask_socketio import emit
from flask import request
from userManager.manager import user_manager
from flask import render_template
from flask_jwt_extended import decode_token
from flask import current_app
import jwt
import json
import common

try:
    from __main__ import socketio
    from __main__ import app
except ImportError:
    from app import socketio
import db


### For anyone who trys to change or add anything. Please know. I am so, so sorry. 

user_aggregator = user_manager()

def validate_user_content(user_name, user_hash): #Foundational security check, used in the the login process. 
    potential_user = db.get_user_by_username(user_name)
    if (potential_user == None):
        raise Exception("No user of given name.") #These errors are relayed and displayed onscreen
    if common.compare_hash(user_hash,potential_user.salt,potential_user.user_hash) == False:
        raise Exception("Invalid password")
    return True

def validate_user(user_name,user_hash): #Wpr for validate_user_content, allows other functions to use the same logic without faultering due to the flipped error
    try: 
        return validate_user_content(user_name,user_hash) 
    except Exception as e:
        return False

def relay_friend_requests(user_name:str): 
    request = {"requests":db.get_friend_requests(user_name)}
    emit("update_friend_requests",json.dumps(request),room=user_aggregator.get_relay_connection_reference(user_name))

def relay_online_friends_list(user_name:str,notify_friends=True,on_disconnect=False):
    all_friends = db.get_friends_by_username(user_name)
    online_friends = []
    for friend in all_friends:
        if (user_aggregator.is_online(friend)): #Main logic to determin if a user should be labelled online or offline
            online_friends.append([db.get_user_by_username_array(friend),True]) 
            if (notify_friends):
                relay_online_friends_list(friend,notify_friends=False)
        else:
            online_friends.append([db.get_user_by_username_array(friend),False])
    if (on_disconnect == False):
        emit("update_friends_list",json.dumps({"friends_list":online_friends}),room=user_aggregator.get_relay_connection_reference(user_name))
    


@socketio.on('relay_all_users')
def relay_all_users(message):
    message_json = json.loads(message)
    all_users = db.get_all_users()
    emit("update_users_list",json.dumps({"users_list":all_users}),room=user_aggregator.get_relay_connection_reference(message_json["sender"]))
@socketio.on('relay_searched_users')
def relay_searched_users(message):
    message_json = json.loads(message)
    all_users = db.get_all_users()
    filtered_users = []
    for user in all_users:
        if (message_json['search_term'] in user[0]):
            filtered_users.append(user)
    emit("update_users_list",json.dumps({"users_list":filtered_users}),room=user_aggregator.get_relay_connection_reference(message_json["sender"]))



@socketio.on('update_user_roll')
def update_user_roll(message):
    message_json = json.loads(message)
    db.update_user_role(message_json['user_to_change'],message_json['new_role'])
    relay_friend_requests(message_json['sender'])
    relay_online_friends_list(message_json['sender'])
    inform_status(json.dumps({'sender':message_json['user_to_change']}))
    
@socketio.on('update_mute_status')
def update_mute_status(message):
    message_json = json.loads(message)
    db.update_user_mute(message_json['user_to_change'],message_json['mute_status'])
    
@socketio.on('check_mute_status')
def check_mute_status(message):
    message_json = json.loads(message)
    db.check_mute_status(message_json['sender'])



def user_sign_up_update():
    online_users = user_aggregator.get_all_online_users()
    for users in online_users:
        relay_all_users(json.dumps({"sender":users}))

def inform_error(error_msg:str, user_name:str, registered=True): ##Allows us to inform the frontend of any error which might occur. 
    if (registered): 
        emit("error",json.dumps({"error_msg":error_msg}),room=user_aggregator.get_relay_connection_reference(user_name)) 
    else:
        emit("error",json.dumps({"error_msg":error_msg}),room=user_name) 

def jwt_token_check(token):
    try:
        decode_token(token,allow_expired=False)
        return True
    except Exception as e:
        return False

@socketio.on('user_search_get_all')
def user_search_list(message):
    message_json = json.loads(message)
    user_name = message_json["sender"]
    
    existing_friends = db.get_friends_by_username(user_name)
    all_users_objs = db.get_all_users()
    all_users_array = []
    sent_requests = db.get_friend_sent_requests(user_name)
    
    for x in range(0,len(all_users_objs)):
        if not (all_users_objs[x][0] in existing_friends) and not (all_users_objs[x][0] == user_name):
            all_users_array.append([all_users_objs[x][0],all_users_objs[x][0] in sent_requests])
    
    for entry in all_users_array:
        entry[0] = db.get_user_by_username_array(entry[0])
    
    emit("user_search_get_all",json.dumps({"users":all_users_array}),room=user_aggregator.get_relay_connection_reference(user_name))

@socketio.on('connect')
def connect(): #Main method which establishes connection to oncoming users
    user_name = request.cookies.get("username")
    user_hash = request.cookies.get("user_hash")
    
    if (validate_user(user_name,user_hash)):
        if (user_aggregator.is_online(user_name)):
            inform_error("No dual account use",request.sid,registered=False)
        else:
            connection_reference = request.sid
            user_aggregator.recognise_user(user_name, connection_reference)
            
            relay_friend_requests(user_name)
            relay_online_friends_list(user_name)
            user_sign_up_update()
    else:
        inform_error("Invalid connection credentials",request.sid,registered=False)

@socketio.on('disconnect')
def manage_disconnect(): #Manages user disconnections
    user_name = request.cookies.get("username")
    if (user_aggregator.is_online(user_name)):
        user_aggregator.unrecognise_user(user_name)
        relay_online_friends_list(user_name,on_disconnect=True)

@socketio.on("cancel_friend_request") 
def cancel_friend_request(message):
    message_json = json.loads(message)
    if db.is_valid_username(message_json['sender']) and db.is_valid_username(message_json['recipient']):
        if not message_json['sender']==message_json['recipient']: 
            db.delete_friend_request(message_json['sender'],message_json['recipient'])
            if (user_aggregator.is_online(message_json['recipient'])):
                relay_friend_requests(message_json['recipient'])
            user_search_list(message)
            relay_friend_requests(message_json['sender'])   

@socketio.on("send_friend_request") 
def send_friend_request(message):
    message_json = json.loads(message)
    if db.is_valid_username(message_json['sender']) and db.is_valid_username(message_json['recipient']):
        if not message_json['sender']==message_json['recipient']: 
            db.send_friend_request(message_json['sender'],message_json['recipient'])
            if (user_aggregator.is_online(message_json['recipient'])):
                relay_friend_requests(message_json['recipient'])
            user_search_list(message)
            relay_friend_requests(message_json['sender'])   
            
@socketio.on("send_friend_request_response") 
def send_friend_request_response(message):
    message_json = json.loads(message)
    if db.is_valid_username(message_json['sender']) and db.is_valid_username(message_json['recipient']):
        if (message_json['message']):
            db.append_friends_relationship(message_json['sender'],message_json['recipient'])
        db.delete_friend_request(message_json['sender'],message_json['recipient'])
        
        if (user_aggregator.is_online(message_json['sender'])):
            relay_online_friends_list(message_json['sender'])
            relay_friend_requests(message_json['sender'])
        if (user_aggregator.is_online(message_json['recipient'])):
            relay_online_friends_list(message_json['recipient'])
            relay_friend_requests(message_json['recipient'])
            
@socketio.on("new_chat_room")
def create_new_chat_room(message):
    message_json = json.loads(message)
    if (db.is_not_mute(message_json['sender'])):
        if db.is_valid_username(message_json['sender']):
            chat_room_id = db.create_new_chatroom(message_json['sender'])
            get_chatroom_config(message)
            send_chat_room(json.dumps({'sender':message_json['sender'],'chat_room_id':chat_room_id}))
    else:
        inform_error("You cannot make a new chat room when muted.",request.sid,registered=False)

@socketio.on("open_chat")
def send_chat_room(message):
    message_json = json.loads(message)
    if db.is_valid_username(message_json['sender']):
        chat_room_details = db.get_chat_room_by_id(message_json['chat_room_id'])
        emit("open_chat_room",json.dumps(chat_room_details),room=user_aggregator.get_relay_connection_reference(message_json['sender']))

@socketio.on("add_user_to_chat")
def add_user_to_chat(message):
    message_json = json.loads(message)
    if (db.is_not_mute(message_json['sender'])):
        if (db.is_valid_username(message_json['sender']) and db.is_valid_username(message_json['add_user'])):
            if (db.is_valid_chatroomid(message_json['chat_room_id'])):
                db.add_user_to_chat(message_json['add_user'],message_json['chat_room_id'])
                update_chat_for_relevent_online_users(message_json['chat_room_id'])
    else:
        inform_error("You cannot post to group chats when muted.",request.sid,registered=False)

@socketio.on("send_message_to_chat")
def send_messaage_to_chat(message):
    message_json = json.loads(message)
    if (db.is_not_mute(message_json['sender'])):
        if db.is_valid_username(message_json['sender']) and db.is_valid_chatroomid(message_json['chat_room_id']):
            db.add_message_to_chat(message_json['sender'],message_json['message'],message_json['chat_room_id'])
            update_chat_for_relevent_online_users(message_json['chat_room_id'])
    else:
        inform_error("You cannot send messages when muted.",request.sid,registered=False)


@socketio.on("get_chatrooms")
def get_chatroom_config(message):
    message_json = json.loads(message)
    user_name = message_json['sender']
    emit('recieve_chatrooms',json.dumps({"chat_rooms":db.get_chats_by_username(user_name)}),room=user_aggregator.get_relay_connection_reference(user_name))

@socketio.on('change_chat_name')
def change_chat_name(message):
    message_json = json.loads(message)
    db.set_chat_name(int(message_json['chat_id']),message_json['new_chat_name'])
    update_chat_for_relevent_online_users(message_json['chat_id'])
    
def update_chat_for_relevent_online_users(chat_id):
    chat_room = db.get_chat_room_by_id(chat_id)
    for user in chat_room['members']:
        if user_aggregator.is_online(user):
            send_chat_room(json.dumps({'sender':user,'chat_room_id':chat_id}))
            get_chatroom_config(json.dumps({'sender':user}))

@socketio.on("delete_chat_by_id")
def delete_chat_by_id(message):
    message_json = json.loads(message)
    users_to_update = db.delete_chat_by_id(message_json['chat_room_id'])
    
    for user in users_to_update:
        if user_aggregator.is_online(user):
            get_chatroom_config(json.dumps({'sender':user}))
            new_chat_room_id = db.get_random_chatroom_for_user(user)
            send_chat_room(json.dumps({'sender':user,'chat_room_id':new_chat_room_id}))
    
@socketio.on("get_autocomplete_suggestions")
def get_autocomplete_suggestions(message):
    message_json = json.loads(message)
    suggestion = db.get_user_suggestion(message_json['entered'],message_json['sender'])

    emit("name_suggestion",json.dumps({"suggestion":suggestion}),room=user_aggregator.get_relay_connection_reference(message_json['sender']))
    
###### Article Functions ######
@socketio.on("get_articles")
def get_articles_config(message):
    message_json = json.loads(message)
    user_name = message_json['sender']
    emit('recieve_articles',json.dumps({"articles":db.get_all_articles()}),room=user_aggregator.get_relay_connection_reference(user_name))

@socketio.on("get_article_by_id")
def get_article_by_id(message):
    message_json = json.loads(message)
    
    article = db.get_article_by_id(message_json['article_id'])
    article['author'] = db.get_user_by_username_array(article['author'])
        
    emit("open_article",json.dumps(article),room=user_aggregator.get_relay_connection_reference(message_json['sender']))
    get_comments_by_article_id(message)

@socketio.on("post_article")
def post_article(message):
    message_json = json.loads(message)
    if (db.is_not_mute(message_json['sender'])):
        if (message_json['article']['article_id'] == 'null'):
            article_id = db.post_article(message_json['article'])
            get_articles_config(message)
            message_json['article_id'] = article_id
            get_article_by_id(json.dumps(message_json))
        else:
            db.edit_an_article(message_json['article'])
            message_json['article_id'] = message_json['article']['article_id']
            get_article_by_id(json.dumps(message_json))

            online_users = user_aggregator.get_all_online_users()
            for user in online_users:
                get_article_by_id(json.dumps({'article_id':message_json['article_id'],'sender':user}))
        update_everyones_article_list()
    else:
        inform_error("You cannot post articles when muted.",request.sid,registered=False)
    
def update_everyones_article_list():
    all_online_users = user_aggregator.get_all_online_users()
    for user in all_online_users:
        get_articles_config(json.dumps({'sender':user}))
    
@socketio.on("delete_article")
def delete_article(message):
    message_json = json.loads(message)
    db.delete_article_by_id(message_json['article_id'])
    update_everyones_article_list()
    hide_deleted_article_from_users(message_json['article_id'])

def hide_deleted_article_from_users(article_id):
    online_users = user_aggregator.get_all_online_users()
    for user in online_users:
        emit('inform_deleted_article',json.dumps({"article_id":article_id}),room=user_aggregator.get_relay_connection_reference(user))
    
@socketio.on("post_comment")
def post_comment(message):
    message_json = json.loads(message)
    if (db.is_not_mute(message_json['sender'])):
        if not (message_json['article_id'] == None):
            db.post_comment_to_article(message_json)
            update_everyones_comment_section(message_json['article_id'])
    else:
        inform_error("You cannot post commented when muted",request.sid,registered=False)

@socketio.on("delete_post_by_id")
def delete_post_by_id(message):
    message_json = json.loads(message)
    db.delete_comment_by_id(int(message_json['comment_id']))
    update_everyones_comment_section(message_json['article_id'])

def update_everyones_comment_section(article_id):
    online_users = user_aggregator.get_all_online_users()
    for user in online_users:
        get_comments_by_article_id(json.dumps({'sender':user,'article_id':article_id}))

@socketio.on("get_comments_by_article_id")
def get_comments_by_article_id(message):
    message_json = json.loads(message)
    comments = db.get_comments_by_article_id(message_json['article_id'])
    emit("get_article_comments",json.dumps({'article_id':message_json['article_id'],'comments':comments}),room=user_aggregator.get_relay_connection_reference(message_json['sender']))

@socketio.on("inform_status")
def inform_status(message):
    message_json = json.loads(message)
    status = db.get_user_status(message_json['sender'])
    emit("get_user_status",json.dumps({'status':status}),room=user_aggregator.get_relay_connection_reference(message_json['sender']))