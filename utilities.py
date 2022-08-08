from dataclasses import dataclass
from lark.tree import Meta
import numbers
from fractions import Fraction
from typing import Any, Optional
from ast_base import *

trace = False

def set_trace(b: bool):
  global trace
  trace = b

def tracing_on():
  return trace

@dataclass
class Context:
    pass

# Want the value of the expression (not its address).
# If the value is a pointer, duplicate with the specified percentage
# of its permission.
# (rvalue)
@dataclass
class ValueCtx(Context):
  percentage : Fraction

# Want a copy of the address of the expression's result with
# the specified percentage of its permission.
# (lvalue)
@dataclass
class AddressCtx(Context):
  percentage : Fraction

# Want the address of the subexpression.
# (lvalue)
@dataclass
class ObserveCtx(Context):
  pass

def priv_to_percent(priv):
  if priv == 'write':
    return Fraction(1,1)
  elif priv == 'read':
    return Fraction(1,2)
  elif priv == 'none':
    return Fraction(0,1)
  else:
    raise Exception('in priv_to_percent, unrecognized ' + priv)

def error_header(location):
  # seeing a strange error where some Meta objects don't have a line member.
  if hasattr(location, 'line'):
    return '{file}:{line1}.{column1}-{line2}.{column2}: ' \
        .format(file=location.filename,
                line1=location.line, column1=location.column,
                line2=location.end_line, column2=location.end_column)
            
def error(location, msg):
    raise Exception(error_header(location) + msg)

def warning(location, msg):
    header = '{file}:{line1}.{column1}-{line2}.{column2}: ' \
        .format(file=location.filename,
                line1=location.line, column1=location.column,
                line2=location.end_line, column2=location.end_column)
    print(header + 'warning: ' + msg)

def allocate_locals(var_priv_vals, env, mem, location):
    for var, priv, val in var_priv_vals:
        if priv == 'write' and isinstance(val, Pointer) \
           and val.permission != Fraction(1,1):
            error(location, 'need writable pointer, not ' + str(val))
        elif priv == 'read' and isinstance(val, Pointer) \
                  and (not val.address is None) \
                  and val.permission == Fraction(0,1):
            error(location, 'need readable pointer, not ' + str(val))
        if not isinstance(val, Pointer):
          error(location, 'for variable initialization, expected a pointer, not ' + str(val))
        env[var] = val

def deallocate_locals(vars, env, mem, location):
    for var in vars:
        if tracing_on():
          print('deallocating local variable: ' + var)
        ptr = env[var]
        ptr.kill(mem, location)

compare_ops = { 'less': lambda x, y: x < y,
                'less_equal': lambda x, y: x <= y,
                'greater': lambda x, y: x > y,
                'greater_equal': lambda x, y: x >= y}

