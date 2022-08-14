from dataclasses import dataclass
from typing import List, Set, Dict, Tuple, Any
from lark.tree import Meta
from fractions import Fraction
from utilities import *
from values import *
from memory import *
from primitive_operations import eval_prim, compare_ops

verbose = False

# Parameters

@dataclass(frozen=True)
class Param:
    location: Meta
    kind: str # let, var, inout, sink, set
    privilege: str # read, write
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

# Miscelaneous

@dataclass
class Initializer:
  location: Meta
  percentage: Exp
  arg: Exp
  __match_args__ = ("location", "percentage", "arg")
  def __str__(self):
      return str(self.percentage) + " of " + str(self.arg)
  def __repr__(self):
      return str(self)
  def free_vars(self):
      percent_fv = set() if isinstance(self.percentage, str) \
          else self.percentage.free_vars()
      return percent_fv | self.arg.free_vars()
  def step(self, runner, machine):
    if runner.state == 0:
      if self.percentage == 'default':
        self.percentage = Frac(self.location, Fraction(1,2))
      machine.schedule(self.percentage, runner.env)
    elif runner.state == 1:
      percent = runner.results[0].value
      runner.amount = to_number(percent, self.location)
      machine.schedule(self.arg, runner.env, runner.context)
    else:
      val = runner.results[1].value
      val_copy = val.duplicate(runner.amount, self.location)
      machine.finish_expression(Result(runner.results[1].temporary, val_copy),
                                self.location)
      
# Expressions

# Dimitri:
# lvalue for let, inout, and set parameters, rvalue for sink parameters.

@dataclass
class Call(Exp):
  fun: Exp
  args: List[Initializer]
  
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
      machine.schedule(self.fun, runner.env)
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
            bind_param(param, arg, runner.body_env, machine.memory,
                       self.location)
          machine.push_frame()
          machine.schedule(body, runner.body_env, return_mode=ret_mode)
        case _:
          error(self.location, 'expected function in call, not '
                + str(runner.clos))
    else:
      # return from the function
      for (param, arg) in zip(runner.params, runner.args):
        dealloc_param(param, arg, runner.body_env, machine.memory,
                      self.location)
      if runner.return_value is None:
        runner.return_value = Void()
      if isinstance(runner.context, ValueCtx):
        if runner.clos.return_mode == 'value':
          result = runner.return_value
        elif runner.clos.return_mode == 'address':
          result = machine.memory.read(runner.return_value, self.location)
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
class Prim(Exp):
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
        machine.schedule(self.args[runner.state], runner.env, ValueCtx())
      else:
        result = eval_prim(self.op, [res.value for res in runner.results],
                           machine, self.location)
        if isinstance(runner.context, AddressCtx):
          # join produces an address, no need to allocate
          if self.op != 'join':
            result = machine.memory.allocate(result)
        machine.finish_expression(Result(True, result), self.location)
            
@dataclass
class Member(Exp):
    arg: Exp
    field: str
    __match_args__ = ("arg", "field")
    def __str__(self):
        return str(self.arg) + "." + self.field
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.arg.free_vars()
    def step(self, runner, machine):
      if runner.state == 0:
        machine.schedule(self.arg, runner.env, AddressCtx())
      else:
        mod_ptr = runner.results[0].value
        mod = machine.memory.read(mod_ptr, self.location)
        if not isinstance(mod, Module):
          error(e.location, "expected a module, not " + str(val))
        if self.field in mod.exports.keys():
          ptr = mod.exports[self.field]
          if isinstance(runner.context, ValueCtx):
            result = Result(True, machine.memory.read(ptr, self.location))
          elif isinstance(runner.context, AddressCtx):
            result = Result(False, ptr)
          machine.finish_expression(result, self.location)
        else:
          error(self.location, 'no member ' + self.field
                + ' in module ' + mod.name)

