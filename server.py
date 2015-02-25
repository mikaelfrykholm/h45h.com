import base64
import datetime
import hashlib
import os
from subprocess import Popen, PIPE
import tornado.ioloop
import tornado.web
from tornado.options import define, options
import xattr


class MainHandler(tornado.web.RequestHandler):
    def get(self, arg, head=False):
        if not arg:
            self.redirect("/post.html")
        path = os.path.join('files',arg)
        try:
            with open(path,"rb") as f: 
                self.set_header("Expires", datetime.datetime.utcnow() + datetime.timedelta(1000000)) 
                mimetype = Popen(["file","-b","--mime-type", path], stdout=PIPE).communicate()[0].decode('utf8').strip()
                self.set_header("Content-Type", mimetype)
                attrs = xattr.xattr(f)
                try:
                    orig_filename = attrs.get('user.filename').decode('utf-8')
                    self.set_header('Content-Disposition',' inline; filename="{}"'.format(orig_filename))
                except IOError:
                    pass
                self.set_header('content-length',os.stat(f.fileno()).st_size)
                if head:
                   self.finish()
                   return
                self.write(f.read())
                self.finish()
        except IOError:
            raise tornado.web.HTTPError(404)
    def head(self, arg):
        self.get(arg, head=True)

    def post(self, arg):
        file_body = self.request.arguments.get('data')[0]
        if not file_body:
            self.finish()
            return
        filename = base64.urlsafe_b64encode(hashlib.sha256(file_body).digest()).decode('utf-8') 
        with open(os.path.join('files',filename),"wb") as f:
            f.write(file_body)
        self.write('<html><body><a href="http://h45h.com/{}"></body></html>{}'.format(filename,filename))
    def put(self, arg):
        filename = base64.urlsafe_b64encode(hashlib.sha256(self.request.body).digest()).decode('utf-8')
        with open(os.path.join('files',filename),"wb") as f:
            f.write(self.request.body)
            attrs = xattr.xattr(f)
            attrs.set(b'user.filename',arg.encode('utf-8'))
        self.write('http://h45h.com/{}\n'.format(filename))       


application = tornado.web.Application([
    (r"/(.*\.html)", tornado.web.StaticFileHandler,     dict(path=os.path.join(os.path.dirname(__file__)))),
    (r"/(.*)", MainHandler),
], debug=True)

if __name__ == "__main__":
    tornado.options.parse_command_line()
    path = os.path.join(os.path.join(os.path.dirname(__file__)), 'files')
    if not os.path.exists(path):
        os.makedirs(path)
    application.listen(8888)
    tornado.ioloop.IOLoop.instance().start()
