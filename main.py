import tkinter
import tkinter.font
import urllib.parse
import dukpy

from helpers import tree_to_list
from html_parser import HTMLParser, Text, Element
from css_parser import CSSParser, style, cascade_priority
from js_context import JSContext
from network import request

WIDTH, HEIGHT = 800, 600
SCROLL_STEP = 100
HSTEP, VSTEP = 13, 18
CHROME_PX = 100


class Tab:
    def __init__(self):
        self.url = None
        self.focus = None
        self.history = []
        self.scroll = 0
        with open('browser.css') as f:
            self.default_style_sheet = CSSParser(f.read()).parse()

    def scrolldown(self):
        max_y = self.document.height - (HEIGHT - CHROME_PX)
        self.scroll = min(self.scroll + SCROLL_STEP, max_y)

    def scrollup(self):
        self.scroll -= SCROLL_STEP
        if self.scroll < 0:
            self.scroll = 0

    def click(self, x, y):
        self.focus = None

        y += self.scroll

        objs = [obj for obj in tree_to_list(self.document, [])
                if obj.x <= x < obj.x + obj.width
                and obj.y <= y < obj.y + obj.height]

        if not objs: return
        elt = objs[-1].node

        while elt:
            if isinstance(elt, Text):
                pass
            elif elt.tag == "input":
                if self.js.dispatch_event('click', elt): return
                self.focus = elt
                elt.attributes["value"] = ""
                return self.render()
            elif elt.tag == 'button':
                if self.js.dispatch_event('click', elt): return
                while elt:
                    if elt.tag == 'form' and 'action' in elt.attributes:
                        return self.submit_form(elt)
                    else:
                        elt = elt.parent
                return
            elif elt.tag == "a" and "href" in elt.attributes:
                if self.js.dispatch_event('click', elt): return
                url = resolve_url(elt.attributes["href"], self.url)
                return self.load(url)
            elt = elt.parent

    def keypress(self, char):
        if self.focus:
            self.focus.attributes['value'] += char
            if self.js.dispatch_event("keydown", self.focus): return
            self.render()

    def draw(self, canvas):
        for cmd in self.display_list:
            if cmd.top > self.scroll + HEIGHT - CHROME_PX: continue
            if cmd.bottom + VSTEP < self.scroll: continue
            cmd.execute(self.scroll - CHROME_PX, canvas)
        if self.focus:
            obj = [obj for obj in tree_to_list(self.document, [])
                   if obj.node == self.focus and isinstance(obj, InputLayout)][0]
            text = self.focus.attributes.get('value', '')
            x = obj.x + obj.font.measure(text)
            y = obj.y - self.scroll + CHROME_PX
            canvas.create_line(x, y, x, y + obj.height)

    def go_back(self):
        if len(self.history) > 1:
            self.history.pop()
            back = self.history.pop()
            self.load(back)

    def load(self, url, body=None):
        self.url = url
        self.history.append(url)
        headers, body = request(url, body)
        self.nodes = HTMLParser(body).parse()
        self.rules = self.default_style_sheet.copy()
        self.js = JSContext(self)

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

        scripts = [node.attributes["src"] for node
                   in tree_to_list(self.nodes, [])
                   if isinstance(node, Element)
                   and node.tag == "script"
                   and "src" in node.attributes]

        for script in scripts:
            header, body = request(resolve_url(script, url))
            try:
                self.js.run(body)
            except dukpy.JSRuntimeError as e:
                print("Script", script, "crashed", e)

        self.render()

    def render(self):
        style(self.nodes, sorted(self.rules, key=cascade_priority))
        self.document = DocumentLayout(self.nodes)
        self.document.layout()
        self.display_list = []
        self.document.paint(self.display_list)

    def submit_form(self, elt):
        if self.js.dispatch_event("submit", elt): return

        inputs = [node for node in tree_to_list(elt, []) if
                  isinstance(node, Element) and node.tag == 'input' and 'name' in node.attributes]
        body = ''
        for input in inputs:
            name = input.attributes['name']
            value = input.attributes.get('value', '')
            name = urllib.parse.quote(name)
            value = urllib.parse.quote(value)
            body += '&' + name + '=' + value
        body = body[1:]
        url = resolve_url(elt.attributes["action"], self.url)
        self.load(url, body)


