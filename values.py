from dataclasses import dataclass
import numbers
from fractions import Fraction
from typing import Any
from ast_base import Stmt
from utilities import *
from graphviz import log_graphviz

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
        if tracing_on():
          print('transferred ' + str(amount) + ' from ' + str(other) + ' to '
                + str(self))

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
        return 'fun ' + str(self.name) + '(' + ', '.join([ptr.node_label() for x, ptr in self.env.items()]) + ')'
    

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

@dataclass(eq=False)
class Module(Value):
    name: str
    exports: dict[str, Value]
    members: dict[str, Value] # all the members
    __match_args__ = ("name", "exports")
    def duplicate(self, percentage):
        exports_copy = {x: val.duplicate(percentage) \
                        for x,val in self.exports.items()}
        return Module(self.name, exports_copy)
    def __str__(self):
      return self.name + '{' + ','.join([x + '=' + str(v) for x,v in self.exports.items()]) + '}'
    def __repr__(self):
        return str(self)
    def kill(self, mem, location, progress=set()):
        if tracing_on():
          print('*** killing module ' + self.name + ' (' + str(id(self)) + ')')
        delete_env(self.name, self.members, mem, location)
        if tracing_on():
          print('*** finished killing module ' + self.name + ' (' + str(id(self)) + ')')
    def clear(self, mem, location, progress=set()):
        for val in self.members.values():
          val.clear(mem, location, progress)
    def node_name(self):
        return str(self.name)
    def node_label(self):
        return str(self.name)

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

def delete_env(label, env, mem, loc):
  changed = True
  while changed:
    changed = False
    deletes = set()
    for x, ptr in env.items():
      if ptr.permission == Fraction(1,1):
        if tracing_on():
            print('kill env ' + x)
        ptr.kill(mem, loc)
        deletes |= set([x])
        changed = True
      else:
        # this is to deal with cycles due to recursive functions -Jeremy
        ptr.clear(mem, loc)
      if tracing_on():
        log_graphviz(label, env, mem.memory)
    for x in deletes:
        del env[x]
        