@dataclass
class Array(Exp):
    size: Exp
    arg: Exp
    __match_args__ = ("size","arg")
    def __str__(self):
        return "new " + "[" + str(self.size) + "]" + str(self.arg)
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.size.free_vars() | self.arg.free_vars()
    def step(self, runner, machine):
      if runner.state == 0:
        machine.schedule(self.size, runner.env)
      elif runner.state == 1:
        machine.schedule(self.arg, runner.env)
      else:
        sz = runner.results[0].value
        val = runner.results[1].value
        size = to_integer(sz, self.location)
        vals = [val.duplicate(Fraction(1,2), self.location) for i in range(0,size-1)]
        vals.append(val)
        array = TupleValue(vals)
        if isinstance(runner.context, ValueCtx):
            result = array
        elif isinstance(runner.context, AddressCtx):
            result = machine.memory.allocate(array)
        machine.finish_expression(Result(True, result), self.location)

@dataclass
class TupleExp(Exp):
    inits: List[Initializer]
    __match_args__ = ("inits",)
    def __str__(self):
        return '(new ' + ', '.join([str(e) for e in self.inits]) + ')'
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return set().union(*[init.free_vars() for init in self.inits])
    def step(self, runner, machine):
      if runner.state < len(self.inits):
        machine.schedule(self.inits[runner.state], runner.env)
      else:
        vals = [res.value.duplicate(1, self.location) for res in runner.results]
        for res in runner.results:
          res.value.kill(machine.memory, self.location)
        tup = TupleValue(vals)
        if isinstance(runner.context, ValueCtx):
          result = tup
        elif isinstance(runner.context, AddressCtx):
          result = machine.memory.allocate(tup)
        machine.finish_expression(Result(True, result), self.location)
        
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
    def step(self, runner, machine):
        if self.ident not in runner.env:
            error(self.location, 'use of undefined variable ' + self.ident)
        ptr = runner.env[self.ident]
        if isinstance(runner.context, ValueCtx):
          result = Result(True, machine.memory.read(ptr, self.location))
        elif isinstance(runner.context, AddressCtx):
          result = Result(False, ptr)
        machine.finish_expression(result, self.location)

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
    
@dataclass
class Index(Exp):
    arg: Exp
    index: Exp
    __match_args__ = ("arg", "index")
    def __str__(self):
        return str(self.arg) + "[" + str(self.index) + "]"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.arg.free_vars() | self.index.free_vars()
    def step(self, runner, machine):
      if runner.state == 0:
        # machine.schedule(self.arg, runner.env, runner.context)
        machine.schedule(self.arg, runner.env, AddressCtx())
      elif runner.state == 1:
        machine.schedule(self.index, runner.env)
      else:
        ind = runner.results[1].value
        i = to_integer(ind, self.location)
        if isinstance(runner.context, ValueCtx):
          if tracing_on():
              print('in Index.step, ValueCtx')
          #tup = runner.results[0].value
          tup_ptr = runner.results[0].value
          tup = machine.memory.raw_read(tup_ptr.get_address(), tup_ptr.get_path(),
                                        self.location)
          if not isinstance(tup, TupleValue):
            error(self.location, 'expected a tuple, not ' + str(tup))
          val = tup.elts[int(i)]
          if runner.results[0].temporary:
              val = val.duplicate(tup_ptr.permission, self.location)
          result = Result(runner.results[0].temporary, val)
        elif isinstance(runner.context, AddressCtx):
          if tracing_on():
              print('in Index.step, AddressCtx')
          res = duplicate_if_temporary(runner.results[0], self.location)
          ptr = res.value
          result = Result(runner.results[0].temporary, PointerOffset(ptr, int(i)))
        else:
          error(self.location, 'unrecognized context ' + repr(runner.context))
        machine.finish_expression(result, self.location)

