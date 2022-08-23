#
# This file defines the language features related to futures in Arete,
# which includes
# * creation of a future
# * waiting on a future

from dataclasses import dataclass
from abstract_syntax import Param
from ast_base import *
from ast_types import *
from values import *
from utilities import *

      
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

  def type_check(self, env):
    arg_type = self.arg.type_check(env)
    return FutureType(self.location, arg_type)
    
    
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
      if not future.thread.return_value is None \
         and future.thread.num_children == 0:
        val = future.thread.return_value
        if isinstance(runner.context, ValueCtx):
          result = Result(True, val)
        elif isinstance(runner.context, AddressCtx):
          result = Result(True, machine.memory.allocate(val))
        machine.finish_expression(result, self.location)

  def type_check(self, env):
    arg_type = self.arg.type_check(env)
    arg_type = unfold(arg_type)
    if isinstance(arg_type, FutureType):
      return arg_type.result_type
    elif isinstance(arg_type, AnyType):
      return AnyType(self.location)
    else:
      error(self.arg.location, 'in wait, expected a future, not '
            + str(arg_type))
