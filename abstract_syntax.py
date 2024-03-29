from dataclasses import dataclass
from typing import List, Set, Dict, Tuple, Any
from lark.tree import Meta
from fractions import Fraction
from utilities import *
from values import *
from memory import *
from ast_base import *
from ast_types import *
from coercions import *

    
# Expressions

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
      

@dataclass
class Int(Exp):
  value: int
  __match_args__ = ("value",)

  def __str__(self):
      return str(self.value)

  def __repr__(self):
      return str(self)

  def free_vars(self):
      return set()

  def const_eval(self, env):
      return self

  def step(self, runner, machine):
      runner.produce_value(Number(self.value), machine, self.location)

  def type_check(self, env, ctx):
    return IntType(self.location), self
    
    
@dataclass
class Frac(Exp):
  value: Fraction
  __match_args__ = ("value",)
  
  def __str__(self):
      return str(self.value)
  
  def __repr__(self):
      return str(self)
  
  def free_vars(self):
      return set()
  
  def const_eval(self, env):
      return self
  
  def type_check(self, env, ctx):
    return RationalType(self.location), self
      
  def step(self, runner,  machine):
      runner.produce_value(Number(self.value), machine, self.location)    

@dataclass
class Bool(Exp):
  value: bool
  __match_args__ = ("value",)
  
  def __str__(self):
    return str(self.value)
  
  def __repr__(self):
    return str(self)
  
  def free_vars(self):
    return set()
  
  def const_eval(self, env):
    return self

  def type_check(self, env, ctx):
    return BoolType(self.location), self
  
  def step(self, runner, machine):
      runner.produce_value(Boolean(self.value), machine, self.location)

      
@dataclass
class IfExp(Exp):
  cond: Exp
  thn: Exp
  els: Exp
  __match_args__ = ("cond", "thn", "els")
  
  def __str__(self):
      return "(" + str(self.cond) + "?" + str(self.thn) \
          + " : " + str(self.els) + ")"
    
  def __repr__(self):
      return str(self)
    
  def free_vars(self):
      return self.cond.free_vars() | self.thn.free_vars() \
          | self.els.free_vars()
    
  def const_eval(self, env):
    new_cond = self.cond.const_eval(env)
    new_thn = self.thn.const_eval(env)
    new_els = self.els.const_eval(env)
    return IfExp(self.location, new_cond, new_thn, new_els)
      
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.cond, runner.env)
    elif runner.state == 1:
      cond = runner.results[0].value
      if to_boolean(cond, self.location):
        machine.schedule(self.thn, runner.env, runner.context)
      else:
        machine.schedule(self.els, runner.env, runner.context)
    elif runner.state == 2:
      result = Result(runner.results[1].temporary,
                      runner.results[1].value.duplicate(1, self.location))
      machine.finish_expression(result, self.location)

  def type_check(self, env, ctx):
    cond_type, new_cond = self.cond.type_check(env, 'none')
    thn_type, new_thn = self.thn.type_check(env, ctx)
    els_type, new_els = self.els.type_check(env, ctx)
    if not consistent(cond_type, BoolType(self.location)):
      static_error(self.location, 'in conditional, expected a Boolean, not '
            + str(cond_type))
    if not consistent(thn_type, els_type):
      static_error(self.location,
                   'in conditional, branches must be consistent, not '
                   + str(cond_type))
    return join(thn_type, els_type), \
           IfExp(self.location, new_cond, new_thn, new_els)
    
    
# Statements
      
@dataclass
class Seq(Stmt):
  first: Stmt
  rest: Stmt
  __match_args__ = ("first", "rest")
  
  def __str__(self):
    if verbose():
      return str(self.first) + "\n" + str(self.rest)
    else:
      return "..."
  
  def __repr__(self):
    return str(self)

  def free_vars(self):
    return self.first.free_vars() | self.rest.free_vars()

  def const_eval(self, env):
    new_first = self.first.const_eval(env)
    new_rest = self.rest.const_eval(env)
    return Seq(self.location, new_first, new_rest)
  
  def type_check(self, env, ret):
    new_first = self.first.type_check(env, ret)
    new_rest = self.rest.type_check(env, ret)
    return Seq(self.location, new_first, new_rest)

  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.first, runner.env)
    elif not runner.return_value is None:
      machine.finish_statement(self.location)
    else:
      machine.finish_statement(self.location)
      machine.schedule(self.rest, runner.env, runner.context)
      
  def debug_skip(self):
      return True

    
