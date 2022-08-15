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
  def read(self, ptr, location, duplicate=True):
      if not (isinstance(ptr, Pointer) or isinstance(ptr, PointerOffset)):
          error(location, 'in read expected a pointer, not ' + str(ptr))
      if duplicate and none(ptr.get_permission()):
          error(location, 'pointer does not have read permission: ' + str(ptr))
      if not self.valid_address(ptr.get_address()):
          error(location, 'in read, bad address: ' + str(ptr.address))

      val = self.raw_read(ptr.get_address(), ptr.get_path(), location)
      #percent = Fraction(1,1)
      percent = ptr.get_permission()
      if duplicate:
        retval = val.duplicate(percent, location)
      else:
        retval = val
      if tracing_on():
          print('read from ' + str(ptr))
          print('    value: ' + str(self.memory[ptr.get_address()]))
          print('    producing: ' + str(retval))
      return retval

  def unchecked_write(self, ptr, val, location):
      address = ptr.get_address()
      path = ptr.get_path()
      old_val = self.get_tuple_element(self.memory[address], path, location)
      val_copy = val.duplicate(1, location)
      self.memory[address] = \
          self.set_tuple_element(self.memory[address],
                                 path, val_copy, location)
      if tracing_on():
        print('wrote ' + str(val_copy) + ' into ' + str(ptr))
      old_val.kill(self, location)
    
  def write(self, ptr, val, location):
      if not (isinstance(ptr, Pointer) or isinstance(ptr, PointerOffset)):
          error(location, 'in write expected a pointer, not ' + str(ptr))
      if not writable(ptr.get_permission()):
          error(location, 'pointer does not have write permission: ' + str(ptr))
      if not self.valid_address(ptr.get_address()):
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

def bind_param(param, res : Result, env, mem, loc):
  val = res.value
  if not (isinstance(val, Pointer) or isinstance(val, PointerOffset)):
    error(loc, 'for binding, expected a pointer, not ' + str(val))
  if res.temporary:
    # what if val is a PointerOffset??
    env[param.ident] = val
    
  if param.kind == 'let':
    if (not val.get_address() is None) \
         and val.get_permission() == Fraction(0,1):
      error(loc, 'let binding requires non-zero permission, not '
            + str(val))
    if not res.temporary:      
      env[param.ident] = val.duplicate(Fraction(1,2), loc)
    env[param.ident].kill_zero = True

  elif param.kind == 'var' or param.kind == 'inout':
    if val.get_permission() != Fraction(1,1):
      error(loc, param.kind + ' binding requires permission 1/1, not '
            + str(val))
    if not res.temporary:
      env[param.ident] = val.duplicate(Fraction(1,1), loc)
      if param.kind == 'var':
        val.kill(mem, loc)

  # The ref kind is not in Val. It doesn't guarantee any
  # read/write ability and it does not guarantee others
  # won't mutate. Unline `var`, it does not consume the
  # initializing value.
  elif param.kind == 'ref':
    if not res.temporary:
      env[param.ident] = val.duplicate(Fraction(1,1), loc)
        
  # the def form is OBSOLETE
  elif param.kind == 'def':  
    if param.privilege == 'write':
      if val.get_permission() != Fraction(1,1):
        error(loc, 'need writable pointer, not ' + str(val))
      if not res.temporary:
        env[param.ident] = val.duplicate(Fraction(1,1), loc)
    elif param.privilege == 'read' and (not val.address is None):
      if val.permission == Fraction(0,1):
        error(loc, 'need readable pointer, not ' + str(val))
      if not res.temporary:
        env[param.ident] = val.duplicate(Fraction(1,2), loc)
  else:
    error(loc, 'unrecognized kind of parameter: ' + param.kind)
    
def inout_end_of_life(ptr, source, loc):
    if ptr.permission != Fraction(1,1):
        error(loc, 'failed to restore inout variable '
              + 'to full\npermission by the end of its scope')
    if source.address is None:
        error(loc, "inout can't return ownership because"
              + " previous owner died")
    ptr.transfer(Fraction(1,1), source, loc)
        
def dealloc_param(param, arg, env, mem, loc):
  ptr = env[param.ident]
  if param.kind == 'inout':
    inout_end_of_life(ptr, arg.value, loc)
  ptr.kill(mem, loc)

