from dataclasses import dataclass
from lark.tree import Meta
import numbers
from fractions import Fraction
from typing import Any
from ast_base import *

def error_header(location):
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

def env_init(env, var, val):
    env[var] = [val]

def env_get(env, var):
    return env[var][0]

def env_set(env, var, val):
    env[var][0] = val

def declare_locals(vars, env):
    for var in vars:
        env_init(env, var, None)

def allocate_locals(var_priv_vals, env, location):
    for var, priv, val in var_priv_vals:
        if priv == 'write' and isinstance(val, Pointer) \
           and val.permission != Fraction(1,1):
            error(location, 'need writable pointer, not ' + str(val))
        elif priv == 'read' and isinstance(val, Pointer) \
                  and (not val.address is None) \
                  and val.permission == Fraction(0,1):
            error(location, 'need readable pointer, not ' + str(val))
        env_set(env, var, val)

def deallocate_locals(vars, env, mem, location):
    for var in vars:
        v = env_get(env, var)
        if not v is None:
            v.kill(mem, location)

def kill_temp(val, mem, location):
    if not (val is None):
        if val.temporary:
            val.kill(mem, location)
        
compare_ops = { 'less': lambda x, y: x < y,
                'less_equal': lambda x, y: x <= y,
                'greater': lambda x, y: x > y,
                'greater_equal': lambda x, y: x >= y}

def eval_prim(op, vals, mem, location):
    match op:
      case 'equal':
        left, right = vals
        retval = Boolean(True, left.equals(right))
        kill_temp(left, mem, location)
        kill_temp(right, mem, location)
        return retval
      case 'not_equal':
        left, right = vals
        retval = Boolean(True, not left.equals(right))
        kill_temp(left, mem, location)
        kill_temp(right, mem, location)
        return retval
      case 'add':
        left = to_number(vals[0], location)
        right = to_number(vals[1], location)
        return Number(True, left + right)
      case 'sub':
        left = to_number(vals[0], location)
        right = to_number(vals[1], location)
        return Number(True, left - right)
      case 'mul':
        left = to_number(vals[0], location)
        right = to_number(vals[0], location)
        return Number(True, left * right)
      case 'div':
        left = to_number(vals[0], location)
        right = to_number(vals[1], location)
        return Number(True, Fraction(left, right))
      case 'neg':
        val = to_number(vals[0], location)
        return Number(True, - val)
      case 'and':
        left = to_boolean(vals[0], location)
        right = to_boolean(vals[1], location)
        return Boolean(True, left and right)
      case 'or':
        left = to_boolean(vals[0], location)
        right = to_boolean(vals[1], location)
        return Boolean(True, left or right)
      case 'not':
        val = to_boolean(vals[0], location)
        return Boolean(True, not val)
      case 'null':
        # fraction is 1/1 because null has all of nothing! -Jeremy
        return Pointer(True, None, Fraction(1,1), None)
      case 'is_null':
        ptr = vals[0]
        match ptr:
          case Pointer(tmp, addr, priv):
            retval = Boolean(True, addr is None)
          case _:
            retval = Boolean(True, False)
        kill_temp(ptr, mem, location)
        return retval
      case 'split':
        ptr = vals[0]
        ptr1 = ptr.duplicate(Fraction(1, 2))
        ptr2 = ptr.duplicate(Fraction(1, 1))
        return allocate([ptr1, ptr2], mem)
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
        return Number(True, ptr.permission)
      case cmp if cmp in compare_ops.keys():
        left, right = vals
        l = to_number(left, location)
        r = to_number(right, location)
        retval = Boolean(True, compare_ops[cmp](l, r))
        kill_temp(left, mem, location)
        kill_temp(right, mem, location)
        return retval
      case _:
        error(location, 'unknown primitive operator ' + op)
    
def writable(frac):
    return frac == Fraction(1, 1)

def readable(frac):
    return Fraction(0, 1) < frac and frac < Fraction(1, 1)

def none(frac):
    return frac == Fraction(0, 1)

next_address = 0

def allocate(vals, mem):
    global next_address
    addr = next_address
    next_address += 1
    mem[addr] = vals
    return Pointer(True, addr, Fraction(1,1), None)

def read(ptr, index, mem, location, dup):
    if not isinstance(ptr, Pointer):
        error(location, 'in read expected a pointer, not ' + str(ptr))
    if none(ptr.permission):
        error(location, 'pointer does not have read permission: ' + str(ptr))
    # whether to copy here or not?
    # see tests/fail_indirect_write
    if not ptr.address in mem.keys():
        error(location, 'in read, bad address: ' + str(ptr.address))
    if not (index < len(mem[ptr.address])):
        error(location, 'in read, index too big: ' + str(index)
              + ' for address ' + str(ptr.address))
    if dup:
        retval = mem[ptr.address][index].duplicate(ptr.permission)
    else:
        retval = mem[ptr.address][index]
    if False:
        print('read from ' + str(ptr) + '[' + str(index) + ']')
        print('    value: ' + str(mem[ptr.address][index]))
        print('    producing: ' + str(retval))
    return retval
    #return mem[ptr.address]

def write(ptr, index, val, mem, location):
    if not isinstance(ptr, Pointer):
        error(location, 'in write expected a pointer, not ' + str(ptr))
    if not writable(ptr.permission):
        error(location, 'pointer does not have write permission: ' + str(ptr))
    if not ptr.address in mem.keys():
        error(location, 'in write, bad address: ' + str(ptr.address))
    if not (index < len(mem[ptr.address])):
        error(location, 'in write, index too big: ' + str(index)
              + ' for address ' + str(ptr.address))
    mem[ptr.address][index].kill(mem, location)
    if val.temporary:
        mem[ptr.address][index] = val
    else:
        mem[ptr.address][index] = val.duplicate(1)
    mem[ptr.address][index].temporary = False

@dataclass
class Value:
    temporary: bool
    def node_name(self):
        return str(self)
    def node_label(self):
        return str(self)

@dataclass
class Void(Value):
    pass

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
        if self.address is None:
            ptr = Pointer(True, None, Fraction(1,1), self)
        else:
            other_priv = self.permission * percentage
            self.permission -= other_priv
            ptr = Pointer(True, self.address, other_priv, self)
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
        self.lender = find_lender(self.lender)
        if self.lender is None and (not self.address is None):
            if self.permission == Fraction(1,1):
                delete(self, mem, location)
            elif self.permission != Fraction(0,1):
                warning(location, 'memory leak, killing nonempty pointer'
                        + ' without lender ' + str(self))
        if (not self.lender is None) and (not self.address is None):
            self.lender.permission += self.permission
        self.address = None
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
    def kill(self, mem, location):
        pass # ???
    def __str__(self):
        return "future"
    def __repr__(self):
        return str(self)

def to_number(val, location):
    match val:
      case Number(tmp, value):
        return value
      case _:
        error(location, 'expected an integer, not ' + str(val))

def to_boolean(val, location):
    match val:
      case Boolean(tmp, value):
        return value
      case _:
        error(location, 'expected a boolean, not ' + str(val))

def delete(ptr, mem, location):
    match ptr:
      case Pointer(tmp, addr, priv):
        if not writable(priv):
            error(location, 'delete needs writable pointer, not ' + str(ptr))
        if not addr in mem.keys():
            error(location, 'already deleted address ' + str(addr))
        for val in mem[addr]:
            val.kill(mem, location)
        del mem[addr]
    