@dataclass
class Deref(Exp):
    arg: Exp
    __match_args__ = ("arg",)
    def __str__(self):
        return '(*' + str(self.arg) + ')'
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.arg.free_vars()
    def step(self, runner, machine):
      if runner.state == 0:
        machine.schedule(self.arg, runner.env)
      else:
        if tracing_on():
            print('in Deref.step')
        ptr = runner.results[0].value
        if not isinstance(ptr, Pointer):
          error(self.location, 'deref expected a pointer, not ' + str(ptr))
        if isinstance(runner.context, ValueCtx):
            result = Result(True, machine.memory.read(ptr, self.location))
        elif isinstance(runner.context, AddressCtx):
            result = duplicate_if_temporary(runner.results[0], self.location)
        machine.finish_expression(result, self.location)

@dataclass
class AddressOf(Exp):
    arg: Exp
    __match_args__ = ("arg",)
    def __str__(self):
        return '&' + str(self.arg)
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.arg.free_vars()
    def step(self, runner, machine):
      if runner.state == 0:
        machine.schedule(self.arg, runner.env, AddressCtx())
      else:
        res = duplicate_if_temporary(runner.results[0], self.location)
        if isinstance(runner.context, ValueCtx):
          result = Result(runner.results[0].temporary, res.value)
        elif isinstance(runner.context, AddressCtx):
          result = Result(True, machine.memory.allocate(res.value))
        machine.finish_expression(result, self.location)
        
@dataclass
class Lambda(Exp):
    params: List[Param]
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

def duplicate_if_temporary(result: Result, loc):
  if result.temporary:
    tmp = True
    val = result.value.duplicate(1, loc)
  else:
    tmp = False
    val = result.value
  return Result(tmp, val)

@dataclass
class BindingExp(Exp):
    param: Param
    arg: Exp
    body: Exp
    __match_args__ = ("param", "arg", "body")
    def __str__(self):
      if verbose:
        return str(self.param) + " = " + str(self.arg) + ";\n" \
            + str(self.body)
      else:
        return str(self.param) + " = " + str(self.arg) + "; ..."
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.arg.free_vars() \
            | (self.body.free_vars() - set([self.param.ident]))
    def step(self, runner, machine):
      if runner.state == 0:
        machine.schedule(self.arg, runner.env, AddressCtx())
      elif runner.state == 1:
        runner.body_env = runner.env.copy()
        bind_param(self.param, runner.results[0],
                   runner.body_env, machine.memory, self.arg.location)
        machine.schedule(self.body, runner.body_env)
      else:
        dealloc_param(self.param, runner.results[0],
                      runner.body_env, machine.memory, self.location)
        result = duplicate_if_temporary(runner.results[1], self.location)
        machine.finish_expression(result, self.location)

@dataclass
class DefExp(Exp):
    var: Param
    init: Initializer
    body: Exp
    __match_args__ = ("var", "init", "body")
    def __str__(self):
        return "var " + str(self.var) + " = " + str(self.init) + ";\n" \
            + str(self.body)
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.init.free_vars() | \
            (self.body.free_vars() - set([self.var.ident]))
    def step(self, runner, machine):
      if runner.state == 0:
        machine.schedule(self.init, runner.env, AddressCtx())
      elif runner.state == 1:
        val = runner.results[0].value
        runner.body_env = runner.env.copy()
        bind_param(self.var, val, runner.body_env, machine.memory,
                   self.location)
        machine.schedule(self.body, runner.body_env, runner.context)
      else:
        dealloc_param(self.var, runner.body_env, machine.memory, self.location)
        result = duplicate_if_temporary(runner.results[1], self.location)
        machine.finish_expression(result, self.location)

@dataclass
class FutureExp(Exp):
  arg: Exp
  __match_args__ = ("arg",)
  def __str__(self):
    return "future " + str(self.arg)
  def __repr__(self):
    return str(self)
  def free_vars(self):
    return self.arg.free_vars()
  def step(self, runner, machine):
    thread = machine.spawn(self.arg, runner.env)
    if isinstance(runner.context, ValueCtx):
      result = Future(thread)
    elif isinstance(runner.context, AddressCtx):
      future = Future(thread)
      result = machine.memory.allocate(future)
    machine.finish_expression(Result(True, result), self.location)

