import datetime
import hashlib
import os
from subprocess import Popen, PIPE
import tornado.ioloop
import tornado.web
from tornado.options import define, options

# There are two 'xattr' (xattr and pyxattr) modules in the wild, we try to be compatible with both
import xattr

class MainHandler(tornado.web.RequestHandler):
    def get(self, arg, head=False):
        if not arg:
            t = tornado.template.Loader(os.path.join(os.getcwd(), 'templates'))
            self.write(t.load("post.html").generate(hostname=self.get_request_header('Host')))
            return

        path = os.path.join('files', os.path.basename(arg))
        try:
            with open(path,"rb") as f:
                attrs = self.get_xattrs(f)

                self.set_header("Expires", datetime.datetime.utcnow() + datetime.timedelta(1000000)) 
                if 'user.mime_type' in attrs:
                    self.set_header("Content-Type", attrs['user.mime_type'].decode('utf-8'))
                try:
                    orig_filename = attrs.get('user.filename').decode('utf-8')
                    self.set_header('Content-Disposition',' inline; filename="{}"'.format(orig_filename))
                except (AttributeError, IOError):
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
        filename = hashlib.sha256(file_body).hexdigest()
        with open(os.path.join('files', filename), "wb") as f:
            f.write(file_body)
            mimetype = Popen(["file", "-b","--mime-type", f.name], stdout=PIPE).communicate()[0].decode('utf8').strip()
            self.set_xattr(f, 'user.mime_type', mimetype.encode('utf-8'))
        self.write('<html><body><a href="http://' + self.get_request_header('Host') + '/{}"></body></html>{}'.format(filename,filename))

    def put(self, arg):
        filename = hashlib.sha256(self.request.body).hexdigest()
        with open(os.path.join('files',filename),"wb") as f:
            f.write(self.request.body)
            mimetype = Popen(["file", "-b","--mime-type", f.name], stdout=PIPE).communicate()[0].decode('utf8').strip()
            self.set_xattr(f, 'user.mime_type', mimetype.encode('utf-8'))
            self.set_xattr(f, 'user.filename', arg.encode('utf-8'))
            self.write('http://' + self.get_request_header('Host') + '/{}\n'.format(f.name))
            self.write(self.transcode(f.name, mimetype))

    def transcode(self, filename, mimetype):
        outputs = []
        if mimetype[:5] == 'video':
            if not mimetype[6:] == 'mp4':
                outputs.extend(['-strict', 'experimental'])
                outputs.append(filename+'.mp4')
            outputs.append(filename+'.mkv')
        elif mimetype[:5] == 'audio':
            outputs.append(filename+'.mp3')
            outputs.append(filename+'.opus')
        return Popen([options.transcoder, "-i", filename]+outputs , stdout=PIPE).communicate()[0].decode('utf8').strip()

    def get_request_header(self, header):
        return self.request.headers.get(header)

    ### item is a file object, filename or file-like object
    def get_xattrs(self, item):
        try:
            return xattr.xattr(item)
        except AttributeError:
            # we are using python3-pyxattr
            attrs = {}
            for aname in {'user.mime_type', 'user.filename'}:
                try:
                    attrs[i] = xattr.get(item, name)
                except:
                    pass
        return attrs

    ### item is a file object, filename or file-like object
    def set_xattr(self, item, name, value):
        try:
            xattr.xattr(item).set(name, value)
        except AttributeError:
            # we are using python3-pyxattr
            xattr.set(item, name, value)

application = tornado.web.Application([
    (r"/(.*\.html)", tornado.web.StaticFileHandler,     dict(path=os.path.join(os.path.dirname(__file__)))),
    (r"/(.*)", MainHandler),
], debug=True)

if __name__ == "__main__":
    # Server options
    define('port', default=8888, help='TCP port to listen on')
    define('transcoder', default='ffmpeg', help='The ffmpeg/avconv CLI compatible transcoder to use for multimedia.')

    tornado.options.parse_command_line()
    path = os.path.join(os.path.join(os.path.dirname(__file__)), 'files')
    if not os.path.exists(path):
        os.makedirs(path)
    application.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()
