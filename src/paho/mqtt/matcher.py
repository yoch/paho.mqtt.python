class MQTTMatcher(object):

    class Node(object):
        __slots__ = '_children', '_content'

        def __init__(self):
            self._children = {}
            self._content = None

    def __init__(self):
        self._root = self.Node()

    def __setitem__(self, key, value):
        node = self._root
        for sym in key.split('/'):
            node = node._children.setdefault(sym, self.Node())
        node._content = value

    def __getitem__(self, key):
        try:
            node = self._root
            for sym in key.split('/'):
                node = node[sym]
            if node._content is None:
                raise KeyError(key)
            return node._content
        except KeyError:
            raise KeyError(key)

    def __delitem__(self, key):
        lst = []
        try:
            parent, node = None, self._root
            for k in key.split('/'):
                 parent, node = node, node[k]
                 lst.append((parent, k, node))
            # TODO
            node._content = None
        except KeyError:
            raise KeyError(key)
        else:  # cleanup
            for parent, k, node in reversed(lst):
                if node or node._content is not None:
                     break
                del parent[k]

    def subscribers(self, topic):
        lst = topic.split('/')
        normal = not topic.startswith('$')
        def rec(node, i=0):
            if i == len(lst):
                if node._content is not None:
                    yield node._content
            else:
                part = lst[i]
                if part in node._children:
                    for content in rec(node._children[part], i + 1):
                        yield content
                if '+' in node._children and (normal or i > 0):
                    for content in rec(node._children['+'], i + 1):
                        yield content
            if '#' in node._children and (normal or i > 0):
                content = node._children['#']._content
                if content is not None:
                    yield content
        return rec(self._root)