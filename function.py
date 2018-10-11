#-*- coding=utf-8 -*-
import json
import requests
import collections
import sys
reload(sys)
sys.setdefaultencoding('utf-8')
if sys.version_info[0]==3:
    import urllib.parse as urllib
else:
    import urllib
import os
import re
import time
import shutil
import base64
import hashlib
import markdown
import humanize
import StringIO
from dateutil.parser import parse
from Queue import Queue
from threading import Thread
from config import *
from __init__ import *

#######授权链接
LoginUrl=BaseAuthUrl+'/common/oauth2/v2.0/authorize?response_type=code\
&client_id={client_id}&redirect_uri={redirect_uri}&scope=offline_access%20files.readwrite.all'
OAuthUrl=BaseAuthUrl+'/common/oauth2/v2.0/token'
AuthData='client_id={client_id}&redirect_uri={redirect_uri}&client_secret={client_secret}&code={code}&grant_type=authorization_code'
ReFreshData='client_id={client_id}&redirect_uri={redirect_uri}&client_secret={client_secret}&refresh_token={refresh_token}&grant_type=refresh_token'

headers={'User-Agent':'ISV|PyOne|PyOne/2.0'}

def convert2unicode(string):
    return string.encode('utf-8')

def get_value(key):
    allow_key=['client_secret','client_id']
    if key not in allow_key:
        return u'禁止获取'
    config_path=os.path.join(config_dir,'config.py')
    with open(config_path,'r') as f:
        value=re.findall('{}="(.*)"'.format(key),f.read())[0]
    return value


################################################################################
###################################授权函数#####################################
################################################################################
def open_json(filepath):
    token=False
    with open(filepath,'r') as f:
        try:
            token=json.load(f)
        except:
            for i in range(1,10):
                try:
                    token=json.loads(f.read()[:-i])
                except:
                    token=False
                if token!=False:
                    return token
    return token

def ReFreshToken(refresh_token):
    client_id=get_value('client_id')
    client_secret=get_value('client_secret')
    headers['Content-Type']='application/x-www-form-urlencoded'
    data=ReFreshData.format(client_id=client_id,redirect_uri=urllib.quote(redirect_uri),client_secret=client_secret,refresh_token=refresh_token)
    url=OAuthUrl
    r=requests.post(url,data=data,headers=headers)
    return json.loads(r.text)


def GetToken(Token_file='token.json'):
    if os.path.exists(os.path.join(data_dir,Token_file)):
        token=open_json(os.path.join(data_dir,Token_file))
        try:
            if time.time()>int(token.get('expires_on')):
                print 'token timeout'
                refresh_token=token.get('refresh_token')
                token=ReFreshToken(refresh_token)
                if token.get('access_token'):
                    with open(os.path.join(data_dir,Token_file),'w') as f:
                        json.dump(token,f,ensure_ascii=False)
        except:
            with open(os.path.join(data_dir,'Atoken.json'),'r') as f:
                Atoken=json.load(f)
            refresh_token=Atoken.get('refresh_token')
            token=ReFreshToken(refresh_token)
            if token.get('access_token'):
                    with open(os.path.join(data_dir,Token_file),'w') as f:
                        json.dump(token,f,ensure_ascii=False)
        return token.get('access_token')
    else:
        return False


def GetAppUrl():
    global app_url
    if os.path.exists(os.path.join(data_dir,'AppUrl')):
        with open(os.path.join(data_dir,'AppUrl'),'r') as f:
            app_url=f.read().strip()
        return app_url
    else:
        # if od_type=='business':
        #     token=GetToken(Token_file='Atoken.json')
        #     print 'token:',token
        #     if token:
        #         header={'Authorization': 'Bearer {}'.format(token)}
        #         url='https://api.office.com/discovery/v1.0/me/services'
        #         r=requests.get(url,headers=header)
        #         retdata=json.loads(r.text)
        #         print retdata
        #         if retdata.get('value'):
        #             return retdata.get('value')[0]['serviceResourceId']
        #     return False
        # else:
        #     return app_url
        return app_url

################################################################################
###############################onedrive操作函数#################################
################################################################################
def GetExt(name):
    try:
        return name.split('.')[-1]
    except:
        return 'file'

def date_to_char(date):
    return date.strftime('%Y/%m/%d')

