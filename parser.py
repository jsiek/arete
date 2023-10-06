from abstract_syntax import *
from functions import *
from variables_and_binding import *
from tuples_and_arrays import *
from records import *
from variants import *
from modules import *
from pointers import *
from futures import *
from interfaces_and_impls import *
from primitive_operations import PrimitiveCall
from ast_types import *
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

def parse_tree_to_list(e):
    if e.data == 'empty':
        return tuple([])
    elif e.data == 'single':
        return tuple([parse_tree_to_ast(e.children[0])])
    elif e.data == 'push':
        return tuple([parse_tree_to_ast(e.children[0])]) \
            + parse_tree_to_list(e.children[1])
    else:
        raise Exception('parse_tree_to_str_list, unexpected ' + str(e))
    
def parse_tree_to_str_list(e):
    if e.data == 'nothing':
        return tuple()
    elif e.data == 'just':
        return parse_tree_to_str_list(e.children[0])
    elif e.data == 'empty':
        return type()
    elif e.data == 'single':
        return tuple([e.children[0].value])
    elif e.data == 'push':
        return tuple([e.children[0].value]) \
            + parse_tree_to_str_list(e.children[1])
    else:
        raise Exception('parse_tree_to_str_list, unexpected ' + str(e))

def parse_tree_to_req(e):
    e.meta.filename = filename
    if e.data == 'impl_req':
        return ImplReq(e.meta,
                       str(e.children[0].value) + str(next_impl_num()),
                       str(e.children[0].value),
                       parse_tree_to_type_list(e.children[1]),
                       None)
    else:
        raise Exception('unrecognized requirement ' + str(e))
    
def parse_tree_to_type(e):
    e.meta.filename = filename
    if e.data == 'nothing' or e.data == 'any_type':
        return AnyType(e.meta)
    elif e.data == 'just':
        return parse_tree_to_type(e.children[0])
    elif e.data == 'int_type':
        return IntType(e.meta)
    elif e.data == 'rational_type':
        return RationalType(e.meta)
    elif e.data == 'bool_type':
        return BoolType(e.meta)
    elif e.data == 'void_type':
        return VoidType(e.meta)
    elif e.data == 'array_type':
        return ArrayType(e.meta, parse_tree_to_type(e.children[0]))
    elif e.data == 'ptr_type':
        return PointerType(e.meta,
                           parse_tree_to_type(e.children[0]))
    elif e.data == 'tuple_type':
        return TupleType(e.meta,
                         parse_tree_to_type_list(e.children[0]))
    elif e.data == 'function_type':
       return FunctionType(e.meta,
                           tuple(), # TODO: add type parameters
                           parse_tree_to_param_type_list(e.children[0]),
                           parse_tree_to_type(e.children[1]),
                           tuple()) # TODO: add requirements
    elif e.data == 'variant_type':
        return VariantType(e.meta,
                           parse_tree_to_alt_list(e.children[0]))
    elif e.data == 'record_type':
        return RecordType(e.meta,
                           parse_tree_to_alt_list(e.children[0]))
    elif e.data == 'recursive_type':
        return RecursiveType(e.meta,
                             str(e.children[0].value),
                             parse_tree_to_type(e.children[1]))
    elif e.data == 'type_var':
        return TypeVar(e.meta, str(e.children[0].value))
    elif e.data == 'type_application':
        return TypeApplication(e.meta,
                               parse_tree_to_type(e.children[0]),
                               parse_tree_to_type_list(e.children[1]))
    else:
        raise Exception('unrecognized type annotation ' + repr(e))
    
def parse_tree_to_type_list(e):
    e.meta.filename = filename
    if e.data == 'empty':
        return ()
    elif e.data == 'single':
        return (parse_tree_to_type(e.children[0]),)
    elif e.data == 'push':
        return (parse_tree_to_type(e.children[0]),) \
            + parse_tree_to_type_list(e.children[1])
    else:
        raise Exception('unrecognized as a type list ' + repr(e))

def parse_tree_to_param_type_list(e):
    e.meta.filename = filename
    if e.data == 'empty':
        return ()
    elif e.data == 'single':
        kind = str(e.children[0].data)
        ty = parse_tree_to_type(e.children[1])
        return ((kind, ty) ,)
    elif e.data == 'push':
        kind = str(e.children[0].data)
        ty = parse_tree_to_type(e.children[1])
        return ((kind, ty),) \
            + parse_tree_to_param_type_list(e.children[2])
    else:
        raise Exception('unrecognized as a type list ' + repr(e))
    
def parse_tree_to_req_list(e):
    e.meta.filename = filename
    if e.data == 'empty':
        return ()
    elif e.data == 'single':
        return (parse_tree_to_req(e.children[0]),)
    elif e.data == 'push':
        return (parse_tree_to_req(e.children[0]),) \
            + parse_tree_to_req_list(e.children[1])
    else:
        raise Exception('unrecognized as a req list ' + repr(e))
    
