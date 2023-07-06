import tkinter
import tkinter.font
from html_parser import HTMLParser, Text, Element
from css_parser import CSSParser, style, cascade_priority
from network import request

WIDTH, HEIGHT = 800, 600
SCROLL_STEP = 100
HSTEP, VSTEP = 13, 18

class Browser:
    def __init__(self):
        self.url = None
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(
            self.window,
            bg="white",
            width=WIDTH,
            height=HEIGHT

        )
        self.canvas.pack()
        self.scroll = 0
        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<Up>", self.scrollup)
        self.window.bind("<Button-1>", self.click)

        with open('browser.css') as f:
            self.default_style_sheet = CSSParser(f.read()).parse()

    def scrolldown(self, e):
        max_y = self.document.height - HEIGHT
        self.scroll = min(self.scroll + SCROLL_STEP, max_y)
        self.draw()

    def scrollup(self, e):
        self.scroll -= SCROLL_STEP
        if self.scroll < 0:
            self.scroll = 0
        self.draw()

    def click(self, e):
        x, y = e.x, e.y
        y += self.scroll

        objs = [obj for obj in tree_to_list(self.document, [])
                if obj.x <= x < obj.x + obj.width
                and obj.y <= y < obj.y + obj.height]

        if not objs: return
        elt = objs[-1].node

        while elt:
            if isinstance(elt, Text):
                pass
            elif elt.tag == "a" and "href" in elt.attributes:
                url = resolve_url(elt.attributes["href"], self.url)
                return self.load(url)
            elt = elt.parent

    def draw(self):
        self.canvas.delete("all")
        for cmd in self.display_list:
            if cmd.top > self.scroll + HEIGHT: continue
            if cmd.bottom + VSTEP < self.scroll: continue
            cmd.execute(self.scroll, self.canvas)

    def load(self, url):
        self.url = url
        headers, body = request(url)
        self.nodes = HTMLParser(body).parse()
        rules = self.default_style_sheet.copy()

        # links = [node.attributes["href"]
        #          for node in tree_to_list(self.nodes, [])
        #          if isinstance(node, Element)
        #          and node.tag == "link"
        #          and "href" in node.attributes
        #          and node.attributes.get("rel") == "stylesheet"]
        # for link in links:
        #     try:
        #         header, body = request(resolve_url(link, url))
        #     except:
        #         continue
        #     rules.extend(CSSParser(body).parse())

        style(self.nodes, sorted(rules, key=cascade_priority))
        self.document = DocumentLayout(self.nodes)
        self.document.layout()
        self.display_list = []
        self.document.paint(self.display_list)
        self.draw()


def tree_to_list(tree, list):
    list.append(tree)
    for child in tree.children:
        tree_to_list(child, list)
    return list

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

class DrawText:
    def __init__(self, x1, y1, text, font, color):
        self.top = y1
        self.left = x1
        self.text = text
        self.font = font
        self.bottom = y1 + font.metrics("linespace")
        self.color = color

    def execute(self, scroll, canvas):
        canvas.create_text(
            self.left,
            self.top - scroll,
            text=self.text,
            font=self.font,
            fill=self.color,
            anchor="nw"
        )


class DrawRect:
    def __init__(self, x1, y1, x2, y2, color):
        self.top = y1
        self.bottom = y2
        self.left = x1
        self.right = x2
        self.color = color

    def execute(self, scroll, canvas):
        canvas.create_rectangle(
            self.left,
            self.top - scroll,
            self.right,
            self.bottom - scroll,
            width=0,
            fill=self.color
        )


FONTS = {}


def get_font(size, weight, slant):
    key = (size, weight, slant)
    if key not in FONTS:
        font = tkinter.font.Font(size=size, weight=weight, slant=slant)
        FONTS[key] = font
    return FONTS[key]


class DocumentLayout:
    def __init__(self, node):
        self.node = node
        self.parent = None
        self.children = []

    def paint(self, display_list):
        self.children[0].paint(display_list)

    def layout(self):
        self.width = WIDTH - 2 * HSTEP
        self.x = HSTEP
        self.y = VSTEP
        child = BlockLayout(self.node, self, None)
        self.children.append(child)
        child.layout()
        self.height = child.height + 2 * VSTEP