def Dir(path=u'/'):
    app_url=GetAppUrl()
    if path=='/':
        BaseUrl=app_url+u'v1.0/me/drive/root/children?expand=thumbnails'
        items.remove()
        queue=Queue()
        # queue.put(dict(url=BaseUrl,grandid=grandid,parent=parent,trytime=1))
        g=GetItemThread(queue)
        g.GetItem(BaseUrl)
        queue=g.queue
        if queue.qsize()==0:
            return
        tasks=[]
        for i in range(min(5,queue.qsize())):
            t=GetItemThread(queue)
            t.start()
            tasks.append(t)
        for t in tasks:
            t.join()
        RemoveRepeatFile()
    else:
        grandid=0
        parent=''
        if path.endswith('/'):
            path=path[:-1]
        if not path.startswith('/'):
            path='/'+path
        if items.find_one({'grandid':0,'type':'folder'}):
            parent_id=0
            for idx,p in enumerate(path[1:].split('/')):
                if parent_id==0:
                    parent_id=items.find_one({'name':p,'grandid':idx})['id']
                else:
                    parent_id=items.find_one({'name':p,'grandid':idx,'parent':parent_id})['id']
                items.delete_many({'parent':parent_id})
            grandid=idx+1
            parent=parent_id
        path=urllib.quote(path)
        BaseUrl=app_url+u'v1.0/me/drive/root:{}:/children?expand=thumbnails'.format(path)
        queue=Queue()
        # queue.put(dict(url=BaseUrl,grandid=grandid,parent=parent,trytime=1))
        g=GetItemThread(queue)
        g.GetItem(BaseUrl,grandid,parent,1)
        queue=g.queue
        if queue.qsize()==0:
            return
        tasks=[]
        for i in range(min(10,queue.qsize())):
            t=GetItemThread(queue)
            t.start()
            tasks.append(t)
        for t in tasks:
            t.join()
        RemoveRepeatFile()
        CreateIndex()


class GetItemThread(Thread):
    def __init__(self,queue):
        super(GetItemThread,self).__init__()
        self.queue=queue
        if share_path=='/':
            self.share_path=share_path
        else:
            sp=share_path
            if not sp.startswith('/'):
                sp='/'+share_path
            if sp.endswith('/') and sp!='/':
                sp=sp[:-1]
            self.share_path=sp

    def run(self):
        while 1:
            time.sleep(0.5) #避免过快
            info=self.queue.get()
            url=info['url']
            grandid=info['grandid']
            parent=info['parent']
            trytime=info['trytime']
            self.GetItem(url,grandid,parent,trytime)
            if self.queue.empty():
                time.sleep(5) #再等5s
                print('waiting 5s if queue is not empty')
                if self.queue.empty():
                    break

    def GetItem(self,url,grandid=0,parent='',trytime=1):
        app_url=GetAppUrl()
        token=GetToken()
        print(u'getting files from url {}'.format(url))
        header={'Authorization': 'Bearer {}'.format(token)}
        try:
            r=requests.get(url,headers=header)
            data=json.loads(r.content)
            if data.get('error'):
                print('error:{}! waiting 180s'.format(data.get('error').get('message')))
                time.sleep(180)
                self.queue.put(dict(url=url,grandid=grandid,parent=parent,trytime=trytime))
                return
            values=data.get('value')
            if len(values)>0:
                for value in values:
                    item={}
                    if value.get('folder'):
                        item['type']='folder'
                        item['order']=0
                        item['name']=convert2unicode(value['name'])
                        item['id']=convert2unicode(value['id'])
                        item['size']=humanize.naturalsize(value['size'], gnu=True)
                        item['size_order']=int(value['size'])
                        item['lastModtime']=date_to_char(parse(value['lastModifiedDateTime']))
                        item['grandid']=grandid
                        item['parent']=parent
                        grand_path=value.get('parentReference').get('path').replace('/drive/root:','')
                        if grand_path=='':
                            path=convert2unicode(value['name'])
                        else:
                            path=grand_path.replace(self.share_path,'',1)+'/'+convert2unicode(value['name'])
                        if path.startswith('/') and path!='/':
                            path=path[1:]
                        if path=='':
                            path=convert2unicode(value['name'])
                        item['path']=path
                        subfodler=items.insert_one(item)
                        if value.get('folder').get('childCount')==0:
                            continue
                        else:
                            url=app_url+'v1.0/me'+value.get('parentReference').get('path')+'/'+value.get('name')+':/children?expand=thumbnails'
                            self.queue.put(dict(url=url,grandid=grandid+1,parent=item['id'],trytime=1))
                    else:
                        item['type']=GetExt(value['name'])
                        grand_path=value.get('parentReference').get('path').replace('/drive/root:','')
                        if grand_path=='':
                            path=convert2unicode(value['name'])
                        else:
                            path=grand_path.replace(self.share_path,'',1)+'/'+convert2unicode(value['name'])
                        if path.startswith('/') and path!='/':
                            path=path[1:]
                        if path=='':
                            path=convert2unicode(value['name'])
                        item['path']=path
                        item['name']=convert2unicode(value['name'])
                        item['id']=convert2unicode(value['id'])
                        item['size']=humanize.naturalsize(value['size'], gnu=True)
                        item['size_order']=int(value['size'])
                        item['lastModtime']=date_to_char(parse(value['lastModifiedDateTime']))
                        item['grandid']=grandid
                        item['parent']=parent
                        if GetExt(value['name']) in ['bmp','jpg','jpeg','png','gif']:
                            item['order']=3
                            key1='name:{}'.format(value['id'])
                            key2='path:{}'.format(value['id'])
                            rd.set(key1,value['name'])
                            rd.set(key2,path)
                        elif value['name']=='.password':
                            item['order']=1
                        else:
                            item['order']=2
                        items.insert_one(item)
            if data.get('@odata.nextLink'):
                self.queue.put(dict(url=data.get('@odata.nextLink'),grandid=grandid,parent=parent,trytime=1))
        except Exception as e:
            trytime+=1
            print(u'error to opreate GetItem("{}","{}","{}"),try times :{}, reason: {}'.format(url,grandid,parent,trytime,e))
            if trytime<=3:
                self.queue.put(dict(url=url,grandid=grandid,parent=parent,trytime=trytime))

    def GetItemByPath(self,path):
        if path=='':
            path='/'
        app_url=GetAppUrl()
        token=GetToken()
        header={'Authorization': 'Bearer {}'.format(token)}
        url=app_url+u'v1.0/me/drive/root:{}:/'.format(path)
        r=requests.get(url,headers=header)
        data=json.loads(r.content)
        return data


