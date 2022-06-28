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

def parse_tree_to_param(e):
    if e.data == 'single':
        return [parse_tree_to_param(e.children[0])]
    elif e.data == 'push':
        return [parse_tree_to_param(e.children[0])] \
            + parse_tree_to_param(e.children[1])
    else:
        return Param(e.data, e.children[0].value)

def parse_tree_to_ast(e):
    # expressions
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
    elif e.data == 'new':
        return New(parse_tree_to_ast(e.children[0]))
    elif e.data == 'deref':
        return Deref(parse_tree_to_ast(e.children[0]))
    elif e.data == 'lambda':
        return Lambda(parse_tree_to_param(e.children[0]),
                      parse_tree_to_ast(e.children[1]))
    elif e.data == 'call':
        e1, e2 = e.children
        return Call(parse_tree_to_ast(e1), parse_tree_to_ast(e2))
    # statements
    elif e.data == 'init_share':
        return Init('share',
                    str(e.children[0].value),
                    parse_tree_to_ast(e.children[1]),
                    parse_tree_to_ast(e.children[2]))
    elif e.data == 'init_take':
        return Init('take',
                    str(e.children[0].value),
                    parse_tree_to_ast(e.children[1]),
                    parse_tree_to_ast(e.children[2]))
    elif e.data == 'init_borrow':
        return Init('borrow',
                    str(e.children[0].value),
                    parse_tree_to_ast(e.children[1]),
                    parse_tree_to_ast(e.children[2]))
    elif e.data == 'write':
        return Write(parse_tree_to_ast(e.children[0]),
                     parse_tree_to_ast(e.children[1]),
                    parse_tree_to_ast(e.children[2]))
    elif e.data == 'expr':
        return Expr(parse_tree_to_ast(e.children[0]),
                    parse_tree_to_ast(e.children[1]))
    elif e.data == 'return':
        return Return(parse_tree_to_ast(e.children[0]))
    # lists
    elif e.data == 'single':
        return [parse_tree_to_ast(e.children[0])]
    elif e.data == 'push':
        return [parse_tree_to_ast(e.children[0])] \
            + parse_tree_to_ast(e.children[1])
    elif e.data == 'empty':
        return []
    # whole program
    elif e.data == 'arete':
        return parse_tree_to_ast(e.children[0])
    else:
        raise Exception('unhandled parse tree', e)

def parse(s, trace = False):
    lexed = lark_parser.lex(s)
    if trace:
        print('tokens: ')
        for word in lexed:
            print(repr(word))
        print('')
    parse_tree = lark_parser.parse(s)
    if trace:
        print('parse tree: ')
        print(parse_tree)
        print('')
    ast = parse_tree_to_ast(parse_tree)
    if trace:
        print('abstract syntax tree: ')
        print(ast)
        print('')
    return ast

if __name__ == "__main__":
    file = open(sys.argv[1], 'r')
    p = file.read()
    ast = parse(p)
    print(str(ast))
