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
    requirements: list[AST]
    body: Stmt
    env: dict[str,Pointer]
    __match_args__ = ("name", "params", "return_mode", "requirements", "body", "env")
    
    def duplicate(self, percentage, loc):
      if tracing_on():
        print('duplicating closure ' + str(self))
      env_copy = {x: v.duplicate(Fraction(1,2), loc) \
                  for x,v in self.env.items()}
      return Closure(self.name, self.params, self.return_mode, self.requirements,
                     self.body, env_copy)
    
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
  requirements: list[AST]
  body: Exp
  __match_args__ = ("name", "type_params", "params", "return_type",
                    "return_mode", "requirements", "body")
  
  def __str__(self):
      return "fun " + self.name \
          + ("<" + ", ".join(self.type_params) + ">" \
             if len(self.type_params) > 0 \
             else "") \
          + "(" + ", ".join([str(p) for p in self.params]) + ")" \
          + " -> " + str(self.return_type) + " " \
          + ", ".join([str(req) for req in self.requirements]) \
          + " " + str(self.body)
    
  def __repr__(self):
      return str(self)
    
  def free_vars(self):
    req_vars = set([req.name for req in self.requirements])
    req_mem_vars = set([req.iface.members.keys() for req in self.requirements])
    params = set([p.ident for p in self.params])
    fvars = body.free_vars() - params - req_mem_vars - req_vars
    if tracing_on():
      print('function ' + self.name + ' free variables: ' + str(fvars)
            + '\nrequirements: ' + str(req_mem_vars))
    return fvars
    
  def declare_type(self, env, output):
    ty = FunctionType(self.location,
                      self.type_params,
                      tuple(p.type_annot for p in self.params),
                      self.return_type,
                      tuple(self.requirements))
    env[self.name] = simplify(ty, env)
    output[self.name] = env[self.name]
    
  def type_check(self, env):
    if tracing_on():
      print('type checking function ' + str(self))
    body_env = {x: t.copy() for x,t in env.items()}
    for t in self.type_params:
      body_env[t] = TypeVar(self.location, t)
    ret_ty = simplify(self.return_type, body_env)
    # Bind parameters to their types
    for p in self.params:
        body_env[p.ident] = simplify(p.type_annot, body_env)
        
    # Bring the impls and their members into scope.
    new_reqs = []
    for req in self.requirements:
      new_reqs.append(req.declare_type(body_env, {}))
    self.requirements = new_reqs
    
    # type check the body of the function
    body_type = self.body.type_check(body_env)
    if not consistent(body_type, ret_ty):
      error(self.location, 'return type mismatch:\n' + str(ret_ty)
            + ' inconsistent with ' + str(body_type))
    if tracing_on():
      print('finished type checking function ' + self.name)
      
  def step(self, runner, machine):
    if runner.state == 0:
      lam = Lambda(self.location, self.params, self.return_mode,
                   self.requirements, self.body, self.name)
      machine.schedule(lam, runner.env)
    else:
      machine.memory.unchecked_write(runner.env[self.name],
                                     runner.results[0].value,
                                     self.location)
      machine.finish_definition(self.location)

    