def UpdateFile():
    items.remove()
    Dir(share_path)
    print('update file success!')


def FileExists(filename):
    token=GetToken()
    headers={'Authorization':'bearer {}'.format(token),'Content-Type':'application/json'}
    search_url=app_url+"v1.0/me/drive/root/search(q='{}')".format(filename)
    r=requests.get(search_url,headers=headers)
    jsondata=json.loads(r.text)
    if len(jsondata['value'])==0:
        return False
    else:
        return True

def FileInfo(fileid):
    token=GetToken()
    headers={'Authorization':'bearer {}'.format(token),'Content-Type':'application/json'}
    search_url=app_url+"v1.0/me/drive/items/{}".format(fileid)
    r=requests.get(search_url,headers=headers)
    jsondata=json.loads(r.text)
    return jsondata


################################################上传文件
def list_all_files(rootdir):
    import os
    _files = []
    if len(re.findall('[:#\|\?]+',rootdir))>0:
        newf=re.sub('[:#\|\?]+','',rootdir)
        shutil.move(rootdir,newf)
        rootdir=newf
    if rootdir.endswith(' '):
        shutil.move(rootdir,rootdir.rstrip())
        rootdir=rootdir.rstrip()
    if len(re.findall('/ ',rootdir))>0:
        newf=re.sub('/ ','/',rootdir)
        shutil.move(rootdir,newf)
        rootdir=newf
    flist = os.listdir(rootdir) #列出文件夹下所有的目录与文件
    for f in flist:
        path = os.path.join(rootdir,f)
        if os.path.isdir(path):
            _files.extend(list_all_files(path))
        if os.path.isfile(path):
            _files.append(path)
    return _files

def _filesize(path):
    size=os.path.getsize(path)
    # print('{}\'s size {}'.format(path,size))
    return size

def _file_content(path,offset,length):
    size=_filesize(path)
    offset,length=map(int,(offset,length))
    if offset>size:
        print('offset must smaller than file size')
        return False
    length=length if offset+length<size else size-offset
    endpos=offset+length-1 if offset+length<size else size-1
    # print("read file {} from {} to {}".format(path,offset,endpos))
    with open(path,'rb') as f:
        f.seek(offset)
        content=f.read(length)
    return content



