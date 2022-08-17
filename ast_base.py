from dataclasses import dataclass
from lark.tree import Meta

@dataclass
class Value:
    def node_name(self):
        return str(self)
    def node_label(self):
        return str(self)

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