@dataclass
class Wait(Exp):
  arg: Exp
  __match_args__ = ("arg",)
  def __str__(self):
    return "wait " + str(self.arg)
  def __repr__(self):
    return str(self)
  def free_vars(self):
    return self.arg.free_vars()
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.arg, runner.env)
    else:
      future = runner.results[0].value
      if not isinstance(future, Future):
        error(self.location, 'in wait, expected a future, not ' + str(future))
      if not future.thread.result is None \
         and future.thread.num_children == 0:
        if isinstance(runner.context, ValueCtx):
          result = Result(True, future.thread.result)
        elif isinstance(runner.context, AddressCtx):
          result = Result(True, machine.memory.allocate(future.thread.result))
        machine.finish_expression(result, self.location)
  
    
# Statements

@dataclass
class Seq(Stmt):
  first: Stmt
  rest: Stmt
  __match_args__ = ("first", "rest")
  def __str__(self):
    if verbose:
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
    
@dataclass
class DefInit(Exp):
    var: Param
    init: Initializer
    body: Stmt
    __match_args__ = ("var", "init", "body")
    def __str__(self):
      if verbose:
        return "def " + str(self.var) + " = " + str(self.init) + ";\n" \
            + str(self.body)
      else:
        return "def " + str(self.var) + " = " + str(self.init) + "; ..."
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.init.free_vars() \
            | (self.body.free_vars() - set([self.var.ident]))
    def step(self, runner, machine):
      if runner.state == 0:
        machine.schedule(self.init, runner.env, AddressCtx())
      elif runner.state == 1:
        val = runner.results[0].value
        runner.body_env = runner.env.copy()
        bind_parameter(self.var.ident, self.var.privilege, val,
                       runner.body_env, machine.memory,
                       self.init.location)
        machine.schedule(self.body, runner.body_env)
      else:
        deallocate_parameter(self.var.ident, runner.body_env,
                             machine.memory, self.location)
        machine.finish_statement(self.location)
        
# This is meant to have the same semantics as the `let`, `var`, and
# `inout` statement in Val.
@dataclass
class BindingStmt(Exp):
    param: Param
    arg: Exp
    body: Stmt
    __match_args__ = ("param", "arg", "body")
    def __str__(self):
      if verbose:
        return str(self.param) + " = " + str(self.arg) + ";\n" \
            + str(self.body)
      else:
        return str(self.param) + " = " + str(self.arg) + "; ..."
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.arg.free_vars() \
            | (self.body.free_vars() - set([self.param.ident]))
    def step(self, runner, machine):
      if runner.state == 0:
        machine.schedule(self.arg, runner.env, AddressCtx())
      elif runner.state == 1:
        runner.body_env = runner.env.copy()
        bind_param(self.param, runner.results[0],
                   runner.body_env, machine.memory, self.arg.location)
        machine.schedule(self.body, runner.body_env)
      else:
        dealloc_param(self.param, runner.results[0],
                      runner.body_env, machine.memory, self.location)
        machine.finish_statement(self.location)
        
# Dimitri:
# return values are always evaluated for their rvalue

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
    
