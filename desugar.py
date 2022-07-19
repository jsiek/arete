from abstract_syntax import *
from utilities import *

def desugar_init(init, env):
    match init:
      case Initializer(loc, percent, arg):
        if percent == 'default':
            new_percent = 'default'
        else:
            new_percent = desugar_exp(percent, env)
        new_arg = desugar_exp(arg, env)
        return Initializer(loc, new_percent, new_arg)
      case _:
        error(init.location, 'in desugar_init, expected an initializer, not '
              + repr(init))

def desugar_exp(e, env):
    match e:
      case Var(x):
        if x not in env:
            error(e.location, 'use of undefined variable ' + x)
        if env[x]:
            return Index(e.location, e, Int(0))
        else:
            return e
      case Int(n):
        return e
      case Frac(f):
        return e
      case Bool(b):
        return e
      case Prim(op, args):
        new_args = [desugar_exp(arg, env) for arg in args]
        return Prim(e.location, op, new_args)
      case Member(arg, field):
        new_arg = desugar_exp(arg, env)
        return Member(e.location, new_arg, field)
      case New(inits):
        new_inits = [desugar_init(init, env) for init in inits]
        return New(e.location, new_inits)
      case Array(size, arg):
        new_size = desugar_exp(size, env)
        new_arg = desugar_exp(arg, env)
        return Array(e.location, new_size, new_arg)
      case Lambda(params, body):
        body_env = env.copy()
        for p in params:
            body_env[p.ident] = False
        new_body = desugar_stmt(body, body_env)
        return Lambda(e.location, params, new_body)
      case Call(fun, inits):
        new_fun = desugar_exp(fun, env)
        new_inits = [desugar_init(init, env) for init in inits]
        return Call(e.location, new_fun, new_inits)
      case Index(arg, index):
        new_arg = desugar_exp(arg, env)
        new_index = desugar_exp(index, env)
        return Index(e.location, new_arg, new_index)
      case IfExp(cond, thn, els):
        new_cond = desugar_exp(cond, env)
        new_thn = desugar_exp(thn, env)
        new_els = desugar_exp(els, env)
        return IfExp(e.location, new_cond, new_thn, new_els)
      case Let(var, init, body):
        new_init = desugar_init(init, env)
        body_env = env.copy()
        body_env[var.ident] = False
        new_body = desugar_exp(body, body_env)
        return Let(e.location, var, new_init, new_body)
      case FutureExp(arg):
        new_arg = desugar_exp(arg, env)
        return FutureExp(e.location, new_arg)
      case Await(arg):
        new_arg = desugar_exp(arg, env)
        return Await(e.location, new_arg)
      case _:
        error(e.location, 'error in desugar_exp, unhandled: ' + repr(e)) 
    
def desugar_stmt(s, env):
    match s:
      case LetInit(var, init, body):
        new_init = desugar_init(init, env)
        body_env = env.copy()
        body_env[var.ident] = False
        new_body = desugar_stmt(body, body_env)
        return LetInit(s.location, var, new_init, new_body)
      case VarInit(var, rhs, body):
        #  var x = e in b[x]
        #  =>
        #  let !x = new e in b[*x]
        new_init = desugar_init(init, env, var.kind)
        body_env = env.copy()
        body_env[var] = True
        new_body = desugar_stmt(body, body_env)
        return LetInit(s.location, Param(s.location, var, 'write'),
                       new_rhs, new_body)
      case Seq(first, rest):
        new_first = desugar_stmt(first, env)
        new_rest = desugar_stmt(rest, env)
        return Seq(s.location, new_first, new_rest)
      case Return(arg):
        new_arg = desugar_exp(arg, env)
        return Return(s.location, new_arg)
      case Pass():
        return Pass(s.location)
      case Write(lhs, rhs):
        new_lhs = desugar_exp(lhs, env)
        new_rhs = desugar_init(rhs, env)
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
        new_thn = desugar_stmt(thn, env)
        new_els = desugar_stmt(els, env)
        return IfStmt(s.location, new_cond, new_thn, new_els)
      case While(cond, body):
        new_cond = desugar_exp(cond, env)
        new_body = desugar_stmt(body, env)
        return While(s.location, new_cond, new_body)
      case Block(body):
        return Block(s.location, desugar_stmt(body, env))
      case _:
        raise Exception('error in desugar_stmt, unhandled: ' + repr(s)) 

def declare_decl(decl, env):
    match decl:
      case Import(module, imports):
        for x in imports:
            env[x] = False
      case _:
        env[decl.name] = False
    
def desugar_decl(decl, env):
    match decl:
      case Global(name, rhs):
        new_rhs = desugar_exp(rhs, env)
        return Global(decl.location, name, new_rhs)
      case Function(name, params, body):
        body_env = env.copy()
        for p in params:
            body_env[p.ident] = False
        new_body = desugar_stmt(body, body_env)
        return Function(decl.location, name, params, new_body)
      case ModuleDecl(name, exports, body):
        new_body = desugar_decls(body, env)
        return ModuleDecl(decl.location, name, exports, new_body)
      case Import(module, imports):
        new_module = desugar_exp(module, env)
        return Import(decl.location, new_module, imports)

def desugar_decls(decls, env):
    body_env = env.copy()
    for d in decls:
        declare_decl(d, body_env)
    return [desugar_decl(d, body_env) for d in decls]
        
    