def eval_prim(op, vals, machine, location):
    match op:
      case 'copy':
        return vals[0].duplicate(1)
      case 'len':
        tup = vals[0]
        if not isinstance(tup, TupleValue):
          error(location, "in len, expected a tuple or array not " + str(tup))
        n = len(tup.elts)
        return Number(n)
      case 'equal':
        left, right = vals
        return Boolean(left.equals(right))
      case 'not_equal':
        left, right = vals
        return Boolean(not left.equals(right))
      case 'add':
        left, right = vals
        l = to_number(left, location)
        r = to_number(right, location)
        return Number(l + r)
      case 'sub':
        left = to_number(vals[0], location)
        right = to_number(vals[1], location)
        return Number(left - right)
      case 'mul':
        left = to_number(vals[0], location)
        right = to_number(vals[0], location)
        return Number(left * right)
      case 'div':
        left = to_number(vals[0], location)
        right = to_number(vals[1], location)
        return Number(Fraction(left, right))
      case 'int_div':
        left = to_number(vals[0], location)
        right = to_number(vals[1], location)
        return Number(left // right)
      case 'neg':
        val = to_number(vals[0], location)
        return Number(- val)
      case 'and':
        left = to_boolean(vals[0], location)
        right = to_boolean(vals[1], location)
        return Boolean(left and right)
      case 'or':
        left = to_boolean(vals[0], location)
        right = to_boolean(vals[1], location)
        return left or right
      case 'not':
        val = to_boolean(vals[0], location)
        return Boolean(not val)
      case 'null':
        return Pointer(None, [], Fraction(1,1), None)
      case 'is_null':
        ptr = vals[0]
        match ptr:
          case Pointer(addr, path, priv):
            return Boolean(addr is None)
          case _:
            return Boolean(False)
      case 'split':
        ptr = vals[0]
        ptr1 = ptr.duplicate(Fraction(1, 2))
        ptr2 = ptr.duplicate(Fraction(1, 1))
        # is this allocation necessary?
        #return machine.memory.allocate(TupleValue([ptr1, ptr2]))
        return TupleValue([ptr1, ptr2])
      case 'join':
        ptr1, ptr2 = vals
        ptr = ptr1.duplicate(1)
        ptr.transfer(1, ptr2, location)
        return ptr
      case 'permission':
        ptr = vals[0]
        if not isinstance(ptr, Pointer):
          error(location, "permission operation requires pointer, not "
                + str(ptr))
        return Number(ptr.permission)
      case 'upgrade':
        ptr = vals[0]
        b = ptr.upgrade(location)
        return Boolean(b)
      case cmp if cmp in compare_ops.keys():
        left, right = vals
        l = to_number(left, location)
        r = to_number(right, location)
        return Boolean(compare_ops[cmp](l, r))
      case _:
        error(location, 'unknown primitive operator ' + op)    
        
def writable(frac):
    return frac == Fraction(1, 1)

def readable(frac):
    return Fraction(0, 1) < frac and frac < Fraction(1, 1)

def none(frac):
    return frac == Fraction(0, 1)


@dataclass
class Value:
    def node_name(self):
        return str(self)
    def node_label(self):
        return str(self)

@dataclass
class Void(Value):
    def kill(self, mem, loc, progress=set()):
      pass
    def clear(self, mem, loc, progress=set()):
      pass

@dataclass(eq=False)
class Module(Value):
    name: str
    members: dict[str, Value]
    __match_args__ = ("name", "members")
    def duplicate(self, percentage):
        return self # ??
    def __str__(self):
      return self.name + '{' + ','.join([x + '=' + str(v) for x,v in self.members.items()]) + '}'
    def __repr__(self):
        return str(self)
    def kill(self, mem, location, progress=set()):
        for member in members.values:
            member.kill(mem, location, progress)
    def clear(self, mem, location, progress=set()):
        raise Exception('unimplemented')

@dataclass
class Number(Value):
  value: numbers.Number
  def equals(self, other):
    return self.value == other.value
  def initialize(self, kind, location, ret=False):
    return Number(self.value)
  def init(self, percent, location):
    return self.initialize('read', location, False)
  def duplicate(self, percentage):
    return Number(self.value)
  def return_copy(self):
    return Number(self.value)
  def kill(self, mem, location, progress=set()):
    pass
  def clear(self, mem, location, progress=set()):
    pass
  def __str__(self):
    return str(self.value)
  def __repr__(self):
    return str(self)
  def node_name(self):
    return 'num' + str(self)
  def node_label(self):
    return str(self)

@dataclass
class Boolean(Value):
    value: bool
    def equals(self, other):
        return self.value == other.value
    def initialize(self, kind, location, ret=False):
        return Boolean(False, self.value)
    def init(self, percent, location):
        return self.initialize('read', location, False)
    def duplicate(self, percentage):
        return Boolean(self.value)
    def return_copy(self):
        return Boolean(self.value)
    def kill(self, mem, location, progress=set()):
        pass
    def clear(self, mem, location, progress=set()):
        pass
    def __str__(self):
        return repr(self.value)
    def __repr__(self):
        return str(self)

@dataclass
class TupleValue(Value):
    elts: list[Value]
    
    def equals(self, other):
      raise Exception('unimplemented')
    
    def initialize(self, kind, location, ret=False):
      raise Exception('unimplemented')
    
    def init(self, percent, location):
      raise Exception('unimplemented')
    
    def duplicate(self, percentage):
      return TupleValue([elt.duplicate(percentage) for elt in self.elts])
    
    def return_copy(self):
      raise Exception('unimplemented')
    
    def kill(self, mem, location, progress=set()):
      for elt in self.elts:
        elt.kill(mem, location, progress)

    def clear(self, mem, location, progress=set()):
      for elt in self.elts:
        elt.clear(mem, location, progress)
        
    def __str__(self):
        return '⟨' + ', '.join([str(elt) for elt in self.elts]) + '⟩'
      
    def __repr__(self):
        return str(self)
      
    def node_name(self):
        return str(self)
      
    def node_label(self):
        return '|'.join(['<' + str(i) + '>' + elt.node_label() \
                         for (i,elt) in zip(range(0,len(self.elts)),
                                            self.elts)])
      
# find the first ptr in the lender chain that is not yet killed,
# i.e. that has a non-None address.
def find_lender(ptr):
   if ptr is None:
       return None
   elif ptr.address is None:
       lender = find_lender(ptr.lender)
       ptr.lender = lender
       return lender
   else:
       return ptr
   
def priv_str(priv):
  if isinstance(priv, Fraction):
    return str(priv.numerator) + '/' + str(priv.denominator)
  elif isinstance(priv, str):
    if priv == 'none':
      return 'N'
    elif priv == 'read':
      return 'R'
    elif priv == 'write':
      return 'W'
    elif priv == 'dead':
      return 'D'
    elif priv is None:
      return 'None'
  else:
    return str(priv)

@dataclass
class Pointer(Value):
    address: int
    path: list[int]      # the path through nested tuples
    permission: Fraction   # none is 0, read is 1/n, write is 1/1
    lender: Value          # who this pointer borrowed from, if any
    
    __match_args__ = ("address", "path", "permission")

    def equals(self, other):
        return self.address == other.address and self.path == other.path

    def path_str(self, path):
      if len(path) == 0:
        return ''
      elif len(path) == 1:
        return str(path[0])
      else:
        return str(path[0]) + '.' + self.path_str(path[1:])
      
    def __str__(self):
        self.lender = find_lender(self.lender)
        if self.address is None:
          return 'null'
        return "ptr(" + str(self.address) + '.' + self.path_str(self.path) \
          + "@" + priv_str(self.permission) \
          + "(" + str(id(self)) + ")" \
          + ("->" + str(id(self.lender)) if not self.lender is None else "") \
          + ")"
      
    def __repr__(self):
        return str(self)

    def node_name(self):
        if len(self.path) == 0:
          return str(self.address) + ':base'
        elif len(self.path) == 1:
          return str(self.address) + ':' + str(self.path[0])
        else:
          return str(self.address) + ':base' # TODO

    def node_label(self):
        if self.address is None:
          return 'null'
        return str(self.address) + '.' + self.path_str(self.path) \
          + '@' + str(self.permission) + ' ' \
            + '(' + str(id(self)) + ')' 

    def transfer(self, percent, other, location):
        if not isinstance(other, Pointer):
            error(location, "in transfer, expected pointer, not " + str(other))
        if self.address != other.address:
            error(location, "cannot transfer between different addresses: "
                  + str(self.address) + " != " + str(other.address))
        amount = other.permission * percent
        other.permission -= amount
        self.permission += amount

    def upgrade(self, location):
        self.lender = find_lender(self.lender)
        if self.lender is None:
            #error(location, "failed to upgrade " + str(self) + ", no lender")
            pass
        else:
            self.transfer(Fraction(1,1), self.lender, location)
        return self.permission == Fraction(1,1)
        # if not self.permission == Fraction(1,1):
        #     error(location, "failed to upgrade pointer " + str(self))
        
    def duplicate(self, percentage):
        self.lender = find_lender(self.lender)
        if self.address is None:
            ptr = Pointer(None, [], Fraction(1,1), self)
        else:
            other_priv = self.permission * percentage
            self.permission -= other_priv
            ptr = Pointer(self.address, self.path, other_priv, self)
        if tracing_on():
          print('duplicated ' + str(self) + ' into ' + str(ptr))
        return ptr
    
    def element_address(self, i, percentage):
        other_priv = self.permission * percentage
        self.permission -= other_priv
        ptr = Pointer(self.address, self.path + [i], other_priv, self)
        if tracing_on():
          print('element address ' + str(self) + ' into ' + str(ptr))
        return ptr
        
    # self: the pointer being initialized from
    # kind: the permission of the pointer to return
    def initialize(self, kind, location, ret=False):
      if kind == 'write':
          return self.duplicate(1)
      elif kind == 'read':
          if ret == True:
              return self.duplicate(1)
          else:
              return self.duplicate(Fraction(1,2))
      else:
          raise Exception('initialize unexpected permission: ' + priv)

    # self: the pointer being initialized from
    # percent: the amount of permission to take from self
    def init(self, percent, location):
        return self.duplicate(percent)
      
    # Copy the return value of a function.
    # Similar to initialize with respect to permissions, but
    # produces a temporary value.
    def return_copy(self):
      return self.duplicate(1)
          
    def kill(self, mem, location, progress=set()):
        if self.address is None:
          return
        if self.address in progress:
          return
        self.lender = find_lender(self.lender)
        if tracing_on():
          print('kill: ' + str(self) + ' ignoring ' + str(progress))
        if self.lender is None:
            if self.permission == Fraction(1,1):
              delete(self, mem, location, progress)
            elif self.permission == Fraction(0,1):
              pass # OK, someone else will delete
            else:
              warning(location, 'memory leak, killing pointer'
                    + ' without lender ' + str(self))
        else:
            self.lender.permission += self.permission
            if tracing_on():
              print('returned ' + str(self.permission)
                    + ' to ' + str(self.lender))
        self.address = None
        self.permission = Fraction(0,1)

    def clear(self, mem, location, progress=set()):
        if self.address is None:
          return
        if self.address in progress:
          return
        val = mem.memory[self.address]
        val.clear(mem, location)
      
@dataclass
class Closure(Value):
    name: str
    params: list[Any]
    return_mode: str    # 'value' or 'address'
    body: Stmt
    env: Any # needs work
    __match_args__ = ("name", "params", "return_mode", "body", "env")
    
    def duplicate(self, percentage):
      if tracing_on():
        print('duplicating closure ' + str(self))
      env_copy = {x: v.duplicate(Fraction(1,2)) for x,v in self.env.items()}
      return Closure(self.name, self.params, self.return_mode, self.body,
                       env_copy)
    
    def initialize(self, kind, location, ret=False):
        return self # ???
      
    def init(self, percent, location):
        return self.initialize('read', location, False)
      
    def kill(self, mem, location, progress=set()):
      if tracing_on():
        print('kill closure ' + str(self))
      for x, ptr in self.env.items():
        ptr.kill(mem, location, progress)
        
    def clear(self, mem, location, progress=set()):
      for x, ptr in self.env.items():
        ptr.kill(mem, location, progress)
      
    def __str__(self):
        return self.name + '(' + ', '.join([str(ptr) for x, ptr in self.env.items()]) + ')'
      
    def __repr__(self):
        return str(self)

    def node_name(self):
        return str(self.name)
      
    def node_label(self):
        return 'fun ' + str(self.name)
    

@dataclass
class Future(Value):
    thread: Any
    __match_args__ = ("thread",)
    def duplicate(self, percentage):
        return self
    def initialize(self, kind, location, ret=False):
        return self # ???
    def init(self, percent, location):
        return self.initialize('read', location, False)
    def kill(self, mem, location, progress=set()):
        pass # ???
    def clear(self, mem, location, progress=set()):
        pass # ???
    def __str__(self):
        return "future"
    def __repr__(self):
        return str(self)

def to_number(val, location):
    match val:
      case Number(value):
        return value
      case _:
        error(location, 'expected an number, not ' + str(val))

def to_integer(val, location):
    match val:
      case Number(value):
        return int(value)
      case _:
        error(location, 'expected an integer, not ' + str(val))
        
def to_boolean(val, location):
    match val:
      case Boolean(value):
        return value
      case _:
        error(location, 'expected a boolean, not ' + str(val))

def delete(ptr, mem, location, progress=set()):
    match ptr:
      case Pointer(addr, path, priv):
        if not writable(priv):
            error(location, 'delete needs writable pointer, not ' + str(ptr))
        mem.deallocate(addr, location, progress)
    
@dataclass
class Memory:
  memory: dict[int,Value]
  next_address: int

  def __init__(self):
    self.memory = {}
    self.next_address = 0

  def size(self):
    return len(self.memory)

  def __str__(self):
    return str(self.memory)

  def valid_address(self, addr):
    return addr in self.memory.keys()

  def get_block(self, addr):
    return self.memory[addr]
  
  def allocate(self, vals):
    addr = self.next_address
    self.next_address += 1
    self.memory[addr] = vals
    return Pointer(addr, [], Fraction(1,1), None)

  def deallocate(self, addr, location, progress):
    if not self.valid_address(addr):
        error(location, 'already deleted address ' + str(addr))
    if tracing_on():
      print('deallocating ' + str(addr))
    self.memory[addr].kill(self, location, progress | set([addr]))
    del self.memory[addr]

  def get_tuple_element(self, tup, path):
    if len(path) == 0:
      return tup
    else:
      if not isinstance(tup, TupleValue):
        raise Exception('expected tuple in get_tuple_element, not ' + repr(tup))
      return self.get_tuple_element(tup.elts[path[0]], path[1:])

  def set_tuple_element(self, old, path, val):
      if len(path) == 0:
        return val
      else:
        if not isinstance(old, TupleValue):
          raise Exception('expected tuple in set_tuple_element')
        tup = old
        i = path[0]
        front = tup.elts[:i]
        back = tup.elts[i+1:]
        ith = self.set_tuple_element(tup.elts[i], path[1:], val)
        if tracing_on():
          print('new middle: ' + str(ith))
        return TupleValue(front + [ith] + back)

  def raw_read(self, address, path):
    if tracing_on():
      print('raw_read(' + str(address) + ', ' + str(path) + ')')
    return self.get_tuple_element(self.memory[address], path)
      
  def read(self, ptr, location, context=ValueCtx(Fraction(1,1))):
      if not isinstance(ptr, Pointer):
          error(location, 'in read expected a pointer, not ' + str(ptr))
      if none(ptr.permission):
          error(location, 'pointer does not have read permission: ' + str(ptr))
      if not self.valid_address(ptr.address):
          error(location, 'in read, bad address: ' + str(ptr.address))

      val = self.raw_read(ptr.address, ptr.path)
      if isinstance(context, ObserveCtx):
          retval = val
      else:
          retval = val.duplicate(ptr.permission * context.percentage)
      if tracing_on():
          print('read from ' + str(ptr))
          print('    value: ' + str(self.memory[ptr.address]))
          print('    producing: ' + str(retval))
      return retval

  def unchecked_write(self, ptr, val, location):
      old_val = self.get_tuple_element(self.memory[ptr.address], ptr.path)
      val_copy = val.duplicate(1)
      self.memory[ptr.address] = \
          self.set_tuple_element(self.memory[ptr.address],
                                 ptr.path, val_copy)
      if tracing_on():
        print('wrote ' + str(val_copy) + ' into ' + str(ptr))
      old_val.kill(self, location)
    
  def write(self, ptr, val, location):
      if not isinstance(ptr, Pointer):
          error(location, 'in write expected a pointer, not ' + str(ptr))
      if not writable(ptr.permission):
          error(location, 'pointer does not have write permission: ' + str(ptr))
      if not self.valid_address(ptr.address):
          error(location, 'in write, bad address: ' + str(ptr.address))
      self.unchecked_write(ptr, val, location)

  def compute_fractions(self):
    fraction_dict = {}
    for addr in self.memory.keys():
      fraction_dict[addr] = Fraction(0,1)
    for addr in self.memory.keys():
      for v in self.memory[addr]:
        if isinstance(v, Pointer):
          fraction_dict[v.address] += v.permission
    # for addr in self.memory.keys():
    #   if (fraction[addr] != Fraction(0,1)) \
    #      and (fraction[addr] != Fraction(1,1)):
    #     print('**warning fraction[' + str(addr) + '] == ' + str(fraction[addr]))
    return fraction_dict

def generate_graphviz(env, mem):
    result = 'digraph {\n'
    result += 'overlap=scale\n'
    # nodes
    # result += 'subgraph cluster_env {\n'
    for var, val in env.items():
        if isinstance(val, Pointer):
            result += 'var_' + var + '[label="' \
                + var + ':' + val.node_label() + '"];\n'
    # result += '}\n'
    # result += 'subgraph cluster_memory {\n'
    for addr, val in mem.items():
        result += str(addr) + ' [shape=record,label="' \
            + '<base> ' + str(addr) + ': |' \
            + val.node_label() \
            + '"];\n'
    # result += '}\n'
    # edges
    for var, val in env.items():
        if isinstance(val, Pointer):
            if not (val.address is None):
                result += 'var_' + var + ' -> ' \
                    + str(val.address) + ' [len=1];\n'
    for addr, val in mem.items():
      if isinstance(val, Pointer) and not (val.address is None):
        result += str(addr) + ' -> ' + val.node_name() + ' [len=1];\n'
      elif isinstance(val, TupleValue):
        for i, elt in zip(range(0, len(val.elts)), val.elts):
          if isinstance(elt, Pointer) and not elt.address is None:
            result += str(addr) + ':' + str(i) \
              + ' -> ' + elt.node_name() + ' [len=1];\n'
    result += '}\n'
    return result

graph_number = 0
  
def log_graphviz(env, mem):
    global graph_number
    filename = "env_mem_" + str(graph_number) + ".dot"
    graph_number += 1
    file = open(filename, 'w')
    file.write(generate_graphviz(env, mem))
    file.close()
    print('log graphviz: ' + filename)