class Browser:
    def __init__(self):
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(
            self.window,
            bg="white",
            width=WIDTH,
            height=HEIGHT

        )
        self.canvas.pack()

        self.window.bind("<Down>", self.handle_down)
        self.window.bind("<Up>", self.handle_up)
        self.window.bind("<Button-1>", self.handle_click)
        self.window.bind("<Key>", self.handle_key)
        self.window.bind("<Return>", self.handle_enter)

        self.tabs = []
        self.active_tab = None

        self.focus = None
        self.address_bar = ''

    def handle_down(self, e):
        self.tabs[self.active_tab].scrolldown()
        self.draw()

    def handle_click(self, e):
        if e.y < CHROME_PX:
            self.focus = None
            if 40 <= e.x < 40 + 80 * len(self.tabs) and 0 <= e.y < 40:
                self.active_tab = int((e.x - 40) / 80)
            elif 10 <= e.x < 30 and 10 <= e.y < 30:
                # clicked on new tab button
                self.load("https://browser.engineering/")
            elif 10 <= e.x < 35 and 50 <= e.y < 90:
                # clicked back button
                self.tabs[self.active_tab].go_back()
            elif 50 <= e.x < WIDTH - 10 and 50 <= e.y < 90:
                # clicked on address bar
                self.focus = "address_bar"
                self.address_bar = ""
        else:
            self.focus = 'content'
            self.tabs[self.active_tab].click(e.x, e.y - CHROME_PX)
        self.draw()

    def handle_key(self, e):
        if len(e.char) == 0: return
        if not (0x20 <= ord(e.char) < 0x7f): return
        if self.focus == 'address_bar':
            self.address_bar += e.char
            self.draw()
        elif self.focus == 'content':
            self.tabs[self.active_tab].keypress(e.char)
            self.draw()

    def handle_enter(self, e):
        if self.focus == 'address_bar':
            self.tabs[self.active_tab].load(self.address_bar)
            self.focus = None
            self.draw()

    def handle_up(self, e):
        self.tabs[self.active_tab].scrollup()
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        self.tabs[self.active_tab].draw(self.canvas)
        self.canvas.create_rectangle(0, 0, WIDTH, CHROME_PX,
                                     fill="white", outline="black")
        tabfont = get_font(20, 'normal', 'roman')
        for i, tab in enumerate(self.tabs):
            name = 'Tab {}'.format(i)
            x1 = 40 + 80 * i
            x2 = 120 + 80 * i
            self.canvas.create_line(x1, 0, x1, 40, fill='black')
            self.canvas.create_line(x2, 0, x2, 40, fill='black')
            self.canvas.create_text(x1 + 10, 10, anchor="nw", text=name, font=tabfont, fill="black")
            if i == self.active_tab:
                self.canvas.create_line(0, 40, x1, 40, fill="black")
                self.canvas.create_line(x2, 40, WIDTH, 40, fill="black")

            # new tab button
            buttonfont = get_font(30, "normal", "roman")
            self.canvas.create_rectangle(10, 10, 30, 30, outline="black", width=1)
            self.canvas.create_text(11, 0, anchor="nw", text="+", font=buttonfont, fill="black")

            # url bar
            self.canvas.create_rectangle(40, 50, WIDTH - 10, 90,
                                         outline="black", width=1)
            if self.focus == 'address_bar':
                self.canvas.create_text(55, 55, anchor='nw', text=self.address_bar,
                                        font=buttonfont, fill="black")
                w = buttonfont.measure(self.address_bar)
                self.canvas.create_line(55 + w, 55, 55 + w, 85, fill="black")
            else:
                url = self.tabs[self.active_tab].url
                self.canvas.create_text(55, 55, anchor='nw', text=url,
                                        font=buttonfont, fill="black")

            # back button
            self.canvas.create_rectangle(10, 50, 35, 90,
                                         outline="black", width=1)
            self.canvas.create_polygon(
                15, 70, 30, 55, 30, 85, fill='black')

    def load(self, url):
        new_tab = Tab()
        new_tab.load(url)
        self.active_tab = len(self.tabs)
        self.tabs.append(new_tab)
        self.draw()


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
    elif node.tag == "input":
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
        is_atomic = not isinstance(self.node, Text) and \
                    (self.node.tag == "input" or self.node.tag == "button")

        if not is_atomic:
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
            if node.tag == 'br':
                self.new_line()
            elif node.tag == 'input' or node.tag == 'button':
                self.input(node)
            else:
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

    def input(self, node):
        width = INPUT_WIDTH_PX
        if self.cursor_x + width > self.width:
            self.new_line()
        line = self.children[-1]
        input = InputLayout(node, line, self.previous_word)
        line.children.append(input)
        self.previous_word = input
        font = self.get_font(node)
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


INPUT_WIDTH_PX = 200


class InputLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.children = []
        self.parent = parent
        self.previous = previous

    def layout(self):
        weight = self.node.style['font-weight']
        style = self.node.style['font-style']
        if style == 'normal': style = 'roman'
        size = int(float(self.node.style["font-size"][:-2]) * .75)
        self.font = get_font(size, weight, style)

        self.width = INPUT_WIDTH_PX
        if self.previous:
            space = self.previous.font.measure(' ')
            self.x = self.previous.x + self.previous.width + space
        else:
            self.x = self.parent.x

        self.height = self.font.metrics('linespace')

    def paint(self, display_list):
        bgcolor = self.node.style.get("background-color",
                                      "transparent")
        if bgcolor != "transparent":
            x2, y2 = self.x + self.width, self.y + self.height
            rect = DrawRect(self.x, self.y, x2, y2, bgcolor)
            display_list.append(rect)

        if self.node.tag == 'input':
            text = self.node.attributes.get('value')
        elif self.node.tag == 'button':
            if len(self.node.children) == 1 and isinstance(self.node.children[0], Text):
                text = self.node.children[0].text
            else:
                print('Ignoring HTML content inside button')
                text = ''

        color = self.node.style["color"]
        display_list.append(
            DrawText(self.x, self.y, text, self.font, color))


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