def _upload(filepath,remote_path): #remote_path like 'share/share.mp4'
    token=GetToken()
    headers={'Authorization':'bearer {}'.format(token)}
    url=app_url+'v1.0/me/drive/root:'+urllib.quote(remote_path)+':/content'
    r=requests.put(url,headers=headers,data=open(filepath,'rb'))
    trytime=1
    while 1:
        try:
            if data.get('error'):
                print(data.get('error').get('message'))
                return False
            elif data.get('@microsoft.graph.downloadUrl'):
                return data
            else:
                print(data)
                return False
        except Exception as e:
            trytime+=1
            print('error to opreate _upload("{}","{}"), try times {}'.format(filepath,remote_path,trytime))
        finally:
            if trytime>3:
                break

def _upload_part(uploadUrl, filepath, offset, length,trytime=1):
    size=_filesize(filepath)
    offset,length=map(int,(offset,length))
    if offset>size:
        print('offset must smaller than file size')
        return {'status':'fail','msg':'params mistake','code':1}
    length=length if offset+length<size else size-offset
    endpos=offset+length-1 if offset+length<size else size-1
    print('upload file {} {}%'.format(filepath,round(float(endpos)/size*100,1)))
    filebin=_file_content(filepath,offset,length)
    headers={}
    # headers['Authorization']='bearer {}'.format(token)
    headers['Content-Length']=str(length)
    headers['Content-Range']='bytes {}-{}/{}'.format(offset,endpos,size)
    try:
        r=requests.put(uploadUrl,headers=headers,data=filebin)
        data=json.loads(r.content)
        if data.get('@microsoft.graph.downloadUrl'):
            print(u'{} upload success!'.format(filepath))
            return {'status':'success','msg':'all upload success','code':0,'info':data}
        elif r.status_code==202:
            offset=data.get('nextExpectedRanges')[0].split('-')[0]
            return {'status':'success','msg':'partition upload success','code':1,'offset':offset}
        else:
            trytime+=1
            if trytime<=3:
                return {'status':'fail'
                        ,'msg':'please retry'
                        ,'sys_msg':data.get('error').get('message')
                        ,'code':2,'trytime':trytime}
            else:
                return {'status':'fail'
                        ,'msg':'retry times limit'
                        ,'sys_msg':data.get('error').get('message')
                        ,'code':3}
    except Exception as e:
        trytime+=1
        print('error to opreate _upload_part("{}","{}","{}","{}"), try times {}'.format(uploadUrl, filepath, offset, length,trytime))
        if trytime<=3:
            return {'status':'fail','msg':'please retry','code':2,'trytime':trytime,'sys_msg':''}
        else:
            return {'status':'fail','msg':'retry times limit','code':3,'sys_msg':''}

def _GetAllFile(parent_id="",parent_path="",filelist=[]):
    for f in db.items.find({'parent':parent_id}):
        if f['type']=='folder':
            _GetAllFile(f['id'],'/'.join([parent_path,f['name']]),filelist)
        else:
            fp='/'.join([parent_path,f['name']])
            if fp.startswith('/'):
                fp=base64.b64encode(fp[1:].encode('utf-8'))
            else:
                fp=base64.b64encode(fp.encode('utf-8'))
            filelist.append(fp)
    return filelist


def AddResource(data):
    #检查父文件夹是否在数据库，如果不在则获取添加
    grand_path=data.get('parentReference').get('path').replace('/drive/root:','')
    if grand_path=='':
        parent_id=''
        grandid=0
    else:
        g=GetItemThread(Queue())
        parent_id=data.get('parentReference').get('id')
        grandid=len(data.get('parentReference').get('path').replace('/drive/root:','').split('/'))-1
        grand_path=grand_path[1:]
        parent_path=''
        pid=''
        for idx,p in enumerate(grand_path.split('/')):
            parent=items.find_one({'name':p,'grandid':idx,'parent':pid})
            if parent is not None:
                pid=parent['id']
                parent_path='/'.join([parent_path,parent['name']])
            else:
                parent_path='/'.join([parent_path,p])
                fdata=g.GetItemByPath(parent_path)
                item={}
                item['type']='folder'
                item['name']=fdata.get('name')
                item['id']=fdata.get('id')
                item['size']=humanize.naturalsize(fdata.get('size'), gnu=True)
                item['lastModtime']=date_to_char(parse(fdata.get('lastModifiedDateTime')))
                item['grandid']=idx
                item['parent']=pid
                items.insert_one(item)
                pid=fdata.get('id')
    #插入数据
    item={}
    item['type']='file'
    item['name']=data.get('name')
    item['id']=data.get('id')
    item['size']=humanize.naturalsize(data.get('size'), gnu=True)
    item['lastModtime']=date_to_char(parse(data.get('lastModifiedDateTime')))
    item['grandid']=grandid
    item['parent']=parent_id
    items.insert_one(item)


