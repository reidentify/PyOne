#-*- coding=utf-8 -*-
from config import *
from views import *
from function import *
from __init__ import *
import sys
import eventlet
reload(sys)
sys.setdefaultencoding("utf-8")
eventlet.monkey_patch()



######################注册应用
from admin import admin as admin_blueprint
app.register_blueprint(admin_blueprint)


######################函数
app.jinja_env.globals['FetchData']=FetchData
app.jinja_env.globals['path_list']=path_list
app.jinja_env.globals['CanEdit']=CanEdit
app.jinja_env.globals['len']=len
app.jinja_env.globals['enumerate']=enumerate
app.jinja_env.globals['os']=os
app.jinja_env.globals['re']=re
app.jinja_env.globals['file_ico']=file_ico
app.jinja_env.globals['title']=title
app.jinja_env.globals['tj_code']=tj_code if tj_code is not None else ''
app.jinja_env.globals['allow_site']=','.join(allow_site)
app.jinja_env.globals['share_path']=share_path
app.jinja_env.globals['downloadUrl_timeout']=downloadUrl_timeout
################################################################################
#####################################启动#######################################
################################################################################
if __name__=='__main__':
    app.run(port=58693,debug=True)



