# Propagate constants.
# TODO: more partial evaluation.

from abstract_syntax import *
from functions import *
from variables_and_binding import *
from variants import *
from tuples_and_arrays import *
from modules import *
from pointers import *
from futures import *
from dataclasses import dataclass
from parser import parse, set_filename
from typing import List, Set, Dict, Tuple, Any
from fractions import Fraction
import numbers
import sys
import copy
from utilities import *

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
      return Number(n)
    case Frac(f):
      return Number(f)
    case Bool(b):
      return Boolean(b)
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
        return PrimitiveCall(loc, op, args)
  
def const_eval_exp(e, env):
    match e:
      case PercentOf(loc, percent, arg):
        if percent == 'default':
          new_percent = 'default'
        else:
          new_percent = const_eval_exp(percent, env)
        new_arg = const_eval_exp(arg, env)
        return PercentOf(loc, new_percent, new_arg)
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
      case PrimitiveCall(op, args):
        new_args = [const_eval_exp(arg, env) for arg in args]
        return const_eval_prim(e.location, op, new_args)
      case ModuleMember(arg, field):
        new_arg = const_eval_exp(arg, env)
        return ModuleMember(e.location, new_arg, field)
      case VariantMember(arg, field):
        new_arg = const_eval_exp(arg, env)
        return VariantMember(e.location, new_arg, field)
      case Array(size, arg):
        new_size = const_eval_exp(size, env)
        new_arg = const_eval_exp(arg, env)
        return Array(e.location, new_size, new_arg)
      case TupleExp(inits):
        new_inits = [const_eval_exp(init, env) for init in inits]
        return TupleExp(e.location, new_inits)
      case TagVariant(tag, arg, ty):
        return TagVariant(e.location, tag, const_eval_exp(arg, env), ty)
      case Lambda(params, ret_mode, body, name):
        body_env = env.copy()
        for p in params:
          if p.ident in body_env.keys():
            del body_env[p.ident]
        new_body = const_eval_statement(body, body_env)
        return Lambda(e.location, params, ret_mode, new_body, name)
      case Call(fun, args):
        new_fun = const_eval_exp(fun, env)
        new_args = [const_eval_exp(arg, env) for arg in args]
        return Call(e.location, new_fun, new_args)
      case Index(arg, index):
        new_arg = const_eval_exp(arg, env)
        new_index = const_eval_exp(index, env)
        return Index(e.location, new_arg, new_index)
      case Deref(arg):
        new_arg = const_eval_exp(arg, env)
        return Deref(e.location, new_arg)
      case AddressOf(arg):
        new_arg = const_eval_exp(arg, env)
        return AddressOf(e.location, new_arg)
      case IfExp(cond, thn, els):
        new_cond = const_eval_exp(cond, env)
        new_thn = const_eval_exp(thn, env)
        new_els = const_eval_exp(els, env)
        return IfExp(e.location, new_cond, new_thn, new_els)
      case BindingExp(param, rhs, body):
        new_rhs = const_eval_exp(rhs, env)
        body_env = env.copy()
        if param.ident in body_env.keys():
          del body_env[param.ident]
        new_body = const_eval_exp(body, body_env)
        return BindingExp(e.location, param, new_rhs, new_body)
      case FutureExp(arg):
        new_arg = const_eval_exp(arg, env)
        return FutureExp(e.location, new_arg)
      case Wait(arg):
        new_arg = const_eval_exp(arg, env)
        return Wait(e.location, new_arg)
      case _:
        error(e.location, 'error in const_eval_exp, unhandled: ' + repr(e)) 

def const_eval_statement(s, env):
    match s:
      case BindingStmt(param, rhs, body):
        new_rhs = const_eval_exp(rhs, env)
        body_env = env.copy()
        if param.ident in body_env.keys():
          del body_env[param.ident]
        new_body = const_eval_statement(body, body_env)
        return BindingStmt(s.location, param, new_rhs, new_body)
      case Seq(first, rest):
        new_first = const_eval_statement(first, env)
        new_rest = const_eval_statement(rest, env)
        return Seq(s.location, new_first, new_rest)
      case Return(arg):
        new_arg = const_eval_exp(arg, env)
        return Return(s.location, new_arg)
      case Pass():
        return s
      case Write(lhs, rhs):
        new_lhs = const_eval_exp(lhs, env)
        new_rhs = const_eval_exp(rhs, env)
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
        new_thn = const_eval_statement(thn, env)
        new_els = const_eval_statement(els, env)
        return IfStmt(s.location, new_cond, new_thn, new_els)
      case While(cond, body):
        new_cond = const_eval_exp(cond, env)
        new_body = const_eval_statement(body, env)
        return While(s.location, new_cond, new_body)
      case Block(body):
        return Block(s.location, const_eval_statement(body, env))
      case Match(cond, cases):
        new_cases = []
        for (tag, x, body) in cases:
          body_env = env.copy()
          if x in body_env.keys():
            del body_env[x]
          new_cases += [(tag, x, const_eval_statement(body, body_env))]
        return Match(s.location, const_eval_exp(cond, env), new_cases)
      case _:
        error(s.location, 'error in const_eval_statement, unhandled: ' + repr(s)) 

def const_eval_decl(decl, env):
    match decl:
      case ConstantDef(name, type_annot, rhs):
        new_rhs = const_eval_exp(rhs, env)
        if is_constant(new_rhs):
          env[name] = new_rhs
        else:
          error(decl.location, 'right-hand side must be a constant, not '
                + str(rhs))
        return []
      case TypeAlias(name, type):
        return [TypeAlias(decl.location, name, type)]
      case TypeOperator(name, params, body):
        return [TypeOperator(decl.location, name, params, body)]
      case Global(name, type_annot, rhs):
        new_rhs = const_eval_exp(rhs, env)
        return [Global(decl.location, name, type_annot, new_rhs)]
      case Function(name, ty_params, params, return_ty, return_mode, body):
        body_env = env.copy()
        for p in params:
          if p.ident in body_env.keys():
            del body_env[p.ident]
        new_body = const_eval_statement(body, body_env)
        return [Function(decl.location, name, ty_params, params, return_ty,
                         return_mode, new_body)]
      case ModuleDef(name, exports, body):
        body_env = env.copy()
        new_body = const_eval_decls(body, body_env)
        return [ModuleDef(decl.location, name, exports, new_body)]
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
