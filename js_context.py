import dukpy

from css_parser import CSSParser
from helpers import tree_to_list
from html_parser import HTMLParser
from network import request, url_origin, resolve_url

EVENT_DISPATCH_CODE = "new Node(dukpy.handle).dispatchEvent(new Event(dukpy.type))"

class JSContext:
    def __init__(self, tab):
        self.tab = tab
        self.interp = dukpy.JSInterpreter()

        # js to python object mappers
        self.node_to_handle = {}
        self.handle_to_node = {}

        self.interp.export_function("log", print)
        self.interp.export_function("querySelectorAll",
                                    self.querySelectorAll)
        self.interp.export_function("getAttribute",
                                    self.getAttribute)
        self.interp.export_function("innerHTML_set",
                                    self.innerHTML_set)
        self.interp.export_function("XMLHttpRequest_send",
                                    self.XMLHttpRequest_send)

        with open("runtime.js") as f:
            self.interp.evaljs(f.read())

    def run(self, code):
        return self.interp.evaljs(code)

    def dispatch_event(self, type, elt):
        handle = self.node_to_handle.get(elt, -1)
        do_default = self.interp.evaljs(EVENT_DISPATCH_CODE, type=type, handle=handle)
        return not do_default


    def querySelectorAll(self, selector_text):
        selector = CSSParser(selector_text).selector()
        nodes = [node for node in tree_to_list(self.tab.nodes, []) if selector.matches(node)]
        return [self.get_handle(node) for node in nodes]

    def getAttribute(self, handle, attr):
        etl = self.handle_to_node[handle]
        return etl.attributes.get(attr, None)

    def innerHTML_set(self, handle, s):
        doc = HTMLParser("<html><body>" + s + "</body></html>").parse()
        new_nodes = doc.children[0].children
        elt = self.handle_to_node[handle]
        elt.children = new_nodes
        for child in elt.children:
            child.parent = elt
        self.tab.render()

    def XMLHttpRequest_send(self, method, url, body):
        full_url = resolve_url(url, self.tab.url)
        if url_origin(full_url) != url_origin(self.tab.url):
            raise Exception("Cross-origin XHR request not allowed")
        headers, out = request(full_url, body)
        return out

    def get_handle(self, elt):
        if elt not in self.node_to_handle:
            handle = len(self.node_to_handle)
            self.node_to_handle[elt] = handle
            self.handle_to_node[handle] = elt
        else:
            handle = self.node_to_handle[elt]
        return handle