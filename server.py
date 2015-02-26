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
            t = tornado.template.Loader(os.path.join(os.getcwd(), 'templates'))
            self.write(t.load("post.html").generate(hostname=self.get_request_header('Host')))
            return

        path = os.path.join('files',arg)
        try:
            with open(path,"rb") as f:
                attrs = xattr.xattr(f)
                self.set_header("Expires", datetime.datetime.utcnow() + datetime.timedelta(1000000)) 
                if 'user.Content-Type' in xattrs:
                    self.set_header("Content-Type", xattrs['user.Content-Type'].decode('utf-8'))
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
        with open(os.path.join('files', filename), "wb") as f:
            f.write(file_body)
            attrs = xattr.xattr(f)
            mimetype = Popen(["file", "-b","--mime-type", f.name], stdout=PIPE).communicate()[0].decode('utf8').strip()
            attrs['user.Content-Type'] = mimetype.encode('utf-8')
        self.write('<html><body><a href="http://' + self.get_request_header('Host') + '/{}"></body></html>{}'.format(filename,filename))

    def put(self, arg):
        filename = base64.urlsafe_b64encode(hashlib.sha256(self.request.body).digest()).decode('utf-8')
        with open(os.path.join('files',filename),"wb") as f:
            f.write(self.request.body)
            attrs = xattr.xattr(f)
            mimetype = Popen(["file", "-b","--mime-type", f.name], stdout=PIPE).communicate()[0].decode('utf8').strip()
            attrs['user.Content-Type'] = mimetype.encode('utf-8')
            attrs['user.filename'] =  arg.encode('utf-8')
            self.write('http://' + self.get_request_header('Host') + '/{}\n'.format(f.name))
            self.write(self.transcode(f.name, mimetype))

    def transcode(self, filename, mimetype):
        outputs = []
        if 'video' in mimetype:
            if not 'mp4' in mimetype:
                outputs.append(filename+'.mp4')
            outputs.append(filename+'.mkv')
        elif 'audio' in mimetype:
            outputs.append(filename+'.mp3')
            outputs.append(filename+'.opus')
        return Popen(["ffmpeg", "-i", filename]+outputs , stdout=PIPE).communicate()[0].decode('utf8').strip()

    def get_request_header(self, header):
        return self.request.headers.get(header)

application = tornado.web.Application([
    (r"/(.*\.html)", tornado.web.StaticFileHandler,     dict(path=os.path.join(os.path.dirname(__file__)))),
    (r"/(.*)", MainHandler),
], debug=True)

if __name__ == "__main__":
    # Server options
    define('port', default=8888, help='TCP port to listen on')

    tornado.options.parse_command_line()
    path = os.path.join(os.path.join(os.path.dirname(__file__)), 'files')
    if not os.path.exists(path):
        os.makedirs(path)
    application.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()
