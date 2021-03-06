from abstract_syntax import *
from collections import OrderedDict
from dataclasses import dataclass
from lark import Lark, Token, logger
from typing import List, Set, Dict, Tuple
import sys

from lark import logger
import logging
#logger.setLevel(logging.DEBUG)

filename = '???'

def set_filename(fname):
    global filename
    filename = fname

##################################################
# Concrete Syntax Parser
##################################################

lark_parser = Lark(open("./Arete.lark").read(), start='arete', parser='lalr',
                   debug=True, propagate_positions=True)

##################################################
# Parsing Concrete to Abstract Syntax
##################################################

def parse_tree_to_str_list(e):
    if e.data == 'empty':
        return []
    elif e.data == 'single':
        return [e.children[0].value]
    elif e.data == 'push':
        return [e.children[0].value] + parse_tree_to_str_list(e.children[1])
    else:
        raise Exception('parse_tree_to_str_list, unexpected ' + str(e))

def parse_tree_to_type_annot(e):
    e.meta.filename = filename
    if e.data == 'nothing' or e.data == 'any_type':
        return AnyType(e.meta)
    elif e.data == 'just':
        return parse_tree_to_type_annot(e.children[0])
    elif e.data == 'int_type':
        return IntType(e.meta)
    elif e.data == 'bool_type':
        return BoolType(e.meta)
    elif e.data == 'array_type':
        return ArrayType(e.meta, parse_tree_to_type_annot(e.children[0]))
    elif e.data == 'ptr_type':
        return PointerType(e.meta,
                           [parse_tree_to_type_annot(elt_ty) \
                            for elt_ty in e.children])
    else:
        raise Exception('unrecognized type annotation ' + repr(e))
    
def parse_tree_to_param(e):
    e.meta.filename = filename
    if e.data == 'empty':
        return []
    elif e.data == 'single':
        return [parse_tree_to_param(e.children[0])]
    elif e.data == 'push':
        return [parse_tree_to_param(e.children[0])] \
            + parse_tree_to_param(e.children[1])
    else:
        return Param(e.meta, e.data, e.children[0].value,
                     parse_tree_to_type_annot(e.children[1]))

primitive_ops = {'add', 'sub', 'mul', 'div', 'int_div', 'neg',
                 'and', 'or', 'not',
                 'null', 'is_null', 'len', 'split', 'join',
                 'equal', 'not_equal',
                 'less', 'greater', 'less_equal', 'greater_equal',
                 'permission', 'upgrade'}
    