@dataclass
class Write(Stmt):
    lhs: Exp
    rhs: Initializer
    __match_args__ = ("lhs", "rhs")
    def __str__(self):
        return str(self.lhs) + " = " + str(self.rhs) + ";"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.lhs.free_vars() | self.rhs.free_vars()
    def step(self, runner, machine):
      # TODO: switch the ordering back to lhs then rhs?
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
class Transfer(Stmt):
    lhs: Exp
    percent: Exp
    rhs: Exp
    __match_args__ = ("lhs", "percent", "rhs")
    def __str__(self):
        return str(self.lhs) + " <- " + str(self.percent) + " of " \
            + str(self.rhs) + ";"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.lhs.free_vars() | self.percent.free_vars() \
            | self.rhs.free_vars()
    def step(self, runner, machine):
      if runner.state == 0:
        machine.schedule(self.lhs, runner.env)
      elif runner.state == 1:
        machine.schedule(self.percent, runner.env)
      elif runner.state == 2:
        machine.schedule(self.rhs, runner.env)
      else:
        dest_ptr = runner.results[0].value
        amount = runner.results[1].value
        src_ptr = runner.results[2].value
        percent = to_number(amount, self.location)
        dest_ptr.transfer(percent, src_ptr, self.location)
        machine.finish_statement(self.location)
    
@dataclass
class Delete(Stmt):
    arg: Exp
    __match_args__ = ("arg",)
    def __str__(self):
        return "delete " + str(self.arg) + ";"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.arg.free_vars()
    def step(self, runner, machine):
      if runner.state == 0:
        machine.schedule(self.arg, runner.env)
      else:
        ptr = runner.results[0].value
        if not isinstance(ptr, Pointer):
          error(self.location, 'in delete, expected a pointer, not ' + str(ptr))
        delete(ptr, machine.memory, self.location)
        ptr.address = None
        ptr.permission = Fraction(0,1)
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

@dataclass
class IfStmt(Stmt):
    cond: Exp
    thn: Stmt
    els: Stmt
    __match_args__ = ("cond", "thn", "els")
    def __str__(self):
      if verbose:
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
    def step(self, runner, machine):
      machine.finish_statement(self.location)

@dataclass
class Block(Stmt):
    body: Exp
    __match_args__ = ("body",)
    def __str__(self):
        return "{\n" + str(self.body) + "\n}"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.body.free_vars()
    def step(self, runner, machine):
      if runner.state == 0:
        machine.schedule(self.body, runner.env)
      else:
        machine.finish_statement(self.location)
    
# Declarations
    
@dataclass
class Global(Exp):
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
class TypeDef(Exp):
  name: str
  type: Type
  __match_args__ = ("name", "type")
  def __str__(self):
    return "type " + str(self.name) + " = " + str(self.type) + ";"
  def __repr__(self):
    return str(self)
  def step(self, runner, machine):
    machine.finish_definition(self.location)

  
@dataclass
class Function(Decl):
    name: str
    params: List[Param]
    return_type: Type
    return_mode: str    # 'value' or 'address'
    body: Exp
    __match_args__ = ("name", "params", "return_type", "return_mode", "body")
    def __str__(self):
        return "function " + self.name \
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

@dataclass
class ModuleDef(Decl):
  name: str
  exports: List[str]
  body: List[Decl]
  __match_args__ = ("name", "exports", "body")
  def __str__(self):
    return 'module ' + self.name + '\n'\
        + '  exports ' + ", ".join(ex for ex in self.exports) + ' {\n' \
        + '\n'.join([str(d) for d in self.body]) + '\n}\n'
  def __repr__(self):
    return str(self)
  def step(self, runner, machine):
    if runner.state == 0:
      runner.body_env = {}
      for d in self.body:
        declare_decl(d, runner.body_env, machine.memory)
    if runner.state < len(self.body):
      machine.schedule(self.body[runner.state], runner.body_env)
    else:
      for ex in self.exports:
        if not ex in runner.body_env:
          error(self.location, 'export ' + ex + ' not defined in module')
      mod = Module(self.name,
                   {ex: runner.body_env[ex] for ex in self.exports},
                   runner.body_env)
      machine.memory.memory[runner.env[self.name].address] = mod
      machine.finish_definition(self.location)

