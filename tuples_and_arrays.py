#
# This file defines the language features related to tuples and arrays in Arete,
# which includes
# * tuple values,
# * the `split` and `let` primitives,
# * array creation,
# * tuple creation, and
# * element access (indexing).
#
# Tuple values are defined in `values.py` because some pointer
# operations (split) also make use of tuple values.

from dataclasses import dataclass
from abstract_syntax import Int
from variables_and_binding import Param
from ast_base import *
from ast_types import *
from values import Result, to_integer, duplicate_if_temporary, PointerOffset, \
    Number, Pointer
from utilities import *
import math

@dataclass
class TupleValue(Value):
    elts: list[Value]

    def equals(self, other):
      if len(self.elts) == len(other.elts):
        return all([e1 == e2 for e1,e2 in zip(self.elts, other.elts)])
      else:
        return False
    
    def duplicate(self, percentage, loc):
      return TupleValue([elt.duplicate(percentage, loc) for elt in self.elts])
    
    def kill(self, mem, location, progress=set()):
      for elt in self.elts:
        elt.kill(mem, location, progress)

    def clear(self, mem, location, progress=set()):
      for elt in self.elts:
        elt.clear(mem, location, progress)

    def get_subobject(self, path, loc, mem):
      if len(path) == 0:
        return self
      else:
        return self.elts[path[0]].get_subobject(path[1:], loc, mem)

    def set_subobject(self, path, val, loc, mem):
        if len(path) == 0:
          return val
        else:
          i = path[0]
          if i < 0 or i >= len(self.elts):
            error(loc, 'path index ' + str(i) + ' is out of bounds for tuple '
                  + str(self))
          front = self.elts[:i]
          back = self.elts[i+1:]
          ith = self.elts[i].set_subobject(path[1:], val, loc, mem)
          return TupleValue(front + [ith] + back)
      
    def __str__(self):
        return '⟨' + ', '.join([str(elt) for elt in self.elts]) + '⟩'
      
    def __repr__(self):
        return str(self)

    def __len__(self):
      return len(self.elts)
      
    def node_name(self):
        return str(self)
      
    def node_label(self):
        return '|'.join(['<' + str(i) + '>' + elt.node_label() \
                         for (i,elt) in zip(range(0,len(self.elts)),
                                            self.elts)])
    def gen_graphviz(self, addr):
      result = ''
      elt_names = []
      elt_labels = []
      for elt in self.elts:
        subresult, elt_name, elt_label = elt.gen_graphviz(None)
        result += subresult
        elt_names.append(elt_name)
        elt_labels.append(elt_label)
      if addr is None:
        name = str(id(self))
        base = ''
      else:
        name = str(addr)
        base = '<base> ' + str(addr) + ': |'
      tuple_label = base \
        + '|'.join(['<' + str(i) + '>' + label \
                    for (i,label) in zip(range(0,len(elt_labels)),elt_labels)])
      # add node
      result += name + ' [shape=record,label="' + tuple_label + '"];\n'

      # add out-edges
      for i, elt_name in zip(range(0, len(elt_names)), elt_names):
        if not elt_name is None:
          result += name + ':' + str(i) + ' -> ' + elt_name + ';\n'

      return result, name, '•'

@dataclass
class SliceValue(Value):
  tuple_ptr: Pointer # pointer to a tuple
  start: int
  stop: int
  step: int

  def is_pointer(self):
    return True
      
  def __str__(self):
    return str(self.tuple_ptr) + "[" + str(self.start) \
      + ":" + str(self.stop) + ":" + str(self.step) + "]"
      
  def __repr__(self):
    return str(self)

  def __len__(self):
    return math.ceil((self.stop - self.start) / self.step)

  def get_permission(self):
    return self.tuple_ptr.get_permission()

  def get_address(self):
    return self.tuple_ptr.get_address()
  
  def get_ptr_path(self):
    return self.tuple_ptr.get_ptr_path()

  def extended_path(self, offset):
    return self.tuple_ptr.get_ptr_path() + [self.start + self.step * offset]

  def set_permission(self, perm):
    self.tuple_ptr.set_permission(perm)

  def get_kill_when_zero(self):
    return self.tuple_ptr.get_kill_when_zero()

  def kill(self, mem, location, progress=set()):
    pass

  def duplicate(self, percentage, location):
    return SliceValue(self.tuple_ptr.duplicate(percentage, location),
                      self.start, self.stop, self.step)

  def transfer(self, percent, source, location):
    self.tuple_ptr.transfer(percent, source, location)

  def upgrade(self, location):
    return self.tuple_ptr.upgrade(location)
    
  def get_subobject(self, path, loc, mem):
    if len(path) == 0:
      return self
    else:
      i = path[0]
      index = self.start + i * self.step
      tup = mem.read(self.tuple_ptr)
      return tup.get_subobject([i] + path[1:], loc, mem)
    