def parse_tree_to_ast(e):
    e.meta.filename = filename
    # expressions
    if e.data == 'var':
        return Var(e.meta, str(e.children[0].value))
    elif e.data == 'int':
        return Int(e.meta, int(e.children[0]))
    elif e.data == 'true':
        return Bool(e.meta, True)
    elif e.data == 'false':
        return Bool(e.meta, False)
    elif e.data in primitive_ops:
        return Prim(e.meta, e.data, [parse_tree_to_ast(c) for c in e.children])
    elif e.data == 'new':
        return New(e.meta, parse_tree_to_ast(e.children[0]))
    elif e.data == 'array':
        return Array(e.meta,
                     parse_tree_to_ast(e.children[0]),
                     parse_tree_to_ast(e.children[1]))
    elif e.data == 'lambda':
        return Lambda(e.meta,
                      parse_tree_to_param(e.children[0]),
                      parse_tree_to_ast(e.children[1]))
    elif e.data == 'call':
        e1, e2 = e.children
        return Call(e.meta, parse_tree_to_ast(e1), parse_tree_to_ast(e2))
    elif e.data == 'index':
        e1, e2 = e.children
        return Index(e.meta, parse_tree_to_ast(e1), parse_tree_to_ast(e2))
    elif e.data == 'deref':
        return Index(e.meta, parse_tree_to_ast(e.children[0]), Int(e.meta, 0))
    elif e.data == 'paren':
        return parse_tree_to_ast(e.children[0])
    elif e.data == 'member':
        return Member(e.meta,
                      parse_tree_to_ast(e.children[0]),
                      str(e.children[1].value))
    elif e.data == 'condition':
        return IfExp(e.meta,
                     parse_tree_to_ast(e.children[0]),
                     parse_tree_to_ast(e.children[1]),
                     parse_tree_to_ast(e.children[2]))
    elif e.data == 'let':
        return Let(e.meta,
                   parse_tree_to_param(e.children[0]),
                   parse_tree_to_ast(e.children[1]),
                   parse_tree_to_ast(e.children[2]))
    elif e.data == 'future':
        return FutureExp(e.meta, parse_tree_to_ast(e.children[0]))
    elif e.data == 'await':
        return Await(e.meta, parse_tree_to_ast(e.children[0]))
    
    # statements
    elif e.data == 'let_init':
        return LetInit(e.meta,
                       parse_tree_to_param(e.children[0]),
                       parse_tree_to_ast(e.children[1]),
                       parse_tree_to_ast(e.children[2]))
    elif e.data == 'var_init':
        return VarInit(e.meta,
                       e.children[0].value,
                       parse_tree_to_ast(e.children[1]),
                       parse_tree_to_ast(e.children[2]))
    elif e.data == 'return':
        return Return(e.meta, parse_tree_to_ast(e.children[0]))
    elif e.data == 'write':
        return Write(e.meta,
                     parse_tree_to_ast(e.children[0]),
                     parse_tree_to_ast(e.children[1]))
    elif e.data == 'transfer':
        return Transfer(e.meta,
                        parse_tree_to_ast(e.children[0]),
                        parse_tree_to_ast(e.children[1]),
                        parse_tree_to_ast(e.children[2]))
    elif e.data == 'expr':
        return Expr(e.meta, parse_tree_to_ast(e.children[0]))
    elif e.data == 'assert':
        return Assert(e.meta, parse_tree_to_ast(e.children[0]))
    elif e.data == 'return':
        return Return(e.meta, parse_tree_to_ast(e.children[0]))
    elif e.data == 'seq':
        return Seq(e.meta,
                   parse_tree_to_ast(e.children[0]),
                   parse_tree_to_ast(e.children[1]))
    elif e.data == 'last_stmt':
        return parse_tree_to_ast(e.children[0])
    elif e.data == 'if' or e.data == 'else_if':
        return IfStmt(e.meta,
                      parse_tree_to_ast(e.children[0]),
                      parse_tree_to_ast(e.children[1]),
                      parse_tree_to_ast(e.children[2]))
    elif e.data == 'else':
        return parse_tree_to_ast(e.children[0])
    elif e.data == 'no_else':
        return Pass(e.meta)
    elif e.data == 'while':
        return While(e.meta,
                      parse_tree_to_ast(e.children[0]),
                      parse_tree_to_ast(e.children[1]))
    elif e.data == 'delete':
        return Delete(e.meta, parse_tree_to_ast(e.children[0]))
    elif e.data == 'block':
        return Block(e.meta, body=parse_tree_to_ast(e.children[0]))
    elif e.data == 'pass':
        return Pass(e.meta)

    # declarations
    elif e.data == 'import':
        return Import(e.meta,
                      parse_tree_to_ast(e.children[0]),
                      parse_tree_to_str_list(e.children[1]))
    elif e.data == 'global':
        return Global(e.meta,
                      str(e.children[0].value),
                      parse_tree_to_type_annot(e.children[1]),
                      parse_tree_to_ast(e.children[2]))
    elif e.data == 'constant':
        return ConstantDecl(e.meta,
                            str(e.children[0].value),
                            parse_tree_to_type_annot(e.children[1]),
                            parse_tree_to_ast(e.children[2]))
    elif e.data == 'function':
        return Function(e.meta,
                        str(e.children[0].value),
                        parse_tree_to_param(e.children[1]),
                        parse_tree_to_type_annot(e.children[2]),
                        parse_tree_to_ast(e.children[3]))
    elif e.data == 'module':
        return ModuleDecl(e.meta,
                          str(e.children[0].value),
                          parse_tree_to_str_list(e.children[1]),
                          parse_tree_to_ast(e.children[2]))
    
    # miscelaneous
    elif e.data == 'default_init':
        return Initializer(e.meta, 'default', parse_tree_to_ast(e.children[0]))
    elif e.data == 'frac_init':
        return Initializer(e.meta, parse_tree_to_ast(e.children[0]), parse_tree_to_ast(e.children[1]))
    
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
    filename = sys.argv[1]
    file = open(filename, 'r')
    p = file.read()
    ast = parse(p)
    print(str(ast))