def parse_tree_to_alt(e):
    return (str(e.children[0].value),
            parse_tree_to_type(e.children[1]))
    
def parse_tree_to_alt_list(e):
    if e.data == 'empty':
        return ()
    elif e.data == 'single':
        return (parse_tree_to_alt(e.children[0]),)
    elif e.data == 'push':
        return (parse_tree_to_alt(e.children[0]),) \
            + parse_tree_to_alt_list(e.children[1])
    else:
        raise Exception('unrecognized as a type list ' + repr(e))
    
def parse_tree_to_param(e):
  e.meta.filename = filename
  if e.data == 'empty' or e.data == 'nothing':
    return []
  elif e.data == 'just':
    return parse_tree_to_param(e.children[0])
  elif e.data == 'single':
    return [parse_tree_to_param(e.children[0])]
  elif e.data == 'push':
    return [parse_tree_to_param(e.children[0])] \
      + parse_tree_to_param(e.children[1])
  elif e.data == 'binding':
    return Param(e.meta, e.children[0].data, None, e.children[1].value,
                 parse_tree_to_type(e.children[2]))
  elif e.data == 'no_binding':
    return NoParam(e.meta)
  else:    
    raise Exception('unrecognized parameter' + repr(e))

def parse_tree_to_case(e):
    tag = str(e.children[0].value)
    var = parse_tree_to_param(e.children[1])
    body = parse_tree_to_ast(e.children[2])
    return (tag, var, body)

def parse_tree_to_case_list(e):
    if e.data == 'single':
        return (parse_tree_to_case(e.children[0]),)
    elif e.data == 'push':
        return (parse_tree_to_case(e.children[0]),) \
            + parse_tree_to_case_list(e.children[1])
    else:
        raise Exception('unrecognized as a type list ' + repr(e))
    
primitive_ops = {'add', 'sub', 'mul', 'div', 'int_div', 'mod', 'neg', 'sqrt',
                 'and', 'or', 'not',
                 'copy',
                 'len', 'split', 'join',
                 'equal', 'not_equal',
                 'less', 'greater', 'less_equal', 'greater_equal',
                 'permission', 'upgrade', 'breakpoint',
                 'exit', 'input', 'print'}

impl_num = 0
def next_impl_num():
    global impl_num
    ret = impl_num
    impl_num += 1
    return ret
    
