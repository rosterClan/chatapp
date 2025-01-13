from flask import Flask, render_template, request, abort, url_for, Response
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
from sqlalchemy.orm import Session
import db
import secrets
from flask import jsonify, request
from flask_jwt_extended import create_access_token
from datetime import timedelta
import os
import common

app = Flask(__name__)

script_dir = os.path.dirname(os.path.abspath(__file__))
# certificate = os.path.join(script_dir,"certs/flaskapp.crt")
# certificatePrivateKey = os.path.join(script_dir,"certs/flaskapp.key")

certificate = os.path.join(script_dir,"certs/luna/flaskapp.crt")
certificatePrivateKey = os.path.join(script_dir,"certs/luna/flaskapp.key")

app.config['JWT_SECRET_KEY'] = common.hash_string(open(certificatePrivateKey, 'r').read())
socketio = SocketIO(app)
jwt = JWTManager(app)

username = ""
all_users = []

import socket_routes

@app.route("/")
def index():
    return render_template("index.jinja")

@app.route("/login")
def login():    
    return render_template("login.jinja")

@app.route("/login/user", methods=["POST"])
def login_user():
    global username

    if not request.is_json:
        abort(404)

    user_hash = request.json.get("user_hash")
    username = request.json.get("username")
    access_token = create_access_token(identity=username,expires_delta=timedelta(days=1))

    try:
        socket_routes.validate_user_content(username,user_hash)
        return jsonify(access_token=access_token,error=None,redirect=url_for('home'))
    except Exception as e:
        return jsonify(access_token=None,error=str(e),redirect=None)

@app.route("/signup")
def signup():
    return render_template("signup.jinja")

@app.route("/signup/user", methods=["POST"])
def signup_user():
    if not request.is_json:
        abort(404)

    username = request.json.get("username")    
    user_hash = request.json.get("user_hash")
    
    if username.strip() == "":
        return jsonify(access_token=None,error="No empty space username",redirect=None)

    if db.get_user_by_username(username) == None:
        db.insert_user_refactored(user_hash,username)

        access_token = create_access_token(identity=username,expires_delta=timedelta(days=1))
        return jsonify(access_token=access_token,error=None,redirect=url_for('home')) 
    else:
        return jsonify(access_token=None,error="Please select a unique username",redirect=None)

@app.errorhandler(404)
def page_not_found(_):
    return render_template('404.jinja'), 404

@app.route("/home")
def home():
    global all_users
    all_users = db.get_all_users()
    user_role = db.get_user_role(username)
    return render_template("home.jinja", user_role=user_role, all_users=all_users)

if __name__ == '__main__':
    app.jinja_env.auto_reload = True
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    socketio.run(app,ssl_context=(certificate, certificatePrivateKey))
    