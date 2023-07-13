import socket
import ssl

COOKIE_JAR = {}


def url_origin(url):
    (scheme, host, path) = parse_url(url)
    return scheme + "://" + host


def parse_url(url):
    scheme, url = url.split("://", 1)
    if "/" not in url:
        url = url + "/"
    host, path = url.split("/", 1)
    return scheme, host, "/" + path


def request(url, payload=None):
    (scheme, host, path) = parse_url(url)
    assert scheme in ["http", "https"], \
        "Unknown scheme {}".format(scheme)

    s = socket.socket(
        family=socket.AF_INET,
        type=socket.SOCK_STREAM,
        proto=socket.IPPROTO_TCP,
    )

    port = 80 if scheme == "http" else 443

    if ":" in host:
        host, port = host.split(":", 1)
        port = int(port)

    s.connect((host, port))

    if scheme == "https":
        ctx = ssl.create_default_context()
        s = ctx.wrap_socket(s, server_hostname=host)

    method = "POST" if payload else "GET"

    body = "{} {} HTTP/1.0\r\n".format(method, path) + "HOST: {}\r\n".format(host)
    if payload:
        length = len(payload.encode('utf8'))
        body += 'Content-Length: {}\r\n'.format(length)

    if host in COOKIE_JAR:
        cookie = COOKIE_JAR[host]
        body += 'Cookie: {}\r\n'.format(cookie)

    body += "\r\n" + (payload if payload else "")

    s.send(body.encode('utf8'))

    response = s.makefile("r", encoding="utf8", newline="\r\n")

    statusline = response.readline()
    version, status, explanation = statusline.split(" ", 2)
    assert status == "200", "{}: {}".format(status, explanation)

    headers = {}
    while True:
        line = response.readline()
        if line == "\r\n": break
        header, value = line.split(":", 1)
        headers[header.lower()] = value.strip()

    assert "transfer-encoding" not in headers
    assert "content-encoding" not in headers

    if 'set-cookie' in headers:
        kv = headers['set-cookie']
        COOKIE_JAR[host] = kv


    body = response.read()
    s.close()

    return headers, body


def resolve_url(url, current):
    if '://' in url:
        return url
    elif url.startswith('/'):
        scheme, hostpath = current.split('://', 1)
        host, oldpath = hostpath.split('/', 1)
        return scheme + "://" + host + url
    else:
        dir, _ = current.rsplit('/', 1)
        while url.startswith('../'):
            url = url[3:]
            if dir.count('/') == 2: continue
            dir, _ = dir.rsplit('/', 1)
        return dir + '/' + url
