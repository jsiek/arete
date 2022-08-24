#
# This file defines the language features related to functions in Arete,
# which includes
# * function values (closures),
# * module-level function definitions,
# * function calls,
# * return statements, and
# * lambda expressions.
#

from dataclasses import dataclass
from abstract_syntax import Param
from ast_base import *
from ast_types import *
from values import Result, Pointer
from utilities import *

@dataclass
class Closure(Value):
    name: str
    params: list[Any]
    return_mode: str    # 'value' or 'address'
    body: Stmt
    env: dict[str,Pointer]
    __match_args__ = ("name", "params", "return_mode", "body", "env")
    
    def duplicate(self, percentage, loc):
      if tracing_on():
        print('duplicating closure ' + str(self))
      env_copy = {x: v.duplicate(Fraction(1,2), loc) for x,v in self.env.items()}
      return Closure(self.name, self.params, self.return_mode, self.body,
                       env_copy)
    
    def kill(self, mem, location, progress=set()):
      if tracing_on():
        print('kill closure ' + str(self))
      for x, ptr in self.env.items():
        ptr.kill(mem, location, progress)
        
    def clear(self, mem, location, progress=set()):
      for x, ptr in self.env.items():
        ptr.kill(mem, location, progress)
      
    def __str__(self):
        if verbose():
            return '<' + self.name + '>' + '(' + ', '.join([str(ptr) for x, ptr in self.env.items()]) + ')'
        else:
            return '<' + self.name + '>'
      
    def __repr__(self):
        return str(self)

    def node_name(self):
        return str(self.name)
      
    def node_label(self):
        return 'fun ' + str(self.name) + '(' + ', '.join([ptr.node_label() for x, ptr in self.env.items()]) + ')'
    

@dataclass
class Function(Decl):
  name: str
  type_params: list[str]
  params: list[Param]
  return_type: Type
  return_mode: str    # 'value' or 'address'
  body: Exp
  __match_args__ = ("name", "type_params", "params", "return_type",
                    "return_mode", "body")
  
  def __str__(self):
      return "function " + self.name \
          + ("<" + ", ".join(self.type_params) + ">" \
             if len(self.type_params) > 0 \
             else "") \
          + "(" + ", ".join([str(p) for p in self.params]) + ")" \
          + " -> " + str(self.return_type) \
          + " " + str(self.body)
    
  def __repr__(self):
      return str(self)
    
  def free_vars(self):
      return body.free_vars() - set([p.ident for p in self.params])
    
  def step(self, runner, machine):
    if runner.state == 0:
      lam = Lambda(self.location, self.params, self.return_mode, self.body,
                   self.name)
      machine.schedule(lam, runner.env)
    else:
      machine.memory.unchecked_write(runner.env[self.name],
                                     runner.results[0].value,
                                     self.location)
      machine.finish_definition(self.location)

  def declare_type(self, env, output):
    ty = FunctionType(self.location,
                      self.type_params,
                      tuple(p.type_annot for p in self.params),
                      self.return_type)
    env[self.name] = simplify(ty, env)
    output[self.name] = env[self.name]
    
  def type_check(self, env):
    body_env = env.copy()
    for t in self.type_params:
      body_env[t] = TypeVar(self.location, t)
    ret_ty = simplify(self.return_type, body_env)
    for p in self.params:
        body_env[p.ident] = simplify(p.type_annot, body_env)
    body_type = self.body.type_check(body_env)
    if not consistent(body_type, ret_ty):
      error(decl.location, 'return type mismatch:\n' + str(ret_ty)
            + ' inconsistent with ' + str(body_type))
    
