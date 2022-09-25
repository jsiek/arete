#
# This file defines the language features related to pointers in Arete,
# which includes
# * percent-of, 
# * dereference,
# * address-of,
# * transfer, and
# * delete.

from dataclasses import dataclass
from abstract_syntax import Int
from variables_and_binding import Param
from ast_base import *
from ast_types import *
from values import *
from utilities import *

@dataclass
class PercentOf(Exp):
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

  def const_eval(self, env):
    if self.percentage == 'default':
      new_percent = 'default'
    else:
      new_percent = self.percentage.const_eval(env)
    new_arg = self.arg.const_eval(env)
    return PercentOf(self.location, new_percent, new_arg)
    
  def type_check(self, env, ctx):
    if self.percentage == 'default':
      percent_type = RationalType(self.location)
      new_percent = 'default'
    else:
      percent_type, new_percent = self.percentage.type_check(env, 'none')
    arg_type, new_arg = self.arg.type_check(env, 'let') # TODO
    percent_type = unfold(percent_type)
    if isinstance(percent_type, RationalType) \
       or isinstance(percent_type, IntType):
      return arg_type, PercentOf(self.location, new_percent, new_arg)
    elif isinstance(percent_type, AnyType):
      return AnyType(self.location), \
             PercentOf(self.location, new_percent, new_arg)
    else:
      error(self.location, 'in initializer, expected percentage '
            + 'not ' + str(percent_type))
      
  def step(self, runner, machine):
    if runner.state == 0:
      if self.percentage == 'default':
        self.percentage = Frac(self.location, Fraction(1,2))
      machine.schedule(self.percentage, runner.env,
                       ValueCtx(runner.context.duplicate))
    elif runner.state == 1:
      percent = runner.results[0].value
      runner.amount = to_number(percent, self.location)
      machine.schedule(self.arg, runner.env, runner.context)
    else:
      val = runner.results[1].value
      val_copy = val.duplicate(runner.amount, self.location)
      machine.finish_expression(Result(runner.results[1].temporary, val_copy),
                                self.location)


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

  def const_eval(self, env):
    new_arg = self.arg.const_eval(env)
    return Deref(self.location, new_arg)
    
  def type_check(self, env, ctx):
    arg_type, new_arg = self.arg.type_check(env, ctx)
    new_self = Deref(self.location, new_arg)
    arg_type = unfold(arg_type)
    if isinstance(arg_type, PointerType):
      return arg_type.type, new_self
    elif isinstance(arg_type, AnyType):
      return AnyType(self.location), new_self
    else:
      error(self.location, 'in deref, expected a pointer, not '
            + str(arg_type))
      
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.arg, runner.env,
                       ValueCtx(runner.context.duplicate))
    else:
      if tracing_on():
          print('in Deref.step')
      ptr = runner.results[0].value
      if not isinstance(ptr, Pointer):
        error(self.location, 'deref expected a pointer, not ' + str(ptr))
      if isinstance(runner.context, ValueCtx):
          val = machine.memory.read(ptr, self.location)
          result = Result(True, val.duplicate(ptr.get_permission(),
                                              self.location))
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

  def const_eval(self, env):
    new_arg = self.arg.const_eval(env)
    return AddressOf(self.location, new_arg)
    
  def type_check(self, env, ctx):
    arg_type, new_arg = self.arg.type_check(env, ctx)
    return PointerType(self.location, arg_type), \
           AddressOf(self.location, new_arg)
        
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

  def const_eval(self, env):
    new_lhs = self.lhs.const_eval(env)
    new_percent = self.percent.const_eval(env)
    new_rhs = self.rhs.const_eval(env)
    return Transfer(self.location, new_lhs, new_percent, new_rhs)

  def type_check(self, env):
    lhs_type, new_lhs = self.lhs.type_check(env, 'none') # TODO
    lhs_type = unfold(lhs_type)
    percent_type, new_percent = self.percent.type_check(env, 'none')
    rhs_type, new_rhs = self.rhs.type_check(env, 'none') # TODO
    rhs_type = unfold(rhs_type)
    if not (isinstance(lhs_type, PointerType) or isinstance(lhs_type, AnyType)):
      error(self.location, 'in transfer LHS, expected a pointer, not '
            + str(lhs_type))
    if not (isinstance(rhs_type, PointerType) or isinstance(rhs_type, AnyType)):
      error(self.location, 'in transfer RHS, expected a pointer, not '
            + str(rhs_type))
    return None, Transfer(self.location, new_lhs, new_percent, new_rhs)

  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.lhs, runner.env, ValueCtx(duplicate=False))
    elif runner.state == 1:
      machine.schedule(self.percent, runner.env)
    elif runner.state == 2:
      machine.schedule(self.rhs, runner.env, ValueCtx(duplicate=False))
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

  def const_eval(self, env):
    new_arg = self.arg.const_eval(env)
    return Delete(self.location, new_arg)
    
  def type_check(self, env):
    arg_type, new_arg = self.arg.type_check(env, 'var')
    arg_type = unfold(arg_type)
    if not (isinstance(arg_type, PointerType) or isinstance(arg_type, AnyType)):
      error(self.location, 'in delete, expected a pointer, not '
            + str(arg_type))
    return None, Delete(self.location, new_arg)

  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.arg, runner.env)
    else:
      ptr = runner.results[0].value
      if not isinstance(ptr, Pointer):
        error(self.location, 'in delete, expected a pointer, not ' + str(ptr))
      if not writable(ptr.get_permission()):
          error(self.location, 'delete needs writable pointer, not '
                + str(ptr))
      machine.memory.deallocate(ptr.get_address(), self.location, set())
      ptr.address = None
      ptr.permission = Fraction(0,1)
      machine.finish_statement(self.location)
