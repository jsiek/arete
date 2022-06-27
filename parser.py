from abstract_syntax import *
from collections import OrderedDict
from dataclasses import dataclass
from lark import Lark, Token, logger
from typing import List, Set, Dict, Tuple
import sys

from lark import logger
import logging
#logger.setLevel(logging.DEBUG)

##################################################
# Concrete Syntax Parser
##################################################

lark_parser = Lark(open("./Arete.lark").read(), start='arete', parser='lalr',
                   debug=True)

##################################################
# Parsing Concrete to Abstract Syntax
##################################################

def parse_tree_to_ast(e):
    if e.data == 'var':
        return Var(str(e.children[0].value))
    elif e.data == 'int':
        return Int(int(e.children[0]))
    elif e.data == 'add':
        e1, e2 = e.children
        return Prim('add', [parse_tree_to_ast(e1), parse_tree_to_ast(e2)])
    elif e.data == 'sub':
        e1, e2 = e.children
        return Prim('sub', [parse_tree_to_ast(e1), parse_tree_to_ast(e2)])
    elif e.data == 'neg':
        return Prim('neg', [parse_tree_to_ast(e.children[0])])
    elif e.data == 'init':
        return Init(str(e.children[0].value),
                    parse_tree_to_ast(e.children[1]))
    elif e.data == 'assign':
        return Assign(str(e.children[0].value),
                      parse_tree_to_ast(e.children[1]))
    elif e.data == 'write':
        return Write(parse_tree_to_ast(e.children[0]),
                     parse_tree_to_ast(e.children[1]))
    elif e.data == 'expr':
        return Expr(parse_tree_to_ast(e.children[0]))
    elif e.data == 'return':
        return Return(parse_tree_to_ast(e.children[0]))
    elif e.data == 'new':
        return New(parse_tree_to_ast(e.children[0]))
    elif e.data == 'deref':
        return Deref(parse_tree_to_ast(e.children[0]))
    elif e.data == 'share':
        return Share(parse_tree_to_ast(e.children[0]))
    elif e.data == 'release':
        return Release(parse_tree_to_ast(e.children[0]))
    elif e.data == 'borrow':
        return Borrow(str(e.children[0].value),
                      parse_tree_to_ast(e.children[1]),
                      parse_tree_to_ast(e.children[2]))
    elif e.data == 'block':
        return Block([parse_tree_to_ast(child) for child in e.children])
    elif e.data == 'single':
        return [parse_tree_to_ast(e.children[0])]
    elif e.data == 'add_exp' or e.data == 'add_stmt' or e.data == 'add_param':
        return [parse_tree_to_ast(e.children[0])] \
            + parse_tree_to_ast(e.children[1])
    elif e.data == 'empty':
        return []
    elif e.data == 'lambda':
        return Lambda(e.children[0], parse_tree_to_ast(e.children[1]))
    elif e.data == 'arete':
        return parse_tree_to_ast(e.children[0])
    else:
        raise Exception('unhandled parse tree', e)

def parse(s):
    lexed = lark_parser.lex(s)
    print('tokens: ')
    for word in lexed:
        print(repr(word))
    print('')
    parse_tree = lark_parser.parse(s)
    print('parse tree: ')
    print(parse_tree)
    print('')
    ast = parse_tree_to_ast(parse_tree)
    print('abstract syntax tree: ')
    print(ast)
    print('')
    return ast

if __name__ == "__main__":
    file = open(sys.argv[1], 'r')
    p = file.read()
    ast = parse(p)
    print(str(ast))