def CreateUploadSession(path):
    token=GetToken()
    headers={'Authorization':'bearer {}'.format(token),'Content-Type':'application/json'}
    url=app_url+'v1.0/me/drive/root:'+urllib.quote(path)+':/createUploadSession'
    data={
          "item": {
            "@microsoft.graph.conflictBehavior": "rename",
          }
        }
    try:
        r=requests.post(url,headers=headers,data=json.dumps(data))
        retdata=json.loads(r.content)
        if r.status_code==409:
            print('file exists')
            return False
        else:
            return retdata
    except Exception as e:
        print('error to opreate CreateUploadSession("{}"),reason {}'.format(path,e))
        return False

def UploadSession(uploadUrl, filepath):
    token=GetToken()
    length=327680*10
    offset=0
    trytime=1
    while 1:
        result=_upload_part(uploadUrl, filepath, offset, length,trytime=trytime)
        code=result['code']
        #上传完成
        if code==0:
            return result['info']
        #分片上传成功
        elif code==1:
            trytime=1
            offset=result['offset']
        #错误，重试
        elif code==2:
            if result['sys_msg']=='The request has been throttled':
                print(result['sys_msg']+' ; wait for 1800s')
                time.sleep(1800)
            offset=offset
            trytime=result['trytime']
        #重试超过3次，放弃
        elif code==3:
            return False



def Upload(filepath,remote_path=None):
    token=GetToken()
    headers={'Authorization':'bearer {}'.format(token),'Content-Type':'application/json'}
    if remote_path is None:
        remote_path=os.path.basename(filepath)
    if remote_path.endswith('/'):
        remote_path=os.path.join(remote_path,os.path.basename(filepath))
    if not remote_path.startswith('/'):
        remote_path='/'+remote_path
    if _filesize(filepath)<1024*1024*3.25:
        result=_upload(filepath,remote_path)
        if result==False:
            print(u'{} upload fail!'.format(filepath))
        else:
            print(u'{} upload success!'.format(filepath))
            AddResource(result)
    else:
        session_data=CreateUploadSession(remote_path)
        if session_data==False:
            print('file exists')
        else:
            if session_data.get('uploadUrl'):
                uploadUrl=session_data.get('uploadUrl')
                data=UploadSession(uploadUrl,filepath)
                if data!=False:
                    AddResource(data)
            else:
                print(session_data)
                print('create upload session fail! {}'.format(remote_path))
                return False


class MultiUpload(Thread):
    def __init__(self,waiting_queue):
        super(MultiUpload,self).__init__()
        self.queue=waiting_queue

    def run(self):
        while not self.queue.empty():
            localpath,remote_dir=self.queue.get()
            Upload(localpath,remote_dir)


def UploadDir(local_dir,remote_dir,threads=5):
    print(u'geting file from dir {}'.format(local_dir))
    localfiles=list_all_files(local_dir)
    print(u'get {} files from dir {}'.format(len(localfiles),local_dir))
    print(u'check filename')
    for f in localfiles:
        dir_,fname=os.path.dirname(f),os.path.basename(f)
        if len(re.findall('[:/#\|]+',fname))>0:
            newf=os.path.join(dir_,re.sub('[:/#\|]+','',fname))
            shutil.move(f,newf)
    localfiles=list_all_files(local_dir)
    check_file_list=[]
    if local_dir.endswith('/'):
        local_dir=local_dir[:-1]
    for file in localfiles:
        dir_,fname=os.path.dirname(file),os.path.basename(file)
        remote_path=remote_dir+'/'+dir_.replace(local_dir,'')+'/'+fname
        remote_path=remote_path.replace('//','/')
        check_file_list.append((remote_path,file))
    print(u'check repeat file')
    if remote_dir=='/':
        cloud_files=_GetAllFile()
    else:
        if remote_dir.startswith('/'):
            remote_dir=remote_dir[1:]
        if items.find_one({'grandid':0,'type':'folder','name':remote_dir.split('/')[0]}):
            parent_id=0
            parent_path=''
            for idx,p in enumerate(remote_dir.split('/')):
                if parent_id==0:
                    parent=items.find_one({'name':p,'grandid':idx})
                    parent_id=parent['id']
                    parent_path='/'.join([parent_path,parent['name']])
                else:
                    parent=items.find_one({'name':p,'grandid':idx,'parent':parent_id})
                    parent_id=parent['id']
                    parent_path='/'.join([parent_path,parent['name']])
            grandid=idx+1
            cloud_files=_GetAllFile(parent_id,parent_path)
    try:
        cloud_files=dict([(i,i) for i in cloud_files])
    except:
        cloud_files={}
    queue=Queue()
    tasks=[]
    for remote_path,file in check_file_list:
        if not cloud_files.get(base64.b64encode(remote_path)):
            queue.put((file,remote_path))
    print "check_file_list {},cloud_files {},queue {}".format(len(check_file_list),len(cloud_files),queue.qsize())
    print "start upload files 5s later"
    time.sleep(5)
    for i in range(min(threads,queue.qsize())):
        t=MultiUpload(queue)
        t.start()
        tasks.append(t)
    for t in tasks:
        t.join()
    #删除错误数据
    RemoveRepeatFile()



