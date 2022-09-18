#
# This file defines the language features related to variables in Arete,
# which includes
# * variable (occurences)
# * binding expressions
# * binding statements
#
# Of course, function parameters are also related to variables, but
# functions are defined in `functions.py`.

from dataclasses import dataclass
from abstract_syntax import Param
from ast_base import *
from ast_types import *
from values import *
from utilities import *

@dataclass
class Var(Exp):
  ident: str
  __match_args__ = ("ident",)

  def __str__(self):
      return self.ident

  def __repr__(self):
      return str(self)

  def free_vars(self):
      return set([self.ident])

  def const_eval(self, env):
    if self.ident in env:
      return env[self.ident]
    else:
      return self
    
  def type_check(self, env):
    if self.ident not in env:
        error(self.location, 'use of undefined variable ' + self.ident)
    (ty, exp) = env[self.ident]
    if exp is None:
      return ty, self
    else:
      return ty, exp
  
  def step(self, runner, machine):
      if self.ident not in runner.env:
          error(self.location, 'use of undefined variable ' + self.ident)
      ptr = runner.env[self.ident]
      if isinstance(runner.context, ValueCtx):
        val = machine.memory.read(ptr, self.location)
        if runner.context.duplicate:
          val = val.duplicate(ptr.get_permission(), self.location)
        result = Result(runner.context.duplicate, val)
      elif isinstance(runner.context, AddressCtx):
        result = Result(False, ptr)
      machine.finish_expression(result, self.location)


#
# aka. let-expressions in functional languages
#
@dataclass
class BindingExp(Exp):
  param: Param
  arg: Exp
  body: Exp
  __match_args__ = ("param", "arg", "body")

  def __str__(self):
    if verbose():
      return str(self.param) + " = " + str(self.arg) + ";\n" \
          + str(self.body)
    else:
      return str(self.param) + " = " + str(self.arg) + "; ..."

  def __repr__(self):
      return str(self)

  def free_vars(self):
      return self.arg.free_vars() \
          | (self.body.free_vars() - set([self.param.ident]))

  def const_eval(self, env):
    param = self.param
    rhs = self.arg
    body = self.body
    new_param = param.with_type(simplify(param.type_annot, env))
    new_rhs = rhs.const_eval( env)
    body_env = env.copy()
    if new_param.ident in body_env.keys():
      del body_env[new_param.ident]
    new_body = body.const_eval(body_env)
    return BindingExp(self.location, new_param, new_rhs, new_body)
    
  def type_check(self, env):
    rhs_type, new_arg = self.arg.type_check(env)
    if not consistent(rhs_type, self.param.type_annot):
      error(self.arg.location, 'type of initializer ' + str(rhs_type) + '\n'
            + ' is inconsistent with declared type ' + str(self.param.type_annot))
    body_env = copy_type_env(env)
    body_env[self.param.ident] = (rhs_type, None)
    body_type, new_body = self.body.type_check(body_env)
    return body_type, BindingExp(self.location, self.param, new_arg, new_body)
  
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.arg, runner.env, AddressCtx())
    elif runner.state == 1:
      runner.body_env = runner.env.copy()
      machine.bind_param(self.param, runner.results[0],
                         runner.body_env, self.arg.location)
      machine.schedule(self.body, runner.body_env, runner.context)
    else:
      machine.dealloc_param(self.param, runner.results[0],
                            runner.body_env, self.location)
      result = duplicate_if_temporary(runner.results[1], self.location)
      machine.finish_expression(result, self.location)


  
# This is meant to have the same semantics as the `let`, `var`, and
# `inout` statement in Val.
@dataclass
class BindingStmt(Exp):
  param: Param
  arg: Exp
  body: Stmt
  __match_args__ = ("param", "arg", "body")
  
  def __str__(self):
    if verbose():
      return str(self.param) + " = " + str(self.arg) + ";\n" \
          + str(self.body)
    else:
      return str(self.param) + " = " + str(self.arg) + "; ..."
    
  def __repr__(self):
      return str(self)
    
  def free_vars(self):
      return self.arg.free_vars() \
          | (self.body.free_vars() - set([self.param.ident]))

  def const_eval(self, env):
    param = self.param
    rhs = self.arg
    body = self.body
    new_param = param.with_type(simplify(param.type_annot, env))
    new_rhs = rhs.const_eval( env)
    body_env = env.copy()
    if new_param.ident in body_env.keys():
      del body_env[new_param.ident]
    new_body = body.const_eval(body_env)
    return BindingStmt(self.location, new_param, new_rhs, new_body)
    
  def type_check(self, env):
    arg_type, new_arg = self.arg.type_check(env)
    if not consistent(arg_type, self.param.type_annot):
      error(self.arg.location, 'type of initializer ' + str(arg_type) + '\n'
            + ' is inconsistent with declared type '
            + str(new_param.type_annot))
    body_env = env.copy()
    body_env[self.param.ident] = (self.param.type_annot, None)
    body_type, new_body = self.body.type_check(body_env)
    return body_type, BindingStmt(self.location, self.param, new_arg, new_body)
    
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.arg, runner.env, AddressCtx())
    elif runner.state == 1:
      runner.body_env = runner.env.copy()
      machine.bind_param(self.param, runner.results[0],
                         runner.body_env, self.arg.location)
      # Treat binding statements special for debugging. 
      # Pretend they finish before the body runs.
      if runner.pause_on_finish:
          machine.pause = True
          runner.pause_on_finish = False
      machine.schedule(self.body, runner.body_env)
    else:
      machine.dealloc_param(self.param, runner.results[0],
                            runner.body_env, self.location)
      machine.finish_statement(self.location)

