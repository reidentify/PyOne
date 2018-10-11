#-*- coding=utf-8 -*-
from __init__ import *
from function import *
from config import *

################################################################################
###################################试图函数#####################################
################################################################################
@app.before_request
def before_request():
    bad_ua=['Googlebot-Image','FeedDemon ','BOT/0.1 (BOT for JCE)','CrawlDaddy ','Java','Feedly','UniversalFeedParser','ApacheBench','Swiftbot','ZmEu','Indy Library','oBot','jaunty','YandexBot','AhrefsBot','MJ12bot','WinHttp','EasouSpider','HttpClient','Microsoft URL Control','YYSpider','jaunty','Python-urllib','lightDeckReports Bot','PHP','vxiaotou-spider','spider']
    global referrer
    try:
        ip = request.headers['X-Forwarded-For'].split(',')[0]
    except:
        ip = request.remote_addr
    try:
        ua = request.headers.get('User-Agent')
    except:
        ua="null"
    if sum([i.lower() in ua.lower() for i in bad_ua])>0:
        return redirect('http://www.baidu.com')
    print '{}:{}:{}'.format(request.endpoint,ip,ua)
    referrer=request.referrer if request.referrer is not None else 'no-referrer'

@app.route('/<path:path>',methods=['POST','GET'])
@app.route('/',methods=['POST','GET'])
@limiter.limit("200/minute;50/second")
def index(path='/'):
    if path=='favicon.ico':
        return redirect('https://onedrive.live.com/favicon.ico')
    if items.count()==0:
        if not os.path.exists(os.path.join(config_dir,'data/token.json')):
            return redirect(url_for('admin.install',step=0))
        else:
            #subprocess.Popen('python {} UpdateFile'.format(os.path.join(config_dir,'function.py')),shell=True)
            return make_response('<h1>正在更新数据！如果您是网站管理员，请在后台运行命令：python function.py UpdateFile</h1>')
    #参数
    page=request.args.get('page',1,type=int)
    image_mode=request.args.get('image_mode')
    sortby=request.args.get('sortby')
    order=request.args.get('order')
    resp,total = FetchData(path=path,page=page,per_page=50,sortby=sortby,order=order,dismiss=True)
    if total=='files':
        return show(resp['id'])
    #是否有密码
    password,_,cur=has_item(path,'.password')
    md5_p=md5(path)
    has_verify_=has_verify(path)
    if request.method=="POST":
        password1=request.form.get('password')
        if password1==password:
            resp=make_response(redirect(url_for('.index',path=path)))
            resp.delete_cookie(md5_p)
            resp.set_cookie(md5_p,password)
            return resp
    if password!=False:
        if (not request.cookies.get(md5_p) or request.cookies.get(md5_p)!=password) and has_verify_==False:
            return render_template('password.html',path=path)
    readme,ext_r=GetReadMe(path)
    head,ext_d=GetHead(path)
    #设置cookies
    if image_mode:
        image_mode=request.args.get('image_mode',type=int)
    else:
        image_mode=request.cookies.get('image_mode') if request.cookies.get('image_mode') is not None else 0
        image_mode=int(image_mode)
    if sortby:
        sortby=request.args.get('sortby')
    else:
        sortby=request.cookies.get('sortby') if request.cookies.get('sortby') is not None else 'lastModtime'
        sortby=sortby
    if order:
        order=request.args.get('order')
    else:
        order=request.cookies.get('order') if request.cookies.get('order') is not None else 'desc'
        order=order
    #参数
    resp,total = FetchData(path=path,page=page,per_page=50,sortby=sortby,order=order,dismiss=True)
    pagination=Pagination(query=None,page=page, per_page=50, total=total, items=None)
    resp=make_response(render_template('index.html'
                    ,pagination=pagination
                    ,items=resp
                    ,path=path
                    ,image_mode=image_mode
                    ,readme=readme
                    ,ext_r=ext_r
                    ,head=head
                    ,ext_d=ext_d
                    ,sortby=sortby
                    ,order=order
                    ,endpoint='.index'))
    resp.set_cookie('image_mode',str(image_mode))
    resp.set_cookie('sortby',str(sortby))
    resp.set_cookie('order',str(order))
    return resp

@app.route('/file/<fileid>')
def show(fileid):
    name=GetName(fileid)
    path=GetPath(fileid)
    ext=name.split('.')[-1].lower()
    if request.method=='POST':
        url=request.url.replace(':80','').replace(':443','')
        if ext in ['csv','doc','docx','odp','ods','odt','pot','potm','potx','pps','ppsx','ppsxm','ppt','pptm','pptx','rtf','xls','xlsx']:
            downloadUrl=GetDownloadUrl(fileid)
            url = 'https://view.officeapps.live.com/op/view.aspx?src='+urllib.quote(downloadUrl)
            return redirect(url)
        elif ext in ['bmp','jpg','jpeg','png','gif']:
            return render_template('show/image.html',url=url,path=path)
        elif ext in ['mp4','webm']:
            return render_template('show/video.html',url=url,path=path)
        elif ext in ['mp4','webm','avi','mpg', 'mpeg', 'rm', 'rmvb', 'mov', 'wmv', 'mkv', 'asf']:
            return render_template('show/video2.html',url=url,path=path)
        elif ext in ['avi','mpg', 'mpeg', 'rm', 'rmvb', 'mov', 'wmv', 'mkv', 'asf']:
            return render_template('show/video2.html',url=url,path=path)
        elif ext in ['ogg','mp3','wav']:
            return render_template('show/audio.html',url=url,path=path)
        elif CodeType(ext) is not None:
            content=_remote_content(fileid)
            return render_template('show/code.html',content=content,url=url,language=CodeType(ext),path=path)
        else:
            downloadUrl=GetDownloadUrl(fileid)
            return redirect(downloadUrl)
    else:
        if 'no-referrer' in allow_site:
            downloadUrl=GetDownloadUrl(fileid)
            resp=redirect(downloadUrl)
            return resp
        elif sum([i in referrer for i in allow_site])>0:
            downloadUrl=GetDownloadUrl(fileid)
            return redirect(downloadUrl)
        else:
            return abort(404)

@app.route('/robot.txt')
def robot():
    resp="""
User-agent:  *
Disallow:  /
    """
    resp=make_response(resp)
    resp.headers['Content-Type'] = 'text/javascript; charset=utf-8'
    return resp