@dataclass
class Call(Exp):
  fun: Exp
  args: list[Exp]
  witnesses: tuple[Exp] = ()
  
  __match_args__ = ("fun", "args")
  
  def __str__(self):
      return str(self.fun) \
          + "(" + ", ".join([str(arg) for arg in self.args]) + ")" \
          + ", ".join([str(wit) for wit in self.witnesses])
  
  def __repr__(self):
      return str(self)
  
  def free_vars(self):
      return self.fun.free_vars() \
          | set().union(*[arg.free_vars() for arg in self.args]) \
          | set().union(*[wit.free_vars() for wit in self.witnesses])
  
  def type_check(self, env):
    fun_type = self.fun.type_check(env)
    arg_types = [arg.type_check(env) for arg in self.args]
    fun_type = unfold(fun_type)
    if tracing_on():
      print('type checking call ' + str(self))
      print('function type: ' + str(fun_type))
      print('in environment: ' + str(env))
    if isinstance(fun_type, FunctionType):
      fun_env = {x: t.copy()  for x, t in env.items()}

      for t in fun_type.type_params:
        fun_env[t] = TypeVar(self.location, t)
      if len(fun_type.param_types) != len(arg_types):
        error(self.location, 'incorrect number of arguments: '
              + str(len(arg_types))
              + '\nexpected: ' + str(len(fun_type.param_types)))
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
        
      # check that the type requirements are satisfied and record them
      # in self.witnesses
      self.witnesses = []
      for req in fun_type.requirements:
        iface_impl_info = env[req.iface_name]
        req_impl_types = [substitute(matches, simplify(ty, fun_env)) \
                          for ty in req.impl_types]
        if tracing_on():
          print('searching for impl of ' + req.iface_name
                + ' for ' + str(req_impl_types))
        witness_exp = None
        for impl_tys, wit_exp in iface_impl_info.impls:
          if all([t1 == t2 for t1, t2 in zip(req_impl_types, impl_tys)]):
            if tracing_on():
              print('found ' + str(wit_exp))
            witness_exp = wit_exp
            break
        if witness_exp is None:
          error(self.location, 'could not find impl of ' + req.iface_name
                + ' for ' + str(req_impl_types)
                + '\nin impls:\n'
                + str(iface_impl_info.impls))
        self.witnesses.append(witness_exp)
      
      rt = simplify(fun_type.return_type, fun_env)
      ret = substitute(matches, rt)
      if tracing_on():
        print('finished type checking: ' + str(self))
        print('type: ' + str(ret))
      return ret
    elif isinstance(fun_type, AnyType):
      return AnyType(self.location)
    else:
      error(self.location, "in call, expected a function, not "
            + str(fun_type))

  def set_closure(self, runner, machine):
      if runner.clos is None:
        runner.clos = runner.results[0].value
        if not isinstance(runner.clos, Closure):
          error(self.location, 'expected function in call, not '
                + str(runner.clos))
          
  def step(self, runner, machine):
    if runner.state == 0:
      if tracing_on():
        print('starting call, #witnesses = ' + str(len(self.witnesses)))
      # evaluate the operator subexpression
      machine.schedule(self.fun, runner.env,
                       ValueCtx(runner.context.duplicate))
      runner.clos = None
    elif runner.state <= len(self.args):
      self.set_closure(runner, machine)
      # evaluate the operand subexpressions
      machine.schedule(self.args[runner.state - 1], runner.env, AddressCtx())
    elif runner.state <= len(self.args) + len(self.witnesses):
      # evaluate the witness subexpressions
      i = runner.state - 1 - len(self.args)
      machine.schedule(self.witnesses[i], runner.env, AddressCtx())
    elif runner.state == 1 + len(self.args) + len(self.witnesses):
      self.set_closure(runner, machine)
      # call the function
      match runner.clos:
        case Closure(name, params, ret_mode, reqs, body, clos_env):
          if len(params) != len(self.args):
            error(self.location, 'wrong number of arguments, expected '
                  + str(len(params)) + ' not ' + str(len(self.args)))
          runner.params = params
          runner.body_env = clos_env.copy()
          runner.args = runner.results[1:1+len(self.args)]
          witness_res = runner.results[1+len(self.args):]
          runner.witnesses = [res.value for res in witness_res]
          if tracing_on():
            print('call with len(witnesses): ' + str(len(runner.witnesses)))
            
          # Bind the parameters to their arguments.
          for param, arg in zip(params, runner.args):
            machine.bind_param(param, arg, runner.body_env, self.location)

          # Bind required impls to their witnesses.
          for req, witness_ptr in zip(reqs, runner.witnesses):
            req.bind_impl(witness_ptr, runner.body_env, machine)
            
          machine.push_frame()
          if machine.current_thread.pause_on_call:
              machine.pause = True
              machine.current_thread.pause_on_call = False
          if tracing_on():
            print('calling function ' + runner.clos.name)
          machine.schedule(body, runner.body_env, return_mode=ret_mode)
          if debug_mode() == 'n':
              if machine.pause:
                  machine.pause = False
                  runner.pause_on_finish = True
        case _:
          error(self.location, 'expected function in call, not '
                + str(runner.clos))
    else:
      # return from the function:
      # deallocate the parameters
      for (param, arg) in zip(runner.params, runner.args):
        machine.dealloc_param(param, arg, runner.body_env,
                              runner.clos.body.location)

      # deallocate the witness member bindings:
      for witness_ptr in runner.witnesses:
        witness = machine.memory.read(witness_ptr, self.location)
        for x in witness.fields.keys():
          runner.body_env[x].kill(machine.memory, self.location)
      
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
  requirements: list[AST]
  body: Stmt
  name: str = "lambda"
  __match_args__ = ("params", "return_mode", "requirements", "body", "name")

  def __str__(self):
      return "lambda " \
          + "(" + ", ".join([str(p) for p in self.params]) + ") " \
          + ", ".join(str(req) for req in self.requirements) \
          + " " + str(self.body)

  def __repr__(self):
      return str(self)

  def free_vars(self):
    req_vars = set([req.name for req in self.requirements])
    req_mem_vars = set()
    for req in self.requirements:
      req_mem_vars = req_mem_vars | set(req.iface.members.keys())
    params = set([p.ident for p in self.params])
    return self.body.free_vars() - params - req_mem_vars - req_vars

  def step(self, runner, machine):
      clos_env = {}
      free = self.free_vars()
      if tracing_on():
        print('free vars of ' + self.name + ': ' + str(free))
      for x in free:
          if not x in runner.env.keys():
            error(self.location, 'in lambda, undefined free variable ' + x)
          v = runner.env[x]
          clos_env[x] = v.duplicate(Fraction(1,2), self.location)            
      clos = Closure(self.name, self.params, self.return_mode, self.requirements,
                     self.body, clos_env)
      if isinstance(runner.context, ValueCtx):
          result = clos
      elif isinstance(runner.context, AddressCtx):
          result = machine.memory.allocate(clos)
      else:
          error(self.location, 'function not allowed in this context')
      machine.finish_expression(Result(True, result), self.location)

  def type_check(self, env):
    body_env = {x: t.copy() for x,t in env.items()}
    for p in self.params:
        body_env[p.ident] = p.type_annot
    new_reqs = []
    for req in self.requirements:
      new_reqs.append(req.declare_type(body_env, {}))
    self.requirements = new_reqs
    ret_type = self.body.type_check(body_env)
    return FunctionType(self.location,
                        tuple(),
                        tuple(p.type_annot for p in self.params),
                        ret_type,
                        tuple())
