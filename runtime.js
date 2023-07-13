console = {
    log: function(x) {
        call_python('log', x)
    }
}

document = {
    querySelectorAll: function(s) {
        var handles = call_python("querySelectorAll", s);
        return handles.map(function(handle) { return new Node(handle) })
    }
}

var listeners = {}

function Node(handle) { this.handle = handle; }

Node.prototype.getAttribute = function(attr) {
    return call_python("getAttribute", this.handle, attr);
}

Node.prototype.addEventListener = function(type, listener) {
    if (!listeners[this.handle]) listeners[this.handle] = {}
    var dict = listeners[this.handle]
    if (!(type in dict)) dict[type] = []
    dict[type].push(listener)
}

Node.prototype.dispatchEvent = function(event) {
    var type = event.type;
    var handle = this.handle
    var list = (listeners[handle] && listeners[handle][type]) || []
    for (var i = 0; i < list.length; i++) {
        list[i].call(this, event);
    }
    return event.do_default
}

Object.defineProperty(Node.prototype, 'innerHTML', {
    set: function(s) {
        call_python('innerHTML_set', this.handle, s.toString())
    }
})

function Event(type) {
    this.type = type
    this.do_default = true
}

Event.prototype.preventDefault = function() {
    this.do_default = false
}

function XMLHttpRequest() {}

XMLHttpRequest.prototype.open = function(method, url, is_async) {
    if (is_async) throw new Error('async not implemented yet')
    this.method = method
    this.url = url
}

XMLHttpRequest.prototype.send = function(body) {
    this.responseText = call_python('XMLHttpRequest_send', this.method, this.url, body)
}