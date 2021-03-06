# Propagate constants.
# TODO: more partial evaluation.

from abstract_syntax import *
from dataclasses import dataclass
from parser import parse, set_filename
from typing import List, Set, Dict, Tuple, Any
from fractions import Fraction
import numbers
import sys
import copy
from utilities import *

def const_eval_init(init, env):
    match init:
      case Initializer(loc, percent, arg):
        if percent == 'default':
          new_percent = 'default'
        else:
          new_percent = const_eval_exp(percent, env)
        new_arg = const_eval_exp(arg, env)
        return Initializer(loc, new_percent, new_arg)
      case _:
        error(init.location, 'in const_eval_init, expected an initializer, not '
              + str(init))

def is_constant(e):
  match e:
    case Int(n):
      return True
    case Frac(f):
      return True
    case Bool(b):
      return True
    case _:
      return False

def eval_constant(e):
  match e:
    case Int(n):
      return Number(True, n)
    case Frac(f):
      return Number(True, f)
    case Bool(b):
      return Boolean(True, b)
    case _:
      error(e.location, "expected a constant, not " + str(e))
      
def const_eval_prim(loc, op, args):
  match op:
    case 'div':
      if is_constant(args[0]) and is_constant(args[1]):
        left = to_number(eval_constant(args[0]), loc)
        right = to_number(eval_constant(args[1]), loc)
        return Frac(loc, Fraction(left, right))
    case _:
        return Prim(loc, op, args)
  
def const_eval_exp(e, env):
    match e:
      case Var(x):
        if x in env:
          return env[x]
        else:
          return e
      case Int(n):
        return e
      case Frac(f):
        return e
      case Bool(b):
        return e
      case Prim(op, args):
        new_args = [const_eval_exp(arg, env) for arg in args]
        return const_eval_prim(e.location, op, new_args)
      case Member(arg, field):
        new_arg = const_eval_exp(arg, env)
        return Member(e.location, new_arg, field)
      case New(inits):
        new_inits = [const_eval_init(init, env) for init in inits]
        return New(e.location, new_inits)
      case Array(size, arg):
        new_size = const_eval_exp(size, env)
        new_arg = const_eval_exp(arg, env)
        return Array(e.location, new_size, new_arg)
      case Lambda(params, body):
        body_env = env.copy()
        for p in params:
          if p.ident in body_env.keys():
            del body_env[p.ident]
        new_body = const_eval_stmt(body, body_env)
        return Lambda(e.location, params, new_body)
      case Call(fun, args):
        new_fun = const_eval_exp(fun, env)
        new_args = [const_eval_init(arg, env) for arg in args]
        return Call(e.location, new_fun, new_args)
      case Index(arg, index):
        new_arg = const_eval_exp(arg, env)
        new_index = const_eval_exp(index, env)
        return Index(e.location, new_arg, new_index)
      case IfExp(cond, thn, els):
        new_cond = const_eval_exp(cond, env)
        new_thn = const_eval_exp(thn, env)
        new_els = const_eval_exp(els, env)
        return IfExp(e.location, new_cond, new_thn, new_els)
      case Let(var, init, body):
        new_init = const_eval_init(init, env)
        body_env = env.copy()
        if var.ident in body_env.keys():
          del body_env[var.ident]
        new_body = const_eval_exp(body, env)
        return Let(e.location, var, new_init, new_body)
      case FutureExp(arg):
        new_arg = const_eval_exp(arg, env)
        return FutureExp(e.location, new_arg)
      case Await(arg):
        new_arg = const_eval_exp(arg, env)
        return Await(e.location, new_arg)
      case _:
        error(e.location, 'error in const_eval_exp, unhandled: ' + repr(e)) 

def const_eval_stmt(s, env):
    match s:
      case LetInit(var, init, body):
        new_init = const_eval_init(init, env)
        body_env = env.copy()
        if var.ident in body_env.keys():
          del body_env[var]
        new_body = const_eval_stmt(body, body_env)
        return LetInit(s.location, var, new_init, new_body)
      case Seq(first, rest):
        new_first = const_eval_stmt(first, env)
        new_rest = const_eval_stmt(rest, env)
        return Seq(s.location, new_first, new_rest)
      case Return(arg):
        new_arg = const_eval_exp(arg, env)
        return Return(s.location, new_arg)
      case Pass():
        return s
      case Write(lhs, rhs):
        new_lhs = const_eval_exp(lhs, env)
        new_rhs = const_eval_init(rhs, env)
        return Write(s.location, new_lhs, new_rhs)
      case Transfer(lhs, percent, rhs):
        new_lhs = const_eval_exp(lhs, env)
        new_percent = const_eval_exp(percent, env)
        new_rhs = const_eval_exp(rhs, env)
        return Transfer(s.location, new_lhs, new_percent, new_rhs)
      case Expr(arg):
        new_arg = const_eval_exp(arg, env)
        return Expr(s.location, new_arg)
      case Assert(arg):
        new_arg = const_eval_exp(arg, env)
        return Assert(s.location, new_arg)
      case Delete(arg):
        new_arg = const_eval_exp(arg, env)
        return Delete(s.location, new_arg)
      case IfStmt(cond, thn, els):
        new_cond = const_eval_exp(cond, env)
        new_thn = const_eval_stmt(thn, env)
        new_els = const_eval_stmt(els, env)
        return IfStmt(s.location, new_cond, new_thn, new_els)
      case While(cond, body):
        new_cond = const_eval_exp(cond, env)
        new_body = const_eval_stmt(body, env)
        return While(s.location, new_cond, new_body)
      case Block(body):
        return Block(s.location, const_eval_stmt(body, env))
      case _:
        error(s.location, 'error in const_eval_stmt, unhandled: ' + repr(s)) 

def const_eval_decl(decl, env):
    match decl:
      case ConstantDecl(name, type_annot, rhs):
        new_rhs = const_eval_exp(rhs, env)
        if is_constant(new_rhs):
          env[name] = new_rhs
        else:
          error(decl.location, 'right-hand side must be a constant, not '
                + str(rhs))
        return []
      case Global(name, type_annot, rhs):
        new_rhs = const_eval_exp(rhs, env)
        return [Global(decl.location, name, type_annot, new_rhs)]
      case Function(name, params, return_ty, body):
        body_env = env.copy()
        for p in params:
          if p.ident in body_env.keys():
            del body_env[p.ident]
        new_body = const_eval_stmt(body, body_env)
        return [Function(decl.location, name, params, return_ty, new_body)]
      case ModuleDecl(name, exports, body):
        body_env = env.copy()
        new_body = const_eval_decls(body, body_env)
        return [ModuleDecl(decl.location, name, exports, new_body)]
      case Import(module, imports):
        new_module = const_eval_exp(module, env)
        return [Import(decl.location, module, imports)]
      case _:
        error(decl.location, "in const_eval_decl, unhandled: " + str(decl))

def const_eval_decls(decls, env):
    new_decls = []
    for d in decls:
        new_decls += const_eval_decl(d, env)
    return new_decls
