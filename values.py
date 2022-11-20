from dataclasses import dataclass
import numbers
from fractions import Fraction
from typing import Any
from ast_base import Stmt
from utilities import *

# Result of an expression
# includes the result value and whether it's a temporary. 
@dataclass
class Result:
    temporary: bool
    value: Value
    # The permission at the time of binding to a `let` variable
    permission: Fraction = Fraction(0,1)

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
        return repr(self.value).lower()
    def __repr__(self):
        return str(self)

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
    kill_when_zero: bool = False # kill when permission goes to zero (let-bound)
    no_give_backs: bool = False  # (var-bound)
    
    __match_args__ = ("address", "path", "permission")

    def is_pointer(self):
        return True
    
    def get_kill_when_zero(self):
        return self.kill_when_zero
    
    def get_address(self):
        return self.address

    def set_address(self, addr):
        self.address = addr
    
    def get_ptr_path(self):
        return self.path

    def extended_path(self, offset):
        return self.path + [offset]
    
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
        if self.address is None:
          return 'null'
        if verbose():
            return "ptr(" + str(self.address) + '.' + self.path_str(self.path) \
                + "@" + priv_str(self.permission) \
                + "(" + short_id(self) + ")" \
                + ("->" + short_id(self.lender) if not self.lender is None\
                   else "") \
                + ")"
        else:
            return 'ptr(' + str(self.address) + '.' + self.path_str(self.path) \
                + ' @ ' + priv_str(self.permission) + ')'
      
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
        if verbose():
            return str(self.address) + '.' + self.path_str(self.path) \
                + '@' + str(self.permission) + ' ' \
                + '(' + str(id(self)) + ')'
        else:
            return str(self.address) + '.' + self.path_str(self.path) \
                + '@' + str(self.permission)

    def gen_graphviz(self, addr):
      if addr is None:
        name = str(id(self))
        base = ''
        result = ''
      else:
        name = str(addr)
        base = '<base> ' + str(addr) + ': |<ptr> '
        # add node
        result = name + ' [shape=record,label="' + \
          base + self.node_label() + '"];\n'
        # add edge
        result += name + ' -> ' + str(self.address) + ';\n'
      return result, str(self.address), self.node_label()

    def transfer(self, percent, source, location):
        if not source.is_pointer():
            error(location, "in transfer, expected pointer, not " + str(source))
        if self.address != source.get_address():
            error(location, "cannot transfer between different addresses: "
                  + str(self.address) + " != " + str(source.address))
        amount = source.get_permission() * percent
        source.set_permission(source.get_permission() - amount)
        if source.get_kill_when_zero() \
           and source.get_permission() <= Fraction(0,1):
            source.set_address(None)
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
            assert(self.permission >= 0)
            if self.kill_when_zero and self.permission <= Fraction(0,1):
              self.address = None
        if tracing_on():
          print('duplicated ' + str(self) + '\n\tinto ' + str(ptr))
        return ptr

    # OBSOLETE?
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
        if self.lender is None or self.no_give_backs:
            if self.permission == Fraction(1,1):
              mem.deallocate(self.get_address(), location, progress)
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
    offset: Any

    def is_pointer(self):
        return True
    
    def get_kill_when_zero(self):
        return self.ptr.get_kill_when_zero()
    
    def get_pointer(self):
        return self.ptr.get_pointer()
    
    def get_address(self):
        return self.ptr.get_address()

    def set_address(self, addr):
        self.ptr.set_address(addr)
    
    def get_ptr_path(self):
        return self.ptr.extended_path(self.offset)

    def extended_path(self, offset):
        return self.ptr.extended_path(self.offset) + [offset]
    
    def get_permission(self):
        return self.ptr.get_permission()

    def set_permission(self, perm):
        return self.ptr.set_permission(perm)
    
    def duplicate(self, percentage, location):
        # ptr = self.ptr.duplicate(percentage, location)
        # ptr.path = ptr.path + [self.offset]
        # if tracing_on():
        #     print('duplicating PointerOffset to produce\n\t '
        #           + str(ptr))
        # return ptr
        return PointerOffset(self.ptr.duplicate(percentage, location),
                             self.offset)

    def transfer(self, percent, source, location):
        self.ptr.transfer(percent, source, location)
    
    def kill(self, mem, loc):
        # TODO: change to just kill the part
        # kill the whole thing
        self.ptr.kill(mem, loc)
        
    def upgrade(self, location):
        return self.ptr.upgrade(location)

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
        
def duplicate_if_temporary(result: Result, loc):
  if result.temporary:
    tmp = True
    val = result.value.duplicate(1, loc)
  else:
    tmp = False
    val = result.value
  return Result(tmp, val)
