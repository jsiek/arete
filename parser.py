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
    if e.data == 'empty':
        return []
    elif e.data == 'single':
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
    elif e.data == 'true':
        return Bool(True)
    elif e.data == 'false':
        return Bool(False)
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
    elif e.data == 'tuple':
        return TupleExp(parse_tree_to_ast(e.children[0]))
    elif e.data == 'index':
        e1, e2 = e.children
        return Index(parse_tree_to_ast(e1), parse_tree_to_ast(e2))
    elif e.data == 'paren':
        return parse_tree_to_ast(e.children[0])
    
    # statements
    elif e.data == 'var_init':
        return VarInit(str(e.children[0].value),
                       parse_tree_to_ast(e.children[1]),
                       parse_tree_to_ast(e.children[2]))
    elif e.data == 'write':
        return Write(parse_tree_to_ast(e.children[0]),
                     parse_tree_to_ast(e.children[1]))
    elif e.data == 'expr':
        return Expr(parse_tree_to_ast(e.children[0]))
    elif e.data == 'return':
        return Return(parse_tree_to_ast(e.children[0]))
    elif e.data == 'pass':
        return Pass()
    elif e.data == 'seq':
        return Seq(parse_tree_to_ast(e.children[0]),
                   parse_tree_to_ast(e.children[1]))
    elif e.data == 'block':
        return parse_tree_to_ast(e.children[0])
    elif e.data == 'match':
        return Match(parse_tree_to_ast(e.children[0]),
                     parse_tree_to_ast(e.children[1]))
    elif e.data == 'if':
        return IfStmt(parse_tree_to_ast(e.children[0]),
                      parse_tree_to_ast(e.children[1]),
                      parse_tree_to_ast(e.children[2]))
    elif e.data == 'delete':
        return Delete(parse_tree_to_ast(e.children[0]))
    
    # patterns
    elif e.data == 'share_pat':
        return VarPat('share', str(e.children[0].value))
    elif e.data == 'take_pat':
        return VarPat('take', str(e.children[0].value))
    elif e.data == 'borrow_pat':
        return VarPat('borrow', str(e.children[0].value))
    elif e.data == 'share_pat':
        return VarPat('share', str(e.children[0].value))
    elif e.data == 'tuple_pat':
        return TuplePat(parse_tree_to_ast(e.children[0]))
    elif e.data == 'wildcard_pat':
        return WildCard()
    
    # miscelaneous
    elif e.data == 'case':
        return Case(parse_tree_to_ast(e.children[0]),
                    parse_tree_to_ast(e.children[1]))
    elif e.data == 'share_init':
        return Initializer('share', parse_tree_to_ast(e.children[0]))
    elif e.data == 'take_init':
        return Initializer('take', parse_tree_to_ast(e.children[0]))
    elif e.data == 'borrow_init':
        return Initializer('borrow', parse_tree_to_ast(e.children[0]))
        
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