@dataclass
class Import(Decl):
  module: Exp
  imports: List[str]
  __match_args__ = ("module", "imports")
  def __str__(self):
    return 'from ' + str(self.module) + ' import ' \
        + ', '.join(im for im in self.imports) + ';'
  def __repr__(self):
    return str(self)
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.module, runner.env, AddressCtx())
    else:
      mod_ptr = runner.results[0].value
      mod = machine.memory.read(mod_ptr, self.location)
      for x in self.imports:
        if x in mod.exports.keys():
          val = machine.memory.read(mod.exports[x], self.location)
          machine.memory.write(runner.env[x], val, self.location)
        else:
          error(self.location, 'module does not export ' + x)
      machine.finish_definition(self.location)
      
# TODO: instead do allocation and then fill in the result -Jeremy
def declare_decl(decl, env, mem):
    match decl:
      case Import(module, imports):
        for x in imports:
            env[x] = mem.allocate(Void())
      case _:
        env[decl.name] = mem.allocate(Void())
        
# Types

@dataclass(eq=True, frozen=True)
class AnyType(Type):
  def __str__(self):
    return '?'
  def __repr__(self):
    return str(self)

@dataclass(eq=True, frozen=True)
class IntType(Type):
  def __str__(self):
    return 'int'
  def __repr__(self):
    return str(self)

@dataclass(eq=True, frozen=True)
class RationalType(Type):
  def __str__(self):
    return 'rational'
  def __repr__(self):
    return str(self)

@dataclass(eq=True, frozen=True)
class BoolType(Type):
  def __str__(self):
    return 'bool'
  def __repr__(self):
    return str(self)

@dataclass(eq=True, frozen=True)
class VoidType(Type):
  def __str__(self):
    return 'void'
  def __repr__(self):
    return str(self)

@dataclass(eq=True, frozen=True)
class PointerType(Type):
  type: Type
  __match_args__ = ("type",)
  def __str__(self):
    return str(self.type) + '*'
  def __repr__(self):
    return str(self)

@dataclass(eq=True, frozen=True)
class RecursiveType(Type):
  name: str
  type: Type
  __match_args__ = ("name", "type",)
  def __str__(self):
    return '(rec ' + self.name + ' in ' + str(self.type) + ')'
  def __repr__(self):
    return str(self)
  
@dataclass(eq=True, frozen=True)
class ArrayType(Type):
  element_type: Type
  __match_args__ = ("element_type",)
  def __str__(self):
    return 'array[' + str(self.element_type) + ']'
  def __repr__(self):
    return str(self)
  
@dataclass(eq=True, frozen=True)
class TupleType(Type):
  member_types: tuple[Type]  
  __match_args__ = ("member_types",)
  def __str__(self):
    return '⟨' + ', '.join([str(t) for t in self.member_types]) + '⟩'
  def __repr__(self):
    return str(self)
  
@dataclass(eq=True, frozen=True)
class FunctionType(Type):
  param_types: tuple[Type]
  return_type: Type
  __match_args__ = ("param_types", "return_type")
  def __str__(self):
    return '(' + ', '.join([str(t) for t in self.param_types]) + ')' \
        + '->' + str(self.return_type)
  def __repr__(self):
    return str(self)
    
@dataclass(eq=True, frozen=True)
class ModuleType(Type):
  member_types: dict[str, Type]
  __match_args__ = ("member_types",)
  def __str__(self):
    return '{' + ', '.join([n + ':' + str(t) \
                            for n,t in self.member_types.items()]) + '}'
  def __repr__(self):
    return str(self)

@dataclass(eq=True, frozen=True)
class FutureType(Type):
  result_type: Type
  __match_args__ = ("reult_type",)
  def __str__(self):
    return '^' + str(self.result_type)
  def __repr__(self):
    return str(self)

@dataclass(eq=True, frozen=True)
class TypeVar(Type):
    ident: str
    __match_args__ = ("ident",)
    def __str__(self):
        return self.ident
    def __repr__(self):
        return str(self)
  