@dataclass
class Write(Stmt):
  lhs: Exp
  rhs: Exp
  __match_args__ = ("lhs", "rhs")

  def __str__(self):
      return str(self.lhs) + " = " + str(self.rhs) + ";"

  def __repr__(self):
      return str(self)

  def free_vars(self):
      lhs_fvs = self.lhs.free_vars()
      rhs_fvs = self.rhs.free_vars()
      if tracing_on():
        print('free variables of write lhs: ' + str(lhs_fvs))
        print('free variables of write rhs: ' + str(rhs_fvs))
      return lhs_fvs | rhs_fvs

  def const_eval(self, env):
    new_lhs = self.lhs.const_eval(env)
    new_rhs = self.rhs.const_eval(env)
    return Write(self.location, new_lhs, new_rhs)
    
  def type_check(self, env, ret):
    lhs_type, new_lhs = self.lhs.type_check(env, 'write_lhs')
    rhs_type, new_rhs = self.rhs.type_check(env, 'write_rhs')
    require_consistent(lhs_type, rhs_type, 'in assignment', self.location)
    return Write(self.location, new_lhs, make_cast(new_rhs, rhs_type, lhs_type))
    
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.rhs, runner.env)
    elif runner.state == 1:
      machine.schedule(self.lhs, runner.env, AddressCtx())
    else:
      val_ptr = runner.results[0].value
      ptr = runner.results[1].value
      machine.memory.write(ptr, val_ptr, self.location)
      machine.finish_statement(self.location)

      
@dataclass
class Expr(Stmt):
  exp: Exp
  __match_args__ = ("exp",)

  def __str__(self):
      return str(self.exp) + ";"

  def __repr__(self):
    return str(self)

  def free_vars(self):
    return self.exp.free_vars()

  def const_eval(self, env):
    new_arg = self.exp.const_eval(env)
    return Expr(self.location, new_arg)
    
  def type_check(self, env, ret):
    _, new_exp = self.exp.type_check(env, 'none')
    return Expr(self.location, new_exp)

  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.exp, runner.env)
    else:
      machine.finish_statement(self.location)
    
      
@dataclass
class Assert(Stmt):
  exp: Exp
  __match_args__ = ("exp",)
  
  def __str__(self):
      return "assert " + str(self.exp) + ";"
    
  def __repr__(self):
      return str(self)
    
  def free_vars(self):
      return self.exp.free_vars()

  def const_eval(self, env):
    new_arg = self.exp.const_eval(env)
    return Assert(self.location, new_arg)
    
  def type_check(self, env, ret):
    arg_type, new_arg = self.exp.type_check(env, 'none')
    if not consistent(arg_type, BoolType(self.location)):
      static_error(self.location, "in assert, expected a Boolean, not "
                   + str(arg_type))
    return Assert(self.location, new_arg)
  
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.exp, runner.env)
    else:
      val = to_boolean(runner.results[0].value, self.location)
      if not val:
        error(self.location, "assertion failed: " + str(self.exp))
      machine.finish_statement(self.location)
      
@dataclass
class IfStmt(Stmt):
  cond: Exp
  thn: Stmt
  els: Stmt
  __match_args__ = ("cond", "thn", "els")
  
  def __str__(self):
    if verbose():
      return "if " + "(" + str(self.cond) + ") " + str(self.thn) \
          + " else " + str(self.els)
    else:
      return "if " + "(" + str(self.cond) + ") ..."
    
  def __repr__(self):
      return str(self)
    
  def free_vars(self):
      return self.cond.free_vars() | self.thn.free_vars() \
          | self.els.free_vars()

  def const_eval(self, env):
    new_cond = self.cond.const_eval(env)
    new_thn = self.thn.const_eval(env)
    new_els = self.els.const_eval(env)
    return IfStmt(self.location, new_cond, new_thn, new_els)
    
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.cond, runner.env)
    elif runner.state == 1:
      if to_boolean(runner.results[0].value, self.location):
        machine.schedule(self.thn, runner.env)
      else:
        machine.schedule(self.els, runner.env)
    else:
      machine.finish_statement(self.location)

  def type_check(self, env, ret):
    cond_type, new_cond = self.cond.type_check(env, 'none')
    if not consistent(cond_type, BoolType(self.location)):
      static_error(self.location, "in condition of if, expected a Boolean, not "
                   + str(cond_type))
    cast_cond = make_cast(new_cond, cond_type, BoolType(self.location))
    new_thn = self.thn.type_check(env, ret)
    new_els = self.els.type_check(env, ret)
    return IfStmt(self.location, cast_cond, new_thn, new_els)
    
      
@dataclass
class While(Stmt):
  cond: Exp
  body: Stmt
  __match_args__ = ("cond", "body")
  
  def __str__(self):
      return "while " + "(" + str(self.cond) + ")\n" + str(self.body)
    
  def __repr__(self):
      return str(self)
    
  def free_vars(self):
      return self.cond.free_vars() | self.body.free_vars()

  def const_eval(self, env):
    new_cond = self.cond.const_eval(env)
    new_body = self.body.const_eval(env)
    return While(self.location, new_cond, new_body)
    
  def type_check(self, env, ret):
    cond_type, new_cond = self.cond.type_check(env, 'none')
    if not consistent(cond_type, BoolType(self.location)):
      static_error(self.location, "in while, expected a Boolean, not "
                   + str(cond_type))
    new_body = self.body.type_check(env, ret)
    return While(self.location, new_cond, new_body)

  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.cond, runner.env)
    elif runner.state == 1 and runner.return_value == None:
      if to_boolean(runner.results[0].value, self.cond.location):
        machine.schedule(self, runner.env)
        machine.schedule(self.body, runner.env)
      else:
        machine.finish_statement(self.location)
    else:
      machine.finish_statement(self.location)
    