########################删除文件
def DeleteLocalFile(fileid):
    items.remove({'id':fileid})

def DeleteRemoteFile(fileid):
    app_url=GetAppUrl()
    token=GetToken()
    headers={'Authorization':'bearer {}'.format(token)}
    url=app_url+'v1.0/me/drive/items/'+fileid
    r=requests.delete(url,headers=headers)
    if r.status_code==204:
        DeleteLocalFile(fileid)
        return True
    else:
        return False

########################
def CheckTimeOut(fileid):
    app_url=GetAppUrl()
    token=GetToken()
    headers={'Authorization':'bearer {}'.format(token),'Content-Type':'application/json'}
    url=app_url+'v1.0/me/drive/items/'+fileid
    r=requests.get(url,headers=headers)
    data=json.loads(r.content)
    if data.get('@microsoft.graph.downloadUrl'):
        downloadUrl=data.get('@microsoft.graph.downloadUrl')
        start_time=time.time()
        for i in range(10000):
            r=requests.head(downloadUrl)
            print '{}\'s gone, status:{}'.format(time.time()-start_time,r.status_code)
            if r.status_code==404:
                break


def RemoveRepeatFile():
    """
    db.items.aggregate([
        {
            $group:{_id:{id:'$id'},count:{$sum:1},dups:{$addToSet:'$_id'}}
        },
        {
            $match:{count:{$gt:1}}
        }

        ]).forEach(function(it){

             it.dups.shift();
            db.items.remove({_id: {$in: it.dups}});

        });
    """
    deleteData=items.aggregate([
    {'$group': {
        '_id': { 'id': "$id"},
        'uniqueIds': { '$addToSet': "$_id" },
        'count': { '$sum': 1 }
      }},
      { '$match': {
        'count': { '$gt': 1 }
      }}
    ]);
    first=True
    try:
        for d in deleteData:
            first=True
            for did in d['uniqueIds']:
                if not first:
                    items.delete_one({'_id':did});
                first=False
    except Exception as e:
        print(e)
        return


def CreateIndex():
    items.create_index([('name',DESCENDING),('lastModtime',DESCENDING),('size_order',DESCENDING),('type',DESCENDING),('order',ASCENDING)])


################################################################################
###################################功能函数#####################################
################################################################################
def md5(string):
    a=hashlib.md5()
    a.update(string.encode(encoding='utf-8'))
    return a.hexdigest()

def GetTotal(path):
    key='total:{}'.format(path)
    if rd.exists(key):
        return int(rd.get(key))
    else:
        if path=='/':
            total=items.find({'grandid':0}).count()
        else:
            f=items.find_one({'path':path})
            pid=f['id']
            total=items.find({'parent':pid}).count()
            rd.set(key,total,300)
        return total


