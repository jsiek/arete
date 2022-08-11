from dataclasses import dataclass
from utilities import *
from values import *
from memory import *
from graphviz import log_graphviz

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

  def get_tuple_element(self, tup, path, loc):
    if len(path) == 0:
      return tup
    else:
      if not isinstance(tup, TupleValue):
        error(loc, 'expected tuple in get_tuple_element, not ' + repr(tup))
      return self.get_tuple_element(tup.elts[path[0]], path[1:], loc)

  def set_tuple_element(self, old, path, val, loc):
      if len(path) == 0:
        return val
      else:
        if not isinstance(old, TupleValue):
          error(loc, 'expected tuple in set_tuple_element not ' + str(old))
        tup = old
        i = path[0]
        front = tup.elts[:i]
        back = tup.elts[i+1:]
        ith = self.set_tuple_element(tup.elts[i], path[1:], val, loc)
        if tracing_on():
          print('new middle: ' + str(ith))
        return TupleValue(front + [ith] + back)

  def raw_read(self, address, path, loc):
    if tracing_on():
      print('raw_read(' + str(address) + ', ' + str(path) + ')')
    return self.get_tuple_element(self.memory[address], path, loc)

  # TODO: move duplicate logic to callers?
  def read(self, ptr, location, context=ValueCtx(True, Fraction(1,1))):
      if not isinstance(ptr, Pointer):
          error(location, 'in read expected a pointer, not ' + str(ptr))
      if none(ptr.permission):
          error(location, 'pointer does not have read permission: ' + str(ptr))
      if not self.valid_address(ptr.address):
          error(location, 'in read, bad address: ' + str(ptr.address))

      val = self.raw_read(ptr.address, ptr.path, location)
      if context.duplicate:
          retval = val.duplicate(ptr.permission * context.percentage, location)
      else:
          retval = val
      if tracing_on():
          print('read from ' + str(ptr))
          print('    value: ' + str(self.memory[ptr.address]))
          print('    producing: ' + str(retval))
      return retval

  def unchecked_write(self, ptr, val, location):
      old_val = self.get_tuple_element(self.memory[ptr.address], ptr.path,
                                       location)
      val_copy = val.duplicate(1, location)
      self.memory[ptr.address] = \
          self.set_tuple_element(self.memory[ptr.address],
                                 ptr.path, val_copy, location)
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

  # TODO: integrate with fractions in environment to get the whole story. -Jeremy
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
    #     print('**warning fraction[' + str(addr) + '] == ' + str(frrunner[addr]))
    return fraction_dict

def bind_parameter(var, privilege, val, env, mem, location):
    if privilege == 'write' and isinstance(val, Pointer) \
       and val.permission != Fraction(1,1):
        error(location, 'need writable pointer, not ' + str(val))
    elif privilege == 'read' \
         and isinstance(val, Pointer) \
         and (not val.address is None) \
         and val.permission == Fraction(0,1):
        error(location, 'need readable pointer, not ' + str(val))
    if not isinstance(val, Pointer):
      error(location, 'for variable initialization, expected a pointer, not ' + str(val))
    env[var] = val

def allocate_locals(var_priv_vals, env, mem, location):
    for var, priv, val in var_priv_vals:
        bind_parameter(var, priv, val, env, mem, location)

def deallocate_parameter(var, env, mem, location):
    if tracing_on():
      print('deallocating local variable: ' + var)
    ptr = env[var]
    ptr.kill(mem, location)
        
def deallocate_locals(vars, env, mem, location):
    for var in vars:
        deallocate_parameter(var, env, mem, location)

