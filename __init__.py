#-*- coding=utf-8 -*-
from flask import Flask,render_template,redirect,abort,make_response,jsonify,request,url_for,Response
from flask_sqlalchemy import Pagination
from redis import Redis
from flask_caching import Cache
from flask_pymongo import PyMongo,ASCENDING,DESCENDING
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
from config import *
#######flask
app=Flask(__name__)
app.secret_key=os.path.join(config_dir,'PyOne'+password)
app.config["CACHE_TYPE"] = "redis"
app.config["MONGO_URI"] = "mongodb://localhost:27017/two"
cache = Cache(app)
mongo = PyMongo(app)
db=mongo.db
items=mongo.db.items
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200/minute", "50/second"],
)

rd=Redis(host='127.0.0.1',port=6379)