# @cache.memoize(timeout=60*5)
def FetchData(path='/',page=1,per_page=50,sortby='lastModtime',order='desc',dismiss=False):
    path=urllib.unquote(path)
    resp=[]
    if sortby not in ['lastModtime','type','size','name']:
        sortby='lastModtime'
    if sortby=='size':
        sortby='size_order'
    if order=='desc':
        order=DESCENDING
    else:
        order=ASCENDING
    try:
        if path=='/':
            data=items.find({'grandid':0}).collation({"locale": "zh", 'numericOrdering':True})\
                .sort([('order',ASCENDING),(sortby,order)])\
                .limit(per_page).skip((page-1)*per_page)
            for d in data:
                item={}
                item['name']=d['name']
                item['id']=d['id']
                item['lastModtime']=d['lastModtime']
                item['size']=d['size']
                item['type']=d['type']
                if dismiss:
                    if d['name'] not in ('README.md','README.txt','readme.md','readme.txt','.password','HEAD.md','HEAD.txt','head.md','head.txt'):
                        resp.append(item)
                else:
                    resp.append(item)
            total=GetTotal(path)
        else:
            f=items.find_one({'path':path})
            pid=f['id']
            if f['type']!='folder':
                return f,'files'
            data=items.find({'parent':pid}).collation({"locale": "zh", 'numericOrdering':True})\
                .sort([('order',ASCENDING),(sortby,order)])\
                .limit(per_page).skip((page-1)*per_page)
            for d in data:
                item={}
                item['name']=d['name']
                item['id']=d['id']
                item['lastModtime']=d['lastModtime']
                item['size']=d['size']
                item['type']=d['type']
                if dismiss:
                    if d['name'] not in ('README.md','README.txt','readme.md','readme.txt','.password','HEAD.md','HEAD.txt','head.md','head.txt'):
                        resp.append(item)
                else:
                    resp.append(item)
            total=GetTotal(path)
    except:
        resp=[]
        total=0
    return resp,total

@cache.memoize(timeout=60*5)
def _thunbnail(id):
    app_url=GetAppUrl()
    token=GetToken()
    headers={'Authorization':'bearer {}'.format(token),'Content-type':'application/json'}
    url=app_url+'v1.0/me/drive/items/{}/thumbnails/0?select=large'.format(id)
    r=requests.get(url,headers=headers)
    data=json.loads(r.content)
    if data.get('large').get('url'):
        return data.get('large').get('url')
    else:
        return False

@cache.memoize(timeout=60*5)
def _getdownloadurl(id):
    app_url=GetAppUrl()
    token=GetToken()
    filename=GetName(id)
    ext=filename.split('.')[-1]
    if ext in ['webm','avi','mpg', 'mpeg', 'rm', 'rmvb', 'mov', 'wmv', 'mkv', 'asf']:
        downloadUrl=_thunbnail(id)
        downloadUrl=downloadUrl.replace('thumbnail','videomanifest')+'&part=index&format=dash&useScf=True&pretranscode=0&transcodeahead=0'
        return downloadUrl
    else:
        headers={'Authorization':'bearer {}'.format(token),'Content-type':'application/json'}
        url=app_url+'v1.0/me/drive/items/'+id
        r=requests.get(url,headers=headers)
        data=json.loads(r.content)
        if data.get('@microsoft.graph.downloadUrl'):
            return data.get('@microsoft.graph.downloadUrl')
        else:
            return False

def GetDownloadUrl(id):
    if rd.exists('downloadUrl2:{}'.format(id)):
        downloadUrl,ftime=rd.get('downloadUrl2:{}'.format(id)).split('####')
        if time.time()-int(ftime)>=600:
            # print('{} downloadUrl expired!'.format(id))
            downloadUrl=_getdownloadurl(id)
            ftime=int(time.time())
            k='####'.join([downloadUrl,str(ftime)])
            rd.set('downloadUrl2:{}'.format(id),k)
        else:
            # print('get {}\'s downloadUrl from cache'.format(id))
            downloadUrl=downloadUrl
    else:
        # print('first time get downloadUrl from {}'.format(id))
        downloadUrl=_getdownloadurl(id)
        ftime=int(time.time())
        k='####'.join([downloadUrl,str(ftime)])
        rd.set('downloadUrl2:{}'.format(id),k)
    return downloadUrl


def GetName(id):
    key='name:{}'.format(id)
    if rd.exists(key):
        return rd.get(key)
    else:
        item=items.find_one({'id':id})
        rd.set(key,item['name'])
        return item['name']

def GetPath(id):
    key='path:{}'.format(id)
    if rd.exists(key):
        return rd.get(key)
    else:
        item=items.find_one({'id':id})
        rd.set(key,item['path'])
        return item['path']

@cache.memoize(timeout=60*5)
def GetReadMe(path):
    # README
    ext='Markdown'
    readme,_,i=has_item(path,'README.md')
    if readme==False:
        readme,_,i=has_item(path,'readme.md')
    if readme==False:
        ext='Text'
        readme,_,i=has_item(path,'readme.txt')
    if readme==False:
        ext='Text'
        readme,_,i=has_item(path,'README.txt')
    if readme!=False:
        readme=markdown.markdown(readme)
    return readme,ext


