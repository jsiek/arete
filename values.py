from dataclasses import dataclass
import numbers
from fractions import Fraction
from typing import Any
from ast_base import Stmt
from utilities import *

@dataclass
class Value:
    def node_name(self):
        return str(self)
    def node_label(self):
        return str(self)

# Result of an expression
# includes the result value and whether it's a temporary. 
@dataclass
class Result:
    temporary: bool
    value: Value

@dataclass
class Void(Value):
  def kill(self, mem, loc, progress=set()):
    pass
  def clear(self, mem, loc, progress=set()):
    pass
  def duplicate(self, percentage, location):
    pass

@dataclass
class Number(Value):
  value: numbers.Number
  def equals(self, other):
    return self.value == other.value
  def duplicate(self, percentage, location):
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
    def duplicate(self, percentage, location):
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
    
    def duplicate(self, percentage, loc):
      return TupleValue([elt.duplicate(percentage, loc) for elt in self.elts])
    
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

def short_id(object):
    s = str(id(object))
    return s[len(s)-4:]

@dataclass
class Pointer(Value):
    address: int
    path: list[int]      # the path through nested tuples
    permission: Fraction   # none is 0, read is 1/n, write is 1/1
    lender: Value          # who this pointer borrowed from, if any
    kill_zero: bool = False # kill when permission goes to zero (let-bound)
    
    __match_args__ = ("address", "path", "permission")

    def get_address(self):
        return self.address

    def get_path(self):
        return self.path
    
    def get_pointer(self):
        return self
    
    def get_permission(self):
        return self.permission

    def set_permission(self, perm):
        self.permission = perm
    
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
          + "(" + short_id(self) + ")" \
          + ("->" + short_id(self.lender) if not self.lender is None else "") \
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

    def transfer(self, percent, source, location):
        if not isinstance(source, Pointer):
            error(location, "in transfer, expected pointer, not " + str(source))
        if self.address != source.address:
            error(location, "cannot transfer between different addresses: "
                  + str(self.address) + " != " + str(source.address))
        amount = source.permission * percent
        source.permission -= amount
        if source.kill_zero and source.permission <= Fraction(0,1):
            source.address = None
        self.permission += amount
        if tracing_on():
          print('transferred ' + str(amount) + ' from ' + str(source) + ' to '
                + str(self))

    def upgrade(self, location):
        self.lender = find_lender(self.lender)
        if self.lender is None:
            pass
        else:
            self.transfer(Fraction(1,1), self.lender, location)
        return self.permission == Fraction(1,1)
        
    def duplicate(self, percentage, location):
        if self.address is None:
            ptr = Pointer(None, [], Fraction(1,1), self)
        else:
            other_priv = self.permission * percentage
            ptr = Pointer(self.address, self.path, other_priv, self)
            self.permission -= other_priv
            if self.kill_zero and self.permission <= Fraction(0,1):
              self.address = None
        if tracing_on():
          print('duplicated ' + str(self) + '\n\tinto ' + str(ptr))
        return ptr
    
    def element_address(self, i, percentage, location):
        other_priv = self.permission * percentage
        self.permission -= other_priv
        ptr = Pointer(self.address, self.path + [i], other_priv, self)
        if tracing_on():
          print('element address ' + str(self) + ' into ' + str(ptr))
        return ptr

    # TODO: change to just kill the part specified by the path?
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
              error(location, 'memory leak, killing pointer'
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

# This class is needed to avoid prematurely duplicating a Pointer.        
@dataclass
class PointerOffset(Value):
    ptr: Pointer
    offset: int

    def get_pointer(self):
        return self.ptr.get_pointer()
    
    def get_address(self):
        return self.ptr.get_address()

    def get_path(self):
        return self.ptr.get_path() + [self.offset]
    
    def get_permission(self):
        return self.ptr.get_permission()

    def set_permission(self, perm):
        return self.ptr.set_permission(perm)
    
    def duplicate(self, percentage, location):
        other_priv = self.ptr.get_permission() * percentage
        self.ptr.set_permission(self.ptr.get_permission() - other_priv)
        ptr = Pointer(self.ptr.get_address(),
                       self.ptr.get_path() + [self.offset],
                       other_priv, self.get_pointer())
        if tracing_on():
            print('duplicating PointerOffset to produce\n\t '
                  + str(ptr))
        return ptr

    def kill(self, mem, loc):
        # TODO: change to just kill the part
        # kill the whole thing
        self.ptr.kill(mem, loc)
        
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
    def duplicate(self, percentage, loc):
        return self
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
    exports: dict[str, Pointer] # only the exports
    members: dict[str, Pointer] # all the members
    __match_args__ = ("name", "exports")
    def duplicate(self, percentage, loc):
        exports_copy = {x: val.duplicate(percentage, loc) \
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
    for x in deletes:
        del env[x]
        
