from dataclasses import dataclass
from ast_base import Value
from values import Pointer

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
