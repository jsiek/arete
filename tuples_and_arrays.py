#
# This file defines the language features related to tuples and arrays in Arete,
# which includes
# * array creation
# * tuple creation
# * element access (indexing)

from dataclasses import dataclass
from abstract_syntax import Param, Int
from ast_base import *
from ast_types import *
from values import *
from utilities import *

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
      vals = [val.duplicate(Fraction(1,2), self.location) \
              for i in range(0,size-1)]
      vals.append(val)
      array = TupleValue(vals)
      if isinstance(runner.context, ValueCtx):
          result = array
      elif isinstance(runner.context, AddressCtx):
          result = machine.memory.allocate(array)
      machine.finish_expression(Result(True, result), self.location)

  def type_check(self, env):
    size_type = self.size.type_check(env)
    arg_type = self.arg.type_check(env)
    if not (isinstance(size_type, IntType)
            or isinstance(size_type, AnyType)):
        error(self.location, "expected integer array size, not "
              + str(size_type))
    return ArrayType(self.location, arg_type)
      
@dataclass
class TupleExp(Exp):
  inits: list[Exp]
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
      tup = TupleValue(vals)
      if isinstance(runner.context, ValueCtx):
        result = tup
      elif isinstance(runner.context, AddressCtx):
        result = machine.memory.allocate(tup)
      machine.finish_expression(Result(True, result), self.location)

  def type_check(self, env):
    init_types = tuple(init.type_check(env) for init in self.inits)
    return TupleType(self.location, init_types)
    
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
      machine.schedule(self.arg, runner.env,
                       AddressCtx(runner.context.duplicate))
    elif runner.state == 1:
      machine.schedule(self.index, runner.env)
    else:
      ind = runner.results[1].value
      i = to_integer(ind, self.location)
      if isinstance(runner.context, ValueCtx):
        if tracing_on():
            print('in Index.step, ValueCtx')
        tup_ptr = runner.results[0].value
        tup = machine.memory.read(tup_ptr, self.location)
        if not isinstance(tup, TupleValue):
          error(self.location, 'expected a tuple, not ' + str(tup))
        val = tup.elts[int(i)]
        if runner.results[0].temporary:
            percent = tup_ptr.permission
            val = val.duplicate(percent, self.location)
        result = Result(runner.results[0].temporary, val)
      elif isinstance(runner.context, AddressCtx):
        if tracing_on():
            print('in Index.step, AddressCtx')
        res = duplicate_if_temporary(runner.results[0], self.location)
        ptr = res.value
        ptr_offset = PointerOffset(ptr, int(i))
        result = Result(runner.results[0].temporary, ptr_offset)
      else:
        error(self.location, 'unrecognized context ' + repr(runner.context))
      machine.finish_expression(result, self.location)

  def type_check(self, env):
    arg_type = self.arg.type_check(env)
    index_type = self.index.type_check(env)
    arg_type = unfold(arg_type)
    if isinstance(arg_type, TupleType):
      if isinstance(self.index, Int):
        if 0 <= self.index.value \
           and self.index.value < len(arg_type.member_types):
          return arg_type.member_types[self.index.value]
        else:
          error(self.location, 'index ' + str(self.index.value)
                + ' out of bounds for pointer ' + str(arg_type))
      else:
        error(self.location, 'in subscript, expected an integer index, not '
              + str(self.index))
    elif isinstance(arg_type, ArrayType):
      return arg_type.element_type
    elif isinstance(arg_type, AnyType):
      return AnyType(self.location)
    else:
      error(self.location, 'in subscript, expected tuple or array, not '
            + str(arg_type))
      
