from dataclasses import dataclass
import numbers
from fractions import Fraction
from typing import Any
from utilities import *

@dataclass
class Value:
    temporary: bool
    def node_name(self):
        return str(self)
    def node_label(self):
        return str(self)
    
@dataclass
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
    def kill(self, mem, location):
        for member in members.values:
            member.kill(mem, location)

@dataclass
class Number(Value):
    value: numbers.Number
    def equals(self, other):
        return self.value == other.value
    def initialize(self, kind, location, ret=False):
      if self.temporary:
          self.temporary = False
          return self
      else:
          return Number(False, self.value)
    def init(self, percent, location):
        return self.initialize('read', location, False)
    def duplicate(self, percentage):
        return Number(True, self.value)
    def return_copy(self):
      if self.temporary:
          return self
      else:
          return Number(True, self.value)
    def kill(self, mem, location):
        pass
    def __str__(self):
        return str(self.value)
    def __repr__(self):
        return str(self)

@dataclass
class Boolean(Value):
    value: bool
    def equals(self, other):
        return self.value == other.value
    def initialize(self, kind, location, ret=False):
      if self.temporary:
          self.temporary = False
          return self
      else:
          return Boolean(False, self.value)
    def init(self, percent, location):
        return self.initialize('read', location, False)
    def duplicate(self, percentage):
        return Boolean(True, self.value)
    def return_copy(self):
      if self.temporary:
          return self
      else:
          return Boolean(True, self.value)
    def kill(self, mem, location):
        pass
    def __str__(self):
        return repr(self.value)
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
  elif isinstance(priv, Fraction):
    return str(priv.numerator) + '/' + str(priv.denominator)
  else:
    return str(priv)

@dataclass
class Pointer(Value):
    address: int
    permission: Fraction    # none is 0, read is 1/n, write is 1/1
    lender: Value          # who this pointer borrowed from, if any
    
    __match_args__ = ("temporary", "address", "permission")

    def equals(self, other):
        return self.address == other.address
    
    def __str__(self):
        # return "⦅ " + str(self.address) + " @" + priv_str(self.permission) \
        #     + ", " + ("tmp" if self.temporary else "prm") \
        #     + (" from: " +str(self.lender) if not self.lender is None else "") \
        #     + "⦆" 
        return "⦅ " + str(self.address) + " @" + priv_str(self.permission) \
            + ", " + str(id(self)) \
            + "⦆"
    def __repr__(self):
        return str(self)

    def node_name(self):
        return str(self.address)

    def node_label(self):
        return str(self.address) + ' @' + str(self.permission) + ' ' \
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
        
    def duplicate(self, percentage):
        if trace:
            print('duplicating ' + str(percentage) + ' of ' + str(self))
        if self.address is None:
            ptr = Pointer(True, None, Fraction(1,1), self)
        else:
            other_priv = self.permission * percentage
            self.permission -= other_priv
            ptr = Pointer(True, self.address, other_priv, self)
        if trace:
            print('duplication producing ' + str(ptr))
        return ptr
    
    # self: the pointer being initialized from
    # kind: the permission of the pointer to return
    def initialize(self, kind, location, ret=False):
      if kind == 'write':
          # if not writable(self.permission):
          #     error(location, 'initializing writable pointer requires writable pointer, not ' + str(self))
          if self.temporary:
              self.temporary = False
              return self
          else:
              ptr = self.duplicate(1)
              ptr.temporary = False
              return ptr
      elif kind == 'read':
          if self.temporary:
              self.temporary = False
              return self
          elif ret == True:
              ptr = self.duplicate(1)
              ptr.temporary = False
              return ptr
          else:
              ptr = self.duplicate(Fraction(1,2))
              #ptr = self.duplicate(Fraction(1,1))
              ptr.temporary = False
              return ptr
      else:
          raise Exception('initialize unexpected permission: ' + priv)

    # self: the pointer being initialized from
    # percent: the amount of permission to take from self
    def init(self, percent, location):
      if self.temporary:
        self.temporary = False
        return self
      else:
        ptr = self.duplicate(percent)
        ptr.temporary = False
        return ptr
      
    # Copy the return value of a function.
    # Similar to initialize with respect to permissions, but
    # produces a temporary value.
    def return_copy(self):
      if self.temporary:
          return self
      else:
          return self.duplicate(1)
          
    def kill(self, mem, location):
        if trace:
            print('kill ' + str(self))
        self.lender = find_lender(self.lender)
        
        if self.lender is None and (not self.address is None):
            if self.permission == Fraction(1,1):
                delete(self, mem, location)
            elif self.permission != Fraction(0,1):
                warning(location, 'memory leak, killing nonempty pointer'
                        + ' without lender ' + str(self))
        if (not self.lender is None) and (not self.address is None):
            if trace:
                print('giving back ' + str(self.permission) \
                      + '  from ' + str(self))
            self.lender.permission += self.permission
            if trace:
                print('to ' + str(self.lender))
        self.address = None
        #self.permission = Fraction(1,1) # all of nothing! -Jeremy
        self.permission = Fraction(0,1)
    
@dataclass
class Offset(Value):
    ptr: Pointer
    offset: int
    def __str__(self):
        return str(self.ptr) + "[" + str(self.offset) + "]"
    def __repr__(self):
        return str(self)
    def equals(self, other):
        return self.ptr == other.ptr and self.offset == other.offset
    def duplicate(self, percentage):
        return Offset(True, self.ptr.duplicate(percentage), self.offset)
    def return_copy(self):
      if self.temporary:
          return self
      else:
          return Offset(True, self.ptr.duplicate(percentage), self.offset)
    def kill(self, mem, location):
        self.ptr.kill(mem, location)

@dataclass
class Closure(Value):
    params: list[Any]
    body: Stmt
    env: Any # needs work
    __match_args__ = ("temporary", "params", "body", "env")
    def duplicate(self, percentage):
        return self
    def initialize(self, kind, location, ret=False):
        return self # ???
    def init(self, percent, location):
        return self.initialize('read', location, False)
    def kill(self, mem, location):
        pass # ???
    def __str__(self):
        return "closure"
    def __repr__(self):
        return str(self)
    
        
