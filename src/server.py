from yattag import Doc
from yattag import indent
import json
import threading
import webbrowser
from http.server import HTTPServer,SimpleHTTPRequestHandler

config = json.load(open('../config/config.json'))
outputpath = config['outputpath']

#outputpath = outputpath.replace('/final','')

TITLE2FILENAME_PATH = outputpath + "dictionaries/title2filename.json"
TITLE2ID_PATH = outputpath + "dictionaries/title2id.json"
WIKILINK = 'https://en.wikipedia.org/?curid='

FILE = 'frontend.html'
PORT = 8080

title2filename = json.load(open(TITLE2FILENAME_PATH))
title2id = json.load(open(TITLE2ID_PATH))

def process_line(line,doc, tag, text):
    while True:
        start = line.find('[[')
        end = line.find(']]')
        if start > -1 and end > -1 and start < end:
            before = line[:start]
            after = line[end+2:]
            mention = line[start+2:end]

            text(before)

            tokens = mention.split('|')
            entity = tokens[0]

            if len(tokens) > 2:
                alias = tokens[1]
                type = tokens[-1]
            else:
                if len(tokens) == 2:
                    alias = tokens[1]
                else:
                    alias = entity
                type = "ANNOTATION"


            if entity in title2id and len(tokens) > 2:
                id = title2id[entity]
                link = WIKILINK + str(id)
                klass = 'annotation'
                if type == 'RARE_ANNOTATION':
                    klass = 'annotation'
                elif type == 'ANNOTATION':
                    klass = 'annotation'

                with tag('a',('href',link),('target','_blank'),klass=klass):
                    if len(before.strip()) == 0:
                        text(before + alias)
                    else:
                        text(alias)
            elif len(tokens) <= 2:
                link = WIKILINK + str(12)
                klass = 'annotation'
                if type == 'RARE_ANNOTATION':
                    klass = 'annotation'
                elif type == 'ANNOTATION':
                    klass = 'annotation'

                with tag('a', ('href', link), ('target', '_blank'), klass=klass):
                    if len(before.strip()) == 0:
                        text(before + alias)
                    else:
                        text(alias)
            else:
                with tag('font', ('color', 'green')):
                    if len(before.strip()) == 0:
                        text(before + alias)
                    else:
                        text(alias)

            line = after
        else:
            break

    text(line + " ")

def create_html_paragraph(line,doc, tag, text):
    with tag('p'):
        process_line(line,doc,tag,text)

def create_html(title2filename,title):

    doc, tag, text = Doc().tagtext()
    print('title: ' + title)
    if title not in title2filename:
        print('title not found.')
        with tag('p'):
            text('Title not available')
    else:
        with tag('h1'):
            text(title)
        with open(title2filename[title].replace("articles_final","articles_2")) as f:
            content = []
            stop = False
            for line in f:
                line = line.strip()
                if line.startswith('==='):
                    if len(content) > 0:
                        create_html_paragraph(' '.join(content), doc, tag, text)
                        content = []


                    line = line.replace('=','')
                    with tag('h4'):
                        text(line)
                elif line.startswith('=='):
                    if len(content) > 0:
                        create_html_paragraph(' '.join(content), doc, tag, text)
                        content = []
                    line = line.replace('=', '')
                    with tag('h2'):
                        text(line)
                elif not stop:
                    content.append(line)
                    if 'was born at' in line:
                        stop = True
                    #create_html_paragraph(line, doc, tag, text)

    result = indent(doc.getvalue())
    return result

class TestHandler(SimpleHTTPRequestHandler):

    def do_POST(self):
        """Handle a post request by returning the square of the number."""
        length = int(self.headers.get('content-length'))
        data_string = self.rfile.read(length).decode("utf-8")

        print('data string: ' + data_string)

        html = create_html(title2filename,data_string)

        self.send_response(200)
        self.send_header('Content-Type', 'application/xml')
        self.end_headers()

        self.wfile.write(html.encode())


def open_browser():
    """Start a browser after waiting for half a second."""
    def _open_browser():
        webbrowser.open('http://localhost:%s/%s' % (PORT, FILE))
    thread = threading.Timer(0.5, _open_browser)
    thread.start()

def start_server():
    """Start the server."""
    server_address = ("", PORT)
    server = HTTPServer(server_address, TestHandler)
    server.serve_forever()

if __name__ == "__main__":
    open_browser()
    start_server()