# The primitive `split` operator

def interp_split(vals, machine, location):
    ptr = vals[0]
    ptr1 = ptr.duplicate(Fraction(1, 2), location)
    ptr2 = ptr.duplicate(Fraction(1, 1), location)
    return TupleValue([ptr1, ptr2])

set_primitive_interp('split', interp_split)

def type_check_split(arg_types, location):
  assert len(arg_types) == 1
  assert isinstance(arg_types[0], PointerType) \
    or isinstance(arg_types[0], AnyType)
  return TupleType(location, (arg_types[0], arg_types[0]))

set_primitive_type_check('split', type_check_split)
  
# The primitive `len` operator

def interp_len(vals, machine, location):
  tup = vals[0]
  if not isinstance(tup, TupleValue):
      error(location, 'in len, expected a tuple, not ' + str(tup))
  return Number(len(tup))

set_primitive_interp('len', interp_len)

def type_check_len(arg_types, location):
  assert len(arg_types) == 1
  assert isinstance(arg_types[0], ArrayType) \
    or isinstance(arg_types[0], TupleType) \
    or isinstance(arg_types[0], AnyType)
  return IntType(location)
    
set_primitive_type_check('len', type_check_len)

# Array creation

@dataclass
class Array(Exp):
  size: Exp
  arg: Exp
  __match_args__ = ("size","arg")
  
  def __str__(self):
      return "[" + str(self.size) + " of " + str(self.arg) + "]" 
    
  def __repr__(self):
      return str(self)
    
  def free_vars(self):
      return self.size.free_vars() | self.arg.free_vars()

  def const_eval(self, env):
    new_size = self.size.const_eval(env)
    new_arg = self.arg.const_eval(env)
    return Array(self.location, new_size, new_arg)
  
  def type_check(self, env, ctx):
    size_type, new_size = self.size.type_check(env, 'none')
    arg_type, new_arg = self.arg.type_check(env, 'let')
    if not (isinstance(size_type, IntType)
            or isinstance(size_type, AnyType)):
        static_error(self.location, "expected integer array size, not "
                     + str(size_type))
    return ArrayType(self.location, arg_type), \
           Array(self.location, new_size, new_arg)

  # TODO: compare the ownership transfer here to that of tuple creation.
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

# Tuple Creation

@dataclass
class TupleExp(Exp):
  inits: list[Exp]
  __match_args__ = ("inits",)

  def __str__(self):
      return '⟨' + ', '.join([str(e) for e in self.inits]) + '⟩'

  def __repr__(self):
      return str(self)

  def free_vars(self):
      return set().union(*[init.free_vars() for init in self.inits])

  def const_eval(self, env):
    new_inits = [init.const_eval(env) for init in self.inits]
    return TupleExp(self.location, new_inits)
    
  def type_check(self, env, ctx):
    init_types = []
    new_inits = []
    for init in self.inits:
        init_type, new_init = init.type_check(env, 'write_rhs')
        init_types.append(init_type)
        new_inits.append(new_init)
    return TupleType(self.location, tuple(init_types)), \
           TupleExp(self.location, new_inits)

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

# Element Access

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

  def const_eval(self, env):
    new_arg = self.arg.const_eval(env)
    new_index = self.index.const_eval(env)
    return Index(self.location, new_arg, new_index)
    
  def type_check(self, env, ctx):
    arg_type, new_arg = self.arg.type_check(env, ctx)
    index_type, new_index = self.index.type_check(env, 'none')
    new_self = Index(self.location, new_arg, new_index)
    arg_type = unfold(arg_type)
    if isinstance(arg_type, TupleType):
      if isinstance(self.index, Int):
        if 0 <= self.index.value \
           and self.index.value < len(arg_type.member_types):
          return arg_type.member_types[self.index.value], new_self
                 
        else:
          static_error(self.location, 'index ' + str(self.index.value)
                + ' out of bounds for pointer ' + str(arg_type))
      else:
        static_error(self.location,
                     'in subscript, expected an integer index, not '
                     + str(self.index))
    elif isinstance(arg_type, ArrayType):
      return arg_type.element_type, new_self
    elif isinstance(arg_type, AnyType):
      return AnyType(self.location), new_self
    else:
      static_error(self.location, 'in subscript, expected tuple or array, not '
                   + str(arg_type))
      
  def step(self, runner, machine):
    if runner.state == 0:
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
        val = tup.get_subobject([int(i)], self.location, machine.memory)
        if runner.results[0].temporary:
            val = val.duplicate(tup_ptr.get_permission(), self.location)
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

