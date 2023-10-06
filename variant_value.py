from dataclasses import dataclass
from ast_base import *

@dataclass
class Variant(Value):
  tag: str
  value: Value

  def __str__(self):
    return 'tag ' + self.tag + ':' + str(self.value)
      
  def __repr__(self):
    return str(self)

  def duplicate(self, percentage, loc):
    return Variant(self.tag, self.value.duplicate(percentage, loc))

  def kill(self, mem, location, progress=set()):
    self.value.kill(mem, location, progress)

  def get_subobject(self, path, loc, mem):
    if len(path) == 0:
      return self
    else:
      if path[0] == self.tag:
        return self.value.get_subobject(path[1:], loc, mem)
      else:
        error(loc, path[0]  + ' is not present in variant ' + str(self))

  def set_subobject(self, path, val, loc, mem):
    if len(path) == 0:
      return val
    else:
      if path[0] == self.tag:
        new_value = self.value.set_subobject(path[1:], val, loc, mem)
      else:
        error(loc, path[0]  + ' is not present in variant ' + str(self))
      return Variant(self.tag, new_value)
    
  def gen_graphviz(self, addr):
    result = ''
    subresult, elt_name, elt_label = self.value.gen_graphviz(None)
    result += subresult
    if addr is None:
      name = str(id(self))
      base = ''
    else:
      name = str(addr)
      base = '<base> ' + str(addr) + ': |'
    variant_label = base + '<' + self.tag + '>' + self.tag + '=' + elt_label
    # add node
    result += name + ' [shape=record,label="' + variant_label + '"];\n'
    # add out-edges
    if not elt_name is None:
      result += name + ':' + self.tag + ' -> ' + elt_name + ';\n'
    return result, name, '•'