BLOCK_ELEMENTS = [
    "html", "body", "article", "section", "nav", "aside",
    "h1", "h2", "h3", "h4", "h5", "h6", "hgroup", "header",
    "footer", "address", "p", "hr", "pre", "blockquote",
    "ol", "ul", "menu", "li", "dl", "dt", "dd", "figure",
    "figcaption", "main", "div", "table", "form", "fieldset",
    "legend", "details", "summary"
]


def layout_mode(node):
    if isinstance(node, Text):
        return "inline"
    elif node.children:
        if any([isinstance(child, Element) and child.tag in BLOCK_ELEMENTS for child in node.children]):
            return "block"
        else:
            return "inline"
    else:
        return "block"


class BlockLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []
        self.display_list = []

    def paint(self, display_list):
        bgcolor = self.node.style.get('background-color', 'transparent')
        if bgcolor != 'transparent':
            x2 = self.x + self.width
            y2 = self.y + self.height
            rect = DrawRect(self.x, self.y, x2, y2, bgcolor)
            display_list.append(rect)

        for x, y, text, font, color in self.display_list:
            display_list.append(DrawText(x, y, text, font, color))
        for child in self.children:
            child.paint(display_list)

    def layout(self):
        self.x = self.parent.x
        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y
        self.width = self.parent.width

        mode = layout_mode(self.node)
        if mode == "block":
            previous = None
            for child in self.node.children:
                next = BlockLayout(child, self, previous)
                self.children.append(next)
                previous = next
        else:
            self.new_line()
            self.recurse(self.node)

        for child in self.children:
            child.layout()

        # height must be computed _after_ children layout
        self.height = sum([child.height for child in self.children])

    def recurse(self, node):
        if isinstance(node, Text):
            self.text(node)
        else:
            # todo: reimplement br and p tags
            for child in node.children:
                self.recurse(child)

    def get_font(self, node):
        weight = node.style['font-weight']
        style = node.style['font-style']
        if style == 'normal': style = 'roman'
        size = int(float(node.style['font-size'][:-2]) * .75)
        return get_font(size, weight, style)

    def text(self, node):
        font = self.get_font(node)
        for word in node.text.split():
            width = font.measure(word)
            if self.cursor_x + width > self.width:
                self.new_line()

            line = self.children[-1]
            text = TextLayout(node, word, line, self.previous_word)
            line.children.append(text)
            self.previous_word = text

            self.cursor_x += width + font.measure(" ")

    def new_line(self):
        self.previous_word = None
        self.cursor_x = 0
        last_line = self.children[-1] if self.children else None
        new_line = LineLayout(self.node, self, last_line)
        self.children.append(new_line)


class LineLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []

    def layout(self):
        self.width = self.parent.width
        self.x = self.parent.x

        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y

        for word in self.children:
            word.layout()

        max_ascent = max([word.font.metrics('ascent') for word in self.children])
        baseline = self.y + 1.25 * max_ascent
        for word in self.children:
            word.y = baseline - word.font.metrics('ascent')
        max_descent = max([word.font.metrics("descent") for word in self.children])
        self.height = 1.25 * (max_ascent + max_descent)

    def paint(self, display_list):
        for child in self.children:
            child.paint(display_list)

class TextLayout:
    def __init__(self, node, word, parent, previous):
        self.node = node
        self.word = word
        self.children = []
        self.parent = parent
        self.previous = previous

    def layout(self):
        weight = self.node.style['font-weight']
        style = self.node.style['font-style']
        if style == 'normal': style = 'roman'
        size = int(float(self.node.style["font-size"][:-2]) * .75)
        self.font = get_font(size, weight, style)

        self.width = self.font.measure(self.word)
        if self.previous:
            space = self.previous.font.measure(' ')
            self.x = self.previous.x + self.previous.width + space
        else:
            self.x = self.parent.x

        self.height = self.font.metrics('linespace')

    def paint(self, display_list):
        color = self.node.style["color"]
        display_list.append(
            DrawText(self.x, self.y, self.word, self.font, color))


def print_tree(node, indent=0):
    print(" " * indent, node)
    for child in node.children:
        print_tree(child, indent + 2)


if __name__ == "__main__":
    import sys

    Browser().load(sys.argv[1])
    tkinter.mainloop()

    # headers, body = request(sys.argv[1])
    # nodes = HTMLParser(body).parse()
    # print_tree(nodes)

# load('http://example.org/index.html')
