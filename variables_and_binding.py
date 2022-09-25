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
from ast_base import *
from ast_types import *
from values import *
from utilities import *

# Parameters

@dataclass(frozen=True)
class Param:
    location: Meta
    kind: str # let, var, inout, sink, set
    privilege: str # read, write # OBSOLETE?
    ident: str
    type_annot: Type
    __match_args__ = ("privilege", "ident")

    # Return a Param that's the same except for the type annotation.
    def with_type(self, ty):
        return Param(self.location, self.kind, self.privilege, self.ident, ty)

    def const_eval(self, env):
      type_annot = simplify(self.type_annot, env)
      return Param(self.location, self.kind, self.privilege,
                   self.ident, type_annot)

    def bind_type(self, env):
      if self.kind == 'let':
        state = ProperFraction()
      elif self.kind == 'inout' or self.kind == 'var':
        state = FullFraction()
      elif self.kind == 'ref':
        state = ProperFraction()
      env[self.ident] = StaticVarInfo(self.type_annot, None, state, self)
  
    # At runtime, bind the result to this parameter/variable
    def bind(self, res : Result, env, memory, loc):
      val = res.value
      if not (isinstance(val, Pointer) or isinstance(val, PointerOffset)):
        error(loc, 'for binding, expected a pointer, not ' + str(val))
      if tracing_on():
          print('for call, binding ' + self.ident + ' to ' + str(val))
      if res.temporary:
        # what if val is a PointerOffset??
        if self.kind == 'let':
          env[self.ident] = val.duplicate(Fraction(1,2), loc)
        else:
          env[self.ident] = val

      if self.kind == 'let':
        if (not val.get_address() is None) \
             and val.get_permission() == Fraction(0,1):
          error(loc, 'let binding requires non-zero permission, not '
                + str(val))
        if not res.temporary:      
          env[self.ident] = val.duplicate(Fraction(1,2), loc)
        env[self.ident].kill_when_zero = True

      elif self.kind == 'var' or self.kind == 'inout':
        success = val.upgrade(loc)
        if not success:
          error(self.location,
                self.kind + ' binding requires permission 1/1, not ' + str(val))
        if not res.temporary:
          env[self.ident] = val.duplicate(Fraction(1,1), loc)
          if self.kind == 'var':
            val.kill(memory, loc)
        if self.kind == 'var':
            env[self.ident].no_give_backs = True

      # The `ref` kind is not in Val. It doesn't guarantee any
      # read/write ability and it does not guarantee others
      # won't mutate. Unlike `var`, it does not consume the
      # initializing value. I'm not entirely sure if `ref`
      # is needed, but it has come in handy a few times.
      elif self.kind == 'ref':
        if not res.temporary:
          env[self.ident] = val.duplicate(Fraction(1,1), loc)

      else:
        error(loc, 'unrecognized kind of parameter: ' + self.kind)
    
    def __str__(self):
        if self.kind is None:
          return self.privilege + ' ' + self.ident + ': ' + str(self.type_annot)
        else:
          return self.kind + ' ' + self.ident + ': ' + str(self.type_annot)
      
    def __repr__(self):
        return str(self)


@dataclass(frozen=True)
class NoParam:
  location: Meta
  
  def bind(self, res : Result, env, mem, loc):
    return

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
    info = env[self.ident]
    if not hasattr(info, 'state'):
      print('bad type env info: ' + str(info))
      exit(-1)
    if not static_readable(info.state):
      warning(self.location, "don't have read permission for " + self.ident
              + ", only " + str(info.state))
    if info.translation is None:
      return info.type, self
    else:
      return info.type, info.translation
  
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
    self.param.bind_type(body_env)
    body_type, new_body = self.body.type_check(body_env)
    return body_type, BindingExp(self.location, self.param, new_arg, new_body)
  
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.arg, runner.env, AddressCtx())
    elif runner.state == 1:
      runner.body_env = runner.env.copy()
      self.param.bind(runner.results[0], runner.body_env, machine.memory,
                      self.arg.location)
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
    self.param.bind_type(body_env)
    body_type, new_body = self.body.type_check(body_env)
    return body_type, BindingStmt(self.location, self.param, new_arg, new_body)
    
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.arg, runner.env, AddressCtx())
    elif runner.state == 1:
      runner.body_env = runner.env.copy()
      self.param.bind(runner.results[0], runner.body_env, machine.memory,
                      self.arg.location)
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

