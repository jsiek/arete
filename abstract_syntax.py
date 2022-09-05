from dataclasses import dataclass
from typing import List, Set, Dict, Tuple, Any
from lark.tree import Meta
from fractions import Fraction
from utilities import *
from values import *
from memory import *
from primitive_operations import eval_prim, compare_ops, type_check_prim
from ast_base import *
from ast_types import *

# Parameters

@dataclass(frozen=True)
class Param:
    location: Meta
    kind: str # let, var, inout, sink, set
    privilege: str # read, write # OBSOLETE?
    ident: str
    type_annot: Type
    __match_args__ = ("privilege", "ident")
    
    def __str__(self):
        if self.kind is None:
          return self.privilege + ' ' + self.ident + ': ' + str(self.type_annot)
        else:
          return self.kind + ' ' + self.ident + ': ' + str(self.type_annot)
      
    def __repr__(self):
        return str(self)

    def type_check(self, env):
      type_annot = simplify(self.type_annot, env)
      return Param(self.location, self.kind, self.privilege,
                   self.ident, type_annot)
        

@dataclass(frozen=True)
class NoParam:
    location: Meta
    
# Expressions


@dataclass
class PrimitiveCall(Exp):
  op: str
  args: List[Exp]
  __match_args__ = ("op", "args")

  def __str__(self):
      return self.op + \
          "(" + ", ".join([str(arg) for arg in self.args]) + ")"

  def __repr__(self):
      return str(self)

  def free_vars(self):
      return set().union(*[arg.free_vars() for arg in self.args])

  def step(self, runner, machine):
    if runner.state < len(self.args):
      if self.op in set(['upgrade', 'permission']):
        dup = False
      else:
        dup = True
      machine.schedule(self.args[runner.state], runner.env,
                       ValueCtx(dup))
    else:
      result = eval_prim(self.op, [res.value for res in runner.results],
                         machine, self.location)
      if isinstance(runner.context, AddressCtx):
        # join produces an address, no need to allocate
        if self.op != 'join':
          result = machine.memory.allocate(result)
      machine.finish_expression(Result(True, result), self.location)

  def type_check(self, env):
    if tracing_on():
      print("starting to type checking " + str(self))
    arg_types = []
    new_args = []
    for arg in self.args:
        arg_type, new_arg = arg.type_check(env)
        arg_types.append(arg_type)
        new_args.append(new_arg)
    if tracing_on():
      print("checking primitive " + str(self.op))
    ret = type_check_prim(self.location, self.op, arg_types)
    if tracing_on():
      print("finished type checking " + str(self))
      print("type: " + str(ret))
    return ret, PrimitiveCall(self.location, self.op, new_args)

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

  def step(self, runner, machine):
      val = Number(self.value)
      if isinstance(runner.context, ValueCtx):
          result = val
      elif isinstance(runner.context, AddressCtx):
          result = machine.memory.allocate(val)
      machine.finish_expression(Result(True, result), self.location)

  def type_check(self, env):
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
  def step(self, runner,  machine):
      val = Number(self.value)
      if isinstance(runner.context, ValueCtx):
          result = val
      elif isinstance(runner.context, AddressCtx):
          result = machine.memory.allocate(val)
      # if not runner.context.duplicate:
      #   error(self.location, 'fraction not allowed in this context')
      machine.finish_expression(Result(True, result), self.location)

  def type_check(self, env):
    return RationalType(self.location), self
      
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
  def step(self, runner, machine):
      val = Boolean(self.value)
      if isinstance(runner.context, ValueCtx):
          result = val
      elif isinstance(runner.context, AddressCtx):
          result = machine.memory.allocate(val)
      # if not runner.context.duplicate:
      #   error(self.location, 'Boolean not allowed in this context')
      machine.finish_expression(Result(True, result), self.location)

  def type_check(self, env):
    return BoolType(self.location), self
      

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

  def type_check(self, env):
    cond_type, new_cond = self.cond.type_check(env)
    thn_type, new_thn = self.thn.type_check(env)
    els_type, new_els = self.els.type_check(env)
    if not (isinstance(cond_type, BoolType)
            or isinstance(cond_type, AnyType)):
      error(self.location, 'in conditional, expected a Boolean, not '
            + str(cond_type))
    if not consistent(thn_type, els_type):
      error(self.location, 'in conditional, branches must be consistent, not '
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

  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.first, runner.env)
    elif not runner.return_value is None:
      machine.finish_statement(self.location)
    else:
      machine.finish_statement(self.location)
      machine.schedule(self.rest, runner.env)
      
  def debug_skip(self):
      return True

  def type_check(self, env):
    first_type, new_first = self.first.type_check(env)
    rest_type, new_rest = self.rest.type_check(env)
    return join(first_type, rest_type), \
           Seq(self.location, new_first, new_rest)
    
    
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

  def type_check(self, env):
    lhs_type, new_lhs = self.lhs.type_check(env)
    rhs_type, new_rhs = self.rhs.type_check(env)
    require_consistent(lhs_type, rhs_type, 'in assignment', self.location)
    return None, Write(self.location, new_lhs, new_rhs)
    
      
@dataclass
class Expr(Stmt):
  exp: Exp
  __match_args__ = ("exp",)

  def __str__(self):
      return "! " + str(self.exp) + ";"

  def __repr__(self):
      return str(self)

  def free_vars(self):
      return self.exp.free_vars()

  def type_check(self, env):
    _, new_exp = self.exp.type_check(env)
    return None, Expr(self.location, new_exp)

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
    
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.exp, runner.env)
    else:
      val = to_boolean(runner.results[0].value, self.location)
      if not val:
        error(self.location, "assertion failed: " + str(self.exp))
      machine.finish_statement(self.location)

  def type_check(self, env):
    arg_type, new_arg = self.exp.type_check(env)
    if not isinstance(arg_type, BoolType):
      error(self.location, "in assert, expected a Boolean, not "
            + str(arg_type))
    return None, Assert(self.location, new_arg)
    
      
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

  def type_check(self, env):
    cond_type, new_cond = self.cond.type_check(env)
    thn_type, new_thn = self.thn.type_check(env)
    els_type, new_els = self.els.type_check(env)
    return join(thn_type, els_type), \
           IfStmt(self.location, new_cond, new_thn, new_els)
    
      
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
    
  def type_check(self, env):
    cond_type, new_cond = self.cond.type_check(env)
    body_type, new_body = self.body.type_check(env)
    return body_type, \
           While(self.location, new_cond, new_body)

  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.cond, runner.env)
    elif runner.state == 1:
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
    
  def type_check(self, env):
    return None, self

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

  def type_check(self, env):
    body_type, new_body = self.body.type_check(env)
    return body_type, Block(self.location, new_body)
    
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.body, runner.env)
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

  def declare_type(self, env, output):
    env[self.name] = simplify(self.type_annot, env)
    output[self.name] = env[self.name]

  def type_check(self, env):
    rhs_type, new_rhs = self.rhs.type_check(env)
    type_annot = simplify(self.type_annot, env)
    if not consistent(rhs_type, type_annot):
      error(self.location, 'type of initializer ' + str(rhs_type) + '\n'
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
  
  def step(self, runner, machine):
    machine.finish_definition(self.location)

  def declare_type(self, env, output):
    env[self.name] = simplify(self.type, env)

  def type_check(self, env):
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

  def step(self, runner, machine):
    machine.finish_definition(self.location)

  def declare_type(self, env, output):
    env[self.name] = TypeOp(self.location, self.params, self.body)

  def type_check(self, env):
    return []
  