def parse_tree_to_ast(e):
    e.meta.filename = filename
    # expressions
    if e.data == 'raw_string':
        return str(e.children[0].value)
    if e.data == 'var':
        return Var(e.meta, str(e.children[0].value))
    elif e.data == 'int':
        return Int(e.meta, int(e.children[0]))
    elif e.data == 'true':
        return Bool(e.meta, True)
    elif e.data == 'false':
        return Bool(e.meta, False)
    elif e.data in primitive_ops:
        return PrimitiveCall(e.meta, e.data,
                             [parse_tree_to_ast(c) for c in e.children])
    elif e.data == 'tuple':
        return TupleExp(e.meta, parse_tree_to_ast(e.children[0]))
    elif e.data == 'record':
        return RecordExp(e.meta,
                         parse_tree_to_ast(e.children[0]))
    elif e.data == 'array':
        return Array(e.meta,
                     parse_tree_to_ast(e.children[0]),
                     parse_tree_to_ast(e.children[1]))
    elif e.data == 'lambda':
        return Lambda(e.meta,
                      parse_tree_to_param(e.children[0]),
                      parse_tree_to_param(e.children[1]),
                      str(e.children[2].data),
                      [],
                      parse_tree_to_ast(e.children[3]),
                      'lambda')
    elif e.data == 'call':
        e1, e2 = e.children
        return Call(e.meta, parse_tree_to_ast(e1), parse_tree_to_ast(e2))
    elif e.data == 'index':
        e1, e2 = e.children
        return Index(e.meta, parse_tree_to_ast(e1), parse_tree_to_ast(e2))
    elif e.data == 'slice':
        e1, e2, e3, e4 = e.children
        return Slice(e.meta, parse_tree_to_ast(e1), parse_tree_to_ast(e2),
                     parse_tree_to_ast(e3), parse_tree_to_ast(e4))
    elif e.data == 'deref':
        return Deref(e.meta, parse_tree_to_ast(e.children[0]))
    elif e.data == 'addrof':
        return AddressOf(e.meta, parse_tree_to_ast(e.children[0]))
    elif e.data == 'paren':
        return parse_tree_to_ast(e.children[0])
    elif e.data == 'module_member':
        return ModuleMember(e.meta,
                            parse_tree_to_ast(e.children[0]),
                            str(e.children[1].value))
    elif e.data == 'variant_member':
        return VariantMember(e.meta,
                             parse_tree_to_ast(e.children[0]),
                             str(e.children[1].value))
    elif e.data == 'record_member':
        return FieldAccess(e.meta,
                           parse_tree_to_ast(e.children[0]),
                           str(e.children[1].value))
    elif e.data == 'condition':
        return IfExp(e.meta,
                     parse_tree_to_ast(e.children[0]),
                     parse_tree_to_ast(e.children[1]),
                     parse_tree_to_ast(e.children[2]))
    elif e.data == 'binding_exp':
        return BindingExp(e.meta,
                          Param(e.meta, e.children[0].data,
                                None, e.children[1].value,
                                parse_tree_to_type(e.children[2])),
                          parse_tree_to_ast(e.children[3]),
                          parse_tree_to_ast(e.children[4]))
    elif e.data == 'future':
        return FutureExp(e.meta, parse_tree_to_ast(e.children[0]))
    elif e.data == 'wait':
        return Wait(e.meta, parse_tree_to_ast(e.children[0]))
    elif e.data == 'tag_variant':
        return TagVariant(e.meta,
                          str(e.children[0].value),
                          parse_tree_to_ast(e.children[1]),
                          parse_tree_to_type(e.children[2]))
    
    # statements
    elif e.data == 'binding_stmt':
        return BindingStmt(e.meta,
                           Param(e.meta, e.children[0].data,
                                 None, e.children[1].value,
                                 parse_tree_to_type(e.children[2])),
                           parse_tree_to_ast(e.children[3]),
                           parse_tree_to_ast(e.children[4]))
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
    elif e.data == 'last_statement':
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
    elif e.data == 'for_in':
        return ForIn(e.meta,
                     parse_tree_to_param(e.children[0]),
                     parse_tree_to_ast(e.children[1]),
                     parse_tree_to_ast(e.children[2]))
    elif e.data == 'delete':
        return Delete(e.meta, parse_tree_to_ast(e.children[0]))
    elif e.data == 'block':
        return Block(e.meta, body=parse_tree_to_ast(e.children[0]))
    elif e.data == 'pass':
        return Pass(e.meta)
    elif e.data == 'match':
        return Match(e.meta,
                     parse_tree_to_ast(e.children[0]),
                     parse_tree_to_case_list(e.children[1]))

    # definitions
    elif e.data == 'import':
        return Import(e.meta,
                      parse_tree_to_ast(e.children[0]),
                      parse_tree_to_list(e.children[1]))
    elif e.data == 'global':
        return Global(e.meta,
                      str(e.children[0].value),
                      parse_tree_to_type(e.children[1]),
                      parse_tree_to_ast(e.children[2]))
    elif e.data == 'constant':
        return ConstantDef(e.meta,
                            str(e.children[0].value),
                            parse_tree_to_type(e.children[1]),
                            parse_tree_to_ast(e.children[2]))
    elif e.data == 'type_definition':
        return TypeAlias(e.meta,
                         str(e.children[0].value),
                         parse_tree_to_type(e.children[1]))
    elif e.data == 'type_operator':
        return TypeOperator(e.meta,
                            str(e.children[0].value),
                            parse_tree_to_str_list(e.children[1]),
                            parse_tree_to_type(e.children[2]))
    elif e.data == 'function':
        return Function(e.meta,
                        str(e.children[0].value),
                        parse_tree_to_str_list(e.children[1]),
                        parse_tree_to_param(e.children[2]),
                        parse_tree_to_type(e.children[3]),
                        str(e.children[4].data),
                        parse_tree_to_req_list(e.children[5]),
                        parse_tree_to_ast(e.children[6]))
    elif e.data == 'module':
        return ModuleDef(e.meta,
                          str(e.children[0].value),
                          parse_tree_to_list(e.children[1]),
                          parse_tree_to_ast(e.children[2]))
    elif e.data == 'interface':
        return Interface(e.meta,
                         str(e.children[0].value),
                         parse_tree_to_str_list(e.children[1]),
                         parse_tree_to_req_list(e.children[2]),
                         parse_tree_to_ast(e.children[3]))
    elif e.data == 'declaration':
        return (str(e.children[0].value), parse_tree_to_type(e.children[1]))
    elif e.data == 'implementation':
        return Impl(e.meta,
                    str(e.children[0].value) + str(next_impl_num()),
                    str(e.children[0].value),
                    parse_tree_to_type_list(e.children[1]),
                    parse_tree_to_ast(e.children[2]))
    
    # miscelaneous
    elif e.data == 'assign':
        return (str(e.children[0].value), parse_tree_to_ast(e.children[1]))
    elif e.data == 'field':
        return (str(e.children[0].value), parse_tree_to_ast(e.children[1]))
    
    # is impl_req needed?
    elif e.data == 'impl_req':
        return ImplReq(e.meta,
                       str(e.children[0].value) + str(next_impl_num()),
                       str(e.children[0].value),
                       parse_tree_to_type_list(e.children[1]),
                       None)
    elif e.data == 'default_initializer':
        return parse_tree_to_ast(e.children[0])
    elif e.data == 'frac_initializer':
        return PercentOf(e.meta, parse_tree_to_ast(e.children[0]), parse_tree_to_ast(e.children[1]))
    
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