@dataclass
class Slice(Exp):
  arg: Exp
  start: Exp
  stop: Exp
  step_size: Exp
  __match_args__ = ("arg", "start", "stop", "step_size")

  def __str__(self):
      return str(self.arg) + "[" + str(self.start) \
          + ":" + str(self.stop) + ":" + str(self.step_size) + "]"
  
  def __repr__(self):
      return str(self)
  
  def free_vars(self):
      return self.arg.free_vars() | self.start.free_vars() \
          | self.stop.free_vars() | self.step_size.free_vars() 
  
  def const_eval(self, env):
    new_arg = self.arg.const_eval(env)
    new_start = self.start.const_eval(env)
    new_stop = self.stop.const_eval(env)
    new_step = self.step_size.const_eval(env)
    return Slice(self.location, new_arg, new_start, new_stop, new_step)

  def type_check(self, env, ctx):
    arg_type, new_arg = self.arg.type_check(env, ctx)
    start_type, new_start = self.start.type_check(env, 'none')
    require_consistent(start_type, IntType(self.location),
                       'start of slice must be an integer', self.location)
    stop_type, new_stop = self.stop.type_check(env, 'none')
    require_consistent(stop_type, IntType(self.location),
                       'stop of slice must be an integer', self.location)
    step_type, new_step = self.step_size.type_check(env, 'none')
    require_consistent(step_type, IntType(self.location),
                       'step of slice must be an integer', self.location)
    new_self = Slice(self.location, new_arg, new_start, new_stop, new_step)
    if isinstance(arg_type, ArrayType):
        return arg_type, new_self
    else:
      static_error(self.location, 'in slice, expected array, not '
                   + str(arg_type))

  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.arg, runner.env,
                       AddressCtx(runner.context.duplicate))
    elif runner.state == 1:
      machine.schedule(self.start, runner.env)
    elif runner.state == 2:
      machine.schedule(self.stop, runner.env)
    elif runner.state == 3:
      machine.schedule(self.step_size, runner.env)
    else:
      tup_ptr = runner.results[0].value
      start = runner.results[1].value
      stop = runner.results[2].value
      step_size = runner.results[3].value
      result = SliceValue(tup_ptr, start.value, stop.value, step_size.value)
      # Even though we're returnig a new value, it's really just
      # a view through an existing pointer, so no, not a temporary. 
      machine.finish_expression(Result(False, result), self.location)
        
# TODO partition

# for_in loop
@dataclass
class ForIn(Stmt):
  param: Param
  arg: Exp
  body: Stmt
  __match_args__ = ("param", "arg", "body")
  
  def __str__(self):
      return "for " + str(self.param) + " in " + str(self.arg) + "\n" \
          + str(self.body)
    
  def __repr__(self):
      return str(self)
    
  def free_vars(self):
      return self.arg.free_vars() \
          | (self.body.free_vars() - set([self.param.ident]))

  def const_eval(self, env):
    new_param = self.param.with_type(simplify(self.param.type_annot, env))
    new_arg = self.arg.const_eval(env)
    new_body = self.body.const_eval(env)
    return ForIn(self.location, new_param, new_arg, new_body)
    
  def type_check(self, env):
    arg_type, new_arg = self.arg.type_check(env, 'none')
    body_env = copy_type_env(env)
    self.param.bind_type(body_env)
    body_type, new_body = self.body.type_check(body_env)
    return body_type, \
           ForIn(self.location, self.param, new_arg, new_body)

  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.arg, runner.env, AddressCtx())
    elif runner.state == 1:
      runner.tuple_ptr = runner.results[0].value
      tup = machine.memory.read(runner.tuple_ptr, self.location)
      if not isinstance(tup, TupleValue):
        error(self.location, 'expected a tuple, not ' + str(tup))
      if isinstance(runner.tuple_ptr, SliceValue):
        runner.tuple_len = len(runner.tuple_ptr)
      else:
        runner.tuple_len = len(tup)
    elif runner.state - 2 < runner.tuple_len:
        # deallocate the previous iteration's binding
        if runner.state > 2:
            self.param.dealloc(machine.memory,
                               runner.results[runner.state - 2],
                               runner.body_env, self.location)
        # bind the current element
        runner.body_env = runner.env.copy()
        index = runner.state - 2
        res = Result(False, PointerOffset(runner.tuple_ptr, index))
        runner.results.append(res)
        self.param.bind(res,
                        runner.body_env, machine.memory, self.arg.location)
        # schedule the body of the loop
        machine.schedule(self.body, runner.body_env)
    else:
      # deallocate the last iteration's binding
      if runner.tuple_len > 0:
          self.param.dealloc(machine.memory, runner.results[runner.state - 3],
                             runner.body_env, self.location)
      machine.finish_statement(self.location)
