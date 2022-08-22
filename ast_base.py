from dataclasses import dataclass
from lark.tree import Meta

@dataclass
class Value:
  def node_name(self):
    return str(self)
  
  def node_label(self):
    return str(self)

  def get_subobject(self, path, loc):
    if len(path) == 0:
      return self
    else:
      error(loc, 'in get_subobject, this value has no sub-parts: ' + str(self))

  def set_subobject(self, path, val, loc):
    if len(path) == 0:
      return val
    else:
      error(loc, 'in set_subobject, this value has no sub-parts: ' + str(self))
      
  def gen_graphviz(self, addr):
    if addr is None:
      return '', None, self.node_label()
    else:
      graph = str(addr) + ' [shape=record,label="' \
             + '<base> ' + str(addr) + ': |' \
             + self.node_label() \
             + '"];\n'
      return graph, str(addr), self.node_label()

@dataclass
class Void(Value):
  def kill(self, mem, loc, progress=set()):
    pass
  def clear(self, mem, loc, progress=set()):
    pass
  def duplicate(self, percentage, location):
    pass

@dataclass
class AST:
    location: Meta
    
    def debug_skip(self):
      return False

@dataclass
class Exp(AST):
    pass

@dataclass
class Stmt(AST):
    pass

@dataclass
class Decl(AST):
  def declare(self, env, mem):
    env[self.name] = mem.allocate(Void())


@dataclass(frozen=True)
class Type:
    location: Meta
