from html import unescape

HTML_ENTITIES = {
    '&quot;': '"',
    '&apos;': "'",
    '&amp;': '&',
    '&gt;': '>',
    '&lt;': '<',
    '&frasl;': '/'
}

class Text:
    def __init__(self, text, parent):
        self.text = text
        self.parent = parent
        self.children = []

    def __repr__(self):
        return repr(self.text)

class Element:
    def __init__(self, tag, attributes, parent):
        self.tag = tag
        self.parent = parent
        self.attributes = attributes
        self.children = []

    def __repr__(self):
        return "<" + self.tag + ">"

class HTMLParser:
    def __init__(self, body):
        self.body = body
        self.unfinished = []

    SELF_CLOSING_TAGS = [
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    ]
    HEAD_TAGS = [
        "base", "basefont", "bgsound", "noscript",
        "link", "meta", "title", "style", "script",
    ]
    def parse(self):
        text = ''
        in_angle = False
        for c in self.body:
            if c == "<":
                in_angle = True
                if text: self.add_text(text)
                text = ''
            elif c == ">":
                in_angle = False
                self.add_tag(text)
                text = ''
            else:
                text += c
        if not in_angle and text:
            self.add_text(text)
        return self.finish()

    def get_attributes(self, text):
        parts = text.split()
        tag = parts[0].lower()
        attributes = {}
        for attrpair in parts[1:]:
            if '=' in attrpair:
                key, value = attrpair.split("=", 1)
                if len(value) > 2 and value[0] in ["'", "\""]:
                    value = value[1:-1]
                attributes[key.lower()] = value
            else:
                attributes[attrpair.lower()] = ''
        return tag, attributes

    def html_entities(self, text):
        # I'm cheating here cuz I couldn't get the algorithm right
        return unescape(text)
        # amp_index = None
        # out = ''
        # for i, c in enumerate(text):
        #     if c == '&':
        #         print('found amp')
        #         amp_index = i
        #     if c == ';' and amp_index:
        #         print('found semi')
        #         print(amp_index)
        #         entity = text[amp_index + 1:i]
        #         print(entity)
        #         char = HTML_ENTITIES[entity]
        #         out = out[:amp_index] + char
        #         amp_index = None
        #     else:
        #         out += c
        # return out

    def add_text(self, text):
        if text.isspace(): return
        self.implicit_tags(None)
        text = self.html_entities(text)
        parent = self.unfinished[-1]
        node = Text(text, parent)
        parent.children.append(node)

    def add_tag(self, tag):
        if tag.startswith("!"): return
        self.implicit_tags(tag)
        tag, attributes = self.get_attributes(tag)
        if tag.startswith('/'):
            if len(self.unfinished) == 1: return
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        elif tag in self.SELF_CLOSING_TAGS:
            parent = self.unfinished[-1]
            node = Element(tag, attributes, parent)
            parent.children.append(node)
        else:
            parent = self.unfinished[-1] if self.unfinished else None
            node = Element(tag, attributes, parent)
            self.unfinished.append(node)

    def implicit_tags(self, tag):
        while True:
            open_tags = [node.tag for node in self.unfinished]
            if open_tags == [] and tag != "html":
                self.add_tag("html")
            elif open_tags == ['html'] and tag not in ['head', 'body', '/html']:
                if tag in self.HEAD_TAGS:
                    self.add_tag("head")
                else:
                    self.add_tag("body")
            elif open_tags == ['html', 'head'] and tag not in ['/head'] + self.HEAD_TAGS:
                self.add_tag('/head')
            else:
                break

    def finish(self):
        if len(self.unfinished) == 0:
            self.add_tag('html')
        while len(self.unfinished) > 1:
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        return self.unfinished.pop()
