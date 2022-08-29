# This desugaring pass currently just copies the AST but this pass is
# here to make it easier in the future to define some language
# features by desugaring into other language features.

from abstract_syntax import *
from functions import *
from variables_and_binding import *
from tuples_and_arrays import *
from variants import *
from modules import *
from interfaces_and_impls import *
from pointers import *
from futures import *
from utilities import *

def desugar_exp(e, env):
    match e:
      case PercentOf(loc, percent, arg):
        new_percent = desugar_exp(percent, env)
        new_arg = desugar_exp(arg, env)
        return PercentOf(loc, new_percent, new_arg)
      case Var(x):
        return e
      case Int(n):
        return e
      case Frac(f):
        return e
      case Bool(b):
        return e
      case PrimitiveCall(op, args):
        new_args = [desugar_exp(arg, env) for arg in args]
        return PrimitiveCall(e.location, op, new_args)
      case ModuleMember(arg, field):
        new_arg = desugar_exp(arg, env)
        return ModuleMember(e.location, new_arg, field)
      case VariantMember(arg, field):
        new_arg = desugar_exp(arg, env)
        return VariantMember(e.location, new_arg, field)
      case Array(size, arg):
        new_size = desugar_exp(size, env)
        new_arg = desugar_exp(arg, env)
        return Array(e.location, new_size, new_arg)
      case TupleExp(inits):
        new_inits = [desugar_exp(init, env) for init in inits]
        return TupleExp(e.location, new_inits)
      case TagVariant(tag, arg, ty):
        return TagVariant(e.location, tag, desugar_exp(arg, env), ty)
      case Lambda(params, ret_mode, reqs, body, name):
        body_env = env.copy()
        for p in params:
            body_env[p.ident] = False
        new_body = desugar_statement(body, body_env)
        return Lambda(e.location, params, ret_mode, reqs, new_body, name)
      case Call(fun, inits):
        new_fun = desugar_exp(fun, env)
        new_inits = [desugar_exp(init, env) for init in inits]
        return Call(e.location, new_fun, new_inits)
      case Index(arg, index):
        new_arg = desugar_exp(arg, env)
        new_index = desugar_exp(index, env)
        return Index(e.location, new_arg, new_index)
      case Deref(arg):
        new_arg = desugar_exp(arg, env)
        return Deref(e.location, new_arg)
      case AddressOf(arg):
        new_arg = desugar_exp(arg, env)
        return AddressOf(e.location, new_arg)
      case IfExp(cond, thn, els):
        new_cond = desugar_exp(cond, env)
        new_thn = desugar_exp(thn, env)
        new_els = desugar_exp(els, env)
        return IfExp(e.location, new_cond, new_thn, new_els)
      case BindingExp(param, rhs, body):
        loc = e.location
        new_rhs = desugar_exp(rhs, env)
        body_env = env.copy()
        body_env[param.ident] = False
        new_body = desugar_exp(body, body_env)
        return BindingExp(loc, param, new_rhs, new_body)
      case FutureExp(arg):
        new_arg = desugar_exp(arg, env)
        return FutureExp(e.location, new_arg)
      case Wait(arg):
        new_arg = desugar_exp(arg, env)
        return Wait(e.location, new_arg)
      case _:
        error(e.location, 'error in desugar_exp, unhandled: ' + repr(e))
    
def desugar_statement(s, env):
    match s:
      case BindingStmt(param, rhs, body):
        loc = s.location
        new_rhs = desugar_exp(rhs, env)
        body_env = env.copy()
        body_env[param.ident] = False
        new_body = desugar_statement(body, body_env)
        return BindingStmt(loc, param, new_rhs, new_body)
      case Seq(first, rest):
        new_first = desugar_statement(first, env)
        new_rest = desugar_statement(rest, env)
        return Seq(s.location, new_first, new_rest)
      case Return(arg):
        new_arg = desugar_exp(arg, env)
        return Return(s.location, new_arg)
      case Pass():
        return Pass(s.location)
      case Write(lhs, rhs):
        new_lhs = desugar_exp(lhs, env)
        new_rhs = desugar_exp(rhs, env)
        return Write(s.location, new_lhs, new_rhs)
      case Transfer(lhs, percent, rhs):
        new_lhs = desugar_exp(lhs, env)
        new_percent = desugar_exp(percent, env)
        new_rhs = desugar_exp(rhs, env)
        return Transfer(s.location, new_lhs, new_percent, new_rhs)
      case Expr(arg):
        new_arg = desugar_exp(arg, env)
        return Expr(s.location, new_arg)
      case Assert(arg):
        new_arg = desugar_exp(arg, env)
        return Assert(s.location, new_arg)
      case Delete(arg):
        new_arg = desugar_exp(arg, env)
        return Delete(s.location, new_arg)
      case IfStmt(cond, thn, els):
        new_cond = desugar_exp(cond, env)
        new_thn = desugar_statement(thn, env)
        new_els = desugar_statement(els, env)
        return IfStmt(s.location, new_cond, new_thn, new_els)
      case While(cond, body):
        new_cond = desugar_exp(cond, env)
        new_body = desugar_statement(body, env)
        return While(s.location, new_cond, new_body)
      case Block(body):
        return Block(s.location, desugar_statement(body, env))
      case Match(cond, cases):
        new_cases = []
        for (tag, x, body) in cases:
          body_env = env.copy()
          body_env[x] = False
          new_cases += [(tag, x, desugar_statement(body, body_env))]
        return Match(s.location, desugar_exp(cond, env), new_cases)
      case _:
        error(s.location, 'error in desugar_statement, unhandled: ' + repr(s)) 

def declare_decl(decl, env):
    match decl:
      case Import(module, imports):
        for x in imports:
            env[x] = False
      case _:
        env[decl.name] = False
    
def desugar_decl(decl, env):
    match decl:
      case ConstantDef(name, type_annot, rhs):
        new_rhs = desugar_exp(rhs, env)
        return ConstantDef(decl.location, name, type_annot, new_rhs)
      case TypeAlias(name, type):
        return TypeAlias(decl.location, name, type)
      case TypeOperator(name, params, body):
        return TypeOperator(decl.location, name, params, body)
      case Global(name, ty, rhs):
        new_rhs = desugar_exp(rhs, env)
        return Global(decl.location, name, ty, new_rhs)
      case Function(name, ty_params, params, ret_ty, ret_mode, reqs, body):
        body_env = env.copy()
        for p in params:
            body_env[p.ident] = False
        new_body = desugar_statement(body, body_env)
        return Function(decl.location, name, ty_params, params, ret_ty,
                        ret_mode, reqs, new_body)
      case ModuleDef(name, exports, body):
        new_body = desugar_decls(body, env)
        return ModuleDef(decl.location, name, exports, new_body)
      case Import(module, imports):
        new_module = desugar_exp(module, env)
        return Import(decl.location, new_module, imports)
      case Interface(name, type_params, extends, members):
        return Interface(decl.location, name, type_params, extends, members)
      case Impl(name, iface_name, impl_types, assgn):
        return Impl(decl.location, name, iface_name, impl_types, assgn)
      case _:
        error(decl.location, "in desugar_decl, unhandled: " + str(decl))

def desugar_decls(decls, env):
    body_env = env.copy()
    for d in decls:
        declare_decl(d, body_env)
    return [desugar_decl(d, body_env) for d in decls]
        
    