@dataclass
class Call(Exp):
  fun: Exp
  args: list[Exp]
  
  __match_args__ = ("fun", "args")
  
  def __str__(self):
      return str(self.fun) \
          + "(" + ", ".join([str(arg) for arg in self.args]) + ")"
  
  def __repr__(self):
      return str(self)
  
  def free_vars(self):
      return self.fun.free_vars() \
          | set().union(*[arg.free_vars() for arg in self.args])
  
  def set_closure(self, runner, machine):
      if runner.clos is None:
        runner.clos = runner.results[0].value
        if not isinstance(runner.clos, Closure):
          error(self.location, 'expected function in call, not '
                + str(runner.clos))
          
  def step(self, runner, machine):
    if runner.state == 0:
      # evaluate the operator subexpression
      machine.schedule(self.fun, runner.env,
                       ValueCtx(runner.context.duplicate))
      runner.clos = None
    elif runner.state <= len(self.args):
      self.set_closure(runner, machine)
      # evaluate the operand subexpressions
      machine.schedule(self.args[runner.state - 1], runner.env, AddressCtx())
    elif runner.state == len(self.args) + 1:
      self.set_closure(runner, machine)
      # call the function
      match runner.clos:
        case Closure(name, params, ret_mode, body, clos_env):
          runner.params = params
          runner.body_env = clos_env.copy()
          runner.args = [res for res in runner.results[1:]]
          if len(params) != len(runner.args):
            error(self.location, 'wrong number of arguments, expected '
                  + str(len(params)) + ' not ' + str(len(runner.args)))
          for param, arg in zip(params, runner.args):
            machine.bind_param(param, arg, runner.body_env, self.location)
          machine.push_frame()
          if machine.current_thread.pause_on_call:
              machine.pause = True
              machine.current_thread.pause_on_call = False
          machine.schedule(body, runner.body_env, return_mode=ret_mode)
          if debug_mode() == 'n':
              if machine.pause:
                  machine.pause = False
                  runner.pause_on_finish = True
        case _:
          error(self.location, 'expected function in call, not '
                + str(runner.clos))
    else:
      # return from the function
      for (param, arg) in zip(runner.params, runner.args):
        machine.dealloc_param(param, arg, runner.body_env, runner.clos.body.location)
      if runner.return_value is None:
        runner.return_value = Void()
      if isinstance(runner.context, ValueCtx):
        if runner.clos.return_mode == 'value':
          result = runner.return_value
        elif runner.clos.return_mode == 'address':
          val = machine.memory.read(runner.return_value, self.location)
          result = val.duplicate(runner.return_value.get_permission(),
                                 self.location)
          runner.return_value.kill(machine.memory, self.location)
        else:
          raise Exception('unrecognized return_mode: '
                          + runner.clos.return_mode)
      elif isinstance(runner.context, AddressCtx):
        if runner.clos.return_mode == 'value':
          result = machine.memory.allocate(runner.return_value)
        elif runner.clos.return_mode == 'address':
          result = runner.return_value
        else:
          raise Exception('unrecognized return_mode: '
                          + runner.clos.return_mode)
      else:
        error(self.location, 'unknown context ' + repr(runner.context))
      machine.finish_expression(Result(True, result), self.location)

  def type_check(self, env):
    fun_type = self.fun.type_check(env)
    arg_types = [arg.type_check(env) for arg in self.args]
    fun_type = unfold(fun_type)
    if tracing_on():
      print('call to function of type ' + str(fun_type))
    if isinstance(fun_type, FunctionType):
      fun_env = env.copy()
      for t in fun_type.type_params:
        fun_env[t] = TypeVar(self.location, t)
      # perform type argument deduction
      matches = {}
      for (param_ty, arg_ty) in zip(fun_type.param_types, arg_types):
          pt = simplify(param_ty, fun_env)
          if not match_types(fun_type.type_params, pt, arg_ty, matches,
                             set()):
              error(self.location, 'in call, '
                    + str(self) + '\n'
                    + 'argument type:\n\t' + str(arg_ty)
                    + '\ndoes not match parameter type:\n\t' + str(param_ty))
      if tracing_on():
        print('deduced: ' + str(matches))
      rt = simplify(fun_type.return_type, fun_env)
      return substitute(matches, rt)
    elif isinstance(fun_type, AnyType):
      return AnyType(self.location)
    else:
      error(self.location, "in call, expected a function, not "
            + str(fun_type))
    
@dataclass
class Return(Stmt):
  arg: Exp
  __match_args__ = ("arg",)
  def __str__(self):
      return "return " + str(self.arg) + ";"
  def __repr__(self):
      return str(self)
  def free_vars(self):
      return self.arg.free_vars()
  def step(self, runner, machine):
    if runner.state == 0:
      if runner.return_mode == 'value':
        context = ValueCtx()
      elif runner.return_mode == 'address':
        context = AddressCtx()
      machine.schedule(self.arg, runner.env, context)
    else:
      runner.return_value = \
        runner.results[0].value.duplicate(1, self.location)
      machine.finish_statement(self.location)

  def type_check(self, env):
    return self.arg.type_check(env)

@dataclass
class Lambda(Exp):
  params: list[Param]
  return_mode: str    # 'value' or 'address'
  body: Stmt
  name: str = "lambda"
  __match_args__ = ("params", "return_mode", "body", "name")

  def __str__(self):
      return "function " \
          + "(" + ", ".join([str(p) for p in self.params]) + ")" \
          + " { " + str(self.body) + " }"

  def __repr__(self):
      return str(self)

  def free_vars(self):
      return self.body.free_vars() - set([p.ident for p in self.params])

  def step(self, runner, machine):
      clos_env = {}
      free = self.body.free_vars() - set([p.ident for p in self.params])
      for x in free:
          if not x in runner.env.keys():
            error(self.location, 'in closure, undefined variable ' + x)
          v = runner.env[x]
          clos_env[x] = v.duplicate(Fraction(1,2), self.location)            
      clos = Closure(self.name, self.params, self.return_mode, self.body,
                     clos_env)
      if isinstance(runner.context, ValueCtx):
          result = clos
      elif isinstance(runner.context, AddressCtx):
          result = machine.memory.allocate(clos)
      else:
          error(self.location, 'function not allowed in this context')
      machine.finish_expression(Result(True, result), self.location)

  def type_check(self, env):
    body_env = env.copy()
    for p in self.params:
        body_env[p.ident] = p.type_annot
    ret_type = self.body.type_check(body_env)
    return FunctionType(self.location,
                        tuple(),
                        tuple(p.type_annot for p in self.params),
                        ret_type)