@dataclass
class Pass(Stmt):
  def __str__(self):
      return "pass"
    
  def __repr__(self):
      return str(self)
    
  def free_vars(self):
      return set()

  def const_eval(self, env):
    return self
  
  def type_check(self, env, ret):
    return self

  def step(self, runner, machine):
    machine.finish_statement(self.location)
    

@dataclass
class Block(Stmt):
  body: Stmt
  __match_args__ = ("body",)

  def __str__(self):
      return "{\n" + str(self.body) + "\n}"

  def __repr__(self):
      return str(self)

  def free_vars(self):
      return self.body.free_vars()

  def const_eval(self, env):
    return Block(self.location, self.body.const_eval(env))
    
  def type_check(self, env, ret):
    new_body = self.body.type_check(env, ret)
    return Block(self.location, new_body)
    
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.body, runner.env,
                       runner.context) # experimental -Jeremy
    else:
      machine.finish_statement(self.location)

  def debug_skip(self):
    return True
        
# Declarations
    
@dataclass
class Global(Decl):
  name: str
  type_annot: Type
  rhs: Exp
  __match_args__ = ("name", "type_annot", "rhs")
  def __str__(self):
    return "var " + str(self.name) + " : " + str(self.type_annot) \
        + " = " + str(self.rhs) + ";"

  def __repr__(self):
    return str(self)

  def free_vars(self):
    return init.free_vars()

  def local_vars(self):
    return set([var.ident])

  def const_eval(self, env):
    new_rhs = self.rhs.const_eval(env)
    new_ty = simplify(self.type_annot, env)
    return [Global(self.location, self.name, new_ty, new_rhs)]
  
  def declare_type(self, env):
    return {self.name: StaticVarInfo(self.type_annot, None, ProperFraction())}

  def type_check(self, env):
    rhs_type, new_rhs = self.rhs.type_check(env, 'var')
    type_annot = self.type_annot
    if not consistent(rhs_type, type_annot):
      static_error(self.location, 'type of initializer ' + str(rhs_type) + '\n'
                   + ' is inconsistent with declared type ' + str(type_annot))
    return [Global(self.location, self.name, type_annot, new_rhs)]
    
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.rhs, runner.env)
    else:
      machine.memory.write(runner.env[self.name], runner.results[0].value,
                           self.location)
      machine.finish_definition(self.location)

@dataclass
class ConstantDef(Exp):
  name: str
  type_annot: Type
  rhs: Exp
  __match_args__ = ("name", "type_annot", "rhs")
  
  def __str__(self):
    return "const " + str(self.name) + " : " + str(self.type_annot) \
        + " = " + str(self.rhs) + ";"

  def __repr__(self):
    return str(self)

  def free_vars(self):
    return init.free_vars()

  def const_eval(self, env):
    new_ty = simplify(self.type_annot, env)
    new_rhs = self.rhs.const_eval(env)
    if is_constant(new_rhs):
      env[self.name] = new_rhs
    else:
      error(self.location, 'right-hand side must be a constant, not '
            + str(rhs))
    return []
    
  def local_vars(self):
    return set([var.ident])

@dataclass
class TypeAlias(Decl):
  name: str
  type: Type
  __match_args__ = ("name", "type")
  
  def __str__(self):
    return "type " + str(self.name) + " = " + str(self.type) + ";"
  
  def __repr__(self):
    return str(self)

  def const_eval(self, env):
    env[self.name] = simplify(self.type, env)
    return []
    
@dataclass
class TypeOperator(Decl):
  name: str
  params: list[str]
  body: Type
  __match_args__ = ("name", "params", "body")
  
  def __str__(self):
    return "typeop " + str(self.name) + "(" + ', '.join(self.params) + ")" \
      + " = " + str(self.body) + ";"
  
  def __repr__(self):
    return str(self)

  def const_eval(self, env):
    body_env = env.copy()
    for t in self.params:
      body_env[t] = TypeVar(self.location, t)
    new_body = simplify(self.body, body_env)
    env[self.name] = TypeOp(self.location, self.params, new_body)
    return []
    
@dataclass
class ApplyCoercion(Exp):
  exp: Exp
  coercion: Coercion

  __match_args__ = ("exp", "coercion")

  def __str__(self):
    return "⟨" + str(self.coercion) + "⟩" + str(self.exp)

  def __repr__(self):
    return str(self)
  
  def free_vars(self):
    return self.exp.free_vars()

  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.exp, runner.env, ValueCtx())
    else:
      val = self.coercion.apply(runner.results[0].value)
      runner.produce_value(val.duplicate(1, self.location),
                           machine, self.location)

def make_cast(exp: Exp, source: Type, target: Type):
    if source == target:
        return exp
    else:
        return ApplyCoercion(exp.location, exp,
                             make_coercion(source, target, exp.location))
