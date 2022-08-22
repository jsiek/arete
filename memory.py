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
  
  def allocate(self, val):
    addr = self.next_address
    self.next_address += 1
    self.memory[addr] = val
    return Pointer(addr, [], Fraction(1,1), None)

  def deallocate(self, addr, location, progress):
    if not self.valid_address(addr):
        error(location, 'already deleted address ' + str(addr))
    if tracing_on():
      print('deallocating ' + str(addr))
    self.memory[addr].kill(self, location, progress | set([addr]))
    del self.memory[addr]

  def raw_read(self, address, path, loc):
    if tracing_on():
      print('raw_read(' + str(address) + ', ' + str(path) + ')')
    return self.memory[address].get_subobject(path, loc)

  def read(self, ptr, location):
      if not (isinstance(ptr, Pointer) or isinstance(ptr, PointerOffset)):
          error(location, 'in read expected a pointer, not ' + str(ptr))
      if none(ptr.get_permission()):
          error(location, 'pointer does not have read permission: ' + str(ptr))
      if not self.valid_address(ptr.get_address()):
          error(location, 'in read, bad address: ' + str(ptr.address))

      retval = self.raw_read(ptr.get_address(), ptr.get_ptr_path(), location)
      if tracing_on():
          print('read from ' + str(ptr))
          print('    value: ' + str(self.memory[ptr.get_address()]))
          print('    producing: ' + str(retval))
      return retval

  def unchecked_write(self, ptr, val, location):
      address = ptr.get_address()
      path = ptr.get_ptr_path()
      old_val = self.memory[address].get_subobject(path, location)
      val_copy = val.duplicate(1, location)
      self.memory[address] = \
          self.memory[address].set_subobject(path, val_copy, location)
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