@cache.memoize(timeout=60*5)
def GetHead(path):
    # README
    ext='Markdown'
    head,_,i=has_item(path,'HEAD.md')
    if head==False:
        head,_,i=has_item(path,'head.md')
    if head==False:
        ext='Text'
        head,_,i=has_item(path,'head.txt')
    if head==False:
        ext='Text'
        head,_,i=has_item(path,'HEAD.txt')
    if head!=False:
        head=markdown.markdown(head)
    return head,ext


def CanEdit(filename):
    ext=filename.split('.')[-1]
    if ext in ["html","htm","php","css","go","java","js","json","txt","sh","md",".password"]:
        return True
    else:
        return False

def CodeType(ext):
    code_type={}
    code_type['html'] = 'html';
    code_type['htm'] = 'html';
    code_type['php'] = 'php';
    code_type['css'] = 'css';
    code_type['go'] = 'golang';
    code_type['java'] = 'java';
    code_type['js'] = 'javascript';
    code_type['json'] = 'json';
    code_type['txt'] = 'Text';
    code_type['sh'] = 'sh';
    code_type['md'] = 'Markdown';
    return code_type.get(ext.lower())

def file_ico(item):
  ext = item['name'].split('.')[-1].lower()
  if ext in ['bmp','jpg','jpeg','png','gif']:
    return "image";

  if ext in ['mp4','mkv','webm','avi','mpg', 'mpeg', 'rm', 'rmvb', 'mov', 'wmv', 'mkv', 'asf']:
    return "ondemand_video";

  if ext in ['ogg','mp3','wav']:
    return "audiotrack";

  return "insert_drive_file";

def _remote_content(fileid):
    kc='{}:content'.format(fileid)
    if rd.exists(kc):
        return rd.get(kc)
    else:
        downloadUrl=GetDownloadUrl(fileid)
        if downloadUrl:
            r=requests.get(downloadUrl)
            r.encoding='utf-8'
            content=r.content
            rd.set(kc,content)
            return content
        else:
            return False

# @cache.memoize(timeout=60)
def has_item(path,name):
    if items.count()==0:
        return False
    key='has_item$#$#$#{}$#$#$#{}'.format(path,name)
    if rd.exists(key):
        values=rd.get(key)
        item,fid,cur=values.split('##########')
        if item=='False':
            item=False
        if cur=='False':
            cur=False
        else:
            cur=True
        if fid=='False':
            fid=False
        return item,fid,cur
    else:
        item=False
        fid=False
        dz=False
        cur=False
        if name=='.password':
            dz=True
        try:
            if path=='/':
                if items.find_one({'grandid':0,'name':name}):
                    fid=items.find_one({'grandid':0,'name':name})['id']
                    item=_remote_content(fid).strip()
            else:
                route=path.split('/')
                if name=='.password':
                    for idx,r in enumerate(route):
                        p='/'.join(route[:idx+1])
                        f=items.find_one({'path':p})
                        pid=f['id']
                        data=items.find_one({'name':name,'parent':pid})
                        if data:
                            fid=data['id']
                            item=_remote_content(fid).strip()
                            if idx==len(route)-1:
                                cur=True
                else:
                    f=items.find_one({'path':path})
                    pid=f['id']
                    data=items.find_one({'name':name,'parent':pid})
                    if data:
                        fid=data['id']
                        item=_remote_content(fid).strip()
        except:
            item=False
        rd.set(key,'{}##########{}##########{}'.format(item,fid,cur),300)
        return item,fid,cur


def verify_pass_before(path):
    plist=path_list(path)
    for i in [i for i in range(len(plist))]:
        n='/'.join(plist[:-i])
        yield n

def has_verify(path):
    verify=False
    md5_p=md5(path)
    passwd,fid,cur=has_item(path,'.password')
    if fid and cur:
        vp=request.cookies.get(md5_p)
        if passwd==vp:
            verify=True
    else:
        for last in verify_pass_before(path):
            if last=='':
                last='/'
            passwd,fid,cur=has_item(last,'.password')
            md5_p=md5(last)
            vp=request.cookies.get(md5_p)
            if passwd==vp:
                verify=True
    return verify


def path_list(path):
    if path=='/':
        return [path]
    if path.startswith('/'):
        path=path[1:]
    if path.endswith('/'):
        path=path[:-1]
    plist=path.split('/')
    return plist


if __name__=='__main__':
    func=sys.argv[1]
    if len(sys.argv)>2:
        args=sys.argv[2:]
        eval(func+str(tuple(args)))
    else:
        eval(func+'()')
